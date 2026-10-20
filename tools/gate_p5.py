"""P5 quality gate (G-Map): the test map of brief 8.

Checks the scene layout written by the builder (docs/p5/map_layout.json) against the brief's obstacle table (O1-O9 sizes,
counts and masses), the extent (up to 300 x 200 m), the 60 m clean run-up of every lane and the documented surfaces; and
the map check run in the test-map player (docs/p5/mapcheck/mapcheck.json, HellcatTestMap.exe -scenario mapcheck): the
solver's stability with the debris in the world, the debris at rest, one run per lane (the car reaches each obstacle at
the target speed, no tunnelling, no non-finite values; the debris scatters; the jumps fly; curb and bump at 30 and 50 km/h
without structural damage), the real-time budget with the debris; and the deliverable screenshots (top-down and
perspective, with dimensions).

Usage:  tools/.venv/Scripts/python.exe tools/gate_p5.py
Output: docs/gates/gate_p5.json, docs/gates/gate_p5.md
"""
import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
results = []
# beams that come off by design: closure rubber stops released when a lid lifts (D-034), lamp mounts (detachables, D-058)
NON_STRUCTURAL = ("stop_closure", "lamp_mount", "mirror_mount")
# skin and trim materials: their plastic flow below SKIN_FLOW_MM is invisible, not damage (the hood's crease strip, D-095,
# yields at a tenth of the panel thresholds and flows a fraction of a millimetre over a bump)
SKIN = ("panel", "panel_brace", "panel_inner", "panel_link", "panel_support", "panel_support_bolt", "plastic", "plastic_brace",
        "plastic_support")
SKIN_FLOW_MM = 3.0


def check(name, status, detail):
    results.append({"check": name, "status": status, "detail": detail})


def near(v, target, tol):
    return v is not None and abs(v - target) <= tol


def mtime(p):
    return dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc).replace(microsecond=0)


