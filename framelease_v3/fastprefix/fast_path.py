"""Opt-in fast prefix for the UniDriveVLA closed-loop agent (FrameLease v3 R&D sprint 2026-11-10; not for DAC 2027).

The three wrapper-level speed-ups measured in outputs/framelease_v3/profiling/run_20261110/report.md (Sec. 6:
prefix 908 -> 436 ms, x2.09, plan deviation at the GPU non-determinism floor scale), packaged so that a closed-loop
agent can switch them on after its model is loaded. Nothing in framelease_v2/, framelease_v3/runtime/, third_party/,
any checkpoint or any config is modified; every change is an attribute of the loaded model instance, one module global
of transformers' qwen3_vl modelling file (dispatching on the registered model), or the in-memory LoRA merge.

  sdpa         Attention of the LLM, the perception expert and the action expert (the 84 Qwen3VLTextAttention modules
               of THIS model) uses torch.nn.functional.scaled_dot_product_attention instead of transformers' eager
               attention (materialised fp32 score matrices). forward_test forces _attn_implementation = 'eager' on
               every call, so the eager function itself is replaced: modeling_qwen3_vl.eager_attention_forward becomes a
               dispatcher that runs SDPA for registered modules and the original eager function for everything else
               (other models in the process, the vision tower if it ever ran eager, training, dropout, bool masks).
               Mask semantics are eager's (additive float mask sliced to the key length). The float mask is converted
               to the query dtype once per mask object; the conversion cache keys on the mask OBJECT (identity, kept
               alive by a strong reference) and its in-place version counter, so a new mask can never hit a stale
               entry (a data_ptr key, as in the profiling wrapper, can: the caching allocator reuses addresses).
  gpu_preproc  Qwen3VLWithExpertModel.embed_image_tensor with its CPU round trip (GPU -> uint8 -> PIL -> slow HF
               Qwen2VL image processor on the CPU -> GPU) replaced by an exact GPU replica of the processor's arithmetic
               (float64 rescale -> float32, (x - mean) / std in float32, temporal repeat, patchify). Everything else of
               the official method (BGR -> RGB, clamp, chunking, ViT call, deepstack / raw feature concatenation) is
               kept line by line. Pixel values are bit-identical; validation_window() checks this against the CPU
               processor (used by the agent in its discarded warm-up pass, never on the simulated timeline).
  lora_merged  peft merge_and_unload of the LLM LoRA (Qwen3VLWithExpertModel.merge_lora). Irreversible in memory.

Exactness contract: each optimization replaces or replicates upstream code whose source hash is recorded in
UPSTREAM_SOURCE_SHA256; apply_fast_prefix refuses (strict_sources=True) when the loaded upstream code differs.

Usage (the agent entry framelease_v3/fastprefix/agent_entry.py does this at the end of setup()):
    fp = apply_fast_prefix(agent.model.planning_head, ('sdpa', 'gpu_preproc', 'lora_merged'))
    with fp.validation_window():   # around the discarded warm-up forward only
        ...
    fp.raise_if_invalid(); manifest = fp.manifest()
"""
from __future__ import annotations

import contextlib
import hashlib
import inspect
import math
import textwrap
import time
import types
import weakref
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 'framelease_v3.fastprefix/1'
OPTIONS = ('sdpa', 'gpu_preproc', 'lora_merged')          # canonical order (also the application order below)
DEFAULT_OPTIONS = OPTIONS

# sha256 of textwrap.dedent(inspect.getsource(fn)), computed 2026-11-10 from the code the agent loads
# (third_party/transformers-linux 4.57.1 and third_party/UniDriveVLA-linux/Bench2Drive, both pinned by the job files).
UPSTREAM_SOURCE_SHA256 = {
    'modeling_qwen3_vl.eager_attention_forward': '8dd801c3a8d26a45507f388d43f47ff8640dd51c4ee3f9c71b3efc87a668788c',
    'modeling_qwen3_vl.repeat_kv': 'e9b1ad4a8df3194d5b12f94567c3a2dfed2c0d9833af1b8f775e5875575ff9c4',
    'Qwen3VLWithExpertModel.embed_image_tensor': 'e8a562b5c43b95efeb8baa720b74e433243be3355eed7fb5693572aa4b056678',
    'Qwen3VLWithExpertModel.merge_lora': '9d610d26b8d567fa4eb8174caa92f4c83b1ce255e06c2bc7d47f8507974fed9e',
}
REQUIRES = {'sdpa': ('modeling_qwen3_vl.eager_attention_forward', 'modeling_qwen3_vl.repeat_kv'),
            'gpu_preproc': ('Qwen3VLWithExpertModel.embed_image_tensor',),
            'lora_merged': ('Qwen3VLWithExpertModel.merge_lora',)}

