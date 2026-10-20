"""Exterior details (Blender side): headlamps, grille and intake meshes, splitter, tail-lamp panel
with lamps and DODGE letters, spoiler, valance with two rectangular exhaust tips, licence plate,
mirrors, door handles, fuel door, antenna, side sills, wheel-well liners.

All positions are in the car frame (x right, y forward, z up); right-side parts are mirrored.
Dimensions from the dimensions.com drawing (front/rear/side/plan views) and the user's photos.
"""
import math

import numpy as np

from . import body_tables as bt
from .meshkit import frame, merge, mirror_x, prism, rounded_rect, to_blender, to_blender_ngons, weld_mirror_pairs
from .panels import StripSurface, _points_in_polygon
from .sidemap import face_param
from .wheels import revolve

# ------------------------------------------------------------------------------------------------
# materials
# ------------------------------------------------------------------------------------------------


def mats():
    import bpy
    from .blend_util import material
    m = {
        "chrome": material("CH_Chrome", (0.9, 0.9, 0.92), metallic=1.0, roughness=0.06),
        "black_gloss": material("CH_Plastic_BlackGloss", (0.012, 0.012, 0.013), roughness=0.12),
        "black_trim": material("CH_Plastic_BlackTrim", (0.02, 0.02, 0.021), roughness=0.55),
        "grille": material("CH_Grille_Mesh", (0.015, 0.015, 0.016), metallic=0.3, roughness=0.45),
        "halo": material("CH_Lamp_Halo", (1.0, 1.0, 1.0), emission=(0.85, 0.92, 1.0)),
        "lens": material("CH_Lamp_Lens", (0.85, 0.88, 0.9), roughness=0.02, alpha=0.35),
        "tail_red": material("CH_Lamp_TailRed", (0.8, 0.02, 0.02), emission=(1.0, 0.02, 0.01)),
        "tail_smoke": material("CH_Lamp_Smoke", (0.04, 0.02, 0.02), roughness=0.05),
        "reverse": material("CH_Lamp_Reverse", (0.75, 0.75, 0.78), metallic=0.6, roughness=0.15),
        "mirror": material("CH_Mirror_Glass", (0.8, 0.82, 0.85), metallic=1.0, roughness=0.02),
        "plate": material("CH_Plate", (0.92, 0.92, 0.9), roughness=0.4),
        "fuel": material("CH_FuelDoor", (0.08, 0.08, 0.085), metallic=0.7, roughness=0.3),
        "liner": material("CH_WheelLiner", (0.015, 0.015, 0.015), roughness=0.9),
        "marker_amber": material("CH_Marker_Amber", (0.9, 0.35, 0.02), emission=(0.6, 0.2, 0.0)),
        "marker_red": material("CH_Marker_Red", (0.6, 0.02, 0.02), emission=(0.5, 0.0, 0.0)),
    }
    # emission strength
    for key, s in (("halo", 2.5), ("tail_red", 4.0), ("marker_amber", 1.5), ("marker_red", 1.5)):
        bsdf = next(n for n in m[key].node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        bsdf.inputs["Emission Strength"].default_value = s
    m["lens"].blend_method = "BLEND" if hasattr(m["lens"], "blend_method") else None
    _grille_texture(m["grille"])
    return m


def _grille_texture(mat):
    """Procedural brick-mesh look for the grille material (dark cells, slightly lighter webs)."""
    nt = mat.node_tree
    for n in [n for n in nt.nodes if n.type in ("TEX_BRICK", "TEX_COORD", "SEPXYZ", "COMBXYZ")]:
        nt.nodes.remove(n)
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.inputs["Scale"].default_value = 30.0
    br.inputs["Mortar Size"].default_value = 0.035
    br.inputs["Color1"].default_value = (0.004, 0.004, 0.004, 1)
    br.inputs["Color2"].default_value = (0.006, 0.006, 0.006, 1)
    br.inputs["Mortar"].default_value = (0.05, 0.05, 0.055, 1)
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["X"], comb.inputs["X"])        # grille faces the front: pattern in x-z
    nt.links.new(sep.outputs["Z"], comb.inputs["Y"])
    nt.links.new(comb.outputs["Vector"], br.inputs["Vector"])
    nt.links.new(br.outputs["Color"], bsdf.inputs["Base Color"])


def _obj(name, V, F, col, mat, mirror=True, smooth=True, ngons=False):
    """Create the right-side part and (optionally) its mirrored left copy in one object."""
    if ngons:
        if mirror:
            VL = V * np.array([-1.0, 1.0, 1.0])
            n = len(V)
            F = list(F) + [[n + i for i in f[::-1]] for f in F]
            V = np.vstack([V, VL])
            # parts spanning the centreline: one shell across x = 0 (no seam, no thickness rim)
            on = np.abs(V[:n, 0]) < 1e-6
            if on.any():
                remap = np.arange(len(V))
                remap[n + np.nonzero(on)[0]] = np.nonzero(on)[0]
                F = [[int(remap[i]) for i in f] for f in F]
        o = to_blender_ngons(name, V, F, col=col, smooth=smooth, auto_smooth_deg=40 if smooth else None)
    else:
        F = np.asarray(F)
        if mirror:
            n = len(V)
            VL, FL = mirror_x(V, F)
            V, F = merge([(V, F), (VL, FL)])
            V, F = weld_mirror_pairs(V, F, n)
        o = to_blender(name, V, F, col=col, smooth=smooth)
    o.data.materials.append(mat)
    return o


# ------------------------------------------------------------------------------------------------
# helpers on the body strip
# ------------------------------------------------------------------------------------------------
def strip_point_normal(m, x, z, face):
    st = m["strip"]
    s, t = face_param(st, x, z, face, t_lo=0.0, t_hi=1.0)
    surf = StripSurface(st)
    P = surf.P(np.array([s]), np.array([t]))[0]
    N = surf.N(np.array([s]), np.array([t]))[0]
    return P, N


def _offset_polygon(pts, d):
    """Closed 2D polygon offset outwards by d (mitred vertex normals)."""
    p = np.asarray(pts, float)
    area2 = np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1])
    e_in = p - np.roll(p, 1, axis=0)
    e_out = np.roll(p, -1, axis=0) - p
    def nrm(e):
        n = np.stack([e[:, 1], -e[:, 0]], axis=1)          # right-hand normal: outwards for CCW
        return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    n = nrm(e_in) + nrm(e_out)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    cosh = np.clip((n * nrm(e_out)).sum(1), 0.5, 1.0)
    return p + np.sign(area2) * n * (d / cosh)[:, None]


