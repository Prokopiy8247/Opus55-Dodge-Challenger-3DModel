"""Interior trim and seating (P1b): front seats, rear bench, door cards, quarter / C-pillar trims,
A- and B-pillar trims, headliner, carpet with toe board and firewall, floor mats, sill plates, kick
panels, package shelf and seat belts.

Parts that follow the body shell (headliner, quarter trims, A-pillars) are placed by ray casts against
the finished exterior (collection Car_Visual), so they sit a fixed distance inside it. Every function
returns a Builder (ikit) in car coordinates; interior.build_interior() turns them into objects.
Material slots used here: see interior.MATS.
"""
import math

import numpy as np

from . import interior_tables as it
from .ikit import Builder, closed_loft, disc, loft, quad, resample, rounded_box, stitches, sweep
from .mechanics import floor_z

CARPET = 0.010            # carpet thickness over the floor pan skin (incl. the pan's 1.5 mm)


# ------------------------------------------------------------------------------------------------
# ray casts against the exterior
# ------------------------------------------------------------------------------------------------
class Shell:
    """World-space BVH trees of exterior parts (evaluated meshes, thickness included)."""

    def __init__(self, names):
        import bpy
        from mathutils.bvhtree import BVHTree
        dg = bpy.context.evaluated_depsgraph_get()
        self.trees = []
        for n in names:
            o = bpy.data.objects.get(n)
            if o is None or o.type != "MESH":
                continue
            oe = o.evaluated_get(dg)
            me = oe.to_mesh()
            co = np.empty(len(me.vertices) * 3, np.float32)
            me.vertices.foreach_get("co", co)
            M = np.array(o.matrix_world)
            W = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
            polys = [tuple(p.vertices) for p in me.polygons]
            oe.to_mesh_clear()
            self.trees.append((n, BVHTree.FromPolygons([tuple(map(float, w)) for w in W], polys)))

    def cast(self, origin, direction, dist=3.0):
        """Nearest hit (point, normal, object name, distance) or None."""
        from mathutils import Vector
        best = None
        o, d = Vector(tuple(map(float, origin))), Vector(tuple(map(float, direction))).normalized()
        for n, t in self.trees:
            loc, nrm, _, dd = t.ray_cast(o, d, dist)
            if loc is not None and (best is None or dd < best[3]):
                best = (np.array(loc), np.array(nrm), n, dd)
        return best


# ------------------------------------------------------------------------------------------------
# seat geometry helpers
# ------------------------------------------------------------------------------------------------
def pillow_section(top_fn, hw, z_bot, r_top=0.03, r_bot=0.015, n_top=41, n_arc=6, n_wall=3, n_bot=13):
    """Closed (u, z) outline: flat bottom at z_bot, side walls at u = -+hw, top surface z = top_fn(u),
    rounded top and bottom corners. The point count does not depend on the arguments (for lofts)."""
    # corner radii never exceed 45 % of the local thickness (thin sections at rounded ends)
    th = min(float(top_fn(0.9 * hw)), float(top_fn(-0.9 * hw))) - z_bot
    r_top = max(min(r_top, 0.45 * th), 1e-4)
    r_bot = max(min(r_bot, 0.45 * th), 1e-4)
    pts = []
    for u in np.linspace(-hw + r_bot, hw - r_bot, n_bot):
        pts.append((u, z_bot))
    for a in np.radians(np.linspace(-90, 0, n_arc)[1:]):
        pts.append((hw - r_bot + r_bot * math.cos(a), z_bot + r_bot + r_bot * math.sin(a)))
    ztr = float(top_fn(hw - r_top))
    for z in np.linspace(z_bot + r_bot, ztr - r_top, n_wall + 2)[1:-1]:
        pts.append((hw, z))
    for a in np.radians(np.linspace(0, 90, n_arc)):
        pts.append((hw - r_top + r_top * math.cos(a), ztr - r_top + r_top * math.sin(a)))
    for u in np.linspace(hw - r_top, -hw + r_top, n_top)[1:-1]:
        pts.append((u, float(top_fn(u))))
    ztl = float(top_fn(-hw + r_top))
    for a in np.radians(np.linspace(90, 180, n_arc)):
        pts.append((-hw + r_top + r_top * math.cos(a), ztl - r_top + r_top * math.sin(a)))
    for z in np.linspace(ztl - r_top, z_bot + r_bot, n_wall + 2)[1:-1]:
        pts.append((-hw, z))
    for a in np.radians(np.linspace(180, 270, n_arc)[:-1]):
        pts.append((-hw + r_bot + r_bot * math.cos(a), z_bot + r_bot + r_bot * math.sin(a)))
    return np.array(pts)


def bolster(u, hw, h, seam=0.150, dip=0.008):
    """Seat surface height offset across the width: slightly dished insert, bolster crown ~60 % out."""
    a = np.abs(u)
    out = -dip * np.cos(np.clip(a / seam, 0.0, 1.0) * np.pi / 2)
    t = np.clip((a - seam) / max(hw - seam, 1e-6), 0.0, 1.0)
    return out + h * np.sin(np.pi * np.clip(0.82 * t, 0.0, 1.0)) ** 1.3


def _rounded_end(stations, r, n=4, front=True):
    """(offset along the axis, drop of the top) for n stations rounding off an end with radius r."""
    out = []
    for k in range(1, n + 1):
        ph = 0.5 * math.pi * k / n
        out.append((r * math.sin(ph), r * (1 - math.cos(ph))))
    return out


