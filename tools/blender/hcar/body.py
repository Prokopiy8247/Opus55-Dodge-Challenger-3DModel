"""Exterior body meshes in Blender, built from the parametric surfaces in shape.py.

Run through the bridge:  bcall.ps1 hcar.body:preview_strip @{}
"""
import math
import time

import numpy as np

from . import body_tables as bt
from .caps import BoundarySamples, HeightCap, coons, polyline_param, smoothstep, table_fn
from .meshkit import grid_faces, merge, mirror_x, to_blender, weld, weld_mirror_pairs
from .shape import KNOTS, LineGuide, Outline, Strip

_MODEL = {}


def model():
    """Cached surface model (rebuilt when the tables module changes)."""
    key = id(bt)
    m = _MODEL.get(key)
    if m is None:
        _MODEL.clear()
        O = Outline(bt.OUTLINE, R=bt.GUIDE_R)
        st = Strip(O, bt.FEATURE_CURVES, bt.STRIP_ANCHORS)
        Og = LineGuide(bt.GH_X0, *bt.GH_Y)
        gh = Strip(Og, bt.GH_CURVES, bt.GH_ANCHORS, keys=bt.GH_KEYS, knots=bt.GH_KNOTS,
                   h_range=(-1.0, 0.30), centres=bt.GH_CENTRES)
        m = {"O": O, "strip": st, "Og": Og, "gh": gh}
        m["hood"] = hood_cap(m)
        m["deck"] = deck_cap(m)
        _MODEL[key] = m
    return m


# ------------------------------------------------------------------------------------------------
# caps
# ------------------------------------------------------------------------------------------------
def _edge_samples(st, s0, s1, ds=0.004, t=1.0, dt_in=0.01):
    """Positions on the strip at parameter t for s in [s0, s1], with the height-field gradient of
    the strip's tangent plane just inside the edge."""
    s = np.linspace(s0, s1, max(int(abs(s1 - s0) / ds), 2) + 1)
    P = st.point(s, np.full_like(s, t))
    tn = t - dt_in if t >= 0.5 else t + dt_in
    N = normals_exact(st, s, np.full_like(s, tn))
    N = np.where(N[:, 2:3] < 0, -N, N)
    grad = np.stack([-N[:, 0] / np.maximum(N[:, 2], 0.2), -N[:, 1] / np.maximum(N[:, 2], 0.2)], axis=1)
    # a height field cannot continue a near-vertical surface: limit the slope handed to the cap
    mag = np.linalg.norm(grad, axis=1, keepdims=True)
    grad = grad * np.minimum(1.0, 1.2 / np.maximum(mag, 1e-9))
    return s, P, grad


def hood_cap(m):
    st, O = m["strip"], m["O"]
    s_rc = O.s_side_y(0.95)             # hood rear corner on the side shut line
    s, P, grad = _edge_samples(st, s_rc, O.S)
    phi = O.phi(s)
    front = P[:, 1] > 2.165
    # front edge y_f(x) for the roll (x decreasing along the front edge)
    fx, fy = P[front, 0][::-1], P[front, 1][::-1]
    zc = table_fn(bt.HOOD_CENTRE)
    bh = table_fn(bt.HOOD_BULGE["height"])
    bw = table_fn(bt.HOOD_BULGE["half_width"])
    blend = bt.HOOD_BULGE["blend"]

    def F(x, y):
        x = np.abs(x)
        z = zc(y) - 0.030 * x * x
        z = z + bh(y) * (1.0 - smoothstep(bw(y) - blend, bw(y), x))
        yf = np.interp(x, fx, fy)
        u = np.clip((yf - y) / 0.018, 0.0, 1.0)
        z = z - 0.024 * (1.0 - u) ** 2
        return z

    bs = BoundarySamples()
    side = ~front
    bs.add(P[side, :2], P[side, 2], grad[side], g=1.0, D=0.14)
    bs.add(P[front, :2], P[front, 2], None, g=0.0, D=0.03)
    rear = polyline_param(np.asarray(bt.HOOD_REAR, float), 120)
    bs.add(rear[:, :2], rear[:, 2], None, g=0.0, D=0.06)
    cap = HeightCap(F, bs)
    cap.outline = dict(side=P[side], front=P[front], rear=rear, s_side=s[side], phi=phi)
    return cap


def roof_cap(m):
    gh = m["gh"]
    Og = m["Og"]
    s, P, grad = _edge_samples(gh, 0.0, Og.S)
    zc = table_fn(bt.ROOF_CENTRE[::-1])

    def F(x, y):
        return zc(y) - 0.10 * x * x

    bs = BoundarySamples()
    bs.add(P[:, :2], P[:, 2], grad, g=1.0, D=0.16)
    cap = HeightCap(F, bs)
    cap.outline = dict(edge=P, s=s)
    return cap


