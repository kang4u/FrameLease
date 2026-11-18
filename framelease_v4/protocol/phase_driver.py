#!/usr/bin/env python3
"""Phase driver of the FrameLease v4 protocol after P1, variant FULL: the gates G0-G8 of Phases 2-7
(framelease_v4/PROTOCOL.md Secs. 4.8, 5.3, 5.9, 7.6, 8.1, 9.11, 9.12, 13.2; outputs/framelease_v4/p1_driver/GAP_AUDIT.md
Sec. 3.6, item E-2). Modelled on framelease_v4/protocol/p1_driver.py, whose helpers it imports (never edits). It starts
CARLA and the GPU only through framelease_v4/protocol/launch_queue.sh, every runner in a dedicated systemd user scope.

  cd /home/kang/Desktop/DAC
  .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/phase_driver.py --dry-run   # what it would do now
  bash framelease_v4/protocol/start_phase_driver.sh                                          # detached, own scope
  .conda-unidrive-linux/bin/python -I -B framelease_v4/protocol/phase_driver.py --once      # one cycle, foreground

Every cycle (--interval-s, default 300 s) walks the gates in order and stops at the first one that is not passed:
  G0 wait (never an ALERT) until outputs/framelease_v4/p1_driver/P1_DONE.json exists, Sec. 13.2 holds the P1 driver's
     "Tuning freeze" and "D1 summary" entries and the coordinating session's Amendment A3, A4, A7 and A9 entries, no
     P1 record transaction is open, and the seal verifies (registration.py --verify: both seal lines OK; a manifest
     difference only of unregistered files, i.e. code in development). APPLY_PLAN row 9 allows A4 "during P2 or P3";
     this driver waits for it here, so the coordinating session applies A4 before the D1 decision.
  G1 D1 (Sec. 4.8): wait until phase_driver/D1_DECISION.json exists. The coordinating session writes it under the
     user's instruction of 2026-11-14 ("from now on, review yourself whether to proceed to the next phase", which it
     reads as covering D1): {"decision": "continue" | "stop", "rationale": "...", "d1_summary_sha256": "<sha256 of
     tuning/d1/FULL_d1_summary.json>"} (optional: "schema" framelease_v4.d1_decision/1, "decided", "by"). The summary
     sha256 must be the file's and the one the P1 driver's "D1 summary" entry cites (else ALERT). Recorded as a dated
     Sec. 13.2 entry that cites the decision file's sha256, quotes the instruction (translated) and states that reading.
     'stop': phase_driver/P2_STOPPED.json, the driver ends (it never starts P2 later).
  G2 P2 job file (Secs. 5.3, 8.2): source linux/env.sh && CUDA_VISIBLE_DEVICES= .conda-unidrive-linux/bin/python -I -B
     framelease_v4/protocol/p2_jobs.py --check --write --jobs-dir outputs/framelease_v4/p2_jobs, run once while its
     three files are missing (p2_jobs.py has no --variant flag: it writes FULL only); the .check.json must show no
     problem and every dry run passed, the stage spec must cite the recorded tuning freeze. The job file, stage spec
     and check sha256 are recorded in Sec. 13.2 BEFORE the copy; then the job file is copied into
     outputs/framelease_v4/queue_p2/jobs.d (temporary name, atomic rename; never twice, never over a different file)
     and the runner is launched (below).
  G3 when every P2 job in queue_p2/jobs.d is final and no runner holds the queue: p2_check.py --queue
     outputs/framelease_v4/queue_p2 (no --write); exit 1 (FAIL) or 2: ALERT; exit 3 (INCOMPLETE): wait. PASS with
     missing episodes (no valid record after the registered retry, GAP_AUDIT Sec. 6 item 5(c)): ALERT naming them,
     unless phase_driver/P2_MISSING_ACK.txt names every missing job id (the coordinating session's decision; the entry
     cites it). Then p2_check.py ... --write, and the data manifest (rl_data/data_manifest.json) and the report
     (rl_data/p2_check.json) are recorded in Sec. 13.2. While P2 runs: job health only (runner rules below, disk).
  G4 P3 (Secs. 5.4-5.9, 8.1; GAP_AUDIT Sec. 3.3), once no runner, closed-loop process or P1 driver is alive (the GPU
     idle), no p3_rl.py process is left from an earlier driver process and the P3 code is registered (p3_rl.py, every
     file under framelease_v4/rl and the P2 gate sources that p3_rl.code_sha256 hashes; else wait): p3_rl.py run
     --stop-after dataset; p3_rl.py calibrate --sizes 33,66,132 (the production sizes) --d-star d* --lengths-from
     outputs/framelease_v4/rl_freeze/dataset --out outputs/framelease_v4/build/phase_driver/p3_calibration.json (once;
     never overwritten); p3_rl.py run --n-jobs <the recommended n_jobs> (capped only if that many workers at the
     probe's peak RSS exceed 75% of MemAvailable); p3_rl.py status (exit 0); rl_freeze.json validated (production,
     frozen, made from the recorded tuning freeze and P2 data manifest, every named file at its sha256) and recorded.
     Exit 4 (an open case of GAP_AUDIT Sec. 6 item 5): ALERT naming the case; the coordinating session decides in
     phase_driver/P3_OPEN_CASES.json ({"options": {"<case>": "<alternative>"}, "rationale": "..."}), passed to every
     later p3_rl.py run and cited by the entry; case (c) 'proceed' follows from the G3 acknowledgement of the missing
     P2 episodes. The P3 tools run on every core (--all-cores 0-15) at nice 10 / ionice best-effort 7.
  G5 stress tests (Sec. 7.6, Amendment A7), each once with --registered on --stress-states (synthetic before the test
     freeze) and the deployed networks of the RL freeze, once stress_bench.py is registered: s3; s2 (registered grid);
     s2 --grid relative (the supplementary grid, only when the entered A7 is the variant A7b: its text names
     `s2 --grid relative` or the "supplementary S2 grid"; under A7a no supplementary run and no supplementary
     sentence); s1 --envelope L* last, behind the exclusive-CPU guard: a process of this project
     alive (a runner, CARLA, a driver, an RL job: stress_bench.BLOCKING_MARKERS) -> wait; foreign CPU (>= 5% of one
     core over 2 s, sampled by the driver and recorded in phase_driver/s1_guard.json) or a foreign-CPU refusal of
     stress_bench.py itself -> retry after --s1-retry-s (600 s), ALERT after --s1-retries (3) retries; with
     phase_driver/S1_ACCEPT_FOREIGN_CPU.txt (the coordinating session's reason) s1 runs with --accept-foreign-cpu.
     Every report (outputs/framelease_v4/stress/, one per glob) is checked as test_freeze.py checks it (S2 and S3: 0
     violations) and never rerun or overwritten; they are recorded in one entry (the supplementary report has no
     other anchor; the test freeze takes S1-S3).
  G6 test freeze (Secs. 3.3 rule 4, 5.9, 8.1; GAP_AUDIT G-1 to G-3, E-1), once test_jobs.py, test_freeze.py,
     check_smoke_ext.py and every file under framelease_v4/arms_ext are registered (else wait): source linux/env.sh
     && CUDA_VISIBLE_DEVICES= test_jobs.py --check --write (once, while index.json is missing; the index validated:
     every block clean, name order = tier order); registration.py --verify (seal OK, no registered file changed);
     test_freeze.py --write and --entry; the record recorded in Sec. 13.2 with the entry text test_freeze.py
     printed, nested under the driver's bullet (unchanged words, re-wrapped); test_freeze.py --verify; the job files
     copied in tier order into outputs/framelease_v4/queue_p4/jobs.d (atomic, never twice); test_freeze.py --verify
     (the copies); phase_driver/P4_QUEUED.json; the runner launched (below; 11.9 GiB free, Sec. 10.1). Passed once a
     runner of queue_p4 has started.
  G7 P4-P6 (tiers 3-6 in queue_p4): job health only (PROTOCOL Sec. 9.11: job health, timing and disk; the driver
     reads no outcome, metric or route of a test-route run and summarizes nothing across arms): the runner rules
     below, the disk, the progress in state.json (per job file: jobs, final). A job file in jobs.d that the test
     freeze does not name: attention (G8 refuses it). Passed when every job in queue_p4/jobs.d is final and no runner
     holds the queue.
  G8 analysis freeze (Sec. 9.12): wait (attention, no ALERT) until Sec. 13.2 cites the sha256 of
     framelease_v4/analysis/analyze_v4.py (the coordinating session's amendment that registers the analysis code)
     and PROTOCOL.md cites the sha256 of every analysis module the record freezes (interim_guard.ANALYSIS_MODULES:
     Amendment A3 or a later one); jobs.d must hold exactly the P4-P6 copies of P4_QUEUED.json at their sha256;
     registration.py --verify (seal OK, no registered file changed); then once
       aggregate_v4.py --queue outputs/framelease_v4/queue_p4 --specs outputs/framelease_v4/test_jobs/FULL \
           --rl-freeze outputs/framelease_v4/rl_freeze/rl_freeze.json --tuning-freeze <tuning freeze> \
           --write-freeze-record outputs/framelease_v4/analysis/final_<stamp>/analysis_freeze.json \
           --out outputs/framelease_v4/analysis/final_<stamp>
     (one final_<stamp> directory: reused after a restart, with --force only when it holds the outputs of an
     aggregation stopped before its record; never --arm-summary, never --analysis-freeze, so every test-route row
     stays health-only and no cross-arm summary is made before the freeze; the driver runs no aggregation at any
     other gate). The record must be the analysis freeze of the registered job files (trigger all_final, every job
     line with a final outcome, the analysis code equal to the registered files on disk, SHA256SUMS holding for every
     file it lists: sha256sum -c; else ALERT, never rewritten); it is recorded in Sec. 13.2 (record, SHA256SUMS of the
     directory, analyze_v4.py; the job status:
     outcome counts over all jobs), which makes it valid (interim_guard.load_freeze); then PHASES_DONE.json and the
     driver stops. A cut (Sec. 10.2) is not driven: the driver waits at G7 while a job is pending.
Long tools (G4-G6, G8) write their output to phase_driver/logs/<step>.<time>.{out,err}; a STOP file or a signal
terminates a P3 or stress tool or the aggregation (its process group; p3_rl.py resumes its stages, a stress run is
redone from scratch, an aggregation without record is redone with --force), while test_jobs.py and test_freeze.py are
waited for. A tool runs in its own session and outlives a killed driver: before the driver starts any tool
(registration.py included) or reads what it writes, it waits (attention, no ALERT) while a process runs that tool
(review fix M2).
Tool code (review fix M4): before G2-G6 run a tool, every file of its code (G2 p2_jobs.py; G3 p2_check.py; G4 and G5
and G6 as above) must be registered: at the sha256 the registered baseline holds, or at a sha256 the sealed PROTOCOL.md
cites (APPLY_PLAN Sec. 2 allows A3 to be split, the P3-P7 tools registered by a later "A3b"); else the gate waits
(attention, no ALERT). G8 applies the same rule to the analysis code. A tool script outside framelease_v4/ (a test
stand-in) is not checked, and the driver refuses to start with one in the project tree.
Record (each gate entry): under an exclusive flock on framelease_v4/.protocol.lock, the p1_driver transaction:
PROTOCOL.md and MANIFEST.sha256 must be the sealed ones; every REGISTERED file must match the sealed manifest
(pre-check); registration.py --write-manifest --force; every registered file must have entered the new manifest with
its sealed sha256 and none may have vanished from it (post-manifest check, p1_driver review fix F1, and review fix
M3); the entry; registration.py --seal; registration.py
--verify. Any failure: ALERT. The entries go under the heading "**Phase gates (P2-P7, FULL).**", created once just
before the paragraph "Each amendment gets the date and time" (so after the P1 driver's "**Stage selections (P1,
FULL).**" block); each is a bullet "* **G<n> <label>** (YYYY-MM-DD HH:MM, Beijing time). ...", a form that
p1_driver.ENTRY_RE ("* **<label>**, <date> (") never matches.
Registered files (phase_driver/registered_baseline.json): seeded from the P1 driver's p1_driver/registered_baseline.json
(read only); every later seal (another editor's or the driver's own, identified by the pair of sealed PROTOCOL.md and
manifest sha256: an amendment that only cites files leaves the manifest unchanged, review fix M1) keeps every baseline
file with its newly sealed sha256 and adds a file of its manifest only if PROTOCOL.md cites that file's sha256 (an
amendment registering it, e.g. A3); the P1 job files (outputs/framelease_v4/p1_jobs/) always count as registered. An
unregistered framelease_v4 file (code in development) may change between seals: the next entry names it.
Runner (one queue at a time: queue_p2 at G2-G3, queue_p4 at G6-G7): it is launched only as
  systemd-run --user --scope --unit=framelease-<queue>-runner-<ts> -p OOMPolicy=continue \
      bash framelease_v4/protocol/launch_queue.sh <queue>
at the driver's own priority, nice 0 on every core (the driver refuses to run niced or pinned to some CPUs, which the
runner, CARLA and the evaluator would inherit), so that an OOM kill ends only the killed process
(outputs/framelease_v4/validity_notes/oom_20261112.md). Launched after the driver copied the job file, after a normal
'queue empty' exit with pending jobs (not after EMPTY_EXIT_LIMIT = 2 such exits in a row without a job started:
attention), or into a queue that never had a runner. Never while <queue>/STOP exists
(attention; the file is the disk watchdog's or the user's), while a runner of another queue of this project is alive
(attention), or with less free disk than the queue needs (P2: 7.3 GiB, outputs/framelease_v4/p2_jobs/README.md;
queue_p4, tiers 3-6: 11.9 GiB, PROTOCOL Sec. 10.1, at its first launch; a relaunch during P4-P6 relies on the runner's
own 6 GiB rule and the disk watchdog);
after a circuit-breaker exit (3) or a runner error (1): ALERT; after a signal exit (4): attention, no relaunch.

Files (outputs/framelease_v4/phase_driver/): state.json (gate -> status, files, sha256, queue progress; rewritten
atomically after every step), driver.log, ALERT.txt, driver.lock (one instance), driver.pid, protocol_txn.json (an
interrupted record transaction), manifest_sealed.sha256 (copy of the last sealed manifest), registered_baseline.json,
STOP (the driver exits at its next check), D1_DECISION.json, P2_MISSING_ACK.txt, P3_OPEN_CASES.json and
S1_ACCEPT_FOREIGN_CPU.txt (written by the coordinating session, atomically: a temporary file in the same directory,
then mv; a decision JSON that is not readable is read again for DECISION_GRACE_S = 120 s after its last modification,
then ALERT), s1_guard.json (the S1 attempts and their foreign-CPU
samples), P4_QUEUED.json (G6: the P4-P6 job files copied and verified), logs/ (the long tools' output),
P2_STOPPED.json (D1 'stop'), PHASES_DONE.json (after G8: the entries, the analysis-freeze record, the seal).
Outside it: outputs/framelease_v4/analysis/final_<stamp>/ (G8: the analysis-freeze record and the aggregation).

Restart and idempotence: the state is reconstructed from the files at every cycle (P1_DONE.json, Sec. 13.2 entries and
amendments, the decision file, the generated files, jobs.d, the runner's status.jsonl); an entry is never written twice
(the entry of a gate is detected, and so is the cited sha256 anywhere in Sec. 13.2), a job file is never generated,
copied or recorded twice, a written report or freeze record is never rewritten. An interrupted record transaction is
finished from protocol_txn.json. Test fault injection (PHASE_DRIVER_TEST_CRASH_AT / _TOUCH_AT) is inert in the project
tree.

ALERT: the driver writes phase_driver/ALERT.txt (gate, problem, command, full output), exits 1 and refuses to start
while the file exists. Fix the cause, move the file aside (mv ALERT.txt ALERT.<UTC>.resolved.txt), start again.

Priority: every tool runs under nice 10 / ionice best-effort 7 while no closed-loop job runs, and pinned to the E-cores
(--ecores, default 12-15) at nice 19 with one BLAS thread while one runs (a runner holds the lock of a queue of this
project, or a gpu_queue.py / CarlaUE4 process is alive): its scheduler CPU time is charged to the simulated timeline
(PROTOCOL Secs. 2.3, 11.2). The P3 and stress tools (G4, G5) run only while no closed-loop job runs, on every core
(--all-cores) at nice 10. The runner keeps the driver's nice 0.
Other editors of PROTOCOL.md hold framelease_v4/.protocol.lock for the whole amendment; while it is held elsewhere
the driver waits --lock-timeout-s (default 300 s) and retries at the next cycle (no ALERT).
Exit codes: 0 done / one cycle done / stopped / P2 stopped by D1 / dry run; 1 ALERT; 2 refused (another instance, STOP
file, niced or pinned to some CPUs, a tool outside framelease_v4/ in the project tree, setup).
"""
from __future__ import annotations

import argparse
import ast
import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import textwrap
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from framelease_v4.protocol import p1_driver as P1  # noqa: E402
from framelease_v4.protocol.p1_driver import Alert, Stop, Wait  # noqa: E402,F401  (p1_driver helpers raise these)


class AttentionWait(Wait):
    """A wait with an attention line and no ALERT, retried at the next cycle: a tool the driver is about to start still
    runs, a tool's code is not registered yet, a decision file is being written."""


VARIANT = 'FULL'
HEADING = '**Phase gates (P2-P7, FULL).**'
ANCHOR = P1.ANCHOR
GATES = ('G0', 'G1', 'G2', 'G3', 'G4', 'G5', 'G6', 'G7', 'G8')
# Sec. 13.2 entries of this driver: key -> (gate, label); the entry starts "* **<gate> <label>** (<date> <time>, ".
LABELS = {'d1_decision': ('G1', 'D1 decision'), 'p2_jobs': ('G2', 'P2 job file'),
          'p2_data': ('G3', 'P2 data manifest'), 'rl_freeze': ('G4', 'RL freeze'),
          'stress': ('G5', 'Stress tests'), 'test_freeze': ('G6', 'Test freeze'),
          'analysis_freeze': ('G8', 'Analysis freeze')}
KEY_OF = {v: k for k, v in LABELS.items()}
ENTRY_RE = re.compile(r'^\* \*\*(?P<gate>G\d) (?P<label>[^*]+)\*\* \((?P<when>\d{4}-\d{2}-\d{2} \d{2}:\d{2}), ')
AMEND_RE = re.compile(r'^\*\*Amendment (?P<id>A\d+[a-z]?)[,:.]? ')
REQUIRED_AMENDMENTS = ('A3', 'A4', 'A7', 'A9')     # the coordinating session's amendments before P2 (G0)
P1_KEYS = ('freeze', 'd1')                          # the P1 driver's entries "Tuning freeze" and "D1 summary" (G0)
# the user's instruction of 2026-11-14, quoted in translation (as Amendment A8 quotes the user), and how the
# coordinating session reads it (review fix S1: Sec. 4.8 makes D1 the user's decision)
DELEGATION = ('The user instructed on 2026-11-14 (translated): "from now on, review yourself whether to proceed to the '
              'next phase". The coordinating session reads this instruction as covering every phase gate after P1, D1 '
              'included (Sec. 4.8: "Continuing or stopping is the user\'s decision"), and takes this decision under it')
DECISIONS = ('continue', 'stop')
DECISION_GRACE_S = 120.0     # a decision file that is not readable JSON yet: a write in progress for this long (S5)
# the code of each gate's tools beyond the tool script itself (review fix M4), relative to the root; a directory
# stands for every file below it (no __pycache__): p3_rl.code_sha256 hashes framelease_v4/rl and the P2 gate sources;
# test_jobs.py and test_freeze.py check and pin the extension arm (APPLY_PLAN Sec. 2, the split "A3b")
P3_CODE = ('framelease_v4/rl',)
TEST_CODE = ('framelease_v4/protocol/check_smoke_ext.py', 'framelease_v4/arms_ext')
PROJECT_CODE = 'framelease_v4'          # the code the registration manifest covers; every tool script lies below it
A7B_RE = re.compile(r'--grid relative|supplementary S2 grid')     # Amendment A7, variant A7b (review fix S4)
EMPTY_EXIT_LIMIT = 2         # 'queue empty' exits in a row with no job started: no further relaunch (review fix S8)
STATE_SCHEMA = 'framelease_v4.phase_driver_state/1'
BASELINE_SCHEMA = 'framelease_v4.phase_driver_baseline/1'
DECISION_SCHEMA = 'framelease_v4.d1_decision/1'
STOPPED_SCHEMA = 'framelease_v4.phase_driver_p2_stopped/1'
DONE_SCHEMA = 'framelease_v4.phase_driver_done/1'
P1_DONE_SCHEMA = 'framelease_v4.p1_driver_done/1'
# framelease_v4/protocol/p2_jobs.py and p2_check.py (compared at the start, consistency_problems())
P2_BLOCK, P2_BLOCK_NO, P2_TIER = 'rl_data', 10, 2
P2_JOB_STEM = f'b{P2_BLOCK_NO:02d}_{P2_BLOCK}'
P2_STAGE_SCHEMA = 'framelease_v4.p2_stage/1'
P2_CHECK_SCHEMA = 'framelease_v4.p2_check/1'
P2_REPORT_SCHEMA = 'framelease_v4.p2_completion_check/1'
P2_MANIFEST_SCHEMA = 'framelease_v4.p2_data_manifest/1'
# framelease_v4/protocol/p3_rl.py, stress_bench.py, test_jobs.py, test_freeze.py (compared without importing them,
# consistency_problems(): their imports need numpy and the RL stack, which the long-lived driver does not load)
P3_OUT = 'outputs/framelease_v4/rl_freeze'
RL_FREEZE_SCHEMA = 'framelease_v4.rl_freeze/1'
CALIBRATION_SCHEMA = 'framelease_v4.p3_rl_calibration/1'
CAL_SIZES = (33, 66, 132)                     # p3_rl.CAL_SIZES: the production probe sizes (episodes)
CAL_OUT_ALLOWED = ('outputs/framelease_v4/build',)
OPEN_CASES = {'no_selectable': ('stop', 'adet', '(a)'), 'distill_shortfall': ('stop', 'deploy_best', '(b)'),
              'missing_episodes': ('stop', 'proceed', '(c)')}     # p3_rl.OPEN_CASES: default, alternative, item
ARM_OF = {'fqi': 'fl_full', 'bandit': 'fl_bandit', 'fqi_nolease': 'fl_fqi_nolease'}
P3_OPTIONS_SCHEMA = 'framelease_v4.p3_open_cases/1'
STRESS_SCHEMA = 'framelease_v4.stress_bench/1'
STRESS_OUT = 'outputs/framelease_v4/stress'
S1_LOADS = (0, 4, 8, 15)
S3_MIN_SEQUENCES = 100_000
SUPPLEMENTARY_LABEL = 'supplementary: S2 relative to the slack floor'
S1_BLOCKING_MARKERS = ('gpu_queue', 'CarlaUE4', 'leaderboard_evaluator', 'run_closed_loop', 'p1_driver', 'launch_queue',
                       'disk_watchdog', 'autoresume', 'framelease_v4/rl/', 'p3_rl')    # stress_bench.BLOCKING_MARKERS
FOREIGN_CPU_SAMPLE_S, FOREIGN_CPU_MIN_SHARE = 2.0, 0.05       # stress_bench.CPU_SAMPLE_S, FOREIGN_CPU_MIN_SHARE
# the four registered stress runs of G5 in their order: key -> (subcommand, test, report glob, Sec. 13.2 wording)
STRESS_RUNS = (('s3', 's3', 'S3', 's3_registered_*.json', 'S3 (cancellation and regression)'),
               ('s2', 's2', 'S2', 's2_registered_*.json', 'S2 (near deadline, registered grid)'),
               ('s2_relative', 's2', 'S2', 's2_relative_registered_*.json',
                'S2 on the supplementary grid relative to the slack floor (Amendment A7)'),
               ('s1', 's1', 'S1', 's1_registered_*.json', 'S1 (CPU contention)'))
S1_GUARD_SCHEMA = 'framelease_v4.phase_driver_s1_guard/1'
TEST_JOBS_DIR = 'outputs/framelease_v4/test_jobs'
TEST_INDEX_SCHEMA = 'framelease_v4.test_jobs_index/1'
TEST_CHECK_SCHEMA = 'framelease_v4.test_check/1'
TEST_FREEZE_DIR = 'outputs/framelease_v4/test_freeze'
TEST_FREEZE_SCHEMA = 'framelease_v4.test_freeze/1'
P4_QUEUE = 'outputs/framelease_v4/queue_p4'
P4_QUEUED_SCHEMA = 'framelease_v4.phase_driver_p4_queued/1'
# framelease_v4/analysis/aggregate_v4.py and interim_guard.py (G8; compared from the source, consistency_problems())
ANALYSIS_DIR = 'outputs/framelease_v4/analysis'      # PROTOCOL Sec. 9.12: outputs to .../analysis/final_<stamp>/
ANALYSIS_RECORD = 'analysis_freeze.json'            # the analysis-freeze record, in the final_<stamp> directory
ANALYSIS_FREEZE_SCHEMA = 'framelease_v4.analysis_freeze/1'
ANALYSIS_MODULES = ('aggregate_v4.py', 'extra_metrics.py', 'commit_audit.py', 'manipulation.py', 'interim_guard.py')
FINAL_OUTCOMES = ('ok', 'agent_crashed', 'sim_failure')
AGG_OUTPUT_FILES = ('runs.csv', 'aggregate.json', 'SHA256SUMS', 'arm_summary.csv')
AGG_RECORD_RE = re.compile(r'^analysis-freeze record (\S+): sha256 ([0-9a-f]{64}), (\d+) jobs, trigger (\S+)\.', re.M)
CRASH_ENV = 'PHASE_DRIVER_TEST_CRASH_AT'      # tests only: os._exit at a named point (fault injection)
TOUCH_ENV = 'PHASE_DRIVER_TEST_TOUCH_AT'      # tests only: '<point>:<file>' appends a line to <root>/<file> there,
#                                               '<point>:-<file>' removes <root>/<file> there
FOREIGN_ENV = 'PHASE_DRIVER_TEST_FOREIGN_CPU'  # tests only (sandbox): JSON list standing in for the foreign-CPU sample
TIMEOUTS = {'registration': 3600, 'p2_jobs': 7200, 'p2_check': 7200, 'launch': 300, 'p3_dataset': 6 * 3600,
            'p3_calibrate': 12 * 3600, 'p3_run': 96 * 3600, 'p3_status': 3600, 'stress': 24 * 3600,
            'test_jobs': 12 * 3600, 'test_freeze': 4 * 3600, 'aggregate': 12 * 3600}
# free disk to launch a runner: P2 alone (outputs/framelease_v4/p2_jobs/README.md, precondition 4); queue_p4 holds the
# rest of the plan, tiers 3-6 (PROTOCOL Sec. 10.1, "free disk needed at phase start, rest of the plan", P4: 11.9 GiB)
MIN_FREE_GIB = {'queue_p2': 7.3, 'queue_p4': 11.9}
DISK_ATTENTION_GIB = 10.0                     # attention below this while a phase runs
CLOSED_LOOP_MARKERS = ('gpu_queue.py', 'CarlaUE4')
P3_MEMORY_SHARE = 0.75                        # p3_rl run: n_jobs x the probe's peak RSS <= this share of MemAvailable
STOP_GRACE_S = 60                             # a long tool gets this long after SIGTERM before SIGKILL
SHA_RE = P1.SHA_RE


# ---------------------------------------------------------------------------------------------------- small helpers

def entry_stamp():
    """'YYYY-MM-DD HH:MM, Beijing time' (the machine runs at +0800)."""
    zone = 'Beijing time' if time.strftime('%z') == '+0800' else f'UTC{time.strftime("%z")}'
    return f'{time.strftime("%Y-%m-%d %H:%M")}, {zone}'


def entry_head(key):
    """The bold start of the entry of `key`: '**G1 D1 decision** (2026-11-15 10:00, Beijing time).'"""
    gate, label = LABELS[key]
    return f'**{gate} {label}** ({entry_stamp()}).'


def label_of(key):
    gate, label = LABELS.get(key, ('?', key))
    return f'{gate} {label}'


def one_line(text, limit=4000):
    """Free text (a rationale, a cause) as one line for an entry: whitespace collapsed, at most `limit` characters."""
    s = ' '.join(str(text or '').split())
    return s if len(s) <= limit else s[:limit - 3] + '...'


def sentence(text):
    s = one_line(text)
    return s if s.endswith(('.', '!', '?')) else s + '.'