# ------------------------------------------------------------------------------------------------
# front seats
# ------------------------------------------------------------------------------------------------
def front_seat(side=-1):
    """Bucket seat at x = side * SEAT_X (driver side = -1). Material slots: 0 leather, 1 perforated
    leather, 2 black plastic, 3 chrome, 4 stitching, 5 emboss decal."""
    fs = it.FRONT_SEAT
    xH, yH, zH = it.H_POINT
    xH = side * abs(xH)
    hw0 = fs["half_w"]
    yb, zb = yH - 0.135, zH - 0.075           # bight
    B = Builder()
    # ---- cushion: stations from the bight (v = 0) forward
    L, rf = 0.505, 0.05
    vs = np.linspace(-0.03, L - rf, 22)

    def cushion_sec(v, drop=0.0):
        zc = np.interp(v, [0.0, 0.25, 0.45, L], [zb + 0.005, zb + 0.030, zb + 0.050, zb + 0.045]) - drop
        bs = np.interp(v, [0.0, 0.12, 0.35, L], [0.55, 1.0, 1.0, 0.45])
        hw = np.interp(v, [0.0, 0.25, L], [hw0 - 0.01, hw0, hw0 - 0.005])
        return pillow_section(lambda u: zc + bolster(u, hw, fs["bolster_h"] * bs), hw, 0.300, r_top=0.028)

    secs = [(v, cushion_sec(v)) for v in vs]
    for dv, drop in _rounded_end(None, rf):
        secs.append((L - rf + dv, cushion_sec(L - rf + dv, drop)))
    S = np.array([np.c_[xH + s[:, 0], np.full(len(s), yb + v), s[:, 1]] for v, s in secs])
    V, F = closed_loft(S)
    # perforated insert: top faces within the seams
    cen = np.array([V[f].mean(axis=0) for f in F])
    top = cen[:, 2] > zb - 0.03
    mats = np.where(top & (np.abs(cen[:, 0] - xH) < 0.148) & (cen[:, 1] < yb + L - 0.06) & (cen[:, 1] > yb + 0.02), 1, 0)
    _add_with_mats(B, V, F, mats)
    # ---- back rest
    a = math.radians(it.TORSO_DEG)
    d = np.array([0.0, -math.sin(a), math.cos(a)])
    n = np.array([0.0, math.cos(a), math.sin(a)])
    X = np.array([1.0, 0.0, 0.0])
    B0 = np.array([xH, yb, zb - 0.02])
    Ls, rt = fs["back_len"], 0.04

    def front_q(u, s, hw, drop=0.0):
        lumbar = 0.020 * math.exp(-((s - 0.22) / 0.12) ** 2)
        bs = float(np.interp(s, [0.0, 0.08, 0.45, 0.70, Ls], [0.5, 1.0, 1.0, 0.45, 0.35]))
        return lumbar + bolster(u, hw, 0.070 * bs, dip=0.006) - drop

    def back_sec(s, drop=0.0):
        hw = float(np.interp(s, [0.0, 0.35, 0.60, Ls], [hw0, hw0, hw0 - 0.012, hw0 - 0.030]))
        t = float(np.interp(s, [0.0, Ls], [0.11, 0.075]))
        sec = pillow_section(lambda u: front_q(u, s, hw, drop), hw, -t + drop, r_top=0.03, r_bot=0.03)
        return sec

    ss = np.linspace(0.0, Ls - rt, 28)
    secs = [(s, back_sec(s)) for s in ss]
    for ds, drop in _rounded_end(None, rt):
        secs.append((Ls - rt + ds, back_sec(Ls - rt + ds, min(drop, 0.032))))
    S = np.array([B0 + s * d + sec[:, :1] * X + sec[:, 1:2] * n for s, sec in secs])
    V, F = closed_loft(S)
    cen = np.array([V[f].mean(axis=0) for f in F])
    rel = cen - B0
    su, ss_, qq = rel @ X, rel @ d, rel @ n
    mats = np.where((qq > -0.02) & (np.abs(su) < 0.148) & (ss_ > 0.04) & (ss_ < 0.50), 1, 0)
    _add_with_mats(B, V, F, mats)
    # ---- headrest and posts
    hc = B0 + d * (Ls + 0.035 + 0.085) - n * 0.012
    V, F = rounded_box(hc, (0.240, 0.170, 0.085), 0.036, axes=[X, d, n])
    B.add(V, F, 0)
    circ = np.array([(0.006 * math.cos(t), 0.006 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 10, endpoint=False)])
    for su_ in (-0.07, 0.07):
        p0 = B0 + d * (Ls - 0.06) + X * su_ - n * 0.03
        p1 = B0 + d * (Ls + 0.08) + X * su_ - n * 0.012
        V, F = sweep(np.linspace(p0, p1, 4), circ, up=(1, 0, 0))
        B.add(V, F, 3)
    # ---- emboss decal on the upper back
    s_e = 0.60
    pe = B0 + d * s_e + n * (front_q(0.0, s_e, hw0 - 0.012) + 0.0012)
    V, F, UV = quad(pe, -X, d, 0.18, 0.09)          # faces forward (n); reads correctly from the front
    B.add(V, F, 5, uv=UV)
    # ---- stitching along the insert seams and across the top of the back insert
    for su_ in (-0.152, 0.152):
        pts = [np.array([xH + su_, yb + v, np.interp(v, [0.0, 0.25, 0.45, L], [zb + 0.005, zb + 0.030, zb + 0.050, zb + 0.045])
                         + bolster(np.array([su_]), hw0, fs["bolster_h"])[0]]) for v in np.linspace(0.03, L - 0.07, 40)]
        V, F = stitches(pts, lambda p: (0, 0, 1))
        B.add(V, F, 4)
        pts = [B0 + d * s + X * su_ + n * front_q(su_, s, hw0) for s in np.linspace(0.05, 0.70, 50)]
        V, F = stitches(pts, lambda p, n=n: n)
        B.add(V, F, 4)
    pts = [B0 + d * 0.50 + X * su_ + n * front_q(su_, 0.50, hw0) for su_ in np.linspace(-0.150, 0.150, 30)]
    V, F = stitches(pts, lambda p, n=n: n)
    B.add(V, F, 4)
    # horizontal pleats across the side bolsters of the back rest and the cushion (as in the photos)
    for s_p in (0.10, 0.17, 0.24, 0.31, 0.38):
        for sg in (-1, 1):
            pts = [B0 + d * s_p + X * u + n * (front_q(u, s_p, hw0) + 0.0004) for u in sg * np.linspace(0.166, 0.243, 12)]
            V, F = stitches(pts, lambda p, n=n: n, pitch=0.0065)
            B.add(V, F, 4)
    for v_p in (0.10, 0.18, 0.26, 0.34):
        zc = float(np.interp(v_p, [0.0, 0.25, 0.45, L], [zb + 0.005, zb + 0.030, zb + 0.050, zb + 0.045]))
        for sg in (-1, 1):
            us_ = sg * np.linspace(0.166, 0.240, 12)
            pts = [np.array([xH + u, yb + v_p, zc + bolster(np.array([u]), hw0, fs["bolster_h"])[0] + 0.0004]) for u in us_]
            V, F = stitches(pts, lambda p: (0, 0, 1), pitch=0.0065)
            B.add(V, F, 4)
    # hard shell on the back of the back rest
    V, F = rounded_box(B0 + d * 0.42 - n * 0.098, (0.42, 0.60, 0.012), 0.010, axes=[X, d, n])
    B.add(V, F, 2)
    # ---- base: seat pan box, rails, side shields with the recline lever, belt buckle (inboard)
    V, F = rounded_box((xH, yb + 0.24, 0.268), (0.44, 0.50, 0.066), 0.012)
    B.add(V, F, 2)
    for su_ in (-0.17, 0.17):
        V, F = rounded_box((xH + su_, yb + 0.22, 0.229), (0.032, 0.62, 0.022), 0.004)
        B.add(V, F, 2)
    sx_out = xH + side * (hw0 + 0.012)
    V, F = rounded_box((sx_out, yb + 0.12, 0.33), (0.022, 0.36, 0.10), 0.01)
    B.add(V, F, 2)
    V, F = rounded_box((sx_out + side * 0.016, yb + 0.20, 0.345), (0.014, 0.10, 0.022), 0.006)
    B.add(V, F, 2)
    xb = xH - side * 0.208
    V, F = rounded_box((xb, yb - 0.005, zb + 0.050), (0.026, 0.020, 0.075), 0.006,
                       axes=[X, d, np.cross(X, d)])
    B.add(V, F, 2)
    return B


