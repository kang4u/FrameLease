#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/env.sh"
cd "$FRAMELEASE_ROOT"
python - <<'PY'
import json, os, shutil
from pathlib import Path
import numpy as np
import torch
from framelease_common import file_hash, verified_manifest, atomic_json
checkpoint=Path(os.environ['CHECKPOINT'])
expected='b127eebb319aa52dbd35f2099bb1bda5c1c7732c2f811cae88454ce15e6c23fc'
assert file_hash(checkpoint)==expected, 'Checkpoint hash mismatch'
verified_manifest('outputs/stage02_unidrive_data/manifest.json')
source=Path('outputs/stage02_unidrive_data/runs/20261102T124159_112b4388/raw')
target=Path(os.environ['WORK_DIR'])/'data/kmeans'
with torch.serialization.safe_globals([set]):
    state=torch.load(checkpoint,map_location='cpu',weights_only=True,mmap=True)['module']
rows=[]
for filename,key in [('b2d_det_900.npy','planning_head.unified_decoder.det_instance_bank.anchor'),
                     ('b2d_map_100.npy','planning_head.unified_decoder.map_instance_bank.anchor'),
                     ('b2d_motion_6.npy','planning_head.unified_decoder.motion_anchor')]:
    original=source/filename
    array=np.load(original,allow_pickle=False)
    tensor=state[key].detach().float().numpy()
    assert np.array_equal(array,tensor) and np.isfinite(array).all(), key
    target.mkdir(parents=True,exist_ok=True)
    path=target/filename
    if path.exists():
        assert file_hash(path)==file_hash(original), 'Refusing to replace different anchor'
    else:shutil.copy2(original,path)
    rows.append({'path':str(path),'checkpoint_key':key,'shape':list(array.shape),'sha256':file_hash(path),'exact_checkpoint_value':True})
result={'status':'CHECKPOINT_ANCHORS_RESTORED','checkpoint_sha256':expected,'anchors':rows,
        'origin':'trained checkpoint tensors; not original kmeans files',
        'original_kmeans_equivalence':'NOT_VERIFIED','full_model_loaded':False,'research_gate_promoted':False}
atomic_json('audits/linux_setup_20261104/restored_anchors.json',result)
print(json.dumps(result,indent=2))
PY
