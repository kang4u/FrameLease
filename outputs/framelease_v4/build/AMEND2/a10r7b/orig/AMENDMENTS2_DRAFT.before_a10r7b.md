# PROTOCOL Sec. 13.2 entries of item AMEND2: drafts

Status: DRAFTS. `framelease_v4/PROTOCOL.md` is not edited by this item. The coordinating session applies each entry
under `framelease_v4/.protocol.lock` in the order and with the steps of `APPLY_PLAN2.md` (same directory). The entry
texts below are verbatim copies of the templates `final/OP_phase_driver_entry.md` and `final/A10_entry.md`, which are
the files an applier reads (`check_drafts.py` checks that both copies agree).

## Placeholders

As in `outputs/framelease_v4/build/AMEND/AMENDMENTS_DRAFT.md`:
* `{{datetime}}`: the time of application, `YYYY-MM-DD HH:MM` (Beijing time).
* `{{sha256:<path>}}`: the full 64-hex sha256 of `<path>` (project-relative) at application. The full value is what
  registers a manifest file (the phase driver's baseline adds a manifest file only when PROTOCOL.md cites its full
  sha256). The appendix lists the values at drafting; a different value at application means the file changed after
  drafting, and its review status is re-checked first (`final/*_spec.json` "must_equal" stops `apply_entry.py`).
* `{{pytest:<log>}}`: the summary line of that pytest log (`apply_entry.py` `pytest_summary`).
* `{{manifest:files}}` and `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`: the count and the sha256
  printed by `registration.py --write-manifest --force`.

## Constraints on the inserted text

Those of `AMEND/AMENDMENTS_DRAFT.md` ("Constraints on the inserted text"), and in addition:
* No entry contains the phrase "Each amendment gets the date and time" anywhere: `apply_entry.py` inserts at the first
  occurrence of the phrase and requires exactly one in PROTOCOL.md.
* No line reads as an entry of the phase driver (`phase_driver.ENTRY_RE`: a bullet that starts with a gate and its
  label in bold) or as its heading "**Phase gates (P2-P7, FULL).**" on a line of its own.
* The operational addition carries no line that `phase_driver.AMEND_RE` reads as an amendment title, does not cite the
  sha256 of `analyze_v4.py` (gate G8 attributes the first line that cites it to the amendment title above it,
  `phase_driver.citing_amendment`) and does not match `phase_driver.A7B_RE` (an operational addition placed after
  Amendment A7 is read as part of A7's text when the driver decides between A7a and A7b).
* A10 cites `analyze_v4.py` by sha256 in its Files table only, below its own title.
* Prose lines of the FILLED text are at most 120 columns (a 64-hex sha256 is longer than its placeholder); table rows
  stay single lines.

`check_drafts.py` (same directory, read only) checks all of this on the filled texts and simulates the application on
a copy of PROTOCOL.md in memory: the operational addition, the phase driver's heading with one gate entry and A10,
each inserted where `apply_entry.py` and the phase driver insert them, plus the in-place texts of A10 that exist now.
`p1_driver.protocol_view` and `phase_driver.phase_view` then raise no ALERT, the P1 entries are unchanged, and the
line citing `analyze_v4.py` belongs to A10. It also reports the open preconditions of the texts (exit 2): step 0 of
`APPLY_PLAN2.md` (A10 finding 1 states the settled commit-audit rule) and the edits E1-E4 of the AMEND drafts
(`APPLY_PLAN2.md` Sec. 3, step 0). Application needs exit 0, "all checks passed".

---

## Operational addition: the phase driver

Registers `framelease_v4/protocol/phase_driver.py`, `start_phase_driver.sh` and `tests/test_phase_driver.py`. Applied
together with Amendment A3 (the last entry of that transaction, `APPLY_PLAN2.md` Sec. 2, step 3) or right after it,
after P1 ends and before the phase driver starts (step 5). `apply_entry.py` cannot apply it (its title check requires
"**Amendment <name>,"); `final/OP_spec.json` serves its `--tests` mode only, and the transaction follows
`APPLY_PLAN2.md` Sec. 3. No in-place text.

**Operational addition, {{datetime}} (Beijing time): the phase driver of Phases 2-7 (FULL; no change of any run, job
file, selection rule or criterion).**
* What it is. `framelease_v4/protocol/phase_driver.py` (sha256
  `{{sha256:framelease_v4/protocol/phase_driver.py}}`) carries out the phase gates G0-G8 after P1 for
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
  `{{sha256:framelease_v4/protocol/start_phase_driver.sh}}`) starts the driver detached in a dedicated
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
  (`{{sha256:outputs/framelease_v4/build/PHASE/review/REVIEW.md}}`), verdict GO_WITH_FIXES; the must-fix items M1-M4
  and the should-fix items S1-S8 are applied (S7 through M2). After the fixes, chaos runs that kill the driver with
  SIGKILL at random times and after the n-th tool call (seeds 10-21, orphaned tools finishing first: 12 of 12; seeds
  30-35, immediate restarts: 6 of 6) reach `PHASES_DONE.json` with every entry once, no ALERT, the P1 driver's entries
  unchanged, and the seal and `--verify` OK.
