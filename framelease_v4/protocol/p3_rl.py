#!/usr/bin/env python3
"""Phase-3 RL production driver: dataset -> P_both -> selection -> refit -> distillation -> export -> freeze.

  cd /home/kang/Desktop/DAC && OMP_NUM_THREADS=1 nice -n 19 ionice -c 3 .conda-unidrive-linux/bin/python -I -B \
      framelease_v4/protocol/p3_rl.py run [--manifest outputs/framelease_v4/rl_data/data_manifest.json] \
      [--selection outputs/framelease_v4/tuning/selection.json] [--out outputs/framelease_v4/rl_freeze] [--n-jobs N] \
      [--stop-after STAGE] [--redo] [--no-selectable stop|adet] [--distill-shortfall stop|deploy_best] \
      [--missing-episodes stop|proceed]
  ... p3_rl.py status [--out DIR]                       (reads only; exit 0 complete, 3 incomplete, 1 inconsistent)
  ... p3_rl.py calibrate [--sizes 33,66,132] [--d-star D] [--lengths-from DATASET_DIR] [--threads 16] \
      [--smt-share 0.5] [--fast-core-ipc 1.0] [--out /tmp/P3RL/calibrate/calibration.json]
  development (never frozen, never the default output directory):
      ... p3_rl.py run --dev-dataset outputs/framelease_v4/rl_dev/smoke_20261110/dataset --dev-d-star 10 --smoke \
      --n-folds 2 [--bench-n 300] --out /tmp/P3RL/out_A
      ... p3_rl.py calibrate --sizes 11,22,44 --out outputs/framelease_v4/build/P3RL/calibration_dev.json

P3 procedure (production, once the P2 data manifest and the tuning freeze are final; one invocation at a time):
  1. ... p3_rl.py run --stop-after dataset          (the dataset and the reward identity: minutes)
  2. ... p3_rl.py calibrate --lengths-from outputs/framelease_v4/rl_freeze/dataset --d-star <d*>
     (the size and the choice-transition counts of the real RL dataset; calibrate always runs here, at P3 start: the
     development calibration outputs/framelease_v4/build/P3RL/calibration_dev.json is validated in sample only, at 11
     episodes, and assumes 20-150 choice transitions per episode where the P1-0 smoke behaviour run logged 4, so its
     prediction is conservative and is not the one that sets --n-jobs)
  3. ... p3_rl.py run --n-jobs <the recommended n_jobs>   (skips dataset, runs the selections through the freeze)
  4. ... p3_rl.py status                            (exit 0: every stage done and consistent)

Implements PROTOCOL Secs. 4.7 (RL grids: 12 candidates per family, 16-32-32-2 network), 5.1-5.9 (dataset, reward
identity, P_both, cross-fitted FQE selection, refit on all episodes, distillation, export with B_pi, RL freeze), 8.1
(P3 on CPU, ending with the test freeze; no test-route run before it), 10.1 (P3 has no run in the budget: the RL
dataset is the 132 P2 runs) and the Sec. 13.2 rule that a freeze is used only once cited there; GAP_AUDIT Sec. 3.3
rows P3-1, P3-2, P3-4, P3-5 and the Sec. 6 item 5 (a)-(c) defaults.

Stages, in chain order (resumable: each writes <out>/stages/<stage>.json atomically after its outputs, with the
sha256 of its inputs and outputs (files under <out> keyed '<out>/...', so a copied output directory checks its own
files), its parameters (with the code sha256) and the sha256 of the previous stage record; a rerun skips a stage whose
record is present and consistent and stops at an inconsistent one unless --redo, which recomputes it and every later
one; an interrupted run resumes by repeating its command, an interrupted --redo with --redo; --n-jobs is not a
parameter; nothing is recomputed in a directory whose rl_freeze.json PROTOCOL Sec. 13.2 cites):
  dataset             P2 manifest episodes -> <out>/dataset (dataset.build_dataset, test routes refused) and the
                      per-episode reward identity pre + sum r_n = official DS (|err| <= 1e-9, Sec. 5.2):
                      <out>/reward_identity.json
  p_both              P_both = Pr(|A_feas| = 2) over the decision epochs of the kappa-1.0 episodes, label below 0.05
                      (Sec. 5.8), with the value of metrics_v4.decision_metrics (the tables) alongside: their counts
                      must be equal (a difference: report, no record): <out>/p_both.json
  then per family f in (fqi, bandit, fqi_nolease) (trainers.FAMILIES; arms fl_full, fl_bandit, fl_fqi_nolease):
  select_<f>          ope.select(ds, trainers.grid(f, d_det=d*), n_folds=5, FQEConfig(), n_jobs=N) (Secs. 5.5-5.6; a
                      candidate whose training fold cannot fit it is unsupported in that fold, Amendment A6):
                      <out>/select_<f>.json
  refit_<f>           the selected candidate refit on every training episode (Sec. 5.6 rule 5): refit_<f>.{json,joblib}
  distill_<f>         trainers.distill to the 16-32-32-2 MLP (10 inputs for fqi_nolease), agreement >= 0.98, one
                      retry at 64x64 (Secs. 4.7, 5.6): <out>/distill_<f>.json
  export_<f>          trainers.export_qnet with B_pi = 100 us (Sec. 5.7), read back by qnet.load_spec:
                      <out>/qnet_<f>.json (name v4_qnet_<sha12>)
  deploy_check        GAP_AUDIT P3-2 (Secs. 5.7, 8.1): each network loaded as the evaluator agent loads it (name
                      registered by behaviour.register_utility_name, v3_shield.make_utility, FRAMELEASE_V4_QNET an
                      ABSOLUTE path: finding QNET-1), every logged decision row of the dataset's runs replayed through
                      v3_shield.decide (answer in A_feas, a_det depth = d*, bypass -> a_det^{d*}, no deviation without
                      both heads), the sha256 pin (another network's file is refused), rl/bench_qnet.py p50 / p99 with
                      the featurize+forward p99 <= B_pi: <out>/deploy_check.json (a failed check: report, no record)
  freeze              GAP_AUDIT P3-4 / Sec. 5.9: the dataset manifest (episode list, sha256 of every source log; the P2
                      manifest and the tuning freeze), the three selection reports with the FQE estimate and 90% CI,
                      the refit, the distillation agreement, the three networks (sha256, name, arm, absolute path),
                      the P_both label, the deploy check, the sha256 of every file under framelease_v4/rl, of
                      this driver and of the P2 gate modules, every deviation, the job lines (an arm is identified
                      by arm and file sha256: two not-trainable families share a name), the notes for the Sec. 13
                      entry (SEC13_NOTES), the stage chain and a sha256 list of every named file:
                      <out>/rl_freeze.json (production; entered in Sec. 13 with the test freeze, Sec. 8.1; read by
                      load_rl_freeze) or <out>/rl_freeze_dev.json (development: frozen false, never a freeze)

Inputs (production): the P2 data manifest (schema framelease_v4.p2_data_manifest/1, p2_check.py --write on PASS) and the
tuning freeze outputs/framelease_v4/tuning/selection.json (schema framelease_v4.tuning_selection/1, select_stage.py
freeze) for d* and L*, through the P2 gate p2_jobs.load_freeze: a selection.json whose sha256 PROTOCOL Sec. 13.2 does
not cite is refused, and so is an unsealed PROTOCOL.md. The manifest must name that freeze, d* and L*, and its
episodes plus its missing jobs must be runs of the registered P2 block (p2_plan: 44 training routes x kappa {1.0, 1.5,
2.0} x seed 11 = 132 runs, Sec. 5.3), each with its p2_jobs job id; a registered run it does not list is a missing
episode (open case (c)). Every episode must be the behaviour utility (eps 0.3, a_det^{d*}, the behaviour seed of its
route and kappa, Sec. 2.6), kappa in {1.0, 1.5, 2.0}, seed 11, with its run directory inside the P2 output directory
of its kappa (p2_jobs.output_dir) and source logs that still have the manifest's sha256; any test route is refused
(PermissionError). When the dataset is built, each run's own config.json (route, kappa, seed, utility) must equal its
manifest entry, and its official DS the manifest's.

Open cases of GAP_AUDIT Sec. 6 item 5 (each option defaults to 'stop', exit 4; the alternative is the audit's proposed
default, a deviation carried by the stage record and to be recorded in PROTOCOL Sec. 13 when used):
  --no-selectable adet           (a) no selectable candidate in a family (decided at refit_<f>, export_<f>): every
                                 candidate has an unsupported evaluation in some fold (Sec. 5.6 rule 3); an
                                 a_det^{d*} head without support in a training fold is a regular unsupported
                                 evaluation (Amendment A6: ope.select does not fit the candidate there; select_<f>
                                 records the folds and their per-head sample counts in the reason); the
                                 a_det^{d*}-equivalent network (both heads unsupported), family "not trainable"
  --distill-shortfall deploy_best  (b) agreement < 0.98 after the 64x64 retry (decided at export_<f>): the best try
  --missing-episodes proceed     (c) P2 jobs without a valid record after the retry, or registered P2 runs the
                                 manifest does not list (decided before dataset): the dataset is the valid episodes,
                                 the missing ones are listed
The expensive stages never rerun for an option: select_<f> and distill_<f> always record their result.
Every code change (this driver, a file under framelease_v4/rl or a P2 gate module) changes the parameters of every
stage: a resume then stops at the first stage, and --redo recomputes all of them. The code is final before the
production run starts. The chain is linear: --redo after an inconsistent record (a corrupted or changed output of one
family) recomputes that stage and every later one, including the selections of the families after it (deterministic,
so the same results, but about 0.1-0.3 h each by calibration_dev.json). One 'run' per output directory at a time
(RunLock: an exclusive lock on <out>/.p3_rl.lock; a second invocation is refused).
Exit codes (run): 0 done, 1 refused input, inconsistent record, failed check, a registered (cited) output directory
or another run holding the lock, 4 open case stopped.
Subcommand calibrate (GAP_AUDIT P3-5): serial CPU-time probes of every part of an ope.select task (fit_candidate per
cost class, FQE per iteration, the rest of a task, the behaviour calibration) on synthetic datasets of the P2 shape, a
cost law c + a n ln n per part, the production folds and FQE iterations per scenario (a_det, 10/30/50% deviation,
every transition bootstrapping), an in-sample check against one real ope.select, and list scheduling of the 36
candidates x 5 folds over the machine's cores (P/E core frequencies, SMT share): the recommended --n-jobs. Output
outside the project or under outputs/framelease_v4/build only (GAP_AUDIT: scratch).
Departures from the GAP_AUDIT wording (PROTOCOL silent; listed in the freeze for the Sec. 13 test-freeze entry,
SEC13_NOTES): the P3-2 bench is a hard gate (featurize_forward p99 <= B_pi, no deploy_check record otherwise), while
PROTOCOL Sec. 5.7 defines B_pi only as a run-time bypass; P3-5 is CPU-time component probes, a cost law and an
in-sample ope.select check, not one timing of a full ope.select at the expected size.
"""
from __future__ import annotations

import os

for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_v, '1')
os.environ['CUDA_VISIBLE_DEVICES'] = ''

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from framelease_v4.rl import common as C  # noqa: E402
from framelease_v4.rl import dataset as D  # noqa: E402
from framelease_v4.rl import features as F  # noqa: E402
from framelease_v4.rl import ope as O  # noqa: E402
from framelease_v4.rl import qnet as Q  # noqa: E402
from framelease_v4.rl import trainers as TR  # noqa: E402

THIS_REL = 'framelease_v4/protocol/p3_rl.py'
DEFAULT_OUT = ROOT / 'outputs' / 'framelease_v4' / 'rl_freeze'
P2_MANIFEST = ROOT / 'outputs' / 'framelease_v4' / 'rl_data' / 'data_manifest.json'     # = p2_check.MANIFEST_PATH
TUNING_FREEZE = ROOT / 'outputs' / 'framelease_v4' / 'tuning' / 'selection.json'      # = select_stage.FREEZE_PATH
PROTOCOL = ROOT / 'framelease_v4' / 'PROTOCOL.md'
P2_MANIFEST_SCHEMA = 'framelease_v4.p2_data_manifest/1'
STAGE_SCHEMA = 'framelease_v4.p3_rl_stage/1'
SELECT_SCHEMA = 'framelease_v4.p3_rl_selection/1'
REFIT_SCHEMA = 'framelease_v4.p3_rl_refit/1'
DISTILL_SCHEMA = 'framelease_v4.p3_rl_distill/1'
IDENTITY_SCHEMA = 'framelease_v4.p3_rl_reward_identity/1'
P_BOTH_SCHEMA = 'framelease_v4.p3_rl_p_both/1'
DEPLOY_SCHEMA = 'framelease_v4.p3_rl_deploy_check/1'
FREEZE_SCHEMA = 'framelease_v4.rl_freeze/1'
CALIBRATION_SCHEMA = 'framelease_v4.p3_rl_calibration/1'
VARIANT = 'FULL'
FAMILIES = TR.FAMILIES
ARM_OF = {'fqi': 'fl_full', 'bandit': 'fl_bandit', 'fqi_nolease': 'fl_fqi_nolease'}           # Sec. 5.6
N_FOLDS = 5                     # Sec. 5.5: 5 route-grouped folds (seed 20261110, ope.route_folds)
FOLD_SEED = 20261110            # Sec. 5.5: the fold seed (= ope.select's default)
N_BOOT = 2000                   # Sec. 5.5: route-cluster bootstrap, 2000 resamples, 90% interval
MIN_AGREEMENT = 0.98            # Secs. 4.7, 5.6: distillation agreement target (one retry at 64x64 in TR.distill)
POLICY_BUDGET_S = 1e-4          # Sec. 5.7: B_pi = 100 us
P_BOTH_MIN = 0.05               # Sec. 5.8
P_BOTH_KAPPA = 1.0              # Sec. 5.8: P_both is judged on the kappa-1.0 episodes
BENCH_N, BENCH_WARM = 20000, 2000   # rl/bench_qnet.py defaults (timed calls per path, warm-up calls)
BENCH_GATE = 'featurize_forward'    # the call QUtility.select times against B_pi (qnet.py; Sec. 5.7)
KAPPAS = (1.0, 1.5, 2.0)        # Sec. 5.3
P2_SEED = 11                    # Sec. 5.3: closed-loop seed of the P2 runs
EPS = 0.3                       # Sec. 5.3: behaviour exploration rate
REQUIRED_LOGS = ('config.json', 'raw/official_results.json', 'raw/agent/framelease/decisions.jsonl',
                 'raw/agent/framelease/ticks.jsonl')                # source logs every P2 manifest episode hashes
SOURCE_LOGS = REQUIRED_LOGS + ('raw/agent/metric_info.json',)      # + the prefix-score input when present
# GAP_AUDIT Sec. 6 item 5: cases the protocol leaves open. Each option defaults to 'stop'; the alternative is the
# proposed default of the audit, a deviation that is to be recorded in PROTOCOL Sec. 13 when used.
OPEN_CASES = {
    'no_selectable': ('stop', 'adet', '(a) a family has no selectable candidate (every candidate has an unsupported '
                      'evaluation in some fold; an a_det^{d*} head without support in a training fold is a regular '
                      'unsupported evaluation, Amendment A6): deploy the a_det^{d*}-equivalent network and label the '
                      'family "not trainable"'),
    'distill_shortfall': ('stop', 'deploy_best', '(b) the distillation agreement stays below 0.98 after the 64x64 '
                          'retry: deploy the best try and report its agreement'),
    'missing_episodes': ('stop', 'proceed', '(c) P2 jobs without a valid record after the retry (or registered P2 '
                         'runs the manifest does not list): the dataset is the valid episodes, the missing ones are '
                         'listed, nothing re-runs beyond the registered retry'),
}
RECORD_NOTE = 'to be recorded in PROTOCOL Sec. 13 when used (GAP_AUDIT Sec. 6 item 5)'
ADET_NOTE = ('not trainable: nothing was selected; the spec\'s candidate field names the simplest grid candidate of '
             'the family only for its feature columns; both heads are unsupported, so the network answers a_det^{d*} '
             'at every choice state. Its core is the same for every family with these columns (fqi and bandit: the '
             'same name v4_qnet_<sha12>), so an arm is identified by its arm and file sha256, never by the name alone')
JOB_LINES_RULE = ('one job line per arm: utility (the network name), FRAMELEASE_V4_QNET (the absolute path, finding '
                  'QNET-1) and qnet_file_sha256. Two arms may share a name (identical decision cores, e.g. two not '
                  'trainable families) and the name pins neither B_pi nor the provenance, so the job generator '
                  'identifies an arm by its arm key and pins qnet_file_sha256')
# Implementation choices where the GAP_AUDIT wording departs from PROTOCOL (which is silent): every freeze lists them
# for the Sec. 13 test-freeze entry
SEC13_NOTES = (
    'GAP_AUDIT P3-2 ("bench_qnet.py: p50 / p99 against B_pi") is a hard gate here: deploy_check passes only when the '
    'featurize_forward p99 is at most B_pi = 100 us; PROTOCOL Sec. 5.7 defines B_pi only as the run-time bypass. The '
    'gate is stricter and changes no network.',
    'GAP_AUDIT P3-5 ("time ope.select on a synthetic dataset of the expected size") is p3_rl.py calibrate: CPU-time '
    'probes of every part of an ope.select task at three sizes, a cost law c + a n ln n and one real ope.select at '
    'the smallest size as an in-sample check; it sets --n-jobs only, which is no stage parameter.',
    'GAP_AUDIT Sec. 6 item 5: an a_det^{d*} head without support in a training fold is a regular unsupported '
    'evaluation (Amendment A6: ope.select marks the candidate unsupported in that fold and continues), so open case '
    '(a) covers a family that it leaves without a selectable candidate; open case (c) also covers a registered P2 run '
    'that the P2 data manifest does not list. Either is a deviation only when used (deviations).',
)


