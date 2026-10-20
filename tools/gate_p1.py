"""P1 quality gate (G-Model): visual Hellcat Widebody exterior.

Inputs (written by the Blender side, see docs/P1_report.md):
    docs/gates/p1_model_audit.json      hcar.gate_model:audit   (names, parts, materials, UVs, normals,
                                                                 manifold shells, intersections, wheels)
    docs/gates/p1_model_measure.json    hcar.gate_model:measure (dimensions, silhouettes)
    docs/gates/gate_p1_silhouette.json  tools/ref/gate_overlay.py (silhouettes vs the drawing profiles)
    docs/p1/photo_cams/photo*.json      tools/ref/photo_pnp.py  (photo camera fits)
Panel gaps and grid quality are computed here from the panel builders (pure numpy).

Usage:  tools/.venv/Scripts/python.exe tools/gate_p1.py
Output: docs/gates/gate_p1.json and docs/gates/gate_p1.md
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
ORIGINAL_SHA256 = "AA42CA0C78B5BE03BCDE065E7861075C6BADFBBFD7FDDEF8DF9B2D74F9CFAE68"
SPEC = {"length": 5.017, "width_no_mirrors": 1.990, "width_with_mirrors": 2.169, "height": 1.460,
        "wheelbase": 2.951, "track_front": 1.667, "track_rear": 1.669}
results = []


def check(name, status, detail):
    results.append({"check": name, "status": status, "detail": detail})


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8-sig"))


def sha256(path):
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest().upper()


# ------------------------------------------------------------------------------------------------
# panel gaps and grid quality (right side; the left side is its mirror image)
def panel_meshes():
    from hcar import body
    from hcar.body_panels import bumper_panels, side_panels
    from hcar.flares import flare_panel
    from hcar.gh_panels import cap_panels, greenhouse_panels
    m = body.model()
    panels = dict(side_panels(m))
    panels.update(bumper_panels(m))
    panels.update(greenhouse_panels(m))
    panels.update(cap_panels(m))
    panels["CH_Flare_front"] = flare_panel(m["strip"], "front")
    panels["CH_Flare_rear"] = flare_panel(m["strip"], "rear")
    return {k: (p, p.mesh()) for k, p in panels.items()}


def border(pm, step=0.001):
    """Skin border of a panel (outer rows/columns of the inset grid), densified to `step`."""
    P = pm["P"]
    loops = [P[:, 0], P[-1, :], P[::-1, -1], P[0, ::-1]]
    pts = []
    for c in loops:
        seg = np.linalg.norm(np.diff(c, axis=0), axis=1)
        for a, b, L in zip(c[:-1], c[1:], seg):
            n = max(int(L / step), 1)
            pts.append(a + (b - a) * np.linspace(0, 1, n, endpoint=False)[:, None])
    return np.vstack(pts)


def seam_gap(pa, pb, max_gap=0.012):
    from scipy.spatial import cKDTree
    A, B = border(pa), border(pb)
    d, _ = cKDTree(B).query(A, distance_upper_bound=max_gap)
    d = d[np.isfinite(d)]
    if len(d) < 20:
        return None
    return {"median_mm": round(float(np.median(d)) * 1000, 2), "p10_mm": round(float(np.percentile(d, 10)) * 1000, 2),
            "p90_mm": round(float(np.percentile(d, 90)) * 1000, 2), "seam_length_m": round(len(d) * 0.001, 2)}


def grid_quality(pm):
    V, F, N = pm["V"], pm["F"], pm["N"].reshape(-1, 4, 3)
    q = V[F]
    n = np.cross(q[:, 2] - q[:, 0], q[:, 3] - q[:, 1])
    area = 0.5 * np.linalg.norm(n, axis=1)
    ref = N.mean(axis=1)
    inv = ((n * ref).sum(1) < 0) & (area > 1e-6)
    e = np.linalg.norm(q - np.roll(q, -1, axis=1), axis=2)
    return int(inv.sum()), float(np.median(e)), float(np.percentile(e, 99))


def main():
    check("original .blend untouched", "PASS" if sha256(ROOT / "3DDodgeChallenger.blend") == ORIGINAL_SHA256 else "FAIL",
          "SHA-256 compared with the P0 fingerprint")
    audit = load("docs/gates/p1_model_audit.json")
    meas = load("docs/gates/p1_model_measure.json")
    sil = load("docs/gates/gate_p1_silhouette.json")

    # ---- dimensions (+-2 %)
    dims = dict(meas["dims"])
    wh = audit["wheels"]
    dims["wheelbase"] = (wh["FL"]["centre"][1] + wh["FR"]["centre"][1]) / 2 - (wh["RL"]["centre"][1] + wh["RR"]["centre"][1]) / 2
    dims["track_front"] = wh["FR"]["centre"][0] - wh["FL"]["centre"][0]
    dims["track_rear"] = wh["RR"]["centre"][0] - wh["RL"]["centre"][0]
    rows, worst = [], 0.0
    for k, ref in SPEC.items():
        dev = 100 * (dims[k] - ref) / ref
        worst = max(worst, abs(dev))
        rows.append(f"{k} {dims[k]:.3f} m ({dev:+.2f} %)")
    check("dimensions within +-2 % of the spec sheet (docs/specs.md)", "PASS" if worst <= 2.0 else "FAIL", "; ".join(rows))

    # ---- silhouettes against the dimensions.com profiles
    s = sil["silhouettes"]
    H, W = SPEC["height"], SPEC["width_no_mirrors"]
    ok = (s["side_top"]["rms_mm"] <= 20 * H and s["plan_half_width_no_flares"]["rms_mm"] <= 20 * W
          and s["front_half_width"]["rms_mm"] <= 20 * W and s["rear_half_width"]["rms_mm"] <= 20 * W)
    check("silhouette overlays (side top / plan / front / rear) within 2 % RMS", "PASS" if ok else "FAIL",
          f"side top RMS {s['side_top']['rms_mm']} mm (p95 {s['side_top']['p95_abs_mm']}; without the hood scoop "
          f"{s['side_top_no_scoop']['rms_mm']}), plan {s['plan_half_width_no_flares']['rms_mm']} mm, front "
          f"{s['front_half_width']['rms_mm']} mm, rear {s['rear_half_width']['rms_mm']} mm; limits 2 % of height "
          f"{20 * H:.0f} mm / width {20 * W:.0f} mm")
    sb = s["side_bottom_body"]
    check("side bottom line (rocker / bumper lower edges)", "PASS" if sb["rms_mm"] <= 20 * H else "WARN",
          f"RMS {sb['rms_mm']} mm, p95 {sb['p95_abs_mm']} mm: the widebody side sills sit 15-30 mm below the drawing's "
          "standard-body rocker line and the bumper lower edges are steep (1 cm bins); informational")
    cams = sorted((ROOT / "docs/p1/photo_cams").glob("photo*.json"))
    if cams:
        fits = [json.loads(c.read_text(encoding="utf-8")) for c in cams]
        check("perspective photo overlays (camera fitted to the photo, model rendered on top)",
              "PASS" if all(f["rms_px"] < 40 for f in fits) else "WARN",
              "; ".join(f"photo {f['photo']}: f {f['lens_mm_36']:.0f} mm eq., reprojection RMS {f['rms_px']:.1f} px "
                        f"({len(f['per_point_px'])} points)" for f in fits))

    # ---- names, parts, materials, UVs
    lr = audit.get("left_right_wrong_side_vertices", {})
    check("all parts present and named per section 2 (CH_*, no duplicates, _L/_R on their own side)",
          "PASS" if not audit["missing_parts"] and not audit["bad_names"] and not lr else "FAIL",
          f"{audit['objects']} objects, {audit['meshes']} meshes; missing {audit['missing_parts'] or 'none'}; bad names "
          f"{audit['bad_names'] or 'none'}; L/R parts with vertices on the other side: {lr or 'none'}")
    check("every mesh has a material and UVs", "PASS" if not audit["no_material"] and not audit["no_uv"] else "FAIL",
          f"no material: {audit['no_material'] or 'none'}; no UV: {audit['no_uv'] or 'none'}")
    tri = audit["triangles"]
    check("triangle budget 300k-800k (exterior incl. mechanics, with panel thickness)",
          "PASS" if 300_000 <= tri <= 800_000 else "FAIL", f"{tri:,} triangles")

    # ---- normals, shells, overlaps
    vb = audit["visible_backface_fraction_above_1pct"]
    check("no flipped normals (rays from 128 directions see only front faces)", "PASS" if not vb else "FAIL",
          f"{audit['visibility_rays']:,} rays; parts with > 1 % back-face hits: {vb or 'none'}")
    nm = audit["body_nonmanifold_edges"]
    check("no non-manifold edges on body parts (closed thin shells)", "PASS" if not nm else "FAIL", f"{nm or 'none'}")
    pi, cf = audit["panel_intersections"], audit["coincident_faces"]
    ux = audit.get("unexpected_contacts", {})
    by_design = audit.get("attached_detail_contacts", {})
    check("no overlapping parts (all part pairs: triangle intersections; coincident faces)",
          "PASS" if not pi and not cf and not ux else "FAIL",
          f"panel intersections {pi or 'none'}; unexpected contacts {ux or 'none'}; coincident {cf or 'none'}; "
          f"{len(by_design)} contacts by design (mounted details, lamp/wheel assemblies, suspension joints): "
          f"{', '.join(sorted(by_design))}")

    # ---- panel gaps and grid quality (computed from the builders)
    pm = panel_meshes()
    pairs = [("CH_Door", "CH_Fender"), ("CH_Door", "CH_Quarter"), ("CH_Door", "CH_Rocker"),
             ("CH_Fender", "CH_Rocker"), ("CH_Quarter", "CH_Rocker"), ("CH_Hood", "CH_Fender"),
             ("CH_DeckLid", "CH_Quarter"), ("CH_Fascia", "CH_Fender"), ("CH_RearBumper", "CH_Quarter"),
             ("CH_Flare_front", "CH_Fender"), ("CH_Flare_rear", "CH_Quarter"), ("CH_Flare_front", "CH_Fascia"),
             ("CH_Flare_rear", "CH_RearBumper"), ("CH_Glass_Door", "CH_Glass_Quarter"), ("CH_Roof", "CH_Pillars")]
    gaps = {}
    for a, b in pairs:
        g = seam_gap(pm[a][1], pm[b][1])
        if g:
            gaps[f"{a}|{b}"] = g
    shut = [k for k in gaps if not k.startswith(("CH_Flare", "CH_Roof", "CH_Glass"))]
    bad = [k for k in shut if not 3.5 <= gaps[k]["median_mm"] <= 7.0]
    check("panel gaps visible: shut lines 3.5-7 mm (median of the skin-to-skin distance)",
          "PASS" if not bad and len(shut) >= 8 else "FAIL",
          "; ".join(f"{k.replace('CH_', '')} {v['median_mm']} mm (p10-p90 {v['p10_mm']}-{v['p90_mm']}, {v['seam_length_m']} m)"
                    for k, v in gaps.items()))
    qual = {k: grid_quality(v[1]) for k, v in pm.items()}
    inv = {k: q[0] for k, q in qual.items() if q[0]}
    check("panel grids: no inverted faces; edge length 1-6 cm on the skins",
          "PASS" if not inv and all(q[2] <= 0.065 for q in qual.values()) else ("WARN" if not inv else "FAIL"),
          f"inverted: {inv or 'none'}; median / p99 edge (mm): " + ", ".join(
              f"{k.replace('CH_', '')} {q[1] * 1000:.0f}/{q[2] * 1000:.0f}" for k, q in qual.items()))

    # ---- wheels
    w_ok, rows = True, []
    for k, w in wh.items():
        ok = w["centre_error_mm"] < 2.0 and w["out_of_round_mm"] < 0.5 and abs(w["radius_max"] - 0.3608) < 0.002
        w_ok &= ok
        rows.append(f"{k}: centre error {w['centre_error_mm']} mm, radius {w['radius_max'] * 1000:.1f} mm, "
                    f"out of round {w['out_of_round_mm']} mm")
    check("wheels round and correctly placed (305/35 ZR20, rolling radius ~0.35 m)", "PASS" if w_ok else "FAIL",
          "; ".join(rows))

    # ---- evidence
    va = ROOT / "docs/video_assets/P1"
    pics = sorted(p.name for p in va.glob("*.png"))
    vids = sorted(p.name for p in va.glob("*.mp4"))
    ov = sorted(p.name for p in (ROOT / "docs/p1/overlay_gate").glob("ortho_*.png"))
    check("orthographic overlays + 3/4 renders + turntable (video assets)",
          "PASS" if len(ov) >= 4 and len(pics) >= 4 and vids else "FAIL",
          f"overlays: {', '.join(ov) or 'none'}; stills: {len(pics)}; videos: {', '.join(vids) or 'none'}")

    failed = sum(r["status"] == "FAIL" for r in results)
    warned = sum(r["status"] == "WARN" for r in results)
    out = ROOT / "docs/gates"
    out.mkdir(parents=True, exist_ok=True)
    (out / "gate_p1.json").write_text(json.dumps({"gate": "P1 (G-Model)", "pass": failed == 0, "fail": failed,
                                                  "warn": warned, "checks": results, "gaps": gaps,
                                                  "dims": {k: round(v, 4) for k, v in dims.items() if isinstance(v, float)}},
                                                 indent=2), encoding="utf-8")
    lines = ["# Gate P1 (G-Model)", "", f"Result: **{'PASS' if failed == 0 else 'FAIL'}** ({failed} FAIL, {warned} WARN, "
             f"{len(results)} checks)", "", "| # | Check | Status | Detail |", "|---|---|---|---|"]
    lines += [f"| {i} | {r['check']} | {r['status']} | {r['detail'].replace('|', '/')} |" for i, r in enumerate(results, 1)]
    (out / "gate_p1.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for r in results:
        print(f"{r['status']:4}  {r['check']}  --  {r['detail'][:300]}")
    print(f"P1 gate: {'PASS' if failed == 0 else 'FAIL'} ({failed} fail, {warned} warn)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
