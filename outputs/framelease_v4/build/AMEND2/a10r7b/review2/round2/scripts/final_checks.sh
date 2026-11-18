#!/bin/bash
# Read-only checks on the project at the end of the re-check (run under run.sh; one command at a time).
cd /home/kang/Desktop/DAC || exit 1
P=".conda-unidrive-linux/bin/python -I -B"
A=outputs/framelease_v4/build/AMEND2
echo "== $(date '+%F %T %z')"
echo "== check mode A10 on the project (read only)"
/usr/bin/time -f "time %e s, max RSS %M kB" $P $A/a10r7b/apply_entry_stream.py $A/final/A10_spec.json 2>&1 | tail -3
echo "== check_drafts.py"
$P $A/check_drafts.py > /tmp/A10A11/recheck1/check_drafts.out 2>&1; echo "exit $?"; tail -3 /tmp/A10A11/recheck1/check_drafts.out
grep -c "found 1x now" /tmp/A10A11/recheck1/check_drafts.out
echo "== derive_inplace5.py --spec"
$P $A/a10r7b/derive_inplace5.py --spec $A/final/A10_spec.json > /tmp/A10A11/recheck1/derive5.out 2>&1; echo "exit $?"
tail -1 /tmp/A10A11/recheck1/derive5.out
echo "== evidence sha256sum -c"
sha256sum -c --quiet $A/a10r7b/evidence_sha256.txt; echo "exit $?"
echo "== RUNBOOK Sec. 1 precondition 1"
ls outputs/framelease_v4/phase_driver/{ALERT.txt,protocol_txn.json} outputs/framelease_v4/p1_driver/{ALERT.txt,protocol_txn.json} framelease_v4/.PROTOCOL.md.entrytmp 2>&1 | sed 's/^/  /'
$P -c "import json; b=json.load(open('outputs/framelease_v4/phase_driver/registered_baseline.json'))['files']; m=dict(reversed(l.rstrip('\n').split('  ',1)) for l in open('outputs/framelease_v4/registration/MANIFEST.sha256')); print([k for k,v in b.items() if m.get(k)!=v] or 'OK')"
echo "== RUNBOOK Sec. 1 precondition 3 (PROGRESS files changed after 2026-11-15 11:05)"
for f in $(find outputs/framelease_v4/build -name 'PROGRESS*.md' -newermt '2026-11-15 11:05' | sort); do
    echo "-- $f: $(grep -c -E 'aggregate_v4|commit_audit|analyze_v4|prop1_coverage|figures_tables|verify_independent' "$f") matching lines"
done
echo "== the reviewed files (sha256)"
sha256sum $A/a10r7b/apply_entry_stream.py $A/a10r7b/apply_entry_stream.diff $A/a10r7b/apply_locked.sh \
    $A/a10r7b/post_check.py $A/a10r7b/sim_tree.py $A/a10r7b/RUNBOOK.md $A/final/A10_entry.md $A/final/A10_spec.json \
    $A/AMENDMENTS2_DRAFT.md | cut -c1-16,65-
echo "== registration and driver state"
sha256sum framelease_v4/PROTOCOL.md outputs/framelease_v4/registration/{MANIFEST.sha256,SEAL.sha256,REGISTRATION.json} \
    framelease_v4/PIPELINE_STATE.md outputs/framelease_v4/{p1_driver,phase_driver}/registered_baseline.json | cut -c1-16,65-
stat -c '%y %n' framelease_v4/PROTOCOL.md outputs/framelease_v4/registration/SEAL.sha256 \
    outputs/framelease_v4/phase_driver/registered_baseline.json outputs/framelease_v4/phase_driver/driver.log
pid=$(cat outputs/framelease_v4/phase_driver/driver.pid); ps -o pid=,etime=,args= -p "$pid"
ls outputs/framelease_v4/phase_driver/ outputs/framelease_v4/p1_driver/ | grep -E 'ALERT|protocol_txn|^STOP$|^PAUSE' || echo "no ALERT, protocol_txn, STOP or PAUSE file"
echo "== __pycache__ and empty files under framelease_v4/"
find framelease_v4 -name __pycache__ -type d | wc -l; find framelease_v4 -path '*__pycache__*' -type f | wc -l
find framelease_v4 -type f -empty | sort
find framelease_v4 -newermt '2026-11-15 11:03' -print | head
echo "== registration.py --verify"
$P framelease_v4/protocol/registration.py --verify; echo "exit $?"