class StageError(RuntimeError):
    """A stage cannot run or its record is inconsistent: the driver stops (exit 1); nothing later runs."""


class Stop(RuntimeError):
    """An open case of GAP_AUDIT Sec. 6 item 5 under its default 'stop' (exit 4): the user decides."""


def rel(p):
    """Path as recorded: relative to the project root when inside it, else absolute (as p1_jobs.rel: a relative path
    is relative to the project root)."""
    p = Path(p)
    p = (p if p.is_absolute() else ROOT / p).resolve()
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def abs_path(r):
    p = Path(r)
    return p if p.is_absolute() else ROOT / p


OUT_TOKEN = '<out>'


def rec_key(out, p):
    """Key of a file in a stage record: '<out>/...' for a file under the output directory (so a copied or moved
    output directory checks its own files, never the original's), else rel(p)."""
    p = Path(p)
    p = (p if p.is_absolute() else ROOT / p).resolve()
    try:
        return f'{OUT_TOKEN}/{p.relative_to(Path(out).resolve()).as_posix()}'
    except ValueError:
        return rel(p)


def rec_path(out, key):
    """Inverse of rec_key: the file a stage-record key names, for the output directory out."""
    if key == OUT_TOKEN or key.startswith(OUT_TOKEN + '/'):
        return Path(out) / key[len(OUT_TOKEN) + 1:]
    return abs_path(key)


def sha_map(paths, out):
    """{rec_key: sha256} of existing files (a missing file maps to None)."""
    res = {}
    for p in paths:
        p = Path(p)
        res[rec_key(out, p)] = C.sha256_file(p) if p.is_file() else None
    return res


def canonical_sha(obj):
    return C.sha256_bytes(json.dumps(C.jsonable(obj), sort_keys=True, separators=(',', ':')).encode())


RL_DIR = ROOT / 'framelease_v4' / 'rl'
GATE_SOURCES = ('protocol/p2_jobs.py', 'protocol/p2_check.py')    # under framelease_v4/: the input gate (S3)


def code_sha256():
    """sha256 of this driver, of every file under framelease_v4/rl (Sec. 5.9 'the sha256 of every framelease_v4/rl
    source': the modules, RL_PROTOCOL.md cited by Sec. 5.5, the README and the tests; __pycache__ excluded) and of the
    P2 modules of the input gate (p2_jobs.py: the tuning freeze gate, the plan, the job ids and output directories;
    p2_check.py: the writer of the P2 data manifest). Keys: 'p3_rl.py', 'rl/<path>', 'protocol/<name>'. Part of every
    stage's parameters."""
    rl = {f'rl/{f.relative_to(RL_DIR).as_posix()}': C.sha256_file(f) for f in sorted(RL_DIR.rglob('*'))
          if f.is_file() and '__pycache__' not in f.relative_to(RL_DIR).parts}
    return {'p3_rl.py': C.sha256_file(Path(__file__)), **rl,
            **{k: C.sha256_file(ROOT / 'framelease_v4' / k) for k in GATE_SOURCES}}


def deviation(case, used):
    """Stage-record entry of an open case decided by an option other than 'stop'."""
    return {'case': case, 'option': used, 'rule': OPEN_CASES[case][2], 'note': RECORD_NOTE}


# ============================================================================================ stage machinery

def _print(msg):
    print(msg, flush=True)


class Ctx:
    """One invocation: output directory, mode, d*, the registered (or development) parameters and the options.

    mode 'production': the dataset is built from the P2 data manifest, d* comes from the cited tuning freeze, and the
    parameters are the registered ones (full grid, 5 folds, FQEConfig(), 2000 bootstrap resamples).
    mode 'development': a prebuilt dataset directory (read-only, copied into <out>/dataset) and an explicit d*; the
    grid, folds and FQE configuration may be reduced; never in the default output directory, never frozen."""

    def __init__(self, out, mode, d_star, options, n_jobs=1, n_folds=N_FOLDS, fqe_cfg=None, grid_kind='registered',
                 n_boot=N_BOOT, manifest=None, freeze=None, dev_dataset=None, log=_print, bench_n=BENCH_N,
                 bench_warm=BENCH_WARM, protocol=PROTOCOL):
        self.out = Path(out).resolve()
        if mode not in ('production', 'development'):
            raise ValueError(f'mode {mode!r}')
        if _inside(self.out, DEFAULT_OUT) and (mode == 'development' or 'PYTEST_CURRENT_TEST' in os.environ):
            raise PermissionError(f'{rel(DEFAULT_OUT)} is written by production runs only (never by development '
                                  'runs or tests)')
        self.mode = mode
        self.d_star = int(d_star)
        self.options = dict(options)
        self.n_jobs = int(n_jobs)
        self.n_folds = int(n_folds)
        self.fqe_cfg = O.FQEConfig() if fqe_cfg is None else fqe_cfg
        self.grid_kind = grid_kind
        self.n_boot = int(n_boot)
        self.manifest = manifest          # production: {'path', 'sha256', 'doc', ...} (load_p2_manifest)
        self.freeze = freeze              # production: p2_jobs.load_freeze() result
        self.dev_dataset = None if dev_dataset is None else Path(dev_dataset).resolve()
        self.log = log
        self.bench_n, self.bench_warm = int(bench_n), int(bench_warm)
        self.protocol = Path(protocol)    # read for the Sec. 13.2 citation of <out>/rl_freeze.json (frozen_citations)
        self._ds = None

    @property
    def dataset_dir(self):
        return self.out / 'dataset'

    def dataset_files(self):
        return [self.dataset_dir / n for n in ('manifest.json', 'episodes.json', 'transitions.npz', 'epochs.npz')]

    def dataset(self):
        if self._ds is None:
            self._ds = D.load_dataset(self.dataset_dir)
        return self._ds

    def grid(self, family):
        return TR.grid(family, smoke=self.grid_kind == 'smoke', d_det=self.d_star)

    def common_params(self):
        return {'mode': self.mode, 'variant': VARIANT, 'd_star': self.d_star, 'code_sha256': code_sha256()}


class Stage:
    """A named stage: inputs(ctx) -> paths hashed before it runs, params(ctx) -> dict that defines it, run(ctx) ->
    {'outputs': [paths], 'result': {...}, 'deviations': [...]}."""

    def __init__(self, name, inputs, run, params=None):
        self.name, self.inputs, self.run = name, inputs, run
        self.params = params or (lambda ctx: {})


def record_path(out, name):
    return Path(out) / 'stages' / f'{name}.json'


def read_record(path):
    try:
        rec = C.read_json(path)
    except (OSError, ValueError):
        return None
    return rec if isinstance(rec, dict) else None


def record_problems(rec, name, prev, params, out):
    """Why a present stage record cannot be reused ([] = consistent): schema and name, the chain link to the
    previous record, the parameters (incl. code sha256), and the current sha256 of every input and output (keys
    resolved by rec_path against the output directory out)."""
    if rec is None:
        return ['unreadable record']
    probs = []
    if rec.get('schema') != STAGE_SCHEMA or rec.get('stage') != name:
        probs.append(f'not a {STAGE_SCHEMA} record of stage {name}')
    if rec.get('previous') != prev:
        probs.append(f'chain: previous {rec.get("previous")} != current {prev}')
    old = rec.get('params') or {}
    if canonical_sha(old) != canonical_sha(params):
        keys = sorted(k for k in set(old) | set(params) if canonical_sha(old.get(k)) != canonical_sha(params.get(k)))
        probs.append(f'parameters differ: {keys}')
    for group in ('inputs', 'outputs'):
        for r, sha in (rec.get(group) or {}).items():
            p = rec_path(out, r)
            cur = C.sha256_file(p) if p.is_file() else None
            if cur != sha:
                probs.append(f'{group[:-1]} {r}: sha256 {cur} != recorded {sha}')
    return probs


def run_stage(ctx, st, prev, params, produced):
    """Run one stage and write its record atomically (after its outputs). produced: {path: sha256} of the outputs
    of the earlier stages in the chain; an input that is such an output must still have that sha256."""
    t0, started = time.time(), C.utc_stamp()
    inputs = sha_map(st.inputs(ctx), ctx.out)
    missing = [r for r, h in inputs.items() if h is None]
    if missing:
        raise StageError(f'{st.name}: missing inputs {missing}')
    changed = [r for r, h in inputs.items() if r in produced and produced[r] != h]
    if changed:
        raise StageError(f'{st.name}: inputs changed since the stage that wrote them: {changed}')
    ctx.log(f'[run ] {st.name} ...')
    res = st.run(ctx) or {}
    outputs = sha_map(res.get('outputs') or [], ctx.out)
    if any(h is None for h in outputs.values()):
        raise StageError(f'{st.name}: outputs not written: {[r for r, h in outputs.items() if h is None]}')
    rec = {'schema': STAGE_SCHEMA, 'stage': st.name, 'script': THIS_REL, 'mode': ctx.mode, 'previous': prev,
           'params': params, 'inputs': inputs, 'outputs': outputs, 'result': res.get('result') or {},
           'deviations': res.get('deviations') or [], 'started_utc': started, 'finished_utc': C.utc_stamp(),
           'wall_s': round(time.time() - t0, 2),
           'host': {'n_jobs': ctx.n_jobs, 'cpu_count': os.cpu_count(), 'loadavg': list(os.getloadavg()),
                    'threads': {v: os.environ.get(v) for v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
                                                              'MKL_NUM_THREADS')}}}
    path = C.atomic_json(record_path(ctx.out, st.name), rec)
    ctx.log(f'[done] {st.name} ({rec["wall_s"]:.1f} s): {json.dumps(C.jsonable(rec["result"]))[:300]}')
    return path, rec


def frozen_citations(out, protocol=PROTOCOL):
    """Lines of PROTOCOL Sec. 13.2 that cite the sha256 of <out>/rl_freeze.json ([] when there is none or it is not
    cited). Once cited, the RL freeze is registered (Secs. 5.9, 8.1, 13.2): drive skips consistent stages in that
    directory but never recomputes one (a code change, --redo or a lost record there is a PermissionError)."""
    from framelease_v4.protocol import p2_jobs as P2J
    path = freeze_path(out, 'production')
    if not path.is_file():
        return []
    return P2J.citations(C.sha256_file(path), Path(protocol).read_text(encoding='utf-8'))


LOCK_NAME = '.p3_rl.lock'


