"""FrameLease v3 fast-prefix runtime option (R&D sprint 2026-11-10; not for DAC 2027).

Opt-in wrapper-level speed-ups of the UniDriveVLA prefix (SDPA attention, exact GPU image preprocessing, merged LoRA)
for the v2/v3 closed-loop agent, applied after model load by a separate agent entry. Nothing in framelease_v2/,
framelease_v3/runtime/ or third_party/ is modified. See README.md in this directory.
"""
