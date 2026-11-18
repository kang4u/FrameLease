# Review 2, round 2: re-check of the fixed applier, wrapper and post-check of item a10r7b before Amendment A10

Independent adversarial re-check, 2026-11-15 11:03-11:53 (Beijing time), of fix pass 2 (10:16-11:05) against
`review2/REVIEW.md` (GO_WITH_FIXES: must-fix M1 and M2, should-fix S1-S8). Nothing was applied: the protocol lock,
PROTOCOL.md, the registration files, the seal, PIPELINE_STATE.md, every registered file, both drivers, their queues,
CARLA and the GPU were not touched, and no file under `framelease_v4/` changed. Every process ran under
`taskset -c 12-15 nice -n 19 ionice -c 3` with one BLAS thread and `CUDA_VISIBLE_DEVICES=''`, one working process at a
time; the simulations ran on scratch trees under `/tmp/A10A11/` only (removed after each run). Largest resident set:
33 MB in every simulation, 230 MB in the test suites. No test-route data and no P2 outcome was read.

Reviewed files (sha256 at the start and at the end of the re-check, equal to RUNBOOK Sec. 6; unchanged by it):

| file (under `outputs/framelease_v4/build/AMEND2/`) | sha256 |
|---|---|
| `a10r7b/apply_entry_stream.py` | `7d86e576f2c8413f642c2c6ab7bba94212dcf573558d3be8e6d03eb19deb3884` |
| `a10r7b/apply_entry_stream.diff` | `8e87f0c20d05cc5e90bff569b09e7433171b26e0bdb1c6d44fe586d245707184` |
| `a10r7b/apply_locked.sh` | `1de9b701aabfc7ec607c840123a315df152393315b4ed9bd386961ebc4212310` |
| `a10r7b/post_check.py` | `7b08460b0fd96ec2cdfd9994677d59f6a378ec42dba23401db116ccfd61149ac` |
| `a10r7b/sim_tree.py` | `59b7a83ce99b98f51b3dc8f17870cafec5920a0683af884caacce5cc00554c92` |
| `a10r7b/RUNBOOK.md` | `125a28838c7bea6cc04538f1bae58cb95273390fb5274ce30c8f0cb927a528a6` |
| `final/A10_entry.md` | `9790c164405f432a813df39986b84853bd18ac078b5d4afff0ea51915ea324ca` |
| `final/A10_spec.json` | `b1de9f6a976da98dc0da9da48fff5a1e2ec55512dfaac581ad7eb73a64335b0e` |
| `AMENDMENTS2_DRAFT.md` | `03bfb7f44e89cbc4d88ac12ca96f7366c05188cfae22de58fccc8b9357861eac` |

`apply_entry_stream.diff` equals `diff -u paper_tools/apply_entry.py a10r7b/apply_entry_stream.py` (headers aside).
`A10_entry.md`, `A10_spec.json` and `AMENDMENTS2_DRAFT.md` are the files review 2 read.

## Verdict: GO

Both must-fix items of review 2 are fixed and hold under every fault tried. M1: in 14 wrapper runs on scratch trees,
a stand-in driver that wanted the protocol lock throughout obtained it 499 times and found a matching seal every time;
the wrapper completes or rolls back the transaction before it releases the lock after a SIGKILL of the applier at any
point, an orphaned `registration.py`, a failing seal, a foreign edit and signals to its process group. M2: a changed
P1 job file stops the applier before `--write-manifest`. S1-S8 are fixed, and the fixes broke nothing: `sim_tree.py`
(43 steps), review 2's own harness (74 expectations) and 34 further cases pass (a 35th is S1 below), A10 and then A11
apply end to end, the test suites give the counts the entries cite, and the A10 entry is right against APPLY_PLAN2
Sec. 4. A10 can be applied now with RUNBOOK Sec. 1 while the phase driver runs. Two should-fix items remain; neither
affects A10 or A11.

## Must fix

None.

## Should fix (neither affects A10 or A11)