def crash_point(ctx, name):
    """Test fault injection; inert unless --root is a sandbox (not the tree this script lives in)."""
    if ctx.cfg.root == ROOT:
        return
    point, _, rel = os.environ.get(TOUCH_ENV, '').partition(':')
    if point == name and rel.startswith('-'):
        (ctx.cfg.root / rel[1:]).unlink()
    elif point == name and rel:
        with open(ctx.cfg.root / rel, 'a', encoding='utf-8') as f:
            f.write(f'# changed by the test hook at {name}\n')
    if os.environ.get(CRASH_ENV) == name:
        ctx.log(f'TEST fault injection: exiting at {name}')
        os._exit(70)


def runner_pid_alive(q):
    """The pid that <queue>/runner.lock names is alive and runs gpu_queue.py on this queue (read only: no lock is
    probed, so a runner that starts at this instant is never disturbed)."""
    try:
        holder = (q.queue / 'runner.lock').read_text(errors='replace')
    except OSError:
        return False
    m = re.match(r'pid (\d+)', holder.strip())
    cmd = P1.pid_cmdline(m.group(1)) if m else ''
    return 'gpu_queue.py' in cmd and str(q.queue) in cmd


def free_gib(path):
    try:
        return shutil.disk_usage(path).free / 2 ** 30
    except OSError:
        return None


def mem_available_mib():
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemAvailable:'):
                return int(line.split()[1]) / 1024.0
    except (OSError, ValueError, IndexError):
        pass
    return None


def tool_pids(script):
    """Live processes (other than this one) whose command line names `script`: a tool left running by an earlier
    driver process (the tools run in their own session, so they outlive a killed driver), or one started by hand. A
    phase driver is never counted (its command line may name the tool scripts as options)."""
    me, out = os.getpid(), []
    for d in Path('/proc').iterdir():
        if d.name.isdigit() and int(d.name) != me:
            cmd = P1.pid_cmdline(d.name)
            if str(script) in cmd and 'python' in cmd and 'phase_driver.py' not in cmd:
                out.append(int(d.name))
    return sorted(out)


def wait_for_tools(ctx, *scripts):
    """Review fix M2: the driver starts a tool, or reads what a tool writes, only while no process runs that tool. A
    tool left by a killed driver process still runs in its own session; starting it again would run a registered step
    twice or let two processes write the same outputs. Raises AttentionWait (attention, no ALERT) while one runs; the
    gate is retried at the next cycle."""
    busy = [f'{Path(s).name} (pids {pids})' for s in scripts for pids in [tool_pids(s)] if pids]
    if busy:
        msg = (f'{", ".join(busy)} still running (left by an earlier driver process, or started by hand): the driver '
               'goes on after it ends')
        ctx.add_attention(msg)
        raise AttentionWait(msg)


def _cpu_ticks():
    out = {}
    for d in Path('/proc').iterdir():
        if not d.name.isdigit():
            continue
        try:
            s = (d / 'stat').read_text(encoding='utf-8', errors='replace')
            i = s.rindex(')')
            f = s[i + 2:].split()
            out[int(d.name)] = (int(f[11]) + int(f[12]), int(f[1]), s[s.index('(') + 1:i])
        except (OSError, ValueError, IndexError):
            continue
    return out


def foreign_cpu(cfg, sample_s=FOREIGN_CPU_SAMPLE_S, min_share=FOREIGN_CPU_MIN_SHARE):
    """Processes other than this driver and its children that used >= min_share of one core over sample_s seconds
    (/proc utime + stime; stress_bench.foreign_cpu's rule): desktop or other load that would make a registered S1
    refuse. In a test sandbox the sample is PHASE_DRIVER_TEST_FOREIGN_CPU (a JSON list; empty when unset)."""
    if cfg.root != ROOT:
        try:
            return list(json.loads(os.environ.get(FOREIGN_ENV) or '[]'))
        except ValueError:
            return []
    me = os.getpid()
    hz = float(os.sysconf('SC_CLK_TCK'))
    t0 = time.monotonic()
    a = _cpu_ticks()
    time.sleep(sample_s)
    b = _cpu_ticks()
    dt = max(time.monotonic() - t0, float(sample_s))
    out = []
    for pid, (ticks, ppid, comm) in b.items():
        if pid == me or ppid == me or pid not in a:
            continue
        share = (ticks - a[pid][0]) / hz / dt
        if share >= min_share:
            out.append({'pid': pid, 'cpu_share': round(share, 4), 'comm': comm,
                        'cmdline': (P1.pid_cmdline(pid).strip() or f'[{comm}]')[:200]})
    return sorted(out, key=lambda r: -r['cpu_share'])


def open_case_of(err):
    """(case key, the tool's STOP line) of a p3_rl.py exit 4 (an open case of GAP_AUDIT Sec. 6 item 5), from the
    option its message names ('rerun with --no-selectable adet'); (None, line) when no option is named."""
    line = next((ln.strip() for ln in err.splitlines() if ln.startswith('STOP (open case')), err.strip()[-600:])
    m = re.search(r'rerun with --([a-z-]+) ([a-z_]+)', err)
    case = m.group(1).replace('-', '_') if m else None
    return (case if case in OPEN_CASES else None), line


def run_long(ctx, cmd, timeout, name, prefix=(), env_extra=None, terminate_on_stop=True):
    """Run a long tool: (exit code or None after the timeout, stdout tail, stderr tail, log stem). Its own session;
    stdout / stderr go to phase_driver/logs/<name>.<time>.{out,err} (a file survives a killed driver, a pipe would not).
    While it runs, a STOP file or a signal terminates its process group (SIGTERM, then SIGKILL after STOP_GRACE_S; the
    G4-G5 tools resume or rerun from scratch) and raises Stop; with terminate_on_stop False the stop waits for the
    tool (a writer whose files are not atomic)."""
    cfg = ctx.cfg
    full = list(prefix) + list(cmd)
    env = dict(os.environ)
    env.update(env_extra or {})
    logs = cfg.driver_dir / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    stem = logs / f'{name}.{time.strftime("%Y%m%dT%H%M%S")}'
    out_p, err_p = Path(f'{stem}.out'), Path(f'{stem}.err')
    t0 = time.monotonic()
    with open(out_p, 'w', encoding='utf-8') as fo, open(err_p, 'w', encoding='utf-8') as fe:
        try:
            p = subprocess.Popen(full, cwd=cfg.root, stdout=fo, stderr=fe, stdin=subprocess.DEVNULL, env=env,
                                 start_new_session=True)
        except OSError as e:
            ctx.log(f'cannot start {P1.show(full)}: {e}')
            return None, '', f'cannot start {full[0]}: {e}', cfg.rel(stem)
        ctx.state['tool'] = {'name': name, 'pid': p.pid, 'started': P1.now_iso(), 'cmd': P1.show(full),
                             'log': cfg.rel(stem) + '.{out,err}'}
        ctx.save()
        ctx.log(f'started pid {p.pid}: {P1.show(full)} (log {cfg.rel(stem)}.out / .err)')
        stopped = timed_out = False
        while p.poll() is None:
            time.sleep(1.0)
            if time.monotonic() - t0 > timeout:
                timed_out = True
            elif terminate_on_stop and (ctx.stop or cfg.stop_path.exists()):
                stopped = True
            if timed_out or stopped:
                for sig, wait_s in ((signal.SIGTERM, STOP_GRACE_S), (signal.SIGKILL, 15)):
                    try:
                        os.killpg(p.pid, sig)
                    except OSError:
                        pass
                    try:
                        p.wait(timeout=wait_s)
                        break
                    except subprocess.TimeoutExpired:
                        continue
                break
    ctx.state['tool'] = None
    rc = None if timed_out else p.returncode
    out = out_p.read_text(encoding='utf-8', errors='replace')
    err = err_p.read_text(encoding='utf-8', errors='replace')
    ctx.log(f'ran ({time.monotonic() - t0:.1f} s, exit {rc}{", stopped" if stopped else ""}): {P1.show(full)}')
    if stopped:
        raise Stop()
    if timed_out:
        err += f'\n[phase_driver] killed after the {timeout} s timeout'
    return rc, out[-60000:], err[-60000:], cfg.rel(stem)


LINE_START = re.compile(r'^(>|(\d+[.)]|[-*+#|=])(\s|$))')    # p1_driver.LIST_START, and '>' in any form (block quote)


def wrap_bullet(text):
    """p1_driver.wrap_entry with LINE_START: a Markdown bullet at 120 columns whose continuation lines never start a
    list, a heading or a block quote (a line starting '>= D*' would render as a quote)."""
    for width in range(120, 96, -1):
        lines = textwrap.wrap(text, width=width, initial_indent='* ', subsequent_indent='  ', break_long_words=False,
                              break_on_hyphens=False)
        if all(not LINE_START.match(ln[2:]) for ln in lines[1:]):
            return lines
    return ['* ' + ' '.join(text.split())]


def nest_entry_lines(lines):
    """The Sec. 13.2 entry a tool printed (a bold head paragraph, then '* ' bullets with '  ' continuation lines, 120
    columns) as a nested block of this driver's bullet: the head paragraph indented by two spaces, every bullet a
    nested '  * ' item with '    ' continuation lines, re-wrapped to 120 columns; no word changes and no sha256 is
    split (Sec. 13.2 citations are found per line). Returns (nested lines, the paragraphs as printed); ValueError for
    another form."""
    paras, head = [], []
    for ln in lines:
        if not ln.strip():
            raise ValueError('a blank line inside the printed entry')
        if ln.startswith('* '):
            paras.append(['bullet', ln[2:]])
        elif paras and ln.startswith('  '):
            paras[-1][1] += ' ' + ln.strip()
        elif not paras and not ln.startswith(' '):
            head.append(ln.strip())
        else:
            raise ValueError(f'unexpected line in the printed entry: {ln[:80]!r}')
    if not head:
        raise ValueError('the printed entry has no head paragraph')
    paras = [['head', ' '.join(head)]] + paras
    out = []
    for kind, text in paras:
        first, rest = ('  ', '  ') if kind == 'head' else ('  * ', '    ')
        for width in range(120, 96, -1):
            wrapped = textwrap.wrap(text, width=width, initial_indent=first, subsequent_indent=rest,
                                    break_long_words=False, break_on_hyphens=False)
            if all(not LINE_START.match(w[len(rest):]) for w in wrapped[1:]) \
                    and (kind == 'bullet' or not LINE_START.match(wrapped[0][2:])):
                break
        else:
            raise ValueError(f'cannot wrap a paragraph of the printed entry without a list-like line: {text[:80]!r}')
        if any(len(w) > 120 for w in wrapped):
            raise ValueError(f'a word longer than the 120 columns in the printed entry: {text[:80]!r}')
        out += wrapped
    return out, [' '.join(t.split()) for _, t in paras]


# ---------------------------------------------------------------------------------------------------- configuration

class QueueCfg:
    """A gpu_queue directory as p1_driver.queue_status() / runner_lock_held() read it (queue, queue_arg, jobs_d)."""

    def __init__(self, cfg, path):
        self.queue = cfg.path(path)
        self.queue_arg = cfg.rel(self.queue)
        self.jobs_d = self.queue / 'jobs.d'
        self.name = self.queue.name                                  # e.g. queue_p2
        self.short = self.name[len('queue_'):] if self.name.startswith('queue_') else self.name   # e.g. p2


