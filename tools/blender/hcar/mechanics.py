"""Simplified mechanical parts (Blender side): floor pan with tunnel, fuel tank, engine (V8 block,
heads, supercharger, pulleys), radiator and core support, front and rear subframes, suspension
(SLA front, five-link rear, coil-overs, knuckles, tie rods), drive shaft, differential, half
shafts, exhaust (pipes, mufflers, connection to the two tips).

Positions follow docs/specs.md (wheelbase 2,950 mm, track 1,667/1,669 mm) and the body shell.
Left/right parts are separate objects named *_L / *_R (x < 0 is the car's left).
"""
import math

import numpy as np

from . import body_tables as bt
from .meshkit import merge, to_blender
from .wheels import revolve


# ------------------------------------------------------------------------------------------------
# primitives (quad meshes)
# ------------------------------------------------------------------------------------------------
def box(c, size, bevel=0.0):
    """Axis-aligned box centred at c with size (sx, sy, sz); optional chamfer of the vertical edges."""
    cx, cy, cz = c
    sx, sy, sz = (s / 2 for s in size)
    if bevel <= 0:
        V = np.array([(x, y, z) for z in (-sz, sz) for y in (-sy, sy) for x in (-sx, sx)]) + c
        F = np.array([[0, 2, 3, 1], [4, 5, 7, 6], [0, 1, 5, 4], [2, 6, 7, 3], [0, 4, 6, 2], [1, 3, 7, 5]])
        return V, F
    b = min(bevel, sx * 0.9, sy * 0.9)
    ring = np.array([(sx - b, -sy), (sx, -sy + b), (sx, sy - b), (sx - b, sy), (-sx + b, sy), (-sx, sy - b),
                     (-sx, -sy + b), (-sx + b, -sy)])
    n = len(ring)
    V = np.vstack([np.c_[ring, np.full(n, -sz)], np.c_[ring, np.full(n, sz)]]) + c
    F = [[k, (k + 1) % n, n + (k + 1) % n, n + k] for k in range(n)]
    F += [[n + k for k in range(n)], list(range(n))[::-1]]
    # caps as fans of quads (keep quads): split the octagon into 3 quads
    caps = []
    for off, rev in ((n, False), (0, True)):
        q = [[off + 0, off + 1, off + 2, off + 3], [off + 0, off + 3, off + 4, off + 7], [off + 4, off + 5, off + 6, off + 7]]
        caps += [qq[::-1] if rev else qq for qq in q]
    return V, np.array(F[:n] + caps)