def _add_with_mats(B, V, F, mats):
    """Builder.add with a per-face material list."""
    base = B.n
    B.V.append(np.asarray(V, float))
    B.UV.append(np.zeros((len(V), 2)))
    for f, m in zip(F, mats):
        B.F.append([int(i) + base for i in f])
        B.M.append(int(m))
    B.n += len(V)


# ------------------------------------------------------------------------------------------------
# rear bench
# ------------------------------------------------------------------------------------------------
def rear_seat():
    """Rear bench: two contoured outer seats, centre section with the folded armrest, integrated
    head rests. Slots: 0 leather, 1 perforated, 2 plastic, 4 stitching."""
    B = Builder()
    xs0 = it.REAR_SEAT_X
    yf, zf = it.REAR_CUSHION_FRONT
    yb, zb = it.REAR_BACK_BOTTOM

    def top_fn(x, zc, hw):
        a = np.abs(x)
        seat = -0.012 * np.exp(-((a - xs0) / 0.16) ** 2)
        hump = 0.022 * np.exp(-(a / 0.09) ** 2)
        side = 0.030 * np.clip((a - (hw - 0.065)) / 0.05, 0.0, 1.0) ** 1.5
        return zc + seat + hump + side

    rf = 0.045
    # stations bracket the floor's kick-up step (0.40 m ahead of y = -1.0, 0.47 m behind y = -1.06)
    ys = np.unique(np.r_[np.linspace(yb - 0.02, yf - rf, 12), [-0.985, -1.005]])

    def sec(y, drop=0.0):
        zc = float(np.interp(y, [yb, yf], [zb + 0.005, zf])) - drop
        zbot = 0.420 if y > -0.99 else 0.485
        hw = float(np.interp(y, [-1.02, -0.98], [it.REAR_HW_BACK, it.REAR_HW_FRONT]))
        return pillow_section(lambda x: top_fn(x, zc, hw), hw, zbot, r_top=0.03, n_top=61)

    secs = [(y, sec(y)) for y in ys]
    for dv, drop in _rounded_end(None, rf):
        secs.append((yf - rf + dv, sec(yf - rf + dv, drop)))
    S = np.array([np.c_[s[:, 0], np.full(len(s), y), s[:, 1]] for y, s in secs])
    V, F = closed_loft(S)
    cen = np.array([V[f].mean(axis=0) for f in F])
    mats = np.where((cen[:, 2] > 0.50) & (np.abs(np.abs(cen[:, 0]) - xs0) < 0.14) & (cen[:, 1] < yf - 0.05), 1, 0)
    _add_with_mats(B, V, F, mats)
    # back rest
    yt, zt = it.REAR_BACK_TOP
    d = np.array([0.0, yt - yb, zt - zb])
    Lb = float(np.linalg.norm(d))
    d /= Lb
    n = np.array([0.0, -d[2], d[1]])
    if n[1] < 0:
        n = -n
    X = np.array([1.0, 0.0, 0.0])
    B0 = np.array([0.0, yb, zb - 0.02])

    def front_q(x, s, drop=0.0):
        a = np.abs(x)
        bol = 0.045 * (np.exp(-((a - (xs0 - 0.200)) / 0.035) ** 2) + np.exp(-((a - (xs0 + 0.195)) / 0.035) ** 2))
        bol *= float(np.interp(s, [0.0, 0.1, 0.45, Lb], [0.4, 1.0, 1.0, 0.6]))
        centre = -0.015 * np.clip(1 - a / 0.13, 0, 1) ** 0.3
        lumbar = 0.015 * math.exp(-((s - 0.20) / 0.12) ** 2)
        return lumbar + bol + centre - drop

    rt = 0.035

    def bsec(s, drop=0.0):
        # narrow beside the wheel houses (up to z ~ 0.81), shoulders wider above them
        hw = float(np.interp(s, [0.0, 0.37, 0.46, Lb], [it.REAR_HW_BACK, it.REAR_HW_BACK, 0.645, 0.640]))
        return pillow_section(lambda x: front_q(x, s, drop), hw, -0.12 + drop, r_top=0.025, r_bot=0.03, n_top=61)

    secs = [(s, bsec(s)) for s in np.linspace(0.0, Lb - rt, 14)]
    for ds, drop in _rounded_end(None, rt):
        secs.append((Lb - rt + ds, bsec(Lb - rt + ds, min(drop, 0.03))))
    S = np.array([B0 + s * d + sec[:, :1] * X + sec[:, 1:2] * n for s, sec in secs])
    V, F = closed_loft(S)
    cen = np.array([V[f].mean(axis=0) for f in F])
    rel = cen - B0
    mats = np.where((rel @ n > -0.02) & (np.abs(np.abs(rel @ X) - xs0) < 0.13) & (rel @ d > 0.05) & (rel @ d < 0.42), 1, 0)
    _add_with_mats(B, V, F, mats)
    # integrated head rests on the outer seats
    for sx in (-1, 1):
        V, F = rounded_box(B0 + d * (Lb + 0.07) + X * sx * xs0 - n * 0.03, (0.235, 0.16, 0.09), 0.035, axes=[X, d, n])
        B.add(V, F, 0)
    # folded centre armrest panel (outline stitching)
    pa = B0 + d * 0.30 + n * 0.012
    from .meshkit import rounded_rect
    rr = rounded_rect(0.20, 0.40, 0.03, 6)
    path = np.array([pa + X * p[0] + d * p[1] for p in rr])
    path = resample(path, 120, closed=True)
    V, F = stitches(np.vstack([path, path[:1]]), lambda p, n=n: n)
    B.add(V, F, 4)
    # buckles at the bight
    for xb in (-0.215, -0.04, 0.04, 0.215):
        V, F = rounded_box((xb, yb + 0.03, zb + 0.045), (0.024, 0.018, 0.06), 0.005)
        B.add(V, F, 2)
    return B