def opening_fill(m, panel, hole_key, depth=None, face="front", enlarge=0.0):
    """Back plate of one opening of a bumper panel (grille, tail-lamp bezel, plate recess): the
    panel's plug for that opening (Panel.plugs), i.e. the cut-out grid cells moved to the end of
    the opening's return flange, whose rim vertices sit exactly on the flange's end loop, so the
    recess is closed. depth and enlarge are kept for the old call signature (the depth comes from
    body_tables.OPENING_DEPTH through the panel's flange)."""
    holes = bt.FASCIA_HOLES if face == "front" else bt.REAR_HOLES
    k = list(holes).index(hole_key)
    plug = panel.mesh()["plugs"][k]
    return plug["V"], plug["F"]


# ------------------------------------------------------------------------------------------------
HEADLAMP_R = 0.069


def headlamp_frames(m):
    """(origin, right, forward) of the two right-side headlamps: the lamp front plane sits 35 mm
    behind the fascia surface at the lamp centre."""
    out = []
    for cx in (0.5796, 0.7495):
        cz = 0.695          # middle of the grille opening: the lamps fill its height (photo 2)
        P, N = strip_point_normal(m, cx, cz, "front")
        fwd = N / np.linalg.norm(N)
        fwd[2] = 0.0
        fwd /= np.linalg.norm(fwd)
        out.append((P - fwd * 0.035, np.cross([0, 0, 1.0], fwd), fwd))
    return out


def headlamps(m, col, M):
    """Four round projector headlamps with halo rings (two per side)."""
    out = []
    parts_housing, parts_chrome, parts_halo, parts_lens = [], [], [], []
    for origin, right, fwd in headlamp_frames(m):
        tf = frame(origin, right, [0, 0, 1.0])      # local x right, y up, z = forward (out)

        def place(V):
            # revolve() builds around the X axis: map (axial, r cos, r sin) -> local (r cos, r sin, axial)
            return tf(np.stack([V[:, 1], V[:, 2], V[:, 0]], axis=1))
        R = HEADLAMP_R
        housing = [(0.004, R + 0.006), (0.0, R + 0.002), (-0.010, R), (-0.055, R - 0.006), (-0.075, 0.0)]
        V, F = revolve(housing, 64)
        parts_housing.append((place(V), F))
        bowl = [(-0.006, R - 0.004), (-0.030, 0.050), (-0.046, 0.034), (-0.050, 0.0)]
        V, F = revolve(bowl, 64)
        parts_chrome.append((place(V), F[:, ::-1]))
        halo = [(-0.010, 0.0590), (-0.008, 0.0605), (-0.010, 0.0620), (-0.012, 0.0605)]   # thin LED ring
        V, F = revolve(halo, 64, closed_profile=True)
        parts_halo.append((place(V), F))
        lens = [(-0.004, 0.0), (-0.008, 0.016), (-0.016, 0.027), (-0.030, 0.029), (-0.034, 0.0)]
        V, F = revolve(lens, 48)
        parts_lens.append((place(V), F))
        cover = [(0.003, 0.0), (0.0035, R * 0.6), (0.0015, R + 0.0005)]   # inside the housing rim
        V, F = revolve(cover, 64)
        parts_lens.append((place(V), F))
    for name, parts, mat in (("CH_Headlamp_Housing", parts_housing, M["black_gloss"]),
                             ("CH_Headlamp_Reflector", parts_chrome, M["chrome"]),
                             ("CH_Headlamp_Halo", parts_halo, M["halo"]),
                             ("CH_Headlamp_Lens", parts_lens, M["lens"])):
        V, F = merge(parts)
        out.append(_obj(name, V, F, col, mat))
    return out


def _lamp_holes(m, V, F, r_hole=0.0785):
    """Round holes in the upper grille where the headlamp housings pass through it (the housing's
    largest radius is 75 mm, at its front rim, which hides the 3.5 mm clearance ring): faces inside
    are removed and the new rim vertices are moved onto the circle."""
    V = V.copy()
    keep = np.ones(len(F), bool)
    frames = headlamp_frames(m)
    rim_all = []
    for origin, right, fwd in frames:
        up = np.array([0, 0, 1.0])
        rel = V - origin
        u, v = rel @ right, rel @ up
        rr = np.hypot(u, v)
        fc_r = rr[F].mean(axis=1)
        keep &= fc_r > r_hole
        rim_all.append((rr, u, v, origin, right, up))
    F2 = F[keep]
    e = np.sort(np.stack([F2, np.roll(F2, -1, axis=1)], axis=-1).reshape(-1, 2), axis=1)
    uniq, cnt = np.unique(e, axis=0, return_counts=True)
    bv = np.unique(uniq[cnt == 1].ravel())
    for rr, u, v, origin, right, up in rim_all:
        sel = bv[rr[bv] < r_hole + 0.025]
        if not len(sel):
            continue
        k = r_hole / np.maximum(rr[sel], 1e-9)
        depth = (V[sel] - origin) - np.outer(u[sel], right) - np.outer(v[sel], up)
        V[sel] = origin + depth + np.outer(u[sel] * k, right) + np.outer(v[sel] * k, up)
    used = np.unique(F2)
    remap = -np.ones(len(V), int)
    remap[used] = np.arange(len(used))
    return V[used], remap[F2]


def grilles(m, col, M, bumper):
    out = []
    for key, name in (("cavity", "CH_Grille_Upper"), ("intake", "CH_Grille_Lower"), ("duct", "CH_Grille_Duct")):
        V, F = opening_fill(m, bumper["CH_Fascia"], key, bt.OPENING_DEPTH[key], "front", enlarge=0.014)
        if key == "cavity":
            V, F = _lamp_holes(m, V, F)
        out.append(_obj(name, V, F, col, M["grille"]))       # plug faces point outwards
    return out


