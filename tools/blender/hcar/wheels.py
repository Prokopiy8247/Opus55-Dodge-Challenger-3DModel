"""Procedural wheels: 305/35ZR20 tire with tread grooves, 20x11 five split-spoke rim, brake disc,
caliper and hub (numpy mesh builders; Blender objects in build()).

Local wheel frame: X = axle (outboard positive), Y forward, Z up; origin = wheel centre on the
tire's centre plane. Right-side wheels use it directly; left-side wheels are mirrored in X.
"""
import math

import numpy as np

from .geom import resample

TIRE_W = 0.305
TIRE_R = (20 * 0.0254 + 2 * 0.305 * 0.35) / 2      # 0.3608 m
RIM_R = 10 * 0.0254                                # bead seat radius 0.254 m
RIM_W = 11 * 0.0254                                # 0.2794 m
RIM_LIP_R = RIM_R + 0.017                          # outer flange radius


def revolve(profile, n, closed_profile=False, angle0=0.0):
    """Revolve a profile [(x, r), ...] around the X axis: returns (V, F) quads, grid (n x m)."""
    prof = np.asarray(profile, float)
    m = len(prof)
    a = angle0 + np.linspace(0, 2 * math.pi, n, endpoint=False)
    V = np.empty((n, m, 3))
    V[..., 0] = prof[None, :, 0]
    V[..., 1] = np.cos(a)[:, None] * prof[None, :, 1]
    V[..., 2] = np.sin(a)[:, None] * prof[None, :, 1]
    i, j = np.meshgrid(np.arange(n), np.arange(m - (0 if closed_profile else 1)), indexing="ij")
    i, j = i.ravel(), j.ravel()
    i1 = (i + 1) % n
    j1 = (j + 1) % m
    F = np.stack([i * m + j, i * m + j1, i1 * m + j1, i1 * m + j], axis=1)
    return V.reshape(-1, 3), F


def tire_profile():
    """Half cross-section of the tire (x = axial, r = radius), from the inner bead over the tread to
    the outer bead, with four circumferential grooves (10 mm wide, 7 mm deep)."""
    h = TIRE_W / 2
    R = TIRE_R
    pts = []
    # inner sidewall: bead (x=-h+0.02, r=RIM_LIP_R-0.004) bulging to x=-h-0.004 at mid height
    for f in np.linspace(0, 1, 14):
        r = RIM_LIP_R - 0.004 + f * (R - 0.028 - (RIM_LIP_R - 0.004))
        bulge = 0.010 * math.sin(math.pi * min(1.0, f * 1.15))
        pts.append((-h + 0.018 - bulge, r))
    # inner shoulder (radius 0.028)
    for a in np.linspace(math.pi, math.pi / 2, 9)[1:]:
        pts.append((-h + 0.028 + 0.028 * math.cos(a) - 0.0, R - 0.028 + 0.028 * math.sin(a)))
    # tread with grooves
    grooves = [-0.085, -0.03, 0.03, 0.085]
    gw, gd = 0.010, 0.007
    xs = np.linspace(-h + 0.028, h - 0.028, 41)
    tread = []
    for x in xs:
        tread.append((x, R - 0.004 * (x / h) ** 2))
    tread = np.array(tread)
    out = []
    for x, r in tread:
        out.append((x, r))
    pts_tread = []
    gi = 0
    for k in range(len(out)):
        x, r = out[k]
        pts_tread.append((x, r))
        if gi < len(grooves) and k + 1 < len(out) and out[k + 1][0] > grooves[gi] - gw / 2:
            g = grooves[gi]
            rg = R - 0.004 * (g / h) ** 2
            pts_tread += [(g - gw / 2, rg), (g - gw / 2 + 0.0015, rg - gd), (g + gw / 2 - 0.0015, rg - gd),
                          (g + gw / 2, rg)]
            gi += 1
    # drop tread points that fall inside grooves
    clean = []
    for x, r in pts_tread:
        inside = any(g - gw / 2 + 1e-6 < x < g + gw / 2 - 1e-6 and r > R - 0.0045 - 0.004 * (g / h) ** 2 + 0.003
                     for g in grooves)
        if not inside:
            clean.append((x, r))
    pts += clean
    # outer shoulder
    for a in np.linspace(math.pi / 2, 0, 9)[1:]:
        pts.append((h - 0.028 + 0.028 * math.cos(a), R - 0.028 + 0.028 * math.sin(a)))
    # outer sidewall down to the bead, with a rim protector bead near the rim
    for f in np.linspace(0, 1, 16)[1:]:
        r = R - 0.028 - f * (R - 0.028 - (RIM_LIP_R + 0.002))
        bulge = 0.012 * math.sin(math.pi * min(1.0, (1 - f) * 1.1))
        prot = 0.006 * math.exp(-((f - 0.86) / 0.05) ** 2)
        pts.append((h - 0.018 + bulge + prot, r))
    return pts


