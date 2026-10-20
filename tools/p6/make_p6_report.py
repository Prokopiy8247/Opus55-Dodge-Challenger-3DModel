"""Writes docs/P6_report.md from the P6 results: the gate (docs/gates/gate_p6.json), the per-scenario summary
(docs/p6/scenario_summary.csv), the driven variants, the sensitivity sweep (docs/p6/sensitivity.json), the NHTSA reference
(docs/p6/refs) and the video assets (docs/video_assets/P6). Narrative sections come from NOTES below.

Usage: tools/.venv/Scripts/python.exe tools/p6/make_p6_report.py
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRIEF = {"S1": 50, "S2": 64, "S3": 50, "S4": 40, "S5": 80, "S6": 70, "S7": 15, "S8": 120}
NOTES = ROOT / "docs/p6/report_notes.md"   # hand-written analysis, inserted after the summary


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def f(v, n=3):
    if v in (None, "", "None"):
        return "-"
    try:
        x = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"{x:.{n}g}" if abs(x) < 1000 else f"{x:.0f}"


def main():
    gate = load(ROOT / "docs/gates/gate_p6.json")
    rows = list(csv.DictReader(open(ROOT / "docs/p6/scenario_summary.csv", encoding="utf-8")))
    by = {(r["scenario"], int(r["target_kmh"])): r for r in rows}
    md = ["# P6 report: all scripted scenarios, driven runs and tuning", "",
          f"Gate G-Crash (P6): **{gate['verdict']}** ({gate['fails']} FAIL, {gate['warns']} WARN, {len(gate['checks'])} checks, "
          "`docs/gates/gate_p6.md`).", ""]
    if NOTES.exists():
        md += [NOTES.read_text(encoding="utf-8").strip(), ""]

    md += ["## Per-scenario summary (brief speeds)", "",
           "Cabin centre of mass filtered CFC 60 (SAE J211). Crush: cabin travel after the contact (dynamic) and the bumper beam's "
           "set-back at rest (residual, struck side for S2 / S3). Deformation: largest structure-node displacement against the rigid "
           "rear cabin. Intrusion: largest rearward displacement of the IIHS-like points. Broken beams exclude closure stops "
           "letting go (D-088).", "",
           "| scenario | entry km/h | crush dyn / res m | deformation m | peak g (long / resultant) | pulse ms | broken | plastic kJ | detached | intrusion cm | event |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for sc, v in BRIEF.items():
        r = by.get((sc, v))
        if not r:
            md.append(f"| {sc} {v} | not run |||||||||| ")
            continue
        res = f(r["crush_left_m"]) if sc == "S2" and r["crush_left_m"] not in ("", None) else f(r["residual_crush_m"])
        ev = ""
        if r["airborne_s"] not in ("", None):
            ev = f"airborne {f(r['airborne_s'])} s over {f(r['jump_m'])} m, landing {f(r['landing_vy'])} m/s, {f(r['landing_vert_cfc60_g'])} g vertical"
        elif r["contact_s"] not in ("", None):
            ev = f"sliding {f(r['contact_s'])} s, leaves at {f(r['exit_kmh'])} km/h, {f(r['exit_heading_deg'])} deg"
        elif sc == "S7":
            ev = f"{r['props_moved']} props moved (up to {f(r['props_max_m'])} m)"
        md.append(f"| {sc} {r['what']} | {f(r['entry_kmh'])} | {f(r['dynamic_crush_m'])} / {res} | {f(r['max_deformation_m'])} | "
                  f"{f(r['peak_long_cfc60_g'])} / {f(r['peak_res_cfc60_g'])} | {f(r['pulse_ms'])} | {r['broken_beams']} | {r['plastic_kJ']} | "
                  f"{r['detached'] or '-'} | {f(r['intrusion_max_cm'])} | {ev or '-'} |")
    md += ["", "Full table with the speed series: `docs/p6/scenario_summary.md` / `.csv`.", ""]

    # speed series
    md += ["## Damage against speed", "", "| scenario | km/h | entry | crush dyn / res m | deformation m | plastic kJ | broken | detached |",
           "|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r["scenario"], int(r["target_kmh"]))):
        md.append(f"| {r['scenario']} | {r['target_kmh']} | {f(r['entry_kmh'])} | {f(r['dynamic_crush_m'])} / {f(r['residual_crush_m'])} | "
                  f"{f(r['max_deformation_m'])} | {r['plastic_kJ']} | {r['broken_beams']} | {r['detached'] or '-'} |")
    md += ["", "![damage vs speed](p6/plots/damage_vs_speed.png)", "", "![frontal pulses](p6/plots/frontal_pulses.png)", "",
           "![event pulses](p6/plots/event_pulses.png)", "", "![energy](p6/plots/energy_vs_time.png)", ""]

    # driven variants
    md += ["## Driven variants (teleport with the speed hold, F5 / F6)", "",
           "| scenario | released at km/h | broken | deformation m | detached | recording | replay |", "|---|---|---|---|---|---|---|"]
    for sc, v in BRIEF.items():
        jf = ROOT / "sim/cache" / sc / "driven" / f"{sc}_{v}kmh_driven.json"
        if not jf.exists():
            continue
        j = load(jf)
        md.append(f"| {sc} {v} | {f(j.get('release_kmh'))} ({j.get('release', '')}) | {j.get('broken_beams')} | {f(j.get('max_deformation_m'))} | "
                  f"{'+'.join(j.get('detached_parts', [])) or '-'} | {j.get('recording')} ({f(j.get('recording_s'))} s, "
                  f"{j.get('recording_bytes', 0) / 1e6:.2f} MB) | {'identical' if j.get('replay_identical') else 'DIFFERS'} |")
    md.append("")

    # sweep
    sp = ROOT / "docs/p6/sensitivity.md"
    if sp.exists():
        md += [sp.read_text(encoding="utf-8").replace("\n## ", "\n### ").replace("# P6 sensitivity sweep (brief 15.5)",
                                                                               "## Sensitivity sweep (brief 15.5)").rstrip(), "",
               "The sweep ran on the P6-005 parameters, before the front calibration x0.7 (D-096), which it informed: the rail "
               "yield alone (its cap unchanged) and the break strengths of rails and bumper clips hardly change the 56 km/h crash "
               "(no rail or clip breaks there), while the tyre pressure and the dampers move the peak and the rebound - the front "
               "wheels reach the wall. The calibrated car's S1 56 km/h is in the summary above (crush 0.567 m, peak 52 g).", ""]

    # videos
    vd = ROOT / "docs/video_assets/P6"
    if vd.exists():
        vids = sorted(p.name for p in vd.glob("*.mp4"))
        md += ["## Captures", "", f"{len(vids)} videos in `docs/video_assets/P6/` (stills of every camera at the event and at the end next to them):", ""]
        md += [f"- `{v}`" for v in vids]
        md += ["", f"![scenarios](video_assets/P6/{sorted(p.name for p in vd.glob('*_scenarios_sheet.jpg'))[-1]})" if list(vd.glob("*_scenarios_sheet.jpg")) else "", ""]

    md += ["## Gate checks", "", "| # | check | status |", "|---|---|---|"]
    for k, c in enumerate(gate["checks"], 1):
        md.append(f"| {k} | {c['check']} | {c['status']} |")
    md += ["", "Details per check: `docs/gates/gate_p6.md`.", ""]
    (ROOT / "docs/P6_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("wrote docs/P6_report.md")


if __name__ == "__main__":
    main()