def deck_cap(m):
    st, O, gh, Og = m["strip"], m["O"], m["gh"], m["Og"]
    s_fc = O.s_side_y(-1.70)
    s, P, grad = _edge_samples(st, 0.0, s_fc)
    rear = P[:, 1] < -2.395
    rx, ry = P[rear, 0], P[rear, 1]
    order = np.argsort(rx)
    rx, ry = rx[order], ry[order]
    # front edge: rear-window base (greenhouse t = 0) from the centre to its corner
    s_gc = Og.s_side_y(-1.62)
    sg, Pg, _ = _edge_samples(gh, 0.0, s_gc, t=0.0)
    zc = table_fn(sorted(bt.DECK_CENTRE))

    def F(x, y):
        x = np.abs(x)
        z = zc(y) - 0.020 * x * x
        ye = np.interp(x, rx, ry)
        L = 0.055
        u = np.clip((y - ye) / L, 0.0, 1.0)
        drop = zc(ye + L) - 0.020 * x * x - 1.018
        return z - np.maximum(drop, 0.0) * (1.0 - u) ** 2

    bs = BoundarySamples()
    bs.add(P[~rear, :2], P[~rear, 2], grad[~rear], g=1.0, D=0.12)
    bs.add(P[rear, :2], P[rear, 2], None, g=0.0, D=0.03)
    bs.add(Pg[:, :2], Pg[:, 2], None, g=0.0, D=0.06)
    cap = HeightCap(F, bs)
    cap.outline = dict(side=P, front=Pg)
    return cap


def cap_grid(cap, c_bottom, c_top, c_left, c_right):
    """Mesh grid (nu x nv x 3) of a cap over a plan Coons patch of four (x, y) boundary arrays."""
    G = coons(c_bottom, c_top, c_left, c_right)
    z = cap.z(G[..., 0], G[..., 1])
    return np.concatenate([G, z[..., None]], axis=-1)


def _resample_xy(p, n):
    return polyline_param(np.asarray(p, float)[:, :2], n)


def cap_meshes(m, step=0.02):
    """Preview grids of hood, roof and deck (right half)."""
    out = {}
    # hood: bottom = rear edge (centre -> rear corner), right = side shut line (rear corner -> front
    # corner), top = front edge (centre -> front corner), left = centreline
    hood = m["hood"]
    o = hood.outline
    rear = o["rear"][:, :2]
    side = o["side"][:, :2]
    front = o["front"][:, :2][::-1]      # centre -> front corner
    nu = max(int(0.8 / step), 8)
    nv = max(int(1.3 / step), 8)
    cb = _resample_xy(rear, nu)
    ct = _resample_xy(front, nu)
    cr = _resample_xy(side, nv)
    cl = np.stack([np.zeros(nv), np.linspace(cb[0, 1], ct[0, 1], nv)], axis=1)
    out["hood"] = cap_grid(hood, cb, ct, cl, cr)
    # deck: bottom = rear edge (centre -> rear corner), right = side shut line, top = rear-window base
    deck = m["deck"]
    P = deck.outline["side"][:, :2]      # s increasing: rear centre -> rear corner -> side -> front
    i_c = int(np.argmin(np.abs(P[:, 1] - (-2.36)) + (P[:, 0] < 0.6)))
    nu = max(int(0.75 / step), 8)
    nv = max(int(0.7 / step), 8)
    cb = _resample_xy(P[:i_c + 1], nu)
    cr = _resample_xy(P[i_c:], nv)
    ct = _resample_xy(deck.outline["front"][:, :2], nu)
    cl = np.stack([np.zeros(nv), np.linspace(cb[0, 1], ct[0, 1], nv)], axis=1)
    out["deck"] = cap_grid(deck, cb, ct, cl, cr)
    return out


def t_rows(per_seg=(30, 6, 5, 6, 4), crease_gap=0.0025):
    """Row parameters: uniform per segment plus rows at +-crease_gap around the crease knots."""
    rows = []
    for k in range(len(KNOTS) - 1):
        a, b = KNOTS[k], KNOTS[k + 1]
        rows.extend(np.linspace(a, b, per_seg[k] + 1)[:-1])
    rows.append(1.0)
    for k in (2, 4):
        rows.extend([KNOTS[k] - crease_gap, KNOTS[k] + crease_gap])
    return np.unique(np.round(rows, 6))


