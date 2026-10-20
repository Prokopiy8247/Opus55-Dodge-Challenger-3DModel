# Hellcat Sandbox: controls

The game is **`Builds/HellcatSandbox/HellcatSandbox.exe`** (P7): the test map of P5 (scene `Assets/Scenes/TestMap.unity`, obstacles
O1-O9 with their spawn points in the pause menu, a drive loop in the open east). `Builds/TestMap/HellcatTestMap.exe` is the same scene
built for the P5 / P6 tools, and the P4b drive scene `Builds/P4b_Drive/HellcatDrive.exe` keeps the 977 m loop of the first drive test.
The game uses the Unity Input System, so a keyboard and an XInput gamepad work together. The default keys follow brief 4.12.

**Start screen.** The sandbox opens on a short title card with the main keys over the car waiting at the start; any key, mouse button
or gamepad button closes it (`-noStartScreen` skips it; command-line scenarios never show it).

## Driving

| Action | Keyboard | Gamepad |
|---|---|---|
| Throttle | W or Up arrow | Right trigger |
| Brake; held at a standstill for 0.3 s: engage reverse | S or Down arrow | Left trigger |
| Steer | A / D or Left / Right arrows | Left stick |
| Handbrake (rear wheels) | Space | B |
| Gear down / up (manual hold; down to 0 = automatic) | Q / E | LB / RB |
| ABS on / off | F7 | - |
| Traction control on / off | F8 | - |

- **Reverse.** Hold S at a standstill to engage reverse; W then drives backwards. Hold W at a standstill to return to drive.
- **Keyboard pedals.** Pressing a pedal ramps it up at 6/s; releasing it ramps it down at 10/s. Gamepad triggers are analogue.
- **Steering.** Keyboard steering is digital. The vehicle controller rate-limits it and reduces the lock with speed (P3b).
- **Gearbox.** It is an eight-speed automatic. Q and E hold a gear manually; Q back to 0 returns to automatic.
- **Driver aids.** ABS and traction control are on by default (`settings.json`).

## Sandbox keys

| Key | Action |
|---|---|
| R | **Reset** to the last safe position: a fresh, undamaged car, settled at rest where it last drove safely. Safe means upright, no beam broken for 1 s and at least 0.6 m from every obstacle; the pose is checked every 0.25 s. |
| Ctrl+R | Reset the map: the debris back where it started and the car to the last safe position |
| Shift+R | **Full repair** in place: a fresh car where this one is, upright and at rest. If the undamaged car would overlap an obstacle, it is moved back (up to 5 m), then forward. |
| C | Cycle cameras: chase, bumper, cockpit, free |
| T | Slow motion x0.1 / real time (the factor is `slowMotionScale` in `settings.json`) |
| P | Pause / resume |
| Shift+P | While paused: advance one frame (1/60 s, 33 substeps of 0.5 ms) |
| N | Node-beam view: beams and nodes, paint hidden. Nodes are small crosses, orange while touching something. |
| Shift+N | Node-beam overlay: the same lines drawn over the paint (x-ray) |
| H | Beam stress heat-map: elastic force / deform threshold, blue 0, yellow 0.5, red 1 or more. Opens the node-beam view if it is closed. |
| Shift+H | Deformation heat-map on the visual mesh: each vertex coloured by its distance from where the undeformed car would put it. Blue is 0, red is 30 cm. Wheels and suspension keep their paint. |
| F5 | Start / stop recording (see below) |
| F6 | Replay the last recording, or the newest file in `recordings/`; F6 again stops it |
| F9 | Reload `params.json` (and `geometry.json`) without restarting: the world is rebuilt and a fresh car is placed where this one is |
| F1 | HUD on / off |
| F12 | Screenshot to `recordings/shot_*.png` |
| Esc | Pause menu (the simulation pauses while it is open) |

Gamepad: **Y** cycles the cameras, **X** resets, **Start** opens the menu and **Back** toggles slow motion.

## Cameras

- **Chase.** The camera follows the centre of mass at a fixed distance (6.4 m behind, 1.9 m up) at any speed. The heading lags a little in turns and the height follows bumps softly.
- **Bumper.** The lens sits 9 cm ahead of the front fascia at 0.62 m height and rides on the front bumper beam nodes. In a frontal crash it is the first thing to hit.
- **Cockpit.** The camera is at the driver's eye point (D-020) and rides on the cabin nodes (sill, roof rails, tunnel), using their best-fit rotation. Its horizontal field of view is 85 degrees.
  - The tach and speedometer needles, the steering wheel and the pedals move with the simulation.
  - The three mirrors show the scene through their own cameras; these cameras run only in this view.
