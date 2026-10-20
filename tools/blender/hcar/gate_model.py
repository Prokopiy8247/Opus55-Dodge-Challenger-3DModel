"""G-Model measurements (Blender side): overall dimensions and view silhouettes of the visual car.

Writes docs/gates/p1_model_measure.json:
    dims (length, width at the flares, width with mirrors, height without the antenna, wheelbase, track)
    side  : z_top / z_bottom per 1 cm of y      (body only: wheels/tires excluded)
    plan  : max |x| per 1 cm of y (with and without mirrors / flares)
    front, rear: max |x| per 1 cm of z for the front half / rear half of the car
"""
import json
import os

import bpy
import numpy as np

from . import PROJECT_ROOT


def _verts(objs, step=0.01):
    """World points of the evaluated meshes: the vertices plus every crossing of a triangle edge
    with the 1 cm bin planes along x, y and z, so per-bin extremes are exact silhouettes (vertices
    alone leave bins of a coarse panel grid empty)."""
    out = []
    dg = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        if o.type != "MESH":
            continue
        co, tri = _world_tris(o, dg)
        out.append(co)
        if not len(tri):
            continue
        e = np.sort(np.vstack([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]]), axis=1)
        e = np.unique(e, axis=0)
        a, b = co[e[:, 0]], co[e[:, 1]]
        for ax in range(3):
            lo = np.minimum(a[:, ax], b[:, ax])
            hi = np.maximum(a[:, ax], b[:, ax])
            k0 = np.ceil(lo / step).astype(np.int64)
            k1 = np.floor(hi / step).astype(np.int64)
            n = np.maximum(k1 - k0 + 1, 0)
            if not n.sum():
                continue
            idx = np.repeat(np.arange(len(e)), n)
            k = np.repeat(k0, n) + (np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n))
            plane = k * step
            da = b[idx, ax] - a[idx, ax]
            t = np.where(np.abs(da) > 1e-12, (plane - a[idx, ax]) / np.where(np.abs(da) > 1e-12, da, 1.0), 0.0)
            p = a[idx] + t[:, None] * (b[idx] - a[idx])
            # nudge onto both sides of the bin plane
            for s in (-1e-6, 1e-6):
                q = p.copy()
                q[:, ax] += s
                out.append(q)
    return np.vstack(out) if out else np.zeros((0, 3))


BODY_PARTS = ("CH_Door", "CH_Fender", "CH_Quarter", "CH_Rocker", "CH_Bumper", "CH_Hood", "CH_DeckLid",
              "CH_Roof", "CH_Pillars", "CH_Flare")
REQUIRED = {  # brief 5.2 part list -> object name prefixes that satisfy it
    "body shell (roof, pillars)": ["CH_Roof", "CH_Pillars_L", "CH_Pillars_R"],
    "hood (scoop, extractors)": ["CH_Hood", "CH_Hood_Scoop", "CH_Hood_Extractor_L", "CH_Hood_Extractor_R"],
    "front fenders L/R": ["CH_Fender_L", "CH_Fender_R"], "doors L/R": ["CH_Door_L", "CH_Door_R"],
    "trunk lid": ["CH_DeckLid"], "rear quarter panels": ["CH_Quarter_L", "CH_Quarter_R"],
    "front bumper, lower intake, splitter": ["CH_Bumper_F", "CH_Grille_Lower", "CH_Splitter"],
    "rear bumper, diffuser": ["CH_Bumper_R", "CH_Valance"], "grille": ["CH_Grille_Upper"],
    "headlights L/R": ["CH_Headlamp_Housing_L", "CH_Headlamp_Housing_R"],
    "taillights": ["CH_TailPanel", "CH_TailLamp_Red"], "side mirrors L/R": ["CH_Mirror_Housing_L", "CH_Mirror_Housing_R"],
    "door handles": ["CH_Door_Handle_L", "CH_Door_Handle_R"], "windshield": ["CH_Glass_Windshield"],
    "side windows": ["CH_Glass_Door_L", "CH_Glass_Door_R", "CH_Glass_Quarter_L", "CH_Glass_Quarter_R"],
    "rear window": ["CH_Glass_Rear"], "rocker panels": ["CH_Rocker_L", "CH_Rocker_R"],
    "exhaust with 2 rectangular tips": ["CH_Exhaust_L", "CH_Exhaust_R", "CH_Exhaust_Tips_L", "CH_Exhaust_Tips_R"],
    "underbody / floor pan": ["CH_FloorPan"], "fuel tank": ["CH_FuelTank"],
    "engine with supercharger": ["CH_Engine"], "radiator and core support": ["CH_Radiator", "CH_CoreSupport"],
    "front / rear subframes": ["CH_Subframe_Front", "CH_Subframe_Rear"],
    "suspension arms and struts": ["CH_Susp_Front_Arms_L", "CH_Susp_Front_Damper_L", "CH_Susp_Rear_Links_L"],
    "brake discs / calipers": ["CH_Wheel_FL_Disc", "CH_Wheel_FL_Caliper"],
    "4 wheels (rim + tire)": ["CH_Wheel_FL_Rim", "CH_Wheel_FR_Tire", "CH_Wheel_RL_Rim", "CH_Wheel_RR_Tire"],
    "widebody flares": ["CH_Flare_front_L", "CH_Flare_rear_R"], "licence plate": ["CH_Plate_Rear"],
    "badges": ["CH_Badge_DODGE", "CH_Badge_SRT_Front", "CH_Badge_SRT_Rear"],
    "spoiler": ["CH_Spoiler"], "antenna": ["CH_Antenna"], "fuel door": ["CH_FuelDoor"],
    "cowl screen": ["CH_Cowl"], "wheel wells": ["CH_WheelLiners_L", "CH_WheelLiners_R"],
}


