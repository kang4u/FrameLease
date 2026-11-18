**Operational addition, 2026-11-15 06:40 (Beijing time): the phase driver of Phases 2-7 (FULL; no change of any run, job
file, selection rule or criterion).**
* What it is. `framelease_v4/protocol/phase_driver.py` (sha256
  `2bf4147c610751c8380f55c59d10f889ce7062849c56351ebbaa8fac1ac7c994`) carries out the phase gates G0-G8 after P1 for
  FULL as registered (Secs. 4.8, 4.9, 5.3-5.9, 7.6, 8.1-8.6, 9.11, 9.12, 10.1;
  `outputs/framelease_v4/p1_driver/GAP_AUDIT.md` Sec. 3.6, item E-2). It imports the helpers of the registered
  `framelease_v4/protocol/p1_driver.py` and never edits it; it starts CARLA and the GPU only through
  `framelease_v4/protocol/launch_queue.sh`. Every cycle (default 300 s) walks the gates in order and stops at the first
  gate that is not passed. Its state lives in `outputs/framelease_v4/phase_driver/` and is rebuilt from the files at
  every cycle: no entry is written twice, no job file is generated, copied or recorded twice, and no report or freeze
  record is rewritten.

  | gate | what the driver does | PROTOCOL |
  |---|---|---|
  | G0 | waits, never with an ALERT, until `outputs/framelease_v4/p1_driver/P1_DONE.json` exists, the P1 stage driver has exited with no open record transaction, Sec. 13.2 holds the P1 driver's "Tuning freeze" and "D1 summary" entries and Amendments A3, A4, A7 and A9, and `registration.py --verify` passes | 4.9, 8.1, 13.2 |
  | G1 | D1: waits for `phase_driver/D1_DECISION.json` (`continue` or `stop`, a rationale, the sha256 of `outputs/framelease_v4/tuning/d1/FULL_d1_summary.json`); the sha256 must be the file's and the one the P1 driver's "D1 summary" entry cites (else ALERT); records the decision; `stop` writes `phase_driver/P2_STOPPED.json` and ends the driver, which never starts P2 later | 4.8 |
  | G2 | P2 job file: `p2_jobs.py --check --write` once (no `--variant` option exists: the tool writes FULL only); the check must be clean and the stage spec must cite the recorded tuning freeze; the job file, stage spec and check are recorded BEFORE the job file is copied atomically into `outputs/framelease_v4/queue_p2/jobs.d`; then the runner is launched | 5.3, 8.1, 8.2 |
  | G3 | once every P2 job is final and no runner holds the queue: `p2_check.py` without, then with `--write`; FAIL: ALERT; missing episodes: ALERT until `phase_driver/P2_MISSING_ACK.txt` names every one of them; the data manifest and the completion report are recorded | 5.3, 5.9, 8.1 |
  | G4 | P3, once no runner, closed-loop process or P1 driver is alive and the P3 code is registered: `p3_rl.py run --stop-after dataset`; `calibrate --sizes 33,66,132` (once, never overwritten); `run --n-jobs` with the recommended count (reduced only when the workers would exceed 75% of the available memory); `status`; `rl_freeze/rl_freeze.json` validated and recorded; an open case (exit 4): ALERT naming it, resolved only by `phase_driver/P3_OPEN_CASES.json` | 4.7, 5.4-5.9, 8.1 |
  | G5 | stress tests, once `stress_bench.py` is registered, each run once and never overwritten: S3; S2 on the registered grid; S2 on the grid relative to the slack floor (only under Amendment A7, variant A7b); S1 last, behind the exclusive-CPU guard (a process of this project: wait; foreign CPU load: retry after 600 s, ALERT after 3 retries, unless `phase_driver/S1_ACCEPT_FOREIGN_CPU.txt` gives the reason to accept it); every report checked as `test_freeze.py` checks it (S2 and S3: 0 violations) and recorded in one entry | 7.6, 9.5 |
  | G6 | test freeze, once `test_jobs.py`, `test_freeze.py`, `check_smoke_ext.py` and `framelease_v4/arms_ext/` are registered: `test_jobs.py --check --write` once; `registration.py --verify`; `test_freeze.py --write` and `--entry`; the record, with the entry text the tool prints; `test_freeze.py --verify`; the job files copied into `outputs/framelease_v4/queue_p4/jobs.d` in tier order; `--verify` again; `phase_driver/P4_QUEUED.json`; the runner | 3.3, 5.9, 8.1, 8.3, 10.1 |
  | G7 | P4-P6: job health only (per job file: jobs and final jobs; no outcome, metric or route of a test-route run is read or summarized); a job file the test freeze does not name: attention; passed when every job is final and the runner has exited | 8.4, 9.11 |
  | G8 | analysis freeze: waits (attention, no ALERT) until Sec. 13.2 cites the sha256 of `framelease_v4/analysis/analyze_v4.py` and PROTOCOL.md cites the sha256 of every aggregator module the record freezes; `queue_p4/jobs.d` must hold exactly the job files of the test freeze; `registration.py --verify`; then `aggregate_v4.py --write-freeze-record` over `queue_p4` once, into one `outputs/framelease_v4/analysis/final_<stamp>/` (never `--arm-summary`, never `--analysis-freeze`); the record must cover every registered job with a final outcome and the registered analysis code, and `SHA256SUMS` must hold; the record is entered, which makes it valid; `phase_driver/PHASES_DONE.json`; the driver stops | 9.11, 9.12 |