* Tests (CPU; sandboxes under /tmp with mock tools, the real `registration.py` and a copy of PROTOCOL.md; no GPU, no
  CARLA, no runner, no systemd scope; logs in `outputs/framelease_v4/operational_phase_driver/`):
  * `framelease_v4/protocol/tests/test_phase_driver.py`
    (`{{sha256:framelease_v4/protocol/tests/test_phase_driver.py}}`; the gates G0-G8, the full chain to
    `PHASES_DONE.json`, crash and restart at every crash point, runner rules, the start script):
    {{pytest:outputs/framelease_v4/operational_phase_driver/pytest_phase_driver.log}} (`pytest_phase_driver.log`,
    `{{sha256:outputs/framelease_v4/operational_phase_driver/pytest_phase_driver.log}}`);
  * the review tests `outputs/framelease_v4/build/PHASE/review/test_review_phase.py`
    (`{{sha256:outputs/framelease_v4/build/PHASE/review/test_review_phase.py}}`; chaos SIGKILL, an orphaned tool, a
    registered file removed in the transaction, a P1 driver record between phase records, a registration-only
    amendment): {{pytest:outputs/framelease_v4/operational_phase_driver/pytest_review_phase.log}}
    (`pytest_review_phase.log`, `{{sha256:outputs/framelease_v4/operational_phase_driver/pytest_review_phase.log}}`).
* Scope. No P1 run, P1 job file, stage selection, tuning freeze or criterion changes, and no file pinned by a job line
  changes; no job line pins these files and no agent imports them. The driver is started after P1 has ended and after
  this entry is sealed. The three files are registered from this entry on; a change of any of them is an amendment.
* Manifest and seal after this addition: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.

---

## A10: registration of the analysis code