def surface_normals(st, s, t, du=0.02):
    """Per-loop normals for a structured grid (s: (ns,), t: (nt,)): each face corner uses the
    normal at its parameters nudged by du of the cell towards the face centre (sharp creases on
    knot rows, smooth elsewhere). Returns (n_faces * 4, 3) in grid_faces corner order."""
    ns, nt = len(s), len(t)
    i, j = np.meshgrid(np.arange(ns - 1), np.arange(nt - 1), indexing="ij")
    i, j = i.ravel(), j.ravel()
    corners = [(0, 0), (1, 0), (1, 1), (0, 1)]  # matches grid_faces: a, a+nv, a+nv+1, a+1
    out = np.empty((len(i), 4, 3))
    for c, (di, dj) in enumerate(corners):
        si = s[i + di] + (1 - 2 * di) * du * (s[i + 1] - s[i])
        tj = t[j + dj] + (1 - 2 * dj) * du * (t[j + 1] - t[j])
        out[:, c] = normals_exact(st, si, tj)
    return out.reshape(-1, 3)


def normals_exact(st, s, t, es=4e-4, et=2e-4):
    S = st.O.S
    s0 = np.clip(s - es, 0, S)
    s1 = np.clip(s + es, 0, S)
    t0 = np.clip(t - et, 0, 1)
    t1 = np.clip(t + et, 0, 1)
    ds = st.point(s1, t) - st.point(s0, t)
    dt = st.point(s, t1) - st.point(s, t0)
    n = np.cross(ds, dt)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    bad = ln[:, 0] < 1e-12  # degenerate parameter point (pole of a loft)
    n = n / np.where(ln < 1e-12, 1.0, ln)
    n[bad] = (0.0, 0.0, 1.0)
    return n


def preview_strip(ds=0.015, name="DBG_Strip"):
    """Whole strip (both halves) as one smooth quad mesh with analytic normals, white paint."""
    import bpy
    from .blend_util import collection, material
    t0 = time.time()
    m = model()
    st = m["strip"]
    S = m["O"].S
    s = np.linspace(0.0, S, int(np.ceil(S / ds)) + 1)
    t = t_rows()
    ss, tt = np.meshgrid(s, t, indexing="ij")
    P = st.point(ss, tt).reshape(-1, 3)
    F = grid_faces(len(s), len(t))
    N = surface_normals(st, s, t)
    # left half: mirror with reversed corner order (normals follow the corners)
    PL, FL = mirror_x(P, F)
    NL = N.reshape(-1, 4, 3)[:, ::-1].copy()
    NL[..., 0] *= -1
    V, Fa = merge([(P, F), (PL, FL)])
    Na = np.vstack([N, NL.reshape(-1, 3)])
    col = collection("Car_Visual_WIP")
    obj = to_blender(name, V, Fa, col=col, normals=Na)
    obj.data.materials.append(paint_white())
    return {"verts": len(V), "faces": len(Fa), "seconds": round(time.time() - t0, 2)}


def grid_normals_numeric(G):
    """Vertex normals of a structured grid by central differences (one-sided at the borders)."""
    du = np.gradient(G, axis=0)
    dv = np.gradient(G, axis=1)
    n = np.cross(du, dv)
    return n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-12)


def preview_all(ds=0.015, step=0.02):
    """Strip + greenhouse strip + caps, both halves, as separate preview objects."""
    import bpy
    from .blend_util import collection
    t0 = time.time()
    m = model()
    col = collection("Car_Visual_WIP")
    res = {}
    # body strip
    res["strip"] = preview_strip(ds=ds)
    # greenhouse strip
    gh = m["gh"]
    S = m["Og"].S
    s = np.linspace(0.0, S, int(np.ceil(S / ds)) + 1)
    kn = bt.GH_KNOTS
    t = np.unique(np.r_[np.linspace(0, kn[1], 18), np.linspace(kn[1], kn[2], 7), np.linspace(kn[2], 1.0, 26),
                        kn[1] - 0.003, kn[1] + 0.003, kn[2] - 0.003, kn[2] + 0.003])
    ss, tt = np.meshgrid(s, t, indexing="ij")
    P = gh.point(ss, tt).reshape(-1, 3)
    F = grid_faces(len(s), len(t))
    N = surface_normals(gh, s, t)
    obj = _mirrored_object("DBG_Greenhouse", P, F, N, col)
    obj.data.materials.append(glass_dark())
    res["gh"] = len(P)
    # caps
    grids = cap_meshes(m, step)
    for name, G in grids.items():
        nu, nv = G.shape[:2]
        P = G.reshape(-1, 3)
        F = grid_faces(nu, nv)
        if name in ("hood", "deck"):
            F = F[:, ::-1]  # Coons (u = x, v = y): make the faces point up
        nrm = grid_normals_numeric(G).reshape(-1, 3)
        Nl = nrm[F.ravel()]
        if np.mean(Nl[:, 2]) < 0:
            Nl = -Nl
        obj = _mirrored_object(f"DBG_{name}", P, F, Nl, col)
        mat = paint_black_matte() if name in ("hood", "roof") else paint_white()
        obj.data.materials.append(mat)
        res[name] = len(P)
    res["seconds"] = round(time.time() - t0, 2)
    return res


