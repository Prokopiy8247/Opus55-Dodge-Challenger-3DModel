"""P6 close: decisions (append_decisions.py), the tuning log rows (tuning_log.py), the report (make_p6_report.py), the
changelog row, the STATUS header, its P6 section, the plan and the phase log row, from docs/gates/gate_p6.json and
docs/p6/scenario_summary.csv. Idempotent.

Usage: tools/.venv/Scripts/python.exe tools/p6/close_p6.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable

P6_SECTION = r"""## P6 scenarios S1-S8 and tuning (decisions D-084 ... D-097)
- Scenarios in the test-map player: `Builds/TestMap/HellcatTestMap.exe -scenario S1..S8 [-targetKmh v] -out <dir>
  [-capture 1] [-lateral m] [-breakGlass s] [-vehicleParams file]`; driven variant `-driven 1`; play a recording
  `-replay <file.hrec>`. Spec table `CarCrashScenario.Specs` (lane, obstacle, kind, capture window, cameras); metrics
  `CrashMetrics` (SDF contact, tunnelling by plate crossing D-093, IIHS-like intrusion D-089, deformation).
- Series: `& tools\p6\run_all_p6.ps1 [-NoBuild] [-Only captured,series,glass,driven]` (build, 8 captured runs, 16 series
  runs, glass test, 8 driven variants, gate); single runs `& tools\p6\run_scenarios.ps1 -Runs 'S1:50:kmh50' [-Capture]
  [-Build]`. Results `sim/cache/<S>/kmh<v>/` (result JSON, pulse, timeseries, .hrec; frames ignored by git), driven
  `sim/cache/<S>/driven/`.
- Evidence: `tools\p6\make_videos.py [--sheet-only]` -> `docs/video_assets/P6/`; gate `tools\gate_p6.py` (summary
  `docs/p6/scenario_summary.md`, plots `docs/p6/plots/`); report `tools\p6\make_p6_report.py` (narrative
  `docs/p6/report_notes.md`); close `tools\p6\close_p6.py`.
- Tuning: `tools\p6\tune.py` (candidate sets -> `sim/cache/tune/<name>/`), `apply_tuning.py --crease 0.1 --front 0.7`
  (adopted), `sweep.py` (sensitivity -> `docs/p6/sensitivity.*`), `tuning_log.py` (rows P6-001 ... P6-006 of
  `docs/tuning_log.csv`). Params added: `pressure.gaugeScale`, `materialZones`, `-vehicleParams` (D-090).
- Calibration (D-091, D-096): NHTSA NCAP 2013 Challenger (`docs/p6/refs`): static crush 615 vs 608 mm; rebound (4.0 vs
  2.7 m/s) and wheelbase shortening (none vs 150 mm) not matched (the wheel path holds the front wheels).
- Open: S8 cell intrusion small (tyres do not collide with their own body, D-058); hood mesh coarse; stretched skins at
  120 km/h; inner suspension nodes do not collide with the ground (the lower-arm pivot dips 2-5 cm in S4 50 / S5 60);
  S7 damage not monotonic (fence panels); glass look (P7).

"""

P7_PLAN = """## Next (plan)
- **P7** polish and delivery: glass look (tint, reflections), interior LOD while driving outside (brief 4.12),
  standalone Windows build (test map as the start scene, minimal start / pause screen), G-Build (starts from the
  exe, runs the test map at the reported fps, controls work, 2560x1440 / 60 fps capture); every gate re-run with
  fresh evidence (P2, P3 / P3b suites, test 15, G-Drive, G-Map, the P6 series); README, `docs/cost_report.md`
  (brief 18), merge `dev` into `main`, final message in Russian.