class RunLock:
    """Exclusive fcntl.flock on <out>/.p3_rl.lock for one 'run' invocation: a second invocation on the same output
    directory would interleave stages and records, so it is refused (StageError, exit 1) while the lock is held. The
    file holds the holder's pid and start time (never empty) and stays; the kernel releases the lock when the process
    ends, also on SIGKILL, so an interrupted run is resumed without any cleanup."""

    def __init__(self, out):
        self.path, self.f = C._check_writable(Path(out) / LOCK_NAME), None

    def __enter__(self):
        import fcntl
        self.f = open(self.path, 'a+', encoding='utf-8')
        try:
            fcntl.flock(self.f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.f.seek(0)
            holder = self.f.read().strip()
            self.f.close()
            raise StageError(f'{rel(self.path)} is held by another p3_rl run ({holder or "unknown"}): one run per '
                             'output directory at a time') from None
        self.f.seek(0)
        self.f.truncate()
        self.f.write(f'pid {os.getpid()} since {C.utc_stamp()}\n')
        self.f.flush()
        return self

    def __exit__(self, *exc):
        import fcntl
        fcntl.flock(self.f.fileno(), fcntl.LOCK_UN)
        self.f.close()
        return False


def drive(ctx, stages, stop_after=None, redo=False):
    """Run the stages in order. A stage whose record is present and consistent (record_problems == []) is skipped;
    an inconsistent record stops the driver (StageError) unless redo, which recomputes that stage and every later one
    (a record after a stage recomputed in this invocation is stale even if its chain link happens to match). An
    interrupted invocation is resumed by repeating it: the interrupted stage has no record and runs again (after an
    interrupted --redo the stale records of the old chain need --redo again). Nothing is recomputed in a directory
    whose rl_freeze.json PROTOCOL Sec. 13.2 cites (frozen_citations: PermissionError). One invocation per output
    directory at a time (RunLock: another one is refused with StageError).
    Returns the list of (stage, 'skip' | 'run', record)."""
    names = [st.name for st in stages]
    if stop_after is not None and stop_after not in names:
        raise StageError(f'--stop-after {stop_after!r}: not a stage ({", ".join(names)})')
    ctx.out.mkdir(parents=True, exist_ok=True)
    with RunLock(ctx.out):
        prev, produced, done, ran, frozen = None, {}, [], None, None
        for st in stages:
            path = record_path(ctx.out, st.name)
            params = {**ctx.common_params(), **st.params(ctx)}
            rec = None
            if path.exists():
                rec = read_record(path)
                probs = record_problems(rec, st.name, prev, params, ctx.out)
                if ran is not None:
                    probs.append(f'stage {ran} before it was recomputed in this invocation')
                for dv in (rec or {}).get('deviations') or []:      # an open case decided by an option: same option
                    if isinstance(dv, dict) and dv.get('case') in OPEN_CASES and \
                            ctx.options.get(dv['case']) != dv.get('option'):
                        opt = dv['case'].replace('_', '-')
                        probs.append(f'the record used --{opt} {dv.get("option")}; pass it again')
                if probs and not redo:
                    raise StageError(f'{st.name}: record {rel(path)} is inconsistent: ' + '; '.join(probs[:6]) +
                                     ' (--redo recomputes this stage and every later one)')
                if probs:
                    ctx.log(f'[redo] {st.name}: ' + '; '.join(probs[:3]))
                    rec = None
                else:
                    ctx.log(f'[skip] {st.name} (record consistent)')
                    done.append((st.name, 'skip', rec))
            if rec is None:
                frozen = frozen_citations(ctx.out, ctx.protocol) if frozen is None else frozen
                if frozen:
                    raise PermissionError(f'{st.name}: {rel(freeze_path(ctx.out, "production"))} is cited in PROTOCOL '
                                          f'Sec. 13.2 (lines {frozen}): the RL freeze is registered and its output '
                                          'directory is never recomputed')
                path, rec = run_stage(ctx, st, prev, params, produced)
                done.append((st.name, 'run', rec))
                ran = ran or st.name
            prev = {'stage': st.name, 'sha256': C.sha256_file(path)}
            produced.update(rec.get('outputs') or {})
            if st.name == stop_after:
                break
        return done


# ============================================================================================ inputs (production)

def load_tuning_freeze(path=TUNING_FREEZE, protocol=PROTOCOL, **kw):
    """The tuning freeze (d*, L*) through the P2 gate p2_jobs.load_freeze: refuses (PermissionError) a selection.json
    whose sha256 PROTOCOL Sec. 13.2 does not cite, and an unsealed PROTOCOL.md (kw seal=None skips the seal check:
    tests only); ValueError for an inconsistent freeze (schema framelease_v4.tuning_selection/1, variant FULL, L* an
    exported envelope, d* a depth of the heuristic grid). Returns {'path', 'sha256', 'L', 'd', 'd_utility',
    'cited_lines', 'protocol'}."""
    from framelease_v4.protocol import p2_jobs as P2J
    return P2J.load_freeze(Path(path), protocol=Path(protocol), **kw)


def p2_plan(freeze, root=ROOT):
    """The registered P2 block (PROTOCOL Sec. 5.3: 44 training routes x kappa {1.0, 1.5, 2.0} x seed 11 = 132 runs; 'the
    RL dataset is exactly these episodes') as p2_jobs.py writes it: {(route, kappa): {'job': p2_jobs.job_id,
    'output_dir': root / p2_jobs.output_dir(kappa)}}. root: where the P2 output directories lie (the project root;
    another root in tests only)."""
    from framelease_v4.protocol import p2_jobs as P2J
    return {(str(r), float(k)): {'job': P2J.job_id(freeze, k, r), 'output_dir': Path(root) / P2J.output_dir(k)}
            for r in sorted(P2J.training_and_test()[0]) for k in KAPPAS}


def _pair(e):
    """(route, kappa) of a P2 manifest entry (kappa None when it is not a number)."""
    try:
        return str(e.get('route_id')), float(e.get('kappa'))
    except (TypeError, ValueError):
        return str(e.get('route_id')), None


def _plan_problems(e, plan, what):
    """A manifest entry against its run of the registered P2 block: the (route, kappa) pair and the job id
    (p2_jobs.job_id); for an episode (what 'episode') also the run directory, inside the P2 output directory of its
    kappa (p2_jobs.output_dir)."""
    pair = _pair(e)
    run = plan.get(pair)
    if run is None:
        return [f'{e.get("job")}: {what} (route {pair[0]}, kappa {e.get("kappa")!r}) is not a run of the registered '
                f'P2 block ({len(plan)} runs: 44 training routes x kappa {KAPPAS}, PROTOCOL Sec. 5.3)']
    probs = []
    if e.get('job') != run['job']:
        probs.append(f'{e.get("job")}: job id != {run["job"]} (p2_jobs.job_id of route {pair[0]}, kappa {pair[1]})')
    if what == 'episode':
        rd, od = abs_path(str(e.get('run_dir'))).resolve(), Path(run['output_dir']).resolve()
        if rd == od or not _inside(rd, od):
            probs.append(f'{e.get("job")}: run directory {e.get("run_dir")} is not inside {rel(od)}, the P2 output '
                         f'directory of kappa {pair[1]} (p2_jobs.output_dir)')
    return probs


def _manifest_episode_problems(e, freeze, plan, test_routes):
    """Why one P2 manifest episode is refused ([] = accepted): the behaviour utility at eps 0.3 with a_det^{d*} and the
    behaviour seed of its route and kappa, kappa in {1.0, 1.5, 2.0}, seed 11, a run of the registered P2 block with its
    job id and a run directory in the P2 output directory of its kappa (_plan_problems), and the sha256 of every source
    log the dataset builder reads, equal to the file now. A test route raises PermissionError."""
    from framelease_v4.rl import behaviour as B
    d_star = int(freeze['d'])
    probs, rid = [], str(e.get('route_id'))
    if rid in test_routes:
        raise PermissionError(f'P2 manifest episode {e.get("job")}: route {rid} is a held-out test route (PROTOCOL '
                              'Sec. 3.3); refusing the manifest')
    beh = B.parse_behaviour(e.get('utility'))
    if beh is None or abs(beh[0] - EPS) > 5e-4 or beh[2] != d_star:
        probs.append(f'{e.get("job")}: utility {e.get("utility")!r} is not the behaviour utility at eps {EPS} with '
                     f'a_det^{d_star}')
    try:
        kappa, seed = float(e.get('kappa')), int(e.get('seed'))
    except (TypeError, ValueError):
        kappa, seed = None, None
    if kappa not in KAPPAS or seed != P2_SEED:
        probs.append(f'{e.get("job")}: kappa {e.get("kappa")!r} / seed {e.get("seed")!r} not in {KAPPAS} / {P2_SEED}')
    else:
        probs += _plan_problems(e, plan, 'episode')
        if beh is not None:
            from framelease_v4.protocol import p2_jobs as P2J
            want = P2J.behaviour_utility(rid, kappa, d_star)[1]
            if e.get('utility') != want:
                probs.append(f'{e.get("job")}: utility {e.get("utility")!r} != {want!r} (behaviour seed rule of route '
                             f'{rid}, kappa {kappa}; PROTOCOL Sec. 2.6)')
    rd = abs_path(str(e.get('run_dir')))
    if not rd.is_dir():
        probs.append(f'{e.get("job")}: run directory {e.get("run_dir")} does not exist')
        return probs
    logs = e.get('source_logs_sha256') or {}
    for name in SOURCE_LOGS:            # Sec. 5.9: the sha256 of every source log the dataset builder reads
        if name not in logs and (name in REQUIRED_LOGS or (rd / name).is_file()):
            probs.append(f'{e.get("job")}: the manifest has no sha256 of {name}')
    for name, h in sorted(logs.items()):
        f = rd / name
        cur = C.sha256_file(f) if f.is_file() else None
        if cur != h:
            probs.append(f'{e.get("job")}: {name} sha256 {cur} != manifest {h}')
    return probs


def load_p2_manifest(path, freeze, missing_option='stop', test_routes=None, protocol=PROTOCOL, plan=None):
    """The P2 data manifest (schema framelease_v4.p2_data_manifest/1, written by p2_check.py --write on PASS only),
    checked against the tuning freeze and the registered P2 block (p2_plan: 44 training routes x kappa {1.0, 1.5,
    2.0} x seed 11, Sec. 5.3; plan: another block in tests only). Refuses (ValueError) another schema or variant; a
    manifest of another tuning freeze, d* or L*; counts (n_episodes, n_missing, n_jobs) that disagree with the lists;
    a (route, kappa) pair or run directory listed twice (episodes and missing jobs together); an episode or missing
    job that is not a run of the registered block or has another job id (p2_jobs.job_id); an episode whose run
    directory is not inside the P2 output directory of its kappa (p2_jobs.output_dir), that is not the behaviour
    utility at eps 0.3 with a_det^{d*} and the behaviour seed of its route and kappa (p2_jobs.behaviour_utility, Sec.
    2.6), kappa in {1.0, 1.5, 2.0}, seed 11, or with a source log the dataset builder reads (SOURCE_LOGS;
    metric_info.json when present) without a sha256 in the manifest or whose sha256 differs from it. A test route
    (episode or missing job) is refused with PermissionError. Whether each episode's run is what the entry declares
    (config.json: route, kappa, seed, utility) is checked when the dataset is built (_manifest_cross_check).
    Missing episodes (the manifest's missing jobs and every registered run the manifest does not list) stop the driver
    (Stop) unless missing_option == 'proceed' (GAP_AUDIT Sec. 6 item 5 (c)). cited_lines: the lines of PROTOCOL Sec.
    13.2 that cite the manifest's sha256 (recorded, not required: Sec. 8.1 ends P2 with the manifest and the test
    freeze enters it in Sec. 13 with the RL freeze, Sec. 5.9).
    Returns {'path', 'sha256', 'doc', 'run_dirs', 'missing' (the manifest's missing jobs, then the registered runs it
    does not list), 'deviations', 'cited_lines', 'n_registered'}."""
    from framelease_v4.protocol import p2_jobs as P2J
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f'{rel(path)}: no P2 data manifest yet (p2_check.py --write after a PASS, Sec. 8.1)')
    sha = C.sha256_file(path)
    doc = C.read_json(path)
    if not isinstance(doc, dict) or doc.get('schema') != P2_MANIFEST_SCHEMA:
        raise ValueError(f'{rel(path)}: not a P2 data manifest (schema {P2_MANIFEST_SCHEMA})')
    test = C.test_route_ids() if test_routes is None else frozenset(str(r) for r in test_routes)
    plan = p2_plan(freeze) if plan is None else plan
    d = int(freeze['d'])
    probs = []
    if doc.get('variant') != VARIANT:
        probs.append(f'variant {doc.get("variant")!r} != {VARIANT}')
    tf = doc.get('tuning_freeze') or {}
    if (tf.get('path'), tf.get('sha256')) != (freeze['path'], freeze['sha256']):
        probs.append(f'tuning freeze {tf.get("path")} / {tf.get("sha256")} != {freeze["path"]} / {freeze["sha256"]}')
    if (doc.get('d_star') or {}).get('d') != d:
        probs.append(f'd* {(doc.get("d_star") or {}).get("d")!r} != freeze d* {d}')
    ls = doc.get('L_star') or {}
    if (ls.get('label'), ls.get('sha256')) != (freeze['L']['label'], freeze['L']['sha256']):
        probs.append(f'L* {ls.get("label")} / {ls.get("sha256")} != freeze {freeze["L"]["label"]} / '
                     f'{freeze["L"]["sha256"]}')
    eps_, missing = doc.get('episodes') or [], list(doc.get('missing') or [])
    for key, n in (('n_episodes', len(eps_)), ('n_missing', len(missing)), ('n_jobs', len(eps_) + len(missing))):
        if doc.get(key) != n:
            probs.append(f'{key} {doc.get(key)!r} != {n} ({len(eps_)} listed episodes, {len(missing)} missing jobs)')
    pairs = [_pair(e) for e in eps_ + missing]
    dirs = [str(abs_path(str(e.get('run_dir'))).resolve()) for e in eps_]
    if len(set(pairs)) != len(pairs) or len(set(dirs)) != len(dirs):
        probs.append('duplicate (route, kappa) pairs (episodes and missing jobs) or run directories')
    for e in eps_:
        probs += _manifest_episode_problems(e, freeze, plan, test)
    for m in missing:
        if str(m.get('route_id')) in test:
            raise PermissionError(f'P2 manifest missing job {m.get("job")}: route {m.get("route_id")} is a held-out '
                                  'test route (PROTOCOL Sec. 3.3); refusing the manifest')
        probs += _plan_problems(m, plan, 'missing job')
    if probs:
        raise ValueError(f'{rel(path)} (sha256 {sha}) is refused:\n  ' + '\n  '.join(probs[:40]))
    unlisted = [{'job': plan[p]['job'], 'route_id': p[0], 'kappa': p[1],
                 'cause': 'a registered P2 run the manifest does not list (neither an episode nor a missing job)'}
                for p in sorted(set(plan) - set(pairs))]
    deviations = []
    if missing or unlisted:
        what = (f'{len(eps_)} episodes, {len(missing)} missing, {len(unlisted)} not listed, {len(plan)} registered '
                'runs: ' + ', '.join(f'{m.get("job")} ({m.get("cause")})' for m in (missing + unlisted)[:10]))
        if missing_option != 'proceed':
            raise Stop(f'P2 data manifest {rel(path)}: {what}. GAP_AUDIT Sec. 6 item 5 '
                       f'{OPEN_CASES["missing_episodes"][2]}; rerun with --missing-episodes proceed to use it '
                       f'({RECORD_NOTE})')
        deviations.append({**deviation('missing_episodes', 'proceed'), 'detail': what, 'n_not_listed': len(unlisted),
                           'missing': [{k: m.get(k) for k in ('job', 'route_id', 'kappa', 'cause')}
                                       for m in missing + unlisted]})
    cited = P2J.citations(sha, Path(protocol).read_text(encoding='utf-8'))
    return {'path': rel(path), 'sha256': sha, 'doc': doc, 'run_dirs': [abs_path(str(e['run_dir'])) for e in eps_],
            'missing': missing + unlisted, 'deviations': deviations, 'cited_lines': cited, 'n_registered': len(plan)}


# ============================================================================================ stage: dataset

def identity_rows(ds):
    """Per-episode reward identity of Sec. 5.2 from the dataset proofs (dataset.build_episode): pre + sum r_n = official
    DS within dataset.SUM_TOL, over all decision epochs and over the choice-epoch SMDP; terminal-only rewards (missing
    logs, prefix_score fallback) are flagged."""
    rows = []
    for i, m in enumerate(ds.episodes):
        p, g = m['proof'], m.get('reconstruction') or {}
        ok = bool(p['identity_ok']) and p['abs_err_epochs'] <= D.SUM_TOL and p['abs_err_choice'] <= D.SUM_TOL
        rows.append({'episode': i, 'route_id': m['route_id'], 'kappa': m.get('kappa'), 'run_dir': rel(m['run_dir']),
                     'kind': m.get('kind'), 'split': m.get('split'), 'ds_official': p['ds_official'],
                     'pre_plus_sum_r': p['pre_plus_sum_r'], 'abs_err_epochs': p['abs_err_epochs'],
                     'abs_err_choice': p['abs_err_choice'], 'identity_ok': ok, 'n_epochs': p['n_epochs'],
                     'n_choice': p['n_choice'], 'reward_mode': p.get('reward_mode'),
                     'terminal_only': bool(g.get('prefix_unavailable')) or p.get('reward_mode') == 'terminal',
                     'penalty_check_ok': g.get('penalty_check_ok')})
    return rows


def _copy_dev_dataset(src, dst):
    """Development mode: copy a prebuilt dataset directory (never modified) into <out>/dataset."""
    import shutil
    C._check_writable(dst)
    dst.mkdir(parents=True, exist_ok=True)
    for n in ('manifest.json', 'episodes.json', 'transitions.npz', 'epochs.npz'):
        tmp = dst / f'.{n}.tmp'
        shutil.copyfile(src / n, tmp)
        os.replace(tmp, dst / n)


def _same(a, b, cast):
    try:
        return cast(a) == cast(b)
    except (TypeError, ValueError):
        return False


def _manifest_cross_check(ds, man):
    """Dataset episodes against the P2 manifest entries (same order): the run directory, the run's own configuration
    (config.json through dataset.run_meta: route, kappa, seed and utility) and the official DS must agree with the
    entry, and the run must have a shield decision log (dataset kind v3); choice-count differences (decision rows after
    the last tick are dropped) are reported."""
    probs, notes = [], []
    eps_ = man['doc']['episodes']
    if len(ds.episodes) != len(eps_):
        return [f'{len(ds.episodes)} dataset episodes != {len(eps_)} manifest episodes'], notes
    for m, e in zip(ds.episodes, eps_):
        if Path(m['run_dir']).resolve() != abs_path(str(e['run_dir'])).resolve():
            probs.append(f'{e.get("job")}: run directory {m["run_dir"]} != {e["run_dir"]}')
        for key, cast in (('route_id', str), ('kappa', float), ('seed', int), ('utility', str)):
            if m.get(key) is None or not _same(m.get(key), e.get(key), cast):
                probs.append(f'{e.get("job")}: {key} {m.get(key)!r} in the run\'s config.json != manifest '
                             f'{e.get(key)!r}')
        if m.get('kind') != 'v3':
            probs.append(f'{e.get("job")}: no shield decision log (dataset kind {m.get("kind")!r}, not v3)')
        if e.get('ds') is None or abs(float(m['proof']['ds_official']) - float(e['ds'])) > 1e-9:
            probs.append(f'{e.get("job")}: official DS {m["proof"]["ds_official"]} != manifest {e.get("ds")}')
        if int(m['proof']['n_choice']) != int(e.get('n_choice') or 0):
            notes.append({'job': e.get('job'), 'n_choice_dataset': m['proof']['n_choice'],
                          'n_choice_manifest': e.get('n_choice')})
    return probs, notes


def dataset_inputs(ctx):
    if ctx.mode == 'development':
        return [ctx.dev_dataset / n for n in ('manifest.json', 'episodes.json', 'transitions.npz', 'epochs.npz')] + \
            [C.TEST_ROUTES_JSON]
    return [abs_path(ctx.manifest['path']), abs_path(ctx.freeze['path']), C.ROUTES_XML, C.TEST_ROUTES_JSON]


def dataset_params(ctx):
    if ctx.mode == 'development':
        return {'dev_dataset': rel(ctx.dev_dataset)}
    return {'p2_manifest': ctx.manifest['path'], 'tuning_freeze': ctx.freeze['path'], 'reward_mode': 'prefix'}


def stage_dataset(ctx):
    """Sec. 5.3 / GAP_AUDIT P3-1 step 1: the dataset from the P2 manifest's run directories (test routes refused by
    dataset.build_dataset), the per-episode reward identity (Sec. 5.2), reward_identity.json."""
    deviations, notes = [], []
    if ctx.mode == 'development':
        _copy_dev_dataset(ctx.dev_dataset, ctx.dataset_dir)
    else:
        D.build_dataset(ctx.manifest['run_dirs'], out_dir=ctx.dataset_dir, allow_test=False, reward_mode='prefix')
        deviations = list(ctx.manifest['deviations'])
    ctx._ds = None
    ds = ctx.dataset()
    test = C.test_route_ids()
    bad = [m['run_dir'] for m in ds.episodes if m.get('split') != 'train' or str(m['route_id']) in test]
    if bad:
        raise PermissionError(f'dataset: test-route or non-training episodes {bad[:5]} (PROTOCOL Sec. 3.3)')
    if ctx.mode == 'production':
        probs, notes = _manifest_cross_check(ds, ctx.manifest)
        if probs:
            raise StageError('dataset: disagrees with the P2 manifest:\n  ' + '\n  '.join(probs[:20]))
    rows = identity_rows(ds)
    failed = [r for r in rows if not r['identity_ok']]
    doc = {'schema': IDENTITY_SCHEMA, 'mode': ctx.mode, 'tolerance': D.SUM_TOL, 'n_episodes': len(rows),
           'all_identity_ok': not failed, 'max_abs_err_epochs': max((r['abs_err_epochs'] for r in rows), default=None),
           'max_abs_err_choice': max((r['abs_err_choice'] for r in rows), default=None),
           'terminal_only': [r['run_dir'] for r in rows if r['terminal_only']], 'n_choice_differences': notes,
           'definition': 'S(t) = RC(t) x P(t) (prefix_score.py); r_n = S(t_{n+1}) - S(t_n), last r = DS - S(t_N); '
                         f'per episode |pre + fsum(r) - DS| <= {D.SUM_TOL:g} over all decision epochs and over the '
                         'choice-epoch SMDP (PROTOCOL Sec. 5.2)', 'episodes': rows}
    path = C.atomic_json(ctx.out / 'reward_identity.json', doc)
    if failed:
        raise StageError(f'dataset: reward identity fails on {len(failed)} episode(s): '
                         f'{[r["run_dir"] for r in failed[:5]]} (see {rel(path)})')
    kap = {}
    for m in ds.episodes:
        kap[str(m.get('kappa'))] = kap.get(str(m.get('kappa')), 0) + 1
    return {'outputs': ctx.dataset_files() + [path], 'deviations': deviations,
            'result': {'n_episodes': len(ds.episodes), 'n_transitions': ds.n,
                       'n_train_episodes_with_choice': len(ds.train_episode_ids()), 'episodes_per_kappa': kap,
                       'identity_all_ok': True, 'max_abs_err_epochs': doc['max_abs_err_epochs'],
                       'max_abs_err_choice': doc['max_abs_err_choice'], 'n_terminal_only': len(doc['terminal_only']),
                       'n_missing': len(ctx.manifest['missing']) if ctx.manifest else None,
                       'n_registered': ctx.manifest.get('n_registered') if ctx.manifest else None,
                       'p2_manifest_cited_lines': ctx.manifest['cited_lines'] if ctx.manifest else None}}


# ============================================================================================ stage: p_both