# ------------------------------------------------------------------------------------------------
# door cards
# ------------------------------------------------------------------------------------------------
DOOR_Y = (-0.585, 0.735)


def door_card(shell, side=-1):
    """Door card on the inside of the door skin (left side built, right mirrored by the caller).
    Slots: 0 leather (upper insert, armrest top), 2 black plastic, 3 chrome, 4 stitching, 6 grille mesh,
    7 satin silver."""
    B = Builder()
    ys = np.linspace(DOOR_Y[0], DOOR_Y[1], 64)
    # inner surface profile (x as a positive distance from the centreline), bottom to top
    zs = np.array([0.300, 0.330, 0.400, 0.480, 0.560, 0.600, 0.618, 0.640, 0.662, 0.672, 0.700, 0.760,
                   0.850, 0.920, 0.955, 0.972, 0.980])
    flat = np.array([0.835, 0.828, 0.826, 0.824, 0.815, 0.806, 0.800, 0.798, 0.798, 0.798, 0.792, 0.790,
                     0.792, 0.800, 0.808, 0.814, 0.828])
    arm = np.array([0.835, 0.828, 0.826, 0.824, 0.815, 0.792, 0.745, 0.728, 0.726, 0.745, 0.788, 0.790,
                    0.792, 0.800, 0.808, 0.814, 0.828])
    secs = []
    for y in ys:
        w = np.clip(min(y - (-0.43), 0.33 - y) / 0.08, 0.0, 1.0)
        w = w * w * (3 - 2 * w)
        xin = flat + (arm - flat) * w
        # back side: 95 mm outboard of the door skin's inner face (the skin bulges out to 0.96)
        back = np.array([0.862, 0.862, 0.858, 0.858, 0.858, 0.858, 0.858, 0.858, 0.858, 0.858, 0.858, 0.858,
                         0.852, 0.845, 0.838, 0.834, 0.834])
        # end taper: the card thins to 2 cm at its front and rear ends
        e = np.clip(min(y - DOOR_Y[0], DOOR_Y[1] - y) / 0.03, 0.0, 1.0)
        xin = back - (back - xin) * (0.25 + 0.75 * e)
        pts = [(back[k], zs[k]) for k in range(len(zs))] + [(xin[k], zs[k]) for k in range(len(zs) - 1, -1, -1)]
        secs.append(np.array([(side * p[0], y, p[1]) for p in pts]))
    S = np.array(secs)
    V, F = closed_loft(S)
    cen = np.array([V[f].mean(axis=0) for f in F])
    inner = np.abs(cen[:, 0]) < 0.832
    mats = np.where(inner & (((cen[:, 2] > 0.705) & (cen[:, 2] < 0.915)) | ((cen[:, 2] > 0.645) & (cen[:, 2] < 0.69)
                                                                              & (np.abs(cen[:, 0]) < 0.77))), 0, 2)
    _add_with_mats(B, V, F, mats)
    # stitching: top and bottom of the leather insert, along the armrest top
    for zz, xx in ((0.708, 0.791), (0.912, 0.799)):
        pts = [np.array([side * (xx - 0.0008), y, zz]) for y in np.linspace(DOOR_Y[0] + 0.06, DOOR_Y[1] - 0.06, 80)]
        V, F = stitches(pts, lambda p: (-side, 0, 0))
        B.add(V, F, 4)
    pts = [np.array([side * 0.738, y, 0.668]) for y in np.linspace(-0.36, 0.27, 60)]
    V, F = stitches(pts, lambda p: (0, 0, 1))
    B.add(V, F, 4)
    X = np.array([1.0, 0.0, 0.0])
    # window / lock switch pod on the armrest front
    pod = np.array([side * 0.752, 0.235, 0.676])
    V, F = rounded_box(pod, (0.052, 0.17, 0.020), 0.008)
    B.add(V, F, 2)
    for k, dy in enumerate((-0.055, -0.018, 0.018, 0.055)):
        V, F = rounded_box(pod + [0.0, dy, 0.012], (0.022, 0.024, 0.010), 0.004)
        B.add(V, F, 7 if k == 3 else 2)
    # inside handle: dark bezel + chrome lever
    hb = np.array([side * 0.788, 0.505, 0.842])
    V, F = rounded_box(hb, (0.012, 0.13, 0.05), 0.012, axes=[X, [0, 1, 0], [0, 0, 1]])
    B.add(V, F, 2)
    V, F = rounded_box(hb + [-side * 0.010, 0.0, 0.0], (0.012, 0.085, 0.016), 0.006)
    B.add(V, F, 3)
    # speaker grille with a silver ring
    sc = np.array([side * 0.8262, 0.475, 0.405])
    V, F, UV = disc(sc, (-side, 0, 0), 0.068, n=40)
    B.add(V, F, 6, uv=UV)
    from .ikit import lathe
    V, F = lathe([(0.0, 0.068), (0.004, 0.071), (0.006, 0.075), (0.0, 0.078)], sc - [side * 0.001, 0, 0], (-side, 0, 0), n=40)
    B.add(V, F, 7)
    return B