class Cfg:
    def __init__(self, a):
        self.root = Path(a.root).resolve()
        self.protocol = self.path(a.protocol)
        self.protocol_lock = self.path(a.protocol_lock)
        self.reg_dir = self.path(a.registration_dir)
        self.manifest = self.reg_dir / 'MANIFEST.sha256'
        self.seal = self.reg_dir / 'SEAL.sha256'
        self.jobs_dir = self.path(a.p1_jobs_dir)            # P1 job files: always registered (p1_driver.is_strict)
        self.p1_dir = self.path(a.p1_driver_dir)
        self.freeze_path = self.path(a.freeze_path)
        self.d1_dir = self.path(a.d1_dir)
        self.p2_jobs_dir = self.path(a.p2_jobs_dir)
        self.p2_queue = QueueCfg(self, a.p2_queue)
        self.rl_data_dir = self.path(a.rl_data_dir)
        self.rl_freeze_dir = self.path(a.rl_freeze_dir)
        self.rl_freeze_path = self.rl_freeze_dir / 'rl_freeze.json'
        self.p3_calibration = self.path(a.p3_calibration)
        self.stress_dir = self.path(a.stress_dir)
        self.test_jobs_dir = self.path(a.test_jobs_dir)
        self.test_freeze_dir = self.path(a.test_freeze_dir)
        self.p4_queue = QueueCfg(self, a.p4_queue)
        self.analysis_dir = self.path(a.analysis_dir)
        self.analyze_code = self.path(a.analyze_code)
        self.driver_dir = self.path(a.driver_dir)
        self.python = str(a.python)
        self.registration_script = str(a.registration_script)
        self.p2_jobs_script = str(a.p2_jobs_script)
        self.p2_check_script = str(a.p2_check_script)
        self.p3_rl_script = str(a.p3_rl_script)
        self.stress_script = str(a.stress_script)
        self.test_jobs_script = str(a.test_jobs_script)
        self.test_freeze_script = str(a.test_freeze_script)
        self.aggregate_script = str(a.aggregate_script)
        self.launch_script = str(a.launch_script)
        self.all_cores = str(a.all_cores)
        self.stress_states = str(a.stress_states)
        self.s1_retries = int(a.s1_retries)
        self.s1_retry_s = float(a.s1_retry_s)
        self.env_script = str(a.env_script)
        self.systemd_run = str(a.systemd_run)
        self.interval_s = float(a.interval_s)
        self.lock_timeout_s = float(a.lock_timeout_s)
        self.dry_run = bool(a.dry_run)
        self.once = bool(a.once)
        self.json_out = bool(getattr(a, 'json', False))
        self.check_consistency = not a.no_consistency_check
        self.normal_priority = bool(a.normal_priority)
        self.allow_nice_launch = bool(a.allow_nice_launch)
        self.ecores = str(a.ecores)
        self.watch_queues = [QueueCfg(self, q) for q in a.watch_queues.split(',') if q.strip()]
        self.required_amendments = tuple(x.strip() for x in a.require_amendments.split(',') if x.strip())
        d = self.driver_dir
        self.alert_path, self.log_path, self.state_path = d / 'ALERT.txt', d / 'driver.log', d / 'state.json'
        self.txn_path, self.stop_path, self.lock_path = d / 'protocol_txn.json', d / 'STOP', d / 'driver.lock'
        self.pid_path, self.sealed_copy = d / 'driver.pid', d / 'manifest_sealed.sha256'
        self.baseline_path = d / 'registered_baseline.json'
        self.decision_path, self.missing_ack_path = d / 'D1_DECISION.json', d / 'P2_MISSING_ACK.txt'
        self.stopped_path, self.done_path = d / 'P2_STOPPED.json', d / 'PHASES_DONE.json'
        self.p3_options_path, self.s1_guard_path = d / 'P3_OPEN_CASES.json', d / 's1_guard.json'
        self.s1_accept_path, self.p4_queued_path = d / 'S1_ACCEPT_FOREIGN_CPU.txt', d / 'P4_QUEUED.json'
        p = self.p1_dir
        self.p1_done, self.p1_baseline, self.p1_txn = p / 'P1_DONE.json', p / 'registered_baseline.json', \
            p / 'protocol_txn.json'
        self.p1_lock = p / 'driver.lock'

    def path(self, p):
        p = Path(p)
        return p if p.is_absolute() else self.root / p

    def rel(self, p):
        p = Path(p)
        try:
            return str(p.relative_to(self.root))
        except ValueError:
            return str(p)

    # paths of the generated files
    def d1_paths(self):
        return self.d1_dir / f'{VARIANT}_d1_summary.json', self.d1_dir / f'{VARIANT}_d1_summary.md'

    def p2_paths(self):
        base = self.p2_jobs_dir / VARIANT / P2_JOB_STEM
        return Path(str(base) + '.jsonl'), Path(str(base) + '.stage.json'), Path(str(base) + '.check.json')

    def p2_outputs(self):
        return self.rl_data_dir / 'p2_check.json', self.rl_data_dir / 'data_manifest.json'

    def test_index_path(self):
        return self.test_jobs_dir / VARIANT / 'index.json'

    def test_freeze_paths(self):
        return self.test_freeze_dir / 'test_freeze.json', self.test_freeze_dir / 'MANIFEST.sha256'

    # priority of the tools (p1_driver.run_cmd prefixes ctx.cfg.low_prio)
    def closed_loop_active(self):
        """True while a closed-loop job may run: the runner named in a watched queue's runner.lock is alive, or (in the
        project tree only, never in a test sandbox) a gpu_queue.py / CarlaUE4 process is alive. No lock is probed."""
        if any(runner_pid_alive(q) for q in self.watch_queues):
            return True
        if self.root != ROOT:
            return False
        for d in Path('/proc').iterdir():
            if d.name.isdigit() and int(d.name) != os.getpid():
                cmd = P1.pid_cmdline(d.name)
                if any(m in cmd for m in CLOSED_LOOP_MARKERS):
                    return True
        return False

    @property
    def low_prio(self):
        if self.normal_priority:
            return []
        if self.closed_loop_active():
            return ['taskset', '-c', self.ecores, 'nice', '-n', '19', 'ionice', '-c2', '-n7']
        return ['nice', '-n', '10', 'ionice', '-c2', '-n7']

    @property
    def heavy_prio(self):
        """The P3 and stress tools (G4, G5), which run only while no closed-loop job runs: every core (--all-cores,
        default 0-15) at nice 10 / ionice best-effort 7."""
        if self.normal_priority:
            return []
        return ['taskset', '-c', self.all_cores, 'nice', '-n', '10', 'ionice', '-c2', '-n7']

    def tool_env(self):
        """Environment additions of a tool: CUDA hidden; one BLAS thread while a closed-loop job runs."""
        env = {'CUDA_VISIBLE_DEVICES': ''}
        if self.closed_loop_active():
            env.update(OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
        return env

    # commands (run from the project root)
    def reg_cmd(self, *flags):
        return [self.python, '-I', '-B', self.registration_script, *flags]

    def p2_jobs_cmd(self):
        script = ('source "$1" && CUDA_VISIBLE_DEVICES= exec "$2" -I -B "$3" --check --write --jobs-dir "$4"')
        return ['bash', '-c', script, 'phase_driver', self.env_script, self.python, self.p2_jobs_script,
                self.rel(self.p2_jobs_dir)]

    def p2_check_cmd(self, write):
        report, manifest = self.p2_outputs()
        cmd = [self.python, '-I', '-B', self.p2_check_script, '--queue', self.p2_queue.queue_arg, '--job-file',
               self.rel(self.p2_paths()[0]), '--report', self.rel(report), '--manifest', self.rel(manifest)]
        return cmd + (['--write'] if write else [])

    def p3_cmd(self, sub, *args):
        """p3_rl.py run / calibrate / status (the production paths named explicitly)."""
        if sub == 'run':
            report, manifest = self.p2_outputs()
            args = ('--manifest', self.rel(manifest), '--selection', self.rel(self.freeze_path), '--out',
                    self.rel(self.rl_freeze_dir), *args)
        elif sub == 'status':
            args = ('--out', self.rel(self.rl_freeze_dir), *args)
        return [self.python, '-I', '-B', self.p3_rl_script, sub, *args]

    def stress_cmd(self, key, qnets=(), envelope=None, accept_foreign=False):
        """stress_bench.py <test> --registered for the G5 run `key` (STRESS_RUNS)."""
        sub = {k: s for k, s, *_ in STRESS_RUNS}[key]
        cmd = [self.python, '-I', '-B', self.stress_script, sub, '--registered']
        if key != 's3':
            cmd += ['--states', self.stress_states] + [x for q in qnets for x in ('--qnet', q)]
        if key in ('s2', 's2_relative'):
            cmd += ['--grid', 'relative' if key == 's2_relative' else 'registered']
        if key == 's1':
            cmd += ['--envelope', envelope] + (['--accept-foreign-cpu'] if accept_foreign else [])
        return cmd

    def test_jobs_cmd(self):
        script = 'source "$1" && CUDA_VISIBLE_DEVICES= exec "$2" -I -B "$3" --check --write --jobs-dir "$4"'
        return ['bash', '-c', script, 'phase_driver', self.env_script, self.python, self.test_jobs_script,
                self.rel(self.test_jobs_dir)]

    def test_freeze_cmd(self, flag):
        return [self.python, '-I', '-B', self.test_freeze_script, flag, '--jobs-dir', self.rel(self.test_jobs_dir),
                '--rl-freeze', self.rel(self.rl_freeze_path), '--selection', self.rel(self.freeze_path),
                '--stress-dir', self.rel(self.stress_dir), '--out-dir', self.rel(self.test_freeze_dir),
                '--queue-dir', self.rel(self.p4_queue.jobs_d)]

    def aggregate_cmd(self, out_dir, record, force=False):
        """aggregate_v4.py --write-freeze-record over the P4-P6 queue (G8). Never --arm-summary (a cross-arm summary)
        and never --analysis-freeze: the aggregation that makes the record keeps every test-route row health-only
        (PROTOCOL Sec. 9.11)."""
        return [self.python, '-I', '-B', self.aggregate_script, '--queue', self.p4_queue.queue_arg, '--specs',
                self.rel(self.test_jobs_dir / VARIANT), '--rl-freeze', self.rel(self.rl_freeze_path),
                '--tuning-freeze', self.rel(self.freeze_path), '--write-freeze-record', self.rel(record), '--out',
                self.rel(out_dir)] + (['--force'] if force else [])

    def launch_cmd(self, q, ts=None):
        ts = ts or time.strftime('%Y%m%dT%H%M%S')
        return [self.systemd_run, '--user', '--scope', f'--unit=framelease-{q.short}-runner-{ts}', '-p',
                'OOMPolicy=continue', 'bash', self.launch_script, q.queue_arg]


# ---------------------------------------------------------------------------------------------------- context / state

def _blank_gate(gate):
    return {'status': 'unknown', 'note': None, 'entry': None, 'files': {}, 'times': {}}


class Ctx:
    """The cycle's context: configuration, plan (dry run), attention list and state.json (p1_driver.Ctx's interface:
    cfg, log, add_plan, add_attention, stop, lock_busy, save)."""

    def __init__(self, cfg, prev_state=None, echo=False):
        self.cfg = cfg
        self.echo = echo
        self.plan = []
        self.attention = []
        self.lock_busy = False
        self.stop = False
        self.cycle = 0
        self.verified = {}              # (PROTOCOL.md, MANIFEST.sha256 sha256) -> G0 seal verification (per process)
        prev = prev_state if isinstance(prev_state, dict) and prev_state.get('schema') == STATE_SCHEMA else {}
        gates = {g: _blank_gate(g) for g in GATES}
        for g in GATES:
            old = (prev.get('gates') or {}).get(g) or {}
            if old.get('times'):
                gates[g]['times'] = dict(old['times'])
        self.state = {'schema': STATE_SCHEMA, 'variant': VARIANT, 'updated': None,
                      'driver': {'pid': os.getpid(), 'started': P1.now_iso(),
                                 'mode': 'dry-run' if cfg.dry_run else 'run', 'interval_s': cfg.interval_s, 'cycle': 0,
                                 'status': 'starting', 'script': str(Path(__file__).resolve())},
                      'gates': gates, 'current_gate': None, 'queue': None, 'registration': None,
                      'registered_baseline': None, 'priority': None, 'attention': [], 'alert': None,
                      'files': {'log': cfg.rel(cfg.log_path), 'alert': cfg.rel(cfg.alert_path),
                                'decision': cfg.rel(cfg.decision_path), 'txn': cfg.rel(cfg.txn_path),
                                'p2_stopped': cfg.rel(cfg.stopped_path), 'done': cfg.rel(cfg.done_path)}}

    def gate(self, g):
        return self.state['gates'][g]

    def log(self, msg):
        line = f'{P1.now_iso()} {msg}'
        if self.cfg.dry_run:
            print(f'  {msg}', flush=True)
            return
        self.cfg.driver_dir.mkdir(parents=True, exist_ok=True)
        with open(self.cfg.log_path, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
        if self.echo:
            print(line, flush=True)

    def add_plan(self, msg):
        self.plan.append(msg)
        if self.cfg.dry_run:
            print(f'  WOULD: {msg}', flush=True)

    def add_attention(self, msg):
        if msg not in self.attention:
            self.attention.append(msg)
            self.log(f'ATTENTION: {msg}')

    def save(self):
        self.state['updated'] = P1.now_iso()
        self.state['driver']['cycle'] = self.cycle
        self.state['attention'] = list(self.attention)
        if self.cfg.dry_run:
            return
        self.cfg.state_path.parent.mkdir(parents=True, exist_ok=True)
        P1.atomic_write(self.cfg.state_path, json.dumps(self.state, indent=1, sort_keys=True, default=str) + '\n')


# ---------------------------------------------------------------------------------------------------- PROTOCOL.md

def phase_view(cfg, text=None):
    """Sec. 13.2 of PROTOCOL.md: p1_driver.protocol_view() (bounds, anchor, the P1 driver's heading and entries; ALERT
    on a broken structure) plus this driver's heading and entries and the amendment titles ('**Amendment A<n>, ...').
    Keys: 'entries' / 'heading' are this driver's, 'p1_entries' / 'p1_heading' the P1 driver's."""
    if text is None:
        text = cfg.protocol.read_text(encoding='utf-8')
    pv = P1.protocol_view(cfg, text)
    lines = pv['lines']
    s, e = pv['sec']
    heads = [i for i in range(s, e) if lines[i].strip() == HEADING]
    if len(heads) > 1:
        raise Alert('PROTOCOL.md', f'the heading {HEADING} occurs {len(heads)} times in Sec. 13.2')
    head = heads[0] if heads else None
    if head is not None and head > pv['anchor']:
        raise Alert('PROTOCOL.md', f'the heading {HEADING} (line {head + 1}) stands after the paragraph "{ANCHOR}"')
    if head is not None and pv['heading'] is not None and head < pv['heading']:
        raise Alert('PROTOCOL.md', f'the heading {HEADING} (line {head + 1}) stands before the P1 driver\'s heading '
                                   f'{P1.HEADING} (line {pv["heading"] + 1})')
    entries, amendments = {}, {}
    for i in range(s, e):
        m = AMEND_RE.match(lines[i])
        if m:
            amendments.setdefault(m.group('id'), []).append(i + 1)
        m = ENTRY_RE.match(lines[i])
        if not m or (m.group('gate'), m.group('label')) not in KEY_OF:
            continue
        j = i + 1
        while j < e and lines[j].startswith('  ') and lines[j].strip():
            j += 1
        body = '\n'.join(lines[i:j])
        key = KEY_OF[(m.group('gate'), m.group('label'))]
        if key in entries:
            raise Alert('PROTOCOL.md', f'two Sec. 13.2 entries for {label_of(key)} (lines {entries[key]["line"]} and '
                                       f'{i + 1})')
        entries[key] = {'line': i + 1, 'when': m.group('when'), 'shas': SHA_RE.findall(body), 'text': body}
    sec_text = '\n'.join(lines[s:e])
    return {'text': text, 'lines': lines, 'sec': (s, e), 'sec_text': sec_text, 'anchor': pv['anchor'],
            'heading': head, 'entries': entries, 'p1_heading': pv['heading'], 'p1_entries': pv['entries'],
            'amendments': amendments}


def insert_entry(cfg, text, entry_lines):
    """PROTOCOL.md text with the entry appended to this driver's subsection; the subsection is created just before the
    anchor paragraph (after the P1 driver's block and after every amendment entered so far)."""
    view = phase_view(cfg, text)
    lines = list(view['lines'])
    if view['heading'] is None:
        a = view['anchor']
        block = [HEADING] + list(entry_lines) + ['']
        if a > 0 and lines[a - 1].strip():
            block = [''] + block
        lines[a:a] = block
    else:
        i = view['heading'] + 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(ANCHOR):
            i += 1
        lines[i:i] = list(entry_lines) + ([''] if i < len(lines) and lines[i].startswith(ANCHOR) else [])
    return '\n'.join(lines)


def own_manifest_shas(view):
    """sha256 of the manifests sealed with this driver's own entries (their manifest clause)."""
    shas = set()
    for ent in view['entries'].values():
        m = P1.MANIFEST_CLAUSE_RE.search(' '.join(ent['text'].split()))
        if m:
            shas.add(m.group(1))
    return shas


def manifest_clause(cfg, m_new, n_files, added, changed=()):
    """p1_driver.manifest_clause (the form p1_driver.MANIFEST_CLAUSE_RE reads) naming this driver's log."""
    text = P1.manifest_clause(m_new, n_files, added, changed)
    return text.replace('outputs/framelease_v4/p1_driver/driver.log', cfg.rel(cfg.log_path))


# ---------------------------------------------------------------------------------------------------- registered files

def _baseline_doc(path):
    doc = P1.read_json(path)
    return doc if isinstance(doc, dict) and isinstance(doc.get('files'), dict) else None


def refresh_baseline(cfg, ctx, view, reg, sealed_text):
    """{path: sha256} of the REGISTERED files, kept in phase_driver/registered_baseline.json; sealed_text is the sealed
    manifest (the caller checked its sha256). p1_driver.refresh_baseline's rules, seeded from the P1 driver's baseline:
      * no own baseline yet: the seed is p1_driver/registered_baseline.json (read, never written), else (no P1 driver
        baseline either) the sealed manifest as a whole;
      * every new seal keeps every baseline file, with its newly sealed sha256, and adds a file of its manifest only if
        Sec. 13.2 or any other part of PROTOCOL.md cites that file's sha256 (an amendment that registers it, e.g. A3).
    A seal is identified by the pair (sealed PROTOCOL.md sha256, sealed manifest sha256), never by the manifest alone
    (review fix M1): PROTOCOL.md is not in the manifest (registration.EXCLUDE_V4), so an amendment that only cites
    files already in the manifest (A3, a split A3b, A4, the registration of the analysis code) re-seals with the
    manifest sha256 of the driver's last entry. The baseline is therefore recomputed at the driver's own seals too,
    which is safe: an own seal changes no registered file (the pre-check and the post-manifest checks of
    ensure_recorded), so it adds only files whose sha256 PROTOCOL.md cites. Never written in a dry run."""
    base = _baseline_doc(cfg.baseline_path)
    seeded = None
    if base is None:
        seed = _baseline_doc(cfg.p1_baseline)
        if seed is not None:
            base, seeded = {'files': seed['files'], 'manifest_sha256': seed.get('manifest_sha256')}, \
                cfg.rel(cfg.p1_baseline)
    sealed = P1.parse_manifest_text(sealed_text)
    seal = (reg['seal_protocol'], reg['seal_manifest'])
    if seeded is None and base is not None and (base.get('protocol_sha256'), base.get('manifest_sha256')) == seal:
        return base['files']
    if base is None and reg['seal_manifest'] in own_manifest_shas(view):
        ctx.add_attention(f'{cfg.rel(cfg.baseline_path)} is missing while the seal is the driver\'s own: every file of '
                          'the sealed manifest is treated as registered')
        return sealed
    if base is None:
        files, how = dict(sealed), 'first baseline: the sealed manifest (no P1 driver baseline found)'
    else:
        old = base['files']
        files = {p: s for p, s in sealed.items() if p in old or s in view['text']}
        how = (f'seal (PROTOCOL.md {reg["seal_protocol"]}, manifest {reg["seal_manifest"]}): {len(files)} registered '
               f'files, {len([p for p in files if p not in old])} newly registered (sha256 cited in PROTOCOL.md), '
               f'{len([p for p in sealed if p not in files])} manifest files not registered'
               + (f'; seeded from {seeded} (manifest {base.get("manifest_sha256")})' if seeded else ''))
    if cfg.dry_run:
        return files
    cfg.driver_dir.mkdir(parents=True, exist_ok=True)
    P1.atomic_write(cfg.baseline_path, json.dumps({'schema': BASELINE_SCHEMA, 'updated': P1.now_iso(),
                                                   'manifest_sha256': reg['seal_manifest'],
                                                   'protocol_sha256': reg['seal_protocol'], 'how': how,
                                                   'seeded_from': seeded or (base or {}).get('seeded_from'),
                                                   'previous_protocol_sha256': (base or {}).get('protocol_sha256'),
                                                   'previous_manifest_sha256': (base or {}).get('manifest_sha256'),
                                                   'files': files}, indent=1, sort_keys=True) + '\n')
    ctx.log(f'registered baseline {cfg.rel(cfg.baseline_path)}: {how} ({len(files)} files)')
    return files


def sealed_baseline(cfg, ctx):
    """refresh_baseline() from the current files when the seal matches PROTOCOL.md and MANIFEST.sha256 (a consistent
    snapshot); else the saved baseline (the P1 driver's when this driver has none; None if neither exists)."""
    reg = P1.registration_view(cfg)
    if reg['seal_ok']:
        text = cfg.manifest.read_text(encoding='utf-8')
        if P1.sha256_text(text) == reg['seal_manifest']:
            return refresh_baseline(cfg, ctx, phase_view(cfg), reg, text)
    base = _baseline_doc(cfg.baseline_path) or _baseline_doc(cfg.p1_baseline)
    return base['files'] if base else None


def baseline_summary(cfg, files):
    base = P1.read_json(cfg.baseline_path)
    base = base if isinstance(base, dict) else {}
    return {'file': cfg.rel(cfg.baseline_path), 'saved': cfg.baseline_path.is_file(),
            'registered_files': None if files is None else len(files),
            'from_manifest_sha256': base.get('manifest_sha256'), 'seeded_from': base.get('seeded_from'),
            'updated': base.get('updated')}


# ------------------------------------------------------------------------------------------------ record transaction

def strict_map(cfg, baseline):
    """The baseline for p1_driver.is_strict / precheck_tree / run_verify (P1 job files count through cfg.jobs_dir)."""
    return dict(baseline or {})


def finish_open_txn(cfg, ctx):
    """Finish a record transaction that an earlier run left open (call with the protocol lock held); p1_driver's
    finish_open_txn with this driver's transaction file and baseline."""
    txn = P1.read_txn(cfg)
    if not txn:
        return
    reg = P1.registration_view(cfg)
    step = txn.get('step')
    what = f'interrupted record of {label_of(txn["key"])} (step {step})'
    if step in ('protocol', 'sealed'):
        if reg['protocol_sha256'] == txn.get('protocol_after'):
            if not reg['seal_ok']:
                if reg['manifest_sha256'] != txn.get('manifest'):
                    raise Alert('registration', f'{what}: PROTOCOL.md holds the entry but MANIFEST.sha256 is not the '
                                                'manifest the entry cites; re-seal by hand after checking')
                P1.run_seal(cfg, ctx, txn['protocol_after'], txn['manifest'])
            P1.run_verify(cfg, ctx, strict_map(cfg, sealed_baseline(cfg, ctx)))
            P1.clear_txn(cfg)
            ctx.log(f'finished the {what}: sealed and verified')
            return
        if reg['protocol_sha256'] == txn.get('protocol_before'):
            P1.write_txn(cfg, {**txn, 'step': 'manifest'})
            ctx.log(f'{what}: PROTOCOL.md was not replaced; the entry is written again')
            return
        if reg['seal_ok']:
            P1.clear_txn(cfg)
            ctx.log(f'{what}: superseded by a sealed PROTOCOL.md; the transaction is closed')
            return
        raise Alert('registration', f'{what}: PROTOCOL.md is neither the version before nor the version after the '
                                    "driver's edit, and SEAL.sha256 does not match it")
    if reg['seal_ok']:
        P1.clear_txn(cfg)
        ctx.log(f'{what}: nothing was written to PROTOCOL.md and the seal matches; the transaction is closed')


def ensure_open_txn_finished(cfg, ctx):
    txn = P1.read_txn(cfg)
    if not txn:
        return
    if cfg.dry_run:
        ctx.add_plan(f'finish the interrupted record of {label_of(txn["key"])} (step {txn.get("step")}) under the '
                     'protocol lock (seal, verify)')
        return
    wait_for_tools(ctx, cfg.registration_script)        # a registration.py of the interrupted record may still run
    with P1.ProtocolLock(cfg, ctx) as lock:
        if not lock.acquired:
            raise Wait(P1.lock_wait_message(cfg))
        finish_open_txn(cfg, ctx)


def p1_entry_texts(cfg, text):
    return {k: v['text'] for k, v in P1.protocol_view(cfg, text)['entries'].items()}


def ensure_recorded(cfg, ctx, key, sha, build, also=(), tail=None):
    """Entry `key` citing `sha` (and every sha256 in `also`) in PROTOCOL Sec. 13.2, sealed and verified: the
    p1_driver.ensure_recorded transaction with this driver's heading, entry form, baseline and transaction file.
    build() -> the entry text after its bold head; the manifest clause is appended. tail() -> lines nested under the
    bullet (every one indented, none blank: nest_entry_lines), e.g. the entry text a tool printed. Returns 'recorded'
    (earlier), 'written' (now) or None (dry run)."""
    def compose(m_new, n_files, added, changed=()):
        lines = wrap_bullet(f'{entry_head(key)} {build()}' + manifest_clause(cfg, m_new, n_files, added, changed))
        extra = list(tail()) if tail else []
        if any(not ln.startswith('  ') or not ln.strip() for ln in extra):
            raise Alert('PROTOCOL.md', f'internal: a nested line of the entry {label_of(key)} is not indented')
        return lines + extra

    def check_entry(ent):
        if ent is None:
            return
        missing = [s for s in (sha, *also) if s not in ent['shas']]
        if missing:
            raise Alert('PROTOCOL.md', f'the Sec. 13.2 entry {label_of(key)} (line {ent["line"]}) does not cite sha256 '
                                       f'{missing} of the current file(s): a file changed after it was recorded')

    view = phase_view(cfg)
    ent = view['entries'].get(key)
    check_entry(ent)
    reg = P1.registration_view(cfg)
    cited = ent is not None or sha in view['sec_text']
    if cited and P1.cited_consistent(reg, P1.read_txn(cfg)):
        return 'recorded'
    if cfg.dry_run:
        if cited:
            ctx.add_plan(f'{label_of(key)}: Sec. 13.2 cites sha256 {sha} but the seal does not match: finish the '
                         'interrupted driver record (seal, verify) if one explains it, else ALERT')
            return None
        ctx.add_plan(f'record {label_of(key)} (sha256 {sha}) under the lock {cfg.rel(cfg.protocol_lock)}: check the '
                     'seal and the registered files against the sealed manifest; registration.py --write-manifest '
                     f'--force; append the entry under {HEADING} in Sec. 13.2'
                     + ('' if view['heading'] is not None else f' (heading created before "{ANCHOR}")')
                     + '; registration.py --seal; registration.py --verify')
        for ln in compose('<new manifest sha256>', '<n>', []):
            print(f'      | {ln}')
        return None
    P1.check_stop(ctx)
    wait_for_tools(ctx, cfg.registration_script)        # review fixes M2, S7: no registration.py of a killed driver
    with P1.ProtocolLock(cfg, ctx) as lock:
        if not lock.acquired:
            raise Wait(P1.lock_wait_message(cfg))
        finish_open_txn(cfg, ctx)
        text = cfg.protocol.read_text(encoding='utf-8')
        view = phase_view(cfg, text)
        ent = view['entries'].get(key)
        check_entry(ent)
        reg = P1.registration_view(cfg)
        if ent is not None or sha in view['sec_text']:
            if P1.cited_consistent(reg, P1.read_txn(cfg)):
                return 'recorded'
            raise Alert('registration', f'Sec. 13.2 already cites {label_of(key)} (sha256 {sha}) but SEAL.sha256 does '
                                        'not match PROTOCOL.md / MANIFEST.sha256 (an unsealed edit); seal or explain '
                                        'it before the driver continues')
        if reg['protocol_sha256'] != reg['seal_protocol']:
            raise Alert('registration', f'PROTOCOL.md (sha256 {reg["protocol_sha256"]}) is not the sealed version '
                                        f'({reg["seal_protocol"]}): an unsealed edit by another process; seal it or '
                                        'revert it before the driver continues')
        txn = P1.read_txn(cfg)
        own = bool(txn) and txn.get('step') in ('begin', 'manifest')
        if reg['manifest_sha256'] != reg['seal_manifest'] and not own:
            raise Alert('registration', f'MANIFEST.sha256 (sha256 {reg["manifest_sha256"]}) is not the sealed manifest '
                                        f'({reg["seal_manifest"]}) and no interrupted driver record explains it')
        if reg['manifest_sha256'] == reg['seal_manifest']:
            P1.atomic_write(cfg.sealed_copy, cfg.manifest.read_text(encoding='utf-8'))
        elif not (cfg.sealed_copy.is_file() and P1.sha256_file(cfg.sealed_copy) == reg['seal_manifest']):
            raise Alert('registration', 'MANIFEST.sha256 was rewritten by an interrupted driver record and no copy of '
                                        'the sealed manifest exists to check the tree against')
        sealed_text = cfg.sealed_copy.read_text(encoding='utf-8')
        if P1.sha256_text(sealed_text) != reg['seal_manifest']:
            raise Alert('registration', 'the copy of the sealed manifest does not have the sealed sha256')
        baseline = strict_map(cfg, refresh_baseline(cfg, ctx, view, reg, sealed_text))
        changed = [d[0] for d in P1.precheck_tree(cfg, ctx, baseline)]       # registered-baseline pre-check
        P = reg['protocol_sha256']
        base = {'key': key, 'sha256': sha, 'protocol_before': P, 'started': P1.now_iso()}
        P1.write_txn(cfg, {**base, 'step': 'begin'})
        crash_point(ctx, 'txn_begin')
        m_new, n_files = P1.run_write_manifest(cfg, ctx)
        P1.write_txn(cfg, {**base, 'step': 'manifest', 'manifest': m_new})
        crash_point(ctx, 'manifest_written')
        # post-manifest check (p1_driver review fix F1): a registered file must enter the new manifest with its sealed
        # sha256; a change between the pre-check and --write-manifest would otherwise be sealed silently
        old_map = P1.parse_manifest_text(sealed_text)
        new_map = P1.parse_manifest_text(cfg.manifest.read_text(encoding='utf-8'))
        laundered = [(p, old_map.get(p, baseline.get(p)), s) for p, s in new_map.items()
                     if P1.is_strict(cfg, p, baseline) and old_map.get(p, baseline.get(p)) not in (None, s)]
        if laundered:
            raise Alert('registration', f'{len(laundered)} registered file(s) changed while the driver re-sealed: '
                                        f'{[d[0] for d in laundered][:10]}; restore them (the unsealed manifest is '
                                        'redone at the restart) or amend the protocol', json.dumps(laundered, indent=1))
        # review fix M3: a registered file that vanished between the pre-check and --write-manifest (or an editor's
        # non-atomic save in that window) would leave the sealed manifest, and no later check would report it
        vanished = [p for p in old_map if P1.is_strict(cfg, p, baseline) and p not in new_map]
        if vanished:
            raise Alert('registration', f'{len(vanished)} registered file(s) vanished while the driver re-sealed: '
                                        f'{vanished[:10]}; restore them (the unsealed manifest is redone at the '
                                        'restart) or amend the protocol',
                        json.dumps([(p, old_map[p]) for p in vanished], indent=1))
        added = P1.manifest_added(cfg)
        if added:
            ctx.log(f'{label_of(key)}: {len(added)} files are new in the manifest: {added}')
        changed = [c for c in changed if c not in added]
        new_text = insert_entry(cfg, text, compose(m_new, n_files, added, changed))
        chk = phase_view(cfg, new_text)['entries'].get(key)
        if chk is None or any(s not in chk['shas'] for s in (sha, *also)) or m_new not in new_text:
            raise Alert('PROTOCOL.md', f'internal: the composed entry {label_of(key)} does not parse back with its '
                                       'sha256')
        if p1_entry_texts(cfg, new_text) != p1_entry_texts(cfg, text):
            raise Alert('PROTOCOL.md', f'internal: the composed entry {label_of(key)} changes the P1 driver\'s entries')
        after = P1.sha256_text(new_text)
        if P1.sha256_file(cfg.protocol) != P:
            raise Alert('PROTOCOL.md', 'PROTOCOL.md changed while the driver held the protocol lock (an editor that '
                                       'does not take the lock); the driver did not write PROTOCOL.md, but '
                                       'MANIFEST.sha256 was rewritten and is not sealed '
                                       "(phase_driver/protocol_txn.json, step 'manifest'): seal the other edit, then "
                                       'restart the driver')
        P1.write_txn(cfg, {**base, 'step': 'protocol', 'manifest': m_new, 'protocol_after': after})
        mode = cfg.protocol.stat().st_mode & 0o7777
        P1.atomic_write(cfg.protocol, new_text, mode=mode, tmp_dir=cfg.driver_dir)
        crash_point(ctx, 'protocol_written')
        P1.run_seal(cfg, ctx, after, m_new)
        P1.write_txn(cfg, {**base, 'step': 'sealed', 'manifest': m_new, 'protocol_after': after})
        crash_point(ctx, 'sealed')
        P1.run_verify(cfg, ctx, baseline)
        P1.clear_txn(cfg)
    ctx.log(f'recorded {label_of(key)} in PROTOCOL.md Sec. 13.2 (sha256 {sha}); manifest {m_new} ({n_files} files), '
            f'PROTOCOL.md {after}; sealed and verified')
    return 'written'


# ---------------------------------------------------------------------------------------------------- queue and runner

def other_runners(cfg, q):
    """Watched queues other than `q` whose runner is alive (a closed-loop job of this project may run there)."""
    return [w.queue_arg for w in cfg.watch_queues if w.queue != q.queue and runner_pid_alive(w)]


def copy_job_file(cfg, ctx, src, q, want_sha, what):
    """Copy the recorded job file `src` into <queue>/jobs.d once (temporary name, atomic rename). 'present', 'copied'
    or None (dry run). Never over a different file, never with ids that jobs.d already holds."""
    dst = q.jobs_d / src.name
    src_sha = P1.sha256_file(src)
    if src_sha != want_sha:
        raise Alert(f'{what} copy', f'{cfg.rel(src)} (sha256 {src_sha}) is not the recorded job file (sha256 '
                                    f'{want_sha}); the driver copies only the file its Sec. 13.2 entry cites')
    if dst.exists():
        if P1.sha256_file(dst) != src_sha:
            raise Alert(f'{what} copy', f'{cfg.rel(dst)} exists and differs from {cfg.rel(src)}; the driver never '
                                        'overwrites a queued job file')
        return 'present'
    new_ids = set(P1.job_ids(src))
    dup = {}
    for f in sorted(q.jobs_d.glob('*.jsonl')) if q.jobs_d.is_dir() else []:
        for i in P1.job_ids(f):
            if i in new_ids:
                dup.setdefault(f.name, []).append(i)
    if dup:
        raise Alert(f'{what} copy', f'job ids of {src.name} already exist in {cfg.rel(q.jobs_d)} (the runner would '
                                    f'skip them): { {k: v[:3] for k, v in dup.items()} }')
    if cfg.dry_run:
        ctx.add_plan(f'copy {cfg.rel(src)} into {cfg.rel(q.jobs_d)}/')
        return None
    P1.check_stop(ctx)
    q.jobs_d.mkdir(parents=True, exist_ok=True)
    tmp = q.jobs_d / f'.{src.name}.phase_driver.tmp'
    data = src.read_bytes()
    with open(tmp, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, dst)
    P1._fsync_dir(q.jobs_d)
    if P1.sha256_file(dst) != src_sha:
        raise Alert(f'{what} copy', f'the copy {cfg.rel(dst)} does not have the sha256 of {cfg.rel(src)}')
    ctx.log(f'{what}: copied {cfg.rel(src)} into {cfg.rel(dst)} ({len(new_ids)} jobs, sha256 {src_sha})')
    crash_point(ctx, 'copied')
    return 'copied'


def launch_runner(cfg, ctx, q):
    """systemd-run --user --scope --unit=framelease-<queue>-runner-<ts> -p OOMPolicy=continue bash launch_queue.sh <q>,
    at the driver's own priority (nice 0). 'launched', 'running' (another runner started meanwhile) or 'stop_file'."""
    P1.check_stop(ctx)
    bad = launch_priority_problem()
    if bad and not cfg.allow_nice_launch:
        raise Alert('runner', f'{bad}: a runner it launched would inherit it (every runner runs at nice 0 on every '
                              'core; scheduler CPU time is charged to the simulated timeline, PROTOCOL Secs. 2.3, '
                              '11.2); restart the driver at normal priority on every core')
    cmd = cfg.launch_cmd(q)
    rc, out, err = P1.run_cmd(ctx, cmd, TIMEOUTS['launch'], low=False)
    if rc == 0:
        ctx.launched_now = True
        ctx.log(f'runner launched in scope {cmd[3][len("--unit="):]}: '
                + ' | '.join(ln for ln in (out + '\n' + err).splitlines() if ln.strip())[-1500:])
        crash_point(ctx, 'launched')
        return 'launched'
    if 'another runner holds' in err:
        ctx.log('launch_queue.sh: another runner started meanwhile; nothing to do')
        return 'running'
    if '/STOP exists' in err:
        ctx.add_attention(f'launch_queue.sh refused: {err.strip()[:300]}')
        return 'stop_file'
    raise Alert('launch_queue', f'the isolated launch exited {rc} (systemd-run --user --scope or launch_queue.sh); the '
                                'driver never falls back to a launch outside a dedicated scope', P1.both(out, err), cmd)


def empty_exits_without_a_job(q):
    """The runner's 'queue empty' exits in <queue>/status.jsonl after its last job record (a job 'start' or 'end'):
    exits with no job started in between (read only)."""
    n = 0
    try:
        lines = (q.queue / 'status.jsonl').read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return 0
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get('event') in ('start', 'end') and r.get('id'):
            n = 0
        elif r.get('event') == 'runner_exit' and r.get('reason') == 'queue empty':
            n += 1
    return n


def ensure_runner(cfg, ctx, q, copied_now, min_free_gib=None, qs=None):
    """p1_driver.ensure_runner's rules for queue `q`, with the isolated launch: start the runner when pending jobs have
    none, after the driver copied a job file now, after a normal 'queue empty' exit, or in a queue that never had a
    runner. Returns 'idle', 'running', 'launched', 'stop_file', 'attention', 'waiting', 'alert' (dry run) or 'dry'."""
    qs = qs or P1.queue_status(q)
    ctx.state['queue'] = P1.queue_summary(qs)
    if not qs['pending']:
        return 'idle'
    if qs['runner_alive'] or P1.runner_lock_held(q):     # the pid check first: no lock test while the runner runs
        if qs['pause_file']:
            ctx.add_attention(f'{q.queue_arg}/PAUSE exists: the runner starts no new job')
        return 'running'
    if qs['stop_file']:
        ctx.add_attention(f'{q.queue_arg}/STOP exists and no runner runs: {len(qs["pending"])} jobs wait. Check the '
                          'disk (df -h), remove STOP by hand, then relaunch in a dedicated scope (systemd-run --user '
                          f'--scope -p OOMPolicy=continue bash framelease_v4/protocol/launch_queue.sh {q.queue_arg})')
        return 'stop_file'
    ex = qs['runner_exit']
    if ex is not None and ex.get('exit_code') in P1.ABNORMAL_RUNNER_EXIT:
        msg = (f'the runner of {q.queue_arg} exited with {ex.get("reason")!r} (exit {ex.get("exit_code")}, '
               f'{P1.ABNORMAL_RUNNER_EXIT[ex["exit_code"]]}) and {len(qs["pending"])} jobs are pending; the driver '
               'does not relaunch it (a relaunch could use up the attempts of further jobs): fix the cause, then '
               'relaunch')
        if cfg.dry_run:
            ctx.add_plan('ALERT and stop: ' + msg)
            return 'alert'
        raise Alert('runner', msg, json.dumps(ex, indent=1, default=str))
    if ex is not None and ex.get('exit_code') == P1.SIGNAL_RUNNER_EXIT:
        ctx.add_attention(f'the runner of {q.queue_arg} was stopped by a signal ({ex.get("reason")!r}, exit '
                          f'{P1.SIGNAL_RUNNER_EXIT}) and {len(qs["pending"])} jobs are pending; the driver never '
                          'relaunches a runner that was stopped on purpose (or by a shutdown): relaunch by hand in a '
                          'dedicated scope (to stop the runner on purpose, place '
                          f'{q.queue_arg}/STOP)')
        return 'attention'
    # a queue with a launch record (launch_queue.sh writes <queue>/launch_<UTC>.json) but no runner record had a launch
    # whose runner did not start: never relaunched in a loop
    launches = sorted(q.queue.glob('launch_*.json')) if q.queue.is_dir() else []
    never = qs['last_runner_start'] is None and ex is None and not launches
    if not copied_now and not never and not (ex is not None and ex.get('reason') == 'queue empty'):
        if qs['last_runner_start'] is None and ex is None:
            last = f'launched ({launches[-1].name}), but no runner record in status.jsonl: the runner did not start'
        else:
            last = ('no exit record after its last start (killed or crashed)' if ex is None
                    else f'exit {ex.get("reason")!r}')
        ctx.add_attention(f'no runner holds {q.queue_arg}/runner.lock and {len(qs["pending"])} jobs are pending (last '
                          f'runner: {last}); the driver relaunches only after copying a job file, after a normal '
                          "'queue empty' exit or into a queue that never had a runner: relaunch by hand in a dedicated "
                          'scope')
        return 'attention'
    busy = other_runners(cfg, q)
    if busy:
        ctx.add_attention(f'{q.queue_arg}: {len(qs["pending"])} jobs wait; a runner of {busy} is alive (the queues '
                          'share the GPU): the runner is launched after it exits')
        return 'waiting'
    if min_free_gib is not None:
        free = free_gib(cfg.root)
        if free is not None and free < min_free_gib:
            ctx.add_attention(f'{q.queue_arg}: {free:.1f} GiB free, below the {min_free_gib} GiB the queue needs: the '
                              'runner is not launched; free disk space')
            return 'waiting'
    n_empty = empty_exits_without_a_job(q)
    if not copied_now and n_empty >= EMPTY_EXIT_LIMIT:     # review fix S8: a pending id the runner never starts
        ctx.add_attention(f'the runner of {q.queue_arg} exited \'queue empty\' {n_empty} times in a row without '
                          f'starting a job while the driver counts {len(qs["pending"])} pending jobs '
                          f'({qs["pending"][:3]}); the driver relaunches no more: check the job lines the runner '
                          'skips, then relaunch by hand in a dedicated scope')
        return 'attention'
    if cfg.dry_run:
        ctx.add_plan(f'launch the runner: {P1.show(cfg.launch_cmd(q, "<ts>"))}')
        return 'dry'
    r = launch_runner(cfg, ctx, q)
    ctx.state['queue'] = P1.queue_summary(P1.queue_status(q))
    ctx.save()
    return r


def disk_health(cfg, ctx):
    free = free_gib(cfg.root)
    ctx.state['disk_free_gib'] = None if free is None else round(free, 2)
    if free is not None and free < DISK_ATTENTION_GIB:
        ctx.add_attention(f'{free:.1f} GiB free on {cfg.root} (below {DISK_ATTENTION_GIB} GiB; the runner starts no '
                          'job below 6 GiB and the disk watchdog stops it below 5 GiB)')


# ------------------------------------------------------------------------------------------ tool code (review fix M4)

def project_code(cfg, path):
    """True if `path` lies below <root>/framelease_v4 (the code the registration manifest covers)."""
    try:
        Path(path).resolve().relative_to((cfg.root / PROJECT_CODE).resolve())
        return True
    except ValueError:
        return False


def tool_scripts(cfg):
    """{option: script} of the tools whose code the gates check (G2-G6) or whose module G8 checks (the aggregation)."""
    return {'--p2-jobs-script': cfg.p2_jobs_script, '--p2-check-script': cfg.p2_check_script,
            '--p3-rl-script': cfg.p3_rl_script, '--stress-script': cfg.stress_script,
            '--test-jobs-script': cfg.test_jobs_script, '--test-freeze-script': cfg.test_freeze_script,
            '--aggregate-script': cfg.aggregate_script}


def gate_code(cfg, gate):
    """The code of the tools gate `gate` runs: the tool scripts and the sources they freeze or check."""
    return {'G2': (cfg.p2_jobs_script,), 'G3': (cfg.p2_check_script,),
            'G4': (cfg.p3_rl_script, *P3_CODE, cfg.p2_jobs_script, cfg.p2_check_script),
            'G5': (cfg.stress_script,),
            'G6': (cfg.test_jobs_script, cfg.test_freeze_script, *TEST_CODE)}[gate]


def code_files(cfg, items):
    """({path relative to the root: sha256}, [missing], [outside]) of the code `items`: files, or directories standing
    for every file below them without __pycache__ (as registration.manifest_paths lists them). A path outside
    <root>/framelease_v4 (a test stand-in for a tool) is returned in `outside` and not hashed."""
    files, missing, outside = {}, [], []
    for item in items:
        p = cfg.path(item)
        if not project_code(cfg, p):
            outside.append(cfg.rel(p))
        elif p.is_dir():
            for f in sorted(p.rglob('*')):
                if f.is_file() and '__pycache__' not in f.relative_to(p).parts:
                    files[cfg.rel(f)] = P1.sha256_file(f)
        elif p.is_file():
            files[cfg.rel(p)] = P1.sha256_file(p)
        else:
            missing.append(cfg.rel(p))
    return files, missing, outside


def require_registered_code(cfg, ctx, gate):
    """Review fix M4: before gate `gate` runs a tool, every file of its code (gate_code) is registered: at the sha256
    the registered baseline holds for it, or at a sha256 that the sealed PROTOCOL.md cites (an amendment that
    registers it: A3, or the split "A3b" of APPLY_PLAN Sec. 2 that registers the P3-P7 tools after P2 has started).
    Otherwise the gate waits (AttentionWait: attention, no ALERT) until the coordinating session's amendment is
    sealed; G8 applies the same rule to the analysis code (analysis_registration). A tool outside <root>/framelease_v4
    (a test stand-in) is not checked: in the project tree the driver refuses to start with one (run_driver)."""
    files, missing, outside = code_files(cfg, gate_code(cfg, gate))
    baseline = sealed_baseline(cfg, ctx) or {}
    pending = sorted(p for p, h in files.items() if baseline.get(p) != h)
    waits, unreg = [], []
    if pending:
        reg = P1.registration_view(cfg)
        if reg['protocol_sha256'] != reg['seal_protocol']:
            waits.append(f'PROTOCOL.md is not the sealed version, and {len(pending)} file(s) are not in the registered '
                         f'baseline at their sha256 ({pending[:5]}): a citation counts in the sealed text only')
        else:
            text = phase_view(cfg)['text']
            unreg = [p for p in pending if files[p] not in text]
            if unreg:
                waits.append(f'{len(unreg)} file(s) at a sha256 that neither the registered baseline holds nor '
                             f'PROTOCOL.md cites: {unreg[:8]}')
    if missing:
        waits.append(f'missing: {missing}')
    ctx.gate(gate)['code'] = {'files': len(files), 'registered': not waits, 'unregistered': unreg[:20],
                              'missing': missing, 'not_checked': outside}
    if waits:
        msg = (f'{gate}: the code of its tools is not registered: ' + '; '.join(waits) + '. The gate goes on once an '
               'amendment registers it (PROTOCOL.md citing the sha256, sealed; e.g. the split A3b of APPLY_PLAN Sec. '
               '2)')
        ctx.add_attention(msg)
        raise AttentionWait(msg)


# ---------------------------------------------------------------------------------------------------- G0 preconditions

def verify_registration(cfg, ctx, baseline):
    """registration.py --verify, read without an ALERT: (ok, detail). ok: both seal lines OK and the manifest matches
    the tree, or only unregistered files differ (code in development, swept in by the manifest's glob). Waits
    (AttentionWait) while a registration.py runs (review fix M2)."""
    wait_for_tools(ctx, cfg.registration_script)
    cmd = cfg.reg_cmd('--verify')
    rc, out, err = P1.run_cmd(ctx, cmd, TIMEOUTS['registration'], cfg.tool_env())
    seals = re.findall(r'^seal (.+): (OK|CHANGED)$', out, re.M)
    if not (len(seals) == 2 and all(s == 'OK' for _, s in seals)):
        return False, f'registration.py --verify: seal lines {seals or "missing"} (exit {rc}): {err.strip()[-300:]}'
    if rc == 0 and re.search(r'^manifest: OK$', out, re.M):
        return True, 'seal OK, manifest OK'
    m = re.search(r'^manifest: (\d+) files differ: (.*)$', out, re.M)
    if rc != 1 or not m:
        return False, f'registration.py --verify exited {rc}: {(out + err).strip()[-300:]}'
    n, diffs = int(m.group(1)), None
    if n <= 10:                                   # registration.py prints the first 10 differences
        try:
            diffs = [tuple(d) for d in ast.literal_eval(m.group(2))]
        except (ValueError, SyntaxError, TypeError):
            diffs = None
    if diffs is None or len(diffs) != n:
        diffs = P1.tree_differences(cfg, ctx, cfg.manifest)
    strict = [d[0] for d in diffs if P1.is_strict(cfg, d[0], baseline)]
    if strict:
        return False, f'{len(strict)} registered file(s) differ from the sealed manifest: {strict[:10]}'
    return True, (f'seal OK; {len(diffs)} unregistered file(s) differ from the manifest (code in development): '
                  f'{[d[0] for d in diffs][:10]}')


def p1_driver_alive(cfg):
    holder = P1.lock_holder_text(cfg.p1_lock)
    m = re.match(r'pid (\d+)', holder)
    return bool(m) and 'p1_driver.py' in P1.pid_cmdline(m.group(1))


def gate_g0(cfg, ctx):
    """G0: P1 done, the P1 driver's freeze and D1 entries, Amendments A3, A4, A7, A9, the seal verifies. Waits (never
    an ALERT). Passed for good once the G1 entry exists (its record transaction verified the seal) or while a record
    transaction of this driver is open (it started after G0 had passed)."""
    st = ctx.gate('G0')
    try:
        view = phase_view(cfg)
    except Alert as a:
        st.update(status='waiting', note=f'Sec. 13.2 cannot be read: {a.problem}')
        ctx.add_attention(f'G0: {a.problem}')
        return 'waiting'
    if 'd1_decision' in view['entries']:
        st.update(status='passed', note='passed (the G1 entry exists)')
        return 'done'
    if P1.read_txn(cfg):            # a record of this driver started after G0 had passed; it explains a seal mismatch
        st.update(status='passed', note=f'passed (a record of this driver is open: {cfg.rel(cfg.txn_path)})')
        return 'done'
    waits = []
    done = P1.read_json(cfg.p1_done)
    if not cfg.p1_done.exists():
        waits.append(f'{cfg.rel(cfg.p1_done)} does not exist yet (P1 runs)')
    elif not isinstance(done, dict) or done.get('schema') != P1_DONE_SCHEMA:
        waits.append(f'{cfg.rel(cfg.p1_done)} is not a P1 driver completion record (schema {P1_DONE_SCHEMA})')
    if p1_driver_alive(cfg):
        waits.append('the P1 stage driver is still running')
    if cfg.p1_txn.exists():
        waits.append(f'{cfg.rel(cfg.p1_txn)} exists (an interrupted P1 record)')
    missing = [P1.LABEL[k] for k in P1_KEYS if k not in view['p1_entries']]
    if missing:
        waits.append(f'Sec. 13.2 has no P1 driver entry {missing}')
    amend = [a for a in cfg.required_amendments if a not in view['amendments']]
    if amend:
        waits.append(f'Sec. 13.2 has no entry of Amendment(s) {amend}')
    dup = {a: ln for a, ln in view['amendments'].items() if a in cfg.required_amendments and len(ln) > 1}
    if dup:
        waits.append(f'Amendment(s) entered more than once: {dup}')
    st['files'] = {'p1_done': cfg.rel(cfg.p1_done) if cfg.p1_done.exists() else None,
                   'amendments': {a: view['amendments'].get(a) for a in cfg.required_amendments},
                   'p1_entries': {k: (view['p1_entries'].get(k) or {}).get('line') for k in P1_KEYS}}
    if waits:
        st.update(status='waiting', note='; '.join(waits))
        return 'waiting'
    reg = P1.registration_view(cfg)
    key = (reg['protocol_sha256'], reg['manifest_sha256'])
    if key not in ctx.verified:
        ctx.verified[key] = verify_registration(cfg, ctx, strict_map(cfg, sealed_baseline(cfg, ctx) or {}))
    ok, detail = ctx.verified[key]
    st['note'] = detail
    if not ok:
        ctx.verified.pop(key, None)                # verified again at the next cycle
        st.update(status='waiting', note=f'the seal does not verify: {detail}')
        ctx.add_attention(f'G0: the seal does not verify: {detail}')
        return 'waiting'
    if 'passed' not in st['times']:
        st['times']['passed'] = P1.now_iso()
        ctx.log(f'G0 passed: P1 done, P1 entries {list(P1_KEYS)}, amendments {list(cfg.required_amendments)}; {detail}')
    st['status'] = 'passed'
    return 'done'


# ---------------------------------------------------------------------------------------------------- G1 D1 decision

def decision_doc(cfg, ctx, path, step):
    """The JSON object of a decision file the coordinating session writes (D1_DECISION.json, P3_OPEN_CASES.json).
    Review fix S5: a file that is not readable JSON yet and was modified less than DECISION_GRACE_S ago is a write in
    progress (AttentionWait, read again at the next cycle); unreadable for longer: ALERT. Write these files atomically
    (a temporary file in the same directory, then mv)."""
    doc = P1.read_json(path)
    if isinstance(doc, dict):
        return doc
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        age = 0.0
    if age < DECISION_GRACE_S:
        msg = (f'{cfg.rel(path)} is not readable JSON yet (modified {age:.0f} s ago: a write in progress?); read again '
               'at the next cycle')
        ctx.add_attention(msg)
        raise AttentionWait(msg)
    raise Alert(step, f'{cfg.rel(path)} exists but is not a readable JSON object (unchanged for {age:.0f} s); write it '
                      'atomically (a temporary file in the same directory, then mv)')


def load_decision(cfg, ctx, view):
    """(decision document, its sha256, the D1 summary sha256) of D1_DECISION.json, validated against the D1 summary
    and the P1 driver's "D1 summary" entry; ALERT on any problem (the file is the coordinating session's)."""
    path = cfg.decision_path
    doc = decision_doc(cfg, ctx, path, 'G1 D1 decision')
    where = cfg.rel(path)
    problems = []
    if doc.get('schema') not in (None, DECISION_SCHEMA):
        problems.append(f'schema {doc.get("schema")!r} (expected {DECISION_SCHEMA})')
    if doc.get('decision') not in DECISIONS:
        problems.append(f'decision {doc.get("decision")!r} (expected one of {list(DECISIONS)})')
    if not isinstance(doc.get('rationale'), str) or not doc['rationale'].strip():
        problems.append('no rationale')
    want = doc.get('d1_summary_sha256')
    jpath = cfg.d1_paths()[0]
    have = P1.sha256_file(jpath) if jpath.is_file() else None
    ent = view['p1_entries'].get('d1')
    if not isinstance(want, str) or not SHA_RE.fullmatch(want):
        problems.append(f'd1_summary_sha256 {want!r} is not a sha256')
    elif want != have:
        problems.append(f'd1_summary_sha256 {want} is not the sha256 of {cfg.rel(jpath)} ({have})')
    elif ent is None or want not in ent['shas']:
        problems.append(f'd1_summary_sha256 {want} is not cited by the P1 driver\'s "D1 summary" entry')
    if problems:
        raise Alert('G1 D1 decision', f'{where}: ' + '; '.join(problems), json.dumps(doc, indent=1)[:5000])
    return doc, P1.sha256_file(path), want


def decision_entry(cfg, doc, sha, d1_sha):
    """The G1 entry text. Other entries are cited by label and sha256, never by line (review fix S2: a line number
    goes stale once text is inserted above it)."""
    jpath = cfg.d1_paths()[0]
    decided = f', decided {one_line(doc["decided"], 60)}' if doc.get('decided') else ''
    by = f' by {one_line(doc["by"], 120)}' if doc.get('by') else ' by the coordinating session'
    if doc['decision'] == 'continue':
        nxt = ('Phase 2 starts after this entry: the P2 job file is generated, entered in this section before it is '
               'queued, and launched (gate G2).')
    else:
        nxt = (f'Phase 2 is not started; the phase driver stops (`{cfg.rel(cfg.stopped_path)}`) and starts no later '
               'phase.')
    return (f'D1 (Sec. 4.8): **{doc["decision"]}**. `{cfg.rel(cfg.decision_path)}` (sha256 `{sha}`){decided}{by}, on '
            f'the D1 summary `{cfg.rel(jpath)}` (sha256 `{d1_sha}`, cited by the P1 driver\'s entry "D1 summary"). '
            f'Rationale: {sentence(doc["rationale"])} {DELEGATION}. {nxt}')


def write_stopped(cfg, ctx, doc, sha):
    if cfg.stopped_path.exists():
        return
    if cfg.dry_run:
        ctx.add_plan(f'write {cfg.rel(cfg.stopped_path)} (D1 = stop) and end')
        return
    view = phase_view(cfg)
    reg = P1.registration_view(cfg)
    stopped = {'schema': STOPPED_SCHEMA, 'written': P1.now_iso(), 'variant': VARIANT,
               'decision': {'path': cfg.rel(cfg.decision_path), 'sha256': sha, 'decision': doc.get('decision'),
                            'rationale': doc.get('rationale'), 'd1_summary_sha256': doc.get('d1_summary_sha256')},
               'entry_line': (view['entries'].get('d1_decision') or {}).get('line'),
               'protocol_sha256': reg['protocol_sha256'], 'manifest_sha256': reg['manifest_sha256'],
               'seal_ok': reg['seal_ok'],
               'next': 'D1 = stop (Sec. 4.8): Phase 2 and every later phase are not started; the phase driver ends.'}
    P1.atomic_write(cfg.stopped_path, json.dumps(stopped, indent=1, sort_keys=True, default=str) + '\n')
    ctx.log(f'P2 STOPPED: D1 = stop recorded; {cfg.rel(cfg.stopped_path)} written; the driver ends')


def gate_g1(cfg, ctx):
    """G1: the D1 decision recorded in Sec. 13.2. 'done' (continue), 'stopped' (stop), 'waiting' or 'dry'."""
    st = ctx.gate('G1')
    view = phase_view(cfg)
    if not cfg.decision_path.exists():
        if 'd1_decision' in view['entries']:
            raise Alert('G1 D1 decision', f'Sec. 13.2 holds the D1 decision entry (line '
                                          f'{view["entries"]["d1_decision"]["line"]}) but {cfg.rel(cfg.decision_path)} '
                                          'is missing')
        st.update(status='waiting', note=f'waiting for {cfg.rel(cfg.decision_path)} (the coordinating session\'s D1 '
                                         'decision under the delegation of 2026-11-14)')
        return 'waiting'
    doc, sha, d1_sha = load_decision(cfg, ctx, view)
    st['files'] = {'decision': cfg.rel(cfg.decision_path), 'sha256': sha, 'decision_value': doc['decision'],
                   'd1_summary_sha256': d1_sha}
    r = ensure_recorded(cfg, ctx, 'd1_decision', sha, lambda: decision_entry(cfg, doc, sha, d1_sha))
    if r is None:
        st.update(status='dry', note=f'D1 = {doc["decision"]}: not yet recorded')
        return 'dry'
    ent = phase_view(cfg)['entries'].get('d1_decision')
    st['entry'] = {'line': ent['line'], 'when': ent['when']} if ent else {'cited': True}
    st['times'].setdefault('recorded', P1.now_iso())
    if doc['decision'] == 'stop':
        write_stopped(cfg, ctx, doc, sha)
        st.update(status='stopped', note='D1 = stop: Phase 2 is not started')
        return 'stopped'
    st.update(status='passed', note='D1 = continue, recorded')
    ctx.save()
    return 'done'


# ---------------------------------------------------------------------------------------------------- G2 P2 job file

def recorded_freeze(cfg, view):
    """(sha256, entry) of the tuning freeze; ALERT unless it is the file the P1 driver's "Tuning freeze" entry cites."""
    path = cfg.freeze_path
    ent = view['p1_entries'].get('freeze')
    if not path.is_file():
        raise Alert('tuning freeze', f'{cfg.rel(path)} is missing although P1 is done')
    sha = P1.sha256_file(path)
    if ent is None or sha not in ent['shas']:
        where = 'missing' if ent is None else f'line {ent["line"]}'
        raise Alert('tuning freeze', f'{cfg.rel(path)} (sha256 {sha}) is not the freeze the P1 driver recorded in Sec. '
                                     f'13.2 (entry "Tuning freeze": {where})')
    return sha, ent


def p2_problems(cfg, freeze_sha):
    """[] if the generated P2 files are complete, passed their check and cite the recorded tuning freeze."""
    jsonl, spec_p, check_p = cfg.p2_paths()
    missing = [cfg.rel(p) for p in (jsonl, spec_p, check_p) if not p.is_file()]
    if missing:
        return [f'missing {missing}']
    sha = P1.sha256_file(jsonl)
    check, spec = P1.read_json(check_p), P1.read_json(spec_p)
    if not isinstance(check, dict) or not isinstance(spec, dict):
        return ['unreadable .check.json or .stage.json']
    try:
        lines = [json.loads(ln) for ln in jsonl.read_text(encoding='utf-8').splitlines() if ln.strip()]
    except ValueError as e:
        return [f'job file does not parse: {e}']
    probs = []
    if check.get('schema') != P2_CHECK_SCHEMA or spec.get('schema') != P2_STAGE_SCHEMA:
        probs.append(f'schemas {check.get("schema")!r} / {spec.get("schema")!r}')
    if check.get('problems'):
        probs.append(f'check problems: {check["problems"][:5]}')
    if check.get('all_dry_runs_ok') is not True:
        probs.append('the check does not report every dry run as passed')
    if check.get('job_file_sha256') != sha or spec.get('job_file_sha256') != sha:
        probs.append('job_file_sha256 of the check / stage spec differs from the job file')
    if not lines or not (len(lines) == check.get('n_lines') == spec.get('n_lines')):
        probs.append(f'line counts: file {len(lines)}, check {check.get("n_lines")}, spec {spec.get("n_lines")}')
    if (spec.get('variant'), spec.get('block'), spec.get('block_no')) != (VARIANT, P2_BLOCK, P2_BLOCK_NO):
        probs.append(f'stage spec of another block: {spec.get("variant")} / {spec.get("block")} / '
                     f'{spec.get("block_no")}')
    if (spec.get('tuning_freeze') or {}).get('sha256') != freeze_sha:
        probs.append(f'the stage spec does not cite the recorded tuning freeze (sha256 {freeze_sha})')
    if spec.get('queue') != cfg.p2_queue.queue_arg:
        probs.append(f'the stage spec names the queue {spec.get("queue")!r}, not {cfg.p2_queue.queue_arg}')
    ids = [j.get('id') for j in lines]
    if len(set(ids)) != len(ids) or any(j.get('block') != P2_BLOCK for j in lines):
        probs.append('duplicate ids or lines of another block')
    if any(j.get('training_route') is not True or (j.get('tuning_freeze') or {}).get('sha256') != freeze_sha
           for j in lines):
        probs.append('a line that is not a training-route line of the recorded tuning freeze')
    return probs


def p2_entry(cfg, freeze_sha, jsha, ssha, csha):
    jsonl, spec_p, check_p = cfg.p2_paths()
    spec = P1.read_json(spec_p)
    L, d = spec.get('L_star') or {}, spec.get('d_star') or {}
    per = ', '.join(f'kappa {k}: {n}' for k, n in sorted((spec.get('runs_per_kappa') or {}).items()))
    pins = spec.get('code_pins') or {}
    return (f'`{cfg.rel(jsonl)}` (sha256 `{jsha}`), {spec.get("n_lines")} job lines: block `{spec.get("block")}`, '
            f'block number {spec.get("block_no")}, tier {spec.get("tier")}, arm `{spec.get("arm")}`, eps '
            f'{spec.get("eps")}, kappa {spec.get("kappas")} ({per}), seed {spec.get("seed")}, '
            f'{len(spec.get("routes") or [])} training routes (subset {spec.get("route_set")}). Stage spec '
            f'`{cfg.rel(spec_p)}` (sha256 `{ssha}`) and check `{cfg.rel(check_p)}` (sha256 `{csha}`; no problem, '
            f'every dry run passed), written by `source linux/env.sh && CUDA_VISIBLE_DEVICES= p2_jobs.py --check '
            f'--write` from the tuning freeze `{cfg.rel(cfg.freeze_path)}` (sha256 `{freeze_sha}`, cited by the P1 '
            f'driver\'s entry "Tuning freeze"): L* = `{L.get("label")}` (`{L.get("path")}`, sha256 '
            f'`{L.get("sha256")}`), d* = {d.get("d")} (utility `{d.get("utility")}`). Code pins: {pins.get("n")} '
            f'files, rule {pins.get("rule")}. Not registered, entered here with the job file (GAP_AUDIT Sec. 6 item '
            f'5(d)): the block number {spec.get("block_no")}, the route order ({spec.get("order_rule")}) and the queue '
            f'`{spec.get("queue")}`. After this entry the job file is copied into `{cfg.rel(cfg.p2_queue.jobs_d)}` and '
            'its runner is launched in a dedicated systemd user scope (`systemd-run --user --scope -p '
            'OOMPolicy=continue bash framelease_v4/protocol/launch_queue.sh`).')


def gate_g2(cfg, ctx):
    """G2: the P2 job file generated once, recorded (job file, stage spec, check), copied into queue_p2/jobs.d, the
    runner launched. 'done' or 'dry'."""
    st = ctx.gate('G2')
    view = phase_view(cfg)
    freeze_sha, _ = recorded_freeze(cfg, view)
    jsonl, spec_p, check_p = cfg.p2_paths()
    q = cfg.p2_queue
    queued = q.jobs_d / jsonl.name
    ent = view['entries'].get('p2_jobs')
    if ent is None:
        wait_for_tools(ctx, cfg.p2_jobs_script)          # M2: never read files a p2_jobs.py still writes
    if all(p.is_file() for p in (jsonl, spec_p, check_p)):
        probs = p2_problems(cfg, freeze_sha)
        if probs:
            raise Alert('G2 P2 job file', f'the generated P2 files do not validate: {probs}; the driver never '
                                          'regenerates them over existing files')
    elif ent is not None or queued.exists():
        raise Alert('G2 P2 job file', f'{cfg.rel(jsonl)}, its stage spec or its check is missing although '
                                      + ('Sec. 13.2 records it' if ent is not None else f'{cfg.rel(queued)} exists'))
    else:
        require_registered_code(cfg, ctx, 'G2')
        if cfg.dry_run:
            ctx.add_plan(f'G2: generate the P2 job file: {P1.show(cfg.p2_jobs_cmd())}; then record it in Sec. 13.2, '
                         f'copy it into {cfg.rel(q.jobs_d)}/ and launch the runner in a dedicated scope')
            st.update(status='dry', note='P2 job file not generated yet')
            return 'dry'
        P1.check_stop(ctx)
        cmd = cfg.p2_jobs_cmd()
        rc, out, err = P1.run_cmd(ctx, cmd, TIMEOUTS['p2_jobs'], cfg.tool_env())
        if rc != 0:
            raise Alert('G2 p2_jobs', f'p2_jobs.py --check --write exited {rc}', P1.both(out[-20000:], err[-20000:]),
                        cmd)
        crash_point(ctx, 'p2_generated')
        probs = p2_problems(cfg, freeze_sha)
        if probs:
            raise Alert('G2 p2_jobs', f'the generated P2 files do not validate: {probs}',
                        P1.both(out[-20000:], err[-20000:]), cmd)
        ctx.log(f'G2: generated {cfg.rel(jsonl)} (sha256 {P1.sha256_file(jsonl)})\n' + out.rstrip()[-3000:])
    jsha, ssha, csha = (P1.sha256_file(p) for p in (jsonl, spec_p, check_p))
    st['files'] = {'job_file': cfg.rel(jsonl), 'sha256': jsha, 'stage_spec': cfg.rel(spec_p), 'stage_spec_sha256': ssha,
                   'check': cfg.rel(check_p), 'check_sha256': csha, 'generated': P1.mtime_iso(check_p),
                   'tuning_freeze_sha256': freeze_sha}
    r = ensure_recorded(cfg, ctx, 'p2_jobs', jsha,
                        lambda: p2_entry(cfg, freeze_sha, jsha, ssha, csha), also=(ssha, csha))
    if r is None:
        st.update(status='dry', note='P2 job file generated, not yet recorded in Sec. 13.2')
        return 'dry'
    ent = phase_view(cfg)['entries'].get('p2_jobs')
    st['entry'] = {'line': ent['line'], 'when': ent['when']} if ent else {'cited': True}
    c = copy_job_file(cfg, ctx, jsonl, q, jsha, 'G2 P2')
    if c is None:
        st.update(status='dry', note='recorded, not yet copied into jobs.d')
        return 'dry'
    st['files'].update(copied_to=cfg.rel(queued), copied=P1.mtime_iso(queued))
    if c == 'copied':
        ctx.save()
        ensure_runner(cfg, ctx, q, copied_now=True, min_free_gib=MIN_FREE_GIB.get(q.name))
    st.update(status='passed', note=f'recorded and queued in {q.queue_arg}')
    ctx.save()
    return 'done'


# ------------------------------------------------------------------------------------------------ G3 P2 data manifest

def load_p2_outputs(cfg, jsha, status_sha):
    """(report, manifest, problems) of the written P2 completion check and data manifest."""
    report_p, man_p = cfg.p2_outputs()
    rep, man = P1.read_json(report_p), P1.read_json(man_p)
    if not isinstance(rep, dict) or not isinstance(man, dict):
        return rep, man, [f'{cfg.rel(report_p)} or {cfg.rel(man_p)} missing or not readable JSON']
    probs = []
    if rep.get('schema') != P2_REPORT_SCHEMA or rep.get('verdict') != 'PASS':
        probs.append(f'report schema / verdict {rep.get("schema")!r} / {rep.get("verdict")!r}')
    if man.get('schema') != P2_MANIFEST_SCHEMA:
        probs.append(f'manifest schema {man.get("schema")!r}')
    for name, doc in (('report', rep), ('manifest', man)):
        if doc.get('job_file_sha256') != jsha:
            probs.append(f'the {name} is not of the recorded P2 job file (sha256 {jsha})')
        if doc.get('status_jsonl_sha256') != status_sha:
            probs.append(f'the {name} was made from other runner records (status.jsonl sha256 '
                         f'{doc.get("status_jsonl_sha256")}, now {status_sha})')
    if man.get('n_missing') != len(man.get('missing') or []) or man.get('n_episodes') != len(man.get('episodes') or []):
        probs.append('the manifest counts do not match its lists')
    return rep, man, probs


def missing_acknowledged(cfg, missing):
    """The acknowledgement file if it names every missing job id, else None."""
    path = cfg.missing_ack_path
    if not missing or not path.is_file():
        return None
    text = path.read_text(encoding='utf-8', errors='replace')
    return path if all(m in text for m in missing) else None


def p2_data_entry(cfg, rep, man, msha, rsha, jsha, ack):
    report_p, man_p = cfg.p2_outputs()
    c = rep.get('counts') or {}
    per = ', '.join(f'kappa {k}: {n}' for k, n in sorted((man.get('episodes_per_kappa') or {}).items()))
    missing = man.get('missing') or []
    if missing:
        miss = (f'{len(missing)} missing episode(s) without a valid official record after the single infrastructure '
                f'retry (Sec. 8.4; listed in the manifest, nothing imputed or re-run, Sec. 9.8): '
                + ', '.join(f'`{m.get("job")}` ({one_line(m.get("cause"), 80)})' for m in missing[:12])
                + (f' and {len(missing) - 12} more' if len(missing) > 12 else '')
                + f'; accepted by the coordinating session (GAP_AUDIT Sec. 6 item 5(c)) in `{cfg.rel(ack)}` (sha256 '
                  f'`{P1.sha256_file(ack)}`)')
    else:
        miss = 'no missing episode'
    return (f'`{cfg.rel(man_p)}` (sha256 `{msha}`) and the completion check `{cfg.rel(report_p)}` (sha256 `{rsha}`), '
            f'written {man.get("written")} by `p2_check.py --queue {cfg.p2_queue.queue_arg} --write` after every job '
            f'of the queue was final and its runner had exited: PASS; {rep.get("n_jobs")} jobs, '
            f'{man.get("n_episodes")} episodes ({per}); {miss}; {len(man.get("excluded_runs") or [])} run directories '
            f'excluded (failed or uncounted attempts); {c.get("error", 0)} errors. Job file sha256 `{jsha}` (entry '
            f'"{label_of("p2_jobs")}"); runner records `{cfg.p2_queue.queue_arg}/status.jsonl` sha256 '
            f'`{man.get("status_jsonl_sha256")}`. P2 ends with this data manifest (Sec. 8.1); P3 builds the offline-RL '
            'dataset from exactly its episodes (Sec. 5.9).')


def run_p2_check(cfg, ctx, write):
    cmd = cfg.p2_check_cmd(write)
    rc, out, err = P1.run_cmd(ctx, cmd, TIMEOUTS['p2_check'], cfg.tool_env())
    return cmd, rc, out, err


def gate_g3(cfg, ctx):
    """G3: P2 job health while it runs; when every job is final and the runner has exited, the completion check
    (PASS required), the data manifest written and recorded. 'done', 'waiting' or 'dry'."""
    st = ctx.gate('G3')
    view = phase_view(cfg)
    q = cfg.p2_queue
    jsonl = cfg.p2_paths()[0]
    jsha = P1.sha256_file(jsonl)
    report_p, man_p = cfg.p2_outputs()
    ent = view['entries'].get('p2_data')
    if ent is not None:
        shas = [P1.sha256_file(p) if p.is_file() else None for p in (man_p, report_p)]
        if any(s not in ent['shas'] for s in shas):
            raise Alert('G3 P2 data manifest', f'{cfg.rel(man_p)} or {cfg.rel(report_p)} is missing or differs from '
                                               f'the sha256 the Sec. 13.2 entry (line {ent["line"]}) cites')
        st.update(status='passed', note='recorded', entry={'line': ent['line'], 'when': ent['when']})
        return 'done'
    qs = P1.queue_status(q)
    ctx.state['queue'] = P1.queue_summary(qs)
    st['progress'] = {'jobs': qs['jobs'], 'final': qs['final'], 'pending': len(qs['pending'])}
    if not qs['jobs']:                                   # review fix S6 (as G7)
        raise Alert('G3 P2', f'{cfg.rel(q.jobs_d)} holds no job although G2 queued {jsonl.name}')
    if qs['pending']:
        if not getattr(ctx, 'launched_now', False):
            ensure_runner(cfg, ctx, q, copied_now=False, min_free_gib=MIN_FREE_GIB.get(q.name), qs=qs)
        disk_health(cfg, ctx)
        st.update(status='running', note=f'{qs["final"]} of {qs["jobs"]} P2 jobs final')
        return 'waiting'
    if qs['runner_alive'] or P1.runner_lock_held(q):
        st.update(status='waiting', note='every P2 job is final; waiting for the runner to exit')
        return 'waiting'
    queued = q.jobs_d / jsonl.name
    if not queued.is_file() or P1.sha256_file(queued) != jsha:
        raise Alert('G3 P2 data manifest', f'{cfg.rel(queued)} is missing or differs from the recorded '
                                           f'{cfg.rel(jsonl)}')
    status_p = q.queue / 'status.jsonl'
    status_sha = P1.sha256_file(status_p) if status_p.is_file() else None
    wait_for_tools(ctx, cfg.p2_check_script)             # M2: never read files a p2_check.py still writes
    if not man_p.exists():
        require_registered_code(cfg, ctx, 'G3')
        if cfg.dry_run:
            ctx.add_plan(f'G3: {P1.show(cfg.p2_check_cmd(False))}; on PASS the same with --write, then record the data '
                         'manifest in Sec. 13.2')
            st.update(status='dry', note='every P2 job is final')
            return 'dry'
        P1.check_stop(ctx)
        cmd, rc, out, err = run_p2_check(cfg, ctx, False)
        if rc == 3:
            ctx.add_attention(f'G3: p2_check.py reports INCOMPLETE although every job in {q.queue_arg}/jobs.d has a '
                              f'final runner record and no runner runs: {(out + err).strip()[-300:]}')
            st.update(status='waiting', note='p2_check INCOMPLETE')
            return 'waiting'
        if rc != 0:
            verdict = {1: 'FAIL', 2: 'error'}.get(rc, 'unexpected')
            raise Alert('G3 p2_check', f'p2_check.py exited {rc} ({verdict}): P3 does not start on this data',
                        P1.both(out[-20000:], err[-20000:]), cmd)
        missing = re.findall(r'^  missing episode (\S+): ', out, re.M)
        if missing and missing_acknowledged(cfg, missing) is None:
            raise Alert('G3 missing episodes', f'p2_check.py PASS with {len(missing)} missing episode(s) after the '
                                               f'registered retry: {missing[:20]}. Open case GAP_AUDIT Sec. 6 item '
                                               '5(c) (the dataset is the valid episodes; nothing re-runs beyond the '
                                               'retry): '
                                               'the coordinating session decides; to continue, name every missing job '
                                               f'id and the decision in {cfg.rel(cfg.missing_ack_path)}',
                        P1.both(out[-20000:], err[-20000:]), cmd)
        cmd, rc, out, err = run_p2_check(cfg, ctx, True)
        wrote = {cfg.path(p).resolve(): s for p, s in
                 re.findall(r'^(?:wrote|unchanged) (.+?)  sha256 ([0-9a-f]{64})$', out, re.M)}
        if rc != 0 or report_p.resolve() not in wrote or man_p.resolve() not in wrote:
            raise Alert('G3 p2_check', f'p2_check.py --write exited {rc} or did not write both the report and the data '
                                       'manifest', P1.both(out[-20000:], err[-20000:]), cmd)
        if P1.sha256_file(man_p) != wrote[man_p.resolve()] or P1.sha256_file(report_p) != wrote[report_p.resolve()]:
            raise Alert('G3 p2_check', 'the written files do not have the printed sha256', P1.both(out, err), cmd)
        ctx.log(f'G3: P2 completion check PASS; wrote {cfg.rel(man_p)} and {cfg.rel(report_p)}\n'
                + out.rstrip()[-3000:])
        crash_point(ctx, 'p2_check_written')
    rep, man, probs = load_p2_outputs(cfg, jsha, status_sha)
    if probs:
        raise Alert('G3 P2 data manifest', f'{cfg.rel(man_p)} / {cfg.rel(report_p)} do not validate: {probs}; the '
                                           'driver never overwrites them')
    missing = [m.get('job') for m in man.get('missing') or []]
    ack = missing_acknowledged(cfg, missing)
    if missing and ack is None:
        raise Alert('G3 missing episodes', f'the data manifest lists {len(missing)} missing episode(s): '
                                           f'{missing[:20]}; name every missing job id and the decision in '
                                           f'{cfg.rel(cfg.missing_ack_path)} to continue (GAP_AUDIT Sec. 6 item 5(c))')
    msha, rsha = P1.sha256_file(man_p), P1.sha256_file(report_p)
    st['files'] = {'data_manifest': cfg.rel(man_p), 'sha256': msha, 'report': cfg.rel(report_p), 'report_sha256': rsha,
                   'episodes': man.get('n_episodes'), 'missing': missing,
                   'missing_ack': cfg.rel(ack) if ack else None}
    also = (rsha,) + ((P1.sha256_file(ack),) if ack else ())
    r = ensure_recorded(cfg, ctx, 'p2_data', msha, lambda: p2_data_entry(cfg, rep, man, msha, rsha, jsha, ack),
                        also=also)
    if r is None:
        st.update(status='dry', note='data manifest written, not yet recorded')
        return 'dry'
    ent = phase_view(cfg)['entries'].get('p2_data')
    st['entry'] = {'line': ent['line'], 'when': ent['when']} if ent else {'cited': True}
    st.update(status='passed', note='P2 done: data manifest recorded')
    ctx.save()
    return 'done'


# ---------------------------------------------------------------------------------------------------- G4 P3 RL

def freeze_params(cfg, view):
    """The recorded tuning freeze as G4-G6 use it: {'sha256', 'entry', 'd', 'L_label', 'L_path', 'L_sha256'}."""
    sha, ent = recorded_freeze(cfg, view)
    doc = P1.read_json(cfg.freeze_path) or {}
    L, dd = doc.get('L_star') or {}, doc.get('d_star') or {}
    d = dd.get('d')
    if isinstance(d, bool) or not isinstance(d, int) or not L.get('envelope_path') \
            or not SHA_RE.fullmatch(str(L.get('envelope_sha256'))):
        raise Alert('tuning freeze', f'{cfg.rel(cfg.freeze_path)} names no d* or no L* envelope path and sha256 '
                                     f'(L_star {L}, d_star {dd})')
    return {'sha256': sha, 'entry': ent, 'd': d, 'L_label': L.get('label'), 'L_path': L['envelope_path'],
            'L_sha256': L['envelope_sha256']}


def recorded_data_manifest(cfg, view):
    """(sha256, document) of the P2 data manifest that the G3 entry cites; ALERT otherwise."""
    ent = view['entries'].get('p2_data')
    man_p = cfg.p2_outputs()[1]
    sha = P1.sha256_file(man_p) if man_p.is_file() else None
    if ent is None or sha is None or sha not in ent['shas']:
        raise Alert('P2 data manifest', f'{cfg.rel(man_p)} (sha256 {sha}) is not the data manifest the G3 entry cites '
                                        f'({"no G3 entry" if ent is None else "line " + str(ent["line"])})')
    return sha, P1.read_json(man_p)


def p3_blockers(cfg):
    """What keeps P3 (and the stress tests) off the CPU: a live runner of a watched queue, a closed-loop process, the
    P1 stage driver (P3 uses every core, PROTOCOL Sec. 8.1: the GPU is idle)."""
    out = [f'the runner of {q.queue_arg}' for q in cfg.watch_queues if runner_pid_alive(q)]
    if not out and cfg.closed_loop_active():
        out.append('a gpu_queue.py / CarlaUE4 process')
    if p1_driver_alive(cfg):
        out.append('the P1 stage driver')
    return out


def p3_options(cfg, ctx, view, man):
    """({case: option}, source) of the open cases of GAP_AUDIT Sec. 6 item 5 that p3_rl.py runs with an option other
    than 'stop'. The coordinating session's phase_driver/P3_OPEN_CASES.json ({"schema": P3_OPTIONS_SCHEMA, "options":
    {case: option}, "rationale": "..."}; ALERT if malformed); and case (c) 'proceed' when the P2 data manifest lists
    missing episodes that the G3 entry accepted (P2_MISSING_ACK.txt names every one and the entry cites it: the
    decision of item 5(c) was taken at G3), unless the file sets that case itself."""
    opts, src = {}, {'file': None, 'sha256': None, 'rationale': None, 'derived': None}
    path = cfg.p3_options_path
    given = {}
    if path.exists():
        doc = decision_doc(cfg, ctx, path, 'G4 open cases')
        probs = []
        if doc.get('schema') not in (None, P3_OPTIONS_SCHEMA):
            probs.append(f'schema {doc.get("schema")!r} (expected {P3_OPTIONS_SCHEMA})')
        given = doc.get('options')
        if not isinstance(given, dict) or not given:
            probs.append('no "options" object')
            given = {}
        for k, v in given.items():
            if k not in OPEN_CASES or v not in OPEN_CASES[k][:2]:
                probs.append(f'option {k}: {v!r} (cases {sorted(OPEN_CASES)}; each "stop" or its alternative)')
        if not isinstance(doc.get('rationale'), str) or not doc['rationale'].strip():
            probs.append('no rationale')
        if probs:
            raise Alert('G4 open cases', f'{cfg.rel(path)}: ' + '; '.join(probs), json.dumps(doc, indent=1)[:5000])
        opts.update({k: v for k, v in given.items() if v != 'stop'})
        src.update(file=cfg.rel(path), sha256=P1.sha256_file(path), rationale=doc['rationale'])
    missing = [m.get('job') for m in (man or {}).get('missing') or []]
    g3 = view['entries'].get('p2_data')
    ack = missing_acknowledged(cfg, missing)
    if missing and 'missing_episodes' not in given and ack is not None and g3 is not None \
            and P1.sha256_file(ack) in g3['shas']:
        opts['missing_episodes'] = 'proceed'
        src['derived'] = (f'--missing-episodes proceed: the {len(missing)} missing P2 episode(s) were accepted at G3 '
                          f'(`{cfg.rel(ack)}`, sha256 `{P1.sha256_file(ack)}`, entry "{label_of("p2_data")}")')
    return opts, src


def p3_flags(opts):
    return [x for k in sorted(opts) for x in (f'--{k.replace("_", "-")}', opts[k])]


def calibration_problems(cfg, doc, d_star):
    """[] if `doc` is the production calibration of p3_rl.py calibrate for this RL dataset and d*."""
    if not isinstance(doc, dict):
        return ['not readable JSON']
    probs = []
    t = doc.get('target') or {}
    if doc.get('schema') != CALIBRATION_SCHEMA or doc.get('kind') != 'production size':
        probs.append(f'schema / kind {doc.get("schema")!r} / {doc.get("kind")!r}')
    if (doc.get('probe') or {}).get('sizes') != list(CAL_SIZES):
        probs.append(f'probe sizes {(doc.get("probe") or {}).get("sizes")} (production: {list(CAL_SIZES)})')
    if t.get('d_star') != d_star or t.get('lengths') != cfg.rel(cfg.rl_freeze_dir / 'dataset'):
        probs.append(f'target d* {t.get("d_star")} / lengths {t.get("lengths")!r} (expected {d_star} / '
                     f'{cfg.rel(cfg.rl_freeze_dir / "dataset")!r})')
    n = (doc.get('recommendation') or {}).get('n_jobs')
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        probs.append(f'recommended n_jobs {n!r}')
    return probs


def p3_workers(cal):
    """(--n-jobs, note): the calibration's recommendation, capped when that many workers at the probe's peak RSS would
    exceed P3_MEMORY_SHARE of the memory available now (the 2026-11-12 OOM kill, validity_notes/oom_20261112.md)."""
    n = cal['recommendation']['n_jobs']
    per = (cal.get('memory') or {}).get('probe_max_rss_mb')
    avail = mem_available_mib()
    if isinstance(per, (int, float)) and per > 0 and avail:
        cap = max(1, int(P3_MEMORY_SHARE * avail // per))
        if cap < n:
            return cap, (f'capped from the recommended {n} to {cap}: {n} workers at the probe\'s peak RSS of {per:.0f} '
                         f'MB exceed {P3_MEMORY_SHARE:.0%} of the {avail:.0f} MiB available')
    return n, None


def p3_select_workers(cfg):
    """{family: n_jobs} with which the select stages ran (their stage records, host.n_jobs)."""
    out = {}
    for f in ARM_OF:
        rec = P1.read_json(cfg.rl_freeze_dir / 'stages' / f'select_{f}.json')
        out[f] = ((rec or {}).get('host') or {}).get('n_jobs')
    return out


def rl_freeze_problems(cfg, doc, freeze_sha, man_sha):
    """[] if `doc` is a production RL freeze of the recorded tuning freeze and P2 data manifest whose named files (the
    three networks among them) are at their recorded sha256."""
    if not isinstance(doc, dict):
        return ['not readable JSON']
    probs = []
    head = (doc.get('schema'), doc.get('variant'), doc.get('mode'), doc.get('frozen'))
    if head != (RL_FREEZE_SCHEMA, VARIANT, 'production', True):
        probs.append(f'schema / variant / mode / frozen {head}')
    if (doc.get('tuning_freeze') or {}).get('sha256') != freeze_sha:
        probs.append(f'made from another tuning freeze ({(doc.get("tuning_freeze") or {}).get("sha256")})')
    if (doc.get('p2_manifest') or {}).get('sha256') != man_sha:
        probs.append(f'made from another P2 data manifest ({(doc.get("p2_manifest") or {}).get("sha256")})')
    fams = doc.get('families') or {}
    if sorted(fams) != sorted(ARM_OF):
        probs.append(f'families {sorted(fams)}')
    for f, arm in ARM_OF.items():
        net = (fams.get(f) or {}).get('network') or {}
        p = cfg.path(str(net.get('path')))
        if net.get('arm') != arm or not net.get('name') or not p.is_file() \
                or P1.sha256_file(p) != net.get('file_sha256'):
            probs.append(f'{f}: network {net.get("path")} (arm {net.get("arm")}, sha256 {net.get("file_sha256")}) '
                         'missing or changed')
    files = doc.get('files') or {}
    changed = [k for k, h in sorted(files.items()) if not cfg.path(k).is_file() or P1.sha256_file(cfg.path(k)) != h]
    if not files or changed:
        probs.append(f'named files missing or changed: {changed[:10] or "no file list"}')
    return probs


def rl_entry(cfg, doc, sha, fz, man_sha, cal, cal_sha, workers, opts, osrc):
    fams = doc.get('families') or {}
    nets = '; '.join(f'`{ARM_OF[f]}` `{fams[f]["network"]["name"]}` (family {f}, `{fams[f]["network"]["path"]}`, '
                     f'file sha256 `{fams[f]["network"]["file_sha256"]}`)' for f in ARM_OF)
    ds = doc.get('dataset') or {}
    devs = doc.get('deviations') or []
    dev = 'none' if not devs else '; '.join(f'{d.get("stage")}: case {d.get("case")}, option {d.get("option")}'
                                            for d in devs)
    wk = ', '.join(f'{f} {n}' for f, n in workers.items())
    if cal is not None:
        rec = cal['recommendation']
        cal_txt = (f'`p3_rl.py calibrate` at the production sizes {list(CAL_SIZES)} on the choice-transition counts of '
                   f'`{cfg.rel(cfg.rl_freeze_dir / "dataset")}` with d* = {fz["d"]}: `{cfg.rel(cfg.p3_calibration)}` '
                   f'(sha256 `{cal_sha}`), recommended n_jobs {rec["n_jobs"]} (predicted select wall time '
                   f'{P1.fmt((rec.get("worst_case_wall_s") or 0) / 3600, 2)} h, worst case)')
    else:
        cal_txt = 'no production calibration file was found'
    if opts:
        opt_txt = ('; '.join(f'--{k.replace("_", "-")} {v} (case {OPEN_CASES[k][2]})' for k, v in sorted(opts.items()))
                   + (f', decided in `{osrc["file"]}` (sha256 `{osrc["sha256"]}`): {sentence(osrc["rationale"])}'
                      if osrc.get('file') else '.') + (f' {osrc["derived"]}.' if osrc.get('derived') else ''))
    else:
        opt_txt = 'none used (every case at its default "stop").'
    return (f'`{cfg.rel(cfg.rl_freeze_path)}` (sha256 `{sha}`), the RL freeze of Sec. 5.9, written by `p3_rl.py run` '
            f'(sha256 `{(doc.get("code_sha256") or {}).get("p3_rl.py")}`): d* = {doc.get("d_star")}, from the tuning '
            f'freeze `{cfg.rel(cfg.freeze_path)}` (sha256 `{fz["sha256"]}`) and the P2 data manifest '
            f'`{cfg.rel(cfg.p2_outputs()[1])}` (sha256 `{man_sha}`, entry "{label_of("p2_data")}"); '
            f'{ds.get("n_episodes")} episodes, {ds.get("n_transitions")} transitions, {ds.get("n_missing")} missing; '
            f'P_both label: {(doc.get("p_both") or {}).get("label")}. Deployed networks: {nets}. Workers: {cal_txt}; '
            f'the select stages ran with n_jobs {wk} (no stage parameter). Open cases of GAP_AUDIT Sec. 6 item 5: '
            f'{opt_txt} Deviations recorded in the freeze: {dev}. `p3_rl.py status`: every stage done and consistent; '
            f'the driver re-hashed the {len(doc.get("files") or {})} files the freeze names. P3 ran on every core at '
            'nice 10 while no closed-loop job ran (GPU idle). Entered when P3 ends (Sec. 8.1); the test freeze enters '
            'it again with the P4-P6 job files (Sec. 5.9). From this entry on `p3_rl.py` never recomputes a stage in '
            f'`{cfg.rel(cfg.rl_freeze_dir)}` (`p3_rl.frozen_citations`).')


def run_p3(cfg, ctx, name, args, timeout, what):
    """p3_rl.py <args> on every core at nice 10 (no closed-loop job runs). Exit 4 (an open case of GAP_AUDIT Sec. 6
    item 5 under its default 'stop'): ALERT naming the case, the coordinating session decides; another non-zero exit
    or the timeout: ALERT."""
    cmd = cfg.p3_cmd(*args)
    rc, out, err, log = run_long(ctx, cmd, timeout, name, cfg.heavy_prio, cfg.tool_env())
    if rc == 4:
        case, line = open_case_of(err)
        alt = OPEN_CASES[case][1] if case else '<alternative>'
        raise Alert('G4 open case', f'p3_rl.py {what} stopped at an open case of GAP_AUDIT Sec. 6 item 5 '
                                    f'{OPEN_CASES[case][2] if case else "(not named)"}, case {case!r}: {line}. The '
                                    'coordinating session decides: to continue with the audit\'s proposed default, '
                                    f'write {cfg.rel(cfg.p3_options_path)} as {{"schema": "{P3_OPTIONS_SCHEMA}", '
                                    f'"options": {{"{case}": "{alt}"}}, "rationale": "..."}} (passed to every later '
                                    'p3_rl.py run; the RL freeze entry cites the file and the freeze records the '
                                    'deviation); without it P3 does not continue', P1.both(out[-20000:], err[-20000:]),
                    cmd)
    if rc != 0:
        raise Alert('G4 p3_rl', f'p3_rl.py {what} exited {rc} (log {log}.out / .err)',
                    P1.both(out[-20000:], err[-20000:]), cmd)
    ctx.log(f'G4: p3_rl.py {what}: done\n' + out.rstrip()[-3000:])
    return out


def gate_g4(cfg, ctx):
    """G4 P3: dataset, calibration at the production sizes, the run with the recommended --n-jobs, status, the RL
    freeze validated and recorded. 'done', 'waiting' or 'dry'."""
    st = ctx.gate('G4')
    view = phase_view(cfg)
    rl_p = cfg.rl_freeze_path
    ent = view['entries'].get('rl_freeze')
    if ent is not None:
        sha = P1.sha256_file(rl_p) if rl_p.is_file() else None
        if sha not in ent['shas']:
            raise Alert('G4 RL freeze', f'{cfg.rel(rl_p)} (sha256 {sha}) is missing or differs from the RL freeze the '
                                        f'Sec. 13.2 entry (line {ent["line"]}) cites')
        st.update(status='passed', note='RL freeze recorded', entry={'line': ent['line'], 'when': ent['when']})
        return 'done'
    fz = freeze_params(cfg, view)
    man_sha, man = recorded_data_manifest(cfg, view)
    wait_for_tools(ctx, cfg.p3_rl_script)        # M2: a p3_rl.py of an earlier driver process ends first
    require_registered_code(cfg, ctx, 'G4')     # M4: p3_rl.py, framelease_v4/rl and the P2 gate sources
    opts, osrc = p3_options(cfg, ctx, view, man)
    flags = p3_flags(opts)
    st['files'] = {'rl_freeze': cfg.rel(rl_p), 'calibration': cfg.rel(cfg.p3_calibration), 'options': opts,
                   'options_file': osrc['file']}
    cal_exists = cfg.p3_calibration.exists()
    cal = P1.read_json(cfg.p3_calibration) if cal_exists else None
    if not rl_p.exists():
        blockers = p3_blockers(cfg)
        if blockers:
            st.update(status='waiting', note=f'P3 waits: {blockers} alive')
            ctx.add_attention(f'G4: P3 uses every core and needs the GPU idle; alive: {blockers}')
            return 'waiting'
        dataset = cfg.rl_freeze_dir / 'dataset'
        if not cal_exists:
            if cfg.dry_run:
                ctx.add_plan(f'G4: {P1.show(cfg.heavy_prio + cfg.p3_cmd("run", "--stop-after", "dataset", *flags))}; '
                             f'then p3_rl.py calibrate --sizes {",".join(map(str, CAL_SIZES))} --d-star {fz["d"]} '
                             f'--lengths-from {cfg.rel(dataset)} --out {cfg.rel(cfg.p3_calibration)}; then p3_rl.py '
                             'run --n-jobs <recommended>, p3_rl.py status, and the RL freeze recorded in Sec. 13.2')
                st.update(status='dry', note='P3 not started')
                return 'dry'
            P1.check_stop(ctx)
            st.update(status='running', note='P3: the dataset stage')
            ctx.save()
            run_p3(cfg, ctx, 'p3_dataset', ('run', '--stop-after', 'dataset', *flags), TIMEOUTS['p3_dataset'],
                   'run --stop-after dataset')
            crash_point(ctx, 'p3_dataset_done')
            cfg.p3_calibration.parent.mkdir(parents=True, exist_ok=True)
            st.update(note='P3: calibrate at the production sizes')
            ctx.save()
            run_p3(cfg, ctx, 'p3_calibrate', ('calibrate', '--sizes', ','.join(map(str, CAL_SIZES)), '--d-star',
                                              str(fz['d']), '--lengths-from', cfg.rel(dataset), '--out',
                                              cfg.rel(cfg.p3_calibration)), TIMEOUTS['p3_calibrate'], 'calibrate')
            cal = P1.read_json(cfg.p3_calibration)
            crash_point(ctx, 'p3_calibrated')
        probs = calibration_problems(cfg, cal, fz['d'])
        if probs:
            raise Alert('G4 calibration', f'{cfg.rel(cfg.p3_calibration)} is not the production calibration of this RL '
                                          f'dataset: {probs}; the driver never overwrites it (move it aside to '
                                          'calibrate again)')
        n_jobs, cap = p3_workers(cal)
        st['files'].update(n_jobs=n_jobs, n_jobs_note=cap)
        if cfg.dry_run:
            ctx.add_plan(f'G4: {P1.show(cfg.heavy_prio + cfg.p3_cmd("run", "--n-jobs", str(n_jobs), *flags))}'
                         + (f' ({cap})' if cap else '') + '; p3_rl.py status; record the RL freeze in Sec. 13.2')
            st.update(status='dry', note='calibrated; the P3 run not started')
            return 'dry'
        if cap:
            ctx.log(f'G4: --n-jobs {cap}')
        P1.check_stop(ctx)
        st.update(status='running', note=f'P3: p3_rl.py run --n-jobs {n_jobs}')
        ctx.save()
        run_p3(cfg, ctx, 'p3_run', ('run', '--n-jobs', str(n_jobs), *flags), TIMEOUTS['p3_run'],
               f'run --n-jobs {n_jobs}')
        crash_point(ctx, 'p3_run_done')
    if cfg.dry_run:
        ctx.add_plan(f'G4: p3_rl.py status; validate {cfg.rel(rl_p)}; record the RL freeze in Sec. 13.2')
        st.update(status='dry', note='RL freeze written, not yet recorded')
        return 'dry'
    P1.check_stop(ctx)
    cmd = cfg.p3_cmd('status')
    rc, out, err, log = run_long(ctx, cmd, TIMEOUTS['p3_status'], 'p3_status', cfg.low_prio, cfg.tool_env())
    if rc != 0:
        raise Alert('G4 p3_rl status', f'p3_rl.py status exited {rc} (0: every stage done and consistent; 3: '
                                       'incomplete; 1: inconsistent) after the RL freeze was written',
                    P1.both(out[-20000:], err[-20000:]), cmd)
    doc = P1.read_json(rl_p)
    probs = rl_freeze_problems(cfg, doc, fz['sha256'], man_sha)
    if probs:
        raise Alert('G4 RL freeze', f'{cfg.rel(rl_p)} does not validate: {probs}')
    sha = P1.sha256_file(rl_p)
    cal_ok = cal is not None and not calibration_problems(cfg, cal, fz['d'])
    cal_sha = P1.sha256_file(cfg.p3_calibration) if cal_ok else None
    workers = p3_select_workers(cfg)
    nets = [doc['families'][f]['network']['file_sha256'] for f in ARM_OF]
    also = tuple(nets) + ((cal_sha,) if cal_sha else ()) + ((osrc['sha256'],) if osrc.get('sha256') else ())
    st['files'].update(sha256=sha, calibration_sha256=cal_sha, workers=workers)
    r = ensure_recorded(cfg, ctx, 'rl_freeze', sha, lambda: rl_entry(cfg, doc, sha, fz, man_sha,
                                                                     cal if cal_ok else None, cal_sha, workers, opts,
                                                                     osrc), also=also)
    if r is None:
        st.update(status='dry', note='RL freeze written, not yet recorded')
        return 'dry'
    ent = phase_view(cfg)['entries'].get('rl_freeze')
    st['entry'] = {'line': ent['line'], 'when': ent['when']} if ent else {'cited': True}
    st.update(status='passed', note='P3 done: RL freeze recorded')
    ctx.save()
    return 'done'


# ---------------------------------------------------------------------------------------------------- G5 stress tests

def recorded_rl_freeze(cfg, view):
    """The RL freeze document that the G4 entry cites; ALERT otherwise."""
    ent = view['entries'].get('rl_freeze')
    rl_p = cfg.rl_freeze_path
    sha = P1.sha256_file(rl_p) if rl_p.is_file() else None
    if ent is None or sha is None or sha not in ent['shas']:
        raise Alert('RL freeze', f'{cfg.rel(rl_p)} (sha256 {sha}) is not the RL freeze the G4 entry cites')
    return P1.read_json(rl_p)


def rl_networks(cfg, doc):
    """The deployed networks of the RL freeze: [{'family', 'arm', 'name', 'path', 'file_sha256'}] in family order."""
    fams = doc.get('families') or {}
    return [{'family': f, 'arm': arm, **{k: (fams[f]['network'] or {}).get(k) for k in ('name', 'path', 'file_sha256')}}
            for f, arm in ARM_OF.items()]


def qnet_args(cfg, nets):
    """--qnet paths (absolute, one per file) of the deployed networks."""
    out = []
    for n in nets:
        p = str(cfg.path(n['path']))
        if p not in out:
            out.append(p)
    return out


def stress_problems(cfg, key, path, nets, L_sha):
    """(report, problems) of the registered stress report `path` of the G5 run `key` (test_freeze.stress_check's
    criteria, PROTOCOL Sec. 7.6): a registered run by the code of the tree now; S1 and S2 on the deployed networks of
    the RL freeze; S3 >= 1e5 sequences on the gate and the runtime with full coverage and 0 violations; S2 (both grids)
    0 admitted actions with bound >= D* and 0 violations, the registered grid with its 71 slack values; S1 the loads
    0 / 4 / 8 / 15, the lease on L*, no project process sharing the CPU."""
    doc = P1.read_json(path)
    if not isinstance(doc, dict):
        return doc, ['not readable JSON']
    test = {k: t for k, _, t, *_ in STRESS_RUNS}[key]
    probs = []
    if (doc.get('schema'), doc.get('test')) != (STRESS_SCHEMA, test) or doc.get('registered') is not True:
        probs.append(f'schema / test / registered {doc.get("schema")!r} / {doc.get("test")!r} / '
                     f'{doc.get("registered")!r}')
    if key == 's2_relative':
        if doc.get('supplementary') is not True or not str(doc.get('label')).startswith(SUPPLEMENTARY_LABEL):
            probs.append(f'not the supplementary S2 report: label {doc.get("label")!r}')
    elif doc.get('label') != f'registered {test} run (PROTOCOL Sec. 7.6)' or doc.get('supplementary'):
        probs.append(f'label {doc.get("label")!r}')
    code = (doc.get('provenance') or {}).get('code_sha256') or {}
    stale = [f for f, h in sorted(code.items()) if not cfg.path(f).is_file() or P1.sha256_file(cfg.path(f)) != h]
    if not code or stale:
        probs.append(f'made by other code than the tree\'s ({stale or "no code_sha256"})')
    names = {}
    for n in nets:
        names.setdefault(n['name'], set()).add(n['file_sha256'])

    def nets_problems(tested):
        if set(tested) != set(names) or any(tested[n] not in names[n] for n in tested):
            return [f'networks {tested} are not the deployed networks of the RL freeze']
        return []

    if test == 'S3':
        n = doc.get('n_sequences')
        if isinstance(n, bool) or not isinstance(n, int) or n < S3_MIN_SEQUENCES \
                or sorted(doc.get('targets') or {}) != ['gate', 'runtime']:
            probs.append(f'{n} sequences on {sorted(doc.get("targets") or {})} (>= {S3_MIN_SEQUENCES} on gate and '
                         'runtime)')
        if doc.get('pass') is not True or doc.get('violations_total') != 0 or doc.get('coverage_ok') is not True:
            probs.append(f'violations {doc.get("violations_total")} (must be 0), coverage_ok {doc.get("coverage_ok")}')
    elif test == 'S2':
        nw = doc.get('networks') or {}
        probs += nets_problems({n: (v or {}).get('file_sha256') for n, v in nw.items()})
        bound = {n: (v or {}).get('admitted_bound_ge_Dstar') for n, v in nw.items()}
        if doc.get('pass') is not True or doc.get('violations_total') != 0 or any(b != 0 for b in bound.values()):
            probs.append(f'admitted actions with bound >= D* {bound} (must be 0), violations '
                         f'{doc.get("violations_total")}')
        if key == 's2' and len(doc.get('slack_grid_s') or []) != 71:
            probs.append(f'{len(doc.get("slack_grid_s") or [])} slack values (Sec. 7.6: 71)')
    else:
        plan = doc.get('plan') or {}
        probs += nets_problems({(n or {}).get('name'): (n or {}).get('file_sha256')
                                for n in plan.get('networks') or []})
        loads = [(r or {}).get('load') for r in doc.get('per_load') or []]
        if loads != list(S1_LOADS):
            probs.append(f'loads {loads} (Sec. 7.6: {list(S1_LOADS)})')
        if (doc.get('envelope') or {}).get('sha256') != L_sha:
            probs.append(f'the lease ran on {doc.get("envelope")}, not on L* (sha256 {L_sha})')
        if doc.get('shared_cpu') is not False:
            probs.append('not run on an exclusive CPU (shared_cpu)')
    return doc, probs


def s1_blockers(cfg):
    """Processes of this project that S1 must not share the CPU with: p3_blockers, a p3_rl.py process and (in the
    project tree) every process whose command line carries a marker of stress_bench.BLOCKING_MARKERS."""
    out = p3_blockers(cfg) + [f'p3_rl.py pid {p}' for p in tool_pids(cfg.p3_rl_script)]
    if cfg.root == ROOT:
        me = os.getpid()
        for d in Path('/proc').iterdir():
            if d.name.isdigit() and int(d.name) != me:
                cmd = P1.pid_cmdline(d.name)
                if any(m in cmd for m in S1_BLOCKING_MARKERS):
                    out.append(f'pid {d.name}: {cmd.strip()[:120]}')
    return out


def s1_guard_load(cfg):
    doc = P1.read_json(cfg.s1_guard_path)
    if not isinstance(doc, dict) or doc.get('schema') != S1_GUARD_SCHEMA:
        doc = {'schema': S1_GUARD_SCHEMA, 'attempts': [], 'closed_series': []}
    return doc


def s1_guard_save(cfg, guard):
    guard['updated'] = P1.now_iso()
    cfg.driver_dir.mkdir(parents=True, exist_ok=True)
    P1.atomic_write(cfg.s1_guard_path, json.dumps(guard, indent=1, sort_keys=True, default=str) + '\n')


def s1_refused(cfg, ctx, st, guard, source, foreign, detail=None):
    """Record a refusal of S1 because of foreign CPU load (the driver's sample or stress_bench's own guard); after
    --s1-retries retries ALERT (the series is closed: a restart after the ALERT begins a new one)."""
    guard['attempts'].append({'time': P1.now_iso(), 'epoch': time.time(), 'outcome': 'refused_foreign_cpu',
                              'source': source, 'foreign_cpu': foreign, 'detail': detail})
    n = sum(1 for a in guard['attempts'] if a['outcome'] == 'refused_foreign_cpu')
    top = '; '.join(f'{p.get("pid")} {p.get("cpu_share")} core {str(p.get("cmdline"))[:60]}'
                    for p in (foreign or [])[:4])
    if n > cfg.s1_retries:
        guard['closed_series'].append({'closed': P1.now_iso(), 'reason': 'ALERT', 'attempts': guard['attempts']})
        guard['attempts'] = []
        s1_guard_save(cfg, guard)
        raise Alert('G5 S1 guard', f'the registered S1 was refused {n} times because of foreign CPU load ({source}; '
                                   f'{cfg.s1_retry_s:.0f} s apart; last: {top or detail}). S1 needs an exclusive CPU '
                                   '(PROTOCOL Sec. 7.6). Either reduce the load and move ALERT.txt aside (a new series '
                                   f'of {cfg.s1_retries + 1} attempts), or accept it: write '
                                   f'{cfg.rel(cfg.s1_accept_path)} with the reason (S1 then runs with '
                                   '--accept-foreign-cpu, recorded in the S1 report and the G5 entry)',
                    json.dumps(guard['closed_series'][-1], indent=1, default=str)[:20000])
    s1_guard_save(cfg, guard)
    st.update(status='waiting', note=f'S1 refused because of foreign CPU load ({n} of {cfg.s1_retries + 1} attempts); '
                                     f'next attempt after {cfg.s1_retry_s:.0f} s')
    ctx.add_attention(f'G5: S1 refused because of foreign CPU load ({source}: {top or detail}); attempt {n} of '
                      f'{cfg.s1_retries + 1}, the next one in {cfg.s1_retry_s:.0f} s')
    return 'waiting'


def ensure_s1(cfg, ctx, st, nets, fz):
    """The registered S1 under the exclusive-CPU guard: no process of this project alive (else wait, not counted);
    the foreign CPU sampled (recorded in s1_guard.json): load -> a refusal (retried every --s1-retry-s, ALERT after
    --s1-retries retries) unless S1_ACCEPT_FOREIGN_CPU.txt exists; then stress_bench.py s1 --registered, whose own
    refusals count the same way. 'ran', 'waiting' or 'dry'."""
    blockers = s1_blockers(cfg)
    if blockers:
        st.update(status='waiting', note=f'S1 waits for an exclusive CPU: {blockers[:5]}')
        ctx.add_attention(f'G5: S1 needs an exclusive CPU; alive: {blockers[:5]}')
        return 'waiting'
    guard = s1_guard_load(cfg)
    refused = [a for a in guard['attempts'] if a['outcome'] == 'refused_foreign_cpu']
    if refused and time.time() - refused[-1]['epoch'] < cfg.s1_retry_s:
        nxt = time.strftime('%H:%M:%S', time.localtime(refused[-1]['epoch'] + cfg.s1_retry_s))
        st.update(status='waiting', note=f'S1 refused {len(refused)} time(s) because of foreign CPU load; next '
                                         f'attempt after {nxt}')
        return 'waiting'
    accept = cfg.s1_accept_path.is_file()
    cmd = cfg.stress_cmd('s1', qnet_args(cfg, nets), fz['L_path'], accept)
    if cfg.dry_run:
        ctx.add_plan(f'G5: sample the foreign CPU, then {P1.show(cfg.heavy_prio + cmd)}')
        st.update(status='dry', note='S1 not run yet')
        return 'dry'
    P1.check_stop(ctx)
    sample = foreign_cpu(cfg)
    if sample and not accept:
        return s1_refused(cfg, ctx, st, guard, 'the driver\'s sample', sample)
    guard['attempts'].append({'time': P1.now_iso(), 'epoch': time.time(), 'outcome': 'started', 'source': 'driver',
                              'foreign_cpu': sample, 'accept_foreign_cpu': accept})
    s1_guard_save(cfg, guard)
    st.update(status='running', note='G5: S1 (CPU contention)')
    ctx.save()
    rc, out, err, log = run_long(ctx, cmd, TIMEOUTS['stress'], 'stress_s1', cfg.heavy_prio, cfg.tool_env())
    if rc == 0:
        guard['attempts'][-1].update(outcome='ran', finished=P1.now_iso())
        s1_guard_save(cfg, guard)
        crash_point(ctx, 'stress_s1_done')
        return 'ran'
    text = err + '\n' + out
    if 'refusing a registered run while these processes use CPU' in text or 'foreign CPU consumers alive' in text:
        guard['attempts'].pop()                       # the attempt is recorded as the refusal below
        lines = [ln.strip() for ln in text.splitlines() if 'core' in ln and ln.strip()[:1].isdigit()]
        return s1_refused(cfg, ctx, st, guard, 'stress_bench.py\'s guard', sample, '; '.join(lines[:4]) or
                          one_line(err[-300:]))
    if 'refusing to run while these processes are alive' in text:
        guard['attempts'][-1].update(outcome='blocked', detail=one_line(err[-600:]))
        s1_guard_save(cfg, guard)
        st.update(status='waiting', note='S1: stress_bench.py saw a process of this project')
        ctx.add_attention(f'G5: stress_bench.py s1 refused: {one_line(err[-400:])}')
        return 'waiting'
    guard['attempts'][-1].update(outcome='failed', exit=rc)
    s1_guard_save(cfg, guard)
    raise Alert('G5 stress', f'stress_bench.py s1 --registered exited {rc} (log {log}.out / .err)',
                P1.both(out[-20000:], err[-20000:]), cmd)


def a7_supplementary(view):
    """Review fix S4: True when the Amendment A7 entered in Sec. 13.2 is the variant A7b (a supplementary S2 grid
    relative to each state's slack floor: its text, from its title to the next amendment title or driver heading,
    names `s2 --grid relative` or the 'supplementary S2 grid'); False for A7a (the registered grid only) or no A7."""
    at = (view['amendments'].get('A7') or [None])[-1]
    if at is None:
        return False
    lines, (_, e) = view['lines'], view['sec']
    j = at
    while j < e and not AMEND_RE.match(lines[j]) and lines[j].strip() not in (HEADING, P1.HEADING) \
            and not lines[j].startswith(ANCHOR):
        j += 1
    return bool(A7B_RE.search(' '.join(' '.join(lines[at - 1:j]).split())))


def stress_runs(view):
    """The G5 runs (STRESS_RUNS): the supplementary relative grid only under Amendment A7b (a7_supplementary)."""
    sup = a7_supplementary(view)
    return tuple(r for r in STRESS_RUNS if r[0] != 's2_relative' or sup)


def stress_entry(cfg, reps, nets, guard, accept_sha):
    def ref(key):
        p, _ = reps[key]
        return f'`{cfg.rel(p)}` (sha256 `{P1.sha256_file(p)}`)'
    s3, s2, s1 = (reps[k][1] for k in ('s3', 's2', 's1'))
    s2r = reps['s2_relative'][1] if 's2_relative' in reps else None
    names = ', '.join(sorted({f'`{n["name"]}`' for n in nets}))
    tries = [a for a in (guard or {}).get('attempts') or []]
    closed = len((guard or {}).get('closed_series') or [])
    ran = next((a for a in reversed(tries) if a.get('outcome') == 'ran'), None)
    if ran is not None:
        fc = ran.get('foreign_cpu') or []
        g = (f'the driver\'s guard found no process of this project alive and sampled the foreign CPU before the run '
             f'({len(fc)} process(es) at >= {FOREIGN_CPU_MIN_SHARE:.0%} of one core over {FOREIGN_CPU_SAMPLE_S:.0f} s'
             f'{": " + ", ".join(str(p.get("comm")) for p in fc[:5]) if fc else ""}); '
             f'{len(tries) - 1} earlier attempt(s) in this series and {closed} closed series '
             f'(`{cfg.rel(cfg.s1_guard_path)}`, sha256 `{P1.sha256_file(cfg.s1_guard_path)}`)')
    else:
        g = 'the S1 report was not run by this driver (no guard record)'
    if s1.get('foreign_cpu_accepted'):
        g += (f'; foreign CPU load accepted by the coordinating session (`{cfg.rel(cfg.s1_accept_path)}`, sha256 '
              f'`{accept_sha}`; --accept-foreign-cpu)')
    sb = P1.sha256_file(cfg.path(cfg.stress_script)) if cfg.path(cfg.stress_script).is_file() else None
    return ('Stress tests of Sec. 7.6 before the test freeze (Secs. 7.6, 8.1), each `stress_bench.py <test> '
            f'--registered` (sha256 `{sb}`) on {cfg.stress_states} decision states, S1 and S2 on the deployed networks '
            f'{names} of the RL freeze (entry "{label_of("rl_freeze")}"). S3 {ref("s3")}: {s3.get("n_sequences")} '
            f'random event sequences on the commit gate and the runtime commit path, coverage ok, '
            f'{s3.get("violations_total")} violations of Eq. 9. S2 {ref("s2")}: {s2.get("n_swept")} states x '
            f'{len(s2.get("slack_grid_s") or [])} slack values, 0 admitted actions with bound >= D*, '
            f'{s2.get("violations_total")} violations. '
            + (f'Supplementary S2 relative to the slack floor (Amendment A7, the supplementary grid) '
               f'{ref("s2_relative")}: {s2r.get("n_swept")} states swept, 0 admitted actions with bound >= D*, '
               f'{s2r.get("violations_total")} violations; labelled "{SUPPLEMENTARY_LABEL}", never in place of the '
               'registered S2. ' if s2r is not None else '')
            + f'S1 {ref("s1")}: loads {"/".join(map(str, S1_LOADS))} busy processes, the lease on L* '
            f'(`{(s1.get("envelope") or {}).get("path")}`), every core at nice 10; {g}. The test freeze takes the S1, '
            'S2 and S3 reports' + ('; the supplementary report is entered here only.' if s2r is not None else '.'))


def gate_g5(cfg, ctx):
    """G5 stress tests: S3, S2 (registered grid), S2 (supplementary relative grid, under Amendment A7b only) and S1
    (exclusive-CPU guard), each once, registered, validated; the reports recorded. 'done', 'waiting' or 'dry'."""
    st = ctx.gate('G5')
    view = phase_view(cfg)
    ent = view['entries'].get('stress')
    if ent is None:
        wait_for_tools(ctx, cfg.stress_script)          # M2: a stress run of an earlier driver process ends first
    runs = stress_runs(view)
    found = {}
    for key, _sub, _test, pattern, _what in runs:
        hits = sorted(cfg.stress_dir.glob(pattern)) if cfg.stress_dir.is_dir() else []
        if len(hits) > 1:
            raise Alert('G5 stress', f'{len(hits)} reports {pattern} in {cfg.rel(cfg.stress_dir)}: the test freeze '
                                     f'takes one per test; move the extra ones aside ({[h.name for h in hits]})')
        found[key] = hits[0] if hits else None
    if ent is not None:
        bad = [k for k, p in found.items() if p is None or P1.sha256_file(p) not in ent['shas']]
        if bad:
            raise Alert('G5 stress', f'the stress reports {bad} are missing or differ from the Sec. 13.2 entry (line '
                                     f'{ent["line"]})')
        st.update(status='passed', note='stress reports recorded', entry={'line': ent['line'], 'when': ent['when']})
        return 'done'
    fz = freeze_params(cfg, view)
    nets = rl_networks(cfg, recorded_rl_freeze(cfg, view))
    st['files'] = {'runs': [r[0] for r in runs], 'a7_supplementary': len(runs) == len(STRESS_RUNS)}
    if any(found[k] is None for k, *_ in runs):
        require_registered_code(cfg, ctx, 'G5')       # M4: stress_bench.py
    reps = {}
    for key, _sub, _test, pattern, what in runs:
        if found[key] is None:
            if key == 's1':
                r = ensure_s1(cfg, ctx, st, nets, fz)
                if r != 'ran':
                    return r
            else:
                blockers = s1_blockers(cfg)
                cmd = cfg.stress_cmd(key, qnet_args(cfg, nets))
                if blockers:
                    st.update(status='waiting', note=f'{what} waits: {blockers[:5]} alive')
                    ctx.add_attention(f'G5: the stress tests run while no process of this project runs; alive: '
                                      f'{blockers[:5]}')
                    return 'waiting'
                if cfg.dry_run:
                    ctx.add_plan(f'G5: {P1.show(cfg.heavy_prio + cmd)}; then the remaining stress runs')
                    st.update(status='dry', note=f'{what} not run yet')
                    return 'dry'
                P1.check_stop(ctx)
                st.update(status='running', note=f'G5: {what}')
                ctx.save()
                rc, out, err, log = run_long(ctx, cmd, TIMEOUTS['stress'], f'stress_{key}', cfg.heavy_prio,
                                             cfg.tool_env())
                hits = sorted(cfg.stress_dir.glob(pattern)) if cfg.stress_dir.is_dir() else []
                if rc not in (0, 1) or not hits:
                    raise Alert('G5 stress', f'stress_bench.py {what} exited {rc} without a report (log {log}.out / '
                                             '.err)', P1.both(out[-20000:], err[-20000:]), cmd)
                crash_point(ctx, f'stress_{key}_done')
            hits = sorted(cfg.stress_dir.glob(pattern)) if cfg.stress_dir.is_dir() else []
            if len(hits) != 1:
                raise Alert('G5 stress', f'after the run of {what}: {len(hits)} reports {pattern}')
            found[key] = hits[0]
        doc, probs = stress_problems(cfg, key, found[key], nets, fz['L_sha256'])
        if probs:
            raise Alert('G5 stress', f'{cfg.rel(found[key])} ({what}) does not pass: {probs}. The driver never reruns '
                                     'or overwrites a registered report; Sec. 7.6: a violation in S2 or S3 stops the '
                                     'test freeze (fix the cause, move the report aside, restart)')
        reps[key] = (found[key], doc)
    shas = {k: P1.sha256_file(p) for k, (p, _) in reps.items()}
    guard = P1.read_json(cfg.s1_guard_path) if cfg.s1_guard_path.is_file() else None
    accept_sha = P1.sha256_file(cfg.s1_accept_path) if cfg.s1_accept_path.is_file() else None
    also = tuple(shas[k] for k in ('s3', 's2', 's2_relative') if k in shas) + \
        ((accept_sha,) if accept_sha and reps['s1'][1].get('foreign_cpu_accepted') else ())
    st['files'] = {k: {'report': cfg.rel(p), 'sha256': shas[k]} for k, (p, _) in reps.items()}
    r = ensure_recorded(cfg, ctx, 'stress', shas['s1'],
                        lambda: stress_entry(cfg, reps, nets, guard, accept_sha), also=also)
    if r is None:
        st.update(status='dry', note='stress reports written, not yet recorded')
        return 'dry'
    ent = phase_view(cfg)['entries'].get('stress')
    st['entry'] = {'line': ent['line'], 'when': ent['when']} if ent else {'cited': True}
    st.update(status='passed', note='stress tests recorded')
    ctx.save()
    return 'done'


# ---------------------------------------------------------------------------------------------------- G6 test freeze

def test_index_problems(cfg, idx):
    """(blocks with a job file, problems) of test_jobs.py's index.json: its blocks complete and clean (no problem, every
    dry run passed), each file at its sha256, name order = tier order (GAP_AUDIT E-1), the queue queue_p4."""
    if not isinstance(idx, dict):
        return [], ['not readable JSON']
    probs = []
    if (idx.get('schema'), idx.get('variant')) != (TEST_INDEX_SCHEMA, VARIANT):
        probs.append(f'schema / variant {idx.get("schema")!r} / {idx.get("variant")!r}')
    if idx.get('queue') != cfg.p4_queue.queue_arg or idx.get('cross_block_problems'):
        probs.append(f'queue {idx.get("queue")!r}, cross-block problems {idx.get("cross_block_problems")}')
    blocks = [b for b in idx.get('blocks') or [] if isinstance(b, dict) and b.get('job_file')]
    tiers, names = [b.get('tier') for b in blocks], [Path(b['job_file']).name for b in blocks]
    if not blocks or tiers != sorted(tiers) or names != sorted(names):
        probs.append(f'blocks {names} (tiers {tiers}): none, or name order is not tier order')
    for b in blocks:
        for k in ('job_file', 'stage_spec', 'check'):
            p = cfg.path(str(b.get(k)))
            if not p.is_file() or P1.sha256_file(p) != b.get(f'{k}_sha256'):
                probs.append(f'{b.get(k)} missing or not at the sha256 of the index')
        chk = P1.read_json(cfg.path(str(b.get('check'))))
        if not isinstance(chk, dict) or chk.get('schema') != TEST_CHECK_SCHEMA or chk.get('problems') \
                or chk.get('all_dry_runs_ok') is not True:
            probs.append(f'{b.get("check")}: a problem, or not every dry run passed')
    return blocks, probs


def frozen_job_files(cfg, rec):
    """[(job file, sha256, tier)] of the test-freeze record, in its block order; ALERT unless that is name order =
    tier order (a cut takes the bottom tiers first, PROTOCOL Sec. 10.2)."""
    blocks = [b for b in ((rec or {}).get('job_files') or {}).get('blocks') or [] if b.get('job_file')]
    out = [(cfg.path(b['job_file']), b.get('job_file_sha256'), b.get('tier')) for b in blocks]
    names, tiers = [p.name for p, _, _ in out], [t for _, _, t in out]
    if not out or names != sorted(names) or tiers != sorted(tiers):
        raise Alert('G6 test freeze', f'the test-freeze record names the job files {names} (tiers {tiers}): none, or '
                                      'name order is not tier order')
    return out


def g6_head(cfg, rec, rsha, msha, idx_sha, n_jobs, detail):
    man = rec.get('manifest') or {}
    return (f'The test freeze (Secs. 3.3 rule 4, 5.9, 7.6, 8.1; GAP_AUDIT Sec. 3.5 G-2, G-3), recorded by the phase '
            f'driver: `test_freeze.py --write` wrote `{cfg.rel(cfg.test_freeze_paths()[0])}` (sha256 `{rsha}`) and its '
            f'manifest `{cfg.rel(cfg.test_freeze_paths()[1])}` ({man.get("n_files")} files, sha256 `{msha}`) after '
            f'`source linux/env.sh && CUDA_VISIBLE_DEVICES= test_jobs.py --check --write` (index '
            f'`{cfg.rel(cfg.test_index_path())}`, sha256 `{idx_sha}`; every line checked with its --dry-run) and '
            f'`registration.py --verify` ({detail}). Nested below: the entry text that `test_freeze.py --entry` '
            'printed, unchanged except for its line breaks. After this entry is sealed: `test_freeze.py --verify`; '
            f'the {n_jobs} job files copied in name order (= tier order) into `{cfg.rel(cfg.p4_queue.jobs_d)}`; '
            f'`test_freeze.py --verify` again (the copies); then the runner of `{cfg.p4_queue.queue_arg}` launched in '
            'a dedicated systemd user scope (`systemd-run --user --scope -p OOMPolicy=continue bash '
            'framelease_v4/protocol/launch_queue.sh`).')


def run_test_freeze(cfg, ctx, flag, name, crash=None):
    cmd = cfg.test_freeze_cmd(flag)
    rc, out, err, log = run_long(ctx, cmd, TIMEOUTS['test_freeze'], name, cfg.low_prio, cfg.tool_env(),
                                 terminate_on_stop=False)
    if rc != 0:
        what = {1: 'a check failed or a file changed', 2: 'refused'}.get(rc, 'unexpected')
        raise Alert('G6 test_freeze', f'test_freeze.py {flag} exited {rc} ({what}; log {log}.out / .err)',
                    P1.both(out[-20000:], err[-20000:]), cmd)
    if crash:
        crash_point(ctx, crash)
    return out


def write_p4_queued(cfg, ctx, rsha, frozen, verify_out):
    doc = {'schema': P4_QUEUED_SCHEMA, 'written': P1.now_iso(), 'variant': VARIANT, 'queue': cfg.p4_queue.queue_arg,
           'test_freeze_record_sha256': rsha,
           'copies': [{'job_file': cfg.rel(src), 'copy': cfg.rel(cfg.p4_queue.jobs_d / src.name), 'sha256': want,
                       'tier': tier} for src, want, tier in frozen],
           'verify': verify_out.strip()[-3000:]}
    P1.atomic_write(cfg.p4_queued_path, json.dumps(doc, indent=1, sort_keys=True) + '\n')
    ctx.log(f'G6: {len(frozen)} P4-P6 job files queued in {cfg.p4_queue.queue_arg} and verified; '
            f'{cfg.rel(cfg.p4_queued_path)} written')
    crash_point(ctx, 'p4_queued')


def gate_g6(cfg, ctx):
    """G6 test freeze: the P4-P6 job files (once), the test freeze written and recorded with the entry text
    test_freeze.py prints, verified, the job files copied in tier order into queue_p4/jobs.d, verified again, the
    runner launched. 'done', 'waiting' or 'dry'."""
    st = ctx.gate('G6')
    view = phase_view(cfg)
    q = cfg.p4_queue
    rec_p, man_p = cfg.test_freeze_paths()
    idx_p = cfg.test_index_path()
    ent = view['entries'].get('test_freeze')
    if ent is None:
        wait_for_tools(ctx, cfg.test_jobs_script, cfg.test_freeze_script)     # M2: no writer of an earlier process
        queued = sorted(q.jobs_d.glob('*.jsonl')) if q.jobs_d.is_dir() else []
        if queued:
            raise Alert('G6 test freeze', f'{cfg.rel(q.jobs_d)} holds job files ({[p.name for p in queued]}) before '
                                          'the test freeze is recorded (PROTOCOL Secs. 3.3 rule 4, 8.1)')
        require_registered_code(cfg, ctx, 'G6')     # M4: test_jobs.py, test_freeze.py, check_smoke_ext.py, arms_ext
        if not idx_p.exists():
            if cfg.dry_run:
                ctx.add_plan(f'G6: {P1.show(cfg.low_prio + cfg.test_jobs_cmd())}; test_freeze.py --write and --entry; '
                             'record the test freeze in Sec. 13.2; test_freeze.py --verify; copy the job files into '
                             f'{cfg.rel(q.jobs_d)}/ in tier order; test_freeze.py --verify; launch the runner')
                st.update(status='dry', note='P4-P6 job files not generated yet')
                return 'dry'
            P1.check_stop(ctx)
            st.update(status='running', note='G6: test_jobs.py --check --write')
            ctx.save()
            cmd = cfg.test_jobs_cmd()
            rc, out, err, log = run_long(ctx, cmd, TIMEOUTS['test_jobs'], 'test_jobs', cfg.low_prio, cfg.tool_env(),
                                         terminate_on_stop=False)
            if rc != 0:
                what = {1: 'a check failed', 2: 'refused'}.get(rc, 'unexpected')
                raise Alert('G6 test_jobs', f'test_jobs.py --check --write exited {rc} ({what}; log {log}.out / .err)',
                            P1.both(out[-20000:], err[-20000:]), cmd)
            crash_point(ctx, 'test_jobs_written')
        blocks, probs = test_index_problems(cfg, P1.read_json(idx_p))
        if probs:
            raise Alert('G6 test_jobs', f'{cfg.rel(idx_p)} does not validate: {probs[:8]}; the driver never '
                                        'regenerates the job files over existing ones')
        ok, detail = verify_registration(cfg, ctx, strict_map(cfg, sealed_baseline(cfg, ctx) or {}))
        if not ok:
            if 'registered file(s) differ' in detail:
                raise Alert('G6 test freeze', f'before the test freeze: {detail} (no test freeze before an amendment '
                                              'restores or registers them, test_freeze.py procedure)')
            st.update(status='waiting', note=f'the seal does not verify: {detail}')
            ctx.add_attention(f'G6: the seal does not verify: {detail}')
            return 'waiting'
        if cfg.dry_run:
            ctx.add_plan(f'G6: {P1.show(cfg.low_prio + cfg.test_freeze_cmd("--write"))}, then --entry; record the test '
                         f'freeze in Sec. 13.2; --verify; copy {len(blocks)} job files into {cfg.rel(q.jobs_d)}/; '
                         '--verify; launch the runner')
            st.update(status='dry', note='P4-P6 job files written; the test freeze not yet written')
            return 'dry'
        P1.check_stop(ctx)
        st.update(status='running', note='G6: test_freeze.py --write')
        ctx.save()
        run_test_freeze(cfg, ctx, '--write', 'test_freeze_write', crash='test_freeze_written')
        printed = run_test_freeze(cfg, ctx, '--entry', 'test_freeze_entry')
        rec = P1.read_json(rec_p)
        rsha = P1.sha256_file(rec_p) if rec_p.is_file() else None
        msha = P1.sha256_file(man_p) if man_p.is_file() else None
        if not isinstance(rec, dict) or rec.get('schema') != TEST_FREEZE_SCHEMA \
                or (rec.get('manifest') or {}).get('sha256') != msha:
            raise Alert('G6 test freeze', f'{cfg.rel(rec_p)} is not a test-freeze record naming {cfg.rel(man_p)} '
                                          f'(sha256 {msha})')
        lines = printed.rstrip('\n').split('\n')
        try:
            nested, _ = nest_entry_lines(lines)
        except ValueError as e:
            raise Alert('G6 test freeze', f'the entry test_freeze.py --entry printed has another form: {e}', printed)
        if rsha not in printed or msha not in printed:
            raise Alert('G6 test freeze', 'the entry test_freeze.py --entry printed does not cite the written record '
                                          f'(sha256 {rsha}) and its manifest (sha256 {msha})', printed)
        frozen = frozen_job_files(cfg, rec)
        idx_sha = P1.sha256_file(idx_p)
        st['files'] = {'record': cfg.rel(rec_p), 'sha256': rsha, 'manifest': cfg.rel(man_p), 'manifest_sha256': msha,
                       'index': cfg.rel(idx_p), 'index_sha256': idx_sha}
        r = ensure_recorded(cfg, ctx, 'test_freeze', rsha,
                            lambda: g6_head(cfg, rec, rsha, msha, idx_sha, len(frozen), detail),
                            also=(msha, idx_sha), tail=lambda: nested)
        if r is None:
            st.update(status='dry', note='test freeze written, not yet recorded')
            return 'dry'
        view = phase_view(cfg)
        ent = view['entries'].get('test_freeze')
    rsha = P1.sha256_file(rec_p) if rec_p.is_file() else None
    if ent is None or rsha not in ent['shas']:
        raise Alert('G6 test freeze', f'{cfg.rel(rec_p)} (sha256 {rsha}) is missing or not the record the Sec. 13.2 '
                                      'entry cites')
    st['entry'] = {'line': ent['line'], 'when': ent['when']}
    frozen = frozen_job_files(cfg, P1.read_json(rec_p))
    copied_now = False
    done = P1.read_json(cfg.p4_queued_path)
    if isinstance(done, dict) and done.get('schema') == P4_QUEUED_SCHEMA:
        if done.get('test_freeze_record_sha256') != rsha:
            raise Alert('G6 test freeze', f'{cfg.rel(cfg.p4_queued_path)} names another test-freeze record')
        bad = [src.name for src, want, _ in frozen
               if not (q.jobs_d / src.name).is_file() or P1.sha256_file(q.jobs_d / src.name) != want]
        if bad:
            raise Alert('G6 P4-P6 queue', f'the queued job files {bad} in {cfg.rel(q.jobs_d)} are missing or differ '
                                          'from the test freeze')
    else:
        wait_for_tools(ctx, cfg.test_freeze_script)
        require_registered_code(cfg, ctx, 'G6')
        if cfg.dry_run:
            ctx.add_plan(f'G6: test_freeze.py --verify; copy {[s.name for s, _, _ in frozen]} into '
                         f'{cfg.rel(q.jobs_d)}/ in this order; test_freeze.py --verify; launch the runner')
            st.update(status='dry', note='recorded; the job files not yet queued')
            return 'dry'
        P1.check_stop(ctx)
        run_test_freeze(cfg, ctx, '--verify', 'test_freeze_verify')
        for src, want, _tier in frozen:
            copied_now = (copy_job_file(cfg, ctx, src, q, want, 'G6 P4-P6') == 'copied') or copied_now
        out = run_test_freeze(cfg, ctx, '--verify', 'test_freeze_verify_copies')
        write_p4_queued(cfg, ctx, rsha, frozen, out)
    qs = P1.queue_status(q)
    st['progress'] = {'jobs': qs['jobs'], 'final': qs['final'], 'pending': len(qs['pending'])}
    if qs['last_runner_start'] is None and qs['runner_exit'] is None and not qs['runner_alive']:
        r = ensure_runner(cfg, ctx, q, copied_now, min_free_gib=MIN_FREE_GIB.get(q.name), qs=qs)
        if r not in ('launched', 'running'):
            st.update(status='waiting' if r != 'dry' else 'dry', note=f'P4-P6 queued; the runner is not launched ({r})')
            return 'waiting' if r != 'dry' else 'dry'
    st.update(status='passed', note=f'test freeze recorded; P4-P6 queued in {q.queue_arg}, runner launched')
    ctx.save()
    return 'done'


# ---------------------------------------------------------------------------------------------------- G7 P4-P6 health

def p4_queued_copies(cfg):
    """{job file name: {'job_file', 'copy', 'sha256', 'tier'}} of phase_driver/P4_QUEUED.json (G6: the registered
    P4-P6 job files copied into queue_p4/jobs.d); ALERT if it is missing or malformed."""
    doc = P1.read_json(cfg.p4_queued_path)
    copies = doc.get('copies') if isinstance(doc, dict) and doc.get('schema') == P4_QUEUED_SCHEMA else None
    if not isinstance(copies, list) or not copies \
            or any(not isinstance(c, dict) or not c.get('copy') or not SHA_RE.fullmatch(str(c.get('sha256')))
                   for c in copies):
        raise Alert('G7 P4-P6', f'{cfg.rel(cfg.p4_queued_path)} is missing or malformed although G6 passed')
    return {Path(c['copy']).name: c for c in copies}


def p4_progress(qs, copies):
    """The job health of queue_p4 for state.json (PROTOCOL Sec. 9.11): per job file the number of jobs and of jobs with
    a final runner record, the runner's state. No outcome, metric or route of a run is read or summarized."""
    per = {name: {'tier': (copies.get(name) or {}).get('tier'), 'jobs': f['jobs'], 'final': f['final'],
                  'registered': name in copies} for name, f in sorted(qs['job_files'].items())}
    return {'jobs': qs['jobs'], 'final': qs['final'], 'pending': len(qs['pending']), 'per_job_file': per,
            'runner_alive': qs['runner_alive'], 'stop_file': qs['stop_file'], 'pause_file': qs['pause_file'],
            'checked': P1.now_iso()}


def gate_g7(cfg, ctx):
    """G7 P4-P6 (tiers 3-6 in queue_p4): job health only (PROTOCOL Sec. 9.11: job health, timing and disk; no
    test-route result is read and nothing is summarized across arms). The runner rules of ensure_runner, the disk,
    the progress per job file in state.json. 'done' once every job in jobs.d is final and no runner holds the queue,
    else 'waiting'."""
    st = ctx.gate('G7')
    q = cfg.p4_queue
    copies = p4_queued_copies(cfg)
    qs = P1.queue_status(q)
    ctx.state['queue'] = P1.queue_summary(qs)
    st['progress'] = p4_progress(qs, copies)
    if not cfg.dry_run:
        st['times'].setdefault('started', P1.now_iso())
    if not qs['jobs']:
        raise Alert('G7 P4-P6', f'{cfg.rel(q.jobs_d)} holds no job although G6 queued {len(copies)} job files')
    extra = sorted(n for n in qs['job_files'] if n not in copies)
    if extra:
        ctx.add_attention(f'G7: {cfg.rel(q.jobs_d)} holds job files that the test freeze does not name: {extra}; the '
                          'analysis freeze (G8) covers the registered job files only and refuses while they are there')
    if qs['pending']:
        if qs['stop_file'] and qs['runner_alive']:
            ctx.add_attention(f'{q.queue_arg}/STOP exists: the runner starts no new job and exits (the disk '
                              'watchdog\'s or the user\'s file; the driver never removes it)')
        if not getattr(ctx, 'launched_now', False):
            ensure_runner(cfg, ctx, q, copied_now=False, qs=qs)
        disk_health(cfg, ctx)
        st.update(status='running', note=f'{qs["final"]} of {qs["jobs"]} P4-P6 jobs final (job health only, PROTOCOL '
                                         'Sec. 9.11)')
        return 'waiting'
    if qs['runner_alive'] or P1.runner_lock_held(q):
        st.update(status='waiting', note=f'every P4-P6 job is final ({qs["jobs"]}); waiting for the runner to exit')
        return 'waiting'
    if 'all_final' not in st['times'] and not cfg.dry_run:
        st['times']['all_final'] = P1.now_iso()
        ctx.log(f'G7: every P4-P6 job is final ({qs["jobs"]} jobs in {len(qs["job_files"])} job files) and the runner '
                'has exited')
    st.update(status='passed', note=f'every P4-P6 job is final ({qs["jobs"]} jobs); the runner has exited')
    return 'done'


# ------------------------------------------------------------------------------------------------ G8 analysis freeze

def analysis_code_files(cfg):
    """{path: sha256 or None} of the analysis modules that an analysis-freeze record freezes (interim_guard
    ANALYSIS_MODULES, in the directory of --analyze-code)."""
    d = cfg.analyze_code.parent
    return {cfg.rel(d / m): (P1.sha256_file(d / m) if (d / m).is_file() else None) for m in ANALYSIS_MODULES}


def analysis_registration(cfg, view):
    """([wait reasons], {path: sha256} of the analysis modules and analyze_v4.py, the Sec. 13.2 line that cites
    analyze_v4.py). G8 needs analyze_v4.py cited in Sec. 13.2 by its current sha256 (the coordinating session's
    amendment that registers the analysis code before the analysis freeze, Sec. 9.12) and every analysis module at a
    sha256 that PROTOCOL.md cites (Amendment A3 or a later amendment)."""
    waits, code = [], analysis_code_files(cfg)
    a = cfg.analyze_code
    a_sha = P1.sha256_file(a) if a.is_file() else None
    line = None
    if a_sha is None:
        waits.append(f'{cfg.rel(a)} does not exist yet')
    else:
        s, e = view['sec']
        line = next((i + 1 for i in range(s, e) if a_sha in view['lines'][i]), None)
        if line is None:
            waits.append(f'Sec. 13.2 does not cite {cfg.rel(a)} (sha256 {a_sha}): the amendment that registers the '
                         'analysis code (PROTOCOL Sec. 9.12) is not entered yet')
    unreg = [p for p, h in code.items() if h is None or h not in view['text']]
    if unreg:
        waits.append(f'the analysis modules {unreg} are missing or at a sha256 that PROTOCOL.md does not cite (not '
                     'registered)')
    return waits, {**code, cfg.rel(a): a_sha}, line


def citing_amendment(view, line):
    """The id of the amendment whose paragraph holds the Sec. 13.2 line `line` (1-based): the nearest
    '**Amendment A<n>' title at or above it, before a driver heading; None otherwise. An entry names the amendment, not
    a line number: a line after the driver's block moves when the entry is inserted."""
    s, _ = view['sec']
    for i in range(line - 1, s - 1, -1):
        ln = view['lines'][i]
        m = AMEND_RE.match(ln)
        if m:
            return m.group('id')
        if ln.strip() in (HEADING, P1.HEADING):
            return None
    return None


def analysis_dirs(cfg):
    d = cfg.analysis_dir
    return sorted(p for p in d.glob('final_*') if p.is_dir()) if d.is_dir() else []


def analysis_target(cfg):
    """(directory, record, force) of the analysis freeze: the one outputs/framelease_v4/analysis/final_<stamp>/. An
    existing one is reused: with its record, or (an aggregation stopped before it wrote the record) redone there with
    --force; else a new final_<stamp>. ALERT for more than one (the driver makes one analysis freeze)."""
    dirs = analysis_dirs(cfg)
    if len(dirs) > 1:
        raise Alert('G8 analysis freeze', f'{len(dirs)} directories final_* in {cfg.rel(cfg.analysis_dir)} '
                                          f'({[d.name for d in dirs]}): the driver makes one analysis freeze; move the '
                                          'extra ones aside after checking them')
    if dirs:
        d = dirs[0]
        rec = d / ANALYSIS_RECORD
        return d, rec, not rec.exists() and any((d / n).exists() for n in AGG_OUTPUT_FILES)
    d = cfg.analysis_dir / f'final_{time.strftime("%Y%m%dT%H%M%S")}'
    return d, d / ANALYSIS_RECORD, False


def registered_p4_jobs(cfg, copies):
    """({copy: sha256}, {job id: copy}) of the registered P4-P6 job files in queue_p4/jobs.d (P4_QUEUED.json); ALERT
    if jobs.d holds another job file or a copy is missing or changed (the analysis freeze covers exactly the job
    files of the test freeze)."""
    q = cfg.p4_queue
    names = sorted(p.name for p in q.jobs_d.glob('*.jsonl')) if q.jobs_d.is_dir() else []
    extra = [n for n in names if n not in copies]
    if extra:
        raise Alert('G8 analysis freeze', f'{cfg.rel(q.jobs_d)} holds job files that the test freeze does not name '
                                          f'({extra}): the analysis freeze covers the registered P4-P6 job files only; '
                                          'an amendment decides (move them aside or register them), then restart')
    bad = [n for n, c in copies.items()
           if not cfg.path(c['copy']).is_file() or P1.sha256_file(cfg.path(c['copy'])) != c['sha256']]
    if bad:
        raise Alert('G8 analysis freeze', f'the queued job files {bad} are missing or differ from the test freeze')
    files, ids = {}, {}
    for c in copies.values():
        files[c['copy']] = c['sha256']
        for i in P1.job_ids(cfg.path(c['copy'])):
            ids[i] = c['copy']
    return files, ids


def analysis_record_problems(cfg, doc, want_files, job_ids, code):
    """[] if `doc` is the analysis-freeze record of the registered P4-P6 job files (the criteria of
    interim_guard.record_problems, checked by the driver): schema, freeze time, trigger 'all_final' without a cut (the
    driver freezes when every job is final), the job files = the queue_p4 copies at their registered sha256, every job
    line once with a final outcome of its own job file, the analysis code = the registered modules on disk, a
    route-split sha256."""
    if not isinstance(doc, dict) or doc.get('schema') != ANALYSIS_FREEZE_SCHEMA:
        return [f'not an analysis-freeze record (schema {ANALYSIS_FREEZE_SCHEMA})']
    probs = []
    if not doc.get('frozen'):
        probs.append('no freeze time')
    if doc.get('trigger') != 'all_final' or doc.get('cut_amendment'):
        probs.append(f'trigger {doc.get("trigger")!r}, cut {doc.get("cut_amendment")!r} (the driver freezes when every '
                     'job is final, without a cut)')
    if doc.get('job_files') != want_files:
        probs.append(f'job files {doc.get("job_files")} are not the registered P4-P6 copies {want_files}')
    jobs = doc.get('jobs') if isinstance(doc.get('jobs'), dict) else {}
    if set(jobs) != set(job_ids):
        probs.append(f'{len(jobs)} jobs in the record, {len(job_ids)} job lines in the job files '
                     f'(differences: {sorted(set(jobs) ^ set(job_ids))[:5]})')
    bad = sorted(j for j, v in jobs.items() if not isinstance(v, dict) or v.get('outcome') not in FINAL_OUTCOMES
                 or v.get('job_file') != job_ids.get(j))
    if bad:
        probs.append(f'{len(bad)} jobs without a final outcome {FINAL_OUTCOMES} or of another job file: {bad[:5]}')
    want_code = {p: h for p, h in code.items() if p != cfg.rel(cfg.analyze_code)}
    if doc.get('analysis_code') != want_code:
        probs.append(f'the analysis code of the record {doc.get("analysis_code")} is not the registered code on disk '
                     f'{want_code}')
    if not SHA_RE.fullmatch(str(doc.get('route_split_sha256'))):
        probs.append(f'route split sha256 {doc.get("route_split_sha256")!r}')
    return probs


def sha256sums_problems(cfg, out_dir, sums):
    """Review fix S3: `sha256sum -c` of the aggregation's SHA256SUMS ([] if it holds): every line '<sha256>  <name>'
    names a file of `out_dir` that has that sha256, and the list is not empty."""
    try:
        lines = [ln for ln in sums.read_text(encoding='utf-8').splitlines() if ln.strip()]
    except (OSError, UnicodeDecodeError) as e:
        return [f'{cfg.rel(sums)} is not readable: {e}']
    probs = []
    for ln in lines:
        m = re.fullmatch(r'([0-9a-f]{64}) [ *](.+)', ln)
        name = Path(m.group(2)) if m else None
        if name is None or name.is_absolute() or '..' in name.parts:
            probs.append(f'{cfg.rel(sums)}: the line {ln[:100]!r} is not "<sha256>  <file of the directory>"')
            continue
        f = out_dir / name
        have = P1.sha256_file(f) if f.is_file() else None
        if have != m.group(1):
            probs.append(f'{cfg.rel(sums)}: {name} is {"missing" if have is None else "at sha256 " + have}, not '
                         f'{m.group(1)}')
    if not lines:
        probs.append(f'{cfg.rel(sums)} lists no file')
    return probs


def analysis_entry(cfg, view, rec_p, rsha, doc, out_dir, sums_sha, code, a_line, copies):
    jobs = doc.get('jobs') or {}
    a_amend = citing_amendment(view, a_line) if a_line else None
    status = ', '.join(f'{o} {sum(1 for v in jobs.values() if v.get("outcome") == o)}' for o in FINAL_OUTCOMES)
    files = '; '.join(f'`{c["copy"]}` (tier {c.get("tier")}, sha256 `{c["sha256"]}`)'
                      for c in sorted(copies.values(), key=lambda c: c['copy']))
    a_rel = cfg.rel(cfg.analyze_code)
    mods = ', '.join(f'`{Path(p).name}` (sha256 `{h}`)' for p, h in code.items() if p != a_rel)
    tf = cfg.test_freeze_paths()[0]
    tf_sha = P1.sha256_file(tf) if tf.is_file() else None
    return (f'The analysis freeze of Sec. 9.12: every registered job of tiers 3-6 was final and the runner of '
            f'`{cfg.p4_queue.queue_arg}` had exited; `aggregate_v4.py --write-freeze-record` wrote `{cfg.rel(rec_p)}` '
            f'(sha256 `{rsha}`; trigger {doc.get("trigger")}, frozen {doc.get("frozen")}). Job status: {len(jobs)} '
            f'jobs of the {len(copies)} job files of the test freeze (entry "{label_of("test_freeze")}", record '
            f'`{cfg.rel(tf)}` sha256 `{tf_sha}`): {files}; outcomes {status}; no job cut. Analysis code frozen by the '
            f'record: {mods}; '
            f'the analysis script `{a_rel}` (sha256 `{code.get(a_rel)}`) is registered in Sec. 13.2 by '
            + (f'Amendment {a_amend}. ' if a_amend else 'an entry that cites its sha256. ') +
            f'Route split sha256 `{doc.get("route_split_sha256")}`. The aggregation that made the record ran without '
            '--arm-summary and without --analysis-freeze: every test-route row stayed health-only and no cross-arm '
            f'summary was made (Sec. 9.11). Its outputs and its guard log are in `{cfg.rel(out_dir)}` (`SHA256SUMS` '
            f'sha256 `{sums_sha}`). The record is valid from this entry on (its sha256 in Sec. 13 of the sealed '
            'PROTOCOL.md, `interim_guard.load_freeze`); the confirmatory analysis writes its outputs into the same '
            f'directory with a sha256 manifest. The phase driver stops after this entry (`{cfg.rel(cfg.done_path)}`).')


def run_aggregate(cfg, ctx, out_dir, rec_p, force):
    """aggregate_v4.py --write-freeze-record (G8), at the tool priority; ALERT unless it exits 0 and reports the record
    with the sha256 the file has. Its outputs go to phase_driver/logs (a STOP file or a signal terminates it: an
    aggregation stopped before the record is redone with --force)."""
    cmd = cfg.aggregate_cmd(out_dir, rec_p, force)
    rc, out, err, log = run_long(ctx, cmd, TIMEOUTS['aggregate'], 'aggregate_freeze', cfg.low_prio, cfg.tool_env())
    if rc != 0:
        what = {1: 'refused: an output or the record exists, or a protected path', 2: 'inconsistent inputs, or a job '
                'not final', 4: 'refused by the interim-look guard'}.get(rc, 'unexpected')
        raise Alert('G8 aggregate_v4', f'aggregate_v4.py --write-freeze-record exited {rc} ({what}; log {log}.out / '
                                       '.err): no analysis freeze', P1.both(out[-20000:], err[-20000:]), cmd)
    m = AGG_RECORD_RE.search(out)
    if not m or cfg.path(m.group(1)).resolve() != rec_p.resolve() or not rec_p.is_file() \
            or P1.sha256_file(rec_p) != m.group(2):
        raise Alert('G8 aggregate_v4', f'aggregate_v4.py did not report the record {cfg.rel(rec_p)} with the sha256 '
                                       'the file has', P1.both(out[-20000:], err[-20000:]), cmd)
    ctx.log(f'G8: analysis-freeze record {cfg.rel(rec_p)} written (sha256 {m.group(2)}, {m.group(3)} jobs, trigger '
            f'{m.group(4)})\n' + out.rstrip()[-3000:])
    crash_point(ctx, 'aggregate_written')


def write_phases_done(cfg, ctx, view, rec_p, rsha, out_dir, doc):
    reg = P1.registration_view(cfg)
    ents = [{'key': k, 'label': label_of(k), 'line': e['line'], 'when': e['when']}      # in Sec. 13.2 order
            for k, e in sorted(view['entries'].items(), key=lambda kv: kv[1]['line'])]
    done = {'schema': DONE_SCHEMA, 'written': P1.now_iso(), 'variant': VARIANT, 'entries': ents,
            'gates': {g: ctx.gate(g).get('status') for g in GATES},
            'analysis_freeze': {'record': cfg.rel(rec_p), 'sha256': rsha, 'dir': cfg.rel(out_dir),
                                'frozen': (doc or {}).get('frozen'), 'trigger': (doc or {}).get('trigger'),
                                'jobs': len((doc or {}).get('jobs') or {})},
            'protocol_sha256': reg['protocol_sha256'], 'manifest_sha256': reg['manifest_sha256'],
            'seal_ok': reg['seal_ok'],
            'next': 'P7 (PROTOCOL Secs. 8.1, 9.12): the confirmatory analysis on the frozen record (analyze_v4.py), '
                    'the independent verification and the report are the coordinating session\'s; the phase driver '
                    'started no further step and stops.'}
    P1.atomic_write(cfg.done_path, json.dumps(done, indent=1, sort_keys=True, default=str) + '\n')
    ctx.log(f'PHASES DONE: the analysis freeze is recorded; {cfg.rel(cfg.done_path)} written; the driver stops')


def gate_g8(cfg, ctx):
    """G8 analysis freeze (PROTOCOL Sec. 9.12), reached once every P4-P6 job is final and the runner has exited (G7):
    wait until Sec. 13.2 registers the analysis code; registration.py --verify; aggregate_v4.py --write-freeze-record
    once into outputs/framelease_v4/analysis/final_<stamp>/; the record validated and recorded; PHASES_DONE.json.
    'finished', 'waiting' or 'dry'."""
    st = ctx.gate('G8')
    view = phase_view(cfg)
    ent = view['entries'].get('analysis_freeze')
    copies = p4_queued_copies(cfg)
    if ent is None:
        wait_for_tools(ctx, cfg.aggregate_script)       # M2: an aggregation of an earlier process ends first
        waits, code, a_line = analysis_registration(cfg, view)
        st['files'] = {'analyze_code': cfg.rel(cfg.analyze_code), 'code': code, 'registration_line': a_line}
        if waits:
            st.update(status='waiting', note='; '.join(waits))
            ctx.add_attention('G8: the analysis freeze waits: ' + '; '.join(waits))
            return 'waiting'
        want_files, job_ids = registered_p4_jobs(cfg, copies)
        out_dir, rec_p, force = analysis_target(cfg)
        if not rec_p.exists():
            ok, detail = verify_registration(cfg, ctx, strict_map(cfg, sealed_baseline(cfg, ctx) or {}))
            if not ok:
                if 'registered file(s) differ' in detail:
                    raise Alert('G8 analysis freeze', f'before the analysis freeze: {detail} (no analysis freeze '
                                                      'before an amendment restores or registers them)')
                st.update(status='waiting', note=f'the seal does not verify: {detail}')
                ctx.add_attention(f'G8: the seal does not verify: {detail}')
                return 'waiting'
            if cfg.dry_run:
                ctx.add_plan(f'G8: {P1.show(cfg.low_prio + cfg.aggregate_cmd(out_dir, rec_p, force))}; validate the '
                             'record; record the analysis freeze in Sec. 13.2; write '
                             f'{cfg.rel(cfg.done_path)} and stop')
                st.update(status='dry', note='every P4-P6 job is final and the analysis code is registered; the '
                                             'analysis-freeze record is not written yet')
                return 'dry'
            P1.check_stop(ctx)
            if force:
                ctx.log(f'G8: {cfg.rel(out_dir)} holds the outputs of an aggregation stopped before its record: redone '
                        'there with --force')
            st.update(status='running', note=f'G8: aggregate_v4.py --write-freeze-record into {cfg.rel(out_dir)}')
            ctx.save()
            run_aggregate(cfg, ctx, out_dir, rec_p, force)
            view = phase_view(cfg)
            changed, code, a_line = analysis_registration(cfg, view)        # the code on disk after the run
            if changed:
                raise Alert('G8 analysis freeze', f'the analysis code changed while aggregate_v4.py made the record '
                                                  f'{cfg.rel(rec_p)}: {"; ".join(changed)}')
        doc = P1.read_json(rec_p)
        probs = analysis_record_problems(cfg, doc, want_files, job_ids, code)
        sums = out_dir / 'SHA256SUMS'
        probs += sha256sums_problems(cfg, out_dir, sums)
        if probs:
            raise Alert('G8 analysis freeze', f'{cfg.rel(rec_p)} does not validate: {probs}. The driver never rewrites '
                                              'a record (aggregate_v4.py refuses to replace one): check it, move the '
                                              'directory aside, then restart')
        rsha, sums_sha = P1.sha256_file(rec_p), P1.sha256_file(sums)
        st['files'].update(record=cfg.rel(rec_p), sha256=rsha, dir=cfg.rel(out_dir), sha256sums=sums_sha)
        a_sha = code[cfg.rel(cfg.analyze_code)]
        r = ensure_recorded(cfg, ctx, 'analysis_freeze', rsha,
                            lambda: analysis_entry(cfg, view, rec_p, rsha, doc, out_dir, sums_sha, code, a_line,
                                                   copies), also=(sums_sha, a_sha))
        if r is None:
            st.update(status='dry', note='analysis-freeze record written, not yet recorded')
            return 'dry'
        view = phase_view(cfg)
        ent = view['entries'].get('analysis_freeze')
    dirs = analysis_dirs(cfg)
    rec_p = dirs[0] / ANALYSIS_RECORD if len(dirs) == 1 else None
    rsha = P1.sha256_file(rec_p) if rec_p is not None and rec_p.is_file() else None
    if ent is None or rsha is None or rsha not in ent['shas']:
        raise Alert('G8 analysis freeze', f'the analysis-freeze record ({[cfg.rel(d) for d in dirs]}) is missing or '
                                          'not the one the Sec. 13.2 entry cites')
    st['entry'] = {'line': ent['line'], 'when': ent['when']}
    st['files'] = {**(st.get('files') or {}), 'record': cfg.rel(rec_p), 'sha256': rsha}
    st.update(status='passed', note='analysis freeze recorded')
    if not cfg.done_path.exists():
        if cfg.dry_run:
            ctx.add_plan(f'write {cfg.rel(cfg.done_path)} and stop')
            return 'dry'
        write_phases_done(cfg, ctx, view, rec_p, rsha, dirs[0], P1.read_json(rec_p))
    return 'finished'


GATE_FUNCS = (('G0', gate_g0), ('G1', gate_g1), ('G2', gate_g2), ('G3', gate_g3), ('G4', gate_g4), ('G5', gate_g5),
              ('G6', gate_g6), ('G7', gate_g7), ('G8', gate_g8))


# ---------------------------------------------------------------------------------------------------- cycle and main

def write_alert(cfg, ctx, a):
    ctx.state['alert'] = {'time': P1.now_iso(), 'gate': ctx.state.get('current_gate'), 'step': a.step,
                          'problem': a.problem, 'file': cfg.rel(cfg.alert_path)}
    ctx.state['driver']['status'] = 'ALERT'
    if cfg.dry_run:
        ctx.add_plan(f'ALERT and stop: {a.step}: {a.problem}')
        if a.output:
            for ln in a.output.splitlines()[:40]:
                print(f'      | {ln}')
        return
    text = (f'PHASE DRIVER ALERT {P1.now_iso()}\ngate:    {ctx.state.get("current_gate")}\nstep:    {a.step}\n'
            f'problem: {a.problem}\n' + (f'command: {P1.show(a.cmd)}\n' if a.cmd else '') + f'\n{a.output}\n\n---\n'
            'The phase driver stopped (exit 1) and refuses to start while this file exists. Investigate and fix the '
            'cause, then move this file aside (mv ALERT.txt ALERT.<UTC>.resolved.txt) and start the driver again '
            '(bash framelease_v4/protocol/start_phase_driver.sh). Decisions the coordinating session writes into this '
            'directory: P2_MISSING_ACK.txt (every missing P2 job id and the decision), P3_OPEN_CASES.json (the option '
            'of an open case of GAP_AUDIT Sec. 6 item 5 and the rationale), S1_ACCEPT_FOREIGN_CPU.txt (S1 under '
            'foreign CPU load, with the reason).\n')
    cfg.driver_dir.mkdir(parents=True, exist_ok=True)
    path = cfg.alert_path
    if path.exists():
        path = cfg.driver_dir / f'ALERT.{time.strftime("%Y%m%dT%H%M%S")}.txt'
    P1.atomic_write(path, text)
    ctx.log(f'ALERT ({cfg.rel(path)}): {a.step}: {a.problem}')


def cycle(cfg, ctx):
    """One pass over the gates. 'done' (every gate passed, or P2 stopped by D1), 'alert', 'stopped' or 'continue'."""
    ctx.attention = []
    ctx.lock_busy = False
    ctx.plan = []
    ctx.launched_now = False
    ctx.state['driver']['status'] = 'running'
    try:
        P1.check_stop(ctx)
        try:
            ensure_open_txn_finished(cfg, ctx)
        except Wait as w:
            ctx.add_attention(str(w))
        try:                    # the registered baseline, from a consistent sealed state
            ctx.state['registered_baseline'] = baseline_summary(cfg, sealed_baseline(cfg, ctx))
        except Alert as a:      # a broken Sec. 13.2 structure: an ALERT only when an entry has to be written
            ctx.add_attention(f'{a.step}: {a.problem}')
        ctx.state['priority'] = {'closed_loop_active': cfg.closed_loop_active(), 'tool_prefix': cfg.low_prio}
        for k, (g, fn) in enumerate(GATE_FUNCS):
            P1.check_stop(ctx)
            ctx.state['current_gate'] = g
            try:
                r = fn(cfg, ctx)
            except Wait as w:          # AttentionWait (a live tool, unregistered code, a decision being written), lock
                ctx.gate(g).update(status='waiting' if isinstance(w, AttentionWait) else 'waiting_lock', note=str(w))
                ctx.log(f'{g}: {w}')
                r = 'waiting'
            if r == 'stopped':
                ctx.state['driver']['status'] = 'P2_STOPPED'
                return 'done'
            if r == 'finished':
                ctx.state['driver']['status'] = 'DONE'
                return 'done'
            if r != 'done':
                for g2, _ in GATE_FUNCS[k + 1:]:
                    ctx.gate(g2).update(status='blocked', note=f'waits for {g}')
                break
        ctx.state['driver']['status'] = 'waiting'
        return 'continue'
    except Alert as a:
        write_alert(cfg, ctx, a)
        return 'alert'
    except Stop:
        ctx.state['driver']['status'] = 'stopped'
        ctx.log('stop requested: the driver exits')
        return 'stopped'
    except Exception as e:  # noqa: BLE001  (a bug or an unexpected state: never advance past it)
        write_alert(cfg, ctx, Alert('driver', f'unexpected {type(e).__name__}: {e}', traceback.format_exc()))
        return 'alert'
    finally:
        try:
            ctx.state['registration'] = P1.registration_view(cfg)
        except OSError:
            pass
        ctx.save()


def consistency_problems():
    """The constants hard-coded here must equal those of framelease_v4/protocol/p2_jobs.py, p2_check.py, p1_driver.py,
    p3_rl.py, stress_bench.py, test_jobs.py, test_freeze.py and framelease_v4/analysis/interim_guard.py,
    aggregate_v4.py."""
    try:
        from framelease_v4.protocol import p2_check as PC
        from framelease_v4.protocol import p2_jobs as P2
    except Exception as e:  # noqa: BLE001
        return [f'cannot import framelease_v4/protocol/p2_jobs.py / p2_check.py: {e}']
    want = {'p2_jobs.BLOCK': (P2.BLOCK, P2_BLOCK), 'p2_jobs.BLOCK_NO': (P2.BLOCK_NO, P2_BLOCK_NO),
            'p2_jobs.TIER': (P2.TIER, P2_TIER), 'p2_jobs.STAGE_SCHEMA': (P2.STAGE_SCHEMA, P2_STAGE_SCHEMA),
            'p2_jobs.CHECK_SCHEMA': (P2.CHECK_SCHEMA, P2_CHECK_SCHEMA),
            'p2_jobs.block_paths': (P2.block_paths()[0].name, f'{P2_JOB_STEM}.jsonl'),
            'p2_jobs.QUEUE_REL': (P2.QUEUE_REL, 'outputs/framelease_v4/queue_p2'),
            'p2_jobs.JOBS_DIR': (str(P2.JOBS_DIR), str(ROOT / 'outputs/framelease_v4/p2_jobs')),
            'p2_check.SCHEMA': (PC.SCHEMA, P2_REPORT_SCHEMA),
            'p2_check.MANIFEST_SCHEMA': (PC.MANIFEST_SCHEMA, P2_MANIFEST_SCHEMA),
            'p2_check.REPORT_PATH': (str(PC.REPORT_PATH), str(ROOT / 'outputs/framelease_v4/rl_data/p2_check.json')),
            'p2_check.MANIFEST_PATH': (str(PC.MANIFEST_PATH),
                                       str(ROOT / 'outputs/framelease_v4/rl_data/data_manifest.json')),
            'p1_driver.DONE_SCHEMA': (P1.DONE_SCHEMA, P1_DONE_SCHEMA)}
    probs = [f'{k}: {a!r} != {b!r}' for k, (a, b) in want.items() if a != b]
    # the G4-G8 tools import numpy and the RL stack: their constants are read from the source, never imported
    fdir = ROOT / 'framelease_v4'
    expect = {
        'protocol/p3_rl.py': {'DEFAULT_OUT': P3_OUT, 'FREEZE_SCHEMA': RL_FREEZE_SCHEMA,
                              'CALIBRATION_SCHEMA': CALIBRATION_SCHEMA, 'CAL_SIZES': CAL_SIZES,
                              'CAL_OUT_ALLOWED': CAL_OUT_ALLOWED, 'VARIANT': VARIANT, 'ARM_OF': ARM_OF,
                              'OPEN_CASES': {k: v[:2] for k, v in OPEN_CASES.items()}},
        'protocol/stress_bench.py': {'SCHEMA': STRESS_SCHEMA, 'OUT_DIR': STRESS_OUT, 'LOADS': S1_LOADS,
                                     'S3_MIN_SEQUENCES': S3_MIN_SEQUENCES, 'SUPPLEMENTARY_LABEL': SUPPLEMENTARY_LABEL,
                                     'BLOCKING_MARKERS': S1_BLOCKING_MARKERS, 'CPU_SAMPLE_S': FOREIGN_CPU_SAMPLE_S,
                                     'FOREIGN_CPU_MIN_SHARE': FOREIGN_CPU_MIN_SHARE},
        'protocol/test_jobs.py': {'QUEUE_REL': P4_QUEUE, 'JOBS_DIR': TEST_JOBS_DIR, 'INDEX_SCHEMA': TEST_INDEX_SCHEMA,
                                  'CHECK_SCHEMA': TEST_CHECK_SCHEMA, 'INDEX_NAME': 'index.json', 'VARIANT': VARIANT},
        'protocol/test_freeze.py': {'SCHEMA': TEST_FREEZE_SCHEMA, 'OUT_DIR': TEST_FREEZE_DIR,
                                    'RECORD_NAME': 'test_freeze.json', 'MANIFEST_NAME': 'MANIFEST.sha256',
                                    'STRESS_DIR': STRESS_OUT},
        'analysis/interim_guard.py': {'FREEZE_SCHEMA': ANALYSIS_FREEZE_SCHEMA, 'FINAL_OUTCOMES': FINAL_OUTCOMES,
                                      'ANALYSIS_MODULES': ANALYSIS_MODULES},
        'analysis/aggregate_v4.py': {'OUTPUT_FILES': AGG_OUTPUT_FILES}}
    for name, consts in expect.items():
        try:
            have = source_constants(fdir / name, consts)
        except (OSError, SyntaxError, ValueError) as e:
            probs.append(f'cannot read framelease_v4/{name}: {e}')
            continue
        for k, v in consts.items():
            got = have.get(k)
            if k == 'OPEN_CASES' and isinstance(got, dict):
                got = {c: tuple(x[:2]) for c, x in got.items()}
                letters = {c: str(x[2])[:3] for c, x in have[k].items()}
                if letters != {c: x[2] for c, x in OPEN_CASES.items()}:
                    probs.append(f'{name}.OPEN_CASES items {letters}')
            if got != v:
                probs.append(f'{name}.{k}: {got!r} != {v!r}')
    return probs


def source_constants(path, names):
    """{name: value} of the module-level assignments `names` of a Python source, read without importing it: literals,
    and ROOT / '<part>' / ... chains as the relative path '<part>/...'."""
    def value(node):
        if isinstance(node, ast.Name) and node.id == 'ROOT':
            return ''
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            left, right = value(node.left), ast.literal_eval(node.right)
            return f'{left}/{right}' if left else str(right)
        return ast.literal_eval(node)
    out = {}
    for node in ast.parse(Path(path).read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id in names:
            try:
                out[node.targets[0].id] = value(node.value)
            except (ValueError, TypeError, SyntaxError):
                out[node.targets[0].id] = '<not a literal>'
    return out


def launch_priority_problem():
    """None, or why a runner launched by this process would not get the priority of every runner: the process is
    pinned to a subset of the CPUs (taskset; checked first) or runs niced. The runner, CARLA and the evaluator inherit
    both through launch_queue.sh and systemd-run --scope."""
    try:
        aff = os.sched_getaffinity(0)
    except (AttributeError, OSError):
        aff = None
    if aff is not None and len(aff) < (os.cpu_count() or len(aff)):
        return f'the driver is pinned to CPUs {sorted(aff)} of {os.cpu_count()} (CPU affinity)'
    if os.nice(0) != 0:
        return f'the driver runs at nice {os.nice(0)}'
    return None


def unchecked_tools(cfg):
    """['<option> <path>'] of the tool scripts outside <root>/framelease_v4, whose registration the gates cannot check
    (test stand-ins; refused in the project tree)."""
    return [f'{opt} {path}' for opt, path in tool_scripts(cfg).items() if not project_code(cfg, cfg.path(path))]


def driver_running(cfg):
    """(running, holder text): the pid written into driver.lock is alive and runs phase_driver.py (no lock taken)."""
    holder = P1.lock_holder_text(cfg.lock_path)
    m = re.match(r'pid (\d+)', holder)
    return bool(m) and 'phase_driver.py' in P1.pid_cmdline(m.group(1)), holder


def dry_run(cfg):
    ctx = Ctx(cfg, P1.read_json(cfg.state_path))
    print(f'phase_driver --dry-run {P1.now_iso()} (changes nothing; a check tool runs without --write)')
    print(f'root:     {cfg.root}')
    try:
        reg = P1.registration_view(cfg)
        view = phase_view(cfg)
        print(f'protocol: {cfg.rel(cfg.protocol)} sha256 {reg["protocol_sha256"]}; MANIFEST {reg["manifest_sha256"]} '
              f'({reg["manifest_files"]} files); seal {"OK" if reg["seal_ok"] else "MISMATCH"}; heading {HEADING} '
              + (f'at line {view["heading"] + 1}' if view['heading'] is not None
                 else f'absent (created at the first entry, before line {view["anchor"] + 1}: "{ANCHOR} ...")')
              + f'; entries: {sorted(view["entries"]) or "none"}; P1 driver entries: '
              f'{sorted(view["p1_entries"]) or "none"}; amendments: {sorted(view["amendments"]) or "none"}')
        for qc in (cfg.p2_queue, cfg.p4_queue):
            q = P1.queue_status(qc)
            print(f'queue:    {qc.queue_arg}: {q["jobs"]} jobs, {q["final"]} final, {len(q["pending"])} pending; '
                  f'runner.lock "{q["runner_lock"]}"; STOP {q["stop_file"]}, PAUSE {q["pause_file"]}')
        waits = analysis_registration(cfg, view)[0]
        print(f'analysis: {cfg.rel(cfg.analysis_dir)}/final_*: {[d.name for d in analysis_dirs(cfg)] or "none"}; '
              f'analysis code registered for G8: {"yes" if not waits else "no (" + "; ".join(waits) + ")"}')
    except Alert as a:
        print(f'WOULD ALERT and stop: {a.step}: {a.problem}')
        return 1
    running, holder = driver_running(cfg)
    print(f'driver:   another driver running: {running}{" (" + holder + ")" if holder else ""}; ALERT.txt '
          f'{cfg.alert_path.exists()}; STOP {cfg.stop_path.exists()}; P1_DONE.json {cfg.p1_done.exists()}; '
          f'D1_DECISION.json {cfg.decision_path.exists()}; P2_STOPPED.json {cfg.stopped_path.exists()}; '
          f'PHASES_DONE.json {cfg.done_path.exists()}; open record transaction: {bool(P1.read_txn(cfg))}')
    print(f'priority: closed-loop job running: {cfg.closed_loop_active()}; tool prefix {cfg.low_prio or "none"}')
    if cfg.alert_path.exists():
        print('NOTE: the driver refuses to start while ALERT.txt exists')
    for path, what in ((cfg.stopped_path, 'P2 was stopped by D1'), (cfg.done_path, 'every phase is done')):
        if path.exists():
            print(f'{what} ({cfg.rel(path)}): the driver would exit at once')
            return 0
    probs = consistency_problems() if cfg.check_consistency else []
    print(f'tools:    constants consistent with p1_driver p2_jobs p2_check p3_rl stress_bench test_jobs test_freeze '
          f'interim_guard aggregate_v4: {"yes" if not probs else probs}; outside {PROJECT_CODE}/ (registration not '
          f'checked{", refused in the project tree" if cfg.root == ROOT else ""}): {unchecked_tools(cfg) or "none"}')
    print('cycle (as the driver would run it now):')
    outcome = cycle(cfg, ctx)
    print('gates:')
    for g in GATES:
        st = ctx.gate(g)
        print(f'  {g}  {st["status"]:<12} {st.get("note") or ""}')
    for a in ctx.attention:
        print(f'ATTENTION: {a}')
    if ctx.plan:
        print('would do now:')
        for p in ctx.plan:
            print(f'  - {p}')
    else:
        print(f'would do now: nothing; waiting at {ctx.state.get("current_gate")} (re-checked every '
              f'{cfg.interval_s:.0f} s)')
    if cfg.json_out:
        print(json.dumps(ctx.state, indent=1, sort_keys=True, default=str))
    return 0 if outcome != 'alert' else 1


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('--dry-run', action='store_true', help='print what the driver would do now; change nothing')
    ap.add_argument('--json', action='store_true', help='with --dry-run: also print the would-be state.json')
    ap.add_argument('--once', action='store_true', help='run one cycle in the foreground and exit')
    ap.add_argument('--interval-s', type=float, default=300.0)
    ap.add_argument('--lock-timeout-s', type=float, default=300.0,
                    help='wait for the protocol lock this long per cycle')
    ap.add_argument('--root', default=str(ROOT), help='project root (tests: a sandbox)')
    ap.add_argument('--protocol', default='framelease_v4/PROTOCOL.md')
    ap.add_argument('--protocol-lock', default='framelease_v4/.protocol.lock')
    ap.add_argument('--registration-dir', default='outputs/framelease_v4/registration')
    ap.add_argument('--driver-dir', default='outputs/framelease_v4/phase_driver')
    ap.add_argument('--p1-driver-dir', default='outputs/framelease_v4/p1_driver', help='read only')
    ap.add_argument('--p1-jobs-dir', default='outputs/framelease_v4/p1_jobs',
                    help='registered P1 job files (read only)')
    ap.add_argument('--freeze-path', default='outputs/framelease_v4/tuning/selection.json')
    ap.add_argument('--d1-dir', default='outputs/framelease_v4/tuning/d1')
    ap.add_argument('--p2-jobs-dir', default='outputs/framelease_v4/p2_jobs')
    ap.add_argument('--p2-queue', default='outputs/framelease_v4/queue_p2')
    ap.add_argument('--rl-data-dir', default='outputs/framelease_v4/rl_data')
    ap.add_argument('--rl-freeze-dir', default=P3_OUT, help='p3_rl.py run --out (the RL freeze directory)')
    ap.add_argument('--p3-calibration', default='outputs/framelease_v4/build/phase_driver/p3_calibration.json',
                    help='p3_rl.py calibrate --out (outside the project or under outputs/framelease_v4/build)')
    ap.add_argument('--stress-dir', default=STRESS_OUT)
    ap.add_argument('--stress-states', default='synthetic', choices=('synthetic', 'recorded'),
                    help='decision states of S1 and S2 in P3 (PROTOCOL Sec. 7.6: synthetic before the test freeze)')
    ap.add_argument('--s1-retries', type=int, default=3,
                    help='S1 refused because of foreign CPU load: retries before an ALERT')
    ap.add_argument('--s1-retry-s', type=float, default=600.0, help='seconds between two S1 attempts')
    ap.add_argument('--test-jobs-dir', default=TEST_JOBS_DIR)
    ap.add_argument('--test-freeze-dir', default=TEST_FREEZE_DIR)
    ap.add_argument('--p4-queue', default=P4_QUEUE, help='the one queue of tiers 3-6 (GAP_AUDIT E-1)')
    ap.add_argument('--analysis-dir', default=ANALYSIS_DIR,
                    help='G8: the analysis freeze goes to <dir>/final_<stamp>/ (PROTOCOL Sec. 9.12)')
    ap.add_argument('--analyze-code', default='framelease_v4/analysis/analyze_v4.py',
                    help='G8 waits until Sec. 13.2 cites the sha256 of this file; its directory holds the analysis '
                         'modules the record freezes')
    ap.add_argument('--all-cores', default='0-15', help='CPUs of the P3 and stress tools (taskset -c)')
    ap.add_argument('--watch-queues', default='outputs/framelease_v4/queue_p1,outputs/framelease_v4/queue_p2,'
                                              'outputs/framelease_v4/queue_p4',
                    help='queues whose runner marks a closed-loop job as running (priority, one runner at a time)')
    ap.add_argument('--require-amendments', default=','.join(REQUIRED_AMENDMENTS),
                    help='amendment ids G0 waits for in Sec. 13.2')
    ap.add_argument('--python', default=str(ROOT / '.conda-unidrive-linux/bin/python'))
    ap.add_argument('--registration-script', default='framelease_v4/protocol/registration.py')
    ap.add_argument('--p2-jobs-script', default='framelease_v4/protocol/p2_jobs.py')
    ap.add_argument('--p2-check-script', default='framelease_v4/protocol/p2_check.py')
    ap.add_argument('--p3-rl-script', default='framelease_v4/protocol/p3_rl.py')
    ap.add_argument('--stress-script', default='framelease_v4/protocol/stress_bench.py')
    ap.add_argument('--test-jobs-script', default='framelease_v4/protocol/test_jobs.py')
    ap.add_argument('--test-freeze-script', default='framelease_v4/protocol/test_freeze.py')
    ap.add_argument('--aggregate-script', default='framelease_v4/analysis/aggregate_v4.py')
    ap.add_argument('--launch-script', default='framelease_v4/protocol/launch_queue.sh')
    ap.add_argument('--env-script', default='linux/env.sh')
    ap.add_argument('--systemd-run', default='systemd-run', help='tests: a stand-in that runs the command')
    ap.add_argument('--ecores', default='12-15', help='CPUs of the tools while a closed-loop job runs (taskset -c)')
    ap.add_argument('--no-consistency-check', action='store_true',
                    help='tests: skip the comparison with the constants of the tools')
    ap.add_argument('--normal-priority', action='store_true',
                    help='run the tools without the nice / ionice / taskset prefix (tests under nice 19 only)')
    ap.add_argument('--allow-nice-launch', action='store_true',
                    help='tests only: run (and launch the mock runner) although the driver itself runs niced or with '
                         'a restricted CPU affinity')
    return ap.parse_args(argv)


def main(argv=None):
    a = parse_args(argv)
    cfg = Cfg(a)
    if cfg.dry_run:
        return dry_run(cfg)
    cfg.driver_dir.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(cfg.lock_path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(f'phase_driver: another instance holds {cfg.lock_path} ({P1.lock_holder_text(cfg.lock_path)}); exiting',
              file=sys.stderr)
        os.close(lock_fd)
        return 2
    os.ftruncate(lock_fd, 0)
    os.write(lock_fd, f'pid {os.getpid()} started {P1.now_iso()}\n'.encode())
    P1.atomic_write(cfg.pid_path, f'{os.getpid()}\n')
    ctx = Ctx(cfg, P1.read_json(cfg.state_path), echo=cfg.once or sys.stdout.isatty())
    ctx.log(f'START pid {os.getpid()} root {cfg.root} interval {cfg.interval_s:.0f} s'
            + (' (--once)' if cfg.once else ''))
    code = 2
    try:
        code = run_driver(cfg, ctx)
    finally:
        ctx.log(f'EXIT code {code}')
        try:
            if cfg.pid_path.read_text().strip() == str(os.getpid()):
                cfg.pid_path.unlink()
        except OSError:
            pass
        os.close(lock_fd)
    return code


def run_driver(cfg, ctx):
    """The start checks and the cycle loop of main() (the instance lock is held). Returns the exit code."""
    if cfg.alert_path.exists():
        ctx.state['driver']['status'] = 'ALERT (unresolved)'
        ctx.state['alert'] = {'file': cfg.rel(cfg.alert_path), 'note': 'present at start; the driver refuses to run'}
        ctx.save()
        ctx.log(f'refusing to run: {cfg.rel(cfg.alert_path)} exists (resolve it, then move it aside)')
        print(f'phase_driver: {cfg.alert_path} exists; resolve it first', file=sys.stderr)
        return 1
    if cfg.stop_path.exists():
        ctx.log(f'refusing to run: {cfg.rel(cfg.stop_path)} exists (remove it to start the driver)')
        print(f'phase_driver: {cfg.stop_path} exists; remove it to start', file=sys.stderr)
        return 2
    for path, status, what in ((cfg.stopped_path, 'P2_STOPPED', 'D1 = stop: P2 and every later phase are not started'),
                               (cfg.done_path, 'DONE', 'every phase is done')):
        if path.exists():
            ctx.state['driver']['status'] = status
            ctx.save()
            ctx.log(f'{cfg.rel(path)} exists ({what}); nothing to do')
            return 0
    bad = launch_priority_problem()
    if bad and not cfg.allow_nice_launch:
        msg = (f'{bad}; a runner it launches would inherit it (every runner runs at nice 0 on every core): start it '
               'at normal priority without a CPU pinning (the tools it runs get their own lower priority)')
        ctx.log(f'refusing to run: {msg}')
        print(f'phase_driver: {msg}', file=sys.stderr)
        return 2
    probs = consistency_problems() if cfg.check_consistency else []
    if probs:
        ctx.log(f'refusing to run: the driver constants differ from the tools: {probs}')
        print(f'phase_driver: constants differ from the tools: {probs}', file=sys.stderr)
        return 2
    outside = unchecked_tools(cfg)
    if outside and cfg.root == ROOT:
        msg = (f'the tools {outside} lie outside {PROJECT_CODE}/: their registration cannot be checked (review fix '
               'M4); use the project tools')
        ctx.log(f'refusing to run: {msg}')
        print(f'phase_driver: {msg}', file=sys.stderr)
        return 2

    def on_signal(signum, _frame):
        ctx.stop = True
        ctx.log(f'signal {signum}: stopping at the next safe point')
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    while True:
        ctx.cycle += 1
        outcome = cycle(cfg, ctx)
        if outcome == 'done':
            return 0
        if outcome == 'alert':
            return 1
        if outcome == 'stopped' or cfg.once:
            return 0
        end = time.monotonic() + cfg.interval_s
        while time.monotonic() < end and not ctx.stop and not cfg.stop_path.exists():
            time.sleep(min(1.0, max(0.0, end - time.monotonic())))
        if ctx.stop or cfg.stop_path.exists():
            ctx.state['driver']['status'] = 'stopped'
            ctx.save()
            ctx.log('stop requested (signal or STOP file): the driver exits')
            return 0


if __name__ == '__main__':
    raise SystemExit(main())