def p_both_summary(ds, kappa=P_BOTH_KAPPA):
    """Sec. 5.8: P_both = Pr(|A_feas| = 2), pooled over the shield decision epochs (decision rows up to the last tick,
    dataset.build_episode) of the kappa episodes; v2-policy episodes have no shield and are not counted. Label
    'not testable at this operating point' when P_both < 0.05 (the RL arms still run; H2 is computed with the label)."""
    def pooled(rows):
        n_ep = sum(int(m['proof']['n_epochs']) for m in rows)
        n_ch = sum(int(m['proof']['n_choice']) for m in rows)
        per = [m['proof']['n_choice'] / m['proof']['n_epochs'] for m in rows if m['proof']['n_epochs']]
        return {'p_both': (n_ch / n_ep) if n_ep else None, 'decision_epochs': n_ep, 'choice_epochs': n_ch,
                'n_episodes': len(rows), 'per_episode': {
                    'min': min(per, default=None), 'median': float(np.median(per)) if per else None,
                    'max': max(per, default=None)}}
    shield = [m for m in ds.episodes if m.get('kind') == 'v3' and m.get('kappa') is not None]
    by_kappa = {}
    for m in shield:
        by_kappa.setdefault(f'{float(m["kappa"]):.1f}', []).append(m)
    main_ = pooled([m for m in shield if float(m['kappa']) == float(kappa)])
    p = main_['p_both']
    label = ('undetermined (no decision epoch at this kappa)' if p is None else
             'not testable at this operating point' if p < P_BOTH_MIN else 'testable')
    return {'schema': P_BOTH_SCHEMA, 'kappa': float(kappa), 'threshold': P_BOTH_MIN, **main_, 'label': label,
            'by_kappa': {k: pooled(v) for k, v in sorted(by_kappa.items())},
            'rule': 'P_both = Pr(|A_feas| = 2) over decision epochs (outline IV-B); if P_both < 0.05 in the kappa-1.0 '
                    'episodes of the RL dataset the RL contribution is labelled "not testable at this operating '
                    'point", the RL arms still run and H2 is reported with that label (PROTOCOL Sec. 5.8)'}


def p_both_logs(ds, kappa=P_BOTH_KAPPA):
    """decisions.jsonl of the shield (v3) episodes of the kappa: the logs behind P_both (inputs of stage p_both)."""
    return [abs_path(m['run_dir']) / 'raw' / 'agent' / 'framelease' / 'decisions.jsonl' for m in ds.episodes
            if m.get('kind') == 'v3' and m.get('kappa') is not None and float(m['kappa']) == float(kappa)]


def metrics_v4_p_both(ds, kappa=P_BOTH_KAPPA):
    """P_both of the kappa episodes as every table computes it (Sec. 5.8): metrics_v4.decision_metrics over each run's
    decisions.jsonl, read by metrics_v4.read_jsonl as metrics_v4.run_metrics reads it, pooled (choice epochs / shield
    epochs). Returns {'p_both', 'shield_epochs', 'choice_epochs', 'n_runs', 'logs': {path: sha256}}."""
    from framelease_v4.arms import metrics_v4 as M
    n_sh = n_ch = 0
    logs = {}
    for f in p_both_logs(ds, kappa):
        dm = M.decision_metrics(M.read_jsonl(f))
        n_sh += int(dm['shield_epochs'])
        n_ch += 0 if dm['p_both'] is None else int(round(dm['p_both'] * dm['shield_epochs']))
        logs[rel(f)] = C.sha256_file(f)
    return {'p_both': n_ch / n_sh if n_sh else None, 'shield_epochs': n_sh, 'choice_epochs': n_ch,
            'n_runs': len(logs), 'logs': logs}


def stage_p_both(ctx):
    """Sec. 5.8: P_both and its label from the dataset proofs (p_both_summary), with the value every table reports
    (metrics_v4_p_both) alongside: their decision and choice epoch counts must be equal, otherwise p_both.json is
    written with the difference and the driver stops (no record), so the label and the tables cannot disagree."""
    ds = ctx.dataset()
    doc = p_both_summary(ds)
    if doc['p_both'] is None and ctx.mode == 'production':
        raise StageError('p_both: the RL dataset has no decision epoch in a kappa-1.0 episode')
    m4 = metrics_v4_p_both(ds)
    same = (m4['shield_epochs'], m4['choice_epochs']) == (doc['decision_epochs'], doc['choice_epochs'])
    doc['metrics_v4'] = {**m4, 'agrees': same,
                         'rule': 'metrics_v4.decision_metrics (the P_both of every table) pooled over the same runs; '
                                 'its shield and choice epoch counts must equal the dataset\'s'}
    path = C.atomic_json(ctx.out / 'p_both.json', doc)
    if not same:
        raise StageError(f'p_both: the dataset counts {doc["choice_epochs"]} / {doc["decision_epochs"]} differ from '
                         f'metrics_v4.decision_metrics {m4["choice_epochs"]} / {m4["shield_epochs"]} over the '
                         f'kappa-{P_BOTH_KAPPA:g} runs (see {rel(path)})')
    return {'outputs': [path], 'result': {**{k: doc[k] for k in ('p_both', 'label', 'decision_epochs',
                                                                 'choice_epochs', 'n_episodes')},
                                          'metrics_v4_p_both': m4['p_both']}}


# ============================================================================================ stage: select_<family>

def select_params(ctx, family):
    return {'family': family, 'grid': ctx.grid_kind, 'candidates': [c.as_dict() for c in ctx.grid(family)],
            'n_folds': ctx.n_folds, 'fold_seed': FOLD_SEED, 'fqe': ctx.fqe_cfg.as_dict(), 'n_boot': ctx.n_boot}


NOT_SELECTABLE = 'every candidate has an unsupported held-out evaluation in some fold (PROTOCOL Sec. 5.6 rule 3)'
# Amendment A6: a candidate whose training fold cannot fit it (ope.fit_support 'ok' false: no head with min_support
# samples, or a head a_det^{d*} needs below min_support) is not fitted there; its held-out evaluation in that fold is
# unsupported, a regular unsupported evaluation of Sec. 5.6 rule 3 (the fold record carries 'fit_unsupported')
FIT_UNSUPPORTED = ('every candidate has an unsupported evaluation in some fold (PROTOCOL Sec. 5.6 rule 3); training '
                   'folds that cannot fit a candidate (Amendment A6)')
HEADS = ('REFINE', 'REFRESH')   # the action heads in the order of ope.fit_support (trainers.REFINE, trainers.REFRESH)


def fit_unsupported_folds(rep):
    """Amendment A6: the training folds of a selection report (ope.select) whose fit data cannot fit a candidate, from
    the fold records' 'fit_unsupported' (ope.fit_support): per fold (index into rep['folds']; a candidate's fold
    records are in fold order) the logged samples per head of its fit episodes and the candidates it cannot fit, each
    with its min_support, the heads with that support and the heads a_det^{d*} needs on the fit states. [] when every
    fold fits every candidate."""
    by_fold = {}
    for r in rep['candidates']:
        for k, f in enumerate(r['folds']):
            s = f.get('fit_unsupported')
            if s is None:
                continue
            e = by_fold.setdefault(k, {'fold': k, 'n_samples': dict(zip(HEADS, (int(n) for n in s['n_samples']))),
                                       'candidates': []})
            e['candidates'].append({'label': r['label'], 'min_support': int(s['min_support']),
                                    'supported': [h for h, x in zip(HEADS, s['supported']) if x],
                                    'a_det_needs': [h for h, x in zip(HEADS, s['a_det_needs']) if x]})
    return [by_fold[k] for k in sorted(by_fold)]


def not_selectable_reason(rep, fit_folds):
    """The not_trainable_reason of a family without a selectable candidate: with training folds that cannot fit a
    candidate (fit_unsupported_folds), FIT_UNSUPPORTED with the per-head sample counts of each such fold and, per
    min_support, the number of candidates and the cause (no head with min_support samples, or the heads a_det^{d*}
    needs below it); otherwise the held-out rule (NOT_SELECTABLE)."""
    if not fit_folds:
        return NOT_SELECTABLE
    n_cands, parts = len(rep['candidates']), []
    for e in fit_folds:
        causes = {}
        for c in e['candidates']:
            missing = [h for h in c['a_det_needs'] if h not in c['supported']]
            why = ('no head with min_support samples' if not c['supported'] else
                   f'a_det^{{d*}} needs the unsupported {"/".join(missing)} head')
            causes[(c['min_support'], why)] = causes.get((c['min_support'], why), 0) + 1
        counts = ' / '.join(f'{h} {e["n_samples"][h]}' for h in HEADS)
        parts.append(f'fold {e["fold"]} with {counts} logged samples: ' +
                     ', '.join(f'{n} of {n_cands} candidates (min_support {m}, {why})'
                               for (m, why), n in sorted(causes.items())))
    return f'{FIT_UNSUPPORTED}: ' + '; '.join(parts)


def stage_select(ctx, family):
    """Secs. 5.5-5.6 / GAP_AUDIT P3-1 step 3: ope.select(ds, trainers.grid(family, d_det=d*), n_folds=5, FQEConfig(),
    n_jobs=N) on every training episode. The report is always recorded; a family without a selectable candidate is
    marked not_trainable (with the reason) and decided at refit_<family> (option --no-selectable), so the selection
    never reruns. The reason comes from the fold records (not_selectable_reason): training folds that cannot fit a
    candidate (Amendment A6: ope.select marks the candidate unsupported there and continues; 'fit_unsupported' of
    the report lists them, fit_unsupported_folds) with their per-head sample counts, otherwise the held-out rule of
    Sec. 5.6 rule 3. fqe_not_converged names the candidates whose FQE hit the iteration cap in a fitted fold (a fold
    without a fit runs no FQE). Any error of ope.select stops the driver."""
    ds = ctx.dataset()
    cands = ctx.grid(family)
    ids = ds.train_episode_ids()
    if not ids:
        raise StageError(f'select_{family}: no training episode with a choice epoch')
    rep = O.select(ds, cands, ids, n_folds=ctx.n_folds, fqe_cfg=ctx.fqe_cfg, n_jobs=ctx.n_jobs, seed=FOLD_SEED,
                   n_boot=ctx.n_boot)
    fit_folds = fit_unsupported_folds(rep)
    sel = rep['selected']
    row = next((r for r in rep['candidates'] if r['label'] == sel), None)
    est = None if row is None else {'label': sel, 'mean_delta': row['mean_delta'], 'bootstrap': row['bootstrap'],
                                    'unsupported_folds': row['unsupported_folds']}
    not_conv = sorted({r['label'] for r in rep['candidates'] for f in r['folds']
                       if f.get('fit_unsupported') is None and not f.get('fqe_converged')})
    doc = {'schema': SELECT_SCHEMA, **rep, 'mode': ctx.mode, 'd_star': ctx.d_star, 'arm': ARM_OF[family],
           'grid': ctx.grid_kind, 'n_train_episodes': len(ids),
           'train_routes': sorted({str(ds.episodes[i]['route_id']) for i in ids}), 'estimate': est,
           'not_trainable': sel is None,
           'not_trainable_reason': None if sel is not None else not_selectable_reason(rep, fit_folds),
           'fit_unsupported': fit_folds, 'fqe_not_converged': not_conv,
           'heuristic_fqe_not_converged': sorted(int(f) for f, h in rep['heuristic'].items() if not h.get('converged')),
           'protocol': 'PROTOCOL Secs. 5.5-5.6: argmax of the cross-fitted mean paired delta vs a_det^{d*}; the '
                       'selected candidate is deployed whatever the sign of its estimate'}
    path = C.atomic_json(ctx.out / f'select_{family}.json', doc)
    return {'outputs': [path],
            'result': {'selected': sel, 'not_trainable': sel is None,
                       'not_trainable_reason': doc['not_trainable_reason'], 'estimate': est,
                       'n_candidates': len(cands), 'n_folds': rep['n_folds'], 'n_train_episodes': len(ids),
                       'fit_unsupported_folds': [e['fold'] for e in fit_folds], 'fqe_not_converged': not_conv,
                       'candidates': [{'label': r['label'], 'mean_delta': r['mean_delta'],
                                       'unsupported_folds': r['unsupported_folds']} for r in rep['candidates']]}}


# ============================================================================================ stage: refit_<family>

def selected_candidate(out, family):
    """(selection report, Candidate or None) of select_<family>.json; None = no selectable candidate."""
    doc = C.read_json(Path(out) / f'select_{family}.json')
    if doc.get('selected') is None:
        return doc, None
    row = next(r for r in doc['candidates'] if r['label'] == doc['selected'])
    return doc, TR.Candidate(**row['candidate'])


def not_trainable(ctx, family, stage, reason=None):
    """Open case (a): Stop under the default; the deviation entry with --no-selectable adet. reason: the selection
    report's not_trainable_reason."""
    reason = reason or NOT_SELECTABLE
    if ctx.options['no_selectable'] != 'adet':
        raise Stop(f'{stage}: family {family} has no selectable candidate ({reason}). GAP_AUDIT Sec. 6 item 5 '
                   f'{OPEN_CASES["no_selectable"][2]}; rerun with --no-selectable adet ({RECORD_NOTE})')
    return {**deviation('no_selectable', 'adet'), 'family': family, 'reason': reason}


def train_states(ds, ids):
    """Distillation states: every choice state and every non-terminal next state of the episodes (as rl/smoke.py)."""
    m = ds.episode_mask(ids)
    return np.concatenate([ds.X[m], ds.XN[m & ~ds.DONE]])


def stage_refit(ctx, family):
    """Sec. 5.6 rule 5 / GAP_AUDIT P3-1 step 4: the selected candidate refit (trainers.fit_candidate) on every
    training episode of the RL dataset; the forests (trainers.TreeQ) are kept as a joblib file for the distillation
    and loaded only after their sha256 matches this stage's record."""
    import joblib
    ds = ctx.dataset()
    sel, cand = selected_candidate(ctx.out, family)
    ids = ds.train_episode_ids()
    base = {'schema': REFIT_SCHEMA, 'family': family, 'arm': ARM_OF[family], 'mode': ctx.mode, 'd_star': ctx.d_star,
            'train_episodes': ids, 'train_routes': sorted({str(ds.episodes[i]['route_id']) for i in ids})}
    if cand is None:
        dv = not_trainable(ctx, family, f'refit_{family}', sel.get('not_trainable_reason'))
        path = C.atomic_json(ctx.out / f'refit_{family}.json', {**base, 'not_trainable': True, 'candidate': None,
                                                                 'label': None, 'model': None})
        return {'outputs': [path], 'deviations': [dv], 'result': {'not_trainable': True}}
    q, info = TR.fit_candidate(ds, ids, cand)
    model = C._check_writable(ctx.out / f'refit_{family}.joblib')
    tmp = model.with_name(model.name + '.tmp')
    joblib.dump(q, tmp, compress=3)
    os.replace(tmp, model)
    doc = {**base, 'not_trainable': False, 'candidate': cand.as_dict(), 'label': cand.label,
           'selection_estimate': sel.get('estimate'), 'n_transitions': info['n'], 'supported': info['supported'],
           'n_samples': info['n_samples'], 'train_deviation_rate': info.get('train_deviation_rate'),
           'train_agreement_with_logged': info.get('train_agreement_with_logged'), 'iterations': info['iterations'],
           'model': model.name, 'model_format': 'joblib (compress 3) of trainers.TreeQ, in the output directory'}
    path = C.atomic_json(ctx.out / f'refit_{family}.json', doc)
    return {'outputs': [path, model],
            'result': {'label': cand.label, 'n_transitions': info['n'], 'supported': info['supported'],
                       'n_samples': info['n_samples'], 'train_deviation_rate': info.get('train_deviation_rate'),
                       'model_bytes': model.stat().st_size}}


# ============================================================================================ stage: distill_<family>

def load_refit_model(out, family):
    """The refit trainers.TreeQ, unpickled only after its sha256 equals the output recorded by refit_<family>."""
    import joblib
    model = Path(out) / f'refit_{family}.joblib'
    want = ((read_record(record_path(out, f'refit_{family}')) or {}).get('outputs') or {}).get(rec_key(out, model))
    if want is None or not model.is_file() or C.sha256_file(model) != want:
        raise StageError(f'{rel(model)} does not match the refit_{family} stage record; refusing to load it')
    return joblib.load(model)


def _mlp_doc(mlp):
    return {'W': [np.asarray(w).tolist() for w in mlp['W']], 'b': [np.asarray(b).tolist() for b in mlp['b']],
            'val_loss': mlp.get('val_loss'), 'best_epoch': mlp.get('best_epoch'), 'epochs_run': mlp.get('epochs_run')}


def stage_distill(ctx, family):
    """Secs. 4.7, 5.6 / GAP_AUDIT P3-1 step 5: trainers.distill of the refit forests into the 16 -> 32 -> 32 -> 2 MLP
    (10 inputs for fqi_nolease) on every choice state and non-terminal next state of the training episodes; agreement
    target 0.98 with one retry at 64x64 (inside trainers.distill). Below 0.98 after the retry the best try is kept too
    (trainers.distill at its width with min_agreement 0) and export_<family> decides (--distill-shortfall), so the
    distillation never reruns for an option."""
    fit = C.read_json(ctx.out / f'refit_{family}.json')
    base = {'schema': DISTILL_SCHEMA, 'family': family, 'arm': ARM_OF[family], 'mode': ctx.mode,
            'min_agreement': MIN_AGREEMENT}
    if fit['not_trainable']:
        path = C.atomic_json(ctx.out / f'distill_{family}.json', {**base, 'not_trainable': True, 'mlp': None})
        return {'outputs': [path], 'result': {'not_trainable': True}}
    cand = TR.Candidate(**fit['candidate'])
    q = load_refit_model(ctx.out, family)
    states = train_states(ctx.dataset(), fit['train_episodes'])
    mlp, fid = TR.distill(q, cand, states, min_agreement=MIN_AGREEMENT)
    best = None
    if not fid['ok']:
        tries = fid['tries']
        k = max(range(len(tries)), key=lambda i: (tries[i]['agreement'] or 0.0, -i))
        best = {'try': k, 'hidden': tries[k]['hidden'], 'agreement': tries[k]['agreement'], 'mlp': None,
                'same_as_final': k == len(tries) - 1}
        if k != len(tries) - 1:
            mlp_b, fid_b = TR.distill(q, cand, states, hidden=tuple(tries[k]['hidden']), min_agreement=0.0)
            best.update(agreement=fid_b['final']['agreement'], fidelity=fid_b, mlp=_mlp_doc(mlp_b))
    doc = {**base, 'not_trainable': False, 'candidate': cand.as_dict(), 'label': cand.label,
           'n_states': int(len(states)), 'ok': fid['ok'], 'agreement': fid['final']['agreement'],
           'hidden': fid['final']['hidden'], 'fidelity': fid, 'mlp': _mlp_doc(mlp), 'best_try': best,
           'states': 'choice states and non-terminal next states of the training episodes'}
    path = C.atomic_json(ctx.out / f'distill_{family}.json', doc)
    return {'outputs': [path], 'result': {'label': cand.label, 'ok': fid['ok'], 'agreement': doc['agreement'],
                                          'hidden': doc['hidden'], 'n_tries': len(fid['tries']),
                                          'n_states': doc['n_states'],
                                          'best_try_agreement': None if best is None else best['agreement']}}


