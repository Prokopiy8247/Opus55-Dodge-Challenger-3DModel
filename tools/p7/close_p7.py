"""P7 close: decisions (append_decisions.py), the report (make_p7_report.py), the changelog row, the STATUS header, its P7
section, the plan and the phase log row, from docs/gates/gate_p7.json. Idempotent. The cost row and the cost report are
written separately (tools/cost/collect_usage.py + append_row.py, tools/cost/make_cost_report.py) at the very end.

Usage: tools/.venv/Scripts/python.exe tools/p7/close_p7.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable

P7_SECTION = r"""## P7 polish, standalone build, final gates (decisions D-098 ... D-104)
- The game: `Builds/HellcatSandbox/HellcatSandbox.exe` (`BuildTasks.BuildSandbox`; the test map scene with the game rig, the
  start screen `StartScreen`, the interior LOD `InteriorLod`, the drive test and showcase on the east loop, the controls check
  `ControlsCheck`). `Builds/TestMap/HellcatTestMap.exe` is the same scene for the P5 / P6 tools.
- Checks: `& tools\p7\run_p7.ps1 [-Build] [-Only controls,drive,drive1440,determinism,mapcheck,capture]` -> `docs/p7/`, the
  capture encoded by `tools\p7\encode_p7.py` -> `docs/video_assets/P7/`; gate `tools\gate_p7.py` (G-Build); report
  `tools\p7\make_p7_report.py` (narrative `docs/p7/report_notes.md`).
- Every earlier gate on the final code: `& tools\p7\run_suites.ps1` (P3 / P3b suites, test 15, the P4b drive player and its drive
  test, then gates P2, P3, P3b, P4b, P5, P6).
- Solver: sleeping debris (D-098, `TailSleepPhase`, `SoftBodyWorld.MarkSleepable / WakeTail`); look: glass (D-099, importer),
  sky (D-100, `CameraSky`), interior LOD (D-101).
- Docs: `docs/README.md` (run, controls, tuning, rebuilding), root `README.md`, `docs/metrics.csv` (`tools\p7\write_metrics.py`),
  `docs/cost_report.md` (`tools\cost\make_cost_report.py`).

"""


def run(script, *args):
    subprocess.run([PY, str(ROOT / script), *args], check=True)


def main():
    run("tools/p7/append_decisions.py")
    run("tools/p7/make_p7_report.py")
    g = json.loads((ROOT / "docs/gates/gate_p7.json").read_text(encoding="utf-8"))

    p = ROOT / "docs/changelog.md"
    s = p.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")
    if "\n| P7 |" not in s:
        s += ("\n| P7 | 2026-10-15 | P7 | Standalone game `Builds/HellcatSandbox/HellcatSandbox.exe` (test map, start screen, the drive "
              "test, showcase and controls check; D-102); sleeping debris in the solver (D-098: the sandbox from 60 to 87 fps, every "
              "view 77 fps or more, the car's physics unchanged bit for bit); glass with full-strength reflections and a "
              "lighter windshield (D-099), procedural sky (D-100), interior LOD (D-101); hood crease strip 0.3 after T6 and the bump caught "
              "0.1 yielding (D-103, D-104), the whole P6 series run again on the final build; controls check (23 controls through a "
              "virtual keyboard and gamepad), 2560 x 1440 / 60 fps capture, frame rates at 1600 x 900 and 1440p; every earlier "
              "gate re-run on the final code; README, metrics.csv, cost report. Gate G-Build (P7) "
              f"{g['verdict']} ({g['fails']} fail, {g['warns']} warn). |")
        p.write_bytes((s + "\n").encode("utf-8"))
        print("changelog row added")

    p = ROOT / "docs/STATUS.md"
    t = p.read_text(encoding="utf-8")
    head = ("Last update: 2026-10-15. **All phases done (P0-P7)**; gate G-Build P7 "
            f"{g['verdict']} {g['fails']} fail / {g['warns']} warn, every earlier gate re-run on the final code (`docs/P7_report.md`). "
            "The game: `Builds/HellcatSandbox/HellcatSandbox.exe`; how to run, controls, tuning: `docs/README.md`; cost: "
            "`docs/cost_report.md`. `dev` merged into `main`.\n")
    t = re.sub(r"Last update: .*?\n(?=AUTONOMY MODE)", lambda m: head, t, count=1, flags=re.S)
    if "## P7 polish" not in t:
        t = t.replace("## Architecture (short)", P7_SECTION + "## Architecture (short)", 1)
    nxt = re.search(r"## Next \(plan\)\n.*?(?=\n## )", t, flags=re.S)
    if nxt:
        t = t.replace(nxt.group(0), "## Next (plan)\n- Nothing scheduled: the brief's deliverables are complete. Open questions for the "
                      "user are at the end of `docs/P7_report.md`.", 1)
    row = f"| P7 | done | {g['verdict']} ({g['fails']} fail, {g['warns']} warn) | docs/gates/gate_p7.md, docs/P7_report.md, docs/cost_report.md |"
    if "\n| P7 |" in t:
        t = re.sub(r"\n\| P7 \|[^\n]*", "\n" + row, t, count=1)
    else:
        t = t.rstrip("\n") + "\n" + row + "\n"
    p.write_text(t, encoding="utf-8")
    print("STATUS updated")


if __name__ == "__main__":
    main()