def splitter(col, M):
    outer = np.array([(0.0, 2.386), (0.30, 2.377), (0.55, 2.358), (0.72, 2.322), (0.82, 2.262),
                      (0.870, 2.160), (0.887, 2.000), (0.890, 1.935)])
    inner = np.array([(0.0, 2.190), (0.30, 2.186), (0.60, 2.176), (0.76, 2.140), (0.825, 2.060),
                      (0.840, 1.935)])
    from .geom import resample
    n = 60
    o = resample(outer, n)
    i = resample(inner, n)
    z0, z1, zl = 0.193, 0.209, 0.236
    rows = [np.c_[i, np.full(n, z1)], np.c_[o, np.full(n, z1)], np.c_[o + 0.0, np.full(n, zl)],
            np.c_[o, np.full(n, zl + 0.0)] * 0 + np.c_[o - (o - i) * 0.04, np.full(n, zl)],
            np.c_[o - (o - i) * 0.04, np.full(n, z1 + 0.004)]]
    # closed section loop: top inner -> top outer -> lip up -> lip back -> bottom
    loop = [np.c_[i, np.full(n, z1)], np.c_[o - (o - i) * 0.05, np.full(n, z1)],
            np.c_[o - (o - i) * 0.05, np.full(n, zl)], np.c_[o, np.full(n, zl)], np.c_[o, np.full(n, z0)],
            np.c_[i, np.full(n, z0)]]
    _ = rows
    V = np.vstack(loop)
    k = len(loop)
    F = []
    for r in range(k):
        r1 = (r + 1) % k
        for c in range(n - 1):
            F.append([r * n + c, r * n + c + 1, r1 * n + c + 1, r1 * n + c])
    F = np.array(F)
    return [_obj("CH_Splitter", V, F, col, M["black_trim"], smooth=False)]


def face_points(m, xz, face, off):
    """Points on the front/rear face of the body strip at view coordinates (x, z), moved `off`
    along the outward surface normal (negative = behind the skin). Returns (P, N)."""
    st = m["strip"]
    surf = StripSurface(st)
    xz = np.asarray(xz, float)
    cache = {}
    st_par = np.empty((len(xz), 2))
    for k, (x, z) in enumerate(xz):
        key = (round(float(x), 6), round(float(z), 6))
        if key not in cache:
            cache[key] = face_param(st, abs(float(x)), float(z), face, t_lo=0.0, t_hi=1.0)
        st_par[k] = cache[key]
    P = surf.P(st_par[:, 0], st_par[:, 1])
    N = surf.N(st_par[:, 0], st_par[:, 1])
    sgn = np.where(xz[:, 0] < 0, -1.0, 1.0)
    P[:, 0] *= sgn
    N[:, 0] *= sgn
    return P + np.asarray(off, float).reshape(-1, 1) * N, N


def _resample_closed(poly, n):
    """n points evenly spaced by arc length along a closed polygon, starting at its first point."""
    poly = np.asarray(poly, float)
    P = np.vstack([poly, poly[:1]])
    s = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    q = np.linspace(0, s[-1], n, endpoint=False)
    return np.stack([np.interp(q, s, P[:, 0]), np.interp(q, s, P[:, 1])], axis=1)


def _densify(poly, step=0.008):
    """Closed polygon with extra points so no segment is longer than `step` (outlines laid onto a
    curved surface would otherwise sag as long chords)."""
    poly = np.asarray(poly, float)
    out = []
    for a, b in zip(poly, np.roll(poly, -1, axis=0)):
        k = max(int(np.ceil(np.linalg.norm(b - a) / step)), 1)
        out.append(a + (b - a) * np.linspace(0, 1, k, endpoint=False)[:, None])
    return np.vstack(out)


def _curved_prism(poly, depth, rings=6):
    """Prism like meshkit.prism, but its two caps are concentric rings (scaled copies of the outline
    towards its centre) instead of one n-gon, so they can follow a curved surface when laid onto it.
    Local z: 0 on the top cap, -depth on the bottom cap. Returns (V (n, 3), quad/tri face list)."""
    poly = np.asarray(poly, float)
    area2 = np.sum(poly[:, 0] * np.roll(poly[:, 1], -1) - np.roll(poly[:, 0], -1) * poly[:, 1])
    if area2 < 0:
        poly = poly[::-1]
    n = len(poly)
    c = poly.mean(axis=0)
    scales = np.linspace(1.0, 0.0, rings + 1)[:-1]
    V, F = [], []
    for z, flip in ((0.0, False), (-depth, True)):
        base = len(V)
        for sc in scales:
            V += [(*(c + (q - c) * sc), z) for q in poly]
        V.append((*c, z))
        centre = len(V) - 1
        for k in range(rings - 1):
            for j in range(n):
                a, b = base + k * n + j, base + k * n + (j + 1) % n
                f = [a, b, b + n, a + n]
                F.append(f[::-1] if flip else f)
        last = base + (rings - 1) * n
        for j in range(n):
            f = [last + j, last + (j + 1) % n, centre]
            F.append(f[::-1] if flip else f)
    top0, bot0 = 0, n * rings + 1
    for j in range(n):                       # side walls between the outer loops
        j1 = (j + 1) % n
        F.append([top0 + j1, top0 + j, bot0 + j, bot0 + j1])
    return np.array(V, float), F