# ============================================================================================ stage: export_<family>

def adet_mlp(n_in, hidden=(32, 32)):
    """Zero-weight MLP of the a_det^{d*}-equivalent network (open case (a)): with both heads unsupported,
    qnet.QUtility answers a_det^{d*} at every choice state."""
    sizes = [int(n_in), *hidden, 2]
    return {'W': [np.zeros((a, b)) for a, b in zip(sizes[:-1], sizes[1:])], 'b': [np.zeros(b) for b in sizes[1:]]}


def _file_ref(p):
    p = Path(p)
    return {'path': rel(p), 'sha256': C.sha256_file(p)}


def stage_export(ctx, family):
    """Secs. 5.7, 8.1 / GAP_AUDIT P3-1 step 6: trainers.export_qnet with B_pi = 100 us into <out>/qnet_<family>.json,
    read back through qnet.load_spec (the name v4_qnet_<sha12> pins the decision-relevant content); the a_det depth
    must be d*, the inputs 16 (10 for fqi_nolease). Open cases decided here: (a) --no-selectable, (b)
    --distill-shortfall."""
    sp, fp, dp = (ctx.out / f'{s}_{family}.json' for s in ('select', 'refit', 'distill'))
    sel, fit, dis = C.read_json(sp), C.read_json(fp), C.read_json(dp)
    deviations = []
    if dis['not_trainable']:
        deviations.append(not_trainable(ctx, family, f'export_{family}', sel.get('not_trainable_reason')))
        cand = min(ctx.grid(family), key=lambda c: c.complexity)      # names the columns only (ADET_NOTE)
        mlp, supported, agreement, hidden = adet_mlp(len(cand.columns)), [False, False], None, [32, 32]
    else:
        cand, supported = TR.Candidate(**dis['candidate']), list(fit['supported'])
        mlp, agreement, hidden = dis['mlp'], dis['agreement'], dis['hidden']
        if not dis['ok']:
            if ctx.options['distill_shortfall'] != 'deploy_best':
                raise Stop(f'export_{family}: distillation agreement {dis["agreement"]} < {MIN_AGREEMENT} after the '
                           f'64x64 retry. GAP_AUDIT Sec. 6 item 5 {OPEN_CASES["distill_shortfall"][2]}; rerun with '
                           f'--distill-shortfall deploy_best ({RECORD_NOTE})')
            b = dis['best_try']
            mlp = dis['mlp'] if b['same_as_final'] else b['mlp']
            agreement, hidden = b['agreement'], b['hidden']
            deviations.append({**deviation('distill_shortfall', 'deploy_best'), 'family': family,
                               'agreement': agreement, 'hidden': hidden})
    prov = {'mode': ctx.mode, 'family': family, 'arm': ARM_OF[family], 'd_star': ctx.d_star,
            'dataset': rel(ctx.dataset_dir), 'dataset_manifest_sha256': C.sha256_file(ctx.dataset_files()[0]),
            'p2_manifest': None if ctx.manifest is None else {k: ctx.manifest[k] for k in ('path', 'sha256')},
            'tuning_freeze': None if ctx.freeze is None else {k: ctx.freeze[k] for k in ('path', 'sha256')},
            'dev_dataset': None if ctx.dev_dataset is None else rel(ctx.dev_dataset),
            'selection': _file_ref(sp), 'selected': sel.get('selected'), 'estimate': sel.get('estimate'),
            'refit': _file_ref(fp), 'distillation': {**_file_ref(dp), 'agreement': agreement, 'hidden': hidden,
                                                     'ok': dis.get('ok')},
            'train_episodes': len(fit['train_episodes']), 'train_routes': fit['train_routes'],
            'not_trainable': bool(dis['not_trainable']), 'deviations': deviations, 'code_sha256': code_sha256(),
            'candidate_field': 'columns only, not selected (ADET_NOTE)' if dis['not_trainable'] else 'selected'}
    spec = TR.export_qnet({'W': [np.asarray(w, dtype=np.float64) for w in mlp['W']],
                           'b': [np.asarray(b, dtype=np.float64) for b in mlp['b']]},
                          cand, supported, provenance=prov, policy_budget_s=POLICY_BUDGET_S)
    path = C.atomic_json(ctx.out / f'qnet_{family}.json', spec)
    back = Q.load_spec(path)
    n_in = len(F.NO_LEASE_COLUMNS) if family == 'fqi_nolease' else len(F.ALL_COLUMNS)
    probs = []
    if int(back['a_det']['depth']) != ctx.d_star:
        probs.append(f'a_det depth {back["a_det"]["depth"]} != d* {ctx.d_star}')
    if len(back['feature_columns']) != n_in:
        probs.append(f'{len(back["feature_columns"])} inputs != {n_in}')
    if float(back['policy_budget_s']) != POLICY_BUDGET_S:
        probs.append(f'policy budget {back["policy_budget_s"]} != {POLICY_BUDGET_S}')
    if probs:
        raise StageError(f'export_{family}: {rel(path)}: ' + '; '.join(probs))
    return {'outputs': [path], 'deviations': deviations,
            'result': {'name': back['name'], 'weights_sha256': back['weights_sha256'], 'arm': ARM_OF[family],
                       'candidate': None if dis['not_trainable'] else cand.label, 'supported': supported,
                       'agreement': agreement, 'hidden': hidden, 'n_inputs': n_in, 'a_det_depth': ctx.d_star,
                       'policy_budget_s': POLICY_BUDGET_S, 'not_trainable': bool(dis['not_trainable']),
                       'note': ADET_NOTE if dis['not_trainable'] else None}}


# ============================================================================================ stage: deploy_check

def network_ref(path):
    """(identity, spec) of an exported network; qnet.load_spec verifies its schema, weights sha256 and name. abs_path
    is the value for FRAMELEASE_V4_QNET: the evaluator agent reads it in its own working directory, so a relative
    path passes the launcher dry run and fails in the agent (finding QNET-1); job lines use abs_path only."""
    path = Path(path).resolve()
    spec = Q.load_spec(path)
    return {'path': rel(path), 'abs_path': str(path), 'file_sha256': C.sha256_file(path), 'name': spec['name'],
            'weights_sha256': spec['weights_sha256'], 'family': (spec.get('candidate') or {}).get('family'),
            'n_inputs': len(spec['feature_columns']), 'a_det_depth': int(spec['a_det']['depth']),
            'supported': list(spec['supported']), 'policy_budget_s': float(spec['policy_budget_s'])}, spec


def logged_decision_files(ds):
    """decisions.jsonl of every dataset episode with v3 decision rows: the logged decision and choice states."""
    return [abs_path(m['run_dir']) / 'raw' / 'agent' / 'framelease' / 'decisions.jsonl' for m in ds.episodes
            if m.get('kind') == 'v3']


class _RawAnswer:
    """A utility wrapper that keeps the raw answer of select(): v3_shield.decide replaces an answer outside A_feas by
    the heuristic, so the A_feas check reads the answer before that replacement."""

    def __init__(self, utility):
        self.utility, self.name, self.last = utility, utility.name, None

    def select(self, features, feasible):
        self.last = self.utility.select(features, feasible)
        return self.last


class _QnetEnv:
    """FRAMELEASE_V4_QNET set to an absolute path for the block, the previous value restored after it."""

    def __init__(self, path):
        if not Path(path).is_absolute():
            raise StageError(f'{path}: {Q.ENV_QNET} must be an absolute path (finding QNET-1)')
        self.path, self.old = str(path), None

    def __enter__(self):
        self.old = os.environ.get(Q.ENV_QNET)
        os.environ[Q.ENV_QNET] = self.path
        return self

    def __exit__(self, *exc):
        if self.old is None:
            os.environ.pop(Q.ENV_QNET, None)
        else:
            os.environ[Q.ENV_QNET] = self.old
        return False


REPLAY_PROBLEMS = ('shield_mismatch', 'left_feasible_set', 'wrong_reason', 'depth_not_d_star', 'bypass_not_adet',
                   'deviation_unsupported')


def replay_network(name, path, files, d_star):
    """GAP_AUDIT P3-2: the network loaded as the evaluator agent loads it (rl/agent_entry.py): the name registered by
    behaviour.register_utility_name, then v3_shield.make_utility(name), which builds qnet.QUtility from
    $FRAMELEASE_V4_QNET (an absolute path; the instance refuses a file with another sha256), one fresh instance per
    logged run. Every logged decision row is replayed through v3_shield.decide with the shield result rebuilt by
    rl/smoke.py _shield_result. Problem counters (each must be 0): a rebuilt feasible set that differs from the logged
    one, an answer outside A_feas, a reason other than both_feasible:<name>, an instance whose a_det depth is not
    d*, a bypassed choice whose answer is not a_det^{d*}(depth), a deviation from a_det^{d*} without both heads
    supported. Timing-dependent (overrun bypasses), so the counts of actions are reported, not compared."""
    from framelease_v3.runtime import v3_shield as VS
    from framelease_v4.rl import behaviour as B
    from framelease_v4.rl import smoke as RS
    c = {k: 0 for k in ('runs', 'rows', 'choice_rows', 'deviations', 'network_calls', 'disabled_runs',
                        *REPLAY_PROBLEMS)}
    acts = {'REFINE': 0, 'REFRESH': 0}
    bypass = {}
    with _QnetEnv(path):
        if not B.register_utility_name(name):
            raise StageError(f'{name}: not a framelease_v4 utility name')
        for f in files:
            u = VS.make_utility(name)
            if not isinstance(u, Q.QUtility) or u.name != name:
                raise StageError(f'{name}: v3_shield.make_utility built {type(u).__name__} {getattr(u, "name", None)}')
            c['runs'] += 1
            c['depth_not_d_star'] += int(u.d_det != int(d_star))
            ru = _RawAnswer(u)
            for r in C.read_jsonl(f):
                c['rows'] += 1
                sr = RS._shield_result(r)
                if tuple(sr.feasible) != tuple(r.get('feasible') or ()):
                    c['shield_mismatch'] += 1
                    continue
                feats = dict(r.get('features') or {})
                ru.last = None
                a, reason = VS.decide(sr, ru, feats)
                if not sr.both:
                    continue
                c['choice_rows'] += 1
                acts[a] = acts.get(a, 0) + 1
                c['left_feasible_set'] += int(ru.last not in sr.feasible)
                c['wrong_reason'] += int(reason != f'both_feasible:{name}')
                if ru.last != B.a_det_action(feats.get('depth'), int(d_star)):
                    c['deviations'] += 1
                    c['bypass_not_adet'] += int(feats.get('v4_bypass') is not None)
                    c['deviation_unsupported'] += int(not u.both_supported)
            st = u.stats()
            c['network_calls'] += st['network_calls']
            c['disabled_runs'] += int(st['disabled'])
            for k, v in st['bypass'].items():
                bypass[k] = bypass.get(k, 0) + v
    return {**c, 'actions_at_choice': acts, 'bypass': bypass,
            'deviation_rate': c['deviations'] / c['choice_rows'] if c['choice_rows'] else None,
            'problems': {k: c[k] for k in REPLAY_PROBLEMS if c[k]}}


def pin_refused(name, other_path):
    """True when the instance of name refuses another network's file under FRAMELEASE_V4_QNET (the sha256 pin)."""
    from framelease_v3.runtime import v3_shield as VS
    from framelease_v4.rl import behaviour as B
    with _QnetEnv(other_path):
        B.register_utility_name(name)
        try:
            VS.make_utility(name)
        except ValueError:
            return True
    return False


def bench_rows(files, limit=5000):
    """(features, shield) of the logged choice states (|A_feas| = 2), as rl/bench_qnet.py choice_feature_dicts takes
    them from the pilot; every decision row when the logs have no choice state."""
    rows, every = [], []
    for f in files:
        for r in C.read_jsonl(f):
            item = (r.get('features') or {}, r.get('shield'))
            if len(r.get('feasible') or ()) == 2:
                rows.append(item)
            elif len(every) < limit:
                every.append(item)
            if len(rows) >= limit:
                return rows, 'choice states'
    return (rows, 'choice states') if rows else (every, 'decision states (the logs have no choice state)')


def bench_network(spec, rows, n, warm):
    """rl/bench_qnet.py run on the network: p50 / p99 per timed path (us); BENCH_GATE is the call QUtility.select
    times against B_pi (an overrun is discarded at run time and > 5% overruns disable the network, Sec. 5.7)."""
    from framelease_v4.rl import bench_qnet as BQ
    res = BQ.run(spec, rows, n=int(n), warm=int(warm))
    return {k: {s: v[s] for s in ('n', 'p50_us', 'p90_us', 'p99_us', 'max_us')} for k, v in res.items()
            if isinstance(v, dict) and 'p50_us' in v}


def deploy_check_inputs(ctx):
    return [ctx.out / f'qnet_{f}.json' for f in FAMILIES] + ctx.dataset_files()[:1] + \
        logged_decision_files(ctx.dataset())


def deploy_check_params(ctx):
    return {'bench_n': ctx.bench_n, 'bench_warm': ctx.bench_warm, 'gate': BENCH_GATE,
            'policy_budget_us': POLICY_BUDGET_S * 1e6, 'replay_problems': list(REPLAY_PROBLEMS)}


def stage_deploy_check(ctx):
    """GAP_AUDIT P3-2 (Secs. 5.7, 8.1): per network, (1) identity: schema, sha256 name, family, a_det depth = d*,
    inputs, B_pi; (2) replay_network over every logged decision row of the dataset's runs; (3) pin: the name refuses
    another network's file; (4) bench_qnet p50 / p99, the BENCH_GATE p99 at most B_pi. <out>/deploy_check.json is
    written in every case; any failed check stops the driver (StageError; no record, so a rerun repeats the check:
    a timing failure on a loaded CPU is repeated on an idle one)."""
    ds = ctx.dataset()
    files = logged_decision_files(ds)
    rows, rows_kind = bench_rows(files)
    nets = {f: network_ref(ctx.out / f'qnet_{f}.json') for f in FAMILIES}
    budget_us = POLICY_BUDGET_S * 1e6
    per, probs = {}, []
    for f in FAMILIES:
        ref, spec = nets[f]
        n_in = len(F.NO_LEASE_COLUMNS) if f == 'fqi_nolease' else len(F.ALL_COLUMNS)
        ident = {'family': ref['family'] == f, 'a_det_depth': ref['a_det_depth'] == ctx.d_star,
                 'n_inputs': ref['n_inputs'] == n_in, 'policy_budget': ref['policy_budget_s'] == POLICY_BUDGET_S}
        rep = replay_network(ref['name'], Path(ref['abs_path']), files, ctx.d_star)
        other = next((nets[g][0] for g in FAMILIES if nets[g][0]['name'] != ref['name']), None)
        pin = None if other is None else pin_refused(ref['name'], Path(other['abs_path']))
        bench = bench_network(spec, rows, ctx.bench_n, ctx.bench_warm) if rows else {}
        p99 = (bench.get(BENCH_GATE) or {}).get('p99_us')
        fails = [f'{k} mismatch' for k, ok in ident.items() if not ok]
        fails += [f'replay {k} = {v}' for k, v in rep['problems'].items()]
        fails += ['no logged choice state replayed'] if not rep['choice_rows'] else []
        fails += ['the name accepted another network file'] if pin is False else []
        fails += [f'{BENCH_GATE} p99 {p99} us > B_pi {budget_us:g} us'] if p99 is None or p99 > budget_us else []
        per[f] = {'arm': ARM_OF[f], **ref, 'identity': ident, 'replay': rep, 'pin_refuses_other_file': pin,
                  'pin_other': None if other is None else other['name'], 'bench_us': bench,
                  'bench_gate_p99_us': p99, 'ok': not fails, 'failures': fails}
        probs += [f'{f} ({ref["name"]}): {x}' for x in fails]
    doc = {'schema': DEPLOY_SCHEMA, 'mode': ctx.mode, 'd_star': ctx.d_star, 'policy_budget_us': budget_us,
           'gate': f'{BENCH_GATE} p99 <= B_pi', 'bench_states': {'n': len(rows), 'kind': rows_kind},
           'n_logged_runs': len(files), 'networks': per, 'ok': not probs, 'failures': probs,
           'host': {'cpu': _cpu_model(), 'loadavg': list(os.getloadavg()), 'affinity': sorted(os.sched_getaffinity(0)),
                    'threads': {v: os.environ.get(v) for v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
                                                              'MKL_NUM_THREADS')}},
           'checks': 'GAP_AUDIT P3-2: loaded by name through behaviour.register_utility_name + v3_shield.make_utility '
                     f'with an absolute {Q.ENV_QNET}; logged decision rows replayed through v3_shield.decide (answer '
                     'in A_feas, reason, a_det depth = d*, bypass -> a_det, no deviation without both heads); the '
                     'sha256 pin refuses another file; bench_qnet p50 / p99 against B_pi = 100 us (Sec. 5.7)'}
    path = C.atomic_json(ctx.out / 'deploy_check.json', doc)
    if probs:
        raise StageError(f'deploy_check: {len(probs)} failed check(s), see {rel(path)}: ' + '; '.join(probs[:6]))
    return {'outputs': [path], 'result': {f: {'name': v['name'], 'abs_path': v['abs_path'], 'ok': v['ok'],
                                              'choice_rows': v['replay']['choice_rows'],
                                              'deviation_rate': v['replay']['deviation_rate'],
                                              'bypass': v['replay']['bypass'],
                                              'p50_us': (v['bench_us'].get(BENCH_GATE) or {}).get('p50_us'),
                                              'p99_us': v['bench_gate_p99_us']} for f, v in per.items()}}


