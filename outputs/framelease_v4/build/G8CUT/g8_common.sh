# Common settings of the G8CUT scripts (RUNBOOK.md); sourced, never run. G8_ROOT (environment) replaces the project
# root for the scratch-tree dry run only (/tmp/G8CUT/root).
set -u
G8_ROOT="${G8_ROOT:-/home/kang/Desktop/DAC}"
cd "$G8_ROOT" || exit 99
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' MPLBACKEND=Agg
X="taskset -c 12-15 nice -n 19 ionice -c 3"
PY=/home/kang/Desktop/DAC/.conda-unidrive-linux/bin/python
P="$X $PY -I -B"
V4=outputs/framelease_v4
Q4=$V4/queue_p4
HERE=$V4/build/G8CUT
LIB=$HERE/g8_lib.py
LOGS=$HERE/logs
A2=$V4/build/AMEND2/a10r7b
RL_FREEZE=$V4/rl_freeze/rl_freeze.json
TUNING=$V4/tuning/selection.json
D1=$V4/tuning/d1/FULL_d1_summary.json
OFFLINE=$V4/offline_ablation
S1=$V4/stress/s1_registered_20261115T124141Z.json
S2=$V4/stress/s2_registered_20261115T123104Z.json
S2R=$V4/stress/s2_relative_registered_20261115T123118Z.json
S3=$V4/stress/s3_registered_20261115T122819Z.json
mkdir -p "$LOGS"

# run LABEL CMD...: CMD under taskset -c 12-15 nice -n 19 ionice -c 3 with wall time and max RSS; full output in
# $LOGS/LABEL.<time>.log, one line in $LOGS/steps.log; returns CMD's exit code.
run() {
    local label=$1; shift
    local ts; ts=$(date +%Y%m%dT%H%M%S)
    local log="$LOGS/$label.$ts.log"
    echo "+ $*" > "$log"
    $X /usr/bin/time -f 'TIME %e s, max RSS %M KB' "$@" >> "$log" 2>&1
    local rc=$?
    local tm; tm=$(grep '^TIME' "$log" | tail -1)
    echo "$(date '+%Y-%m-%d %H:%M:%S') $label exit $rc ($tm) $log" >> "$LOGS/steps.log"
    echo "[$label] exit $rc (${tm#TIME }); log $log"
    return $rc
}

# the one analysis-freeze directory (prints it; exit 1 when there is none or more than one)
final_dir() {
    local d=( $V4/analysis/final_* )
    if [ ! -e "${d[0]}" ]; then echo "no $V4/analysis/final_* directory" >&2; return 1; fi
    if [ "${#d[@]}" -ne 1 ]; then echo "${#d[@]} final_* directories: ${d[*]}" >&2; return 1; fi
    echo "${d[0]}"
}

# registration.py --verify: both seal lines OK and "manifest: OK" (exit 0), else exit 2 with the output
seal_ok() {
    local out; out=$($P framelease_v4/protocol/registration.py --verify 2>&1)
    echo "$out" | sed 's/^/  registration: /' | cut -c1-300
    [ "$(echo "$out" | grep -c ': OK$')" -eq 3 ] || { echo "registration.py --verify: not 'manifest: OK' and both seals OK"; return 2; }
}
