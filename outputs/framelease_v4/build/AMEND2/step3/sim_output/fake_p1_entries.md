* **Tuning freeze**, 2026-11-15 06:17 (Beijing time). `outputs/framelease_v4/tuning/selection.json` (sha256
  `49a980146bdabfb46751b9a93490b10dd7be409df0a2ff6d559b18dcc2472475`), written 2026-11-15T06:17:32+0800 by
  `select_stage.py --variant FULL --freeze --write` from the eight stage selections above (Sec. 4.9): L* = `B0`
  (`outputs/framelease_v4/envelopes/B0.json`, sha256 `9ef8479f04dab873d22b50e8732176804ed67f351f17584355b241e424fa1927`,
  validity std); d* = 1 (utility `v4_adet_d1`); A* = 1.0 s; Event-Triggered `s_hb2.0` (theta* = s, A_hb* = 2.0 s);
  fl_risk: lease point `E5` (L* = B0: fl_risk runs the better of E5 / E10 by mean DS on lease_s1 (T22a), ties earlier).
  Manifest and seal: `MANIFEST.sha256`, 221 files; new in it:
  `outputs/framelease_v4/p1_jobs/FULL/b09_age_s2.check.json`, `outputs/framelease_v4/p1_jobs/FULL/b09_age_s2.jsonl`,
  `outputs/framelease_v4/p1_jobs/FULL/b09_age_s2.stage.json`, sha256
  `4bfe7451a41b853042f181cbcd7c326649b4222279bc35dd9787afa38c8d4033`, sealed with this entry.
* **D1 summary**, 2026-11-15 06:17 (Beijing time). `outputs/framelease_v4/tuning/d1/FULL_d1_summary.json` (sha256
  `9095a11a7daaa4a982206af657829e43d475043d3102559f4c2ef137b6c8aa37`) and
  `outputs/framelease_v4/tuning/d1/FULL_d1_summary.md` (sha256
  `0f31816a869e1be35b408c191de67d490995b05cf7e6dd852578f479a59deae5`), written 2026-11-15T06:17:41+0800 by
  `d1_summary.py --variant FULL --queue outputs/framelease_v4/queue_p1 --write` after every job of the queue was final:
  9 blocks on training routes only, with the tuning freeze (sha256
  `49a980146bdabfb46751b9a93490b10dd7be409df0a2ff6d559b18dcc2472475`). D1, continuing or stopping, is the user's
  decision (Sec. 4.8); no later phase was started. Manifest and seal: `MANIFEST.sha256`, 221 files, sha256
  `4bfe7451a41b853042f181cbcd7c326649b4222279bc35dd9787afa38c8d4033`, sealed with this entry.
