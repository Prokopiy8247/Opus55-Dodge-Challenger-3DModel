**What P7 delivers.**

- **The standalone game** is `Builds/HellcatSandbox/HellcatSandbox.exe` (D-102): the test map with the full game layer and a
  minimal start screen. It also runs every command-line check: crash scenarios, driven variants, the map check, the drive test,
  the controls check and the showcase capture. How to run, the controls and how to tune: `docs/README.md` and `docs/controls.md`.
- **Polish:**
  - glass that reads as glass: tinted, with full-strength reflections, a lighter windshield and a privacy rear (D-099);
  - a procedural sky for the background and the reflections (D-100);
  - interior level of detail while driving outside (brief 4.12, D-101).
- **Frame rate.** The first sandbox drive test showed the 46 debris props costing a quarter of every substep: 53-56 fps in the
  chase and cockpit views. Sleeping debris (D-098) puts them to sleep while they are at rest and the car is far away. The result
  is 87 fps on average and 77 fps or more in every view (90 fps at 2560 x 1440), with the car's physics unchanged bit for bit.
- **A regression found and fixed.** The final re-run of the validation suite failed T6: after the 0.2 m drop one hood beam
  had yielded. The map check, now reporting bent beams by material (D-103), showed the speed bump bending the same strip: the
  hood's crease zone from P6 (D-095) yielded at a tenth of the panel thresholds. At 0.3 (D-104) the drop and the bump stay
  elastic. The whole P6 series was run again with it on the final build.
- **Final verification.**
  - **G-Build:** the controls check (23 controls through a virtual keyboard and gamepad), the 5-minute drive, frame rates at
    1600 x 900 and 2560 x 1440, and the 1440p / 60 fps capture.
  - **Earlier evidence re-run on the final code:** the validation and dynamics suites, test 15, the P4b drive test, the map
    check and the whole P6 crash series.
- **Deliverables D9 and D10 completed:**
  - `docs/metrics.csv`, one row per scripted run;
  - `docs/README.md` and the root `README.md`;
  - the cost report `docs/cost_report.md` (brief 18).

**Deviations from the brief.**

- **No skinned debris.** The debris props are drawn rigid on the best-fit frames of their nodes; they deform in the solver only.
- **Vehicle self-collision.** It is limited to the detachable parts (D-058). The tyres do not collide with their own body, so at
  120 km/h the wheels pushed back do not load the hinge pillars (P6 open point 1).
- **Top speed** is 283 km/h against the published 314 km/h (P3b open point): the node tyres lose power under drive.
- **Calibration gaps.** The NCAP rebound and the wheelbase shortening are not matched (P6). The S7 debris damage is not
  monotonic in speed (a gate warning): the fence panels decide it.
- **Drive loop.** The drive test and the showcase use a 419 m loop in the east of the map rather than P4b's 977 m loop, which
  does not fit on the 300 x 200 m map. The P4b drive scene keeps the long loop and its own drive test.


**Open questions for the user** (none blocks the delivery):

1. **S8 passenger cell.** Should the cell collapse more at 120 km/h? That needs tyre-to-body self-collision, a solver cost.
2. **Top speed.** Is 283 km/h acceptable, or should the tyre losses under drive be re-tuned?
3. **Hood.** Would a finer hood skeleton be worth a re-export and a new P2 / P4 / P6 cycle? It would give smaller folds.