def tail_lamps(m, col, M, bumper):
    """Black bezel recessed 22 mm behind the bumper skin (following its curvature, reaching under
    the opening's return flange), two lamp units per side and the DODGE letters on it (photo 5)."""
    out = []
    depth = bt.OPENING_DEPTH["lamps"]
    V, F = opening_fill(m, bumper["CH_RearBumper"], "lamps", depth, "rear", enlarge=0.014)
    out.append(_obj("CH_TailPanel", V, F, col, M["black_gloss"]))
    # lamp units: rounded rectangles laid onto the bezel surface (local w = outwards)
    red, smoke, bar = [], [], []

    def lay(cx, cz, uvw, base):
        uvw = np.asarray(uvw, float)
        P, _ = face_points(m, np.c_[cx + uvw[:, 0], cz + uvw[:, 1]], "rear", base + uvw[:, 2])
        return P
    ring = -depth + 0.011            # light-guide ring 11 mm proud of the bezel
    for x0, x1 in ((0.205, 0.500), (0.515, 0.812)):
        w, h = x1 - x0, 0.137
        cx, cz = (x0 + x1) / 2, 0.8815
        outer = _densify(rounded_rect(w, h, 0.045, n_corner=10))
        inner = _densify(rounded_rect(w - 0.024, h - 0.024, 0.035, n_corner=10))
        # same point count on both loops for the ring band: resample the inner loop by arc length
        inner = _resample_closed(inner, len(outer))
        n = len(outer)
        Vr = np.vstack([lay(cx, cz, np.c_[outer, np.zeros(n)], ring), lay(cx, cz, np.c_[inner, np.zeros(n)], ring)])
        Fr = [[k, (k + 1) % n, n + (k + 1) % n, n + k] for k in range(n)]
        red.append((Vr, np.array(Fr)))
        Vs, Fs = _curved_prism(inner, 0.006)
        smoke.append((lay(cx, cz, Vs, ring - 0.004), Fs))
        Vb, Fb = _curved_prism(_densify(rounded_rect(w - 0.07, 0.022, 0.011)), 0.004, rings=3)
        bar.append((lay(cx, cz, Vb, ring + 0.002), Fb))          # its underside 2 mm above the lens
    V, F = merge(red)
    out.append(_obj("CH_TailLamp_Red", V, F, col, M["tail_red"], smooth=False))
    for name, parts, mat in (("CH_TailLamp_Lens", smoke, M["tail_smoke"]), ("CH_TailLamp_Bar", bar, M["reverse"])):
        Vs, Fs = [], []
        off = 0
        for v, f in parts:
            Vs.append(v)
            Fs += [[i + off for i in ff] for ff in f]
            off += len(v)
        out.append(_obj(name, np.vstack(Vs), Fs, col, mat, ngons=True, smooth=False))
    P, N = face_points(m, [(0.0, 0.882)], "rear", -depth + 0.002)
    out.append(dodge_letters(col, M, P[0], N[0]))
    return out


def dodge_letters(col, M, loc, normal):
    """Chrome DODGE letters on the centre of the tail-lamp panel (Blender text -> mesh)."""
    import bpy
    from .blend_util import remove_object
    remove_object("CH_Badge_DODGE")
    cu = bpy.data.curves.new("CH_Badge_DODGE", "FONT")
    cu.body = "D O D G E"
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.size = 0.032
    cu.extrude = 0.0015
    cu.space_character = 1.05
    ob = bpy.data.objects.new("CH_Badge_DODGE_tmp", cu)
    col.objects.link(ob)
    # text plane tangent to the bezel; rotation about x maps local z (text normal) onto the
    # bezel normal (0, -sin a, cos a); reads left-to-right seen from behind
    ob.rotation_euler = (math.atan2(-float(normal[1]), float(normal[2])), 0, 0)
    ob.location = tuple(float(c) for c in loc)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    mesh_ob = bpy.data.objects.new("CH_Badge_DODGE", me)
    mesh_ob.matrix_world = ob.matrix_world
    col.objects.link(mesh_ob)
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.curves.remove(cu)
    me.materials.append(M["chrome"])
    return mesh_ob


def spoiler(m, col, M):
    """Flat black blade spoiler on the deck-lid rear edge (side#27 profile, plan#18 width)."""
    deck = m["deck"]
    xs = np.linspace(0.0, 0.80, 65)
    z_low = 1.034                              # lower edge of the rear face (white deck strip below)
    rows = []
    for x in xs:
        xd = min(x, 0.70)
        zf = float(deck.z(np.array([xd]), np.array([-2.292]))[0])
        z_lip = 1.118 - 0.012 * (x / 0.8) ** 2
        # top surface: front foot -> rear lip (rising)
        ty = np.linspace(-2.292, -2.452, 9)
        tz = zf + 0.003 + (z_lip - zf - 0.003) * ((-2.292 - ty) / 0.160) ** 1.3
        # rear lip rounding and rear face
        ry = np.array([-2.458, -2.461, -2.459])
        rz = np.array([z_lip - 0.003, z_lip - 0.012, z_low + 0.006])
        # underside: from the rear-face bottom forward, hugging the deck lid
        uy = np.linspace(-2.452, -2.300, 12)
        uz = np.maximum(deck.z(np.full(12, xd), np.maximum(uy, -2.428)) + 0.005, z_low)
        prof = np.r_[np.c_[ty, tz], np.c_[ry, rz], np.c_[uy, uz]]
        # taper the height above the deck towards the rounded ends
        f = 1.0 - max(0.0, (x - 0.70) / 0.10) ** 2 * 0.75
        base = np.maximum(deck.z(np.full(len(prof), xd), np.maximum(prof[:, 0], -2.428)), z_low - 0.004)
        prof[:, 1] = base + (prof[:, 1] - base) * f
        rows.append(np.c_[np.full(len(prof), x), prof])
    rows = np.array(rows)
    prof_y = rows[0, :, 1]
    nx, npf = rows.shape[:2]
    V = rows.reshape(-1, 3)
    F = []
    for i in range(nx - 1):
        for j in range(npf):
            j1 = (j + 1) % npf
            F.append([i * npf + j, i * npf + j1, (i + 1) * npf + j1, (i + 1) * npf + j])
    end = [[(nx - 1) * npf + j for j in range(npf)][::-1]]
    F = [f for f in F] + end
    return [_obj("CH_Spoiler", V, F, col, M["black_gloss"], ngons=True, smooth=True)]


