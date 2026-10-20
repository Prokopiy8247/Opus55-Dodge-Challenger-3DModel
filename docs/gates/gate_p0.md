# Gate P0

Result: **PASS** (0 FAIL, 3 WARN, 21 checks)

| # | Check | Status | Detail |
|---|---|---|---|
| 1 | original .blend untouched | PASS | sha256 AA42CA0C78B5BE03BCDE065E7861075C6BADFBBFD7FDDEF8DF9B2D74F9CFAE68 |
| 2 | working file v001 saved | PASS | 3DDodgeChallenger_v001.blend 97468 bytes |
| 3 | Blender MCP scripts kept as files | PASS | p0_01_save_as_v001.py, p0_02_inspect_and_capture.py |
| 4 | P0 video asset (Blender before-state screenshot) | PASS | 2026-10-10_P0_blender_initial_scene.png |
| 5 | hardware matches brief (CPU, RAM, GPU, driver) | PASS | AMD Ryzen 7 5700X3D 8-Core Processor 8C/16T, 63.9 GB, NVIDIA GeForce RTX 5070, 616.92, 12227 MiB, 12.0, 4 |
| 6 | drive C: low on space (everything on W:) | WARN | C: 19.1 GB free at audit time |
| 7 | Unity editor 6000.6.0f1 installed | PASS | C:\Program Files\Unity\Hub\Editor\6000.6.0f1\Editor\Unity.exe (6000.6.0f1_f7f8ed4d1e24); Windows variations: mono, win32_player_development_mono, win32_player_nondevelopment_mono, win64_player_development_mono, win64_player_nondevelopment_mono, win_arm64_player_development_mono, win_arm64_player_nondevelopment_mono |
| 8 | IL2CPP module | WARN | not installed; Mono backend is used for Windows builds |
| 9 | Unity project created | PASS | W:\YouTube\3D Model Dodge Challenger\Unity\HellcatSandbox |
| 10 | Unity licence works in batch mode | PASS | Unity Personal; log also shows 'Access token is unavailable' (non-blocking) |
| 11 | package versions pinned in manifest.json | PASS | com.unity.burst@2.0.0, com.unity.collections@6.6.0, com.unity.inputsystem@1.20.1, com.unity.test-framework@1.8.0, com.unity.recorder@5.1.7, com.unity.render-pipelines.universal@17.6.0 |
| 12 | package assemblies load (Collections, Input System, Recorder, Test Framework, NUnit) | PASS | burstEnabled=True; Mathematics in UnityEngine.MathematicsModule; Burst in UnityEngine.BurstModule |
| 13 | GPU visible to Unity + compute shader smoke test | PASS | NVIDIA GeForce RTX 5070 Direct3D11 11944 MB; ok: 4096 values verified, dispatch + readback 6,19 ms |
| 14 | docs/physics_notes.md written from official docs | PASS | 640 lines, sections 1-9 present=True |
| 15 | benchmark matches spec (3,000 nodes / 15,000 beams / dt 0.5 ms) | PASS | editor: 3000 nodes, 15000 beams; player: 3000 nodes, 15000 beams |
| 16 | Burst code executed in every run, no NaN/Inf | PASS | 28 runs |
| 17 | determinism: identical state hash across runs, thread counts, ST/MT and editor/player | PASS | shuffled: ['dfce03a034eda5e7']; ordered: ['5ee7da084acbd50e'] |
| 18 | real time at 2000 Hz (player build) | PASS | ST 7296 steps/s (x3.6); MT 29023 steps/s (x14.5, 15 workers) |
| 19 | 60 fps frame budget (33 substeps per frame, player build) | PASS | MT mean 1.14 ms / p99 1.53 ms; ST mean 4.52 ms / p99 5.70 ms (budget 16.67 ms) |
| 20 | plastic deformation and breaking exercised | PASS | 976 plastic, 99 broken beams after the wall impact |
| 21 | stability guideline omega*dt < 0.5 on the synthetic lattice | WARN | max omega*dt 0.520, 402 nodes >= 0.5 (valence up to 18); run stayed stable |