def tube(path, r, n=12, closed_ends=True):
    """Tube of radius r along a polyline path (m, 3)."""
    path = np.asarray(path, float)
    m = len(path)
    d = np.gradient(path, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    ref = np.array([0.0, 0.0, 1.0])
    rings = []
    for i in range(m):
        t = d[i]
        a = ref if abs(np.dot(t, ref)) < 0.9 else np.array([1.0, 0.0, 0.0])
        u = np.cross(t, a)
        u /= np.linalg.norm(u)
        v = np.cross(t, u)
        ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
        rings.append(path[i] + r * (np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v))
    V = np.vstack(rings)
    F = [[i * n + j, i * n + (j + 1) % n, (i + 1) * n + (j + 1) % n, (i + 1) * n + j]
         for i in range(m - 1) for j in range(n)]
    if closed_ends:
        c0, c1 = len(V), len(V) + 1
        V = np.vstack([V, path[0], path[-1]])
        F += [[c0, (j + 1) % n, j, j] for j in range(n)]
        F += [[c1, (m - 1) * n + j, (m - 1) * n + (j + 1) % n, (m - 1) * n + (j + 1) % n] for j in range(n)]
    return V, np.array(F)


def cylinder(p0, p1, r, n=16):
    return tube(np.array([p0, p1]), r, n)


def coil(p0, p1, r_coil, r_wire, turns=6.5, n_per_turn=24):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    axis = p1 - p0
    L = np.linalg.norm(axis)
    t = axis / L
    a = np.array([0, 0, 1.0]) if abs(t[2]) < 0.9 else np.array([1.0, 0, 0])
    u = np.cross(t, a)
    u /= np.linalg.norm(u)
    v = np.cross(t, u)
    k = np.linspace(0, 1, int(turns * n_per_turn))
    ang = 2 * math.pi * turns * k
    path = p0 + (k * L)[:, None] * t + r_coil * (np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v)
    return tube(path, r_wire, 8)


def slab(G, t, axis=(0.0, 0.0, 1.0)):
    """Closed plate from a grid G (nu, nv, 3) extruded by t against `axis` (the grid's (i, j) winding
    faces along `axis`; quads only)."""
    nu, nv = G.shape[:2]
    top = G.reshape(-1, 3)
    bot = top - t * np.asarray(axis, float)
    n = len(top)
    q = [[i * nv + j, (i + 1) * nv + j, (i + 1) * nv + j + 1, i * nv + j + 1] for i in range(nu - 1) for j in range(nv - 1)]
    F = q + [[n + a for a in f[::-1]] for f in q]
    loop = ([(i, 0) for i in range(nu)] + [(nu - 1, j) for j in range(1, nv)]
            + [(i, nv - 1) for i in range(nu - 2, -1, -1)] + [(0, j) for j in range(nv - 2, 0, -1)])
    ring = [i * nv + j for i, j in loop]
    m = len(ring)
    F += [[ring[(k + 1) % m], ring[k], n + ring[k], n + ring[(k + 1) % m]] for k in range(m)]
    return np.vstack([top, bot]), np.array(F)


def arm(p_in1, p_in2, p_out, w=0.025):
    """Triangular control arm (A-arm): two inner pivots and one outer ball joint, as 3 tubes."""
    parts = [cylinder(p_in1, p_out, w / 2, 10), cylinder(p_in2, p_out, w / 2, 10), cylinder(p_in1, p_in2, w / 2.5, 10)]
    return merge(parts)


# ------------------------------------------------------------------------------------------------
def _add(name, parts, col, mat, smooth=True):
    V, F = merge(parts) if isinstance(parts, list) else parts
    o = to_blender(name, V, F, col=col, smooth=smooth)
    o.data.materials.append(mat)
    return o


def mats():
    from .blend_util import material
    return {
        "under": material("CH_Underbody", (0.03, 0.03, 0.032), roughness=0.8),
        "steel": material("CH_Steel_Dark", (0.12, 0.12, 0.13), metallic=0.8, roughness=0.5),
        "alu": material("CH_Aluminium", (0.55, 0.56, 0.58), metallic=1.0, roughness=0.35),
        "engine": material("CH_Engine_Orange", (0.65, 0.18, 0.04), metallic=0.3, roughness=0.4),
        "black": material("CH_Plastic_BlackTrim", (0.02, 0.02, 0.021), roughness=0.55),
        "rad": material("CH_Radiator", (0.05, 0.05, 0.055), metallic=0.6, roughness=0.5),
        "spring": material("CH_Spring_Red", (0.55, 0.04, 0.03), metallic=0.4, roughness=0.35),
        "exhaust": material("CH_Exhaust_Steel", (0.09, 0.085, 0.08), metallic=0.8, roughness=0.6),
    }


# cabin / boot floor height (y, z) along the car: cabin floor, kick-up over the fuel tank under the
# rear seat, floor over the rear axle, boot floor
FLOOR_TAB = [(-2.30, 0.36), (-2.02, 0.36), (-1.95, 0.47), (-1.06, 0.47), (-1.00, 0.40), (-0.70, 0.40),
             (-0.62, 0.205), (1.00, 0.205)]


def tunnel_height(x, y):
    """Transmission tunnel above the cabin floor: wide and tall around the 8HP90 (y > 0.33), narrow over
    the drive shaft under the front seats and the console, so the seat cushions clear it."""
    x = np.abs(np.asarray(x, float))
    y = np.asarray(y, float)
    # narrow up to the front edge of the seat cushions (y = 0.26), then widening around the gearbox
    h = np.interp(y, [-0.30, 0.27, 0.33], [0.20, 0.20, 0.32])
    # over the rear kick-up the tunnel keeps its top (0.405 m) and fades into the rising floor
    zf = np.interp(y, [a for a, _ in FLOOR_TAB], [b for _, b in FLOOR_TAB])
    h = np.clip(0.205 + h - zf, 0.0, None)
    w0 = np.interp(y, [0.27, 0.33], [0.095, 0.17])          # half width of the flat top
    t = np.clip((w0 + 0.035 - x) / 0.035, 0.0, 1.0)         # 35 mm steep side
    return np.where(y > -0.72, h * t * t * (3 - 2 * t), 0.0)


def floor_grid():
    """Sampling of the floor pan: x as a fraction of the half width (5 cm over the floor, 1 cm over the
    tunnel sides) and y rows with the kinks of the floor profile and the tunnel transition included.
    The carpet uses the same sampling, so both surfaces have parallel chords."""
    u = np.unique(np.round(np.r_[np.linspace(-1.0, 1.0, 33), np.linspace(-0.3125, 0.3125, 51)], 6))
    kinks = [a for a, _ in FLOOR_TAB] + [-0.70, 0.27, 0.30, 0.33]
    ys = np.unique(np.round(np.r_[np.linspace(-2.30, -1.03, 18), np.linspace(-1.01, 1.00, 57), kinks], 6))
    return u, ys[(ys >= -2.30) & (ys <= 1.00)]


def floor_z(x, y):
    """Top of the floor pan's skin surface (the 1.5 mm thickness goes upwards from it)."""
    zf = np.interp(y, [a for a, _ in FLOOR_TAB], [b for _, b in FLOOR_TAB])
    return zf + tunnel_height(x, y) + 0.02 * (np.abs(np.asarray(x, float)) / 0.8) ** 4


def coilover_axes():
    """Right-side coil-over axes {'front'|'rear': (bottom, top, coil radius)} (shared with the wheel
    liners, whose inner wall leaves a slot for them)."""
    W = bt.WHEELS
    zw = W["FR"]["z"]
    yf, yr = W["FR"]["y"], W["RR"]["y"]
    knuckle_f = np.array([abs(W["FR"]["x"]) - 0.12, yf, zw])
    knuckle_r = np.array([abs(W["RR"]["x"]) - 0.12, yr, zw])
    return {"front": (knuckle_f + np.array([-0.06, 0.0, -0.06]), np.array([0.55, yf, 0.78]), 0.055),
            "rear": (knuckle_r + np.array([-0.10, -0.075, -0.08]), np.array([0.52, yr - 0.09, 0.70]), 0.05)}


def build_all():
    from .blend_util import collection
    col = collection("Car_Visual_WIP")
    M = mats()
    out = []
    W = bt.WHEELS
    zw = W["FR"]["z"]
    yf, yr = W["FR"]["y"], W["RR"]["y"]
    # ---- floor pan with transmission tunnel (one piece, both sides): cabin floor, kick-up over the
    # fuel tank under the rear seat, floor over the rear axle (narrow between the coil-overs), boot floor
    u, ys = floor_grid()
    nx = len(u)
    rows = []
    for y in ys:
        hw = 0.80 if y > -1.02 else (0.50 if y > -1.96 else 0.60)
        xs = u * hw
        rows.append(np.c_[xs, np.full(nx, y), floor_z(xs, y)])
    rows = np.array(rows)
    V = rows.reshape(-1, 3)
    F = np.array([[i * nx + j, i * nx + j + 1, (i + 1) * nx + j + 1, (i + 1) * nx + j]
                  for i in range(len(ys) - 1) for j in range(nx - 1)])
    out.append(_add("CH_FloorPan", (V, F), col, M["under"]))
    # ---- fuel tank under the rear seat (below the kick-up, in front of the rear subframe)
    # saddle tank: two halves either side of the drive shaft
    out.append(_add("CH_FuelTank", [box((sx * 0.205, -0.92, 0.30), (0.27, 0.42, 0.16), bevel=0.05) for sx in (-1, 1)],
                    col, M["under"]))
    # ---- engine: block, heads (V), supercharger, pulleys
    eng = [box((0.0, 1.38, 0.52), (0.46, 0.62, 0.30), bevel=0.04)]
    for sx in (-1, 1):
        hc = np.array([sx * 0.20, 1.38, 0.72])
        V, F = box((0, 0, 0), (0.17, 0.60, 0.11), bevel=0.02)
        a = math.radians(-sx * 35)
        R = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
        eng.append((V @ R.T + hc, F))
    eng.append(box((0.0, 1.36, 0.86), (0.36, 0.56, 0.14), bevel=0.05))   # supercharger case
    eng.append(box((0.0, 1.72, 0.84), (0.16, 0.14, 0.11), bevel=0.03))   # snout / throttle body
    out.append(_add("CH_Engine", eng, col, M["engine"]))
    pul = []
    for (x, z, r) in ((0.0, 0.84, 0.055), (0.0, 0.48, 0.10), (0.16, 0.66, 0.06), (-0.16, 0.66, 0.06)):
        V, F = revolve([(0.0, 0.0), (0.0, r), (0.03, r), (0.03, 0.0)], 24)
        pul.append((V[:, [1, 0, 2]] + [x, 1.70, z], F))
    out.append(_add("CH_Engine_Pulleys", pul, col, M["alu"]))
    out.append(_add("CH_Transmission", cylinder((0, 1.05, 0.37), (0, 0.35, 0.36), 0.14, 20), col, M["alu"]))
    # ---- radiator and core support
    # the core reaches behind the support's bars and posts (seen through the grille there is no
    # straight path past it into the engine bay); 5 mm clear of the support in y
    out.append(_add("CH_Radiator", box((0.0, 2.02, 0.565), (1.32, 0.05, 0.43)), col, M["rad"]))
    core = [box((0.0, 2.08, 0.80), (1.40, 0.06, 0.05)), box((0.0, 2.08, 0.32), (1.40, 0.06, 0.05)),
            box((-0.68, 2.08, 0.56), (0.05, 0.06, 0.50)), box((0.68, 2.08, 0.56), (0.05, 0.06, 0.50))]
    out.append(_add("CH_CoreSupport", core, col, M["steel"]))
    # radiator shroud: black plastic cover from the core support's top bar to under the hood's front
    # edge (closes the view through the hood / fascia shut line into the engine bay); its front edge
    # follows the inside of the fascia's top return 12 mm behind it (plan curve measured at z 0.82-0.85)
    xs = np.linspace(-0.65, 0.65, 27)
    y_front = np.interp(np.abs(xs), [0.0, 0.3, 0.5, 0.65], [2.286, 2.265, 2.2335, 2.2037])
    tt = np.linspace(0.0, 1.0, 9)
    G = np.stack([np.c_[np.full(9, x), 1.97 + (yf_ - 1.97) * tt, np.full(9, 0.836)] for x, yf_ in zip(xs, y_front)])
    # upright lip 6 cm behind the front edge up to 1 cm under the hood (blocks the level view through
    # the hood / fascia shut line; the hood's underside is >= 0.88 m there)
    Gl = np.stack([np.c_[np.full(2, x), np.full(2, yf_ - 0.06), [0.828, 0.872]] for x, yf_ in zip(xs, y_front)])
    out.append(_add("CH_RadiatorShroud", [slab(G, 0.008), slab(Gl, 0.006, axis=(0.0, -1.0, 0.0))], col, M["black"]))
    # ---- front subframe (rails + cross members) and rear cradle
    # rails from under the toe board (y 0.96) to the core support
    fsub = [box((sx * 0.42, 1.50, 0.30), (0.07, 1.08, 0.09)) for sx in (-1, 1)]
    fsub += [box((0.0, 1.32, 0.27), (0.90, 0.08, 0.07)), box((0.0, 1.85, 0.30), (0.90, 0.08, 0.07))]   # rear member ahead of the exhaust drop
    out.append(_add("CH_Subframe_Front", fsub, col, M["steel"]))
    # rails under the half shafts, cross members under the drive shaft
    rsub = [box((sx * 0.40, yr, 0.27), (0.07, 0.75, 0.08)) for sx in (-1, 1)]
    rsub += [box((0.0, yr + 0.30, 0.235), (0.88, 0.07, 0.07)), box((0.0, yr - 0.30, 0.235), (0.88, 0.07, 0.07))]
    out.append(_add("CH_Subframe_Rear", rsub, col, M["steel"]))
    # ---- drive shaft, differential, half shafts
    out.append(_add("CH_DriveShaft", cylinder((0, 0.35, 0.33), (0, yr + 0.18, 0.32), 0.045, 16), col, M["steel"]))
    out.append(_add("CH_Differential", box((0.0, yr, 0.33), (0.30, 0.30, 0.24), bevel=0.06), col, M["alu"]))
    # ---- per side: suspension, half shaft, exhaust
    for side, sx in (("L", -1.0), ("R", 1.0)):
        xw = sx * abs(W["FR"]["x"])
        xr = sx * abs(W["RR"]["x"])
        knuckle_f = np.array([xw - sx * 0.12, yf, zw])
        knuckle_r = np.array([xr - sx * 0.12, yr, zw])
        parts = [box(tuple(knuckle_f), (0.06, 0.12, 0.22), bevel=0.02), box(tuple(knuckle_r), (0.06, 0.12, 0.18), bevel=0.02)]
        out.append(_add(f"CH_Knuckles_{side}", parts, col, M["steel"]))
        # front SLA: lower arm, upper arm, tie rod, coil-over
        la = arm((sx * 0.38, yf + 0.18, 0.24), (sx * 0.38, yf - 0.20, 0.24), knuckle_f + [0, 0, -0.12])
        # upper A-arm wide enough for the coil-over to pass between its legs
        ua = arm((sx * 0.45, yf + 0.20, 0.62), (sx * 0.45, yf - 0.20, 0.62), knuckle_f + [0, 0, 0.14])
        tr = cylinder((sx * 0.40, yf + 0.14, 0.30), knuckle_f + [0, 0.12, -0.04], 0.011, 10)
        out.append(_add(f"CH_Susp_Front_Arms_{side}", [la, ua, tr], col, M["steel"]))
        cb, ct, _ = coilover_axes()["front"]
        top = ct * [sx, 1, 1]
        bot = cb * [sx, 1, 1]
        out.append(_add(f"CH_Susp_Front_Damper_{side}", cylinder(bot, top, 0.024, 16), col, M["alu"]))
        out.append(_add(f"CH_Susp_Front_Spring_{side}", coil(bot + (top - bot) * 0.55, top - (top - bot) * 0.14, 0.055, 0.008),
                        col, M["spring"]))
        # rear five-link: five rods + coil-over
        links = []
        for (yi, zi, yo, zo) in ((0.20, 0.26, 0.10, -0.10), (-0.20, 0.26, -0.10, -0.10), (0.15, 0.55, 0.06, 0.12),
                                 (-0.28, 0.52, -0.10, 0.12), (0.32, 0.30, 0.12, -0.02)):
            links.append(cylinder((sx * 0.36, yr + yi, zi), knuckle_r + [0, yo, zo], 0.012, 10))
        out.append(_add(f"CH_Susp_Rear_Links_{side}", links, col, M["steel"]))
        cb, ct, _ = coilover_axes()["rear"]
        top = ct * [sx, 1, 1]
        bot = cb * [sx, 1, 1]
        out.append(_add(f"CH_Susp_Rear_Damper_{side}", cylinder(bot, top, 0.022, 16), col, M["alu"]))
        out.append(_add(f"CH_Susp_Rear_Spring_{side}", coil(bot + (top - bot) * 0.30, top - (top - bot) * 0.08, 0.05, 0.008),
                        col, M["spring"]))
        out.append(_add(f"CH_HalfShaft_{side}", cylinder((sx * 0.14, yr, 0.33), knuckle_r, 0.025, 12), col, M["steel"]))
        # exhaust: manifold area -> along the tunnel side -> muffler behind the rear axle -> tip
        # under the floor all the way (below the tank, the subframe rails and the half shafts)
        path = np.array([(sx * 0.30, 1.30, 0.42), (sx * 0.30, 1.17, 0.36), (sx * 0.27, 1.06, 0.165), (sx * 0.24, 0.95, 0.155),
                         (sx * 0.22, 0.70, 0.155), (sx * 0.22, -0.70, 0.155), (sx * 0.25, -1.20, 0.155),
                         (sx * 0.30, -1.80, 0.155), (sx * 0.40, -1.95, 0.20), (sx * 0.46, -2.10, 0.235),
                         (sx * 0.5385, -2.38, 0.241)])
        from .geom import resample
        pipe = tube(resample(path, 60), 0.035, 12)
        muffler = box((sx * 0.44, -2.03, 0.265), (0.22, 0.34, 0.13), bevel=0.06)
        out.append(_add(f"CH_Exhaust_{side}", [pipe, muffler], col, M["exhaust"]))
    return [o.name for o in out]
