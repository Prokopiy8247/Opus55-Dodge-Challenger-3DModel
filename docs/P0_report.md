# P0 report: environment audit, Unity project, BeamNG notes, Burst micro-benchmark

Date: 2026-10-10. Status: **P0 complete, waiting for user confirmation before P0.5.** Gate: `docs/gates/gate_p0.md` (PASS, 0 FAIL, 3 WARN).

## 1. Headline numbers

Synthetic soft body (3,000 nodes, 15,000 beams, 2,000 kg, braced box lattice 4.35 × 1.35 × 1.35 m) hitting a wall at 15 m/s, dt = 0.5 ms (2000 Hz), 33 substeps per 60 fps frame, 5 s simulated per run. Standalone Windows player (Mono + Burst AOT), random node/beam order (worst-case memory locality):

| Mode | Steps/s | µs/step | Frame (33 substeps) mean / p99 | × real time at 2000 Hz | Share of a 16.7 ms frame |
|---|---|---|---|---|---|
| Single thread (one Burst job per frame) | 6,743–6,840 | 146–148 | 4.82–4.89 / 5.36–6.26 ms | 3.4× | 29 % |
| Parallel, 4 workers | 20,216 | 49.5 | 1.63 / 2.07 ms | 10.1× | 10 % |
| Parallel, 8 workers | 27,376 | 36.5 | 1.21 / 1.57 ms | 13.7× | 7 % |
| Parallel, 15 workers (all) | 29,023 | 34.5 | 1.14 / 1.53 ms | 14.5× | 7 % |

- Burst code ran in all 28 runs (editor and player), no NaN/Inf. Plasticity and breaking were exercised: 976 beams deformed plastically and 99 broke.
- **Determinism:** the final state hash is bit-identical across repeated runs, 1–15 worker threads, two batch sizes, the single- and multi-threaded kernels, and editor (JIT) vs. player (AOT) Burst code.
- **Conclusion:** the 2000 Hz target is reachable on the CPU with a large margin. Unity stays the engine; no fallback is needed at this stage.

## 2. Environment audit (brief section 2: "confirm, do not assume")

| Item | Brief says | Found | Status |
|---|---|---|---|
| OS | Windows 11 | Windows 11 Enterprise 10.0.26200 | PASS |
| CPU | Ryzen 7 5700X3D, 8C/16T | AMD Ryzen 7 5700X3D, 8C/16T, 96 MB L3 | PASS |
| RAM | 64 GB | 63.9 GB | PASS |
| GPU | RTX 5070, driver 32.0.16.1692 | RTX 5070, 12 GB, driver 32.0.16.1692 (NVIDIA 616.92), compute capability 12.0 | PASS |
| Disk C: | ~19 GB free | 19.1 GB at audit, 18.7 GB after P0 | WARN (low) |
| Disk W: | everything goes here | 56.1 GB free at audit, 54.6 GB after P0 | PASS, watch it |
| Blender | 5.2.2 LTS | `W:\Blender\blender.exe`, 5.2.2 LTS | PASS |
| Unity Hub | 3.22.2 | `W:\Unity\Unity Hub`, 3.22.2 | PASS |
| Unity editor | 6000.6.0f1 | `C:\Program Files\Unity\Hub\Editor\6000.6.0f1` (changeset f7f8ed4d1e24); the editor itself lives on C: | PASS |
| Unity modules | - | Windows Mono, Mac Mono, WebGL. **No IL2CPP** | WARN (Mono is enough) |
| Visual Studio | Community 2026 | Community 2026 18.10 at `W:\Visual Studio`, VC++ x64 tools, Windows SDK 10.0.26100 | PASS |
| .NET SDK | 10 | 10.0.401 | PASS |
| Python / uv | 3.12 / uv | Python 3.12.10, uv 0.12.15 | PASS |
| Git | `W:\Git` | `W:\Git\Git\cmd\git.exe`, 2.51.1 (path differs from brief) | PASS |
| VS Code | installed | 1.141.0 | PASS |
| Unreal Engine | 5.8.2 (not used) | `W:\Unreal Engine 5\UE_5.8`, 5.8.2 | PASS |
| Godot | 4.7.2 (not used) | not found on PATH; not searched further | not verified |

Raw data: `docs/p0/env_audit.json` (script `tools/p0/p0_env_audit.ps1`).

## 3. Blender and the MCP connection