# ------------------------------------------------------------------------------------------------
# quarter trims (behind the doors, around the rear seat, up the C-pillar) and B-pillar trims
# ------------------------------------------------------------------------------------------------
def _solid(shell, side, y, z):
    """Ray from inside the cabin outwards: (hit, x distance of the shell or None) - glass and the
    doors do not count as shell (the trim stops at them)."""
    h = shell.cast((side * 0.25, y, z), (side, 0, 0), 1.0)
    if h is None:            # the ray leaves through the wheel arch opening: the design surface rules
        return (np.array([side * 9.0, y, z]), None, "none", 9.0)
    if h[2].startswith(("CH_Glass", "CH_Door")):
        return None
    return h


def _edge(fn, a, b, iters=16):
    """Bisection between a (fn true) and b (fn false)."""
    for _ in range(iters):
        m = (a + b) / 2
        if fn(m):
            a = m
        else:
            b = m
    return a


def _trim_x(h, y, z, extra=0.0):
    """Trim surface |x| at (y, z): a design surface (flush with the door card next to the B-pillar,
    0.705-0.725 m around the rear seat) unless the shell is closer (wheel house, C-pillar)."""
    x_hit = abs(h[0][0])
    x_rear = float(np.interp(z, [0.42, 0.95, 1.05, 1.10], [0.705, 0.725, 0.80, 2.0]))
    x_des = float(np.interp(y, [-0.85, -0.72], [x_rear, max(x_rear, 0.785)]))
    if -1.92 < y < -1.035:
        # flat cover over the rear wheel house (inner wall at 0.598, top at 0.802), easing out above it
        x_des = float(np.interp(z, [0.83, 0.87], [0.590, x_des]))
    # 8 mm over the wheel house wall; 30 mm under the quarter panel's rolled belt-line edge
    gap = 0.008 if h[2].startswith("CH_WheelLiners") else (0.030 if h[2].startswith("CH_Quarter") and z > 1.0 else 0.016)
    ar = 0.040 * math.exp(-((z - 0.635) / 0.035) ** 4) * float(np.clip(min(y + 1.02, -0.80 - y) / 0.05, 0, 1))
    return min(x_hit - gap, x_des) - ar - extra