def preview_flares_wheels():
    """Flares (both sides) and the four wheel assemblies; cuts the wheel openings out of the
    strip preview object."""
    import bpy
    from . import wheels as wh
    from .blend_util import collection, material
    from .flares import flare_panel
    from .panels import panel_to_arrays
    t0 = time.time()
    m = model()
    col = collection("Car_Visual_WIP")
    res = {}
    for key in ("front", "rear"):
        pm = flare_panel(m["strip"], key).mesh()
        V, F, N = panel_to_arrays(pm)
        obj = _mirrored_object(f"DBG_Flare_{key}", V, F, N, col)
        obj.data.materials.append(paint_white())
        res[key] = len(V)
    # cut the openings out of the strip preview: drop faces inside the lip radius on the sides
    strip = bpy.data.objects.get("DBG_Strip")
    if strip is not None:
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(strip.data)
        dead = []
        for f in bm.faces:
            c = f.calc_center_median()
            for fl in bt.FLARES.values():
                if abs(c.x) > 0.55 and math.hypot(c.y - fl["y"], c.z - fl["z"]) < fl["lip_r"] + 0.05:
                    dead.append(f)
                    break
        bmesh.ops.delete(bm, geom=dead, context="FACES")
        bm.to_mesh(strip.data)
        bm.free()
    mats = {
        "tire": material("CH_Tire_Rubber", (0.022, 0.022, 0.024), roughness=0.82),
        "rim": material("CH_Wheel_Graphite", (0.055, 0.056, 0.06), metallic=0.85, roughness=0.38),
        "disc": material("CH_Brake_Disc", (0.35, 0.35, 0.36), metallic=0.9, roughness=0.42),
        "caliper": material("CH_Brake_Caliper_Red", (0.62, 0.06, 0.03), roughness=0.3),
    }
    tV, tF = wh.build_tire()
    for name, w in bt.WHEELS.items():
        sx = 1.0 if w["x"] > 0 else -1.0
        hub = bpy.data.objects.get(f"DBG_Wheel_{name}") or bpy.data.objects.new(f"DBG_Wheel_{name}", None)
        if hub.name not in col.objects:
            col.objects.link(hub)
        hub.location = (w["x"], w["y"], w["z"])
        hub.scale = (sx, 1.0, 1.0)
        parts = []
        V = tV.copy()
        o = to_blender(f"DBG_Wheel_{name}_Tire", V, tF, col=col)
        o.data.materials.append(mats["tire"])
        parts.append(o)
        rim = wh.build_rim_blender(f"DBG_Wheel_{name}_Rim", col, mats)
        parts.append(rim)
        dV, dF = wh.build_disc(r=0.195 if w["front"] else 0.175)
        o = to_blender(f"DBG_Wheel_{name}_Disc", dV, dF, col=col)
        o.data.materials.append(mats["disc"])
        parts.append(o)
        cV, cF = wh.build_caliper(r_disc=0.195 if w["front"] else 0.175, front=w["front"])
        o = to_blender(f"DBG_Wheel_{name}_Caliper", cV, cF, col=col)
        o.data.materials.append(mats["caliper"])
        parts.append(o)
        for p in parts:
            p.parent = hub
            if sx < 0:
                # mirrored parent flips the winding: fix the normals in the mesh instead
                p.data.flip_normals()
        res[name] = len(parts)
    res["seconds"] = round(time.time() - t0, 2)
    return res