def _cpu_model():
    from framelease_v4.rl import bench_qnet as BQ
    return BQ.cpu_model()


# ============================================================================================ stage: freeze

def freeze_path(out, mode):
    """<out>/rl_freeze.json in production (the RL freeze of Sec. 5.9); <out>/rl_freeze_dev.json in development (the
    same contents, frozen: false, refused by load_rl_freeze: a development run is never a freeze)."""
    return Path(out) / ('rl_freeze.json' if mode == 'production' else 'rl_freeze_dev.json')


def freeze_inputs(ctx):
    extra = [] if ctx.mode != 'production' else [abs_path(ctx.manifest['path']), abs_path(ctx.freeze['path'])]
    return [record_path(ctx.out, n) for n in stage_names() if n != 'freeze'] + extra


def freeze_episodes(ctx):
    """Sec. 5.9 'the dataset manifest: episode list, and the sha256 of every source log'. Production: the entries of
    the P2 manifest (their logs were re-hashed against it when this invocation loaded it, load_p2_manifest);
    development: the dataset episodes with the sha256 of their logs now."""
    keys = ('job', 'route_id', 'kappa', 'seed', 'behaviour_seed', 'utility', 'run_dir', 'ds', 'n_choice', 'flags',
            'source_logs_sha256')
    if ctx.mode == 'production':
        return [{k: e.get(k) for k in keys} for e in ctx.manifest['doc']['episodes']]
    out = []
    for m in ctx.dataset().episodes:
        rd = abs_path(m['run_dir'])
        out.append({'job': None, 'route_id': m['route_id'], 'kappa': m.get('kappa'), 'seed': m.get('seed'),
                    'behaviour_seed': None, 'utility': m.get('utility'), 'run_dir': rel(rd),
                    'ds': m['proof']['ds_official'], 'n_choice': m['n_choice'], 'flags': [],
                    'source_logs_sha256': {n: C.sha256_file(rd / n) for n in SOURCE_LOGS if (rd / n).is_file()}})
    return out


def _estimate(sel):
    est = sel.get('estimate') or {}
    boot = est.get('bootstrap') or {}
    return {'mean_delta': est.get('mean_delta'), 'ci90': [boot.get('lo'), boot.get('hi')],
            'coverage': boot.get('coverage'), 'n_routes': boot.get('n_routes'), 'n_episodes': boot.get('n_episodes'),
            'n_boot': boot.get('n_boot'), 'unsupported_folds': est.get('unsupported_folds')}


def freeze_family(ctx, f, recs, dep):
    """The Sec. 5.9 / P3-4 entries of one family: selection report, FQE estimate and 90% CI of the selected
    candidate, refit, distillation agreement, the deployed network (sha256, name, absolute path) and its deploy
    check."""
    out = ctx.out
    sel, fit, dis = (C.read_json(out / f'{s}_{f}.json') for s in ('select', 'refit', 'distill'))
    ref, _ = network_ref(out / f'qnet_{f}.json')
    exp = recs[f'export_{f}']['result']
    if exp['name'] != ref['name']:
        raise StageError(f'freeze: qnet_{f}.json is {ref["name"]}, export_{f} recorded {exp["name"]}')
    chk = dep['networks'][f]
    model = out / fit['model'] if fit.get('model') else None        # None: not trainable (a stale file is not named)
    return {'arm': ARM_OF[f], 'not_trainable': bool(sel['not_trainable']),
            'selection_report': _file_ref(out / f'select_{f}.json'), 'selected': sel['selected'],
            'estimate': _estimate(sel), 'n_candidates': len(sel['candidates']), 'n_folds': sel['n_folds'],
            'candidates': [{'label': r['label'], **_estimate({'estimate': r})} for r in sel['candidates']],
            'fqe_not_converged': sel['fqe_not_converged'],
            'refit': {**_file_ref(out / f'refit_{f}.json'), 'label': fit.get('label'),
                      'n_transitions': fit.get('n_transitions'), 'supported': fit.get('supported'),
                      'n_samples': fit.get('n_samples'), 'model': None if model is None else _file_ref(model)},
            'distillation': {**_file_ref(out / f'distill_{f}.json'), 'deployed_agreement': exp['agreement'],
                             'deployed_hidden': exp['hidden'], 'ok': dis.get('ok'), 'target': MIN_AGREEMENT,
                             'n_states': dis.get('n_states')},
            'network': {**ref, 'arm': ARM_OF[f], 'note': exp.get('note')},
            'deploy_check': {'ok': chk['ok'], 'choice_rows': chk['replay']['choice_rows'],
                             'deviation_rate': chk['replay']['deviation_rate'], 'bypass': chk['replay']['bypass'],
                             'bench_us': chk['bench_us']}}


def stage_freeze(ctx):
    """PROTOCOL Sec. 5.9 / GAP_AUDIT P3-4: the RL freeze. Contents: the dataset manifest (episode list and the sha256
    of every source log; the P2 manifest and the tuning freeze with their sha256 and Sec. 13.2 citations), the RL
    dataset files, the reward identity, P_both and its label, per family the selection report, the FQE estimate and
    90% CI of the selected candidate, the refit, the distillation agreement, the deployed network (sha256, name
    v4_qnet_<sha12>, arm, absolute path for FRAMELEASE_V4_QNET), the deploy check, the sha256 of every
    file under framelease_v4/rl, of this driver and of the P2 gate modules (code_sha256), every deviation (open
    cases), the job lines with JOB_LINES_RULE and the names shared by arms, SEC13_NOTES, the stage chain and a sha256
    list of every file it names. Production: <out>/rl_freeze.json, frozen, entered in PROTOCOL Sec. 13 with the test
    freeze (Sec. 8.1). Development: <out>/rl_freeze_dev.json, never a freeze."""
    names = [n for n in stage_names() if n != 'freeze']
    recs = {n: read_record(record_path(ctx.out, n)) for n in names}
    dep = C.read_json(ctx.out / 'deploy_check.json')
    if not dep.get('ok'):
        raise StageError('freeze: deploy_check.json is not ok')
    fams = {f: freeze_family(ctx, f, recs, dep) for f in FAMILIES}
    ident, pb = C.read_json(ctx.out / 'reward_identity.json'), C.read_json(ctx.out / 'p_both.json')
    ds = ctx.dataset()
    prod = ctx.mode == 'production'
    doc = {'schema': FREEZE_SCHEMA, 'variant': VARIANT, 'mode': ctx.mode, 'frozen': prod,
           'created_utc': C.utc_stamp(), 'script': THIS_REL, 'd_star': ctx.d_star,
           'tuning_freeze': None if not prod else {**{k: ctx.freeze.get(k) for k in ('path', 'sha256', 'd',
                                                                                     'cited_lines')},
                                                   'L_star': {k: ctx.freeze['L'].get(k) for k in ('label', 'sha256')}},
           'p2_manifest': None if not prod else {k: ctx.manifest[k] for k in ('path', 'sha256', 'cited_lines')},
           'dev_dataset': None if prod else rel(ctx.dev_dataset),
           'dataset': {'dir': rel(ctx.dataset_dir), 'files': {rel(p): C.sha256_file(p) for p in ctx.dataset_files()},
                       'n_episodes': len(ds.episodes), 'n_transitions': ds.n,
                       'n_missing': len(ctx.manifest['missing']) if prod else None,
                       'n_registered': ctx.manifest.get('n_registered') if prod else None,
                       'missing': ctx.manifest['missing'] if prod else [], 'episodes': freeze_episodes(ctx)},
           'reward_identity': {**_file_ref(ctx.out / 'reward_identity.json'),
                               'all_identity_ok': ident['all_identity_ok'],
                               'max_abs_err_epochs': ident['max_abs_err_epochs'],
                               'max_abs_err_choice': ident['max_abs_err_choice'],
                               'terminal_only': ident['terminal_only']},
           'p_both': {**_file_ref(ctx.out / 'p_both.json'), **{k: pb[k] for k in (
               'p_both', 'label', 'kappa', 'threshold', 'decision_epochs', 'choice_epochs', 'n_episodes')},
               'metrics_v4_p_both': pb['metrics_v4']['p_both']},
           'families': fams,
           'job_lines': {ARM_OF[f]: {'utility': v['network']['name'], Q.ENV_QNET: v['network']['abs_path'],
                                     'qnet_file_sha256': v['network']['file_sha256']} for f, v in fams.items()},
           'job_lines_rule': JOB_LINES_RULE,
           'sec13_notes': {'items': list(SEC13_NOTES),
                           'note': 'to be named in the Sec. 13 test-freeze entry: where the implementation departs '
                                   'from the GAP_AUDIT wording (PROTOCOL silent)'},
           'shared_names': {n: arms for n, arms in shared_names(fams).items() if len(arms) > 1},
           'deploy_check': {**_file_ref(ctx.out / 'deploy_check.json'), 'ok': True, 'host': dep.get('host')},
           'code_sha256': code_sha256(),
           'deviations': [{**dv, 'stage': n} for n in names for dv in (recs[n].get('deviations') or [])],
           'stage_chain': [{'stage': n, 'record_sha256': C.sha256_file(record_path(ctx.out, n)),
                            'finished_utc': recs[n].get('finished_utc'), 'wall_s': recs[n].get('wall_s')}
                           for n in names],
           'entry': 'PROTOCOL Secs. 5.9 and 8.1: entered in Sec. 13 as part of the test freeze (selection.json, this '
                    'record, the P4-P6 job files); job lines take utility and FRAMELEASE_V4_QNET (absolute) from '
                    'job_lines' if prod else 'development record: never a freeze, never entered in PROTOCOL Sec. 13'}
    doc['files'] = freeze_files(doc)
    path = C.atomic_json(freeze_path(ctx.out, ctx.mode), doc)
    return {'outputs': [path], 'result': {'path': rel(path), 'frozen': prod, 'd_star': ctx.d_star,
                                          'networks': {ARM_OF[f]: v['network']['name'] for f, v in fams.items()},
                                          'p_both_label': pb['label'], 'n_deviations': len(doc['deviations'])}}


def shared_names(fams):
    """{network name: [arms]} of the freeze's families (two arms share a name when their decision cores are
    identical, e.g. two not-trainable families: JOB_LINES_RULE)."""
    out = {}
    for v in fams.values():
        out.setdefault(v['network']['name'], []).append(v['arm'])
    return out


def freeze_files(doc):
    """{path: sha256} of every file the freeze names (G-2 lists them; load_rl_freeze re-hashes them)."""
    files = dict(doc['dataset']['files'])
    for k in ('tuning_freeze', 'p2_manifest'):
        if doc.get(k):
            files[doc[k]['path']] = doc[k]['sha256']
    refs = [doc['reward_identity'], doc['p_both'], doc['deploy_check']]
    for v in doc['families'].values():
        refs += [v['selection_report'], v['refit'], v['distillation'], v['refit']['model'] or {}]
        files[v['network']['path']] = v['network']['file_sha256']
    for r in refs:
        if r.get('path'):
            files[r['path']] = r['sha256']
    return dict(sorted(files.items()))


def load_rl_freeze(path=DEFAULT_OUT / 'rl_freeze.json', require_cited=False, check_logs=True, protocol=PROTOCOL):
    """The RL freeze for its readers (the P4-P6 job generator, the test freeze, the stress tests). Refuses
    (PermissionError) a development record or one not frozen, and with require_cited one whose sha256 PROTOCOL Sec.
    13.2 does not cite (after the test-freeze entry); refuses (ValueError) another schema or variant, a named file
    whose sha256 changed, a source log whose sha256 differs from the episode list (check_logs), and a network that
    qnet.load_spec rejects or whose name, file sha256, arm, a_det depth (d*) or absolute path disagrees with the
    record. Returns the document with 'path', 'sha256' and 'cited_lines'."""
    from framelease_v4.protocol import p2_jobs as P2J
    path = Path(path)
    sha = C.sha256_file(path)
    doc = C.read_json(path)
    if not isinstance(doc, dict) or doc.get('schema') != FREEZE_SCHEMA:
        raise ValueError(f'{rel(path)}: not an RL freeze (schema {FREEZE_SCHEMA})')
    if doc.get('mode') != 'production' or doc.get('frozen') is not True:
        raise PermissionError(f'{rel(path)}: a {doc.get("mode")} record (frozen {doc.get("frozen")}) is never a freeze')
    cited = P2J.citations(sha, Path(protocol).read_text(encoding='utf-8'))
    if require_cited and not cited:
        raise PermissionError(f'{rel(path)} (sha256 {sha}) is not cited in PROTOCOL Sec. 13.2 yet')
    probs = [] if doc.get('variant') == VARIANT else [f'variant {doc.get("variant")!r} != {VARIANT}']
    for k, h in (doc.get('files') or {}).items():
        p = abs_path(k)
        cur = C.sha256_file(p) if p.is_file() else None
        if cur != h:
            probs.append(f'{k}: sha256 {cur} != recorded {h}')
    for e in (doc.get('dataset') or {}).get('episodes') or [] if check_logs else []:
        rd = abs_path(str(e.get('run_dir')))
        for n, h in sorted((e.get('source_logs_sha256') or {}).items()):
            cur = C.sha256_file(rd / n) if (rd / n).is_file() else None
            if cur != h:
                probs.append(f'{e.get("run_dir")}/{n}: sha256 {cur} != recorded {h}')
    for f in FAMILIES:
        net = ((doc.get('families') or {}).get(f) or {}).get('network') or {}
        line = (doc.get('job_lines') or {}).get(ARM_OF[f]) or {}
        try:
            ref, _ = network_ref(abs_path(str(net.get('path'))))
        except (OSError, ValueError, KeyError) as e:
            probs.append(f'{f}: network {net.get("path")}: {e}')
            continue
        want = {'name': ref['name'], 'file_sha256': ref['file_sha256'], 'abs_path': ref['abs_path'],
                'a_det_depth': doc.get('d_star'), 'arm': ARM_OF[f]}
        probs += [f'{f}: network {k} {net.get(k)!r} != {v!r}' for k, v in want.items() if net.get(k) != v]
        if (line.get('utility'), line.get(Q.ENV_QNET)) != (ref['name'], ref['abs_path']):
            probs.append(f'{f}: job line {line} does not name {ref["name"]} at {ref["abs_path"]}')
    if probs:
        raise ValueError(f'{rel(path)} (sha256 {sha}) is refused:\n  ' + '\n  '.join(probs[:40]))
    return {**doc, 'path': rel(path), 'sha256': sha, 'cited_lines': cited}


# ============================================================================================ stage list

def stage_names():
    return ['dataset', 'p_both'] + [f'{s}_{f}' for f in FAMILIES for s in ('select', 'refit', 'distill', 'export')] + \
        ['deploy_check', 'freeze']


def distill_inputs(ctx, family):
    fp = ctx.out / f'refit_{family}.json'
    extra = []
    if fp.is_file() and not C.read_json(fp).get('not_trainable'):
        extra = [ctx.out / f'refit_{family}.joblib']
    return ctx.dataset_files() + [fp] + extra


def stage_list():
    """The stages in chain order (Stage(name, inputs, run, params))."""
    out = [Stage('dataset', dataset_inputs, stage_dataset, dataset_params),
           Stage('p_both', lambda ctx: ctx.dataset_files() + p_both_logs(ctx.dataset()), stage_p_both,
                 lambda ctx: {'kappa': P_BOTH_KAPPA, 'threshold': P_BOTH_MIN})]
    for f in FAMILIES:
        out += [
            Stage(f'select_{f}', lambda ctx: ctx.dataset_files(), lambda ctx, f=f: stage_select(ctx, f),
                  lambda ctx, f=f: select_params(ctx, f)),
            Stage(f'refit_{f}', lambda ctx, f=f: ctx.dataset_files() + [ctx.out / f'select_{f}.json'],
                  lambda ctx, f=f: stage_refit(ctx, f), lambda ctx, f=f: {'family': f}),
            Stage(f'distill_{f}', lambda ctx, f=f: distill_inputs(ctx, f), lambda ctx, f=f: stage_distill(ctx, f),
                  lambda ctx, f=f: {'family': f, 'min_agreement': MIN_AGREEMENT, 'hidden': [32, 32],
                                    'retry_hidden': [64, 64], 'seed': 0}),
            Stage(f'export_{f}', lambda ctx, f=f: ctx.dataset_files()[:1] + [ctx.out / f'{s}_{f}.json' for s in (
                'select', 'refit', 'distill')], lambda ctx, f=f: stage_export(ctx, f),
                lambda ctx, f=f: {'family': f, 'policy_budget_s': POLICY_BUDGET_S})]
    out += [Stage('deploy_check', deploy_check_inputs, stage_deploy_check, deploy_check_params),
            Stage('freeze', freeze_inputs, stage_freeze, lambda ctx: {'file': freeze_path(ctx.out, ctx.mode).name})]
    assert [st.name for st in out] == stage_names()
    return out


# ============================================================================================ status