* S1. The width check of the in-place texts measures the "new" fragment, not the line it produces.
  `apply_entry_stream.py` lines 246-249 test the lines of `r['new']` that are not lines of `r['old']`; when "old" starts
  or ends inside a line, the rest of that line lies outside the measure, although the docstring (lines 27-28) and
  RUNBOOK Sec. 0 "Widths" state that the changed lines are at most 120 columns. Case WD7: an in-place text whose "old"
  is the last 30 characters of a 118-column prose line outside Sec. 13.2 (with its line break) and whose "new" appends
  26 characters produces a line of 144 columns; the measured fragment has 56; check mode reads "check: pre-checks
  passed". A10 and A11 are not affected: on the simulated PROTOCOL.md after both, no added prose line exceeds 120
  columns (413 added lines, maximum 120), and `check_drafts.py` (lines 182-188) and `check_a11.py` (lines 185-196)
  measure the produced line from the start of the line before the replacement to the end of the line after it. Fix,
  for a later entry of the same form (RUNBOOK Sec. 5 item 3): after the in-place loop, measure the lines of `probe`
  that are not lines of `text` (`[ln for ln in probe.split('\n') if ln not in set(text.split('\n')) and len(ln) >
  WIDTH and not is_table_row(ln)]`).
* S2. RUNBOOK Sec. 1 treats every `apply_locked: exit` line as final. When SIGKILL ends the inner shell of the wrapper
  (the `bash -c` under `flock`), `flock` returns and the outer shell prints `apply_locked: exit 137` at once, while the
  applier, which inherited the lock descriptor, still runs and holds the lock, and the recovery of the wrapper does not
  run (a SIGKILL of `flock` alone likewise prints the line while the inner shell goes on). Case KI (times from the start
  of a stand-in driver, 0.5 s before the wrapper's): the inner shell killed at 10.1 s; the applier sealed A10 and exited
  at 13.5 s; the stand-in, blocked on the lock from 0.5 s on, obtained it at 13.4 s, as the applier exited, and found
  the seal matching; `apply.out` holds no `apply_locked:` line after the copies line. The exit-137 bullet of RUNBOOK
  Sec. 1 describes the state after the recovery of the wrapper ("PROTOCOL.md unchanged; ..."), and the bullet "No line
  `apply_locked: exit`" does not apply. Add: before reading `apply.out`, wait for the lock (`flock -w 600
  framelease_v4/.protocol.lock true` returns once every process that inherited it has ended; at once in the normal
  case); when `apply.out` then holds no `apply_locked:` line below the applier's output, proceed as for "No line
  `apply_locked: exit`". Only a SIGKILL of a process of the wrapper produces this state (it ignores SIGINT, SIGTERM and
  SIGHUP and runs detached).

## Verified

### M1 of review 2: the lock is released with a matching seal

* Code (`apply_locked.sh`): `trap '' INT TERM HUP` before `flock` (line 42; Python keeps an inherited ignored SIGINT,
  and `subprocess` restores only the signals Python itself ignores, so the applier and `registration.py` ignore all
  three); under the lock, exit 96 unless `sha256sum -c --status` of SEAL.sha256 passes (lines 84-88), then a new
  `attempt_<time>_<pid>/` with PROTOCOL.md, the manifest, SEAL.sha256, REGISTRATION.json and both baselines (lines
  89-97); after the applier, a wait while a python process of the wrapper's process group runs this root's
  `registration.py` (lines 100-108); after a failure: PROTOCOL.md equal to its copy, the sealed manifest put back by
  temporary file and rename; PROTOCOL.md equal to the text whose sha256 the applier printed before the write, exit 94
  (the seal matches, or `--seal` succeeds; `registration.seal` refuses a manifest that PROTOCOL.md does not cite), else
  roll-back of the four files (93); any other PROTOCOL.md kept as `PROTOCOL.unexpected.md` and rolled back (93) or,
  when sealed, left (92); a final check sets 92 whenever the seal does not match (line 154). REGISTRATION.json is read
  by neither driver.
* Lock-wanting stand-in driver (`round2/scripts/holder2.py`: blocking `flock(LOCK_EX)` on the tree's lock as
  `p1_driver.ProtocolLock` takes it, then under the lock the condition of the ALERT in `phase_driver.ensure_recorded`,
  SEAL.sha256 against PROTOCOL.md and MANIFEST.sha256) running through 14 wrapper runs: 499 acquisitions, 0 with a
  mismatching seal; the longest wait 16.8 s, one interval per run.
* Faults (own cases): SIGKILL right after `--seal` (KS): exit 94 "the seal matches"; SIGKILL while a late `--seal` child
  starts (OS): waited 3 s, exit 94, sealed, `gate_g1` done; the RUNBOOK form `setsid nohup ... &` with SIGKILL while a
  late `--write-manifest` child starts and a new file in scope (OM): waited 7 s for the 222-file manifest, "RESTORED the
  sealed manifest", exit 137, the state of before; SIGINT, SIGTERM and SIGHUP to the session's process group of four
  processes after `--write-manifest` (SG): ignored, exit 0, sealed; the wrapper leads its own process group (`setsid`).
  `sim_tree.py`: F1 (94 with the manifest the entry names), H1 (seal impossible: 93, state and REGISTRATION.json of
  before), H2 (foreign edit: 93, `PROTOCOL.unexpected.md`), H3a/H3b (92, "ROLL BACK INCOMPLETE" with the seal matching,
  "ROLL BACK FAILED" unsealed), H4 (94, then STOP; two attempt directories). Review 2's harness: K1/K2 (137, restored,
  `gate_g1` done), K3 (94, `gate_g1` done), K4R (a driver cycle during the recovery: done), O1 (orphan: waited,
  restored, `gate_g1` done), S1 (SIGINT to the group: exit 0), R2 (94 then STOP, each attempt with its own copies),
  X3-X8.
* RUNBOOK: the detached command, exit codes 92-98, the attention line of the phase driver during the transaction
  (`tool_pids` matches the wrapper's `flock` and `bash -c`, whose command lines name `python` and
  `framelease_v4/protocol/registration.py`), the hand recovery only for a wrapper killed by SIGKILL; S2 above adds the
  case of its inner shell.

### M2 of review 2: the P1 job files

`registered |= {k for k in sealed if k.startswith(P1_JOBS)}` (line 224) is the prefix of `p1_driver.is_strict`, which
both drivers use (`phase_driver.strict_map` passes the baseline, `cfg.jobs_dir` is `outputs/framelease_v4/p1_jobs`);
RUNBOOK Sec. 0 names the twelve b04-b09 files. Review 2's harness: P2 (a changed `b04_lease_s2.check.json`: check exit
1, wrapper exit 1 "the manifest equals the sealed one", nothing written, the driver's pre-check still names the file),
X2.

### S1-S8 of review 2 and the additions of fix pass 2

* Review 1 and the three hardenings review 2 was the first to see (registered files from the PROTOCOL.md citations, STOP
  on a registered file absent from the sealed manifest, the line check of the filled entry) hold unchanged: review 2's
  B1-B7, C1, D1-D5, T4.1-T4.9 and `sim_tree.py` B-E and G pass again.
* S1 lock: `--apply` run directly while another process holds the lock stops, also with an own unlocked descriptor of
  the lock file (LK1); under `flock` it seals (LK2); review 2's L3, X9.
* S2 composed count: the newly registered files are those of the composed text and equal the template's
  `{{sha256:...}}` files: 8 for A10, 2 for A11 (E, A, X1); an empty file in scope stops with "would register", the
  manifest restored (T5, X13); `post_check.py` against the attempt copy of the phase baseline: exit 3, the driver's
  refresh adds exactly 8 (A10) and 2 (A11) files, then exit 0 (E, H4); the applier of before fix pass 2 lets
  `post_check.py` fail on the empty file (H5).
* S3 Sec. 13.2 heading and parsers: a template line `### 13.2 Amendments` stops (TL5, T4.10, X12); both drivers'
  parsers read the composed text before the write (code lines 323-325; A, X1).
* S4 stamp order: a clock at 06:30 stops check mode and the wrapper before `--write-manifest` with "(2026-11-15
  06:43)" (CK1, CK2, T2, X10); a clock set back between the pre-check and the fill stops after `--write-manifest`,
  PROTOCOL.md unchanged, the state of before (CK3); a clock equal to the last stamp seals with that stamp (CK4); a later
  phase-driver entry stamped 2026-11-16 00:30 stops the real clock (CK5).