def preview_panels():
    """Side panels (door, fender, quarter, rocker) with gaps, both sides; removes the covered part
    of the strip preview."""
    import bpy
    from .blend_util import collection
    from .body_panels import side_panels
    from .panels import panel_to_arrays
    t0 = time.time()
    m = model()
    col = collection("Car_Visual_WIP")
    res = {}
    from .body_panels import bumper_panels
    from .gh_panels import cap_panels, glass_patch, greenhouse_panels
    panels = dict(side_panels(m))
    panels.update(bumper_panels(m))
    panels.update(greenhouse_panels(m))
    panels.update(cap_panels(m))
    from .blend_util import material
    for name, p in panels.items():
        pm = p.mesh()
        V, F, N, K, D = panel_to_arrays(pm, kinds=True)
        # the walls of deep openings (grille cavity, lower intake, ducts) are black plastic
        mi = ((K == 3) & (D >= 0.04)).astype(int)
        obj = _mirrored_object(f"DBG_{name}", V, F, N, col, mat_idx=mi if mi.any() else None)
        if "Glass" in name:
            mat = glass_dark()
        elif name in ("CH_Roof", "CH_Hood"):
            mat = paint_black_matte()
        else:
            mat = paint_white()
        obj.data.materials.append(mat)
        if mi.any():
            obj.data.materials.append(material("CH_Plastic_BlackTrim", (0.02, 0.02, 0.021), roughness=0.55))
        res[name] = len(V)
    for which in ("front", "rear"):
        G = glass_patch(m, which)
        nu, nv = G.shape[:2]
        P = G.reshape(-1, 3)
        F = grid_faces(nu, nv)
        nrm = grid_normals_numeric(G).reshape(-1, 3)
        Nl = nrm[F.ravel()]
        if np.mean(Nl[:, 2]) < 0:
            F = F[:, ::-1]
            Nl = -nrm[F.ravel()]
        obj = _mirrored_object(f"DBG_CH_Glass_{'Windshield' if which == 'front' else 'Rear'}", P, F, Nl, col)
        obj.data.materials.append(glass_dark())
    # the old greenhouse and cap previews are replaced by panels
    for nm in ("DBG_Greenhouse", "DBG_hood", "DBG_deck"):
        o = bpy.data.objects.get(nm)
        if o is not None:
            o.hide_set(True)
    strip = bpy.data.objects.get("DBG_Strip")
    if strip is not None:
        # every part of the strip is now a panel: hide the preview strip
        strip.hide_set(True)
    res["seconds"] = round(time.time() - t0, 2)
    return res


def preview_details():
    """Headlamps, grilles, splitter, tail lamps, spoiler, valance + exhausts, plate, mirrors,
    handles, fuel door, antenna, sills, liners, markers."""
    from .body_panels import bumper_panels
    from .details import build_all
    t0 = time.time()
    m = model()
    names = build_all(m, bumper_panels(m))
    return {"objects": names, "seconds": round(time.time() - t0, 2)}


def _mirrored_object(name, P, F, N, col, mat_idx=None):
    # loops of vertices on the mirror plane: the normal must lie in the plane (no seam at x = 0)
    N = N.copy()
    on_plane = np.abs(P[F.ravel(), 0]) < 1e-5
    N[on_plane, 0] = 0.0
    N[on_plane] /= np.maximum(np.linalg.norm(N[on_plane], axis=1, keepdims=True), 1e-12)
    PL, FL = mirror_x(P, F)
    NL = N.reshape(-1, F.shape[1], 3)[:, ::-1].copy()
    NL[..., 0] *= -1
    V, Fa = merge([(P, F), (PL, FL)])
    Na = np.vstack([N, NL.reshape(-1, 3)])
    # join each vertex on x = 0 with its own mirror copy (not all coincident vertices: that would
    # collapse the loft poles), so the halves form one shell and the thickness has no rim at x = 0
    V, Fa = weld_mirror_pairs(V, Fa, len(P))
    mi = None if mat_idx is None else np.concatenate([mat_idx, mat_idx])
    return to_blender(name, V, Fa, col=col, normals=Na, mat_idx=mi)


def glass_dark():
    """Tinted see-through glass (alpha blended, transparent shadows; Unity: URP transparent)."""
    from .blend_util import material
    mat = material("CH_Glass_Tint", (0.02, 0.025, 0.03), roughness=0.04, alpha=0.30)
    for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND"), ("use_transparent_shadow", True),
                      ("use_backface_culling", False)):
        try:
            setattr(mat, attr, val)
        except (AttributeError, TypeError):
            pass
    mat["hc_alpha"] = 0.30
    return mat


def paint_black_matte():
    from .blend_util import material
    return material("CH_Paint_MatteBlack", (0.028, 0.028, 0.03), roughness=0.72)


def paint_white():
    import bpy
    from .blend_util import material
    mat = material("CH_Paint_White", (0.88, 0.89, 0.90), roughness=0.18)
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    for key in ("Coat Weight", "Clearcoat"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = 1.0
            break
    if "Coat Roughness" in bsdf.inputs:
        bsdf.inputs["Coat Roughness"].default_value = 0.03
    return mat