Registers `framelease_v4/analysis/{analyze_v4,prop1_coverage,figures_tables,verify_independent}.py` and their tests
(the five aggregator modules and `__init__.py` are Amendment A3's). Applied after A3 and before the analysis freeze
(gate G8 waits for it); recommended before the test freeze (`APPLY_PLAN2.md` Sec. 2, step 6). `final/A10_spec.json`
drives `apply_entry.py` (`--tests`, then `--apply` under the lock); its second in-place text starts at the end of the
Sec. 9.12 paragraph that A9 extends, and its fifth exists only after A3: both are confirmed after step 3
(`APPLY_PLAN2.md` Sec. 4).

**Amendment A10, {{datetime}} (Beijing time): registration of the analysis code: the analysis script, the
Proposition-1 coverage, the figure and table generator and the independent verification (Sec. 9.12; no effect on any
run, job file, selection or criterion).**
* Cause. Sec. 9.12 requires the sha256 of the analysis code in Sec. 13 before the analysis freeze. Amendment A3
  registers the aggregator (GAP_AUDIT rows R-1 to R-3: `framelease_v4/analysis/__init__.py`, `aggregate_v4.py`,
  `commit_audit.py`, `extra_metrics.py`, `interim_guard.py`, `manipulation.py`) and leaves the analysis script, the
  Proposition-1 coverage and the figure and table generators to their own entry. The phase driver (operational
  addition) holds the analysis freeze, gate G8, until an amendment cites the sha256 of `analyze_v4.py`. Each file
  below was built against `outputs/framelease_v4/p1_driver/GAP_AUDIT.md` Sec. 3.7 and reviewed independently
  (`outputs/framelease_v4/build/<item>/review/REVIEW.md`): R4 GO_WITH_FIXES, R5 GO, R6 GO_WITH_FIXES, R7
  GO_WITH_FIXES. Every must-fix item is applied; the second step of R7 must-fix 4 is replaced by the verification
  scope rule below. This entry registers the four files and their tests. From this entry on, a change of any of them
  is an amendment.
* Change: the files, their roles and the PROTOCOL sections they implement.

  | file | role | PROTOCOL | GAP_AUDIT | review |
  |---|---|---|---|---|
  | `framelease_v4/analysis/analyze_v4.py` | the registered analysis: the families H1, S-coll, S-dmr, H2, H3, F3, H4-cl and RL-abl with `sign_flip_test`, `bootstrap_ci`, `holm` and `label_directional` of `framelease_v2/analyze_closed_loop.py` (its sha256 checked against Sec. 12.2), the uncorrected secondary rows, the descriptive contrasts (noise floor, seed 12, RL gain by ability, kappa and seed, the depth contrast of Fig. 1, `fl_risk`), per scenario and per ability, the per-condition columns of Table I, Fig. 3 and Table II-A, the sensitivity, H4 offline, H5, the overhead quantities of Table II-B, the manipulation checks and the missing data; the Sec. 9.11 guard on the command line and in the Python API | 6, 7.2-7.6, 9.1-9.13 | R-4 | `build/R4/review/REVIEW.md`: GO_WITH_FIXES; must-fix 1-2 and should-fix 1-5 applied |
  | `framelease_v4/analysis/prop1_coverage.py` | Proposition-1 coverage of the deployed E* (L* of the cited tuning freeze, and the `fl_risk` point when L* = B0) on the 32 VAL clips: per-tau and whole-path coverage per class from `framelease_v3/envelopes.py` `clip_samples`, `iso_inside` and `coverage_summary` on the merged 37-clip view; clip bootstrap, 2000 resamples, seed 20261109; checks of the inputs, the envelope link, the gate2 reproduction and the pooled counts | 1.3, 4.3, 7.4, 9.13 | R-5 | `build/R5/review/REVIEW.md`: GO; should-fix S1-S5 not applied (below), S6 is this entry |
  | `framelease_v4/analysis/figures_tables.py` | Fig. 1 (with the scenario-type companion), Fig. 3, Table I, Table II-A, Table II-B and the training-route operating-point table with their captions, from the analysis outputs, the offline outputs, the coverage, the RL freeze, the stress reports and the D1 summary only; every shown number in `numbers.json` with its source file, field and row; the Sec. 9.11 permission check of every source; 'registered' only when every used source is registered | 4.8, 7.1-7.6, 9.8, 9.9, 9.11, 9.13 | R-6 | `build/R6/review/REVIEW.md`: GO_WITH_FIXES; must-fix 1-4 applied, should-fix items applied except those named below |
  | `framelease_v4/analysis/verify_independent.py` | the Sec. 9.12 verification: H1 and its findings, S-coll, the secondary SR, RC and infractions/km contrasts and the Table I cells DS (with its CI), SR, RC, collisions/km (route mean and pooled) and infractions/km recomputed from the job files, the runner's final records and the run directories they name; standard library and numpy only (it imports no project module and reads no analysis source); compared with the outputs of `aggregate_v4.py` and `analyze_v4.py` under tolerances fixed in its docstring | 6.1, 9.1-9.3, 9.8, 9.11, 9.12 | R-7 | `build/R7/review/REVIEW.md`: GO_WITH_FIXES; must-fix 1-3 and step 1 of must-fix 4 applied; should-fix items applied except the comparison with `numbers.json` |

* Use of the registered files (fixed by this entry).
  1. Analysis. After the analysis freeze is entered, `analyze_v4.py` runs on the aggregation of the freeze
     (`outputs/framelease_v4/analysis/final_<stamp>/`) with `--analysis-freeze`, `--required-job-files` (the tier 3-6
     job files of the test freeze), `--rl-freeze`, `--offline` (`outputs/framelease_v4/offline_ablation`, written before
     registration) and `--s3` (the registered S3 report), into `final_<stamp>/analysis/`. Its output counts as
     registered only when every condition the script states holds (the registered route table and settings, aggregations
     as the only inputs, the record checked against the registered job files, an RL freeze with a decisive P_both label,
     the offline outputs at their registered location, the registered S3 run, a determined H5 label, the location
     above); any other run is 'development' and lists why. The script reads a test-route row only under a valid
     analysis-freeze record and with its own sha256 cited in Sec. 13 (this entry).
  2. Figures and tables of the paper: `figures_tables.py --require-registered` on registered sources only. Any other
     run carries the development stamp in every figure, table and caption and never enters the paper.
  3. Proposition-1 coverage: `prop1_coverage.py` with the cited tuning freeze on the 32 VAL clips with the registered
     bootstrap; `figures_tables.py` counts a coverage run as registered only in that setting.
  4. Verification (Sec. 9.12): the procedure of the `verify_independent.py` docstring. An independent session
     (Sec. 9.12) runs it after the analysis freeze is entered, with the record, the freeze's aggregation and analysis
     and one `--queue` per queue the aggregation covers. AGREE releases H1 and its findings and the verified Table I
     columns; on DIFFER every difference is resolved and its cause entered in Sec. 13 before any of these numbers
     enters the paper. The sha256 of `verification.json` is entered in its own dated Sec. 13 entry. The other Table I
     columns follow deviation 9.
* Deviations from GAP_AUDIT and PROTOCOL recorded by the reviews (PROTOCOL governs; none changes a run, a pin or a
  criterion).
  1. Development data (Sec. 9.12: "written and tested on synthetic CSVs only"). No test-route run existed or was
     read. The values were used to check the code, never to choose a metric, a rule or a parameter.
     * `analyze_v4.py`: synthetic CSVs (unit tests; the synthetic 632-row matrix of item R4, kept as
       `outputs/framelease_v4/build/R7/dev/syn_r4/`), and on 2026-11-14 five read-only command-line runs on the
       development aggregation of P1 training-route runs `outputs/framelease_v4/build/AGG/smoke_D` of Amendment A9
       (07:40, 07:47 and 08:05 into scratch directories under /tmp; 08:14 and 08:42, the last with the final code and
       `--force`, into `outputs/framelease_v4/build/R4/smoke_train_D/`) and one load check of it (07:35): no
       test-route row, every family with n 0.
     * `prop1_coverage.py`: synthetic samples, envelopes and freezes, and the real inputs of its item: the 32 VAL
       clips of the offline stage (recorded dataset clips, not routes; Sec. 7.4 ran on them before registration) and
       the registered envelopes; development run `outputs/framelease_v4/build/R5/dev_run/`.
     * `figures_tables.py`: a synthetic analysis on synthetic route ids (`outputs/framelease_v4/build/R6/dev_run/`)
       and training-route sources (`outputs/framelease_v4/build/R6/dev/`: the training-route analysis above, the R5
       coverage run, a development RL freeze from the pilot runs, development stress reports and a development D1
       summary computed read-only from `queue_p1` on 2026-11-14 at 10:09), together with the offline outputs
       written before registration and the v2 matrix (Sec. 11.1, items 1 and 4-5).
     * `verify_independent.py`: two synthetic matrices (`build/R7/dev/syn_r4/`, `build/R7/dev/syn_varied/`) and a
       read-only snapshot of the `queue_p1` runner records with the run directories they name
       (`build/R7/dev/p1_snapshot/`, `build/R7/dev/verify_p1/`: 172 job lines, 139 usable training-route runs).
       For the comparison, `aggregate_v4.py` ran read-only on that snapshot on 2026-11-14, 11:46-11:50
       (`build/R7/dev/agg_p1/`; 0 test-route rows), a development aggregation in addition to those of Amendment A9.
       Two probe runs of `aggregate_v4.py --write-freeze-record` on copies of the 7 P1-0 smoke job lines of route
       18305 under /tmp wrote development analysis-freeze records (`build/R7/dev/scratch/freeze_probe_all_final.json`,
       `freeze_probe_cut.json`); no entry cites them, so neither is valid.
  2. Values of data that existed before registration were computed during development. The H4 offline label (Sec. 9.4;
     `build/R4/smoke_train_D/h4_offline.csv`: all 12 rows 'inconclusive'), the Table II-A offline panel and Fig. 1
     (a)-(b) from the offline outputs written before registration (Sec. 11.1 item 5 records that only their column
     headers, not their values, were viewed before registration), and the Proposition-1 coverage of E5, E10 and B0 on
     the 32 VAL clips. The H4 rule, the coverage definitions and their bootstraps are those of Secs. 7.4 and 9.4; no
     selection reads these values (the lease operating point is selected on closed-loop training DS, Secs. 4.2-4.9).
  3. Output location (Sec. 9.12: outputs go to `final_<stamp>/` with a sha256 manifest). The aggregation of the
     analysis freeze occupies `final_<stamp>/` with its own `SHA256SUMS`; the analysis writes into
     `final_<stamp>/analysis/` with its own `SHA256SUMS` and refuses a directory that holds an aggregation.
  4. Collisions per km (Sec. 6.1). The route-level value (`collisions_per_km`) is used by the paired contrasts and
     S-coll. The arm-level value is the pooled ratio (`collisions_per_km_pooled`): the sum of collisions over the sum
     of km driven with the 0.001 km floor per route, over the routes with both values, with a route-cluster
     percentile bootstrap (routes resampled, the ratio of sums per resample; 10,000 resamples, a fresh
     `default_rng(20261110)`, the draws of `bootstrap_ci`; 95%). Table I shows the pooled value and its interval.
  5. Sign-flip test (Sec. 9.1). The Monte Carlo cross-check (Sec. 9.1 names no seed) uses 200,000 sign vectors with
     the registered v4 seed 20261110; decisions use the exact p. Beyond 2^23 bins the registered `sign_flip_test`
     coarsens its DP grid (1-2-5 steps); `analyze_v4.py` reports the grid used next to the registered one (`dp_grid`,
     `dp_grid_registered`), and the verification reports its own p on that grid as a diagnostic.
  6. H4 offline (Sec. 9.4: "If an offline output lacks a paired quantity, the v4 analysis script computes it from
     `per_clip_selected.csv` with the same bootstrap"). `per_clip_selected.csv` holds the TRAIN-selected candidates only
     (subset all, alpha 0.05, AGE, GLOBAL and SUFFIX) and cannot supply a nested quantity; utilization cannot be pooled
     from it (the positives are not recorded). The script uses it only within that scope, reports any other missing
     quantity as missing with its reason, and recomputes every in-scope `paired.csv` row as a check (30 TRAIN rows
     agree, maximum difference 5.0e-6). On the offline outputs of Sec. 11.1 item 5 `paired.csv` supplies all 12 H4 rows.
     The secondary rows are the full crossing of Sec. 9.4's variations (2 comparisons x 2 risk levels x 3 quantities: 1
     primary and 11 secondary rows); 7 of them combine two or more variations; each is secondary and uses the same rule.
  7. H5 (Sec. 9.5 has the labels supported and contradicted). 'undetermined' marks incomplete evidence (an input
     without the commit audit, runs withheld by the interim-look guard, a phase not covered, no registered S3 report)
     and makes the run 'development'; the registered analysis has a determined label. A run the audit could not
     check leaves condition 1 unmet: status ERROR, or NO_LOG (neither `jobs.jsonl` nor `events.jsonl`) when the
     `runs.csv` row that selects the run records commits or no row records them; every NO_LOG run is listed.
  8. Table II-B (Sec. 7.6). `analyze_v4.py` reports the panel-B log quantities per condition as distributions of the
     per-run values (per-run quantiles are never pooled across runs); `figures_tables.py` renders Table II-B with S1-S4.
  9. Verification scope (Sec. 9.12: "recomputes the H1 contrasts and the Table I columns"). `verify_independent.py`
     recomputes DS, SR, RC, collisions/km and infractions/km. GPU usage, DMR, action age p50 and p95, fallback ratio,
     EIR, P_both and the closed-loop R_cond of the notes are registered results (Secs. 7.2, 9.13) and are recomputed
     by a second independent script from the run directories (Secs. 6.2-6.4, including the realized validity of the
     actor boxes behind EIR, R_cond and P_both). That script is registered by its own amendment before the analysis
     freeze and runs after it next to `verify_independent.py`; these columns enter the paper once its result is
     entered in Sec. 13.
  10. Verification statistics. The DP rounds `d / grid` with `numpy.rint`, the rounding of the registered
      `sign_flip_test`; the two decimal readings of "rounded" are reported at exact half-grid ties as diagnostics. A
      missing p counts as 1 in Holm and has no adjusted p. With the registered resamples and seed on both sides every
      bootstrap endpoint is judged to 1e-9. A DP support above 40,000,001 states makes that contrast 'not computable'.
      Every expected file, column and field is compared; an absent one is a difference.
  11. Figure layout (Sec. 7.1: panel (a) offline, the error against observation age and the Fast@Fresh - Deep@Old
      contrast against kappa; panel (b) closed loop, Fixed Deep - Fast Only per scenario type and per ability). Fig. 1
      has the offline panels (a) error against observation age and (b) Fast@Fresh - Deep@Old against kappa, and the
      closed-loop panel (c) Fixed Deep - Fast Only by ability next to the earlier measurement; the per-scenario-type
      difference (44 named rows) is a companion figure in the supplement (Sec. 9.13).
  12. Results that `figures_tables.py` does not render: the secondary offline protocols of Sec. 7.4, the uncorrected
      secondary rows of Sec. 9.3 (`secondary.csv`), the replicates and the noise floor (Sec. 9.6; `descriptive.csv`)
      and the manipulation checks beyond the background-load counts (Sec. 9.7; `analysis.json`). They enter the
      supplement from these files (Sec. 9.13). Compact main-text variants of Tables II-A and II-B are not built.
* Known limitations accepted (review should-fix items not applied; none affects a registered number or the Sec. 9.11
  guard of a command-line run).
  * `prop1_coverage.py`: in the Python API, `compute(routes=...)` replaces the registered test-route set instead of
    adding to it, and route ids are compared as strings (R5 S1, S2; the command line always uses the registered
    split, and no clip is on a test route); `CODE_FILES` omits `framelease_v3/suffix_lease_eval.py` and
    `framelease_v4/arms/metrics_v4.py` (S5; the reused code outside the manifest is fixed by its sha256 under
    "Evidence"). A run outside the registered setting carries no marker of its own (S3); `figures_tables.py` treats
    it as development.
  * `verify_independent.py`: the rendered Table I is not compared with `numbers.json`; `figures_tables.py` traces
    every printed number to its source row instead. The review tests `GuardRecordVocabulary` (a registered test
    route under a copy of PROTOCOL.md) and `ForgedProtocolCopy` exclude each other: under the registered rule the
    first is refused; on a synthetic test route the same three cases pass
    (`build/R7/fix/test_review_R7_vocab_synthetic.py`).
* Reporting rules for Proposition 1 (R5 review S4). With the coverage, the paper states: the lambda of E5 and E10 was
  selected on the same 32 VAL clips (the in-sample row of `frontier.csv`, Sec. 4.3), so the VAL coverage is not held
  out with respect to lambda; the coverage is conditional on a confident detection matched within 2 m and within
  50 m of the LiDAR, so missed actors lie outside it; whole-path coverage counts the recorded taus of each pair only;
  the pedestrian intervals rest on 6 clip clusters.
* Findings of the development runs carried to the analysis freeze (files of Amendment A3; this entry changes none).
  1. Commit audit, null margins. On `build/R7/dev/agg_p1` the commit audit (R-2) of the version of `commit_audit.py`
     used there (sha256 `96dd22c4...bff279`) reported FAIL with 12,958 'margin' violations in 38 of the 48 audited
     `fl_heuristic` runs of the stages `lease_s1` and `lease_s2` (violations: B0 8,179, E10 2,625, E5 2,154); the
     development aggregations `build/AGG/smoke_B`, `smoke_C` and `smoke_D` of 2026-11-11 (P1-0 smoke and `ref` runs
     only; 4,109 accepted commits) were PASS. Every flagged commit is an accepted commit whose logged margin is null
     (+inf) and whose validity record has n_relevant > 0, n_computed 0 and reason `horizon_cap`: the lease prefilter
     (`framelease_v3/runtime/v3_lease.py`) computed no agent because the distance lower bound of every relevant agent
     keeps its margin above delta, so the lease is the horizon cap and the margin at the commit is +inf. That version
     accepted a null margin only when the record named no relevant agent (n_relevant 0 or reason
     `no_relevant_agents`). The rule was settled in `commit_audit.py` before Amendment A3, which registers it: a null
     margin also passes when the validity record has reason `horizon_cap` and n_computed 0 (the prefilter showed
     g > delta for every relevant agent, so M = +inf and Eq. 9 holds); any other null margin with a relevant agent
     is a violation. H5 is decided by the registered commit audit.
  2. Kilometres of a run with RC 0. The aggregator's `runs.csv` holds `km_driven` 0.0 for the smoke run of
     `fl_heuristic` on route 18305 (RC 0), where Sec. 6.1 floors km at 0.001; its collisions/km and infractions/km
     agree with the verification, and the pooled ratio applies the floor.
  3. Run selection without a runner record. For a job whose runner records are absent (a probe with its status lines
     removed) the aggregator selects a run from the job's output directory and the freeze record lists it; the
     verification reads the runner's final record only and lists such a job as a 'freeze record' difference. At the
     analysis freeze every job of `queue_p4` has a final runner record (gate G8).
* In-place text.
  * Sec. 4.1, the status sentence of Amendment A3: "the analysis script, the Proposition-1 coverage and the figure and
    table generators remain required before the analysis freeze" becomes "the analysis script, the Proposition-1
    coverage, the figure and table generator and the independent verification script are registered by Amendment
    A10".
  * Sec. 9.4, the last sentence, ends: "... with the same bootstrap, within that file's scope (TRAIN-selected
    candidates, subset all, alpha 0.05); a nested quantity comes from `paired.csv` only (Amendment A10)."
  * Sec. 9.12, "**Code.**", the last sentence ends: "... before the analysis freeze (the aggregator: Amendment A3; the
    analysis code: Amendment A10)."; then a new paragraph before "**Freeze.**":
    "**Analysis code (Amendment A10).** `analyze_v4.py`, `prop1_coverage.py`, `figures_tables.py` and
    `verify_independent.py` (`framelease_v4/analysis/`) are registered by Amendment A10. Besides synthetic data, they
    were run read-only during development on training-route aggregations, the offline VAL clips and P1 run
    directories, never on a test-route run."
  * Sec. 9.12, "**Freeze.**", the last sentence ends: "..., with a sha256 manifest; the analysis writes into its
    subdirectory `analysis/` with its own manifest (Amendment A10)."
  * Sec. 9.12, "**Verification.**", ends: "... from the raw run directories (Amendment A10:
    `framelease_v4/analysis/verify_independent.py` recomputes DS, SR, RC, collisions/km and infractions/km; a second
    script, registered by its own amendment before the analysis freeze, recomputes the other Table I columns, which
    enter the paper once its result is entered in Sec. 13)."