# Validation pass (one prefix + 10 Euler steps): SDPA-call indices whose output is compared with the original eager
# function on the same inputs: first / last layer of the LLM (28 layers), of the perception expert and of the action
# expert in the first Euler step.
SDPA_CHECK_CALLS = (0, 27, 28, 55, 56, 83)
# Gross-error bound for those checks: relative RMS deviation ||sdpa - eager||_2 / ||eager||_2 over the valid query rows
# of one call (a wrong mask, scale or head mapping gives O(1)). History: the first rule bounded the single largest
# element (max |sdpa - eager| / max |eager| <= 0.05); it fired on bf16 tail noise of correct calls (0.061 on one
# perception-expert call of a smoke frame that had passed at 0.029 the run before: eager rounds its probabilities to
# bf16), so it was replaced by the RMS rule before any equivalence result was looked at; the max-element numbers are
# still recorded ('rel').
SDPA_CHECK_MAX_REL = 0.05
SDPA_EXPECTED_MODULES = {'llm': 28, 'perception_expert': 28, 'action_expert': 28}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def source_sha256(fn):
    return hashlib.sha256(textwrap.dedent(inspect.getsource(fn)).encode('utf-8')).hexdigest()


def parse_options(spec=None):
    """'all' / 'default' / None -> all three; 'none' / '' -> (); 'a,b' or a list -> that subset (canonical order)."""
    if spec is None:
        return DEFAULT_OPTIONS
    if isinstance(spec, str):
        s = spec.strip().lower()
        if s in ('none', 'off', ''):
            return ()
        if s in ('all', 'default', 'on'):
            return DEFAULT_OPTIONS
        items = [x.strip() for x in s.split(',') if x.strip()]
    else:
        items = [str(x).strip().lower() for x in spec]
    unknown = sorted(set(items) - set(OPTIONS))
    if unknown:
        raise ValueError(f'unknown fast-prefix options {unknown}; known: {list(OPTIONS)}')
    if len(set(items)) != len(items):
        raise ValueError(f'duplicate fast-prefix options in {items}')
    return tuple(o for o in OPTIONS if o in items)


def _true_eager(mq):
    """The original eager function even if fast-prefix dispatchers are installed on top of it."""
    fn = mq.eager_attention_forward
    seen = 0
    while getattr(fn, '_framelease_fastprefix_sdpa', None) is not None and seen < 16:
        fn = fn._framelease_fastprefix_sdpa.orig
        seen += 1
    return fn


def upstream_sources(vlm, mq):
    cls = type(vlm)
    fns = {'modeling_qwen3_vl.eager_attention_forward': _true_eager(mq), 'modeling_qwen3_vl.repeat_kv': mq.repeat_kv,
           'Qwen3VLWithExpertModel.embed_image_tensor': cls.embed_image_tensor,
           'Qwen3VLWithExpertModel.merge_lora': cls.merge_lora}
    out = {}
    for name, fn in fns.items():
        try:
            got = source_sha256(fn)
            path = inspect.getsourcefile(fn)
        except (OSError, TypeError) as e:
            got, path = f'unavailable: {e}', None
        out[name] = {'sha256': got, 'expected': UPSTREAM_SOURCE_SHA256[name], 'match': got == UPSTREAM_SOURCE_SHA256[name],
                     'file': path, 'file_sha256': sha256_file(path) if path and Path(path).is_file() else None}
    return out


# ============================================================================================== SDPA attention

