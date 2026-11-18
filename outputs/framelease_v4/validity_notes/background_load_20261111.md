# Background load during P1 and the measured prefix cost (2026-11-11)

Measured per-run prefix cost (CUDA-event time charged to the simulated timeline, PROTOCOL Sec. 2.3) of every
finished P1 run, from raw/agent/framelease/summary.json `prefix_cost_s`. Times are Beijing time (UTC+8).

Known background load: 13:20-13:45 driver review agents (tests, chaos tests); 13:59-15:20 up to six build/review
agents running tests at nice 19 (all cores); from about 15:21 the user's CSMH platform (simulation scheduler,
uvicorn, vite, a CPU-bound preflight script) on the same machine.

| start (Beijing) | block/arm | n prefixes | p50 s | p95 s | max s |
|---|---|---:|---:|---:|---:|
| 12:29:59 | ref/fixed_deep | 26 | 0.4201 | 0.4302 | 0.4363 |
| 12:32:36 | ref/fast_only | 37 | 0.4187 | 0.4249 | 0.4418 |
| 12:35:16 | ref/fast_only | 86 | 0.4192 | 0.4338 | 0.4474 |
| 12:39:05 | ref/fixed_deep | 207 | 0.4182 | 0.4277 | 0.4407 |
| 12:46:40 | ref/fixed_deep | 73 | 0.4172 | 0.4235 | 0.4250 |
| 12:49:57 | ref/fast_only | 94 | 0.4221 | 0.4520 | 0.4688 |
| 12:53:26 | ref/fast_only | 57 | 0.4161 | 0.4206 | 0.4284 |
| 12:56:29 | ref/fixed_deep | 39 | 0.4173 | 0.4269 | 0.4284 |
| 12:59:28 | ref/fixed_deep | 44 | 0.4164 | 0.4220 | 0.4257 |
| 13:01:56 | ref/fast_only | 57 | 0.4167 | 0.4201 | 0.4266 |
| 13:04:32 | ref/fast_only | 49 | 0.4175 | 0.4243 | 0.4333 |
| 13:07:49 | ref/fixed_deep | 48 | 0.4173 | 0.4253 | 0.4372 |
| 13:11:35 | ref/fixed_deep | 112 | 0.4177 | 0.4250 | 0.4487 |
| 13:16:53 | ref/fast_only | 50 | 0.4183 | 0.4247 | 0.4271 |
| 13:19:48 | ref/fast_only | 38 | 0.4180 | 0.4246 | 0.4512 |
| 13:22:43 | ref/fixed_deep | 25 | 0.4172 | 0.4243 | 0.4261 |
| 13:25:19 | ref/fixed_deep | 44 | 0.4246 | 0.4489 | 0.5902 |
| 13:29:39 | ref/fast_only | 66 | 0.4406 | 0.4661 | 0.4955 |
| 13:34:38 | ref/fast_only | 29 | 0.4418 | 0.4568 | 0.4652 |
| 14:00:52 | ref/fixed_deep | 20 | 0.4685 | 0.4783 | 0.4956 |
| 14:03:46 | ref/fixed_deep | 156 | 0.4495 | 0.4785 | 0.4921 |
| 14:13:23 | ref/fast_only | 39 | 0.4257 | 0.4454 | 0.4759 |
| 14:16:45 | ref/fast_only | 45 | 0.4416 | 0.4635 | 0.4667 |
| 14:20:03 | ref/fixed_deep | 36 | 0.4436 | 0.4700 | 0.4803 |
| 14:23:46 | ref/fixed_deep | 143 | 0.4446 | 0.4664 | 0.4908 |
| 14:32:20 | ref/fast_only | 182 | 0.4532 | 0.5172 | 0.6528 |
| 14:42:06 | ref/fast_only | 43 | 0.4760 | 0.5334 | 0.5548 |
| 14:46:13 | ref/fixed_deep | 295 | 0.4549 | 0.4892 | 0.5357 |
| 15:00:17 | ref/fixed_deep | 93 | 0.4385 | 0.4655 | 0.5121 |
| 15:07:24 | ref/fast_only | 113 | 0.4242 | 0.4394 | 0.5895 |
| 15:13:25 | ref/fast_only | 30 | 0.4210 | 0.4311 | 0.4399 |
| 15:16:00 | ref/fixed_deep | 112 | 0.4270 | 0.4615 | 0.5097 |
| 15:22:32 | ref/fixed_deep | 19 | 0.4635 | 0.4789 | 0.4900 |
| 15:25:15 | ref/fast_only | 26 | 0.4498 | 0.4611 | 0.4714 |
| 15:28:01 | ref/fast_only | 133 | 0.4436 | 0.4802 | 0.5300 |

Reading: p50 0.416-0.422 s with no background load (12:29-13:22); 0.43-0.48 s, p95 up to 0.53 s, during the
agent build period; back to 0.421-0.424 s when the agents stopped (15:07-15:13). Every run stays inside the
Sec. 9.7 manipulation band kappa x [0.35, 0.60] s for its p50. Countermeasures from 15:35: no concurrent agent
builds; any CPU work of the coordinating session runs on the E-cores 12-15 (taskset), nice 19, one process.