def status(out, log=_print):
    """Reads only: the state of every stage record in out, in chain order: 'done' (schema, chain link and the sha256
    of every input and output consistent), 'inconsistent' (with the reasons) or 'missing'. The parameters are not
    compared (they come from the invocation's inputs; run compares them and stops on a difference). Returns
    {'done', 'inconsistent', 'missing'} (lists of stage names)."""
    out = Path(out).resolve()
    res = {'done': [], 'inconsistent': [], 'missing': []}
    prev = None
    for n in stage_names():
        p = record_path(out, n)
        if not p.exists():
            res['missing'].append(n)
            log(f'{n:22s} missing')
            prev = None
            continue
        rec = read_record(p)
        probs = record_problems(rec, n, prev, (rec or {}).get('params') or {}, out)
        prev = {'stage': n, 'sha256': C.sha256_file(p)}
        if probs:
            res['inconsistent'].append(n)
            log(f'{n:22s} INCONSISTENT: ' + '; '.join(probs[:3]))
            continue
        res['done'].append(n)
        dv = ', '.join(f'{d.get("case")} -> {d.get("option")}' for d in rec.get('deviations') or [])
        log(f'{n:22s} done  {rec.get("finished_utc")}  {rec.get("wall_s", 0):9.1f} s  mode {rec.get("mode")}'
            + (f'  deviations: {dv}' if dv else '') + f'  {json.dumps(C.jsonable(rec.get("result")))[:160]}')
    return res


# ============================================================================================ calibrate (P3-5)

CAL_EPISODES = 132                  # Sec. 5.3: 44 training routes x kappa {1.0, 1.5, 2.0}
CAL_LENGTHS = (20, 150)             # GAP_AUDIT P3-5: choice transitions per episode (uniform)
CAL_SIZES = (33, 66, 132)           # probe sizes in episodes (the calibration at P3 start)
CAL_SIZES_DEV = (11, 22, 44)        # scaled-down probe sizes (development: one E-core, other work on the machine)
CAL_SEED = 20261111
CAL_DEVIATION = (0.1, 0.3, 0.5)     # scenarios: share of states where the candidate deviates from a_det^{d*}
CAL_TIE = 0.01                      # n_jobs within 1% of the fastest prediction count as equal (fewer workers win)
CAL_OUT_ALLOWED = ('outputs/framelease_v4/build',)   # inside the project the calibration writes only here


def calibration_lengths(n, seed=CAL_SEED, lengths_from=None):
    """Choice transitions of n episodes: uniform in CAL_LENGTHS, or a seeded draw (without replacement while
    possible) from the training episodes of a dataset directory (lengths_from: the P2 dataset at P3 start)."""
    rng = np.random.default_rng(seed + int(n))
    if lengths_from is None:
        return [int(x) for x in rng.integers(CAL_LENGTHS[0], CAL_LENGTHS[1] + 1, int(n))]
    pool = train_lengths(lengths_from)
    return [int(x) for x in rng.choice(pool, int(n), replace=int(n) > len(pool))]


def train_lengths(dataset_dir):
    """Choice transitions of every training episode with a choice epoch of a dataset directory."""
    pool = [int(e['n_choice']) for e in C.read_json(Path(dataset_dir) / 'episodes.json')
            if e.get('split') == 'train' and int(e.get('n_choice') or 0) > 0]
    if not pool:
        raise ValueError(f'{dataset_dir}: no training episode with a choice epoch')
    return pool


def synthetic_dataset(lengths, d_star, seed=CAL_SEED):
    """A dataset.Dataset of the P2 shape, for timing only: episode e on route 'cal<e // 3>' at kappa KAPPAS[e % 3]
    with lengths[e] choice transitions; states uniform in each feature's clip range (depth 1-9, the episode's
    kappa); the behaviour of Sec. 5.3 (eps 0.3 around a_det^{d*}, mu logged); rewards with a weak state-action
    signal plus noise; the evaluation covariates and window gains that ope.select and trainers.fit_candidate read."""
    rng = np.random.default_rng(seed)
    lo, hi = np.array([f.lo for f in F.FEATURES]), np.array([f.hi for f in F.FEATURES])
    dcol, kcol, scol = F.NAMES.index('depth'), F.NAMES.index('kappa'), F.NAMES.index('lease_slack_s')
    parts, episodes = [], []
    for e, n in enumerate(int(x) for x in lengths):
        X = rng.uniform(lo, hi, (n, F.N_FEATURES))
        X[:, dcol] = rng.integers(1, 10, n)             # a choice state is below the shield's max depth 10
        X[:, kcol] = KAPPAS[e % 3]
        base = TR.default_actions(X, d_star)
        A = np.where(rng.uniform(size=n) < EPS, rng.integers(0, 2, n), base).astype(np.int8)
        R = 0.05 * rng.standard_normal(n) + 0.1 * np.where(A == 1, np.sign(X[:, scol]), 0.0)
        T = np.cumsum(rng.uniform(0.1, 1.0, n))
        done, first = np.zeros(n, bool), np.zeros(n, bool)
        done[-1], first[0] = True, True
        XE = np.stack([np.linspace(0.0, 100.0, n), np.ones(n), T], 1)
        arr = {'X': X, 'XN': np.vstack([X[1:], np.zeros((1, F.N_FEATURES))]), 'A': A, 'R': R, 'DONE': done,
               'MU': np.where(A == base, 1 - EPS / 2, EPS / 2), 'BASE': base, 'T': T, 'G': np.cumsum(R[::-1])[::-1],
               'FIRST': first, 'XE': XE, 'XEN': np.vstack([XE[1:], np.zeros((1, 3))]),
               'EP': np.full(n, e, np.int32)}
        for w in D.WINDOWS_S:
            arr[f'GW{w:g}'] = R + 0.02 * rng.standard_normal(n)
        parts.append(arr)
        episodes.append({'route_id': f'cal{e // 3}', 'kappa': KAPPAS[e % 3], 'split': 'train', 'kind': 'synthetic',
                         'n_choice': n, 'ds': float(R.sum()), 'pre_choice_return': 0.0, 'run_id': f'cal{e}'})
    arrays = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    return D.Dataset(arrays, episodes, {'schema': 'framelease_v4.p3_rl_calibration_synthetic/1', 'seed': seed})


def cpu_topology():
    """[{'cpu', 'core', 'max_khz'}] of the online CPUs from /sys (empty when unreadable)."""
    out = []
    for d in Path('/sys/devices/system/cpu').glob('cpu[0-9]*'):
        try:
            core = f"{(d / 'topology' / 'physical_package_id').read_text().strip()}:" \
                   f"{(d / 'topology' / 'core_id').read_text().strip()}"
            out.append({'cpu': int(d.name[3:]), 'core': core,
                        'max_khz': int((d / 'cpufreq' / 'cpuinfo_max_freq').read_text())})
        except (OSError, ValueError):
            continue
    return sorted(out, key=lambda t: t['cpu'])


def worker_speeds(n_workers, topo, ref_khz, smt_share=0.5, fast_core_ipc=1.0):
    """Speed of each of n_workers busy workers relative to the probe CPU (ref_khz), fastest first. Placement: one
    worker per physical core, faster cores first, then the second SMT thread of the SMT cores. A core's speed is its
    maximum-frequency ratio to the probe CPU (times fast_core_ipc for a faster core type); two busy SMT siblings get
    smt_share of their core each (0.5: no SMT gain). Without a topology every worker has speed 1."""
    if not topo:
        return [1.0] * int(n_workers)
    cores = {}
    for t in topo:
        cores.setdefault(t['core'], []).append(t)
    order = sorted(cores.values(), key=lambda ts: -ts[0]['max_khz'])
    speed = [ts[0]['max_khz'] / ref_khz * (fast_core_ipc if ts[0]['max_khz'] > ref_khz else 1.0) for ts in order]
    smt = [i for i, ts in enumerate(order) if len(ts) > 1]
    n1 = min(int(n_workers), len(order))
    n2 = min(int(n_workers) - n1, len(smt))
    shared = set(smt[:n2])
    out = [speed[i] * (smt_share if i in shared else 1.0) for i in range(n1)] + [speed[i] * smt_share
                                                                                  for i in smt[:n2]]
    return sorted(out, reverse=True)


def list_schedule(durations, speeds):
    """Makespan of the tasks in the given order on workers of the given speeds: each task goes to the worker that
    is free first (a faster one at a tie), as joblib hands out ope.select's (candidate, fold) jobs in order."""
    import heapq
    heap = [(0.0, -s, i) for i, s in enumerate(speeds)]
    heapq.heapify(heap)
    end = 0.0
    for d in durations:
        t, ns, i = heapq.heappop(heap)
        fin = t + d / -ns
        end = max(end, fin)
        heapq.heappush(heap, (fin, ns, i))
    return end


def cost_fit(points):
    """t = c + a n ln n over [(n rows, t seconds)] by non-negative least squares: c the per-call overhead (Python and
    per-tree costs), a n ln n the work of an ExtraTrees fit or prediction (random splits over every row of a node,
    depth ~ ln n). The rows must span a factor of 1.5 at least. rel_residual: the largest relative misfit."""
    from scipy.optimize import nnls
    n = np.array([max(float(p[0]), 2.0) for p in points])
    t = np.array([max(float(p[1]), 0.0) for p in points])
    if len(points) < 2 or n.max() / n.min() < 1.5:
        raise ValueError(f'cost_fit: the probe rows {[p[0] for p in points]} span less than a factor of 1.5 '
                         '(use larger, more distant --sizes)')
    (c, a), _ = nnls(np.stack([np.ones_like(n), n * np.log(n)], 1), t)
    fit = {'form': 'c + a n ln n', 'c': float(c), 'a': float(a), 'points': [[float(x), float(y)] for x, y in points]}
    pred = np.array([_cost(fit, x) for x in n])
    fit['rel_residual'] = float(np.max(np.abs(pred - t) / np.maximum(t, 1e-9))) if t.max() > 0 else 0.0
    return fit


def _cost(fit, n):
    n = max(float(n), 2.0)
    return fit['c'] + fit['a'] * n * np.log(n)


def _cpu_timed(fn, *a, **kw):
    """(result, CPU seconds of this process, wall seconds): the model uses CPU time (other work on the machine
    stretches the wall time of a probe, not the work it does)."""
    t0, c0 = time.perf_counter(), time.process_time()
    res = fn(*a, **kw)
    return res, time.process_time() - c0, time.perf_counter() - t0


def config_key(c):
    """The cost class of a candidate: family, leaf size and pessimism (the horizon multiplies the per-iteration
    cost; the bandit window changes only the target)."""
    return f'{c.family}_leaf{c.min_samples_leaf}_beta{c.beta:g}'


def probe_candidates(d_star):
    """One registered candidate per cost class (trainers.grid of each family at d_det = d*)."""
    out = {}
    for f in FAMILIES:
        for c in TR.grid(f, d_det=d_star):
            out.setdefault(config_key(c), c)
    return out


def deviating_policy(d_star, share):
    """A deterministic policy that deviates from a_det^{d*} on a share of the states (a hash of two state columns);
    it sets the FQE horizon of a scenario."""
    def act(X16):
        X16 = np.asarray(X16, dtype=np.float64)
        dflt = TR.default_actions(X16, d_star)
        u = np.modf(np.abs(X16[:, 0]) * 7919.0 + np.abs(X16[:, 6]) * 104729.0)[0] if len(X16) else np.zeros(0)
        return np.where(u < share, 1 - dflt, dflt).astype(np.int8)
    return act


def _task_rest(ds, ev, pol, models):
    """The work of an ope.select task besides the fit and the FQE iterations: the candidate's actions on the
    held-out states and the importance-sampling diagnostics (ope._eval_fold)."""
    m = ds.episode_mask(ev)
    pol(ds.XN[m & ~ds.DONE])
    pol(ds.X[m & ds.FIRST])
    pol(ds.X[m])
    O.importance_diagnostics(ds, ev, pol, models, q_models_cov=True)


def warm_up(d_star, seed=CAL_SEED):
    """One untimed pass of every probed call on a 6-episode dataset: imports (sklearn) and first-call costs stay out
    of the timings."""
    ds = synthetic_dataset(calibration_lengths(6, seed), d_star, seed)
    ids = ds.train_episode_ids()
    ev = O.route_folds(ds, ids, N_FOLDS)[0]
    fit = sorted(set(ids) - set(ev))
    r = O.fqe(ds, ev, TR.heuristic_policy_fn(d_star), O.FQEConfig(iter_cap=2))
    O.behaviour_calibration(ds, ev, O.FQEConfig())
    cand = next(iter(probe_candidates(d_star).values()))
    q, _ = TR.fit_candidate(ds, fit, cand.__class__(**{**cand.as_dict(), 'horizon': 2}))
    _task_rest(ds, ev, TR.policy_fn(q, cand), r['models'])


def probe_size(ds, d_star, log=_print):
    """CPU seconds of the parts of one ope.select task on fold 0 of ds (route-grouped, 5 folds): per cost class the
    first fit_candidate iteration and each further one (horizon 1 and 3), and the rest of the task; the FQE
    overhead and per-iteration cost (iteration caps 1 and 3) and the behaviour calibration on the held-out fold."""
    from dataclasses import replace
    ids = ds.train_episode_ids()
    ev = O.route_folds(ds, ids, N_FOLDS)[0]
    fit = sorted(set(ids) - set(ev))
    n_fit, n_eval = int(ds.episode_mask(fit).sum()), int(ds.episode_mask(ev).sum())
    heur = TR.heuristic_policy_fn(d_star)
    r1, c1, _ = _cpu_timed(O.fqe, ds, ev, heur, O.FQEConfig(iter_cap=1))
    r3, c3, _ = _cpu_timed(O.fqe, ds, ev, heur, O.FQEConfig(iter_cap=3))
    k = max(int(r3['iterations']) - int(r1['iterations']), 1)
    fqe_iter = max((c3 - c1) / k, 0.0)
    _, c_cal, _ = _cpu_timed(O.behaviour_calibration, ds, ev, O.FQEConfig())
    res = {'n_episodes': len(ds.episodes), 'n_rows': ds.n, 'n_fit': n_fit, 'n_eval': n_eval, 'fqe_iter_s': fqe_iter,
           'fqe_overhead_s': max(c1 - fqe_iter, 0.0), 'calibration_s': c_cal, 'configs': {}}
    for key, cand in probe_candidates(d_star).items():
        if cand.family == 'bandit':
            (q, _), c_first, _ = _cpu_timed(TR.fit_candidate, ds, fit, cand)
            c_iter = 0.0
        else:
            _, c_first, _ = _cpu_timed(TR.fit_candidate, ds, fit, replace(cand, horizon=1))
            (q, _), c_k3, _ = _cpu_timed(TR.fit_candidate, ds, fit, replace(cand, horizon=3))
            c_iter = max((c_k3 - c_first) / 2.0, 0.0)
        _, c_rest, _ = _cpu_timed(_task_rest, ds, ev, TR.policy_fn(q, cand), r3['models'])
        res['configs'][key] = {'first_s': c_first, 'iter_s': c_iter, 'rest_s': c_rest}
        log(f'  probe {len(ds.episodes):4d} episodes ({n_fit} fit / {n_eval} held-out rows) {key}: first '
            f'{c_first:.2f} s, per iteration {c_iter:.2f} s, rest {c_rest:.2f} s')
    return res


def fit_model(probes):
    """Cost laws (cost_fit) of every probed part: the fit parts against the fit rows, the others against the held-out
    rows."""
    def law(n_key, get):
        return cost_fit([(p[n_key], get(p)) for p in probes])
    model = {k: law('n_eval', lambda p, k=k: p[k]) for k in ('fqe_iter_s', 'fqe_overhead_s', 'calibration_s')}
    model['configs'] = {key: {'first_s': law('n_fit', lambda p, key=key: p['configs'][key]['first_s']),
                              'iter_s': law('n_fit', lambda p, key=key: p['configs'][key]['iter_s']),
                              'rest_s': law('n_eval', lambda p, key=key: p['configs'][key]['rest_s'])}
                        for key in probes[0]['configs']}
    return model


def task_seconds(model, cand, n_fit, n_eval, fqe_iterations):
    """Predicted CPU seconds of one ope.select task (ope._eval_fold): fit_candidate with the candidate's horizon,
    FQE with the given iterations, the rest."""
    m = model['configs'][config_key(cand)]
    k = 1 if cand.family == 'bandit' else int(cand.horizon)
    return (_cost(m['first_s'], n_fit) + (k - 1) * _cost(m['iter_s'], n_fit) + _cost(m['rest_s'], n_eval)
            + _cost(model['fqe_overhead_s'], n_eval) + int(fqe_iterations) * _cost(model['fqe_iter_s'], n_eval))


def serial_seconds(model, n_evals, heuristic_iterations):
    """ope.select before its parallel part (in the calling process): per fold the FQE of a_det^{d*} and the
    behaviour calibration."""
    return sum(_cost(model['fqe_overhead_s'], n) + int(it) * _cost(model['fqe_iter_s'], n)
               + _cost(model['calibration_s'], n) for n, it in zip(n_evals, heuristic_iterations))