def valance_and_exhaust(m, col, M):
    """Black rear valance under the bumper cover with a cut-out for each of the two rectangular
    exhaust tips (photo 5); the tips are sleeves standing 8 mm proud of the valance, 4 mm clear of
    the cut-out edge."""
    from .geom import resample
    from .panels import _closest_on_polygon
    from .shape import FeatureCurve
    fc0 = FeatureCurve(bt.FEATURE_CURVES[0]).p
    top = fc0[fc0[:, 1] < -2.05]           # starts behind the rear flare's lower end (y -2.03)
    top = top[np.argsort(top[:, 0])]
    n = 70
    top = resample(top, n)
    bot = top.copy()
    centre_w = np.clip(1.0 - top[:, 0] / 0.9, 0, 1)
    bot[:, 1] = top[:, 1] + 0.06 * centre_w                       # tucks forward under the car
    bot[:, 0] = top[:, 0] - 0.03 * (1 - centre_w)
    bot[:, 2] = 0.205 + 0.11 * np.clip((top[:, 0] - 0.70) / 0.19, 0, 1) ** 1.5   # low enough for the tips
    mid = (top + bot) / 2
    mid[:, 1] -= 0.012 * centre_w                                 # slight bulge rearwards
    t0 = top + [0, 0.004, 0.004]
    ctrl = 2 * mid - (t0 + bot) / 2                               # quadratic through the mid row
    nr = 12
    rows = [(1 - u) ** 2 * t0 + 2 * u * (1 - u) * ctrl + u * u * bot for u in np.linspace(0, 1, nr)]
    V = np.vstack(rows)
    F = np.array([[r * n + c, (r + 1) * n + c, (r + 1) * n + c + 1, r * n + c + 1]
                  for r in range(nr - 1) for c in range(n - 1)])
    # tip geometry and the cut-out (rounded rectangle in the x-z view, 4 mm larger than the tip)
    cx, cz = 0.5385, 0.241
    w, h, L = 0.172, 0.056, 0.06
    hole = rounded_rect(w + 0.008, h + 0.008, 0.016) + [cx, cz]
    fc = V[F][:, :, [0, 2]].mean(axis=1)
    keep = ~_points_in_polygon(fc, hole)
    F = F[keep]
    e = np.sort(np.stack([F, np.roll(F, -1, axis=1)], axis=-1).reshape(-1, 2), axis=1)
    uniq, cnt = np.unique(e, axis=0, return_counts=True)
    bv = np.unique(uniq[cnt == 1].ravel())
    xz = V[bv][:, [0, 2]]
    near = np.linalg.norm(xz - [cx, cz], axis=1) < 0.13
    sel = bv[near]
    q = _closest_on_polygon(V[sel][:, [0, 2]], hole)
    V[sel, 0], V[sel, 2] = q[:, 0], q[:, 1]
    out = [_obj("CH_Valance", V, F, col, M["black_trim"])]
    # exhaust tip: rectangular sleeve open towards the rear, inner liner with a closed bottom
    outer = rounded_rect(w, h, 0.012)
    inner = rounded_rect(w - 0.010, h - 0.010, 0.007)
    y0 = float(np.interp(cx, top[:, 0], top[:, 1])) + 0.012
    tf = frame((cx, y0, cz), [1.0, 0, 0], [0, 0, 1.0])
    k = len(outer)
    ring_o0 = tf(np.c_[outer, np.zeros(k)])
    ring_o1 = tf(np.c_[outer, np.full(k, -L)])
    ring_i0 = tf(np.c_[inner, np.zeros(k)])
    ring_i1 = tf(np.c_[inner, np.full(k, -L * 0.6)])
    Vt = np.vstack([ring_o1, ring_o0, ring_i0, ring_i1])
    Ft = []
    for a_ in range(3):
        for c in range(k):
            c1 = (c + 1) % k
            Ft.append([a_ * k + c, a_ * k + c1, (a_ + 1) * k + c1, (a_ + 1) * k + c])
    Ft.append([3 * k + c for c in range(k)])
    Ft.append([c for c in range(k)][::-1])                       # close the sleeve's front end
    out.append(_obj("CH_Exhaust_Tips", Vt, Ft, col, M["black_gloss"], ngons=True, smooth=True))
    return out


def plate(m, col, M, bumper):
    out = []
    V, F = opening_fill(m, bumper["CH_RearBumper"], "plate", bt.OPENING_DEPTH["plate"], "rear", enlarge=0.014)
    from .body import paint_white
    o = _obj("CH_PlateRecess", V, F, col, paint_white())
    out.append(o)
    # parallel to the (inclined) recess: frame from the surface normal at the plate centre
    P0, N0 = face_points(m, [(0.0, 0.5636)], "rear", -0.008)
    N0 = N0[0] / np.linalg.norm(N0[0])
    up = np.cross(N0, [1.0, 0.0, 0.0])
    tf = frame(P0[0], [1.0, 0, 0], up / np.linalg.norm(up))
    Vp, Fp = prism(rounded_rect(0.512, 0.110, 0.006), 0.002)     # clears the recess walls
    out.append(_obj("CH_Plate_Rear", tf(Vp), Fp, col, M["plate"], mirror=False, ngons=True, smooth=False))
    return out


def mirrors(m, col, M):
    """Side mirrors: white housings (half superellipsoids) on black stalks, glass facing rearwards."""
    from .body import paint_white
    cx, cy, cz = 0.979, 0.375, 1.052    # outer edge at x = 1.084: 2,169 mm across the mirrors (spec)
    a, b, c = 0.105, 0.055, 0.062        # half sizes: x (out), y (fwd), z
    nu, nv = 40, 18
    U = np.linspace(-math.pi, math.pi, nu, endpoint=False)
    Vv = np.linspace(0, math.pi / 2, nv)
    p = 0.6
    pts = []
    for v in Vv:
        for u in U:
            cu, su = math.cos(u), math.sin(u)
            cv, sv = math.cos(v), math.sin(v)
            sp = lambda w: math.copysign(abs(w) ** p, w)   # noqa: E731
            x = a * sp(cu) * sp(cv) ** 1.0
            z = c * sp(su) * sp(cv) ** 1.0
            y = b * sv ** 0.8
            pts.append((cx + x, cy + y, cz + z))
    V = np.array(pts)
    F = []
    for j in range(nv - 1):
        for i in range(nu):
            i1 = (i + 1) % nu
            F.append([j * nu + i, j * nu + i1, (j + 1) * nu + i1, (j + 1) * nu + i])
    F = np.array(F)[:, ::-1]
    out = [_obj("CH_Mirror_Housing", V, F, col, paint_white())]
    # glass: inset ellipse at the open rear side
    gl = np.array([(cx + 0.92 * a * math.copysign(abs(math.cos(u)) ** p, math.cos(u)),
                    cy - 0.004, cz + 0.92 * c * math.copysign(abs(math.sin(u)) ** p, math.sin(u))) for u in U])
    Vg = np.vstack([gl, [[cx, cy - 0.004, cz]]])
    Fg = [[i, nu, (i + 1) % nu] for i in range(nu)]
    out.append(_obj("CH_Mirror_Glass", Vg, Fg, col, M["mirror"], ngons=True, smooth=False))
    # stalk: tapered box from the door top to the housing
    p0 = np.array([0.885, 0.43, 0.985])
    p1 = np.array([cx - 0.04, cy + 0.02, cz - 0.02])
    d = p1 - p0
    L = np.linalg.norm(d)
    tf = frame(p0, d / L, [0, 0, 1.0])
    rect0 = rounded_rect(0.030, 0.020, 0.006)
    rect1 = rounded_rect(0.024, 0.016, 0.005)
    k = len(rect0)
    Vs = np.vstack([tf(np.c_[np.zeros(k), rect0[:, 0], rect0[:, 1]] @ np.diag([1, 1, 1])),
                    tf(np.c_[np.full(k, L), rect1[:, 0], rect1[:, 1]])])
    # frame(): local x along the stalk; the rectangles lie in local (y, z)
    Fs = [[c, (c + 1) % k, k + (c + 1) % k, k + c] for c in range(k)]
    out.append(_obj("CH_Mirror_Stalk", Vs, Fs, col, M["black_trim"], ngons=True))
    return out