* Records. Each gate entry is written with the transaction of the P1 stage driver: an exclusive flock on
  `framelease_v4/.protocol.lock`; PROTOCOL.md and `MANIFEST.sha256` must be the sealed ones and every registered file
  must equal the sealed manifest; `registration.py --write-manifest --force`; every registered file must have entered
  the new manifest with its sealed sha256 and none may have vanished from it; the entry; `registration.py --seal`;
  `registration.py --verify`. An interrupted transaction is finished from `phase_driver/protocol_txn.json`. The entries
  stand under the heading "**Phase gates (P2-P7, FULL).**", created once directly before the closing paragraph of
  this section (the rule for dated entries); each is a bullet that starts with the gate and its label in bold and the
  date in parentheses, a form the P1 stage driver never reads as one of its entries. While another editor holds the
  lock, the driver waits up to 300 s and retries at its next cycle.
* Registered files. The driver keeps its baseline in `phase_driver/registered_baseline.json`, seeded read-only from
  the P1 stage driver's. A seal is the pair of the sealed PROTOCOL.md and the sealed manifest; at every new seal the
  baseline keeps each of its files at the newly sealed sha256 and adds a manifest file only when PROTOCOL.md cites
  that file's sha256 (an amendment that registers it). A changed or vanished registered file stops the driver with an
  ALERT; a change of an unregistered `framelease_v4` file (code in development) between seals is named in the next
  entry. Before G2-G6 run a tool, every file of its code must be registered (in the baseline, or cited by the sealed
  PROTOCOL.md); otherwise the gate waits. G8 applies the same rule to the analysis code.
* Tools. The long tools (G4, G5, G6, G8) write their output to `phase_driver/logs/`. A STOP file or a signal ends a P3
  or stress tool or the aggregation (its process group): `p3_rl.py` resumes its stages, a stress run is redone from
  scratch, an aggregation without a record is redone with `--force` in the same directory. A tool runs in its own
  session and can outlive a killed driver: before the driver starts any tool, `registration.py` included, or reads
  what it writes, it waits while a process runs that tool.
* Runners. One queue at a time (`queue_p2` at G2-G3, `queue_p4` at G6-G7), launched only as
  `systemd-run --user --scope --unit=framelease-<queue>-runner-<ts> -p OOMPolicy=continue bash
  framelease_v4/protocol/launch_queue.sh <queue>` at the driver's priority, nice 0 on every core: after the copy of a
  job file, after a 'queue empty' exit with pending jobs (not after two such exits in a row without a started job),
  and into a queue that never had a runner. Never while `<queue>/STOP` exists, while a runner of another queue of this
  project is alive, or with less free disk than the queue needs (P2: 7.3 GiB; `queue_p4`: 11.9 GiB at its first
  launch, Sec. 10.1). A circuit-breaker exit or a runner error: ALERT; a signal exit: no relaunch. A cut (Sec. 10.2)
  is not driven: the driver waits at G7 while a job is pending.
* Priority. Every tool runs at nice 10 (I/O class best-effort, level 7) while no closed-loop job runs, and on the
  E-cores 12-15 at nice 19 with one BLAS thread while one runs (its CPU time is charged to the simulated timeline,
  Secs. 2.3, 11.2; Amendment A8). The P3 and stress tools run only while no closed-loop job runs, on every core at
  nice 10. The runners keep nice 0.
* Launch in an isolated scope. `framelease_v4/protocol/start_phase_driver.sh` (sha256
  `5c70674fbf043bd4eb5fec9236b0a5fca2123bc5087bf12ddf75bac3c171a0ca`) starts the driver detached in a dedicated
  systemd user scope `framelease-phase-driver-<ts>` with `OOMPolicy=continue`, as Amendment A8 ("Isolation") moved
  the runner and the P1 stage driver: a kernel OOM kill then ends only the killed process
  (`outputs/framelease_v4/validity_notes/oom_20261112.md`). One instance runs (an exclusive flock on
  `phase_driver/driver.lock`). The script and the driver refuse a niced or CPU-pinned start, since the runners inherit
  priority and affinity, and refuse while `phase_driver/ALERT.txt` or `phase_driver/STOP` exists; after
  `P2_STOPPED.json` or `PHASES_DONE.json` nothing is started. The start passes neither of the two test options:
  `--allow-nice-launch` (lifts the refusal of a niced or pinned start) and `--normal-priority` (tools without nice,
  ionice and taskset) are used in the test sandboxes only. The driver stops at `phase_driver/STOP` or SIGTERM. An
  ALERT stops it until the cause is fixed and `ALERT.txt` is moved aside.