def build_tire(n=144):
    V, F = revolve(tire_profile(), n)
    return V, F


def rim_planform(n_spokes=5, rho_hub=0.075, rho_split=0.150, rho_rim=0.226):
    """Window outlines (holes) of the rim face in the face plane: list of (m, 2) polygons (y, z)."""
    def w_main(r):  # half-width of the main spoke arm (m)
        return 0.023 - 0.008 * (r - rho_hub) / (rho_split - rho_hub)

    def delta(r):   # angular half-spread of the split arms (rad)
        f = np.clip((r - rho_split) / (rho_rim - rho_split), 0, 1)
        return math.radians(2.0) + math.radians(8.5) * f ** 0.85

    w_arm = 0.0095
    holes = []
    for k in range(n_spokes):
        phi0 = 2 * math.pi * k / n_spokes + math.pi / 2
        phi1 = phi0 + 2 * math.pi / n_spokes
        # big window between spoke k (right edge) and spoke k+1 (left edge)
        rs = np.linspace(rho_hub + 0.006, rho_split, 12)
        rs2 = np.linspace(rho_split, rho_rim, 14)[1:]
        right_edge = [(r, phi0 + w_main(r) / r) for r in rs] + [(r, phi0 + delta(r) + w_arm / r) for r in rs2]
        left_edge = [(r, phi1 - w_main(r) / r) for r in rs] + [(r, phi1 - delta(r) - w_arm / r) for r in rs2]
        a0 = right_edge[-1][1]
        a1 = left_edge[-1][1]
        rim_arc = [(rho_rim, a) for a in np.linspace(a0, a1, 18)[1:-1]]
        ah0 = left_edge[0][1]
        ah1 = right_edge[0][1]
        hub_arc = [(rho_hub + 0.006, a) for a in np.linspace(ah0, ah1, 8)[1:-1]]
        loop = right_edge + rim_arc + left_edge[::-1] + hub_arc
        holes.append(_round_polygon(_polar(loop), 0.007))
        # small window inside the split of spoke k+1 (between its two arms): starts where the arms
        # have separated by at least 1 degree
        r_test = np.linspace(rho_split, rho_rim, 400)
        gap = np.array([delta(r) - w_arm / r for r in r_test])
        r0 = r_test[np.argmax(gap > math.radians(0.5))] if (gap > math.radians(0.5)).any() else rho_rim - 0.01
        rr = np.linspace(r0, rho_rim, 12)
        inner_r = [(r, phi1 - delta(r) + w_arm / r) for r in rr]
        inner_l = [(r, phi1 + delta(r) - w_arm / r) for r in rr]
        arc = [(rho_rim, a) for a in np.linspace(inner_r[-1][1], inner_l[-1][1], 6)[1:-1]]
        loop2 = inner_r + arc + inner_l[::-1]
        holes.append(_round_polygon(_polar(loop2), 0.004))
    return holes


def _polar(loop):
    a = np.array(loop)
    return np.stack([a[:, 0] * np.cos(a[:, 1]), a[:, 0] * np.sin(a[:, 1])], axis=1)