class SdpaAttention:
    """Dispatcher installed as modeling_qwen3_vl.eager_attention_forward (see the module docstring)."""

    def __init__(self, torch, mq):
        self.torch, self.mq = torch, mq
        self.modules = {}                     # id(module) -> (weakref, label)
        self.counts = {}
        self.orig = None
        self.installed_fn = None
        self.stats = {'calls': 0, 'sdpa_calls': 0, 'fallback_calls': 0, 'bool_mask_fallbacks': 0,
                      'mask_conversions': 0, 'mask_cache_hits': 0}
        self._mask = None                     # (mask object, version, dtype, k_len, converted)
        self.check_calls = frozenset()
        self._window_calls = None
        self.checks = []

    def register(self, label, root):
        n = 0
        for m in root.modules():
            if isinstance(m, self.mq.Qwen3VLTextAttention):
                self.modules[id(m)] = (weakref.ref(m), label)
                n += 1
        self.counts[label] = self.counts.get(label, 0) + n
        return n

    def install(self):
        if self.installed_fn is not None:
            raise RuntimeError('SDPA dispatcher already installed')
        self.orig = self.mq.eager_attention_forward
        impl = self

        def eager_attention_forward(module, query, key, value, attention_mask, scaling, dropout=0.0, **kwargs):
            return impl(module, query, key, value, attention_mask, scaling, dropout, **kwargs)
        eager_attention_forward._framelease_fastprefix_sdpa = self
        self.installed_fn = eager_attention_forward
        self.mq.eager_attention_forward = eager_attention_forward

    def uninstall(self):
        if self.installed_fn is None:
            return
        if self.mq.eager_attention_forward is not self.installed_fn:
            raise RuntimeError('another attention wrapper was installed on top of this one; remove in reverse order')
        self.mq.eager_attention_forward = self.orig
        self.installed_fn = None
        self._mask = None

    @contextlib.contextmanager
    def suspended(self):
        """Run the block with the original global (harness only: an unmodified model in the same process)."""
        if self.installed_fn is None or self.mq.eager_attention_forward is not self.installed_fn:
            yield
            return
        self.mq.eager_attention_forward = self.orig
        try:
            yield
        finally:
            self.mq.eager_attention_forward = self.installed_fn

    def _mask_for(self, attention_mask, k_len, dtype):
        if attention_mask is None:
            return None
        c = self._mask
        if (c is not None and c[0] is attention_mask and c[1] == attention_mask._version and c[2] == dtype
                and c[3] == k_len):
            self.stats['mask_cache_hits'] += 1
            return c[4]
        torch = self.torch
        m = attention_mask[:, :, :, :k_len]
        if m.dtype != dtype:
            if m.is_floating_point() and torch.finfo(dtype).min > torch.finfo(m.dtype).min:
                # finite values below the target range would round to -inf; eager adds them finitely in fp32
                m = torch.where(torch.isneginf(m), m, m.clamp(min=torch.finfo(dtype).min))
            m = m.to(dtype)
        self._mask = (attention_mask, attention_mask._version, dtype, k_len, m)
        self.stats['mask_conversions'] += 1
        return m

    def __call__(self, module, query, key, value, attention_mask, scaling, dropout=0.0, **kwargs):
        self.stats['calls'] += 1
        entry = self.modules.get(id(module))
        if entry is None or entry[0]() is not module or module.training or dropout:
            self.stats['fallback_calls'] += 1
            return self.orig(module, query, key, value, attention_mask, scaling, dropout, **kwargs)
        torch = self.torch
        if attention_mask is not None and attention_mask.dtype == torch.bool:
            self.stats['bool_mask_fallbacks'] += 1     # eager ADDS a bool mask; SDPA would treat it as keep/drop
            return self.orig(module, query, key, value, attention_mask, scaling, dropout, **kwargs)
        k = self.mq.repeat_kv(key, module.num_key_value_groups)
        v = self.mq.repeat_kv(value, module.num_key_value_groups)
        mask = self._mask_for(attention_mask, k.shape[-2], query.dtype)
        out = torch.nn.functional.scaled_dot_product_attention(query, k, v, attn_mask=mask, dropout_p=0.0,
                                                               scale=scaling, is_causal=False)
        out = out.transpose(1, 2).contiguous()
        self.stats['sdpa_calls'] += 1
        if self._window_calls is not None:
            idx = self._window_calls
            self._window_calls += 1
            if idx in self.check_calls:
                self._check(idx, entry[1], module, query, key, value, attention_mask, scaling, out)
        return out, None

    def _check(self, idx, label, module, query, key, value, attention_mask, scaling, out):
        """Compare with the original eager function on the same inputs. Query rows whose keys are ALL masked (the
        padded prompt positions) are reported separately: eager returns the uniform average of every value there,
        the fused kernel does not, and no valid token ever attends to such a position (its key is masked for every
        row of this and of all later attention calls), so only the valid rows enter the pass / fail rule."""
        torch = self.torch
        with torch.no_grad():
            ref, _ = self.orig(module, query, key, value, attention_mask, scaling, 0.0)
            d = (out.float() - ref.float()).abs()                                # (B, Q, H, D)
            if attention_mask is not None and attention_mask.is_floating_point():
                m = attention_mask[:, :, :, :key.shape[-2]]
                dead = (m <= torch.finfo(torch.float32).min / 2).all(-1).any(1)  # (B, Q): every key masked
            else:
                dead = torch.zeros(d.shape[:2], dtype=torch.bool, device=d.device)
            live = ~dead
            dl, rl = d[live], ref.float()[live]
            mx_live = float(dl.max()) if dl.numel() else 0.0
            scale_live = float(rl.abs().max()) if rl.numel() else 0.0
            mx_dead = float(d[dead].max()) if bool(dead.any()) else None
            rms_ref = float(rl.pow(2).sum().sqrt()) if rl.numel() else 0.0
            rel_rms = (float(dl.pow(2).sum().sqrt()) / rms_ref) if rms_ref > 0 else (0.0 if mx_live == 0 else math.inf)
            self.checks.append({'call': int(idx), 'module': label, 'layer': getattr(module, 'layer_idx', None),
                                'q_len': int(query.shape[-2]), 'k_len': int(key.shape[-2]), 'dtype': str(query.dtype),
                                'fully_masked_rows': int(dead.sum()),
                                'max_abs_diff': mx_live, 'mean_abs_diff': float(dl.mean()) if dl.numel() else 0.0,
                                'max_abs_eager': scale_live,
                                'rel': (mx_live / scale_live) if scale_live > 0 else (0.0 if mx_live == 0 else math.inf),
                                'rel_rms': rel_rms,
                                'max_abs_diff_fully_masked_rows': mx_dead,
                                'max_abs_diff_all_rows': float(d.max()),
                                'finite': bool(torch.isfinite(out).all()), 'eager_finite': bool(torch.isfinite(ref).all())})
            del ref, d, dl, rl

    def describe(self):
        return {'kernel': 'torch.nn.functional.scaled_dot_product_attention (dispatcher installed as '
                          'transformers.models.qwen3_vl.modeling_qwen3_vl.eager_attention_forward)',
                'registered_modules': dict(self.counts), 'installed': self.installed_fn is not None,
                'stats': dict(self.stats)}