* S5 widths and preview: a prose line of 120 columns passes, 121 stops, a table row of 150 passes (WD1-WD3); a template
  line of 104 columns that the fill makes 121 stops in check mode and in the wrapper before `--write-manifest` (WD4,
  WD4w, T3, T4.7-T4.9, X11); in-place "new" lines of 121 columns stop, 120 pass (WD5, WD6); S1 above for lines that
  start or end inside a line.
* S6 cited files after `--write-manifest`: a cited file changed then stops before PROTOCOL.md is written (Y1, X14).
* S7 seal check and attempt directories: exit 96 on an unsealed PROTOCOL.md, no copies (X8); one directory per
  attempt (R2, H4).
* S8: in-place texts counted in the order applied (IP2: the first "new" repeats the second "old": "found 2 times");
  an "old" twice stops check mode and the wrapper before `--write-manifest` (IP1, T1); fsync before the rename (code
  lines 331-336); `apply.out` prints `manifest difference: new [] / left [] / changed []` right after
  `--write-manifest`; `post_check.py` fails on an ALERT or transaction file of either driver (lines 132-135).
* Additions: one clock reading per fill (`clock()`, lines 137-144, 265, 307); a missing or doubled `### 13.2 Amendments`
  heading makes `last_stamp` return None and `clock` stop with a STOP line (code); the in-place width check (S1 above).