def door_handles(m, col, M):
    from .body import paint_white
    from .sidemap import side_param
    st = m["strip"]
    surf = StripSurface(st)
    s, t = side_param(st, -0.462, 0.915, t_lo=0.0, t_hi=1.0)
    P = surf.P(np.array([s]), np.array([t]))[0]
    N = surf.N(np.array([s]), np.array([t]))[0]
    tf = frame(P + N * 0.006, [0, 1.0, 0], [0, 0, 1.0])
    Vh, Fh = prism(rounded_rect(0.160, 0.032, 0.014), 0.008, bevel=0.003)
    Vh = Vh[:, [0, 1, 2]]
    # local frame: x = +y (forward), y = up, z = x x y = outward normal-ish
    return [_obj("CH_Door_Handle", tf(Vh), Fh, col, paint_white(), ngons=True)]


def fuel_door(m, col, M):
    from .sidemap import side_param
    st = m["strip"]
    surf = StripSurface(st)
    s, t = side_param(st, -1.12, 0.985, t_lo=0.0, t_hi=1.0)
    P = surf.P(np.array([s]), np.array([t]))[0]
    N = surf.N(np.array([s]), np.array([t]))[0]
    # left side: mirror the right-side point
    P = P * np.array([-1.0, 1.0, 1.0])
    N = N * np.array([-1.0, 1.0, 1.0])
    ex = np.cross([0, 0, 1.0], N)
    ex /= np.linalg.norm(ex)
    tf = frame(P + N * 0.003, ex, [0, 0, 1.0])
    ang = np.linspace(0, 2 * math.pi, 48, endpoint=False)
    circ = np.c_[0.085 * np.cos(ang), 0.085 * np.sin(ang)]
    Vf, Ff = prism(circ, 0.005, bevel=0.004)
    return [_obj("CH_FuelDoor", tf(Vf), Ff, col, M["fuel"], mirror=False, ngons=True)]


def antenna(col, M):
    V1, F1 = revolve([(0.0, 0.0), (0.0, 0.012), (0.018, 0.009), (0.022, 0.0)], 16)
    V1 = V1[:, [1, 2, 0]] + [0, -1.0, 1.441]
    V2, F2 = revolve([(0.0, 0.0025), (0.16, 0.0018)], 8)
    V2 = V2[:, [1, 2, 0]]
    # tilt the whip backwards by 30 degrees
    a = math.radians(-30)
    R = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    V2 = V2 @ R.T + [0, -1.0, 1.461]
    V, F = merge([(V1, F1), (V2, F2)])
    return [_obj("CH_Antenna", V, F, col, M["black_trim"], mirror=False)]


def side_sills(m, col, M):
    """Black widebody side sill extensions under the rockers, between the flares."""
    ys = np.linspace(-0.98, 0.99, 50)
    st, O = m["strip"], m["O"]
    # profile relative to the rocker's lower edge (strip t = 0): hangs 5 mm below it, sticks out
    rel = np.array([(-0.012, -0.005), (0.033, -0.008), (0.050, -0.018), (0.046, -0.027), (-0.022, -0.030)])
    rows = []
    for y in ys:
        s = O.s_side_y(float(y))
        e = st.point(np.array([s]), np.array([0.0]))[0]
        taper = min(1.0, (y + 0.98) / 0.08, (0.99 - y) / 0.08)
        p = rel.copy()
        p[:, 0] = np.where(p[:, 0] > 0, p[:, 0] * max(taper, 0.2), p[:, 0])
        rows.append(np.c_[e[0] + p[:, 0], np.full(len(p), y), e[2] + p[:, 1]])
    rows = np.array(rows)
    n, k = rows.shape[:2]
    V = rows.reshape(-1, 3)
    F = np.array([[i * k + j, (i + 1) * k + j, (i + 1) * k + j + 1, i * k + j + 1]
                  for i in range(n - 1) for j in range(k - 1)])
    return [_obj("CH_SideSill", V, F, col, M["black_trim"])]


def wheel_liners(col, M):
    out = []
    for key, f in bt.FLARES.items():
        r = f["lip_r"] - 0.005
        # the outer end steps up inboard of the flare's lip flange (which reaches x 0.91 near the arch ends), closing the
        # gap between liner and flare
        xs_ = 0.890 if key == "front" else 0.860       # the rear flare's flange reaches further in
        prof = [(xs_, r + 0.015), (xs_, r), (0.62, r), (0.60, r - 0.02)]
        V, F = revolve(prof, 64)
        # revolve around the X axis -> the arch: keep the upper half only (z > -0.05)
        V[:, 1] += f["y"]
        V[:, 2] += f["z"]
        keep = V[F].mean(axis=1)[:, 2] > f["z"] - 0.06
        out.append((V, F[keep][:, ::-1]))
        # inner wall of the wheel well (closes the view into the engine bay / boot through the arch);
        # annulus r 0.30 .. lip, clear of the arms, springs and dampers (which pass inside r 0.25)
        a0 = -math.asin(min(0.06 / (r - 0.02), 1.0))
        th = np.linspace(a0, math.pi - a0, 49)
        rr = np.linspace(0.30, r - 0.02, 4)
        W = np.stack([np.full((len(th), len(rr)), 0.60),
                      f["y"] + np.cos(th)[:, None] * rr[None, :],
                      f["z"] + np.sin(th)[:, None] * rr[None, :]], axis=-1).reshape(-1, 3)
        nr = len(rr)
        Fw = np.array([[i * nr + j, (i + 1) * nr + j, (i + 1) * nr + j + 1, i * nr + j + 1]
                       for i in range(len(th) - 1) for j in range(nr - 1)])
        # slot for the coil-over (it runs almost parallel to the wall: the strut tower opening)
        from .mechanics import coilover_axes
        b, t, rc = coilover_axes()[key]
        ax_ = (t - b) / np.linalg.norm(t - b)
        fcw = W[Fw].mean(axis=1) - b
        dist = np.linalg.norm(fcw - np.outer(np.clip(fcw @ ax_, 0, np.linalg.norm(t - b)), ax_), axis=1)
        out.append((W, Fw[dist > rc + 0.035]))
    V, F = merge(out)
    return [_obj("CH_WheelLiners", V, F, col, M["liner"])]


