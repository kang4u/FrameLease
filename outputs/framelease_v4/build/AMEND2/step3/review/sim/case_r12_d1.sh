#!/bin/bash
# R12: write_d1_decision.py on the snapshot 'step3done': refusals, --dry-run, the write, a second write; R13 the phase
# driver's dry run with the decision (G1 plan and entry text).
source "$(dirname "$(readlink -f "$0")")/common.sh"
snap_load step3done
cp -a "$SNAP/step3done/PROTOCOL.md" "$T/framelease_v4/PROTOCOL.md"
echo "state $(state); seal lines OK $(seals)"
D="$SIM/d1"; rm -rf "$D"; mkdir -p "$D"
printf '%s\n' 'Every P1 block is final on the training routes (simulation text of the review).' > "$D/ok.txt"
printf '%s\n' 'Continue: written with Claude.' > "$D/claude.txt"
printf '' > "$D/empty.txt"
"${P[@]}" "$PY" -I -B -c "print('x' * 4001)" > "$D/long.txt"
WD=("${P[@]}" "$PY" -I -B "$S3/write_d1_decision.py" --root "$T")
for c in "claude|continue" "empty|continue" "long|continue" "ok|maybe"; do
    f="${c%%|*}"; dec="${c#*|}"
    "${WD[@]}" --decision "$dec" --rationale-file "$D/$f.txt" > "$L/R12_$f.log" 2>&1
    echo "R12 rationale '$f', decision '$dec': exit $?; $(head -2 "$L/R12_$f.log" | cut -c1-120 | tr '\n' '|')"
done
mv "$T/outputs/framelease_v4/p1_driver/P1_DONE.json" "$SIM/P1_DONE.keep"
"${WD[@]}" --decision continue --rationale-file "$D/ok.txt" > "$L/R12_nodone.log" 2>&1
echo "R12 P1_DONE.json missing: exit $?; $(head -1 "$L/R12_nodone.log" | cut -c1-140)"
mv "$SIM/P1_DONE.keep" "$T/outputs/framelease_v4/p1_driver/P1_DONE.json"
"${WD[@]}" --decision continue --rationale-file "$D/ok.txt" --dry-run > "$L/R12_dry.log" 2>&1
echo "R12 --dry-run: exit $?; phase_driver/ exists: $([ -e "$T/outputs/framelease_v4/phase_driver" ] && echo yes || echo no)"
cat "$L/R12_dry.log" | sed 's/^/   /'
"${WD[@]}" --decision continue --rationale-file "$D/ok.txt" > "$L/R12_write.log" 2>&1
echo "R12 write: exit $?; $(cat "$L/R12_write.log" | cut -c1-160); dir: $(ls -A "$T/outputs/framelease_v4/phase_driver" | tr '\n' ' ')"
"${WD[@]}" --decision stop --rationale-file "$D/ok.txt" > "$L/R12_again.log" 2>&1
echo "R12 second write: exit $?; $(head -1 "$L/R12_again.log" | cut -c1-120)"
"${P[@]}" "$PY" -I -B "$T/framelease_v4/protocol/phase_driver.py" --dry-run > "$L/R13_dry.log" 2>&1
echo "R13 phase_driver --dry-run: exit $?; $(grep -E '^  G[012] ' "$L/R13_dry.log" | cut -c1-100 | tr '\n' '|')"
grep -n -E 'D1 \(Sec. 4.8\)|by coordinating session|by the coordinating session' "$L/R13_dry.log" | cut -c1-400 | sed 's/^/   /'
echo "   phase_driver/ after the dry run: $(ls -A "$T/outputs/framelease_v4/phase_driver" | tr '\n' ' ')"