* Scope. No run, job file, pin, stage selection, freeze or criterion changes. No job line pins these files and no
  agent process imports them. The analysis-freeze record freezes the aggregator modules (Amendment A3); the analysis
  script checks its own citation (this entry) before it reads any test-route row; G8 of the phase driver waits for
  this entry. This entry precedes the analysis freeze.
* Files (sha256).

  | file | sha256 |
  |---|---|
  | `framelease_v4/analysis/analyze_v4.py` | `{{sha256:framelease_v4/analysis/analyze_v4.py}}` |
  | `framelease_v4/analysis/prop1_coverage.py` | `{{sha256:framelease_v4/analysis/prop1_coverage.py}}` |
  | `framelease_v4/analysis/figures_tables.py` | `{{sha256:framelease_v4/analysis/figures_tables.py}}` |
  | `framelease_v4/analysis/verify_independent.py` | `{{sha256:framelease_v4/analysis/verify_independent.py}}` |
  | `framelease_v4/analysis/tests/test_analyze_v4.py` | `{{sha256:framelease_v4/analysis/tests/test_analyze_v4.py}}` |
  | `framelease_v4/analysis/tests/test_prop1_coverage.py` | `{{sha256:framelease_v4/analysis/tests/test_prop1_coverage.py}}` |
  | `framelease_v4/analysis/tests/test_figures_tables.py` | `{{sha256:framelease_v4/analysis/tests/test_figures_tables.py}}` |
  | `framelease_v4/analysis/tests/test_verify_independent.py` | `{{sha256:framelease_v4/analysis/tests/test_verify_independent.py}}` |