def cowl(m, col, M):
    """Black cowl screen between the windshield base and the hood's rear edge: tucked 10 mm under
    the glass and 25 mm under the hood, with a shallow trough (closes the top view into the engine
    bay)."""
    from .shape import FeatureCurve
    B = FeatureCurve(bt.GH_CURVES["B"]).p
    base = B[B[:, 1] >= 0.846 - 1e-6]
    base = base[np.argsort(base[:, 0])]                       # centre -> corner
    hr = np.asarray(bt.HOOD_REAR, float)                      # centre -> corner
    xs = np.linspace(0.0, min(base[-1, 0], hr[-1, 0]) - 0.004, 40)
    yb, zb = np.interp(xs, base[:, 0], base[:, 1]), np.interp(xs, base[:, 0], base[:, 2])
    yh, zh = np.interp(xs, hr[:, 0], hr[:, 1]), np.interp(xs, hr[:, 0], hr[:, 2])
    # the windshield dips up to 16 mm at its lower outer corners (gh_panels.glass_patch): follow it
    sb = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(base[:, :2], axis=0), axis=1))]
    u = np.interp(xs, base[:, 0], sb / sb[-1])
    w = np.clip((u - 0.8) / 0.2, 0.0, 1.0)
    z_rear = zb - 0.014 - 0.016 * w * w * (3 - 2 * w) - 0.003 * w
    v = np.linspace(0.0, 1.0, 9)[None, :]
    y = (yb - 0.010)[:, None] + v * ((yh + 0.025) - (yb - 0.010))[:, None]
    z = z_rear[:, None] + v * ((zh - 0.030) - z_rear)[:, None] - 0.012 * np.sin(np.pi * v)
    V = np.stack([np.repeat(xs[:, None], v.shape[1], axis=1), y, z], axis=-1).reshape(-1, 3)
    nv = v.shape[1]
    F = np.array([[i * nv + j, (i + 1) * nv + j, (i + 1) * nv + j + 1, i * nv + j + 1]
                  for i in range(len(xs) - 1) for j in range(nv - 1)])
    return [_obj("CH_Cowl", V, F, col, M["black_trim"])]


def markers(m, col, M):
    """Side markers: amber slot on the front flares, red on the rear bumper sides."""
    out = []
    from .sidemap import side_param
    st = m["strip"]
    surf = StripSurface(st)
    for (y, z, w, h, mat, nm) in ((1.985, 0.462, 0.11, 0.022, M["black_gloss"], "CH_Marker_Front"),
                                  (-2.13, 0.552, 0.15, 0.03, M["marker_red"], "CH_Marker_Rear")):
        s, t = side_param(st, y, z, t_lo=0.0, t_hi=1.0)
        P = surf.P(np.array([s]), np.array([t]))[0]
        N = surf.N(np.array([s]), np.array([t]))[0]
        if nm == "CH_Marker_Front":
            P = P + N * 0.034   # on the flare
        tf = frame(P + N * 0.002, [0, 1.0, 0], [0, 0, 1.0])
        V, F = prism(rounded_rect(w, h, h / 2.2), 0.003)
        out.append(_obj(nm, tf(V), F, col, mat, ngons=True, smooth=False))
    return out


def hood_scoop_and_extractors(m, col, M):
    """Centre scoop at the rear of the hood (opening facing forward) and two heat extractors
    (wedges opening rearwards), as in reference photos 1, 2 and 4."""
    from .body import paint_black_matte
    hood = m["hood"]
    out = []
    # ---- scoop: sections along y from the opening (front) to the hood rear edge
    y_open, y_rear = 1.30, 1.16
    ys = np.linspace(y_open, y_rear, 12)
    nx = 25
    rows = []
    for k, y in enumerate(ys):
        f = (y_open - y) / (y_open - y_rear)
        h = 0.055 * (1.0 - 0.25 * f)                     # opening lip highest, settling rearwards
        half_top, half_base = 0.235, 0.295
        u = np.linspace(-1, 1, nx)
        xb = u * half_base
        zb = hood.z(np.abs(xb), np.full(nx, y))
        xt = np.sign(u) * np.minimum(np.abs(u) * half_base, half_top + (np.abs(u) * half_base - half_top) * 1.0)
        # height profile across: flat top, rounded shoulders down to the base
        s = np.clip((half_base - np.abs(xb)) / (half_base - half_top + 1e-9), 0, 1)
        lift = h * (s * s * (3 - 2 * s))
        rows.append(np.c_[xb, np.full(nx, y), zb + lift])
    rows = np.array(rows)
    V = rows.reshape(-1, 3)
    # rows run rearwards (-y), columns along +x: this order faces up
    F = [[i * nx + j, (i + 1) * nx + j, (i + 1) * nx + j + 1, i * nx + j + 1]
         for i in range(len(ys) - 1) for j in range(nx - 1)]
    # front face around the opening: from the front section down to a recessed opening outline
    front = rows[0]
    zb0 = hood.z(np.abs(front[:, 0]), np.full(nx, y_open))
    opening = front.copy()
    opening[:, 1] += -0.004
    inner = np.c_[front[:, 0] * 0.93, np.full(nx, y_open - 0.010), zb0 + (front[:, 2] - zb0) * 0.80 + 0.004]
    base = len(V)
    V = np.vstack([V, inner])
    F += [[j, j + 1, base + j + 1, base + j] for j in range(nx - 1)]   # lip faces forward
    out.append(_obj("CH_Hood_Scoop", V, np.array(F), col, paint_black_matte(), mirror=False))
    # mesh insert inside the opening
    mesh_pts = np.vstack([inner, np.c_[inner[::-1, 0], np.full(nx, y_open - 0.012), zb0[::-1] + 0.006]])
    Fm = [list(range(len(mesh_pts)))]
    out.append(_obj("CH_Hood_Scoop_Mesh", mesh_pts, Fm, col, M["grille"], mirror=False, ngons=True, smooth=False))
    # ---- heat extractors: wedges at x = +-0.42, rising rearwards, open rear face
    nx2 = 11
    ys2 = np.linspace(1.43, 1.21, 10)
    rows = []
    for y in ys2:
        f = (1.43 - y) / 0.22
        h = 0.032 * f ** 0.8
        u = np.linspace(-1, 1, nx2)
        xb = 0.42 + u * 0.085
        zb = hood.z(xb, np.full(nx2, y))
        s = np.clip((1 - np.abs(u)) / 0.25, 0, 1)
        rows.append(np.c_[xb, np.full(nx2, y), zb + h * (s * s * (3 - 2 * s))])
    rows = np.array(rows)
    V = rows.reshape(-1, 3)
    F = [[i * nx2 + j, (i + 1) * nx2 + j, (i + 1) * nx2 + j + 1, i * nx2 + j + 1]
         for i in range(len(ys2) - 1) for j in range(nx2 - 1)]
    out.append(_obj("CH_Hood_Extractor", V, np.array(F), col, paint_black_matte()))
    last = rows[-1]
    zb = hood.z(last[:, 0], np.full(nx2, last[0, 1]))
    louv = np.vstack([last + [0, 0.002, -0.002], np.c_[last[::-1, 0], np.full(nx2, last[0, 1] + 0.002), zb[::-1]]])
    out.append(_obj("CH_Hood_Extractor_Vent", louv, [list(range(len(louv)))[::-1]], col, M["grille"],
                    ngons=True, smooth=False))                       # faces rearwards
    return out