"""


def run(script, *args):
    subprocess.run([PY, str(ROOT / script), *args], check=True)


def main():
    run("tools/p6/append_decisions.py")
    run("tools/p6/tuning_log.py")
    run("tools/p6/make_p6_report.py")
    g = json.loads((ROOT / "docs/gates/gate_p6.json").read_text(encoding="utf-8"))

    # changelog
    p = ROOT / "docs/changelog.md"
    s = p.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")
    if "\n| P6 |" not in s:
        s += ("\n| P6 | 2026-10-15 | P6 | All scripted scenarios S1-S8 on the test map (`CarCrashScenario` in the lane frame, D-084; "
              "`-scenario Sx` in `Builds/TestMap/HellcatTestMap.exe`) with speed series, metrics (CFC 60 pulse, crush, IIHS-like "
              "intrusion, deformation, broken beams by material, detached parts, energy ledger incl. drive and aero work D-092), "
              "input recordings replayed bit-identically from the saved file with the event re-rendered at 250 fps (D-086), "
              "driven variants through the teleport / F5 / F6 path (D-087), captures from four cameras and videos "
              "(`docs/video_assets/P6`). S3 is a centred pole (D-085). Tunnelling through plates by path crossing (D-093); "
              "scenario harness fixes (D-094); params tools: tyre gauge scale, material zones, `-vehicleParams` (D-090). Tuning "
              "(D-095): closure stops survive landings, ductile headlamp brackets, hood crease zone; front calibration x0.7 "
              "against NHTSA's 2013 Challenger NCAP test (D-091, D-096); sensitivity sweep on 5 parameters. Gate G-Crash (P6) "
              f"{g['verdict']} ({g['fails']} fail, {g['warns']} warn). |")
        p.write_bytes((s + "\n").encode("utf-8"))
        print("changelog row added")

    # STATUS: header, P6 section, plan, phase log
    p = ROOT / "docs/STATUS.md"
    t = p.read_text(encoding="utf-8")
    head = ("Last update: 2026-10-15. Phase **P6 done** (all scenarios S1-S8, speed series, driven variants, tuning; gate G-Crash P6 "
            f"{g['verdict']} {g['fails']} fail / {g['warns']} warn); next **P7** (polish: glass look, interior LOD; standalone build "
            "2560x1440 capture; re-run all gates with fresh evidence incl. the drive test and the validation suites; README, cost "
            "report, merge to main, final Russian message). Scenarios: `-scenario S1..S8` in `Builds/TestMap/HellcatTestMap.exe`, "
            "series `tools/p6/run_all_p6.ps1`, results `sim/cache/<S>/kmh<v>/`, summary `docs/p6/scenario_summary.md`, report "
            "`docs/P6_report.md`.\n")
    t = re.sub(r"Last update: .*?\n(?=AUTONOMY MODE)", lambda m: head, t, count=1, flags=re.S)
    if "## P6 scenarios" not in t:
        t = t.replace("## Architecture (short)", P6_SECTION + "## Architecture (short)", 1)
    nxt = re.search(r"## Next \(plan\)\n.*?(?=\n## )", t, flags=re.S)
    if nxt and "**P7** polish and delivery" not in nxt.group(0):
        t = t.replace(nxt.group(0), P7_PLAN.rstrip("\n"), 1)
    row = f"| P6 | done | {g['verdict']} ({g['fails']} fail, {g['warns']} warn) | docs/gates/gate_p6.md, docs/P6_report.md |"
    if "\n| P6 |" in t:
        t = re.sub(r"\n\| P6 \|[^\n]*", "\n" + row, t, count=1)
    else:
        t = t.rstrip("\n") + "\n" + row + "\n"
    if "P6 end" not in t:
        t = t.replace("P4 end 2026-10-14T18:58:24Z, P4b end 2026-10-14T21:27:23Z, P5 end 2026-10-14T22:10:20Z.",
                      "P4 end 2026-10-14T18:58:24Z, P4b end 2026-10-14T21:27:23Z, P5 end 2026-10-14T22:10:20Z, P6 end see cost_log.csv.")
    p.write_text(t, encoding="utf-8")
    print("STATUS updated")


if __name__ == "__main__":
    main()