* Evidence (outside the manifest; fixed by these sha256). Reviews: `outputs/framelease_v4/build/R4/review/REVIEW.md`
  (`{{sha256:outputs/framelease_v4/build/R4/review/REVIEW.md}}`), `build/R5/review/REVIEW.md`
  (`{{sha256:outputs/framelease_v4/build/R5/review/REVIEW.md}}`), `build/R6/review/REVIEW.md`
  (`{{sha256:outputs/framelease_v4/build/R6/review/REVIEW.md}}`), `build/R7/review/REVIEW.md`
  (`{{sha256:outputs/framelease_v4/build/R7/review/REVIEW.md}}`). Output manifests of the development runs:
  `build/R4/smoke_train_D/SHA256SUMS` (`{{sha256:outputs/framelease_v4/build/R4/smoke_train_D/SHA256SUMS}}`),
  `build/R5/dev_run/SHA256SUMS` (`{{sha256:outputs/framelease_v4/build/R5/dev_run/SHA256SUMS}}`),
  `build/R6/dev/SHA256SUMS` (`{{sha256:outputs/framelease_v4/build/R6/dev/SHA256SUMS}}`),
  `build/R6/dev_run/SHA256SUMS` (`{{sha256:outputs/framelease_v4/build/R6/dev_run/SHA256SUMS}}`),
  `build/R7/dev/agg_p1/SHA256SUMS` (`{{sha256:outputs/framelease_v4/build/R7/dev/agg_p1/SHA256SUMS}}`),
  `build/R7/dev/verify_p1/SHA256SUMS` (`{{sha256:outputs/framelease_v4/build/R7/dev/verify_p1/SHA256SUMS}}`),
  `build/R7/dev/syn_r4/verify/SHA256SUMS` (`{{sha256:outputs/framelease_v4/build/R7/dev/syn_r4/verify/SHA256SUMS}}`),
  `build/R7/dev/syn_varied/verify/SHA256SUMS`
  (`{{sha256:outputs/framelease_v4/build/R7/dev/syn_varied/verify/SHA256SUMS}}`). Code that the coverage reuses
  outside the registration manifest, equal to the sha256 recorded in
  `outputs/framelease_v3/gate2_offline/gate2_20261109/config.json` (R5 review Sec. 3): `framelease_v3/envelopes.py`
  (`{{sha256:framelease_v3/envelopes.py}}`), `framelease_v2/calibration.py`
  (`{{sha256:framelease_v2/calibration.py}}`) and `framelease_v3/suffix_lease_eval.py`
  (`{{sha256:framelease_v3/suffix_lease_eval.py}}`).