- **Port mapping.** The Blender instance with the project file listens on 127.0.0.1:9876. In this session the server for that port is named `custom-blender-planets` (the name is misleading; the port is what matters). The config is the Mirasim runtime MCP file; the server is `uvx mcp-for-blender --host localhost --port 9876` with `BLENDER_MCP_SAFE_MODE=1` and `DISABLE_TELEMETRY=true`.
- **Version.** The MCP server is mcp-for-blender **2.1.9** (from the uv cache), but the `uvx` command is not version-pinned. The **Blender add-on is outdated**: protocol 7, add-on 1.7, while the server expects 13. Core tools work (execute code, scene info, screenshots). The update command `uvx mcp-for-blender install-addon` was **not** run; see open question 2.
- **Telemetry.** The server process has telemetry off (`DISABLE_TELEMETRY`), so it sent nothing. The add-on's own consent flag was **on**, which would allow collection by any other client. It was switched off with the MCP `disable_telemetry` tool, as the brief requires. Re-enable: Blender › Preferences › Add-ons › Blender MCP › Allow Telemetry.
- **Safe mode** (AST allowlist) blocks `os`, `open`, `exec` and similar calls. Blender scripts therefore live in `tools/blender/*.py` and their exact text is sent through MCP. Saving `.blend` files is allowed.
- **Other clients.** The OpenAI Codex VS Code extension also runs mcp-for-blender servers on ports 9876, 9877 and 9878. They were not connected during P0, but they could drive the same Blender; see open question 3.
- **First action.** The original was saved as `3DDodgeChallenger_v001.blend` (`tools/blender/p0_01_save_as_v001.py`). The original's SHA-256 `AA42CA0C…AE68` (97,318 bytes, 15:08:18) is unchanged; the gate re-checks it. The open file had unsaved changes (`*` in the title); they went into v001, not into the original.
- **What the file contains:** Blender's default startup scene. One collection, `Collection`, holds `Cube` (2 m, 6 faces, material `Material`), `Light` (point, 1000 W) and `Camera`. Materials: `Material` and `Dots Stroke` (grease-pencil default). Units: metric, metres, kilograms, unit scale 1.0. Render: EEVEE, 1920×1080, 24 fps, frames 1–250. Enabled add-ons include `blender_mcp` and `io_scene_fbx`. Before-state screenshot: `docs/video_assets/P0/2026-10-10_P0_blender_initial_scene.png`.

## 4. Unity: licence, project, packages

- **Licence in batch mode:** works. `Product: Unity Personal, Expiration: Unlimited`; entitlements resolved. The log also shows `Access token is unavailable; failed to update` and a licensing-client signature warning (code 10, "ignoring"). Neither blocked anything. If the Personal licence ever needs re-validation, sign in to Unity Hub again.
- **Project:** `Unity/HellcatSandbox`, created in batch mode from the editor's URP template (`com.unity.template.urp-blank-17.2.1`). Took 90 s. Colour space Linear, new Input System only (`activeInputHandler: 1`), Mono, Windows graphics APIs D3D11 then D3D12. URP 17.6.0 is assigned per quality level (Mobile, PC; PC is active); the global Graphics default is empty, which is how this template ships.
- **Caches:** the batch wrapper `tools/unity/run_unity_batch.ps1` redirects the Package Manager cache (`UPM_CACHE_ROOT`) and TEMP to `W:\…\Unity\_cache` and `Unity\_tmp`. Unity still wrote 55 MB into its Bee build cache on C: (`%LOCALAPPDATA%\Unity\Caches\bee`). Project Library is 1.3 GB.

Package compatibility with 6000.6.0f1, verified with the editor's Package Manager (`docs/p0/packages_probe.json`), by compiling and running code (`docs/p0/unity_environment.json`), and by a player build:

| Brief package | Result in 6000.6.0f1 | Pinned | Status |
|---|---|---|---|
| Burst | `com.unity.burst` **2.0.0**, built-in. The package is now only type forwarders; the compiler lives in the engine module `UnityEngine.BurstModule`. The API (`[BurstCompile]`, `BurstCompiler`, `FloatMode`) is unchanged. Burst AOT built `lib_burst_generated.dll` for Windows x64. | 2.0.0 | PASS |
| Collections | `com.unity.collections` **6.6.0**, built-in, versioned with the editor | 6.6.0 | PASS |
| Mathematics | `com.unity.mathematics` 1.4.0 is now an **empty** package ("moved to a module"). `Unity.Mathematics` types come from `UnityEngine.MathematicsModule`; nothing to install. | - (module) | PASS |
| Jobs | `com.unity.jobs` exists only as the deprecated 0.70.0-preview.7. The C# Job System is part of the engine (`Unity.Jobs`) and parallel-for works. **Do not install.** | - (core) | PASS (not needed) |
| Input System | 1.20.0 came with the template; 1.20.1 is recommended | 1.20.1 | PASS |
| Test Framework | 1.8.0, built-in (NUnit loads) | 1.8.0 | PASS |
| Recorder | 5.1.7 (registry; pulls `com.unity.bindings.openimageio` 1.0.2). Editor-only: it records Play Mode in the editor, not inside a standalone build. | 5.1.7 | PASS |
| Cinemachine (optional) | 6.6.0, built-in and compatible; **not installed**; own node-attached cameras are planned | - | compatible |
| URP | 17.6.0, built-in | 17.6.0 | PASS |

- **GPU in Unity:** RTX 5070 under D3D11 (11,944 MB). A compute-shader smoke test dispatched and read back 4,096 values, all correct, in 6.2 ms including first-use overhead. The compute path is available as a later optimisation; the CPU Burst path stays the baseline.

## 5. Burst solver micro-benchmark: setup and full results

- **Code:** `Unity/HellcatSandbox/Assets/Sim/Benchmark/` (assembly `Hellcat.Sim`). Batch entry points are in `Assets/Editor/P0/P0BenchmarkTasks.cs`. The player runs it with `Builds/P0_SolverBench/HellcatSolverBench.exe -batchmode -nographics -solverBenchOut <json>`, so the shipped game can self-benchmark.
- **Structure:** a 30×10×10 node lattice with 0.15 m spacing. It has every axial edge (8,300) plus 6,700 of the 7,650 face diagonals, chosen evenly, for exactly 15,000 beams. Valence is 10 on average and up to 18. Node mass is 0.667 kg.
- **Beam material:** k = 40 kN/m, c = 20 N·s/m. Plastic threshold 2 kN with linear hardening of 40 kN/m, strength 3 kN.
- **Ground:** penalty contact with a 2.5 cm bias, Coulomb μ = 0.8. A static wall stands at x = 8 m; the structure starts at 15 m/s.
- **Beam kernel:** length, direction, spring + damper, 1-D plastic return mapping with hardening, a break test, and branches for BOUNDED/SUPPORT (inactive here).
- **Node kernel:** gravity, two plane contacts with friction, semi-implicit Euler.
- **Variants:** ST runs one Burst `IJob` per frame (33 substeps inside) and scatters forces into nodes. MT runs, per substep, a parallel beam job (one force vector per beam, no shared writes), then a parallel node job that gathers forces through a CSR node→beam list in beam order and integrates. That gives 66 chained jobs per frame, completed once. No atomics.
- **Layouts:** "shuffled" uses random node and beam order, the worst case for memory locality. "Ordered" uses lattice order, which we will approximate by sorting real car nodes spatially.

Player build (release, Mono + Burst AOT), `docs/benchmarks/P0_burst_bench_player.json`:

| Variant | Layout | Workers | Batch beam/node | Steps/s | µs/step | Frame mean / p95 / p99 / max (ms) | × RT |
|---|---|---|---|---|---|---|---|
| ST | shuffled | - | - | 6,840 | 146.2 | 4.82 / 5.11 / 5.36 / 5.58 | 3.4 |
| ST (repeat) | shuffled | - | - | 6,743 | 148.3 | 4.89 / 5.48 / 6.26 / 6.88 | 3.4 |
| MT | shuffled | 1 | 256/64 | 9,355 | 106.9 | 3.53 / 4.61 / 5.75 / 6.56 | 4.7 |
| MT | shuffled | 2 | 256/64 | 14,028 | 71.3 | 2.35 / 2.66 / 2.88 / 3.05 | 7.0 |
| MT | shuffled | 4 | 256/64 | 20,216 | 49.5 | 1.63 / 1.93 / 2.07 / 2.23 | 10.1 |
| MT | shuffled | 8 | 256/64 | 27,376 | 36.5 | 1.21 / 1.45 / 1.57 / 1.78 | 13.7 |
| MT | shuffled | 15 | 256/64 | **29,023** | **34.5** | **1.14 / 1.38 / 1.53 / 1.73** | **14.5** |
| MT | shuffled | 4 | 1024/256 | 16,015 | 62.4 | 2.06 / 2.78 / 3.17 / 3.81 | 8.0 |
| MT | shuffled | 8 | 1024/256 | 16,307 | 61.3 | 2.02 / 2.58 / 3.01 / 4.18 | 8.2 |
| MT | shuffled | 15 | 1024/256 | 15,750–18,196 | 55.0–63.5 | 1.81–2.10 / … / 2.38–4.38 / … | 7.9–9.1 |
| ST | ordered | - | - | 7,296 | 137.1 | 4.52 / 5.17 / 5.70 / 6.11 | 3.6 |
| MT | ordered | 4 | 1024/256 | 26,320 | 38.0 | 1.25 / 1.61 / 1.75 / 1.92 | 13.2 |
| MT | ordered | 15 | 1024/256 | 24,000 | 41.7 | 1.37 / 2.07 / 3.22 / 5.57 | 12.0 |

Editor batch mode (job debugger and leak detection off), `docs/benchmarks/P0_burst_bench_editor.json`: ST 5,820–6,534 steps/s (2.9–3.3×); best MT 21,831 steps/s (10.9×, 15 workers, 256/64). The editor runs 10–25 % slower than the player and with more jitter.

Interpretation and projection:
- The work per step is about 10 ns per beam on one core. Parallel scaling stops at about 8 workers, because each substep is only ~35 µs of work and job scheduling/wake-up dominates. Small batches (256/64) beat large ones (1024/256), which leave threads idle.
- Projection for the full car (budget up to 6,000 nodes / 40,000 beams, about 2.7× this work): about 95 µs/step in MT, about 3 ms per 60 fps frame, about 5× real time, before collision, tires and skinning. Single-threaded it would be about 1.25× real time, too tight, so the game uses the MT path. ST stays as the reference and determinism oracle.
- Collision (spatial hash rebuilt per substep), pressurized tires and debris bodies are not in this benchmark. They are measured in P3/P3b, where the budget left over is about 85–90 % of the frame.
- Caveat: the machine was running Blender, VS Code, Codex and other apps during the measurements. Treat run-to-run differences of ±20 % as noise.

## 6. BeamNG documentation notes (`docs/physics_notes.md`)

These are 640 lines from 25 official documentation pages; every fact is tagged *documented*, *inference* or *assumption*. Findings that change the brief:

1. **Plasticity needs hardening.** The brief's 4.2 update keeps the spring force exactly at the threshold, which is perfectly plastic. Then `beamStrength > beamDeform` can never be reached, and beams break only through damping spikes. The BeamNG docs say `beamDeform` grows as the beam deforms, capped by `deformLimitStress`. The benchmark kernel already uses a 1-D return mapping with linear hardening; with the brief's rule it produced 0 broken beams in the first run.
2. **Stability rule.** For semi-implicit Euler the exact single-DOF limit is `k·dt²/m + 2·c·dt/m < 4` (undamped: ω·dt < 2). More damping shrinks the stable range, so "add damping" is not a fix. The documented BeamNG tutorial chassis sits at ω·dt ≈ 0.55–1.0. Proposal: warn at ω·dt ≥ 0.5 (the brief's rule) and hard-fail at the full criterion.
3. **Tire pressure** must use absolute pressure in the gas law: `p_abs = (p_gauge,0 + p_atm)·V0/V`, force `(p_abs − p_atm)·A`.
4. **SUPPORT** beams act in compression only and auto-break when stretched past `beamLongBound`. The brief's "stiffens only beyond a set length range" matches only the compression side.
5. **Anti-roll bars** map onto documented 4-node torsion bars (N·m/rad) better than onto "torsional-equivalent beams".
6. **Tire discretisation:** BeamNG uses 10–20 rays per side, typically 16, and warns that more cost CPU and stability. The brief asks for 24–48 cross-sections; start at 24 and benchmark.
7. The "about 3 cm" rule is node-to-**triangle** clearance at spawn, not node-to-node spacing. Separately, keep more than 10 cm between collidable components where possible.

## 7. Plan (P0.5 → P7) with expected wall times

These are agent working times; most of it is iteration and verification. Each phase ends at a checkpoint (brief section 11) and waits for you.

| Phase | Content (short) | Estimate |
|---|---|---|
| P0.5 | Vertical slice. A box car of about 40–60 nodes with 4 simple wheels: Blender script builds the skeleton → `geometry.json` export → Unity loader → the MT solver from P0, plus a spatial-hash node-vs-triangle stub for the wall → keyboard driving on a plane → wall crash → in-game PNG capture and a Recorder clip. Also: local git repo for the project (Unity `.gitignore`), the `docs/changelog.md` routine, and the gate script per phase. | 4–6 h |
| P1 | Exterior Hellcat Widebody in Blender via MCP. Proportion block from the dimension table, then panels, flares, lights, wheels; silhouette overlays against photos 1–6; `model_notes.md`. | 8–14 h |
| P1b | Interior and cockpit view: dashboard, cluster, wheel, seats, console, door cards; compared against the interior photos at the same FOV. | 6–10 h |
| P2 | Parametric physics skeleton, material presets, break groups, `geometry.json`/`params.yaml` export, Blender debug collection, mass and ω·dt report. | 6–10 h |
| P3 | Solver core: all beam kinds, collision with spatial hash + BVH + anticlip, break groups, validation tests 1–8, energy drift. | 8–12 h |
| P3b | Pressurized tires (built in steps), suspension, steering rack, powertrain, brakes; tests 9–14; driving targets. The hardest phase. | 12–20 h |
| P4 | Node-frame skinning (Burst/GPU), glass shards, first scripted crash S1. | 5–8 h |
| P4b | Game layer: input, cameras (chase, bumper, cockpit on cabin nodes, free), HUD, debug views, reset/repair, slow motion, record/replay. | 6–10 h |
| P5 | Test map O1–O9 (code-generated), debris as small node-beam bodies. | 3–6 h |
| P6 | Scenarios S1–S8, sensitivity sweep, tuning log, captures. | 8–16 h |
| P7 | Polish, standalone build, README/controls. | 3–6 h |

Machine times: a Unity player build takes 1.5–3 min (80 s for the P0 build); a batch import/compile run 20–90 s; a benchmark run 15–25 s.

## 8. Risks and mitigations

| # | Risk | Mitigation |
|---|---|---|
| R1 | Unity 6000.6 is newer than LTS. Burst, Mathematics and Collections moved into engine modules or built-in packages, and some third-party assets may expect the old packages. | All required packages verified working and pinned. No third-party packages are planned. If an issue appears, report it with evidence and propose 6000.0 LTS (not switching silently). |
| R2 | **Stiffness ceiling.** With 2,500–6,000 light nodes (0.3–0.8 kg on average) at 2000 Hz, the per-node stiffness cap (ω·dt) makes the body softer than BeamNG cars, which use fewer, heavier nodes. | Use fewer nodes in stiff regions and heavier nodes where needed; bracing before stiffness. Report ω·dt per node at load time. Decide the warning/limit policy (open question 4). |
| R3 | Heavy dampers between light nodes become unstable (c·dt/μ > 2). | Heavier hub and mount nodes, or implicit per-beam damping (see notes 8.3 item 5). |
| R4 | Collision cost (node-vs-triangle with a spatial hash per substep) is not measured yet. | Measure in P0.5/P3. There is 85–90 % of frame headroom. Rebuild the hash every N substeps with a safety margin; triangles sleep when no node is nearby, as BeamNG does. |
| R5 | Parallel scaling stops at about 8 workers because of per-substep scheduling overhead. | Keep small batches; run debris bodies concurrently; fuse jobs if needed. ST remains the reference. |
| R6 | Determinism with contacts: candidate pairs from a spatial hash can come in a thread-dependent order. | Sort contact pairs and apply them in a fixed order, as the gather does now. Every phase checks the state hash in its gate. |
| R7 | Video capture: Unity Recorder works only in the editor. | Record YouTube clips in the editor at 1440p60, MP4/H.264. Inside the standalone build, write our own PNG-sequence capture. No ffmpeg or other third-party encoder without your permission. |
| R8 | Disk: W: has 54.6 GB free; PNG sequences at 1440p can take several GB per minute; C: has 18.7 GB free. | Use MP4 for long clips and short PNG/EXR bursts only. Keep baked GI off (Unity's GI cache defaults to C:, up to 10 GB). |
| R9 | Blender add-on protocol 7 vs. 13; other MCP clients (Codex) on the same port. | Update the add-on and close Codex's Blender servers, if you agree (open questions 2 and 3). |
| R10 | The references have no pure side or top view; the 2 % silhouette target needs one. | Use perspective-corrected 3/4 views with known wheelbase/tire scale and state the uncertainty; ask for photos once in P1. |
| R11 | The pressurized tire is the most likely source of instability. | Build it in steps as in the brief (ring → one pressured section → full torus), capped pressure, positive-volume check. |

## 9. Open questions (batched)

1. **Permission mode.** This session was started by Mirasim with `--permission-mode bypassPermissions`. I did not enable it and cannot change it from inside, so the "no bypass" rule is not technically enforced right now. Can you switch this off in Mirasim? Until then I keep asking before any install or risky action.
2. **Blender add-on update.** Run `uvx mcp-for-blender install-addon` (protocol 7 → 13), then disable/enable the add-on in Blender? Also, should the Mirasim server command be pinned to 2.1.9 (`uvx mcp-for-blender@2.1.9 …`)? *Default if no answer: leave as is; the core tools work.*
3. **Codex's Blender MCP servers** (ports 9876–9878) could drive the same Blender. Can you close them while we work? *Default: I keep using only `custom-blender-planets`/9876.*
4. **Stability policy.** Keep the brief's ω·dt < 0.5 as a warning and use the exact criterion (`k·dt²/m + 2c·dt/m < 4`, with a safety factor) as the hard limit? *Default: yes.*
5. **Plasticity.** Replace the brief's perfectly plastic update with linear hardening, so beams can reach their strength? *Default: yes.*
6. **References.** If possible, please add a pure side photo (from far away) and a top view. Also confirm three details where the photos and the brief disagree:
   - **Roof:** photos 1, 3, 4 and 6 show a dark roof. Is it black?
   - **Hood:** photo 2 shows one centred scoop plus two side heat extractors; the brief says "one offset scoop".
   - **Exhaust:** photos show two rectangular tips; the parts list in the brief says 4.

   *Default: follow the photos.*
7. **Cameras.** Skip Cinemachine and write our own node-attached cameras? *Default: yes.*

## 10. P0 checklist

The P0 checklist has 21 checks: 18 PASS, 3 WARN, 0 FAIL. Full table: `docs/gates/gate_p0.md`, from `python -I tools\gate_p0.py`.

- **WARN:** C: low on space; no IL2CPP module (Mono is used); synthetic lattice max ω·dt 0.52, which stayed stable.
- **PASS:** everything else:
  - the original `.blend` is untouched and v001 exists;
  - scripts are kept as files and the before-screenshot is saved;
  - hardware matches the brief;
  - Unity editor, project and licence work, and packages are pinned and loading;
  - the GPU compute test passes;
  - `physics_notes.md` is written;
  - the benchmark matches the spec, Burst ran everywhere, and determinism holds;
  - real time at 2000 Hz and the 60 fps budget are met;
  - plasticity and breaking were exercised.

## 11. Files produced in P0

- `3DDodgeChallenger_v001.blend`: the working copy. The original is unchanged.
- `tools/blender/p0_01_save_as_v001.py`, `tools/blender/p0_02_inspect_and_capture.py`: Blender MCP scripts.
- `tools/p0/p0_env_audit.ps1`, `tools/unity/run_unity_batch.ps1`, `tools/gate_p0.py`.
- `Unity/HellcatSandbox/`: the project.
  - `Assets/Sim/Benchmark/*` (runtime);
  - `Assets/Editor/P0/*` (package probe, environment probe, benchmark tasks, player build);
  - `Packages/manifest.json` (pinned).
- `Builds/P0_SolverBench/HellcatSolverBench.exe`: the benchmark player, 100.7 MB.
- `docs/physics_notes.md`, `docs/P0_report.md`, `docs/changelog.md`.
- `docs/p0/*.json` (audit, package probe, Unity environment) and `docs/p0/logs/*` (all Unity logs).
- `docs/benchmarks/P0_burst_bench_editor.json`, `docs/benchmarks/P0_burst_bench_player.json`.
- `docs/gates/gate_p0.json`, `docs/gates/gate_p0.md`.
- `docs/video_assets/P0/2026-10-10_P0_blender_initial_scene.png`.
