"""P1b quality gate (G-Interior): interior and cockpit view.

Inputs:
    docs/gates/p1b_interior_audit.json   hcar.gate_interior:audit (names, materials, UVs, triangles,
                                         intersections, coincident faces, eye clearance, needle angles,
                                         steering wheel rotation)
    docs/p1b/photo_cams/cabin2.json      tools/ref/interior_pnp.py (camera fitted to reference/Interior 2.jpg)
    sim/vehicle/hellcat/cockpit.json     hcar.interior:export_cockpit (pivots / axes for Unity)
    docs/video_assets/P1b/               renders (driver view, gauges, steering, cut-aways, animation)

Usage:  tools/.venv/Scripts/python.exe tools/gate_p1b.py
Output: docs/gates/gate_p1b.json and docs/gates/gate_p1b.md
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
results = []

REQUIRED = ["CH_Int_Dash", "CH_Int_ClusterHood", "CH_Int_Cluster", "CH_Int_Needle_Tach", "CH_Int_Needle_Speedo",
            "CH_Int_SteeringWheel", "CH_Int_SteeringColumn", "CH_Int_CentreStack", "CH_Int_Console", "CH_Int_Shifter",
            "CH_Int_Armrest", "CH_Int_DashExtras", "CH_Int_Pedal_Accelerator", "CH_Int_Pedal_Brake", "CH_Int_Footrest",
            "CH_Int_Mirror", "CH_Int_Seat_FL", "CH_Int_Seat_FR", "CH_Int_Seat_Rear", "CH_Int_DoorCard_L",
            "CH_Int_DoorCard_R", "CH_Int_QuarterTrim_L", "CH_Int_QuarterTrim_R", "CH_Int_BPillar_L", "CH_Int_BPillar_R",
            "CH_Int_APillar_L", "CH_Int_APillar_R", "CH_Int_Headliner", "CH_Int_SunVisors", "CH_Int_Carpet",
            "CH_Int_Sill_L", "CH_Int_Sill_R", "CH_Int_PackageShelf", "CH_Int_Belts", "CH_Glass_Frit"]


def check(name, status, detail):
    results.append({"check": name, "status": status, "detail": detail})


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8-sig"))


def main():
    a = load("docs/gates/p1b_interior_audit.json")
    names = set(a["triangles_by_part"])
    missing = [n for n in REQUIRED if n not in names]
    check("all interior parts present and named (CH_Int_*)", "PASS" if not missing and not a["bad_names"] else "FAIL",
          f"{a['objects']} objects; missing {missing or 'none'}; bad names {a['bad_names'] or 'none'}")
    check("every interior mesh has a material and UVs", "PASS" if not a["no_material"] and not a["no_uv"] else "FAIL",
          f"no material: {a['no_material'] or 'none'}; no UV: {a['no_uv'] or 'none'}")
    t = a["triangles"]
    check("interior triangle budget 150k-400k", "PASS" if 150_000 <= t <= 400_000 else "FAIL",
          f"{t:,} triangles; largest: " + ", ".join(f"{k.replace('CH_Int_', '')} {v:,}" for k, v in
                                                    list(a["triangles_by_part"].items())[:6]))
    ui, cf = a["unexpected_intersections"], a["coincident_faces"]
    check("no clipping: no unexpected intersections (interior x interior and x exterior), no coincident faces",
          "PASS" if not ui and not cf else "FAIL",
          f"unexpected {ui or 'none'}; coincident {cf or 'none'}; {len(a['contacts_by_design'])} contacts by design "
          "(mounted parts, parts resting on the carpet, belts)")
    ec = a["eye_clearance_m"]
    check("cockpit camera clear of geometry (near clip 0.01 m)", "PASS" if ec["distance"] > 0.05 else "FAIL",
          f"nearest geometry to the eye point: {ec['nearest']} at {ec['distance']} m")
    nd = a["needles"]
    worst = max(n["error_deg"] for n in nd)
    check("gauges respond to test values (0 / 3000 / 6000 rpm, 0 / 100 / 200 mph)", "PASS" if worst < 0.1 else "FAIL",
          "; ".join(f"{n['gauge']} {n['value']}: {n['angle_deg']} deg (expected {n['expected_deg']})" for n in nd)
          + "; renders 2026-10-11_P1b_gauges_*.png")
    sw = a["steering_wheel"]
    ok = all(abs(((s["rim_top_angle_deg"] - s["steer_deg"] + 180) % 360) - 180) < 0.1 and abs(s["axial_offset_mm"]) < 0.1
             for s in sw)
    check("steering wheel rotates about the column axis with the steering input", "PASS" if ok else "FAIL",
          "; ".join(f"{s['steer_deg']} deg -> rim top at {s['rim_top_angle_deg']} deg, off-plane {s['axial_offset_mm']} mm"
                    for s in sw) + "; renders 2026-10-11_P1b_steer_*.png and the cockpit animation")
    cam = load("docs/p1b/photo_cams/cabin2.json")
    pp = cam["per_point_px"]
    lay_ok = cam["rms_pct_width"] <= 2.0 and all(pp[k] < 40 for k in ("wheel_badge", "tach_centre", "screen_tl",
                                                                     "screen_br", "start_button"))
    check("layout matches the reference (wheel, cluster, centre screen, vents, start button, console) - camera fitted "
          "to reference/Interior 2.jpg", "PASS" if lay_ok else "FAIL",
          f"fit on {len(cam['fit_landmarks'])} landmarks: RMS {cam['rms_fit_px']} px ({cam['rms_pct_width']} % of the "
          f"width), lens {cam['lens_mm_36']} mm eq.; residuals (px): " + ", ".join(f"{k} {v}" for k, v in pp.items())
          + "; overlay docs/p1b/photo_cams/overlay_cabin2.jpg")
    ck = load("sim/vehicle/hellcat/cockpit.json")
    eye_z = ck["eye"][2]
    check("driver eye point and field of view", "PASS" if 1.05 <= eye_z <= 1.21 and 80 <= ck["fov_h_deg"] <= 95 else "FAIL",
          f"eye {ck['eye']} m (z {eye_z} m: brief 1.05-1.10, SAE estimate 1.16 +- 0.05, decision D-020), horizontal "
          f"FOV {ck['fov_h_deg']} deg (configurable in Unity)")
    check("mirrors show the scene behind the car", "WARN",
          "needs the Unity runtime: render-texture cameras on CH_Int_Mirror / CH_Mirror_Glass_L/R are implemented and "
          "verified in P4b (cockpit.json carries the mirror frames)")
    va = ROOT / "docs/video_assets/P1b"
    pics = sorted(p.name for p in va.glob("*.png"))
    vids = sorted(p.name for p in va.glob("*.mp4"))
    check("evidence: driver-view screenshots, cut-aways, gauge and steering renders, cockpit animation",
          "PASS" if len(pics) >= 10 and vids else "FAIL", f"{len(pics)} stills, videos: {', '.join(vids) or 'none'}")

    failed = sum(r["status"] == "FAIL" for r in results)
    warned = sum(r["status"] == "WARN" for r in results)
    out = ROOT / "docs/gates"
    (out / "gate_p1b.json").write_text(json.dumps({"gate": "P1b (G-Interior)", "pass": failed == 0, "fail": failed,
                                                   "warn": warned, "checks": results}, indent=2), encoding="utf-8")
    lines = ["# Gate P1b (G-Interior)", "", f"Result: **{'PASS' if failed == 0 else 'FAIL'}** ({failed} FAIL, {warned} WARN, "
             f"{len(results)} checks)", "", "| # | Check | Status | Detail |", "|---|---|---|---|"]
    lines += [f"| {i} | {r['check']} | {r['status']} | {r['detail'].replace('|', '/')} |" for i, r in enumerate(results, 1)]
    (out / "gate_p1b.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for r in results:
        print(f"{r['status']:4}  {r['check']}  --  {r['detail'][:240]}")
    print(f"P1b gate: {'PASS' if failed == 0 else 'FAIL'} ({failed} fail, {warned} warn)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