def _round_polygon(p, r, iters=3):
    """Chaikin corner cutting (closed polygon), then resample evenly."""
    q = np.asarray(p, float)
    for _ in range(iters):
        a = q
        b = np.roll(q, -1, axis=0)
        q = np.empty((2 * len(a), 2))
        q[0::2] = 0.75 * a + 0.25 * b
        q[1::2] = 0.25 * a + 0.75 * b
    _ = r
    per = np.vstack([q, q[:1]])
    return resample(per, max(len(q) // 2, 24))[:-1]


def face_depth(rho, rho_rim=0.232):
    """Axial position of the spoke face (0 at the rim lip plane, negative inboard): concave dish."""
    f = np.clip(rho / rho_rim, 0, 1)
    return -0.072 * (1 - f ** 1.6)


def _sweep(centre, lateral, width, thick, depth, n_prof=16, p=0.35):
    """Arm mesh: rounded-rectangle cross-section swept along a centreline.
    centre (n, 2) in the face plane (y, z); lateral (n, 2) unit in-plane perpendiculars; width,
    thick (n,) full width and axial thickness; depth (n,) axial position of the top face.
    Returns (V (n*n_prof, 3), F) with X = axial."""
    n = len(centre)
    th = np.linspace(0, 2 * math.pi, n_prof, endpoint=False)
    cu = np.sign(np.cos(th)) * np.abs(np.cos(th)) ** p
    sv = np.sign(np.sin(th)) * np.abs(np.sin(th)) ** p
    V = np.empty((n, n_prof, 3))
    u = cu[None, :] * (width[:, None] / 2)
    v = (sv[None, :] - 1.0) * (thick[:, None] / 2)   # top at v = 0, bottom at -thick
    V[..., 0] = depth[:, None] + v
    V[..., 1] = centre[:, None, 0] + u * lateral[:, None, 0]
    V[..., 2] = centre[:, None, 1] + u * lateral[:, None, 1]
    i, j = np.meshgrid(np.arange(n - 1), np.arange(n_prof), indexing="ij")
    i, j = i.ravel(), j.ravel()
    j1 = (j + 1) % n_prof
    F = np.stack([i * n_prof + j, i * n_prof + j1, (i + 1) * n_prof + j1, (i + 1) * n_prof + j], axis=1)
    return V.reshape(-1, 3), F


def rim_arrays(x_lip=RIM_W / 2, n_spokes=5):
    """Rim as numpy arrays (V, F): five split spokes (swept arms), hub, face ring, barrel and lip."""
    rho_hub, rho_split, rho_end = 0.072, 0.150, 0.233
    parts = []

    def arm(phi_fn, r0, r1, wfn, n=24):
        r = np.linspace(r0, r1, n)
        phi = phi_fn(r)
        c = np.stack([r * np.cos(phi), r * np.sin(phi)], axis=1)
        d = np.gradient(c, axis=0)
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        lat = np.stack([-d[:, 1], d[:, 0]], axis=1)
        w = wfn(r)
        thick = 0.022 + 0.010 * (1 - (r - r0) / (r1 - r0))
        depth = x_lip + face_depth(r, rho_end) - 0.004
        return _sweep(c, lat, w, thick, depth)

    for k in range(n_spokes):
        phi0 = 2 * math.pi * k / n_spokes + math.pi / 2
        parts.append(arm(lambda r: np.full_like(r, phi0), 0.05, rho_split + 0.012,
                         lambda r: 0.056 - 0.016 * np.clip((r - rho_hub) / (rho_split - rho_hub), 0, 1)))
        for sgn in (-1.0, 1.0):
            def phi_b(r, s_=sgn, p0=phi0):
                f = np.clip((r - rho_split + 0.01) / (rho_end - rho_split + 0.01), 0, 1)
                return p0 + s_ * (math.radians(1.0) + math.radians(9.5) * f ** 0.8)
            parts.append(arm(phi_b, rho_split - 0.012, rho_end, lambda r: np.full_like(r, 0.023)))
    # hub face with a centre cap, face ring at the spoke ends, barrel and lip
    hub = [(x_lip - 0.080, 0.0), (x_lip - 0.066, 0.0), (x_lip - 0.062, 0.030), (x_lip - 0.066, 0.052),
           (x_lip - 0.074, 0.080), (x_lip - 0.098, 0.082)]
    ring = [(x_lip - 0.032, 0.240), (x_lip - 0.006, 0.236), (x_lip - 0.002, 0.226), (x_lip - 0.016, 0.221),
            (x_lip - 0.040, 0.224)]
    barrel = [(x_lip + 0.002, RIM_LIP_R), (x_lip + 0.007, RIM_LIP_R - 0.005), (x_lip + 0.004, RIM_R + 0.003),
              (x_lip - 0.010, RIM_R - 0.002), (x_lip - 0.030, 0.241), (-x_lip + 0.030, 0.241),
              (-x_lip + 0.010, RIM_R - 0.002), (-x_lip, RIM_LIP_R - 0.005), (-x_lip - 0.002, RIM_LIP_R)]
    for prof, n in ((hub, 64), (ring, 160), (barrel, 160)):
        parts.append(revolve(prof, n))
    # five lug nuts
    for k in range(5):
        a = 2 * math.pi * k / 5 + math.pi / 2 + math.pi / 5
        V, F = revolve([(x_lip - 0.060, 0.0), (x_lip - 0.058, 0.009), (x_lip - 0.072, 0.010)], 12)
        V[:, 1] += 0.057 * math.cos(a)
        V[:, 2] += 0.057 * math.sin(a)
        parts.append((V, F))
    vs, fs, off = [], [], 0
    for V, F in parts:
        vs.append(V)
        fs.append(F + off)
        off += len(V)
    return np.vstack(vs), np.vstack(fs)


def build_rim_blender(name, col, mats, x_lip=RIM_W / 2):
    """Rim object from rim_arrays (smooth shaded)."""
    from .meshkit import to_blender
    V, F = rim_arrays(x_lip)
    obj = to_blender(name, V, F, col=col)
    obj.data.materials.append(mats["rim"])
    return obj


def build_rim_blender_tess(name, col, mats, x_lip=RIM_W / 2):
    """Rim object (local frame), built with bmesh so the face with its windows can be triangulated."""
    import bmesh
    import bpy
    from mathutils import Vector
    from mathutils.geometry import tessellate_polygon
    bm = bmesh.new()
    rho_rim = 0.236          # face outer edge: a ring joins the spoke ends to the barrel
    holes = rim_planform(rho_rim=0.226)
    n_out = 180
    a = np.linspace(0, 2 * math.pi, n_out, endpoint=False)
    outer = np.stack([rho_rim * np.cos(a), rho_rim * np.sin(a)], axis=1)
    loops = [outer] + holes
    pts = np.vstack(loops)
    tris = tessellate_polygon([[Vector((p[0], p[1], 0.0)) for p in lp] for lp in loops])
    rho = np.linalg.norm(pts, axis=1)
    zf = face_depth(rho, rho_rim)
    thick = 0.030
    # front face (outboard) and back face
    vf = [bm.verts.new((x_lip + z - 0.004, p[0], p[1])) for p, z in zip(pts, zf)]
    vb = [bm.verts.new((x_lip + z - 0.004 - thick, p[0], p[1])) for p, z in zip(pts, zf)]
    for t in tris:
        try:
            bm.faces.new([vf[t[0]], vf[t[2]], vf[t[1]]])
            bm.faces.new([vb[t[0]], vb[t[1]], vb[t[2]]])
        except ValueError:
            pass
    # side walls of the windows and of the outer loop
    off = 0
    for li, lp in enumerate(loops):
        m = len(lp)
        for k in range(m):
            i0, i1 = off + k, off + (k + 1) % m
            quad = [vf[i0], vf[i1], vb[i1], vb[i0]] if li > 0 else [vf[i1], vf[i0], vb[i0], vb[i1]]
            try:
                bm.faces.new(quad)
            except ValueError:
                pass
        off += m
    # barrel, lip and hub as revolved profiles
    prof_barrel = [(x_lip + 0.002, RIM_LIP_R), (x_lip + 0.006, RIM_LIP_R - 0.004), (x_lip + 0.004, RIM_R + 0.004),
                   (x_lip - 0.010, RIM_R), (x_lip - 0.03, rho_rim + 0.001), (-x_lip + 0.03, rho_rim + 0.001),
                   (-x_lip + 0.01, RIM_R), (-x_lip, RIM_LIP_R - 0.004), (-x_lip - 0.002, RIM_LIP_R)]
    _revolve_bm(bm, prof_barrel, 160)
    hub = [(x_lip - 0.072 - 0.004, 0.0), (x_lip - 0.072 + 0.010, 0.030), (x_lip - 0.072 + 0.008, 0.062),
           (x_lip - 0.072 - 0.004, 0.078)]
    _revolve_bm(bm, hub, 64)
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    obj = bpy.data.objects.new(name, me)
    col.objects.link(obj)
    obj.data.materials.append(mats["rim"])
    try:
        mod = obj.modifiers.new("SmoothByAngle", "NODES")
        _ = mod
    except Exception:
        pass
    return obj


def _revolve_bm(bm, profile, n):
    V, F = revolve(profile, n)
    vs = [bm.verts.new(tuple(v)) for v in V]
    for f in F:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass


def build_disc(r=0.195, thick=0.034, n=96, x0=-0.030):
    prof = [(x0 + thick / 2, 0.085), (x0 + thick / 2, r), (x0 - thick / 2, r), (x0 - thick / 2, 0.085)]
    return revolve(prof, n, closed_profile=True)


def build_caliper(r_disc=0.195, front=True, x0=-0.030, disc_half=0.017):
    """Caliper hugging the disc rim (local frame), at the rear-upper side: an outboard and an
    inboard pad block on either side of the disc, joined by a bridge outside the disc's rim (a U,
    so the disc passes through it without touching)."""
    n_ang = 20
    span = math.radians(68 if front else 54)
    c_ang = math.radians(150)   # angle from +Y (forward) towards +Z: rear-upper position
    r_in, r_out = r_disc - 0.048, r_disc + 0.022
    w_out = disc_half + 0.040
    w_gap = disc_half + 0.004
    angs = c_ang + np.linspace(-span / 2, span / 2, n_ang)

    def curved_box(xa, xb, ra, rb):
        rings = [[(xo, rr * math.cos(a), rr * math.sin(a)) for a in angs] for xo in (xa, xb) for rr in (ra, rb)]
        V = np.array(rings).reshape(-1, 3)
        order = [0, 1, 3, 2]      # (xa, ra) (xa, rb) (xb, rb) (xb, ra)
        F = []
        for k in range(4):
            a_, b_ = order[k], order[(k + 1) % 4]
            for j in range(n_ang - 1):
                F.append([a_ * n_ang + j, a_ * n_ang + j + 1, b_ * n_ang + j + 1, b_ * n_ang + j])
        F.append([0 * n_ang, 2 * n_ang, 3 * n_ang, 1 * n_ang])
        F.append([1 * n_ang + n_ang - 1, 3 * n_ang + n_ang - 1, 2 * n_ang + n_ang - 1, 0 * n_ang + n_ang - 1])
        return V, np.array(F)
    parts = [curved_box(x0 + w_gap, x0 + w_out, r_in, r_out),          # outboard pad block
             curved_box(x0 - w_out, x0 - w_gap, r_in, r_out),          # inboard pad block
             curved_box(x0 - w_gap, x0 + w_gap, r_disc + 0.004, r_out)]  # bridge over the rim
    Vs, Fs, off = [], [], 0
    for V, F in parts:
        Vs.append(V)
        Fs.append(F + off)
        off += len(V)
    return np.vstack(Vs), np.vstack(Fs)