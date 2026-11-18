# sourced by the reviewer's case scripts
set -u -o pipefail
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
REAL=/home/kang/Desktop/DAC
S3="$REAL/outputs/framelease_v4/build/AMEND2/step3"
RV="$S3/review"
SIM=/tmp/AMEND3_review
T="$SIM/tree"
L="$SIM/logs"
R="$SIM/runs"
SNAP="$SIM/snap"
P=(taskset -c 12-15 nice -n 19 ionice -c 3)
PY="$REAL/.conda-unidrive-linux/bin/python"
TXN=("${P[@]}" "$PY" -I -B "$S3/step3_txn.py")
mkdir -p "$L" "$R"
state() { (cd "$T" && sha256sum framelease_v4/PROTOCOL.md outputs/framelease_v4/registration/MANIFEST.sha256 \
    outputs/framelease_v4/registration/SEAL.sha256 outputs/framelease_v4/registration/REGISTRATION.json | cut -c1-16 | tr '\n' ' '); }
verify() { "${P[@]}" "$PY" -I -B "$T/framelease_v4/protocol/registration.py" --verify 2>&1 | tr '\n' ' ' | cut -c1-400; }
seals() { "${P[@]}" "$PY" -I -B "$T/framelease_v4/protocol/registration.py" --verify | grep -c '^seal .*: OK$'; }
snap_save() {   # name
    local d="$SNAP/$1"; rm -rf "$d"; mkdir -p "$d"
    cp -a "$T/framelease_v4/PROTOCOL.md" "$d/"
    cp -a "$T/outputs/framelease_v4/registration" "$d/registration"
    cp -a "$T/outputs/framelease_v4/p1_driver" "$d/p1_driver"
    cp -a "$T/outputs/framelease_v4/build/AMEND/AMENDMENTS_DRAFT.md" "$d/"
    cp -a "$T/framelease_v4/protocol/p1_driver.py" "$d/"
    cp -a "$T/framelease_v4/analysis/verify_table1_extra.py" "$d/"
    cp -a "$T/framelease_v4/analysis/commit_audit.py" "$d/"
    cp -a "$T/outputs/framelease_v4/amendment_a3" "$d/amendment_a3"
    rm -rf "$T/outputs/framelease_v4/phase_driver.snapcheck"
}
snap_load() {   # name
    local d="$SNAP/$1"
    cp -a "$d/PROTOCOL.md" "$T/framelease_v4/PROTOCOL.md"
    rm -rf "$T/outputs/framelease_v4/registration" "$T/outputs/framelease_v4/p1_driver" "$T/outputs/framelease_v4/amendment_a3"
    cp -a "$d/registration" "$T/outputs/framelease_v4/registration"
    cp -a "$d/p1_driver" "$T/outputs/framelease_v4/p1_driver"
    cp -a "$d/amendment_a3" "$T/outputs/framelease_v4/amendment_a3"
    cp -a "$d/AMENDMENTS_DRAFT.md" "$T/outputs/framelease_v4/build/AMEND/AMENDMENTS_DRAFT.md"
    cp -a "$d/p1_driver.py" "$T/framelease_v4/protocol/p1_driver.py"
    cp -a "$d/verify_table1_extra.py" "$T/framelease_v4/analysis/verify_table1_extra.py"
    cp -a "$d/commit_audit.py" "$T/framelease_v4/analysis/commit_audit.py"
    rm -rf "$T/outputs/framelease_v4/phase_driver"
}