def quarter_trim(shell, side=-1):
    """Trim on the inside of the quarter panel and the C-pillar (left side built by ray casts; the
    right side is built the same way). Lower panel: from 0.42 m up to the quarter glass's lower edge
    (bisection per column, capped at 1.10 m); C-pillar panel: from 1.08 m up to the headliner, from
    the glass's slanted rear edge back to the rear glass (bisection per row). Slots 0 (arm rest), 2."""
    B = Builder()
    nz = 26
    # two lower panels: beside the rear seat (from the floor) and behind its back rest (trunk side,
    # only above the wheel house and the coil-over)
    for ys, z_lo in ((np.linspace(-0.632, -1.300, 44), None), (np.linspace(-1.300, -1.640, 20), 0.85)):
        rows = []
        for y in ys:
            ok = lambda z, y=y: _solid(shell, side, y, z) is not None  # noqa: E731
            z0 = z_lo if z_lo is not None else max(0.42, float(floor_z(0.70, y)) + 0.02)
            zs_scan = np.linspace(z0, 1.10, 35)
            top = 1.10
            for k, z in enumerate(zs_scan):
                if not ok(z):
                    top = _edge(ok, zs_scan[k - 1], z) - 0.004 if k else z0
                    break
            col = []
            for z in np.linspace(z0, max(top, z0 + 0.01), nz):
                h = _solid(shell, side, y, z)
                # above the belt line a ray that hits nothing has no shell to follow
                good = h is not None and not (h[2] == "none" and z > 1.0)
                col.append((side * _trim_x(h, y, z), y, z) if good else (np.nan, y, z))
            rows.append(col)
        _grid_part(B, np.array(rows), side, lambda c: 0 if 0.60 < c[2] < 0.67 and -1.02 < c[1] < -0.80 else 2)
    # C-pillar
    zs = np.linspace(1.08, 1.33, 14)
    rows = []
    for z in zs:
        ok = lambda y, z=z: _solid(shell, side, y, z) is not None  # noqa: E731
        ys_scan = np.linspace(-0.80, -1.64, 85)
        state = [ok(y) for y in ys_scan]
        # the solid interval behind the quarter glass (C-pillar), if any
        idx = [k for k, s in enumerate(state) if s]
        if not idx:
            rows.append(None)
            continue
        k0 = idx[0]
        k1 = k0
        while k1 + 1 < len(state) and state[k1 + 1]:
            k1 += 1
        y0 = _edge(ok, ys_scan[k0], ys_scan[k0 - 1]) - 0.004 if k0 > 0 else ys_scan[0]
        y1 = _edge(ok, ys_scan[k1], ys_scan[k1 + 1]) + 0.004 if k1 + 1 < len(state) else ys_scan[-1]
        col = []
        for y in np.linspace(y0, y1, 30):
            h = _solid(shell, side, y, z)
            # above the belt line a ray that hits nothing has no shell to follow
            good = h is not None and h[2] != "none"
            col.append((side * _trim_x(h, y, z, extra=0.002), y, z) if good else (np.nan, y, z))
        rows.append(col)
    good = [r for r in rows if r is not None]
    if len(good) >= 2:
        G = np.array(good).transpose(1, 0, 2)        # (y columns, z rows)
        _grid_part(B, G, side, lambda c: 2)
    return B


def _grid_part(B, G, side, mat_fn):
    """Structured (ni, nj, 3) grid with NaN holes -> faces of the complete cells, facing the cabin."""
    ni, nj = G.shape[:2]
    valid = ~np.isnan(G[..., 0])
    V = np.nan_to_num(G.reshape(-1, 3))
    F, mats = [], []
    for i in range(ni - 1):
        for j in range(nj - 1):
            if valid[i, j] and valid[i + 1, j] and valid[i + 1, j + 1] and valid[i, j + 1]:
                F.append([i * nj + j, (i + 1) * nj + j, (i + 1) * nj + j + 1, i * nj + j + 1])
                mats.append(mat_fn(V[F[-1]].mean(axis=0)))
    if not F:
        return
    F = _orient(V, F, (-side, 0, 0))
    used = np.unique(np.array(F).ravel())
    remap = -np.ones(len(V), int)
    remap[used] = np.arange(len(used))
    _add_with_mats(B, V[used], [[int(remap[k]) for k in f] for f in F], mats)


