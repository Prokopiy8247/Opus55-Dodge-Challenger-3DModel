"""G-Interior audit (Blender side): names, materials, UVs, triangle budget, intersections of interior
parts with the exterior and with each other (by-design mounts listed), coincident faces (z-fighting),
clearance around the cockpit camera, needle angles for test values, steering wheel rotation.

    audit()  -> docs/gates/p1b_interior_audit.json
"""
import json
import math
import os
from fnmatch import fnmatch

import bpy
import numpy as np

from . import PROJECT_ROOT
from . import interior_tables as it
from .gate_model import _world_tris, intersections

# contacts by design: mounted / nested interior parts, seats and trims resting on the carpet, the
# mirror glued to the windshield, belts lying on seats and trims
INT_MOUNTED = [
    ("CH_Int_SteeringColumn", "CH_Int_SteeringWheel"), ("CH_Int_SteeringColumn", "CH_Int_Dash"),
    ("CH_Int_Cluster", "CH_Int_Dash"), ("CH_Int_ClusterHood", "CH_Int_Dash"), ("CH_Int_Cluster", "CH_Int_ClusterHood"),
    ("CH_Int_Needle_*", "CH_Int_Cluster"), ("CH_Int_CentreStack", "CH_Int_Dash"), ("CH_Int_DashExtras", "CH_Int_Dash"),
    ("CH_Int_Console", "CH_Int_Dash"), ("CH_Int_Console", "CH_Int_CentreStack"), ("CH_Int_Console", "CH_Int_Carpet"),
    ("CH_Int_Shifter", "CH_Int_Console"), ("CH_Int_Armrest", "CH_Int_Console"), ("CH_Int_Pedal_*", "CH_Int_Dash"),
    ("CH_Int_Footrest", "CH_Int_Carpet"), ("CH_Int_Seat_*", "CH_Int_Carpet"), ("CH_Int_Seat_Rear", "CH_FloorPan"),
    ("CH_Int_Belts", "CH_Int_*"), ("CH_Int_Mirror", "CH_Glass_Windshield"), ("CH_Int_Mirror", "CH_Glass_Frit"),
    ("CH_Int_SunVisors", "CH_Int_Headliner"), ("CH_Int_BPillar_?", "CH_Int_QuarterTrim_?"), ("CH_Int_Sill_?", "CH_Int_Carpet"),
    ("CH_Int_APillar_?", "CH_Int_Dash"), ("CH_Int_APillar_?", "CH_Int_Headliner"), ("CH_Int_Headliner", "CH_Int_QuarterTrim_?"),
    ("CH_Int_Sill_?", "CH_Int_DoorCard_?"), ("CH_Int_Sill_?", "CH_Int_QuarterTrim_?"), ("CH_Int_PackageShelf", "CH_Int_QuarterTrim_?"),
    ("CH_Int_Carpet", "CH_Int_QuarterTrim_?"), ("CH_Int_Sill_?", "CH_Int_*Pillar*"),
]


def _mounted(a, b):
    return any((fnmatch(a, p) and fnmatch(b, q)) or (fnmatch(a, q) and fnmatch(b, p)) for p, q in INT_MOUNTED)


def needle_check():
    """Needle angle for the brief's test values, measured from the posed objects (tip direction in the
    dial frame), and the expected gauge angle."""
    from .interior import needle_frames, pose_cockpit
    out = []
    frames = needle_frames()
    for rpm, mph in ((0, 0), (3000, 100), (6000, 200)):
        pose_cockpit(rpm=rpm, mph=mph)
        bpy.context.view_layer.update()
        for key, val in (("tach", rpm), ("speedo", mph)):
            o = bpy.data.objects[f"CH_Int_Needle_{key.capitalize()}"]
            piv, R, U, A = frames[key]
            tip = np.array(o.matrix_world @ __import__("mathutils").Vector((0.0, 0.05, 0.0))) - piv
            ang = math.degrees(math.atan2(np.dot(tip, R), np.dot(tip, U)))     # clockwise from 12 o'clock
            exp = it.gauge_angle(key, val)
            out.append({"gauge": key, "value": val, "angle_deg": round(ang, 2), "expected_deg": round(exp, 2),
                        "error_deg": round(abs(ang - exp), 3)})
    pose_cockpit()
    return out