def text_badge(name, text, size, loc, rot_deg, mat, col, extrude=0.0012):
    import bpy
    from .blend_util import remove_object
    remove_object(name)
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = text
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.size = size
    cu.extrude = extrude
    try:
        cu.body_format[0].use_italic = True
    except Exception:
        pass
    ob = bpy.data.objects.new(name + "_tmp", cu)
    col.objects.link(ob)
    ob.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    ob.location = loc
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    mo = bpy.data.objects.new(name, me)
    mo.matrix_world = ob.matrix_world
    col.objects.link(mo)
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.curves.remove(cu)
    me.materials.append(mat)
    return mo


def badges(m, col, M):
    out = []
    # front: SRT on the grille, left of centre seen from the car (viewer's right in photo 2)
    P, N = strip_point_normal(m, 0.44, 0.70, "front")
    out.append(text_badge("CH_Badge_SRT_Front", "SRT", 0.045, (-0.44, P[1] - 0.062, 0.70), (90, 0, 180),
                          M["chrome"], col))
    # rear: SRT on the spoiler's right end, seen from behind
    out.append(text_badge("CH_Badge_SRT_Rear", "SRT", 0.04, (0.60, -2.455, 1.100), (90, 0, 0), M["chrome"], col))
    # red Hellcat emblems on the front fenders, behind the wheels
    from .sidemap import side_param
    st = m["strip"]
    surf = StripSurface(st)
    s, t = side_param(st, 0.98, 0.79, t_lo=0.0, t_hi=1.0)
    P = surf.P(np.array([s]), np.array([t]))[0]
    N = surf.N(np.array([s]), np.array([t]))[0]
    tf = frame(P + N * 0.0015, [0, 1.0, 0], [0, 0, 1.0])
    # stylised cat head: rounded body with two ears
    ang = np.linspace(0, 2 * math.pi, 40, endpoint=False)
    head = np.c_[0.026 * np.cos(ang), 0.022 * np.sin(ang)]
    ears = np.array([(0.012, 0.018), (0.024, 0.036), (0.022, 0.012), (-0.022, 0.012), (-0.024, 0.036), (-0.012, 0.018)])
    poly = np.vstack([head[(ang < math.radians(35)) | (ang > math.radians(145))][:0], head])
    _ = ears
    Vh, Fh = prism(poly, 0.0015)
    from .blend_util import material
    red = material("CH_Badge_Red", (0.7, 0.02, 0.02), metallic=0.4, roughness=0.25)
    out.append(_obj("CH_Badge_Hellcat", tf(Vh), Fh, col, red, ngons=True, smooth=False))
    return out


def plate_texture():
    """Neutral EU-style plate image (no real registration): saved under assets/textures."""
    import os
    from . import PROJECT_ROOT
    path = os.path.join(PROJECT_ROOT, "assets", "textures", "plate_rear.png")
    if os.path.exists(path):
        return path
    import bpy
    W, H = 1040, 224
    img = bpy.data.images.new("plate_rear_tmp", W, H, alpha=False)
    px = np.ones((H, W, 4), np.float32)
    px[..., :3] = 0.93
    px[:6, :, :3] = px[-6:, :, :3] = px[:, :6, :3] = px[:, -6:, :3] = 0.05
    px[6:-6, 6:90, :3] = (0.0, 0.2, 0.6)
    img.pixels.foreach_set(px.ravel())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    return path


def build_all(m, bumper):
    from .blend_util import collection
    col = collection("Car_Visual_WIP")
    M = mats()
    objs = []
    for fn in (lambda: headlamps(m, col, M), lambda: grilles(m, col, M, bumper), lambda: splitter(col, M),
               lambda: tail_lamps(m, col, M, bumper), lambda: spoiler(m, col, M),
               lambda: valance_and_exhaust(m, col, M), lambda: plate(m, col, M, bumper),
               lambda: mirrors(m, col, M), lambda: door_handles(m, col, M), lambda: fuel_door(m, col, M),
               lambda: antenna(col, M), lambda: side_sills(m, col, M), lambda: wheel_liners(col, M),
               lambda: markers(m, col, M), lambda: hood_scoop_and_extractors(m, col, M),
               lambda: badges(m, col, M), lambda: cowl(m, col, M)):
        objs += fn()
    return [o.name for o in objs]