# ============================================================================================== GPU image preprocessing

class GpuImagePreprocess:
    """Exact GPU replica of the CPU image path of Qwen3VLWithExpertModel.embed_image_tensor (see module docstring)."""

    def __init__(self, torch, vlm):
        ip = vlm.processor.image_processor
        if not (getattr(ip, 'do_rescale', False) and getattr(ip, 'do_normalize', False)):
            raise ValueError('unexpected image processor configuration (rescale and normalize expected)')
        if getattr(ip, 'do_resize', None) is None:
            raise ValueError('unexpected image processor: no do_resize attribute')
        mean, std = [float(x) for x in ip.image_mean], [float(x) for x in ip.image_std]
        if len(mean) != 3 or len(std) != 3:
            raise ValueError('expected 3-channel mean / std')
        self.torch, self.vlm = torch, vlm
        self.params = {'processor_class': type(ip).__name__, 'rescale_factor': float(ip.rescale_factor),
                       'image_mean': mean, 'image_std': std, 'patch_size': int(ip.patch_size),
                       'temporal_patch_size': int(ip.temporal_patch_size), 'merge_size': int(ip.merge_size),
                       'do_convert_rgb': bool(getattr(ip, 'do_convert_rgb', False))}
        self.stats = {'calls': 0, 'chunks': 0, 'images': 0}
        self.validate_remaining = 0
        self.validation = {'chunks': 0, 'equal_chunks': 0, 'max_abs_diff_float32': 0.0, 'details': []}
        self._prev = None
        self.installed = False

    def pixel_values(self, ch):
        """ch: (n, 3, H, W) uint8 RGB (any device) -> (pixel_values float32 (n*gh*gw, 3*TP*P*P), grid int64 (n, 3))."""
        torch, p = self.torch, self.params
        n, C, H, W = ch.shape
        P, TP, M = p['patch_size'], p['temporal_patch_size'], p['merge_size']
        gh, gw = H // P, W // P
        if gh * P != H or gw * P != W or gh % M or gw % M:
            raise ValueError(f'image size {H}x{W} not divisible by patch {P} x merge {M}')
        mean = torch.tensor(p['image_mean'], dtype=torch.float32, device=ch.device).view(1, C, 1, 1)
        std = torch.tensor(p['image_std'], dtype=torch.float32, device=ch.device).view(1, C, 1, 1)
        x = (ch.to(torch.float64) * p['rescale_factor']).to(torch.float32)       # HF rescale: float64 product
        x = (x - mean) / std                                                       # HF normalize: float32
        x = x[:, None].expand(n, TP, C, H, W)                                      # temporal repeat of one frame
        x = x.reshape(n, 1, TP, C, gh // M, M, P, gw // M, M, P).permute(0, 1, 4, 7, 5, 8, 3, 2, 6, 9)
        pix32 = x.reshape(n * gh * gw, C * TP * P * P)
        grid = torch.tensor([[1, gh, gw]] * n, dtype=torch.int64, device=ch.device)
        return pix32, grid

    def reference(self, ch):
        """The official CPU path for one chunk (exactly embed_image_tensor's PIL + processor calls)."""
        from PIL import Image
        ip = self.vlm.processor.image_processor
        pil = [Image.fromarray(ch[j].permute(1, 2, 0).cpu().numpy()) for j in range(ch.shape[0])]
        ref = ip(images=pil, return_tensors='pt', do_resize=False)
        return ref['pixel_values'], ref['image_grid_thw']

    def _validate(self, ch, pix32, grid, model_dtype):
        torch = self.torch
        ref_pix, ref_grid = self.reference(ch)
        ref_pix = ref_pix.to(pix32.device)
        ref_grid = ref_grid.to(grid.device)
        shape_ok = ref_pix.shape == pix32.shape
        same32 = bool(shape_ok and ref_pix.dtype == pix32.dtype and torch.equal(ref_pix, pix32))
        same_model = bool(shape_ok and torch.equal(ref_pix.to(model_dtype), pix32.to(model_dtype)))
        same_grid = bool(ref_grid.shape == grid.shape and torch.equal(ref_grid.to(grid.dtype), grid))
        diff = float((ref_pix.float() - pix32.float()).abs().max()) if shape_ok else math.inf
        v = self.validation
        v['chunks'] += 1
        v['equal_chunks'] += int(same32 and same_model and same_grid)
        v['max_abs_diff_float32'] = max(v['max_abs_diff_float32'], diff)
        v['details'].append({'images': int(ch.shape[0]), 'shape': list(pix32.shape), 'equal_float32': same32,
                             'equal_model_dtype': same_model, 'equal_grid': same_grid, 'max_abs_diff': diff,
                             'reference_dtype': str(ref_pix.dtype)})
        self.validate_remaining -= 1

    def make_embed(self):
        torch, owner = self.torch, self

        def embed_image_tensor(self, images_tensor, chunk_size=6):
            imgs = images_tensor
            if imgs.shape[2] == 3:
                imgs = imgs[:, :, [2, 1, 0], :, :]
            imgs = torch.clamp(imgs, 0, 255).byte()
            B, N, C, H, W = imgs.shape
            flat = imgs.view(-1, C, H, W)
            all_embs, all_grids = [], []
            all_ds = [[] for _ in range(len(self.qwen3_vl.config.vision_config.deepstack_visual_indexes))]
            all_raw = None
            for i in range(0, flat.shape[0], chunk_size):
                ch = flat[i:i + chunk_size]
                pix32, grid = owner.pixel_values(ch)
                if owner.validate_remaining > 0:
                    owner._validate(ch, pix32, grid, self.qwen3_vl.dtype)
                pix = pix32.to(self.qwen3_vl.device, self.qwen3_vl.dtype)
                grid = grid.to(self.qwen3_vl.device)
                embs_list, deepstack_embs, raw_feature_list = self.qwen3_vl.visual(hidden_states=pix, grid_thw=grid)
                all_embs.append(embs_list)
                all_grids.append(grid)
                for ds_idx, ds_feat in enumerate(deepstack_embs):
                    all_ds[ds_idx].append(ds_feat)
                if all_raw is None:
                    all_raw = [[] for _ in range(len(raw_feature_list))]
                for raw_idx, raw_feat in enumerate(raw_feature_list):
                    all_raw[raw_idx].append(raw_feat)
                del pix, pix32
                owner.stats['chunks'] += 1
            owner.stats['calls'] += 1
            owner.stats['images'] += int(flat.shape[0])
            image_features = torch.cat(all_embs, dim=0)
            grids = torch.cat(all_grids, dim=0)
            merge = self.qwen3_vl.visual.spatial_merge_size
            feature_lens = (grids[:, 1] * grids[:, 2]) // (merge * merge)
            return (image_features, feature_lens.tolist(), grids, [torch.cat(x, dim=0) for x in all_ds],
                    [torch.cat(x, dim=0) for x in all_raw])
        return embed_image_tensor

    def install(self):
        if self.installed:
            raise RuntimeError('GPU preprocessing already installed')
        vlm = self.vlm
        self._prev = vars(vlm).get('embed_image_tensor')
        object.__setattr__(vlm, 'embed_image_tensor', types.MethodType(self.make_embed(), vlm))
        self.installed = True

    def uninstall(self):
        if not self.installed:
            return
        vlm = self.vlm
        if self._prev is None:
            vars(vlm).pop('embed_image_tensor', None)
        else:
            object.__setattr__(vlm, 'embed_image_tensor', self._prev)
        self.installed = False

    def describe(self):
        return {'replaces': 'Qwen3VLWithExpertModel.embed_image_tensor (instance attribute of the loaded model)',
                'processor': dict(self.params), 'installed': self.installed, 'stats': dict(self.stats)}


# ============================================================================================== LoRA merge

def merge_lora(torch, vlm):
    lm = vlm.qwen3_vl.model.language_model
    if not getattr(vlm, '_lora_enabled', False):
        raise RuntimeError('LoRA is not enabled on this model (absent or already merged)')
    info = {'language_model_before': type(lm).__name__,
            'lora_layers': sum(1 for m in lm.modules() if hasattr(m, 'lora_A'))}
    cfg = getattr(lm, 'peft_config', None) or {}
    for name, c in cfg.items():
        info.setdefault('peft_config', {})[name] = {'r': getattr(c, 'r', None), 'lora_alpha': getattr(c, 'lora_alpha', None),
                                                    'target_modules': sorted(map(str, getattr(c, 'target_modules', None) or []))}
    t0 = time.perf_counter()
    with torch.no_grad():
        vlm.merge_lora()
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    lm2 = vlm.qwen3_vl.model.language_model
    left = sum(1 for m in lm2.modules() if hasattr(m, 'lora_A'))
    if left or getattr(vlm, '_lora_enabled', True):
        raise RuntimeError(f'LoRA merge incomplete: {left} LoRA layers left')
    info.update(language_model_after=type(lm2).__name__, merge_wall_s=time.perf_counter() - t0,
                note='peft merge_and_unload in the weights dtype; irreversible in memory')
    return info


# ============================================================================================== handle

class FastPrefix:
    """What apply_fast_prefix did to one loaded model (manifest, statistics, validation)."""

    def __init__(self, options, sources, strict_sources):
        self.options = tuple(options)
        self.sources = sources
        self.strict_sources = bool(strict_sources)
        self.sdpa = None
        self.preproc = None
        self.lora = None
        self.applied_utc = None
        self.apply_wall_s = None
        self.validation = None
        self.versions = {}

    @property
    def active(self):
        return {'sdpa': self.sdpa is not None and self.sdpa.installed_fn is not None,
                'gpu_preproc': self.preproc is not None and self.preproc.installed,
                'lora_merged': self.lora is not None}

    @contextlib.contextmanager
    def validation_window(self, preproc_chunks=1, sdpa_calls=SDPA_CHECK_CALLS):
        """Inside: GPU preprocessing compared with the CPU processor (first preproc_chunks chunks), selected SDPA calls
        compared with the original eager function. Use around a pass whose cost is NOT charged to the timeline."""
        if self.preproc is not None:
            self.preproc.validate_remaining = int(preproc_chunks)
        if self.sdpa is not None:
            self.sdpa.check_calls = frozenset(int(x) for x in sdpa_calls)
            self.sdpa._window_calls = 0
            self.sdpa.checks = []
        t0 = time.perf_counter()
        try:
            yield self
        finally:
            sdpa_seen = None
            if self.sdpa is not None:
                sdpa_seen = self.sdpa._window_calls
                self.sdpa._window_calls = None
                self.sdpa.check_calls = frozenset()
            if self.preproc is not None:
                self.preproc.validate_remaining = 0
            self.validation = self._judge(sdpa_seen, preproc_chunks, sdpa_calls, time.perf_counter() - t0)

    def _judge(self, sdpa_seen, preproc_chunks, sdpa_calls, wall_s):
        failures = []
        out = {'utc': utc_now(), 'window_wall_s': wall_s}
        if self.preproc is not None:
            v = self.preproc.validation
            out['gpu_preproc'] = {k: v[k] for k in ('chunks', 'equal_chunks', 'max_abs_diff_float32')}
            out['gpu_preproc']['details'] = list(v['details'])
            if v['chunks'] < min(1, int(preproc_chunks)):
                failures.append('gpu_preproc: no chunk was validated')
            elif v['equal_chunks'] != v['chunks']:
                failures.append(f'gpu_preproc: {v["chunks"] - v["equal_chunks"]} of {v["chunks"]} chunks differ from the '
                                'CPU processor')
        if self.sdpa is not None:
            checks = list(self.sdpa.checks)
            out['sdpa'] = {'calls_in_window': sdpa_seen, 'checks': checks, 'rel_rms_bound': SDPA_CHECK_MAX_REL,
                           'max_rel_rms': max((c['rel_rms'] for c in checks), default=None),
                           'max_rel_max_element': max((c['rel'] for c in checks), default=None)}
            if not sdpa_seen:
                failures.append('sdpa: no attention call of the registered model went through SDPA')
            for c in checks:
                if not (c['finite'] and c['eager_finite']):
                    failures.append(f'sdpa: non-finite output at call {c["call"]} ({c["module"]})')
                elif not c['rel_rms'] <= SDPA_CHECK_MAX_REL:
                    failures.append(f'sdpa: call {c["call"]} ({c["module"]}) relative RMS deviation {c["rel_rms"]:.3g} > '
                                    f'{SDPA_CHECK_MAX_REL}')
            expected = sorted(int(x) for x in sdpa_calls if sdpa_seen is not None and int(x) < sdpa_seen)
            if sorted(c['call'] for c in checks) != expected:
                failures.append('sdpa: not every requested check ran')
        if self.lora is not None and not self.lora.get('lora_layers'):
            failures.append('lora_merged: no LoRA layer was merged')
        out['failures'] = failures
        out['ok'] = not failures
        return out

    def raise_if_invalid(self):
        if self.validation is None:
            raise RuntimeError('fast prefix was not validated')
        if not self.validation['ok']:
            raise RuntimeError('fast prefix validation failed: ' + '; '.join(self.validation['failures']))

    @contextlib.contextmanager
    def suspended(self):
        """Harness only: the original global attention function for the block (GPU preprocessing and the LoRA merge
        are attributes of this model and do not affect other models)."""
        if self.sdpa is None:
            yield
        else:
            with self.sdpa.suspended():
                yield

    def remove(self):
        """Undo sdpa and gpu_preproc (the LoRA merge cannot be undone)."""
        if self.preproc is not None:
            self.preproc.uninstall()
        if self.sdpa is not None:
            self.sdpa.uninstall()

    def stats(self):
        return {'sdpa': dict(self.sdpa.stats) if self.sdpa else None,
                'gpu_preproc': dict(self.preproc.stats) if self.preproc else None}

    def manifest(self):
        return {'schema': SCHEMA, 'options': list(self.options), 'active': self.active,
                'applied_utc': self.applied_utc, 'apply_wall_s': self.apply_wall_s,
                'sdpa': self.sdpa.describe() if self.sdpa else None,
                'gpu_preproc': self.preproc.describe() if self.preproc else None,
                'lora_merged': dict(self.lora) if self.lora else None,
                'validation': self.validation, 'upstream_sources': self.sources,
                'strict_sources': self.strict_sources, 'versions': dict(self.versions),
                'code': {'framelease_v3/fastprefix/fast_path.py': sha256_file(__file__)},
                'timeline': 'unchanged: the v2 backend times the (faster) prefix and steps with CUDA events and the '
                            'runtime charges kappa x the measured cost, exactly as for the unmodified model'}


def apply_fast_prefix(head, options=DEFAULT_OPTIONS, strict_sources=True):
    """Apply the selected optimizations to a loaded planning head (agent.model.planning_head); returns FastPrefix."""
    import torch
    import transformers
    import transformers.models.qwen3_vl.modeling_qwen3_vl as mq
    opts = parse_options(options)
    vlm = head.qwen3_vl_with_expert
    sources = upstream_sources(vlm, mq)
    bad = sorted({n for o in opts for n in REQUIRES[o] if not sources[n]['match']})
    if bad and strict_sources:
        raise RuntimeError(f'upstream code differs from the fast-prefix contract: {bad}')
    fp = FastPrefix(opts, sources, strict_sources)
    try:
        import peft
        peft_version = peft.__version__
    except ImportError:
        peft_version = None
    fp.versions = {'torch': torch.__version__, 'cuda': torch.version.cuda, 'transformers': transformers.__version__,
                   'peft': peft_version, 'gpu': torch.cuda.get_device_name() if torch.cuda.is_available() else None,
                   'modeling_qwen3_vl': mq.__file__}
    t0 = time.perf_counter()
    if 'lora_merged' in opts:
        fp.lora = merge_lora(torch, vlm)
    if 'sdpa' in opts:
        s = SdpaAttention(torch, mq)
        s.register('llm', vlm.qwen3_vl.model.language_model)      # modules() also reaches a peft-wrapped model
        s.register('perception_expert', vlm.qwen3_perception_expert)
        s.register('action_expert', vlm.qwen3_action_expert)
        n_layers = int(vlm.qwen3_vl.config.text_config.num_hidden_layers)
        want = {k: n_layers for k in SDPA_EXPECTED_MODULES}
        if s.counts != want:
            raise RuntimeError(f'unexpected attention modules {s.counts}, expected {want}')
        s.install()
        fp.sdpa = s
    if 'gpu_preproc' in opts:
        g = GpuImagePreprocess(torch, vlm)
        g.install()
        fp.preproc = g
    fp.apply_wall_s = time.perf_counter() - t0
    fp.applied_utc = utc_now()
    return fp


__all__ = ['SCHEMA', 'OPTIONS', 'DEFAULT_OPTIONS', 'UPSTREAM_SOURCE_SHA256', 'SDPA_CHECK_CALLS', 'SDPA_CHECK_MAX_REL',
           'parse_options', 'upstream_sources', 'source_sha256', 'SdpaAttention', 'GpuImagePreprocess', 'merge_lora',
           'FastPrefix', 'apply_fast_prefix']