def wheel_check():
    """Steering wheel rotation about the column axis: the 12 o'clock rim point for -90 / 0 / +90 deg."""
    from mathutils import Vector
    from .interior import pose_cockpit, wheel_frame
    C, X, U, A = wheel_frame()
    o = bpy.data.objects["CH_Int_SteeringWheel"]
    res = []
    for deg in (-90.0, 0.0, 90.0, 468.0):
        pose_cockpit(steer_deg=deg)
        bpy.context.view_layer.update()
        p = np.array(o.matrix_world @ Vector((0.0, it.WHEEL_R, 0.0))) - C
        ang = math.degrees(math.atan2(np.dot(p, X), np.dot(p, U)))
        axial = float(np.dot(p, A))
        res.append({"steer_deg": deg, "rim_top_angle_deg": round(ang, 2), "axial_offset_mm": round(axial * 1000, 3)})
    pose_cockpit()
    return res


def audit():
    from mathutils.bvhtree import BVHTree
    from mathutils import Vector
    dg = bpy.context.evaluated_depsgraph_get()
    col = bpy.data.collections["Car_Interior"]
    ints = [o for o in col.all_objects if o.type == "MESH"]
    ext = [o for o in bpy.data.collections["Car_Visual"].all_objects if o.type == "MESH"]
    res = {"objects": len(ints)}
    res["bad_names"] = [o.name for o in ints if not o.name.startswith("CH_") or "." in o.name]
    res["no_material"] = [o.name for o in ints if not any(s.material for s in o.material_slots)]
    res["no_uv"] = [o.name for o in ints if not o.data.uv_layers]
    tri = {}
    for o in ints:
        co, t = _world_tris(o, dg)
        tri[o.name] = len(t)
    res["triangles"] = int(sum(tri.values()))
    res["triangles_by_part"] = dict(sorted(tri.items(), key=lambda kv: -kv[1]))
    # intersections: interior x (interior + exterior)
    pairs = intersections(ints + ext, dg, max_pairs=20000)
    ok, bad = {}, {}
    for key, n in pairs.items():
        a, b = key.split("|")
        if not (a.startswith("CH_Int_") or b.startswith("CH_Int_") or "Frit" in a or "Frit" in b):
            continue                         # exterior-only pairs belong to the G-Model audit
        (ok if _mounted(a, b) else bad)[key] = n
    res["contacts_by_design"] = ok
    res["unexpected_intersections"] = bad
    # coincident faces between an interior part and any other part (z-fighting)
    trees = {}
    for o in ints + ext:
        co, t = _world_tris(o, dg)
        if len(t):
            trees[o.name] = (BVHTree.FromPolygons(co.tolist(), t.tolist(), all_triangles=True), co, t)
    overlaps = {}
    for o in ints:
        co, t, = trees[o.name][1], trees[o.name][2]
        if not len(t):
            continue
        cen = co[t].mean(axis=1)[::3]
        nrm = np.cross(co[t[:, 1]] - co[t[:, 0]], co[t[:, 2]] - co[t[:, 0]])[::3]
        nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
        lo, hi = co.min(0) - 0.01, co.max(0) + 0.01
        for name, (tb, cb, _) in trees.items():
            if name == o.name or np.any(cb.min(0) > hi) or np.any(cb.max(0) < lo):
                continue
            hits = 0
            for c, nn in zip(cen, nrm):
                loc, n2, idx, dist = tb.find_nearest(Vector(c), 0.0003)
                if loc is not None and abs(np.dot(np.array(n2), nn)) > 0.99:
                    hits += 1
            if hits > 3:
                overlaps["|".join(sorted((o.name, name)))] = hits
    res["coincident_faces"] = overlaps
    # cockpit camera clearance: nearest geometry to the eye (near clip plane 0.01 m)
    eye = Vector(it.EYE)
    best = (9.0, "")
    for name, (tb, _, _) in trees.items():
        loc, _, _, dist = tb.find_nearest(eye, 1.0)
        if loc is not None and dist < best[0]:
            best = (dist, name)
    res["eye_clearance_m"] = {"distance": round(best[0], 4), "nearest": best[1]}
    res["needles"] = needle_check()
    res["steering_wheel"] = wheel_check()
    path = os.path.join(PROJECT_ROOT, "docs", "gates", "p1b_interior_audit.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    short = {k: v for k, v in res.items() if k not in ("triangles_by_part", "contacts_by_design")}
    short["contacts_by_design"] = len(ok)
    return short