def _orient(V, F, toward):
    """Reverse all faces when the first face's normal points away from `toward`."""
    f = F[len(F) // 2]
    nrm = np.cross(V[f[1]] - V[f[0]], V[f[2]] - V[f[0]])
    return [g[::-1] for g in F] if np.dot(nrm, toward) < 0 else F


def b_pillar_trim(side=-1):
    """Narrow trim strip over the hidden B-pillar between the door and quarter glass, with the front
    belt's upper anchor. Slots: 2 plastic, 3 chrome."""
    B = Builder()
    # 5 mm inside the glass's inner face (door / quarter glass tumblehome)
    path = np.array([(0.828, 0.995), (0.818, 1.05), (0.788, 1.10), (0.751, 1.15), (0.717, 1.20), (0.685, 1.25),
                     (0.662, 1.30)])
    path = np.array([(side * x, -0.660, z) for x, z in path])
    prof = np.array([(0.0, -0.040), (0.010, -0.034), (0.016, 0.0), (0.010, 0.034), (0.0, 0.040), (-0.004, 0.0)])
    V, F = sweep(resample(path, 14), prof, up=(-side, 0, 0))
    B.add(V, F, 2)
    anchor = np.array([side * 0.697, -0.645, 1.195])
    V, F = rounded_box(anchor, (0.014, 0.055, 0.03), 0.006)
    B.add(V, F, 3)
    return B


def a_pillar_trim(shell, side=-1):
    """Trim over the A-pillar between the windshield edge and the door glass front edge, from the dash
    up to the headliner (left side; right mirrored). Slot 2 plastic."""
    import bpy
    B = Builder()
    ws = _obj_world_verts(bpy.data.objects["CH_Glass_Windshield"])
    dg_ = _obj_world_verts(bpy.data.objects["CH_Glass_Door_L" if side < 0 else "CH_Glass_Door_R"])
    secs = []
    eye = np.array(it.EYE) * [abs(side) * (1 if side < 0 else -1), 1, 1]
    for z in np.linspace(1.00, 1.335, 14):
        mw = (np.abs(ws[:, 2] - z) < 0.006) & (ws[:, 0] * side > 0)
        md = (np.abs(dg_[:, 2] - z) < 0.006)
        if not mw.any() or not md.any():
            continue
        e1 = ws[mw][np.argmax(ws[mw][:, 0] * side)]          # windshield side edge
        e2 = dg_[md][np.argmax(dg_[md][:, 1])]              # door glass front edge
        w = e2 - e1
        w /= float(np.linalg.norm(w))
        # from 1 cm off the windshield edge (the glass wraps inwards there; its frit band hides the
        # joint) to 4 mm past the door glass edge, 18 mm in from the glass
        a_, b_ = e1 + w * 0.010, e2 + w * 0.004
        mid = (a_ + b_) / 2
        half = float(np.linalg.norm(b_ - a_)) / 2
        inward = (eye - mid)
        inward -= w * np.dot(inward, w)
        inward /= np.linalg.norm(inward)
        ts = np.linspace(0, math.pi, 13)
        front = [mid + inward * 0.018 + w * half * math.cos(t) + inward * 0.028 * math.sin(t) for t in ts]
        back = [mid + inward * 0.018 + w * half * math.cos(t) - inward * 0.004 * math.sin(t) for t in ts[::-1][1:-1]]
        secs.append(np.array(front + back))
    S = np.array(secs)
    V, F = closed_loft(S)
    B.add(V, F, 2)
    return B


def _obj_world_verts(o):
    co = np.empty(len(o.data.vertices) * 3, np.float32)
    o.data.vertices.foreach_get("co", co)
    M = np.array(o.matrix_world)
    return co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]


# ------------------------------------------------------------------------------------------------
# headliner
# ------------------------------------------------------------------------------------------------
def headliner(shell):
    """Ray-cast headliner 12 mm under the roof skin, between the windshield, rear glass and door glass
    tops (front / rear edges found by bisection on the first hit not being glass). Slot 8 headliner."""
    B = Builder()
    xs = np.linspace(-0.665, 0.665, 57)

    def ok(x, y):
        h = shell.cast((x, y, 1.20), (0, 0, 1), 0.5)
        return h is not None and not h[2].startswith("CH_Glass"), h

    def edge(x, y_in, y_out):
        a, b = y_in, y_out
        for _ in range(18):
            m = (a + b) / 2
            if ok(x, m)[0]:
                a = m
            else:
                b = m
        return a

    rows = []
    for x in xs:
        yf = edge(x, -0.40, 0.45)
        yr = edge(x, -0.40, -1.40)
        ys = np.linspace(yr, yf, 80)
        col = []
        for y in ys:
            good, h = ok(x, y)
            z = (h[0][2] - 0.012) if good else np.nan
            col.append((x, y, z))
        rows.append(col)
    G = np.array(rows)
    # fill rare misses along a column by interpolation
    for i in range(G.shape[0]):
        zc = G[i, :, 2]
        bad = np.isnan(zc)
        if bad.any() and (~bad).sum() >= 2:
            zc[bad] = np.interp(np.nonzero(bad)[0], np.nonzero(~bad)[0], zc[~bad])
    V, F = loft(G, closed_sec=False)
    F = _orient(V, F, (0, 0, -1))
    B.add(V, F, 8)
    # dome light
    V, F = rounded_box((0.0, -0.42, float(np.nanmin(G[:, :, 2][np.abs(G[:, :, 1] + 0.42) < 0.03])) - 0.008),
                       (0.16, 0.08, 0.016), 0.006)
    B.add(V, F, 2)
    return B, G