def target_shapes(ds, d_star):
    """The production folds (ope.route_folds, 5) of the target dataset with their fit and held-out rows, and the FQE
    iterations per fold (ope.fqe's horizon rule, iteration cap of FQEConfig()): 'adet' for a_det^{d*} (the
    selection's reference; a candidate equal to it), 'dev<s>' for a candidate deviating on a share s of the states,
    and the bound 'worst' (every live transition bootstraps: the longest held-out episode + 1)."""
    ids = ds.train_episode_ids()
    cap = int(O.FQEConfig().iter_cap)
    pols = {'adet': TR.heuristic_policy_fn(d_star), **{f'dev{s:g}': deviating_policy(d_star, s) for s in CAL_DEVIATION}}
    folds = []
    for ev in O.route_folds(ds, ids, N_FOLDS):
        row = {'episodes': len(ev), 'n_fit': int(ds.episode_mask(sorted(set(ids) - set(ev))).sum()),
               'n_eval': int(ds.episode_mask(ev).sum()), 'iterations': {}}
        for name, pol in pols.items():
            row['iterations'][name] = min(int(O.fqe(ds, ev, pol, O.FQEConfig(iter_cap=1))['horizon']) + 1, cap)
        row['iterations']['worst'] = min(max(int(ds.episodes[i]['n_choice']) for i in ev) + 1, cap)
        folds.append(row)
    return {'n_episodes': len(ids), 'n_rows': ds.n, 'folds': folds}


def validate_model(ds, model, d_star):
    """In-sample check at the smallest probe size: one real ope.select (n_jobs 1, FQEConfig(), 5 folds, 2000
    resamples) of the first two horizon-8 fqi candidates of the grid; its CPU time against the model's prediction
    for the same folds and the FQE iterations the selection reported."""
    cands = [c for c in TR.grid('fqi', d_det=d_star) if c.horizon == 8][:2]
    ids = ds.train_episode_ids()
    rep, cpu, wall = _cpu_timed(O.select, ds, cands, ids, n_folds=N_FOLDS, fqe_cfg=O.FQEConfig(), n_jobs=1,
                                n_boot=N_BOOT)
    folds = rep['folds']
    n_fit = [int(ds.episode_mask(sorted(set(ids) - set(ev))).sum()) for ev in folds]
    n_eval = [int(ds.episode_mask(ev).sum()) for ev in folds]
    heur = [int(rep['heuristic'][k]['iterations']) for k in range(len(folds))]
    pred = serial_seconds(model, n_eval, heur)
    its = {}
    for row, cand in zip(rep['candidates'], cands):
        its[cand.label] = [int(fo['fqe_iterations']) for fo in row['folds']]
        pred += sum(task_seconds(model, cand, n_fit[k], n_eval[k], it) for k, it in enumerate(its[cand.label]))
    return {'n_episodes': len(ds.episodes), 'n_folds': len(folds), 'candidates': [c.label for c in cands],
            'fqe_iterations': its, 'heuristic_iterations': heur, 'measured_cpu_s': cpu, 'measured_wall_s': wall,
            'predicted_cpu_s': pred, 'ratio_measured_to_predicted': cpu / pred if pred > 0 else None}


def predict_walls(model, shapes, d_star, speeds_by_w, scale=1.0):
    """Predicted wall seconds of the three select_<family> stages (run one after the other) per FQE scenario and
    number of workers: per family the serial part on the fastest worker plus the list-scheduled makespan of the
    12 candidates x 5 folds tasks in ope.select's job order; every prediction times scale."""
    n_evals = [fo['n_eval'] for fo in shapes['folds']]
    serial = serial_seconds(model, n_evals, [fo['iterations']['adet'] for fo in shapes['folds']]) * scale
    out = {}
    for s in shapes['folds'][0]['iterations']:
        fams = {}
        for fam in FAMILIES:
            durs = [task_seconds(model, c, fo['n_fit'], fo['n_eval'], fo['iterations'][s]) * scale
                    for c in TR.grid(fam, d_det=d_star) for fo in shapes['folds']]
            fams[fam] = {'tasks': len(durs), 'task_cpu_s': sum(durs), 'longest_task_s': max(durs), 'serial_s': serial,
                         'wall_s': {w: serial / sp[0] + list_schedule(durs, sp) for w, sp in speeds_by_w.items()}}
        out[s] = {'families': fams, 'wall_s': {w: sum(fams[f]['wall_s'][w] for f in FAMILIES) for w in speeds_by_w}}
    return out


def recommend_n_jobs(pred):
    """--n-jobs: the number of workers with the smallest worst-case (over the FQE scenarios) predicted wall time;
    within CAL_TIE of it the smaller number wins (less memory, room for the system)."""
    ws = sorted(next(iter(pred.values()))['wall_s'])
    worst = {w: max(p['wall_s'][w] for p in pred.values()) for w in ws}
    best = min(worst.values())
    n = min(w for w in ws if worst[w] <= best * (1.0 + CAL_TIE))
    return {'n_jobs': n, 'worst_case_wall_s': worst[n], 'wall_s_by_scenario': {s: p['wall_s'][n] for s, p in
                                                                             pred.items()},
            'rule': f'smallest n_jobs within {CAL_TIE:.0%} of the minimum worst-case (over the FQE scenarios) '
                    'predicted wall time of the three select stages'}


def _mem_available_mb():
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemAvailable:'):
                return int(line.split()[1]) / 1024.0
    except (OSError, ValueError, IndexError):
        pass
    return None


def calibration_out(path):
    """The calibration file: never in the default output directory; inside the project only under
    CAL_OUT_ALLOWED (scratch otherwise, GAP_AUDIT P3-5)."""
    p = Path(path).resolve()
    if _inside(p, DEFAULT_OUT) or (_inside(p, ROOT) and not any(_inside(p, ROOT / a) for a in CAL_OUT_ALLOWED)):
        raise PermissionError(f'{p}: the calibration writes outside the project or under {", ".join(CAL_OUT_ALLOWED)}')
    return C._check_writable(p)


def calibrate(args, log=_print):
    """GAP_AUDIT P3-5: the wall-time model of select_<family> at the production size, to set --n-jobs. Serial probes
    (one process, CPU time) of every part of an ope.select task on synthetic datasets of the P2 shape (sizes in
    episodes, 20-150 choice transitions each, or the lengths of a dataset), a cost law c + a n ln n per part in the
    rows, the production folds and FQE iterations per scenario on a synthetic dataset of the target size, an
    in-sample validation (one real ope.select; the predictions are scaled by the measured / predicted ratio when it
    exceeds 1), and list scheduling of the 36 candidates x 5 folds over 1..threads workers of the machine's cores.
    Writes the calibration JSON (args.out) and returns 0."""
    import resource
    out = calibration_out(args.out)
    sizes = sorted({int(s) for s in str(args.sizes).split(',') if s.strip()})
    if len(sizes) < 2 or sizes[0] < 3:
        raise ValueError(f'--sizes {args.sizes}: at least two probe sizes of >= 3 episodes')
    t0, load0, d_star, seed = time.time(), list(os.getloadavg()), int(args.d_star), int(args.seed)
    lengths_from = None if args.lengths_from is None else Path(args.lengths_from).resolve()
    target_n = CAL_EPISODES if lengths_from is None else len(train_lengths(lengths_from))
    log(f'calibrate: sizes {sizes} episodes, target {target_n} episodes, d* {d_star}, out {out}')
    warm_up(d_star, seed)
    probes, first_ds = [], None
    for n in sizes:
        ds = synthetic_dataset(calibration_lengths(n, seed, lengths_from), d_star, seed + n)
        first_ds = first_ds or ds
        probes.append(probe_size(ds, d_star, log))
    model = fit_model(probes)
    shapes = target_shapes(synthetic_dataset(calibration_lengths(target_n, seed, lengths_from), d_star,
                                             seed + target_n), d_star)
    log(f'  target folds: {[(fo["n_fit"], fo["n_eval"], fo["iterations"]) for fo in shapes["folds"]]}')
    val = None if args.no_validate else validate_model(first_ds, model, d_star)
    if val:
        log(f'  validation ({val["n_episodes"]} episodes): measured {val["measured_cpu_s"]:.1f} s CPU, predicted '
            f'{val["predicted_cpu_s"]:.1f} s (ratio {val["ratio_measured_to_predicted"]:.2f})')
    scale = max(1.0, (val or {}).get('ratio_measured_to_predicted') or 1.0)
    topo = cpu_topology()
    aff = sorted(os.sched_getaffinity(0))
    ref_khz = max((t['max_khz'] for t in topo if t['cpu'] in aff), default=None)
    speeds = {w: worker_speeds(w, topo if ref_khz else [], ref_khz or 1, args.smt_share, args.fast_core_ipc)
              for w in range(1, int(args.threads) + 1)}
    pred = predict_walls(model, shapes, d_star, speeds, scale)
    rec = recommend_n_jobs(pred)
    n_all = shapes['n_rows']
    refit = {f: max(_cost(model['configs'][config_key(c)]['first_s'], n_all) + (
        (1 if c.family == 'bandit' else c.horizon) - 1) * _cost(model['configs'][config_key(c)]['iter_s'], n_all)
        for c in TR.grid(f, d_det=d_star)) * scale for f in FAMILIES}
    rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    avail = _mem_available_mb()
    doc = {'schema': CALIBRATION_SCHEMA, 'script': THIS_REL, 'created_utc': C.utc_stamp(),
           'kind': 'development (scaled-down probe sizes)' if sizes[-1] < target_n else 'production size',
           'code_sha256': code_sha256(),
           'target': {'n_episodes': target_n,
                      'lengths': list(CAL_LENGTHS) if lengths_from is None else rel(lengths_from),
                      'n_folds': N_FOLDS, 'families': list(FAMILIES), 'candidates_per_family': len(TR.grid('fqi')),
                      'tasks_per_family': len(TR.grid('fqi')) * len(shapes['folds']),
                      'fqe': O.FQEConfig().as_dict(), 'd_star': d_star, 'threads': int(args.threads)},
           'probe': {'sizes': sizes, 'seed': seed, 'clock': 'time.process_time (CPU seconds of this process)',
                     'results': probes},
           'model': model, 'target_shapes': shapes, 'validation': val, 'scale': scale,
           'workers': {'topology': topo, 'probe_affinity': aff, 'reference_khz': ref_khz, 'smt_share': args.smt_share,
                       'fast_core_ipc': args.fast_core_ipc, 'speeds': speeds,
                       'placement': 'one worker per physical core (fastest first), then the second SMT threads; '
                                    'a core speed is its max-frequency ratio to the probe CPU (x fast_core_ipc for '
                                    'a faster core type); busy SMT siblings get smt_share of the core each'},
           'prediction': pred, 'recommendation': rec,
           'refit_worst_s': refit, 'not_modelled': 'distillation (trainers.distill, minutes) and the bootstrap',
           'memory': {'probe_max_rss_mb': rss_mb, 'mem_available_mb': avail,
                      'recommended_workers_mb': rss_mb * rec['n_jobs'],
                      'note': 'per-worker memory taken as this probe process\'s peak (largest probe size)'},
           'host': {'cpu': _cpu_model(), 'nproc': os.cpu_count(), 'loadavg_start': load0,
                    'loadavg_end': list(os.getloadavg())},
           'wall_s': round(time.time() - t0, 1)}
    C.atomic_json(out, doc)
    log(f'calibrate: n_jobs {rec["n_jobs"]}: predicted select wall {rec["worst_case_wall_s"] / 3600:.2f} h worst case; '
        + ', '.join(f'{s} {v / 3600:.2f} h' for s, v in rec['wall_s_by_scenario'].items())
        + f'; refit worst {sum(refit.values()) / 60:.1f} min; {doc["wall_s"]:.0f} s; {rel(out)}')
    return 0


# ============================================================================================ CLI

def _inside(p, root):
    try:
        Path(p).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def make_ctx(args, log=_print):
    """Ctx of a 'run' invocation. Production: the tuning freeze (cited in Sec. 13.2, sealed PROTOCOL) and the P2
    manifest are loaded and checked first. Development (--dev-dataset): never the default output directory."""
    options = {'no_selectable': args.no_selectable, 'distill_shortfall': args.distill_shortfall,
               'missing_episodes': args.missing_episodes}
    out = Path(args.out).resolve()                                    # CLI paths: relative to the working directory
    dev_opts = [n for n, v in (('--smoke', args.smoke), ('--n-folds', args.n_folds), ('--dev-d-star', args.dev_d_star),
                               ('--bench-n', args.bench_n)) if v not in (None, False)]
    if args.dev_dataset is None:
        if dev_opts:
            raise ValueError(f'{", ".join(dev_opts)}: development options need --dev-dataset')
        if 'PYTEST_CURRENT_TEST' in os.environ and _inside(out, DEFAULT_OUT):
            raise PermissionError(f'tests never write {rel(DEFAULT_OUT)}')
        freeze = load_tuning_freeze(Path(args.selection).resolve())
        man = load_p2_manifest(Path(args.manifest).resolve(), freeze, args.missing_episodes)
        return Ctx(out, 'production', freeze['d'], options, n_jobs=args.n_jobs, manifest=man, freeze=freeze, log=log)
    if _inside(out, DEFAULT_OUT):
        raise PermissionError(f'development runs never write {rel(DEFAULT_OUT)} (use a scratch directory)')
    if args.dev_d_star is None:
        raise ValueError('--dev-dataset needs --dev-d-star (the a_det depth of the development data)')
    fqe = None
    if args.smoke:
        from framelease_v4.rl.smoke import SMOKE_FQE as fqe
    return Ctx(out, 'development', args.dev_d_star, options, n_jobs=args.n_jobs,
               n_folds=args.n_folds or N_FOLDS, fqe_cfg=fqe, grid_kind='smoke' if args.smoke else 'registered',
               n_boot=500 if args.smoke else N_BOOT, dev_dataset=Path(args.dev_dataset).resolve(), log=log,
               bench_n=args.bench_n or BENCH_N, bench_warm=min(BENCH_WARM, args.bench_n or BENCH_WARM))


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run', help='run (or resume) the stages')
    r.add_argument('--manifest', type=Path, default=P2_MANIFEST, help='P2 data manifest (p2_check.py --write)')
    r.add_argument('--selection', type=Path, default=TUNING_FREEZE, help='tuning freeze (select_stage.py --freeze)')
    r.add_argument('--out', type=Path, default=DEFAULT_OUT)
    r.add_argument('--n-jobs', type=int, default=1, help='ope.select workers (set from calibrate)')
    r.add_argument('--stop-after', choices=stage_names(), default=None)
    r.add_argument('--redo', action='store_true', help='recompute an inconsistent stage and every later one')
    for case, (dflt, alt, rule) in OPEN_CASES.items():
        r.add_argument('--' + case.replace('_', '-'), choices=(dflt, alt), default=dflt,
                       help=f'GAP_AUDIT Sec. 6 item 5 {rule}; default {dflt}; {alt}: {RECORD_NOTE}')
    g = r.add_argument_group('development (never frozen, never the default output directory)')
    g.add_argument('--dev-dataset', type=Path, default=None, help='prebuilt dataset directory (read-only, copied)')
    g.add_argument('--dev-d-star', type=int, default=None, help='a_det depth of the development data')
    g.add_argument('--smoke', action='store_true', help='trainers.grid(smoke=True), smoke FQE config, 500 resamples')
    g.add_argument('--n-folds', type=int, default=None)
    g.add_argument('--bench-n', type=int, default=None, help=f'deploy_check bench calls per path (default {BENCH_N})')
    s = sub.add_parser('status', help='state of every stage record (reads only)')
    s.add_argument('--out', type=Path, default=DEFAULT_OUT)
    c = sub.add_parser('calibrate', help='GAP_AUDIT P3-5: wall-time model of select_<family> at the production size '
                                         '(sets --n-jobs)')
    c.add_argument('--out', type=Path, default=Path('/tmp/P3RL/calibrate/calibration.json'),
                   help=f'calibration JSON (outside the project or under {", ".join(CAL_OUT_ALLOWED)})')
    c.add_argument('--sizes', default=','.join(map(str, CAL_SIZES)),
                   help=f'probe sizes in episodes (development: {",".join(map(str, CAL_SIZES_DEV))})')
    c.add_argument('--d-star', type=int, default=10, help='a_det depth (the tuning freeze d* at P3 start)')
    c.add_argument('--lengths-from', type=Path, default=None,
                   help='dataset directory whose training episodes give the choice-transition counts and the target '
                        f'size (default: uniform {CAL_LENGTHS[0]}-{CAL_LENGTHS[1]}, {CAL_EPISODES} episodes)')
    c.add_argument('--threads', type=int, default=os.cpu_count() or 1, help='workers considered: 1..threads')
    c.add_argument('--smt-share', type=float, default=0.5, help='share of a core per busy SMT sibling (0.5: no gain)')
    c.add_argument('--fast-core-ipc', type=float, default=1.0,
                   help='per-clock speed of a faster core type relative to the probe core (1.0: frequency only)')
    c.add_argument('--seed', type=int, default=CAL_SEED)
    c.add_argument('--no-validate', action='store_true', help='skip the in-sample ope.select check')
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == 'calibrate':
            return calibrate(args) or 0
        if args.cmd == 'status':
            res = status(args.out)
            _print(f'p3_rl status {Path(args.out).resolve()}: {len(res["done"])} done, {len(res["inconsistent"])} '
                   f'inconsistent, {len(res["missing"])} missing')
            return 1 if res['inconsistent'] else 3 if res['missing'] else 0
        ctx = make_ctx(args)
        ctx.log(f'p3_rl: mode {ctx.mode}, d* {ctx.d_star}, out {ctx.out}, n_jobs {ctx.n_jobs}, options {ctx.options}')
        done = drive(ctx, stage_list(), stop_after=args.stop_after, redo=args.redo)
        ctx.log(f'p3_rl: {len(done)} stage(s) final ({sum(1 for _, how, _ in done if how == "run")} run, '
                f'{sum(1 for _, how, _ in done if how == "skip")} skipped)')
        return 0
    except Stop as e:
        print(f'STOP (open case, the user decides): {e}', file=sys.stderr, flush=True)
        return 4
    except (StageError, ValueError, PermissionError, FileNotFoundError) as e:
        print(f'ERROR: {type(e).__name__}: {e}', file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