* Tests (CPU; logs in `outputs/framelease_v4/amendment_a10/`):
  * `tests/test_analyze_v4.py`: {{pytest:outputs/framelease_v4/amendment_a10/pytest_analyze_v4.log}}
    (`pytest_analyze_v4.log`, `{{sha256:outputs/framelease_v4/amendment_a10/pytest_analyze_v4.log}}`);
  * `tests/test_prop1_coverage.py`: {{pytest:outputs/framelease_v4/amendment_a10/pytest_prop1_coverage.log}}
    (`pytest_prop1_coverage.log`, `{{sha256:outputs/framelease_v4/amendment_a10/pytest_prop1_coverage.log}}`);
  * `tests/test_figures_tables.py`: {{pytest:outputs/framelease_v4/amendment_a10/pytest_figures_tables.log}}
    (`pytest_figures_tables.log`, `{{sha256:outputs/framelease_v4/amendment_a10/pytest_figures_tables.log}}`);
  * `tests/test_verify_independent.py`: {{pytest:outputs/framelease_v4/amendment_a10/pytest_verify_independent.log}}
    (`pytest_verify_independent.log`, `{{sha256:outputs/framelease_v4/amendment_a10/pytest_verify_independent.log}}`).

  At drafting (2026-11-14): 48 passed and 107 subtests; 22 passed; 50 passed; 28 passed and 20 subtests
  (`outputs/framelease_v4/build/AMEND2/logs/`).