### Break cases of the task (scratch trees)

* A registered file changed between the pre-check and `--write-manifest`: STOP "registered files changed or left the
  new manifest", the sealed manifest restored, PROTOCOL.md unchanged (RF1, B5, B6); changed between `--write-manifest`
  and `--seal`: sealed, exit 95, the verification names it, the seal matches (RF2, F2, B7).
* The phase driver taking the lock mid-way: the stand-in driver above never obtained the lock inside a run; review 2's
  prober: one busy interval (0.0, 16.2) s of a 16.2-s run (A3c); a holder before the wrapper delays it, then it seals
  (L1, 35 s); a busy lock for longer than the wait gives exit 97 and changes nothing (L2).
* The applier killed after `--write-manifest`: exit 137, the sealed manifest restored (K1 and X5 by SIGKILL, D2); inside
  the rename: restored (K2, X6); after the PROTOCOL.md write: 94, sealed (K3 and X3 by SIGKILL, F1, H4); after `--seal`:
  94 (KS).
* An "old" found twice: STOP before `--write-manifest` (IP1, T1).
* A time stamp earlier than the last Sec. 13.2 entry (G2, 06:43): STOP (CK1-CK3, CK5, T2, X10).
* A filled line over 120 columns: STOP in check mode (WD4, WD4w, T3, X11).
* Template lines in the form of `p1_driver.ENTRY_RE` (`* **D1 summary**, 2026-11-15 12:00 (...`),
  `phase_driver.ENTRY_RE` (`* **G4 RL freeze** (2026-11-15 12:00, ...`), `phase_driver.AMEND_RE` (with ":" and with
  ","), `### 13.2 Amendments` and the P1 driver heading: each stops check mode (TL1-TL6; T4.1-T4.6, G8-G11).
* Memory: check mode 18.8 MB; the wrapper with every descendant 33 MB (E1, `/usr/bin/time`); `post_check.py` 30 MB.

### A10 against APPLY_PLAN2 Sec. 4 and gate G8