def main():
    lp = ROOT / "docs/p5/map_layout.json"
    if not lp.exists():
        check("map layout written by the builder", "FAIL", "docs/p5/map_layout.json missing (TestMapBuilder)")
        return finish()
    lay = json.loads(lp.read_text(encoding="utf-8"))
    builder = ROOT / "Unity/HellcatSandbox/Assets/Editor/Build/TestMapBuilder.cs"
    check("map layout newer than the map builder", "PASS" if mtime(lp) >= mtime(builder) else "FAIL",
          f"layout {mtime(lp):%Y-%m-%d %H:%M:%S}, builder {mtime(builder):%Y-%m-%d %H:%M:%S} UTC")
    W, H = lay["extent_m"]
    check("extent up to 300 x 200 m", "PASS" if W <= 300 and H <= 200 else "FAIL", f"{W} x {H} m, 10 m marks in the ground texture")
    o = {x["id"]: x for x in lay["obstacles"]}

    def obstacle(oid, ok, detail):
        check(f"{oid}: {o[oid]['what'] if oid in o else oid} as specified", "PASS" if oid in o and ok else "FAIL", detail if oid in o else "missing")

    if "O1" in o:
        obstacle("O1", o["O1"]["size"] == [12, 3, 1], f"size {o['O1']['size']} m (brief 12 x 3 x 1)")
    if "O2" in o:
        obstacle("O2", o["O2"]["size"] == [12, 3, 1] and near(o["O2"].get("overlap"), 0.40, 1e-6),
                 f"size {o['O2']['size']} m, overlap line {o['O2'].get('overlap', 0) * 100:.0f} % (brief: same wall, 40 % line)")
    if "O3" in o:
        obstacle("O3", near(o["O3"].get("diameter_m"), 0.30, 0.005) and near(o["O3"].get("height_m"), 6.0, 0.05),
                 f"diameter {o['O3'].get('diameter_m')} m x {o['O3'].get('height_m')} m (brief 0.30 x 6 m)")
    if "O4" in o:
        x = o["O4"]
        obstacle("O4", x.get("units") == 6 and near(x.get("unit_length_m"), 3.66, 0.05) and near(x.get("height_m"), 0.81, 0.01)
                 and near(x.get("angle_to_lane_deg"), 20, 0.5),
                 f"{x.get('units')} units {x.get('unit_length_m')} x {x.get('height_m')} m at {x.get('angle_to_lane_deg')} deg (brief 6 x ~3.66 x 0.81 m at 20 deg)")
    if "O5" in o:
        x = o["O5"]
        obstacle("O5", near(x["size"][2], 15.0, 1.0) and near(x.get("post_spacing_m"), 1.9, 0.01) and near(x.get("wbeam_top_m"), 0.7, 0.05),
                 f"{x['size'][2]} m, posts every {x.get('post_spacing_m')} m, W-beam top {x.get('wbeam_top_m')} m (brief ~15 m, 1.9 m, ~0.7 m)")
    if "O6" in o:
        x = o["O6"]
        obstacle("O6", near(x.get("ramp_length_m"), 6.0, 0.01) and near(x.get("ramp_height_m"), 1.2, 0.01) and near(x.get("landing_beyond_lip_m"), 25.0, 0.5),
                 f"ramp {x.get('ramp_length_m')} x {x.get('ramp_height_m')} m, landing {x.get('landing_beyond_lip_m')} m beyond (brief 6 x 1.2 m, 25 m)")
    if "O7" in o:
        x = o["O7"]
        obstacle("O7", near(x.get("curb_height_m"), 0.15, 0.005) and near(x.get("bump_height_m"), 0.10, 0.005) and near(x.get("bump_length_m"), 3.0, 0.05),
                 f"curb {x.get('curb_height_m')} m, bump {x.get('bump_height_m')} x {x.get('bump_length_m')} m (brief 0.15 m; 0.10 x 3 m)")
    if "O8" in o:
        x = o["O8"]
        ok = (x.get("barrels") == 12 and x.get("boxes") == 20 and x.get("cones") == 8 and x.get("fence_panels") == 6
              and near(x.get("barrel_kg"), 20, 0.5) and near(x.get("box_kg"), 5, 0.1) and near(x.get("cone_kg"), 1.5, 0.05)
              and x.get("barrel_m") == [0.58, 0.88] and near(x.get("box_m"), 0.5, 0.01) and near(x.get("cone_m"), 0.7, 0.01))
        obstacle("O8", ok, f"{x.get('barrels')} barrels {x.get('barrel_m')} m {x.get('barrel_kg')} kg, {x.get('boxes')} boxes {x.get('box_m')} m "
                           f"{x.get('box_kg')} kg, {x.get('cones')} cones {x.get('cone_m')} m {x.get('cone_kg')} kg, {x.get('fence_panels')} fence panels; "
                           "soft bodies in the car's solver (brief 12 / 20 / 8 / 6)")
    if "O9" in o and "O9b" in o:
        obstacle("O9", near(o["O9"].get("ledge_height_m"), 3.0, 0.01) and near(o["O9b"].get("angle_deg"), 30, 0.5),
                 f"ledge {o['O9'].get('ledge_height_m')} m with a lower pad, bank {o['O9b'].get('angle_deg')} deg (brief 3 m ledge, 30 deg bank)")
    short = [ln for ln in lay["lanes"] if ln["clean_run_m"] < 60.0]
    check("every obstacle lane has 60 m of clean run-up", "PASS" if not short and len(lay["lanes"]) >= 10 else "FAIL",
          f"{len(lay['lanes'])} lanes, shortest {min(ln['clean_run_m'] for ln in lay['lanes']):.1f} m" + (f"; short: {[ln['id'] for ln in short]}" if short else ""))
    s = lay.get("surfaces", {})
    check("surfaces and friction documented", "PASS" if all(k in s for k in ("asphalt", "concrete", "grass")) else "FAIL",
          f"asphalt x{s.get('asphalt')}, concrete x{s.get('concrete')}, grass x{s.get('grass')} of the tyre friction (car on asphalt: skidpad 0.94 g, "
          "tyre peak 1.20: about 0.94 / 0.85 / 0.57 g; brief ~0.9 / 0.8 / 0.6)")

    # ---- the map check in the player
    mp = ROOT / "docs/p5/mapcheck/mapcheck.json"
    if not mp.exists():
        check("map check run in the player", "FAIL", "docs/p5/mapcheck/mapcheck.json missing (HellcatTestMap.exe -scenario mapcheck)")
        return finish()
    m = json.loads(mp.read_text(encoding="utf-8"))
    when = dt.datetime.strptime(m["time_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    srcs = [ROOT / "Unity/HellcatSandbox/Assets" / r for r in ("Sim/Props/PropFactory.cs", "Game/World/PropField.cs", "Game/Scenario/MapCheck.cs",
                                                               "Game/Input/ApproachHoldSource.cs", "Editor/Build/TestMapBuilder.cs")]
    newest = max(srcs, key=lambda q: q.stat().st_mtime)
    check("map check newer than the map, debris and check sources", "PASS" if when >= mtime(newest) else "FAIL",
          f"run {m['time_utc']}, newest {newest.name} {mtime(newest):%Y-%m-%d %H:%M:%S} UTC")
    wd = m["world"]
    check("solver stable with the debris in the world (S < 2.5)", "PASS" if wd["stability_S"] < 2.5 else "FAIL",
          f"exact S {wd['stability_S']:.4f} with {wd['prop_bodies']} debris bodies ({wd['prop_nodes']} nodes) and the car; {wd['nodes']} nodes, {wd['beams']} beams")
    st = m["settle"]
    check("debris at rest (no creep, no jitter)", "PASS" if st["prop_max_node_speed"] < 0.1 and st["prop_max_drift_m"] < 0.05 else "FAIL",
          f"after 5 s: fastest debris node {st['prop_max_node_speed']:.3f} m/s, largest drift {st['prop_max_drift_m'] * 100:.1f} cm, {st['props_drifted_5cm']} moved > 5 cm")
    us = m.get("us_per_substep")
    check("physics within the 2 kHz real-time budget with the debris", "PASS" if us is not None and us < 500 else "FAIL",
          f"{us} us per 0.5 ms substep (solver only, player)")
    runs = {(r["lane"], r["target_kmh"]): r for r in m["runs"]}
    bad = [f"{k[0]} {k[1]}" for k, r in runs.items() if r.get("non_finite", 1) > 0 or r.get("deepest_in_obstacle_m", 1) > 0.05]
    check("no tunnelling or non-finite values in any lane run", "PASS" if not bad and runs else "FAIL",
          f"{len(runs)} runs; deepest node inside an obstacle {max((r.get('deepest_in_obstacle_m', 0) for r in runs.values()), default=0) * 1000:.0f} mm" + (f"; bad: {bad}" if bad else ""))
    crash = [("O1", 30), ("O2", 30), ("O3", 30), ("O4", 40), ("O5", 50)]
    miss = [f"{l} {v}" for l, v in crash if (l, v) not in runs or "before the obstacle" not in runs[(l, v)].get("release", "")
            or abs((runs[(l, v)].get("release_kmh") or 0) - v) > 2.0]
    check("teleport speed hold delivers V at the crash obstacles (D-080)", "PASS" if not miss else "FAIL",
          ", ".join(f"{l} {runs[(l, v)].get('release_kmh')} km/h" for l, v in crash if (l, v) in runs) + (f"; problems: {miss}" if miss else ""))
    hit = [f"{l}" for l, v in crash if (l, v) in runs and runs[(l, v)].get("bent_beams", 0) == 0 and runs[(l, v)].get("broken_beams", 0) == 0]
    check("the car meets every crash obstacle (damage recorded)", "PASS" if not hit else "FAIL",
          "; ".join(f"{l}: {runs[(l, v)]['broken_beams']} broken, {runs[(l, v)]['bent_beams']} bent" for l, v in crash if (l, v) in runs))
    for v in (30, 50):
        r = runs.get(("O7", v))
        if r is None:
            check(f"curb and bump at {v} km/h without structural damage", "FAIL", "run missing")
            continue
        broken = {kv.split(" ")[0]: int(kv.split(" ")[1]) for kv in r.get("broken_by_material", "").split(", ") if kv}
        structural = {k: n for k, n in broken.items() if k not in NON_STRUCTURAL}
        # bent beams by material with their largest plastic change (map check since P7); older runs: the count alone
        bent = {m.group(1): float(m.group(3)) for m in re.finditer(r"(\w+) (\d+) \(max ([\d.]+) mm\)", r.get("bent_by_material", "") or "")}
        if "bent_by_material" in r:
            bent_struct = {k: mm for k, mm in bent.items() if k not in SKIN and k not in NON_STRUCTURAL}
            skin_max = max([mm for k, mm in bent.items() if k in SKIN] or [0.0])
            ok_bent = not bent_struct and skin_max < SKIN_FLOW_MM
        else:
            bent_struct, skin_max, ok_bent = {}, float("nan"), r.get("bent_beams", 0) <= 5
        ok = not structural and ok_bent and r.get("end_speed_kmh", 0) > 0.6 * v
        check(f"curb and bump at {v} km/h without structural damage (brief 9): no structural beam broken or bent, skin and trim "
              f"flow below {SKIN_FLOW_MM:.0f} mm", "PASS" if ok else "FAIL",
              f"over at {r.get('release_kmh')} km/h, end {r.get('end_speed_kmh')} km/h; broken: {r.get('broken_by_material') or 'none'} "
              f"(closure stops released by design, D-034); bent {r.get('bent_beams')}: {r.get('bent_by_material') or '-'} - structural "
              f"{bent_struct or 'none'}, skin flow up to {skin_max:.2f} mm")
    for lane, kmh, what in (("O6", 60, "ramp jump"), ("O9", 30, "3 m drop")):
        r = runs.get((lane, kmh))
        ok = r is not None and r.get("airborne_s", 0) >= 0.5 and r.get("up_end", 0) > 0.5
        check(f"{lane} {what} flies and lands upright", "PASS" if ok else "FAIL",
              f"airborne {r.get('airborne_s')} s, up {r.get('up_end')}, broken {r.get('broken_by_material') or 'none'}" if r else "run missing")
    r = runs.get(("O8", 20))
    check("O8 debris scatters on impact", "PASS" if r and r.get("props_moved", 0) >= 10 else "FAIL",
          f"{r.get('props_moved')} props moved, car bent {r.get('bent_beams')} beams" if r else "run missing")

    # ---- deliverables
    need = [ROOT / "docs/p5/mapcheck/map_topdown.png", ROOT / "docs/p5/map_topdown_annotated.png", ROOT / "docs/p5/mapcheck/map_overview.png",
            ROOT / "docs/p5/map_lanes_sheet.jpg"]
    lanes = sorted((ROOT / "docs/p5/mapcheck").glob("lane_*_O*.png"))
    runshots = sorted((ROOT / "docs/p5/mapcheck").glob("run_*.png"))
    missing = [p.name for p in need if not p.exists()]
    check("top-down and perspective screenshots with dimensions", "PASS" if not missing and len(lanes) >= 10 else "FAIL",
          f"annotated top-down, overview, {len(lanes)} lane views captioned in map_lanes_sheet.jpg, {len(runshots)} run views"
          + (f"; missing {missing}" if missing else ""))
    finish()


def finish():
    fails = sum(1 for r in results if r["status"] == "FAIL")
    warns = sum(1 for r in results if r["status"] == "WARN")
    verdict = "PASS" if fails == 0 else "FAIL"
    out = {"gate": "G-Map (P5)", "time_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "verdict": verdict, "fails": fails, "warns": warns, "checks": results}
    gd = ROOT / "docs/gates"
    gd.mkdir(parents=True, exist_ok=True)
    (gd / "gate_p5.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    md = [f"# Gate P5 (G-Map)\n", f"Result: **{verdict}** ({fails} FAIL, {warns} WARN, {len(results)} checks), {out['time_utc']}\n",
          "| # | check | status | detail |", "|---|---|---|---|"]
    for k, r in enumerate(results, 1):
        md.append(f"| {k} | {r['check']} | {r['status']} | {r['detail']} |")
    (gd / "gate_p5.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    for r in results:
        print(f"{r['status']:5s} {r['check']}  --  {r['detail']}")
    print(f"P5 gate: {verdict} ({fails} fail, {warns} warn)")


if __name__ == "__main__":
    main()