# ------------------------------------------------------------------------------------------------
# carpet, toe board, firewall, mats, sills, kick panels
# ------------------------------------------------------------------------------------------------
def carpet():
    """Carpet over the cabin floor and tunnel, rising as the toe board and the firewall behind the dash.
    Slots: 9 carpet, 10 floor mats."""
    from .ikit import offset_surface_grid
    from .mechanics import floor_grid
    B = Builder()
    # the floor pan's own sampling (parallel chords on the steep tunnel sides), 10 mm along its normal
    u, ys_all = floor_grid()
    xs = u * 0.80
    xs = np.r_[-0.795, xs[np.abs(xs) < 0.79], 0.795]
    ys = ys_all[(ys_all >= -0.70) & (ys_all <= 0.80)]         # up the rear kick-up to the seat
    G = np.array([np.c_[xs, np.full(len(xs), y), floor_z(xs, y)] for y in ys])
    Go, N = offset_surface_grid(G, 1.0)
    if np.mean(N[..., 2]) < 0:
        N = -N
    rows = list(G + CARPET * N)
    # toe board at 50 deg up to the firewall, then the firewall
    slope = math.tan(math.radians(50))
    for y in np.linspace(0.82, 0.975, 8):
        rows.append(np.c_[xs, np.full(len(xs), y), floor_z(xs, y) + CARPET + (y - 0.80) * slope])
    zt = floor_z(xs, 0.975) + CARPET + 0.175 * slope
    for z in np.linspace(0.0, 1.0, 6)[1:]:
        rows.append(np.c_[xs, np.full(len(xs), 0.985), zt + (0.90 - zt) * z])
    G = np.array(rows)
    V, F = loft(G, closed_sec=False)
    F = _orient(V, F, (0, 0, 1))
    B.add(V, F, 9)
    # floor mats (front pair and rear pair), 8 mm slabs following the floor
    for (x0, x1, y0, y1) in ((-0.72, -0.21, 0.30, 0.79), (0.21, 0.72, 0.30, 0.79), (-0.66, -0.17, -0.60, -0.36),
                             (0.17, 0.66, -0.60, -0.36)):
        mx = np.linspace(x0, x1, 14)
        my = np.linspace(y0, y1, 16)
        top = np.array([[(x, y, floor_z(x, y) + CARPET + 0.009) for y in my] for x in mx])
        bot = top.copy()
        bot[..., 2] -= 0.007
        Vt, Ft = loft(top, closed_sec=False)
        Ft = _orient(Vt, Ft, (0, 0, 1))
        B.add(Vt, Ft, 10)
        # rim
        ring = [top[i, 0] for i in range(len(mx))] + [top[-1, j] for j in range(1, len(my))] + \
               [top[i, -1] for i in range(len(mx) - 2, -1, -1)] + [top[0, j] for j in range(len(my) - 2, 0, -1)]
        ring = np.array(ring)
        S = np.array([ring, ring - [0, 0, 0.007]])
        Vr, Fr = loft(S, closed_sec=True)
        c = ring.mean(axis=0)
        Fr = _orient(Vr, Fr, ring[0] - c)
        B.add(Vr, Fr, 10)
    return B


def sills_and_kicks(side=-1):
    """Door sill scuff plate along the rocker and the kick panel under the dash end. Slots 2, 7."""
    B = Builder()
    V, F = rounded_box((side * 0.832, 0.07, 0.255), (0.066, 1.33, 0.080), 0.012)
    B.add(V, F, 2)
    V, F = rounded_box((side * 0.812, 0.07, 0.2965), (0.034, 1.26, 0.003), 0.0015)
    B.add(V, F, 7)
    V, F = rounded_box((side * 0.812, 0.86, 0.42), (0.035, 0.23, 0.39), 0.012)
    B.add(V, F, 2)
    return B


def package_shelf():
    """Parcel shelf under the rear glass with two speaker grilles. Slots 2, 6."""
    B = Builder()
    xs = np.linspace(-0.635, 0.635, 30)
    ys = np.linspace(-1.51, -1.695, 8)
    zf = lambda y: 1.100 + 0.018 * (y + 1.51) / -0.185  # noqa: E731
    top = np.array([[(x, y, zf(y)) for y in ys] for x in xs])
    V, F = loft(top, closed_sec=False)
    F = _orient(V, F, (0, 0, 1))
    B.add(V, F, 2)
    for sx in (-1, 1):
        c = np.array([sx * 0.42, -1.60, zf(-1.60) + 0.0015])
        V, F, UV = disc(c, (0, 0, 1), 0.07, n=36)
        B.add(V, F, 6, uv=UV)
    return B


# ------------------------------------------------------------------------------------------------
# seat belts
# ------------------------------------------------------------------------------------------------
def belts():
    """Red three-point belts: front belts hanging from the B-pillar anchors, rear belts from the parcel
    shelf over the back rests (a centre belt too). Slots 11 red belt, 2 plastic (tongues)."""
    B = Builder()
    prof = np.array([(-0.00125, -0.024), (0.00125, -0.024), (0.00125, 0.024), (-0.00125, 0.024)])
    for sx in (-1, 1):
        path = np.array([(sx * 0.690, -0.645, 1.180), (sx * 0.735, -0.646, 1.050), (sx * 0.755, -0.632, 0.850),
                         (sx * 0.762, -0.605, 0.650), (sx * 0.764, -0.570, 0.450), (sx * 0.762, -0.545, 0.300)])
        V, F = sweep(resample(path, 30), prof, up=(sx, 0, 0))
        B.add(V, F, 11)
        V, F = rounded_box((sx * 0.752, -0.628, 0.80), (0.010, 0.028, 0.06), 0.004)
        B.add(V, F, 2)
    # rear belts: shelf -> over the back rest top -> down its face to the bight
    yt, zt = it.REAR_BACK_TOP
    yb, zb = it.REAR_BACK_BOTTOM
    for xb in (-0.47, 0.47, 0.06):
        path = np.array([(xb, -1.53, 1.104), (xb, yt - 0.045, zt + 0.045), (xb, yt + 0.02, zt + 0.02),
                         (xb, (yt + yb) / 2 + 0.035, (zt + zb) / 2 + 0.005), (xb, yb + 0.05, zb + 0.07)])
        V, F = sweep(resample(path, 30), prof, up=(0.0, 0.915, 0.404))     # flat on the back rest
        B.add(V, F, 11)
    return B