* Delegation of the phase gates and D1. The user instructed on 2026-11-14 at 04:00 (Beijing time; translated): "from
  now on, review yourself whether to proceed to the next phase". The coordinating session reads this instruction as
  covering every phase gate after P1, D1 included (Sec. 4.8: "Continuing or stopping is the user's decision"). The D1
  decision stays a recorded decision of the coordinating session; the driver never takes it. The coordinating
  session reads the D1 summary, decides and writes `phase_driver/D1_DECISION.json` (a temporary file in the same
  directory, then `mv`); G1 checks that the decision refers to the D1 summary the P1 stage driver entered and records
  it with the decision file's sha256, its rationale, the instruction quoted in translation and this reading. The
  other decision files (`P2_MISSING_ACK.txt`, `P3_OPEN_CASES.json`, `S1_ACCEPT_FOREIGN_CPU.txt`) are decisions of the
  coordinating session in the same way, each cited by the entry that uses it; the driver never chooses the
  alternative of an open case itself. The P1 stage driver and its operational addition of 2026-11-11 are unchanged:
  it stops after the D1 summary.
* Interim looks (Sec. 9.11). Before G8 the driver reads no outcome, metric or route of a test-route run and runs no
  aggregation; G7 stores per-file job counts only. At G8 every test-route row stays health-only until the record is
  entered.
* Departures (none changes a run, a pin or a criterion).
  1. `p2_jobs.py` has no `--variant` option; the driver runs it without one (FULL is the only variant it writes).
  2. G0 waits for Amendment A4, which the apply plan of Amendments A3-A9
     (`outputs/framelease_v4/build/AMEND/APPLY_PLAN.md`, row 9) allowed "during P2 or P3": A4 is entered before the
     driver passes G0.
  3. Review items M1 (a registration-only seal taken for the driver's own seal) and M3 (a registered file removed
     between the pre-check and `--write-manifest`) describe logic that the registered `p1_driver.py` shares;
     `p1_driver.py` is unchanged. At this entry every file of `outputs/framelease_v4/p1_driver/registered_baseline.json`
     is in the manifest sealed with it, at its registered sha256.
* Review. Independent review `outputs/framelease_v4/build/PHASE/review/REVIEW.md`
  (`d7ef679052cb6af5d3385ae231b0f086e8c522ac0d193b17900dc6bbe655bd0c`), verdict GO_WITH_FIXES; the must-fix items M1-M4
  and the should-fix items S1-S8 are applied (S7 through M2). After the fixes, chaos runs that kill the driver with
  SIGKILL at random times and after the n-th tool call (seeds 10-21, orphaned tools finishing first: 12 of 12; seeds
  30-35, immediate restarts: 6 of 6) reach `PHASES_DONE.json` with every entry once, no ALERT, the P1 driver's entries
  unchanged, and the seal and `--verify` OK.
* Tests (CPU; sandboxes under /tmp with mock tools, the real `registration.py` and a copy of PROTOCOL.md; no GPU, no
  CARLA, no runner, no systemd scope; logs in `outputs/framelease_v4/operational_phase_driver/`):
  * `framelease_v4/protocol/tests/test_phase_driver.py`
    (`b4e5bc442cc1374b8e6af7761644021afe14536122fe8b3e79e023d55dbacf63`; the gates G0-G8, the full chain to
    `PHASES_DONE.json`, crash and restart at every crash point, runner rules, the start script):
    24 passed in 163.54s (0:02:43) (`pytest_phase_driver.log`,
    `42b12b9d6205dd7d6a8d7749f0f63e37c7e5345f5780849c3800e0b4cd2dd7e9`);
  * the review tests `outputs/framelease_v4/build/PHASE/review/test_review_phase.py`
    (`c475f4f745d3de88208c8e7c0b994373526ffc6e0821bf20194f6a226bfa8cb4`; chaos SIGKILL, an orphaned tool, a
    registered file removed in the transaction, a P1 driver record between phase records, a registration-only
    amendment): 6 passed in 66.11s (0:01:06)
    (`pytest_review_phase.log`, `e5f2c98e88088eda4803c8f29f5ba9059921a707eb70a0b839c9938fdcc6b0c1`).
* Scope. No P1 run, P1 job file, stage selection, tuning freeze or criterion changes, and no file pinned by a job line
  changes; no job line pins these files and no agent imports them. The driver is started after P1 has ended and after
  this entry is sealed. The three files are registered from this entry on; a change of any of them is an amendment.
* Manifest and seal after this addition: `MANIFEST.sha256`, 221 files, sha256
  `4bfe7451a41b853042f181cbcd7c326649b4222279bc35dd9787afa38c8d4033`, sealed with this entry.