def _eval_mesh_stats(o, dg):
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    me.calc_loop_triangles()
    tris = len(me.loop_triangles)
    ne = len(me.edges)
    ef = np.zeros(ne, np.int32)
    # edge -> face counts via loops
    le = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("edge_index", le)
    np.add.at(ef, le, 1)
    nonman = int((ef != 2).sum())
    oe.to_mesh_clear()
    return tris, ne, nonman


def _world_tris(o, dg, with_poly=False):
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    me.calc_loop_triangles()
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    tri = np.empty(len(me.loop_triangles) * 3, np.int32)
    me.loop_triangles.foreach_get("vertices", tri)
    poly = np.empty(len(me.loop_triangles), np.int32)
    me.loop_triangles.foreach_get("polygon_index", poly)
    oe.to_mesh_clear()
    M = np.array(o.matrix_world)
    co = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    tri = tri.reshape(-1, 3)
    if np.linalg.det(M[:3, :3]) < 0:
        tri = tri[:, ::-1]           # a mirrored object renders its local front faces as front faces
    return (co, tri, poly) if with_poly else (co, tri)


def ray_hits(objs, dg=None, n_dirs=128, res=110):
    """Cast parallel rays from n_dirs directions around the car at the evaluated meshes. Returns per
    object {name: (front_hits, back_hits)} arrays over its evaluated polygons, and the ray count."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    dg = dg or bpy.context.evaluated_depsgraph_get()
    Vs, Ts, owner, polys, npoly = [], [], [], [], []
    base = 0
    for k, o in enumerate(objs):
        co, tri, poly = _world_tris(o, dg, with_poly=True)
        npoly.append(int(poly.max()) + 1 if len(poly) else 0)
        if not len(tri):
            continue
        Vs.append(co)
        Ts.append(tri + base)
        owner.append(np.full(len(tri), k, np.int32))
        polys.append(poly)
        base += len(co)
    V = np.vstack(Vs)
    T = np.vstack(Ts)
    owner = np.concatenate(owner)
    polys = np.concatenate(polys)
    tree = BVHTree.FromPolygons(V.tolist(), T.tolist(), all_triangles=True)
    lo, hi = V.min(0), V.max(0)
    c = (lo + hi) / 2
    R = float(np.linalg.norm(hi - lo) / 2)
    gold = np.pi * (3 - np.sqrt(5))
    g1, g2 = (a.ravel() for a in np.meshgrid(np.linspace(-1, 1, res), np.linspace(-1, 1, res)))
    tri_hit, tri_back = [], []
    rays = 0
    for i in range(n_dirs):
        zc = 1 - 2 * (i + 0.5) / n_dirs
        r = np.sqrt(1 - zc * zc)
        d = np.array([r * np.cos(gold * i), r * np.sin(gold * i), zc])
        u = np.cross(d, [0, 0, 1.0] if abs(zc) < 0.9 else [1.0, 0, 0])
        u /= np.linalg.norm(u)
        w = np.cross(d, u)
        dv = Vector(d)
        P = c + (g1[:, None] * u + g2[:, None] * w) * R - d * 2.5 * R
        for p in P.tolist():
            loc, nrm, idx, dist = tree.ray_cast(p, dv, 5 * R)
            if loc is not None:
                tri_hit.append(idx)
                tri_back.append(nrm.dot(dv) > 0)
        rays += len(P)
    th = np.array(tri_hit, np.int64)
    tb = np.array(tri_back, bool)
    out = {}
    for k, o in enumerate(objs):
        sel = owner[th] == k
        if not npoly[k]:
            continue
        p = polys[th[sel]]
        out[o.name] = (np.bincount(p[~tb[sel]], minlength=npoly[k]), np.bincount(p[tb[sel]], minlength=npoly[k]))
    return out, rays


def visibility(objs, dg=None, n_dirs=128, res=110):
    """Per object: how many first hits of rays from outside land on a back face (= a flipped or
    open surface seen from outside; Unity culls back faces)."""
    hits, rays = ray_hits(objs, dg, n_dirs, res)
    per = {}
    for name, (f, b) in hits.items():
        n = int(f.sum() + b.sum())
        if n:
            per[name] = {"hits": n, "back_frac": round(float(b.sum() / n), 4)}
    return {"rays": rays, "per_object": per}


def intersections(objs, dg=None, max_pairs=200):
    """Pairs of objects whose evaluated triangles cross each other (BVH overlap)."""
    from mathutils.bvhtree import BVHTree
    dg = dg or bpy.context.evaluated_depsgraph_get()
    trees = []
    for o in objs:
        co, tri = _world_tris(o, dg)
        if len(tri):
            trees.append((o.name, BVHTree.FromPolygons(co.tolist(), tri.tolist(), all_triangles=True),
                          co.min(0), co.max(0)))
    out = {}
    for i, (na, ta, la, ha) in enumerate(trees):
        for nb, tb, lb, hb in trees[i + 1:]:
            if np.any(la > hb + 0.01) or np.any(lb > ha + 0.01):
                continue
            n = len(ta.overlap(tb))
            if n:
                out[f"{na}|{nb}"] = n
                if len(out) >= max_pairs:
                    return out
    return out


# contacts that exist by design: small parts mounted in/on another part's skin, parts of one lamp or
# wheel assembly, and the joints of the simplified mechanics (arms end in the knuckle, a shaft in its
# hub, etc.). Patterns are fnmatch-style name pairs (order-free).
MOUNTED = [
    ("CH_Door_?", "CH_Door_Handle_?"), ("CH_Door_?", "CH_Mirror_Stalk_?"), ("CH_Mirror_Stalk_?", "CH_Mirror_Housing_?"),
    ("CH_Mirror_Housing_?", "CH_Mirror_Glass_?"), ("CH_Hood", "CH_Hood_Scoop"), ("CH_Hood", "CH_Hood_Extractor_?"),
    ("CH_Hood", "CH_Hood_Extractor_Vent_?"), ("CH_Hood_Scoop", "CH_Hood_Scoop_Mesh"),
    ("CH_Hood_Extractor_?", "CH_Hood_Extractor_Vent_?"), ("CH_Fender_?", "CH_Badge_Hellcat_?"),
    ("CH_Bumper_R", "CH_Marker_Rear_?"), ("CH_Flare_front_?", "CH_Marker_Front_?"), ("CH_Bumper_F", "CH_Marker_Front_?"),
    ("CH_Quarter_L", "CH_FuelDoor"), ("CH_Roof", "CH_Antenna"), ("CH_Grille_Upper", "CH_Badge_SRT_Front"),
    ("CH_Spoiler", "CH_Badge_SRT_Rear"), ("CH_TailPanel", "CH_Badge_DODGE"), ("CH_Plate_Rear", "CH_PlateRecess"),
    ("CH_Headlamp_*_?", "CH_Headlamp_*_?"), ("CH_TailLamp_*", "CH_TailLamp_*"), ("CH_Wheel_*", "CH_Wheel_*"),
    ("CH_Susp_*", "CH_Knuckles_?"), ("CH_Susp_Front_Arms_?", "CH_Subframe_Front"), ("CH_Susp_Rear_Links_?", "CH_Subframe_Rear"),
    ("CH_Susp_*_Damper_?", "CH_Susp_*_Spring_?"), ("CH_Knuckles_?", "CH_HalfShaft_?"), ("CH_Knuckles_?", "CH_Wheel_*"),
    ("CH_HalfShaft_?", "CH_Differential"), ("CH_Engine", "CH_Engine_Pulleys"), ("CH_Engine", "CH_Transmission"),
    ("CH_Transmission", "CH_DriveShaft"), ("CH_DriveShaft", "CH_Differential"), ("CH_Exhaust_?", "CH_Exhaust_Tips_?"),
    ("CH_Radiator", "CH_CoreSupport"), ("CH_Subframe_Front", "CH_CoreSupport"), ("CH_Susp_*", "CH_Susp_*"),
]


def all_contacts(objs, dg=None):
    """Every pair of objects whose evaluated triangles cross, split into by-design contacts
    (MOUNTED) and unexpected ones."""
    from fnmatch import fnmatch
    pairs = intersections(objs, dg, max_pairs=10000)
    ok, bad = {}, {}
    for key, n in pairs.items():
        a, b = key.split("|")
        mounted = any((fnmatch(a, p) and fnmatch(b, q)) or (fnmatch(a, q) and fnmatch(b, p)) for p, q in MOUNTED)
        (ok if mounted else bad)[key] = n
    return ok, bad


def audit(collection="Car_Visual"):
    """Names, materials, UVs, triangle budget, normal orientation, closed shells (non-manifold edges
    after the thickness modifier), coincident faces between parts, panel gaps, wheels."""
    from mathutils.bvhtree import BVHTree
    col = bpy.data.collections[collection]
    objs = list(col.all_objects)
    meshes = [o for o in objs if o.type == "MESH"]
    dg = bpy.context.evaluated_depsgraph_get()
    res = {"objects": len(objs), "meshes": len(meshes)}
    res["bad_names"] = [o.name for o in objs if not o.name.startswith("CH_") or "." in o.name]
    res["no_material"] = [o.name for o in meshes if not any(s.material for s in o.material_slots)]
    res["no_uv"] = [o.name for o in meshes if not o.data.uv_layers]
    names = {o.name for o in objs}
    res["missing_parts"] = {k: [n for n in v if n not in names] for k, v in REQUIRED.items()
                            if any(n not in names for n in v)}
    # left / right parts hold only their own side (x < 0 is the car's left); CH_Bumper_R is the rear bumper
    wrong = {}
    for o in meshes:
        if not o.name.endswith(("_L", "_R")) or o.name == "CH_Bumper_R" or not len(o.data.vertices):
            continue
        co = np.empty(len(o.data.vertices) * 3, np.float32)
        o.data.vertices.foreach_get("co", co)
        M = np.array(o.matrix_world)
        x = (co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3])[:, 0]
        n = int((x > 0.001).sum()) if o.name.endswith("_L") else int((x < -0.001).sum())
        if n:
            wrong[o.name] = n
    res["left_right_wrong_side_vertices"] = wrong
    tri_total, nonman = 0, {}
    for o in meshes:
        tris, ne, nm = _eval_mesh_stats(o, dg)
        tri_total += tris
        if any(o.name.startswith(p) for p in BODY_PARTS) and nm:
            nonman[o.name] = nm
    res["triangles"] = tri_total
    res["body_nonmanifold_edges"] = nonman
    # flipped normals: what a viewer outside the car sees must be front faces (Unity culls back faces)
    vis = visibility(meshes, dg)
    res["visible_backface_fraction_above_1pct"] = {k: v for k, v in vis["per_object"].items()
                                                   if v["hits"] >= 20 and v["back_frac"] > 0.01}
    res["visibility_rays"] = vis["rays"]
    # triangle intersections between the main panels (they meet at gaps and must not cross); small
    # parts mounted on a panel (handles, hood scoop and extractors) sit in its skin by design and
    # are only listed
    import re
    panel_re = re.compile(r"^CH_((Door|Fender|Quarter|Rocker|Pillars|Glass_Door|Glass_Quarter)_[LR]|Flare_(front|rear)_[LR]"
                          r"|Bumper_[FR]|Hood|DeckLid|Roof|Glass_Windshield|Glass_Rear|Cowl|TailPanel|Spoiler|Grille_Upper|Grille_Lower"
                          r"|Grille_Duct_[LR]|PlateRecess|Valance|Splitter)$")
    panels = [o for o in meshes if panel_re.match(o.name)]
    res["panel_intersections"] = intersections(panels, dg)
    # every other pair of parts: only the by-design contacts (MOUNTED) may touch
    ok, bad = all_contacts(meshes, dg)
    res["attached_detail_contacts"] = ok
    res["unexpected_contacts"] = {k: v for k, v in bad.items() if k not in res["panel_intersections"]}
    # coincident faces (z-fighting) between different body parts: face centres within 0.3 mm of
    # another part's surface with parallel normals
    trees = {}
    for o in meshes:
        if any(o.name.startswith(p) for p in BODY_PARTS + ("CH_Glass", "CH_Spoiler", "CH_TailPanel")):
            bm_v = [o.matrix_world @ v.co for v in o.data.vertices]
            bm_f = [list(p.vertices) for p in o.data.polygons]
            trees[o.name] = (BVHTree.FromPolygons(bm_v, bm_f), o)
    overlaps = {}
    keys = list(trees)
    for i, ka in enumerate(keys):
        ta, oa = trees[ka]
        Ma = oa.matrix_world
        cents = [(Ma @ p.center, (Ma.to_3x3() @ p.normal).normalized())
                 for i, p in enumerate(oa.data.polygons) if i % 4 == 0]
        for kb in keys[i + 1:]:
            tb, _ = trees[kb]
            hits = 0
            for cpos, cn in cents:
                loc, nrm, idx, dist = tb.find_nearest(cpos, 0.0003)
                if loc is not None and abs(nrm.dot(cn)) > 0.99:
                    hits += 1
            if hits > 3:
                overlaps[f"{ka}|{kb}"] = hits
    res["coincident_faces"] = overlaps
    # panel gaps: smallest vertex distance between neighbouring panels (expected 4-6 mm)
    def min_dist(a, b):
        oa, ob = bpy.data.objects.get(a), bpy.data.objects.get(b)
        if oa is None or ob is None:
            return None
        tb = BVHTree.FromPolygons([ob.matrix_world @ v.co for v in ob.data.vertices], [list(p.vertices) for p in ob.data.polygons])
        best = 1e9
        for v in oa.data.vertices:
            loc, _, _, d = tb.find_nearest(oa.matrix_world @ v.co, 0.05)
            if loc is not None and d < best:
                best = d
        return round(best * 1000, 2)
    res["gaps_mm"] = {f"{a}|{b}": min_dist(a, b) for a, b in (("CH_Door_R", "CH_Fender_R"), ("CH_Door_R", "CH_Quarter_R"),
                                                                ("CH_Hood", "CH_Fender_R"), ("CH_DeckLid", "CH_Quarter_R"),
                                                                ("CH_Bumper_F", "CH_Fender_R"), ("CH_Door_R", "CH_Rocker_R"))}
    # wheels
    from . import body_tables as bt
    wh = {}
    for key, w in bt.WHEELS.items():
        hub = bpy.data.objects.get(f"CH_Wheel_{key}")
        tire = bpy.data.objects.get(f"CH_Wheel_{key}_Tire")
        if hub is None or tire is None:
            wh[key] = None
            continue
        co = np.array([tire.matrix_world @ v.co for v in tire.data.vertices])
        c = np.array(hub.matrix_world.translation)
        r = np.linalg.norm(co[:, 1:] - c[1:], axis=1)
        # roundness: outer radius per 2.5 degree sector (the tread crown profile is not out-of-round)
        ang = np.degrees(np.arctan2(co[:, 2] - c[2], co[:, 1] - c[1]))
        sec = np.floor((ang + 180.0) / 2.5).astype(int)
        rmax = np.array([r[sec == k].max() for k in np.unique(sec)])
        wh[key] = {"centre": [round(float(v), 4) for v in c], "spec_centre": [w["x"], w["y"], w["z"]],
                   "centre_error_mm": round(float(np.linalg.norm(c - [w["x"], w["y"], w["z"]])) * 1000, 2),
                   "radius_max": round(float(r.max()), 4),
                   "out_of_round_mm": round(float(np.ptp(rmax)) * 1000, 2)}
    res["wheels"] = wh
    path = os.path.join(PROJECT_ROOT, "docs", "gates", "p1_model_audit.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    return {k: (v if not isinstance(v, (list, dict)) or len(str(v)) < 400 else f"{len(v)} entries") for k, v in res.items()}


def measure(collection="Car_Visual"):
    col = bpy.data.collections[collection]
    objs = [o for o in col.all_objects if o.visible_get() and o.type == "MESH"]
    names = [o.name for o in objs]
    is_wheel = lambda n: "Wheel" in n  # noqa: E731
    # mechanics under the car are hidden behind the rockers in a side view (the drawing's bottom
    # line is the rocker / bumper edge)
    mech = ("CH_FloorPan", "CH_FuelTank", "CH_Engine", "CH_Transmission", "CH_Radiator", "CH_CoreSupport",
            "CH_Subframe", "CH_DriveShaft", "CH_Differential", "CH_Knuckles", "CH_Susp", "CH_HalfShaft",
            "CH_Exhaust_L", "CH_Exhaust_R")
    objs = [o for o in objs if not o.name.startswith(mech)]
    names = [o.name for o in objs]
    body = [o for o in objs if not is_wheel(o.name) and "Antenna" not in o.name]
    no_mirror = [o for o in body if "Mirror" not in o.name]
    no_flare = [o for o in no_mirror if "Flare" not in o.name and "Liner" not in o.name and "Sill" not in o.name]
    wheels = [o for o in objs if is_wheel(o.name)]
    Vb, Vnm, Vnf, Vw = _verts(body), _verts(no_mirror), _verts(no_flare), _verts(wheels)
    Vall = _verts([o for o in objs if "Antenna" not in o.name])
    dims = {
        "length": float(Vall[:, 1].max() - Vall[:, 1].min()),
        "y_front": float(Vall[:, 1].max()), "y_rear": float(Vall[:, 1].min()),
        "width_no_mirrors": float(2 * np.abs(Vnm[:, 0]).max()),
        "width_with_mirrors": float(2 * np.abs(Vb[:, 0]).max()),
        "width_body_no_flares": float(2 * np.abs(Vnf[:, 0]).max()),
        "height": float(Vall[:, 2].max()),
        "ground_clearance_body": float(Vb[(np.abs(Vb[:, 1]) < 1.0)][:, 2].min()),
    }

    def binned(V, k_axis, v_axis, lo, hi, step=0.01, fn=np.max):
        edges = np.arange(lo, hi + step, step)
        idx = np.digitize(V[:, k_axis], edges) - 1
        out = []
        for i in range(len(edges) - 1):
            m = idx == i
            out.append(float(fn(V[m, v_axis])) if m.any() else None)
        return [round(float(e + step / 2), 4) for e in edges[:-1]], out

    y, ztop = binned(Vnm, 1, 2, -2.62, 2.48)
    _, zbot = binned(Vnm, 1, 2, -2.62, 2.48, fn=np.min)
    _, xmax = binned(np.c_[np.abs(Vnm[:, 0]), Vnm[:, 1:]], 1, 0, -2.62, 2.48)
    _, xmax_nf = binned(np.c_[np.abs(Vnf[:, 0]), Vnf[:, 1:]], 1, 0, -2.62, 2.48)
    Vf = Vnm[Vnm[:, 1] > 0]
    Vr = Vnm[Vnm[:, 1] < 0]
    z, front = binned(np.c_[np.abs(Vf[:, 0]), Vf[:, 1:]], 2, 0, 0.0, 1.50)
    _, rear = binned(np.c_[np.abs(Vr[:, 0]), Vr[:, 1:]], 2, 0, 0.0, 1.50)
    Vf2 = Vnf[Vnf[:, 1] > 0]
    Vr2 = Vnf[Vnf[:, 1] < 0]
    _, front_nf = binned(np.c_[np.abs(Vf2[:, 0]), Vf2[:, 1:]], 2, 0, 0.0, 1.50)
    _, rear_nf = binned(np.c_[np.abs(Vr2[:, 0]), Vr2[:, 1:]], 2, 0, 0.0, 1.50)
    res = {"objects": names, "dims": dims,
           "side": {"y": y, "z_top": ztop, "z_bottom": zbot},
           "plan": {"y": y, "half_width": xmax, "half_width_no_flares": xmax_nf},
           "front_view": {"z": z, "half_width": front, "half_width_no_flares": front_nf},
           "rear_view": {"z": z, "half_width": rear, "half_width_no_flares": rear_nf},
           "wheels": {"bbox_min": Vw.min(axis=0).tolist() if len(Vw) else None,
                      "bbox_max": Vw.max(axis=0).tolist() if len(Vw) else None}}
    path = os.path.join(PROJECT_ROOT, "docs", "gates", "p1_model_measure.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f)
    return {"json": path, "dims": {k: round(v, 4) for k, v in dims.items()}}
