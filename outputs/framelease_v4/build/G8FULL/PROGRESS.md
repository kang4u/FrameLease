# G8FULL progress (second analysis freeze under Amendment A17)

Append-only log. Read this file first when resuming; continue from the last completed step.

- 2026-11-17 15:11 step 0 started: G8FULL directory created; scratch tree /tmp/G8FULL; every process pinned
  (taskset -c 12-15, nice 19, ionice idle, single-threaded BLAS, CUDA_VISIBLE_DEVICES='').
- 2026-11-17 15:12 step 1: registration.py --verify at start: manifest OK, both seals OK (5.1 s, 18 MB).
- 2026-11-17 15:25 step 2: read PROTOCOL Secs. 9.8-9.13 and A13-A17; G8CUT RUNBOOK, DRYRUN, scripts, g8_lib.py, dryrun
  tooling; interim_guard (record_problems, load_freeze, release), phase_driver G8 (analysis_record_problems,
  analysis_entry), aggregate_v4 CLI, verifier CLIs and the paired-difference comparison, f1_class_report.py (sha256
  ac82d65a... = A11/A15 citation), the two Desktop Fig. 3 scripts (read only). Findings: (1) load_freeze accepts any
  record cited in Sec. 13: after A18 both records are valid; the first one releases none of the 505 new runs (recorded
  outcome cut -> want ('pending', None)); (2) the class report has no R_cond class: R_cond 0/0 pairing rows stay
  'unexplained' (A16 rule needed); (3) G8CUT final_dir() refuses two final_* directories and g8_analysis.sh lists its
  own temporary file; (4) the Desktop scripts hard-code FINAL, write PNGs onto the Desktop with the same stems and
  make_fig3ab_table1.py hard-codes "n = 14 routes" in its titles.
- 2026-11-17 15:46 step 3: written dryrun/build_tree.py, dryrun/make_runs.py (stages cut, a17_pending, a17_final),
  g8f_lib.py (imports G8CUT/g8_lib.py), g8f_common/check/stop/freeze/apply/analysis/verify/figs.sh, fig3/*_full.py.
  Tree /tmp/G8FULL/root built (0.4 s, 43 MB); stage cut 6.9 s, 532 run dirs; stand-in first analysis by the G8CUT
  g8_analysis.sh A13 in the tree (68 s, exit 0, H5 contradicted, 62 files incl. the .tmp line); stand-in first
  verification (5 s): AGREE / DIFFER 137, class report 21 unexplained = R_cond pairing-status rows (A16 mechanism
  reproduced by the synthetic no-conflict runs). Next: test the G8FULL scripts step by step in the tree.
- 2026-11-17 15:49 step 4: tree stage a17_pending (502 of 505 new final, 3 open); g8f_check.sh exit 3 NOT FINAL as expected (0.35 s, 45 MB); first-freeze checks pass in the tree.
- 2026-11-17 15:59 step 5: every G8FULL step run once by hand in the tree (check 3/0, stop, freeze 33 s, apply A18 19 s POST OK, analysis 101 s, verify 59 s: AGREE / DIFFER, class report unexplained 121 = R_cond 0/0 rows, resolution entry A21 written; NEG resolution variants A/B/C exit 3; apply A19-A21 19 s each; figs 5 s, FINAL CHECK OK). dryrun/run_dryrun.sh written for the end-to-end rerun.
- 2026-11-17 16:02 step 6: RUNBOOK.md written (Secs. 0-14); end-to-end dry run dryrun/run_dryrun.sh running since 15:59 (log /tmp/G8FULL/dryrun_steps.log).
- 2026-11-17 16:04 step 7: dry run 1: freeze_after_entry exit 2 (record check flagged its own A18 citation as a collision); fixed in g8f_lib.record_info (cited only by an entry after A17 is accepted); the full dry run is repeated after this run ends. DRYRUN.md Secs. 1-2 written.
- 2026-11-17 16:07 step 8: dry run 1 ended (436 s; 30 of 31 steps as expected, the one exception fixed in step 7). Dry run 2 (clean, all fixes) starts.
- 2026-11-17 16:16 step 9: dry run 2 stopped at the verify step (16:16; steps 1-21 as expected, freeze_after_entry now exit 0) to rerun with the final g8f_lib.rel (text-only path relativization: no stat of a run directory named by runner records). Dry run 3 (final) starts.
- 2026-11-17 16:31 step 10: dry run 3 (final code) finished 16:16:56-16:24:05: 31 steps, every exit code as expected,
  430 s; peak RSS 213 MB (analyze_v4.py). Logs copied to dryrun/dryrun_steps.log and dryrun/tree_steps.log; entry
  examples and the sealed protocol tail (0 lines over 120 columns) in dryrun/entries_example/. Read-only g8f_check.sh
  on the project at 16:26: exit 3 NOT FINAL (301 of 632 final, runner 14451 alive), no problem (first freeze valid and
  unchanged). RUNBOOK timings and output lists updated. Remaining: DRYRUN.md Secs. 3-5, final registration verify.
- 2026-11-17 16:32 step 11: DRYRUN.md Secs. 3-5 written. registration.py --verify at end: manifest OK, both seals OK;
  project untouched (no file of framelease_v4/ changed, no new __pycache__ or empty file; analysis/, verification/,
  queues, drivers, G8CUT, cut_*, test_jobs/ and the Desktop figure files unchanged; no queue_p4/STOP). Scratch tree
  kept at /tmp/G8FULL (tmpfs). DONE.
