#!/bin/bash
# Copy the evidence of the last simulation run (/tmp/AMEND3/logs, /tmp/AMEND3/runs, /tmp/AMEND3/rv/results.txt) into
# step3/sim_output/ (emptied first; a10_inplace5_suggestion.json is kept when the Sec. 4.1 status paragraph of the run
# equals the one it was derived from). Run once after sim/run_simulation.sh and sim/run_review_cases.sh.
set -u -o pipefail
HERE="$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")/.." && pwd)"
O="$HERE/sim_output"
SIM=/tmp/AMEND3
L="$SIM/logs"
R="$SIM/runs"
X="$R/08_transaction"
keep="$(mktemp -d /tmp/AMEND3/keep_sim_output.XXXXXX)"
cp -p "$O/a10_inplace5_suggestion.json" "$O/sec_4_1_status_paragraph.txt" "$keep/" 2>/dev/null
rm -rf "$O"
mkdir -p "$O"
cp -p "$L"/summary.txt "$L"/0[0-9]*.log "$L"/1[0-7]*.log "$O/"
cp -p "$X/journal.json" "$O/journal_08_transaction.json"
cp -p "$X/step3_txn.log" "$O/08_step3_txn.log"
for n in A3 A9 A7 A4 OP; do cp -p "$X/entry_$n.md" "$O/"; done
cp -p "$X/phase_driver_dry_run.txt" "$O/phase_driver_dry_run_after_step3.txt"
cp -p "$X/check_drafts_after.txt" "$O/check_drafts_after_step3.txt"
cp -p "$X/sec_4_1_status_paragraph.txt" "$O/"
cp -p "$L/10d_dry_run.log" "$O/d1_decision_dry_run.json"
cp -p "$L/10g_phase_driver_dry_run.log" "$O/phase_driver_dry_run_after_decision.txt"
cp -p "$SIM/stale/06c_copy/journal.json" "$O/journal_06c_kill_before_restore.json"
cp -p "$R/06c_kill/journal.json" "$O/journal_06c_kill_after_restore.json"
for n in 12a 12b 12c 12d; do
    cp -p "$R/$n/journal.json" "$O/journal_${n}.json"
    cp -p "$R/$n/step3_txn.log" "$O/${n}_step3_txn.log"
done
(cd "$SIM" && diff -u runs/08_transaction/PROTOCOL.sealed.md runs/08_transaction/PROTOCOL.new.md) > "$O/protocol_step3.diff"
/home/kang/Desktop/DAC/.conda-unidrive-linux/bin/python -I -B - "$SIM/tree/framelease_v4/PROTOCOL.md" \
    > "$O/fake_p1_entries.md" <<'PYEOF'
import sys
lines = open(sys.argv[1], encoding='utf-8').read().split('\n')
i = next(k for k, ln in enumerate(lines) if ln.startswith('* **Tuning freeze**, '))
j = i + 1
while j < len(lines) and lines[j].strip() and not lines[j].startswith('**'):
    j += 1
print('\n'.join(lines[i:j]))
PYEOF
if cmp -s "$keep/sec_4_1_status_paragraph.txt" "$O/sec_4_1_status_paragraph.txt"; then
    cp -p "$keep/a10_inplace5_suggestion.json" "$O/"
    echo "a10_inplace5_suggestion.json kept (the Sec. 4.1 status paragraph is unchanged)"
else
    echo "the Sec. 4.1 status paragraph differs from the one of a10_inplace5_suggestion.json: not kept"
fi
[ -f "$SIM/rv/results.txt" ] && cp -p "$SIM/rv/results.txt" "$O/review_cases_rerun.txt"
rm -rf "$keep"
echo "sim_output: $(ls "$O" | wc -l) files, $(du -sh "$O" | cut -f1)"