* Manifest and seal after this amendment: `MANIFEST.sha256`, {{manifest:files}} files, sha256
  `{{sha256:outputs/framelease_v4/registration/MANIFEST.sha256}}`, sealed with this entry.

---

## Appendix: sha256 at drafting (2026-11-14 13:55, Beijing time)

A value at application that differs from this list means the file changed after drafting; its review
status is re-checked before the entry is applied.

```
2bf4147c610751c8380f55c59d10f889ce7062849c56351ebbaa8fac1ac7c994  framelease_v4/protocol/phase_driver.py
5c70674fbf043bd4eb5fec9236b0a5fca2123bc5087bf12ddf75bac3c171a0ca  framelease_v4/protocol/start_phase_driver.sh
d7ef679052cb6af5d3385ae231b0f086e8c522ac0d193b17900dc6bbe655bd0c  outputs/framelease_v4/build/PHASE/review/REVIEW.md
b4e5bc442cc1374b8e6af7761644021afe14536122fe8b3e79e023d55dbacf63  framelease_v4/protocol/tests/test_phase_driver.py
c475f4f745d3de88208c8e7c0b994373526ffc6e0821bf20194f6a226bfa8cb4  outputs/framelease_v4/build/PHASE/review/test_review_phase.py
10d7ea4f9516725cd94932a0618bbe5cc6a20bae60b49f4004013b3682cee54c  framelease_v4/analysis/analyze_v4.py
ffaee8ddf74e707901208d1d28ad0f692fefda2a4f4ce24f9e36e6eba1c852c0  framelease_v4/analysis/prop1_coverage.py
bd4ed54c60fbc5259aeb2ed56f5301ad612c3006fd4172f06b889f2ea0c2118c  framelease_v4/analysis/figures_tables.py
4935152684abcfdaef547438772bb041f323344dcbfe636d41b2a161ff149bff  framelease_v4/analysis/verify_independent.py
1a59a3e044478d56a0bb1700d756bfcf80f9c4b2e4b1c38c83fa2a111780564c  framelease_v4/analysis/tests/test_analyze_v4.py
fa72530489076fe1620002e77997abbae46b9f602b8cf39c987de8206a0d1bd3  framelease_v4/analysis/tests/test_prop1_coverage.py
8b61b3b35933e1f4dbc33c682462a6533500158013053182ab0aae6281ae793e  framelease_v4/analysis/tests/test_figures_tables.py
c647f9091c99944fa6d39e97e2f8c7283a819aeb820e668ae512885f2ff77823  framelease_v4/analysis/tests/test_verify_independent.py
4cfda4da4ff9efe19fc69c5583f297e8fdf0fab15bf83ddc994480c43601832f  outputs/framelease_v4/build/R4/review/REVIEW.md
4dbdb3fe1bea1ca387036ed4ab2a4225b8e84fdd8e65be913bfd4f9922fd7fb2  outputs/framelease_v4/build/R5/review/REVIEW.md
40b29a2cfb0fbfde1961870da96d3bca71d60088ef1c56a249c3c62fbb137abf  outputs/framelease_v4/build/R6/review/REVIEW.md
e4333416adefd2109ccf7f574ab2ce06ab22a41a1c4f5410f22c7688772e4917  outputs/framelease_v4/build/R7/review/REVIEW.md
375c92331006f0aac9a0a30ff39698a082d0d2758596daa49dedb27c55c3470d  outputs/framelease_v4/build/R4/smoke_train_D/SHA256SUMS
ccb795dc4db10fbbd9a0ede6005c467c328623ed1f6f715b783116a1d516fa56  outputs/framelease_v4/build/R5/dev_run/SHA256SUMS
931ca0644b7690c72db4c9650eb19ee96e6e091fd160f180a3989f42ab3c77dd  outputs/framelease_v4/build/R6/dev/SHA256SUMS
503766a2d9bca8adf5eec080fc5eb320b72c8ed78dcd884929571f352e2e100f  outputs/framelease_v4/build/R6/dev_run/SHA256SUMS
672a57ee3b336fa494eb7825b3aa99c8964f9be19f8bdf2435c059ce4233786b  outputs/framelease_v4/build/R7/dev/agg_p1/SHA256SUMS
5824a84f4bfbcdc20353bc538e02d124c7459d53e7503d3c5ac815e7b9f63442  outputs/framelease_v4/build/R7/dev/verify_p1/SHA256SUMS
a9a4f543bbd3efad4fadc8c9e735c6e3896fb19457b532b0b70a5f0e45171071  outputs/framelease_v4/build/R7/dev/syn_r4/verify/SHA256SUMS
ea082386a43bdd2794cd4144681d6046ee76923dc7b14a295a4771542227f232  outputs/framelease_v4/build/R7/dev/syn_varied/verify/SHA256SUMS
4b50e33d5abcf1e791fe87d84039cdc560be313827db457ef7160968e633307c  framelease_v3/envelopes.py
eb69bae0a64ece0fabc4c5133d18985f9d83f7c41fc3b42dca39e789f6193e2b  framelease_v2/calibration.py
48417c1fc9ce6d0e7d604da1292f6a002ab266c500f9226b4cd17fbbf490691c  framelease_v3/suffix_lease_eval.py
```

Written at application (no value at drafting):

* `outputs/framelease_v4/amendment_a10/pytest_analyze_v4.log`
* `outputs/framelease_v4/amendment_a10/pytest_figures_tables.log`
* `outputs/framelease_v4/amendment_a10/pytest_prop1_coverage.log`
* `outputs/framelease_v4/amendment_a10/pytest_verify_independent.log`
* `outputs/framelease_v4/operational_phase_driver/pytest_phase_driver.log`
* `outputs/framelease_v4/operational_phase_driver/pytest_review_phase.log`
* `outputs/framelease_v4/registration/MANIFEST.sha256`