* Finding 1 states the rule of `commit_audit.py` 7439a4ea (the file's sha256 now, cited by A3): "a null commit margin
  passes where the validity record names no relevant agent, or has reason `horizon_cap` and n_computed 0 (...); any
  other null margin with a relevant agent is a violation", word for word E3 (APPLY_PLAN2 lines 78-82) and the sealed A3
  text (PROTOCOL.md lines 2370-2372); `null_margin_explained` returns True for `no_relevant_agents` (n_relevant 0, else
  reason `no_relevant_agents`) or for reason `horizon_cap` with n_computed 0, False otherwise.
* Finding 2: `km_driven` of the P1-0 smoke run of `fl_heuristic` on route 18305 (arm `fl_heuristic_fp` in `runs.csv`) is
  0.0 in `build/R7/dev/agg_p1/runs.csv` and 0.001 in `build/R7B/dev/agg_now/` and `agg_snap_2203/` (`aggregate_v4.py`
  ee13c90b, cited by A3).
* Deviation 1: RUNBOOK Sec. 1 precondition 3 (`find ... -newermt '2026-11-15 11:05'`) lists only `review2/PROGRESS.md`;
  its lines after 11:03 record scratch-tree runs, the drivers' parsers and the test suites (logs under `/tmp`), no
  execution of the aggregator or of the four A10 files on real data. No other file under `outputs/framelease_v4/build/`
  changed after 11:03.
* The fifth in-place text: `derive_inplace5.py --spec final/A10_spec.json` exit 0, "in-place text 5 equals the derived
  text", on the current sealed PROTOCOL.md (`ca54d359...`); `check_drafts.py` exit 0, "all checks passed", every
  in-place text found once; `sha256sum -c evidence_sha256.txt` exit 0; check mode on the project: "check: pre-checks
  passed" (6.4 s).
* G8: on the simulated text after A10 (and after A11) `phase_driver.citing_amendment` gives A10 for the first Sec. 13.2
  line citing `analyze_v4.py`, and `phase_driver.analysis_registration` has no wait reason (E3, sim_tree A4/A8, review
  2's A4/A9, `post_check.py`); a later G3 entry that `phase_driver.insert_entry` places in the driver's block leaves it
  with A10. The simulated PROTOCOL.md after A10 and A11: two amendment titles, no other driver-form line, no non-ASCII
  character, 13 table rows over 120 columns.

### Simulations, tests and the project's state

* `sim_tree.py` (unchanged; 11:13:53-11:20:59, 412 s, 33 MB): ALL EXPECTED, 43 steps. Review 2's harness through
  `rerun_review2_sim.py` with its logs moved to scratch (11:29:07-11:43:40, 873 s, 33 MB): ALL EXPECTED, 74
  expectations; the 14 steps that reproduced a defect now read UNEXPECTED and pass the positive log checks. Own cases
  (`round2/scripts/recheck_sim.py`, 11:21:52-11:27:55, 363 s, 33 MB): 34 pass, WD7 is S1 above.
* Test suites with the specs' pytest commands, logs under `/tmp` (the project's logs untouched): A10 48 passed and 107
  subtests, 22 passed, 50 passed (422 warnings), 28 passed and 20 subtests; A11 71 passed and 67 subtests, 14 passed
  and 2 subtests; every exit 0; equal to the logs of 10:54-10:55 that the entries cite (85 s, 230 MB).
* Registration at the start (11:03) and at the end (11:51): "manifest: OK" and both seal lines OK. PROTOCOL.md
  `ca54d359...`, MANIFEST `4bfe7451...`, SEAL `b8d516d1...`, REGISTRATION `c0ee0217...`, PIPELINE_STATE.md
  `73add832...`, P1 baseline `df4435e1...` and phase baseline `cfe58aa1...` equal at start and end (PROTOCOL.md and
  SEAL.sha256 last written 06:43:14): no driver re-seal. The phase driver ran throughout (pid 256142); no ALERT,
  transaction, STOP or PAUSE file of either driver; no `.PROTOCOL.md.entrytmp`; under `framelease_v4/` 3 `__pycache__`
  directories with 8 files and the empty files `.protocol.lock` and `offline/__init__.py`, as before.

## Observations

* Exit 92 with "ROLL BACK INCOMPLETE" can leave a fully consistent state of before (H3a: PROTOCOL.md back, the
  manifest unchanged by A10, the seal matching). The RUNBOOK's instruction (compare the four files with the attempt
  copies) covers it.
* The wrapper waits at most 3600 s for a `registration.py` of its process group; a `--write-manifest` takes about 4 s
  here (OM: 7 s with a 3-s delay).
* A RUNBOOK launch followed by `grep` in the same shell does not read a `console.txt` of an earlier attempt: the
  launched shell truncates it first (0 of 40 trials).
* `paper_tools/apply_entry.py` keeps the defects of RUNBOOK Sec. 5 item 3 and is not used.

## Files of this re-check

`review2/REVIEW_round2.md`; `review2/PROGRESS.md` (lines from 11:03 on); `review2/round2/scripts/` (`recheck_sim.py`,
`inject2.py`, `holder2.py`, `rerun2.py`, `run_tests.py`, `final_checks.sh`, `race_console.sh`, `plog.py`, `run.sh`);
`review2/round2/logs/` (`own/`: every case log, the stand-in driver's records `*_holder.json`, `results.txt`;
`review2_harness/`: `expectations.txt`, `results.txt`, the run output; `sim_tree/`: the run output and
`summary.txt`; the final checks, the outputs of `check_drafts.py` and `derive_inplace5.py`, the test logs as
`recheck_tests_pytest_*.log`). `review2/REVIEW.md` and the item's files are unchanged.