- **Free.** Hold the right mouse button and move the mouse to look. Move with I / J / K / L, go down / up with U / O, and hold Shift for 4x speed. On a gamepad, the right stick looks and the d-pad moves.

## Pause menu (Esc)

- Resume, reset (R) and repair (Shift+R).
- **Spawn points and obstacles.** Use "at rest" or "at V km/h" to teleport to a spawn; the speed slider runs from 0 to 200 km/h in 5 km/h steps. The obstacle spawns stand 60 m before the obstacle face.
- **Speed hold.** With "at V", the car is held at V on the lane and let go (pedals released, wheel straight) 1 m before the obstacle, so it hits at V (D-080). Any pedal, steering, handbrake or gear input takes over at once. The hold can be switched off in the menu; the HUD shows "speed hold" while it is active.
- Camera mode, time scale (x1, x0.5, x0.25, x0.1, x0.05) and the debug views.
- ABS and traction control.
- Recording: record, replay last, and the six newest files in `recordings/`.
- Settings: save the current aids and HUD state to `settings.json`, reload `params.json` (F9), quit.

## Recording and replay (F5 / F6, test 15)

- **Start (F5).** The game takes a snapshot of the complete simulation state: every native array of the world, damage included (D-070). It then records each frame's substep count and driver input.
- **Stop (F5 again).** The run is saved as `recordings/rec_<date>_<time>.hrec`: gzip, the snapshot included, about 0.6 MB per minute plus 0.2 MB for the snapshot. The inputs are also written as `.csv`, one row per frame: start time, substeps, pedals, steering, gear, aid flags.
- **Replay (F6).** The game restores the snapshot and plays the frames back.
  - At time scale 1 it uses the recorded frame partition and is bit-identical to the recording; test 15 and the G-Drive test check this.
  - In slow motion or while stepping, the inputs are looked up per substep. This is deterministic as well, and test 15 found the result identical.
  - When the replay ends, control returns to you.
- **What interrupts.** A reset, repair, teleport or F9 ends a recording (it is saved) or a replay.
- **Other data.** A recording stores a hash of the vehicle data. The replay warns if `geometry.json` or `params.json` changed since; such a replay may differ.

## Files

- **`settings.json`** is next to the executable; in the editor it is in the persistent data folder. It is written with the defaults on the first start:
  - chase distance and height;
  - fields of view;
  - free-camera speed and mouse sensitivity;
  - ABS and TC defaults, slow-motion factor;
  - substep cap per frame;
  - vsync, target frame rate, HUD, screenshot supersampling.
- **`recordings/`** is next to the executable and holds the recordings and screenshots.
- **`HellcatSandbox_Data/StreamingAssets/Vehicles/hellcat/params.json`** (in every build's `<exe>_Data` folder) holds the vehicle's
  simulation parameters (materials, tires, powertrain, aids, material zones). Edit it and press F9; `docs/README.md` explains the
  tuning workflow.

## Command line (tests and captures)

- `-replay <file.hrec>` plays a recording when the game starts (any recording: F5 runs, the scenario runs in `sim\cache`); afterwards you drive.
- `-scenario S1` ... `S8` (test map) runs a scripted scenario of brief 9 (P6): the car is placed on the scenario's lane and driven
  to the obstacle, the run is measured, recorded (`<run>.hrec`) and captured, then replayed from the recording with the event in
  slow motion. Options: `-out <dir>` (results), `-targetKmh <v>`, `-capture 1` (frames from four cameras), `-lateral <m>`
  (lane offset), `-launch 1` (start rolling at the speed), `-postImpact <s>`, `-replayCheck 0`, `-vehicleParams <params.json>`.
  `tools\p6\run_scenarios.ps1` runs them in a series.
- `-scenario S1 -driven 1` runs the driven variant: teleport to the lane at the speed with the speed hold, record (F5), replay (F6).
- `-scenario mapcheck` (test map) runs the P5 map check (`-mapOut dir`).
- `-scenario controls` (sandbox) presses every default key and gamepad control through a virtual keyboard and gamepad and checks the
  game's reaction (gate G-Build); `-controlsOut <dir>`.
- `-scenario showcase` (sandbox, P4b drive scene) writes the scripted showcase capture frame by frame (`-captureOut <dir>`); run it
  with `-screen-fullscreen 1 -window-mode borderless -screen-width 2560 -screen-height 1440` for the 1440p capture.
- `-scenario drive` runs the gate G-Drive test (in the sandbox on the east loop: 90 m straights, R 38 m curves). Options:
  - `-driveSeconds 300`
  - `-driveRecord 60`
  - `-driveOut <dir>`
- The test writes `drive_test.json`, `drive_timeseries.csv`, screenshots and `drive_record.hrec`, then quits.
- `-quitAfter <s>` quits after that many seconds of real time.
