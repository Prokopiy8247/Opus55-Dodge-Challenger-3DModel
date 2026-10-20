"""Interior and cockpit (P1b): dashboard, cluster hood, instrument cluster (pods, dials, needles,
centre display), steering wheel and column, centre stack (touchscreen, vents, start button, climate
panel), console (shifter, cup holders, arm rest), glove box, outer vents, pedals, interior mirror, sun
visors, windshield frit, plus the trim and seats of interior_trim.py.

    build_interior()   builds collection Car_Interior (objects CH_Int_*); needs Car_Visual built first
    pose_cockpit(...)  sets needle / steering / pedal poses for test renders (rest pose = all zero)
    export_cockpit()   writes sim/vehicle/hellcat/cockpit.json (eye, pivots and axes in the car frame)

Animated parts (steering wheel, needles, pedals) are separate objects whose origin is their pivot; the
rest pose is: wheel straight ahead, needles at 12 o'clock (value 0 is reached by rotating to a_min),
pedals released.
"""
import json
import math
import os
import time

import numpy as np

from . import PROJECT_ROOT
from . import interior_tables as it
from . import interior_trim as tr
from .ikit import Builder, closed_loft, disc, lathe, loft, quad, resample, rounded_box, stitches, superellipse, sweep

TEX = os.path.join(PROJECT_ROOT, "assets", "textures", "interior")

# material slots shared by every interior builder: slot -> (name, colour, roughness, metallic, texture,
# tiles per metre (box UV) or None (part UVs), emission strength, alpha from texture)
MATS = {
    0: ("CH_Int_Leather", (0.020, 0.020, 0.021), 0.42, 0.0, "leather_grain.png", 8.0, 0.0, False),
    1: ("CH_Int_LeatherPerf", (0.018, 0.018, 0.019), 0.50, 0.0, "leather_perforated.png", 6.0, 0.0, False),
    2: ("CH_Int_PlasticBlack", (0.022, 0.022, 0.024), 0.55, 0.0, None, None, 0.0, False),
    3: ("CH_Int_Chrome", (0.80, 0.80, 0.82), 0.12, 1.0, None, None, 0.0, False),
    4: ("CH_Int_Stitch", (0.62, 0.62, 0.60), 0.70, 0.0, None, None, 0.0, False),
    5: ("CH_Int_Emboss", (0.03, 0.03, 0.03), 0.50, 0.0, "seat_emboss.png", None, 0.0, True),
    6: ("CH_Int_SpeakerMesh", (0.015, 0.015, 0.016), 0.60, 0.3, "leather_perforated.png", 25.0, 0.0, False),
    7: ("CH_Int_SatinSilver", (0.45, 0.45, 0.47), 0.32, 1.0, None, None, 0.0, False),
    8: ("CH_Int_Headliner", (0.035, 0.035, 0.037), 0.92, 0.0, None, None, 0.0, False),
    9: ("CH_Int_Carpet", (0.012, 0.012, 0.013), 1.00, 0.0, None, None, 0.0, False),
    10: ("CH_Int_FloorMat", (0.010, 0.010, 0.011), 0.95, 0.0, None, None, 0.0, False),
    11: ("CH_Int_BeltRed", (0.42, 0.025, 0.025), 0.65, 0.0, None, None, 0.0, False),
    12: ("CH_Int_SoftTouch", (0.026, 0.026, 0.028), 0.68, 0.0, "leather_grain.png", 5.0, 0.0, False),
    13: ("CH_Int_Carbon", (0.08, 0.08, 0.085), 0.22, 0.2, "carbon_twill.png", 40.0, 0.0, False),
    14: ("CH_Int_GlossBlack", (0.008, 0.008, 0.009), 0.08, 0.0, None, None, 0.0, False),
    15: ("CH_Int_DialTach", (1.0, 1.0, 1.0), 0.35, 0.0, "tach_dial.png", None, 1.6, False),
    16: ("CH_Int_DialSpeedo", (1.0, 1.0, 1.0), 0.35, 0.0, "speedo_dial.png", None, 1.6, False),
    17: ("CH_Int_ClusterDisplay", (1.0, 1.0, 1.0), 0.25, 0.0, "cluster_display.png", None, 1.4, False),
    18: ("CH_Int_Touchscreen", (1.0, 1.0, 1.0), 0.20, 0.0, "screen_perf_pages.png", None, 1.4, False),
    19: ("CH_Int_NeedleRed", (0.9, 0.12, 0.08), 0.40, 0.0, None, None, 3.0, False),
    20: ("CH_Int_StartRed", (0.85, 0.06, 0.05), 0.30, 0.0, None, None, 2.5, False),
    21: ("CH_Int_WheelBadge", (0.03, 0.03, 0.03), 0.35, 0.0, "wheel_badge.png", None, 0.0, True),
    22: ("CH_Int_MirrorGlass", (0.60, 0.62, 0.64), 0.02, 1.0, None, None, 0.0, False),
    23: ("CH_Int_Rubber", (0.015, 0.015, 0.015), 0.85, 0.0, None, None, 0.0, False),
    24: ("CH_Int_Frit", (0.004, 0.004, 0.004), 0.30, 0.0, None, None, 0.0, False),
    25: ("CH_Int_VentSlat", (0.012, 0.012, 0.013), 0.45, 0.0, None, None, 0.0, False),
}


def materials():
    """Create / update the interior materials; returns {slot: material}."""
    import bpy
    out = {}
    for slot, (name, col, rough, metal, tex, tiles, emis, alpha) in MATS.items():
        mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        outn = nt.nodes.new("ShaderNodeOutputMaterial")
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(bsdf.outputs[0], outn.inputs[0])
        bsdf.inputs["Base Color"].default_value = (*col, 1.0)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metal
        if tex:
            img = bpy.data.images.load(os.path.join(TEX, tex), check_existing=True)
            img.reload()                      # the texture generator may have rewritten the file
            ti = nt.nodes.new("ShaderNodeTexImage")
            ti.image = img
            if tiles:
                tc = nt.nodes.new("ShaderNodeTexCoord")
                mp = nt.nodes.new("ShaderNodeMapping")
                mp.inputs["Scale"].default_value = (tiles, tiles, tiles)
                nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
                nt.links.new(mp.outputs["Vector"], ti.inputs["Vector"])
            nt.links.new(ti.outputs["Color"], bsdf.inputs["Base Color"])
            if emis > 0:
                nt.links.new(ti.outputs["Color"], bsdf.inputs["Emission Color"])
                bsdf.inputs["Emission Strength"].default_value = emis
            if alpha:
                nt.links.new(ti.outputs["Alpha"], bsdf.inputs["Alpha"])
                for attr, val in (("surface_render_method", "DITHERED"), ("blend_method", "HASHED")):
                    try:
                        setattr(mat, attr, val)
                    except (AttributeError, TypeError):
                        pass
        elif emis > 0:
            bsdf.inputs["Emission Color"].default_value = (*col, 1.0)
            bsdf.inputs["Emission Strength"].default_value = emis
        mat.diffuse_color = (*col, 1.0) if not tex or tiles else (0.3, 0.3, 0.3, 1.0)
        # read by the Unity material importer (P4): texture, tiling, emission
        mat["hc_texture"] = tex or ""
        mat["hc_tiles_per_m"] = float(tiles or 0.0)
        mat["hc_emission"] = float(emis)
        mat["hc_alpha"] = bool(alpha)
        out[slot] = mat
    return out


def _vec(v):
    return np.asarray(v, float)


def _unit(v):
    v = _vec(v)
    return v / np.linalg.norm(v)


# ------------------------------------------------------------------------------------------------
# dashboard
# ------------------------------------------------------------------------------------------------
DASH_X = 0.775
DASH_FRONT_Y = 0.832          # behind the cowl's rear edge (0.841)


def dashboard(shell):
    """Dashboard body as a loft of (y, z) sections across x. The top follows the windshield / cowl
    ceiling (ray cast) 15 mm below it. Slots: 12 soft touch (top, face), 2 plastic (underside)."""
    B = Builder()
    xs = np.r_[np.linspace(-DASH_X, DASH_X, 85)]

    def ceiling(x, y):
        h = shell.cast((x, y, 0.80), (0, 0, 1), 0.6)
        return h[0][2] if h is not None else 1.05

    secs = []
    for x in xs:
        a = abs(x)
        edge = float(np.clip((DASH_X - a) / 0.05, 0.0, 1.0))           # outer 5 cm round off
        top = []
        for y in np.linspace(DASH_FRONT_Y, 0.640, 9):
            z = min(1.000 + 0.004 * math.sin((0.83 - y) / 0.19 * math.pi), ceiling(x, y) - 0.015)
            top.append((y, z))
        brow = [(0.626, top[-1][1] - 0.003), (0.614, top[-1][1] - 0.013), (0.607, top[-1][1] - 0.030)]
        face = [(0.604, 0.94), (0.600, 0.86), (0.594, 0.78), (0.583, 0.70), (0.567, 0.635), (0.557, 0.600),
                (0.561, 0.575), (0.578, 0.560)]
        under = [(0.640, 0.562), (0.720, 0.590), (0.800, 0.640), (0.858, 0.690), (0.860, 0.80), (0.845, 0.93)]
        pts = top + brow + face + under
        # outer ends: the section shrinks towards its centroid (rounded end caps)
        P = np.array(pts)
        c = P.mean(axis=0)
        P = c + (P - c) * (0.75 + 0.25 * edge)
        secs.append(np.c_[np.full(len(P), x), P])
    S = np.array(secs)
    V, F = closed_loft(S)
    cen = np.array([V[f].mean(axis=0) for f in F])
    mats = np.where(cen[:, 2] > 0.575, 12, 2)
    tr._add_with_mats(B, V, F, mats)
    return B


def cluster_hood():
    """Brow over the instrument cluster (driver side). Slot 12."""
    B = Builder()
    xc = it.CLUSTER_CENTRE[0]
    half = 0.240
    secs = []
    for x in np.linspace(xc - half, xc + half, 31):
        t = (x - xc) / half
        w = 1 - t * t                        # 1 at the centre, 0 at the ends (blends into the dash top)
        y_lip = 0.612 - 0.140 * w ** 0.6
        z_top = 1.000 + 0.055 * w ** 0.4     # >= 1.9 cm over the pod bezels (top at 1.009)
        pts = [(0.700, 0.999), (0.66, z_top), (y_lip + 0.03, z_top), (y_lip + 0.004, z_top - 0.004),
               (y_lip, z_top - 0.012), (y_lip + 0.006, z_top - 0.020), (y_lip + 0.03, z_top - 0.021), (0.640, 0.985)]
        secs.append(np.c_[np.full(len(pts), x), np.array(pts)])
    V, F = closed_loft(np.array(secs))
    B.add(V, F, 12)
    return B


# ------------------------------------------------------------------------------------------------
# instrument cluster
# ------------------------------------------------------------------------------------------------
def pod_centres():
    c = _vec(it.CLUSTER_CENTRE)
    return {"tach": c + [-it.POD_DX, 0, 0], "speedo": c + [it.POD_DX, 0, 0]}


def cluster():
    """Back panel, the two pods with chrome bezels, dials and the centre display. Needles are
    separate objects (needle_mesh). Slots 2, 3, 14, 15, 16, 17."""
    B = Builder()
    eye = _vec(it.EYE)
    c = _vec(it.CLUSTER_CENTRE)
    axis_c = _unit(eye - c)
    up_c = _unit(np.array([0, 0, 1.0]) - axis_c * axis_c[2])
    right_c = np.cross(up_c, axis_c)
    # back panel box (depth from 2 cm behind the dials back to the dash face)
    # back panel between the outer vent and the centre stack (x -0.555 .. -0.230)
    V, F = rounded_box(c - axis_c * 0.045 + right_c * (-0.0175), (0.325, 0.175, 0.05), 0.02, axes=[right_c, up_c, axis_c])
    B.add(V, F, 14)
    for key, pc in pod_centres().items():
        ax = _unit(eye - pc)
        # tube + chrome bezel (lathe profile: (axial towards the eye, radius))
        prof_out = [(-0.006, 0.0735), (0.030, 0.0735), (0.036, 0.0745)]
        prof_bezel = [(0.036, 0.0745), (0.041, 0.0725), (0.042, 0.0690), (0.039, 0.0660), (0.034, 0.0645)]
        prof_in = [(0.034, 0.0645), (0.004, 0.0618), (0.0, 0.0612)]
        for prof, slot in ((prof_out, 2), (prof_bezel, 3), (prof_in, 2)):
            V, F = lathe(prof, pc, ax, n=64)
            B.add(V, F, slot)
        V, F, UV = disc(pc, ax, it.POD_R, n=64)
        B.add(V, F, 15 if key == "tach" else 16, uv=UV)
    # centre display, recessed 4 mm behind the dials, with a gloss frame
    V, F, UV = quad(c - axis_c * 0.004, right_c, up_c, it.DISPLAY_W, it.DISPLAY_H)
    B.add(V, F, 17, uv=UV)
    V, F = rounded_box(c - axis_c * 0.010, (it.DISPLAY_W + 0.016, it.DISPLAY_H + 0.016, 0.010), 0.006,
                       axes=[right_c, up_c, axis_c])
    B.add(V, F, 14)
    return B


def needle_mesh():
    """Needle in its local frame: x right, y up (12 o'clock), z towards the eye; pivot at the origin.
    Slots 19 (needle), 14 (hub cap)."""
    B = Builder()
    L, tail = 0.053, 0.012
    V = np.array([(-0.0024, -tail, 0.0), (0.0024, -tail, 0.0), (0.0009, L, 0.0), (-0.0009, L, 0.0)])
    B.add(V, [[0, 1, 2, 3]], 19)
    V, F, UV = disc((0, 0, 0.0015), (0, 0, 1), 0.0095, n=24, ref=(0, 1, 0))
    B.add(V, F, 14)
    V, F = lathe([(0.0015, 0.0095), (0.0, 0.0095)], (0, 0, 0), (0, 0, 1), n=24)
    B.add(V, F, 14)
    return B


def needle_frames():
    """{name: (pivot, right, up, axis)} of the needles in the car frame (axis towards the eye)."""
    eye = _vec(it.EYE)
    out = {}
    for key, pc in pod_centres().items():
        ax = _unit(eye - pc)
        up = _unit(np.array([0, 0, 1.0]) - ax * ax[2])
        right = np.cross(up, ax)
        out[key] = (pc + ax * 0.003, right, up, ax)
    return out


# ------------------------------------------------------------------------------------------------
# steering wheel and column
# ------------------------------------------------------------------------------------------------
def wheel_frame():
    """(centre, right X, up U, axis A towards the driver)."""
    C = _vec(it.WHEEL_CENTRE)
    U = _vec(it.wheel_up())
    A = -_vec(it.column_axis())
    X = np.cross(U, A)
    return C, X, U, A


def _chaikin(P, n=3, closed=True):
    """Chaikin corner cutting; an open polyline keeps its end points."""
    P = np.asarray(P, float)
    for _ in range(n):
        if closed:
            Q = 0.75 * P + 0.25 * np.roll(P, -1, axis=0)
            R = 0.25 * P + 0.75 * np.roll(P, -1, axis=0)
            P = np.stack([Q, R], axis=1).reshape(-1, P.shape[1])
        else:
            Q = 0.75 * P[:-1] + 0.25 * P[1:]
            R = 0.25 * P[:-1] + 0.75 * P[1:]
            P = np.vstack([P[:1], np.stack([Q, R], axis=1).reshape(-1, P.shape[1]), P[-1:]])
    return P


def rim_outline(n=200):
    """Flat-bottom rim centreline in the wheel plane (s right, t up), closed, clockwise from the top."""
    R, flat = it.WHEEL_R, it.WHEEL_FLAT
    th_c = math.acos(-flat / R)
    pts = [(R * math.sin(t), R * math.cos(t)) for t in np.linspace(-th_c, th_c, 60)]
    pts += [(s, -flat) for s in np.linspace(R * math.sin(th_c), -R * math.sin(th_c), 12)[1:-1]]
    P = _chaikin(np.array(pts), 3)
    return resample(P, n, closed=True)


def steering_wheel():
    """Wheel in its local frame (x right, y up, z towards the driver; origin = wheel centre).
    Slots: 0 leather, 1 perforated grips, 7 satin silver, 14 gloss black, 2 plastic, 3 chrome,
    4 stitching, 21 badge."""
    B = Builder()
    X, U, A = np.eye(3)
    st = rim_outline(260)
    path = np.c_[st[:, 0], st[:, 1], np.zeros(len(st))]
    prof = superellipse(0.0155, 0.0185, 2.3, 22)
    V, F = sweep(path, prof, up=(0, 0, 1), closed_path=True)
    # perforated grips at 3 and 9 o'clock
    ring_n = len(prof)
    mats = []
    for f in F:
        i = f[0] // ring_n
        s, t = st[i % len(st)]
        ang = math.degrees(math.atan2(s, t))
        mats.append(1 if 55 < abs(ang) < 128 else 0)
    tr._add_with_mats(B, V, F, mats)
    # stitching on the driver side of the rim, along the inner edge of the upper arc (on the surface
    # at 45 deg of the superellipse section: 0.74 of each semi-axis)
    inner = []
    for s, t in st:
        ang = math.degrees(math.atan2(s, t))
        if abs(ang) < 52:
            r = math.hypot(s, t)
            k = (r - 0.0185 * 0.74) / r
            inner.append((s * k, t * k, 0.0155 * 0.74))
    if inner:
        Vs, Fs = stitches(np.array(inner), lambda p: (_unit((p[0], p[1], 0.0)) * -0.6 + np.array([0, 0, 0.8])), pitch=0.007)
        B.add(Vs, Fs, 4)
    # side spokes with button panels and silver frames
    sp = np.array([(-0.012, -0.030), (0.006, -0.032), (0.012, 0.0), (0.006, 0.030), (-0.012, 0.028), (-0.016, 0.0)])
    for sx in (-1, 1):
        p = np.array([(sx * 0.055, -0.010, 0.004), (sx * 0.110, -0.016, 0.0), (sx * 0.170, -0.024, -0.002)])
        Vp, Fp = sweep(resample(p, 8), sp, up=(0, 0, 1))      # profile: (axial, vertical)
        B.add(Vp, Fp, 14)
        pc = np.array([sx * 0.112, -0.013, 0.014])
        Vb, Fb = rounded_box(pc, (0.052, 0.040, 0.008), 0.008)
        B.add(Vb, Fb, 14)
        for k, (bx, by) in enumerate(((-0.014, 0.010), (0.0, 0.010), (0.014, 0.010), (-0.014, -0.008), (0.0, -0.008),
                                      (0.014, -0.008))):
            Vb, Fb = rounded_box(pc + [bx, by, 0.005], (0.010, 0.008, 0.004), 0.0018)
            B.add(Vb, Fb, 2)
        from .meshkit import rounded_rect
        loop = rounded_rect(0.060, 0.048, 0.012, 6)
        loop3 = np.c_[loop[:, 0] + pc[0], loop[:, 1] + pc[1], np.full(len(loop), 0.0175)]
        Vr, Fr = sweep(resample(loop3, 48, closed=True), superellipse(0.0025, 0.002, 2.0, 8), up=(0, 0, 1), closed_path=True)
        B.add(Vr, Fr, 7)
    # lower spoke: satin silver U from the hub to the flat bottom
    u_path = np.array([(-0.036, -0.050, 0.006), (-0.044, -0.090, 0.002), (-0.050, -0.128, -0.002), (-0.030, -0.145, -0.003),
                       (0.0, -0.148, -0.003), (0.030, -0.145, -0.003), (0.050, -0.128, -0.002), (0.044, -0.090, 0.002),
                       (0.036, -0.050, 0.006)])
    Vu, Fu = sweep(resample(_chaikin(u_path, 2, closed=False), 40), superellipse(0.009, 0.007, 2.5, 12), up=(0, 0, 1))
    B.add(Vu, Fu, 7)
    # hub / airbag cover, chrome badge surround and the SRT badge
    Vh, Fh = rounded_box((0.0, 0.004, 0.020), (0.150, 0.124, 0.056), 0.030)
    B.add(Vh, Fh, 2)
    from .meshkit import rounded_rect
    loop = rounded_rect(0.100, 0.064, 0.026, 8)
    loop3 = np.c_[loop[:, 0], loop[:, 1] + 0.004, np.full(len(loop), 0.0485)]
    Vr, Fr = sweep(resample(loop3, 64, closed=True), superellipse(0.0022, 0.0026, 2.0, 8), up=(0, 0, 1), closed_path=True)
    B.add(Vr, Fr, 3)
    Vq, Fq, UVq = quad((0.0, 0.004, 0.0487), (1, 0, 0), (0, 1, 0), 0.088, 0.044)
    B.add(Vq, Fq, 21, uv=UVq)
    # paddles behind the side spokes
    for sx in (-1, 1):
        Vp, Fp = rounded_box((sx * 0.135, 0.030, -0.030), (0.055, 0.032, 0.006), 0.003,
                             axes=[_unit((1, 0, sx * 0.25)), (0, 1, 0), _unit((-sx * 0.25, 0, 1))])
        B.add(Vp, Fp, 7)
    # rear cover towards the column
    Vc, Fc = lathe([(-0.008, 0.055), (-0.040, 0.046), (-0.065, 0.034), (-0.065, 0.0)], (0, 0, 0), (0, 0, 1), n=40)
    B.add(Vc, Fc, 2)
    return B


def steering_column():
    """Column shroud from behind the wheel into the dash, with the two stalks. Slot 2."""
    B = Builder()
    C, X, U, A = wheel_frame()
    col = -A
    V, F = rounded_box(C + col * 0.215, (0.105, 0.088, 0.29), 0.03, axes=[X, U, col])
    B.add(V, F, 2)
    circ = superellipse(0.0065, 0.0065, 2.0, 10)
    for sx in (-1, 1):
        p0 = C + col * 0.115 + U * 0.012 + X * sx * 0.04
        p1 = p0 + X * sx * 0.15 + U * 0.02 - col * 0.03
        V, F = sweep(np.linspace(p0, p1, 6), circ, up=(0, 0, 1))
        B.add(V, F, 2)
    return B


# ------------------------------------------------------------------------------------------------
# centre stack, climate panel, start button, console, shifter, arm rest
# ------------------------------------------------------------------------------------------------
def stack_frame():
    a = math.radians(it.STACK_TILT_DEG)
    n = np.array([0.0, -math.cos(a), math.sin(a)])          # face normal (towards the cabin)
    up = np.array([0.0, math.sin(a), math.cos(a)])
    return _vec(it.STACK_CENTRE), np.array([1.0, 0, 0]), up, n


def vent(centre, right, up, n, w, h, slats=6):
    """Vent on a surface point `centre` (normal n): satin silver bezel ring, black backing just in
    front of the surface, horizontal slats tilted 18 deg and a centre tab."""
    B = Builder()
    from .meshkit import rounded_rect
    loop = rounded_rect(w, h, min(w, h) * 0.18, 6)
    path = np.array([centre + n * 0.003 + right * p[0] + up * p[1] for p in loop])
    V, F = sweep(resample(path, 56, closed=True), superellipse(0.004, 0.003, 2.0, 8), up=n, closed_path=True)
    B.add(V, F, 7)
    V, F, UV = quad(centre + n * 0.0008, right, up, w - 0.004, h - 0.004)
    B.add(V, F, 14)
    a = math.radians(18.0)
    a2 = _unit(up * math.cos(a) + n * math.sin(a))
    a3 = _unit(n * math.cos(a) - up * math.sin(a))
    for k in range(slats):
        zc = (k + 0.5) / slats - 0.5
        V, F = rounded_box(centre + up * zc * (h - 0.012) + n * 0.0045, (w - 0.012, 0.0025, 0.0065), 0.001,
                           axes=[right, a2, a3])
        B.add(V, F, 25)
    V, F = rounded_box(centre + n * 0.009, (0.010, 0.018, 0.008), 0.003, axes=[right, up, n])
    B.add(V, F, 7)
    return B


def centre_stack():
    """Carbon surround with the touchscreen and two vents; climate panel with knobs and buttons; red
    start button. Slots 13, 14, 18, 7, 25, 2, 3, 20."""
    B = Builder()
    c, R, U, n = stack_frame()
    V, F = rounded_box(c, (0.445, 0.215, 0.030), 0.03, axes=[R, U, n])
    B.add(V, F, 13)
    V, F = rounded_box(c + n * 0.017, (0.212, 0.134, 0.010), 0.008, axes=[R, U, n])
    B.add(V, F, 14)
    V, F, UV = quad(c + n * 0.0222, R, U, it.SCREEN_W, it.SCREEN_H)
    B.add(V, F, 18, uv=UV)
    for sx in (-1, 1):
        B.merge(vent(c + R * sx * 0.163 + n * 0.015, R, U, n, 0.072, 0.120))
    # start button on the dash face: chrome ring + red face
    sb = _vec(it.START_BUTTON)
    a = math.radians(it.START_BUTTON_TILT_DEG)
    nb = np.array([0.0, -math.cos(a), math.sin(a)])
    V, F = lathe([(-0.004, 0.0175), (0.006, 0.0175), (0.008, 0.0150), (0.007, 0.0125)], sb, nb, n=36)
    B.add(V, F, 3)
    V, F, UV = disc(sb + nb * 0.0065, nb, 0.0125, n=36)
    B.add(V, F, 20, uv=UV)
    return B


def console(shell=None):
    """Console body on the tunnel, carbon tray, cup holders, shifter boot. Slots 2, 13, 14, 3, 7."""
    B = Builder()
    # the body stands on the flat top of the tunnel (half width 0.095 m under the seats), 2 mm above
    # the carpet, and flares out to the arm rest width at the top
    hw_top, hw_bot = it.CONSOLE_W / 2, 0.090
    ys = np.linspace(0.545, -0.585, 48)
    secs = []
    for y in ys:
        z_top = console_top(y)
        xb = np.linspace(-hw_bot, hw_bot, 9)
        zb = np.full(len(xb), float(tr.floor_z(0.0, y)) + tr.CARPET + 0.002)
        pts = [(x, z) for x, z in zip(xb, zb)]
        pts += [(hw_bot, zb[-1] + 0.03), (hw_top, z_top - 0.02), (hw_top - 0.008, z_top - 0.003),
                (hw_top - 0.02, z_top)]
        pts += [(-hw_top + 0.02, z_top), (-hw_top + 0.008, z_top - 0.003), (-hw_top, z_top - 0.02),
                (-hw_bot, zb[0] + 0.03)]
        secs.append(np.array([(p[0], y, p[1]) for p in pts]))
    V, F = closed_loft(np.array(secs))
    B.add(V, F, 2)
    # carbon skin over the waterfall and the shifter / cup holder area (8 mm, follows the top)
    path = np.array([(0.0, y, console_top(y) + 0.0045) for y in np.linspace(-0.105, 0.540, 40)])
    V, F = sweep(path, superellipse(0.0045, (it.CONSOLE_W - 0.014) / 2, 6.0, 28), up=(0, 0, 1))
    B.add(V, F, 13)
    for (cx, cy) in it.CUPHOLDERS:
        z = console_top(cy) + 0.0092
        V, F, UV = disc((cx, cy, z), (0, 0, 1), 0.040, n=40)
        B.add(V, F, 14, uv=UV)
        V, F = lathe([(0.0, 0.0400), (0.002, 0.0415), (0.0, 0.0430)], (cx, cy, z), (0, 0, 1), n=40)
        B.add(V, F, 7)
    # shifter gate: dark recess plate + boot
    sx, sy, sz = it.SHIFTER
    z = console_top(sy) + 0.0095
    V, F = rounded_box((sx, sy - 0.02, z - 0.001), (0.10, 0.17, 0.004), 0.015)
    B.add(V, F, 14)
    V, F = lathe([(0.0, 0.045), (0.010, 0.040), (0.030, 0.028), (0.045, 0.016), (0.050, 0.0)], (sx, sy, z), (0, 0, 1), n=32)
    B.add(V, F, 14)
    # switch bank on the waterfall: panel, volume / tuner knobs, buttons (hazard red)
    yb = it.SWITCH_BANK_Y
    us = _unit((0.0, 0.545 - 0.34, 0.738 - 0.592))           # up the slope
    ns = np.array([0.0, -us[2], us[1]])                       # slope normal (up / back)
    cb = np.array([0.0, yb, console_top(yb)]) + ns * 0.012
    V, F = rounded_box(cb, (0.188, 0.105, 0.010), 0.012, axes=[(1, 0, 0), us, ns])
    B.add(V, F, 14)
    for sx_ in (-1, 1):
        V, F = lathe([(0.0, 0.021), (0.016, 0.021), (0.019, 0.018), (0.019, 0.0)], cb + ns * 0.005 + np.array([sx_ * 0.071, 0, 0]),
                     ns, n=32)
        B.add(V, F, 7)
    for k in range(4):
        for row in (-1, 1):
            p = cb + ns * 0.006 + np.array([-0.0285 + k * 0.019, 0, 0]) + us * row * 0.022
            V, F = rounded_box(p, (0.016, 0.017, 0.005), 0.003, axes=[(1, 0, 0), us, ns])
            B.add(V, F, 20 if (k == 1 and row == 1) else 2)
    return B


def console_top(y):
    ys, zs = zip(*it.CONSOLE_TOP)
    return float(np.interp(y, ys, zs))


def shifter():
    """Pistol-grip selector lever with a chrome release button. Slots 0, 3."""
    B = Builder()
    sx, sy, _ = it.SHIFTER
    z0 = console_top(sy) + 0.004
    path = np.array([(sx, sy, z0), (sx, sy - 0.004, z0 + 0.036), (sx, sy - 0.018, z0 + 0.066), (sx, sy - 0.045, z0 + 0.086),
                     (sx, sy - 0.085, z0 + 0.092)])
    sc = np.array([[0.9, 0.9], [1.0, 1.0], [1.15, 1.2], [1.25, 1.35], [1.1, 1.2]])
    path = resample(_chaikin(path, 2, closed=False), 20)
    scale = np.c_[np.interp(np.linspace(0, 1, 20), np.linspace(0, 1, 5), sc[:, 0]),
                  np.interp(np.linspace(0, 1, 20), np.linspace(0, 1, 5), sc[:, 1])]
    V, F = sweep(path, superellipse(0.015, 0.020, 2.6, 20), up=(1, 0, 0), scale=scale)
    B.add(V, F, 0)
    V, F = rounded_box((sx, sy - 0.078, z0 + 0.108), (0.012, 0.026, 0.008), 0.003)
    B.add(V, F, 3)
    return B


def armrest():
    """Console lid / arm rest with stitched top edge. Slots 0, 4."""
    B = Builder()
    a = it.ARMREST
    yc = (a["y0"] + a["y1"]) / 2
    L = abs(a["y1"] - a["y0"])
    V, F = rounded_box((0.0, yc, a["z"] - 0.042), (a["w"], L, 0.086), 0.028)
    B.add(V, F, 0)
    from .meshkit import rounded_rect
    loop = rounded_rect(a["w"] - 0.030, L - 0.030, 0.02, 8)
    path = np.array([(p[0], yc + p[1], a["z"] + 0.0005) for p in loop])
    path = resample(path, 140, closed=True)
    V, F = stitches(np.vstack([path, path[:1]]), lambda p: (0, 0, 1))
    B.add(V, F, 4)
    return B


# ------------------------------------------------------------------------------------------------
# glove box, outer vents, pedals, mirror, visors, frit
# ------------------------------------------------------------------------------------------------
def dash_extras():
    """Glove box lid and the two outer vents on the dash face. Slots 12, 2, 7, 14, 25."""
    B = Builder()
    R = np.array([1.0, 0, 0])
    # glove box lid on the lower face (face tilt ~14 deg there)
    a = math.radians(14.0)
    n = np.array([0.0, -math.cos(a), math.sin(a)])
    up = np.array([0.0, math.sin(a), math.cos(a)])
    V, F = rounded_box((0.405, 0.571, 0.668), (0.40, 0.012, 0.150), 0.012, axes=[R, n, up])
    B.add(V, F, 12)
    V, F = rounded_box((0.405, 0.564, 0.722), (0.10, 0.008, 0.018), 0.003, axes=[R, n, up])
    B.add(V, F, 7)
    # outer vents on the upper face (tilt ~3 deg), on its surface at y = 0.602
    a = math.radians(3.0)
    n = np.array([0.0, -math.cos(a), math.sin(a)])
    up = np.array([0.0, math.sin(a), math.cos(a)])
    for sx in (-1, 1):
        B.merge(vent(np.array([sx * 0.665, 0.6015, 0.905]), R, up, n, 0.105, 0.072, slats=4))
    return B


def pedal_frames():
    """{name: (pivot, axis)}: rotation about the car's +x axis (positive = pedal pushed forward)."""
    py, pz = it.PEDAL_PIVOT_YZ
    return {k: (np.array([p["x"], py, pz]), np.array([1.0, 0.0, 0.0])) for k, p in it.PEDALS.items()}


def pedal_mesh(name):
    """Pedal arm + pad in car coordinates (origin moved to the pivot by the caller). Slots 2, 23, 7."""
    B = Builder()
    p = it.PEDALS[name]
    py, pz = it.PEDAL_PIVOT_YZ
    x = p["x"]
    yc, zc = p["pad_yz"]
    tilt = math.radians(62.0 if name == "accelerator" else 72.0)
    up = np.array([0.0, math.cos(tilt), math.sin(tilt)])
    nrm = np.array([0.0, -math.sin(tilt), math.cos(tilt)])
    pad_c = np.array([x, yc, zc])
    V, F = rounded_box(pad_c, (p["pad_w"], p["pad_h"], 0.014), 0.006, axes=[[1, 0, 0], up, nrm])
    B.add(V, F, 23)
    if name == "brake":
        V, F = rounded_box(pad_c + nrm * 0.0075, (p["pad_w"] - 0.012, p["pad_h"] - 0.012, 0.002), 0.003,
                           axes=[[1, 0, 0], up, nrm])
        B.add(V, F, 7)
    top = pad_c + up * (p["pad_h"] / 2) - nrm * 0.006
    path = np.array([np.array([x, py, pz]), (np.array([x, py, pz]) + top) / 2 + [0, 0.02, 0.02], top])
    V, F = sweep(resample(_chaikin(path, 2, closed=False), 12), superellipse(0.007, 0.012, 2.4, 10), up=(1, 0, 0))
    B.add(V, F, 2)
    V, F = rounded_box((x, py, pz), (0.030, 0.035, 0.035), 0.008)
    B.add(V, F, 2)
    return B


def footrest():
    B = Builder()
    f = it.FOOTREST
    a = math.radians(50.0)
    up = np.array([0.0, math.cos(a), math.sin(a)])
    nrm = np.array([0.0, -math.sin(a), math.cos(a)])
    V, F = rounded_box((f["x"], f["yz"][0], f["yz"][1]), (0.075, 0.22, 0.016), 0.006, axes=[[1, 0, 0], up, nrm])
    B.add(V, F, 23)
    return B


def mirror_frame():
    m = _vec(it.MIRROR)
    to_eye = _unit(_vec(it.EYE) - m)
    nrm = _unit(to_eye + np.array([0.0, -1.0, 0.0]))            # bisects eye and rear view
    up = _unit(np.array([0, 0, 1.0]) - nrm * nrm[2])
    right = np.cross(up, nrm)
    return m, right, up, nrm


def interior_mirror():
    """Rear-view mirror: stem to the windshield, housing, glass (Unity: render texture). Slots 2, 22."""
    B = Builder()
    m, R, U, n = mirror_frame()
    V, F = rounded_box(m - n * 0.006, (0.250, 0.068, 0.032), 0.020, axes=[R, U, n])
    B.add(V, F, 2)
    V, F, UV = quad(m + n * 0.0105, R, U, 0.232, 0.052)
    B.add(V, F, 22, uv=UV)
    stem = np.array([m - n * 0.02 + U * 0.02, m + np.array([0, -0.004, 0.030]), m + np.array([0, -0.006, 0.040])])
    V, F = sweep(resample(stem, 6), superellipse(0.008, 0.008, 2.0, 10), up=(1, 0, 0))
    B.add(V, F, 2)
    return B


def sun_visors(G_head):
    """Two visors folded flat under the headliner. Slot 8 (fabric), 2 (hinge)."""
    B = Builder()
    for sx in (-1, 1):
        xc = sx * 0.355
        yc = sum(it.VISOR_Y) / 2
        sel = (np.abs(G_head[..., 0] - xc) < 0.04) & (np.abs(G_head[..., 1] - yc) < 0.05)
        zc = float(np.nanmin(G_head[..., 2][sel])) - 0.028
        V, F = rounded_box((xc, yc, zc), (0.345, abs(it.VISOR_Y[1] - it.VISOR_Y[0]), 0.026), 0.012)
        B.add(V, F, 8)
        V, F = rounded_box((sx * 0.17, yc + 0.06, zc + 0.016), (0.022, 0.022, 0.012), 0.005)
        B.add(V, F, 2)
    return B


def windshield_frit():
    """Black ceramic band on the inside of the windshield and rear glass: the border cells of the
    glass patches, 5 mm inside the outer surface (behind the 4.5 mm glass). Slot 24."""
    from .body import model
    from .gh_panels import glass_patch
    from .ikit import offset_surface_grid
    B = Builder()
    m = model()
    for which, widths in (("front", (0.075, 0.045, 0.095)), ("rear", (0.050, 0.040, 0.060))):
        G = glass_patch(m, which)          # (nu, nv, 3) right half; i along x from the centreline
        Go, N = offset_surface_grid(G, 1.0)
        nu, nv = G.shape[:2]
        # outward = away from the cabin: the glass faces up / forward (front) or up / back (rear)
        ref = np.array([0.0, 1.0 if which == "front" else -1.0, 1.0])
        sgn = 1.0 if np.sum(N * ref) > 0 else -1.0
        Gi = G - sgn * N * 0.0060          # 1.5 mm inside the glass's inner face
        # distance (m) of every grid node to the outer border (top row, bottom row, outer column)
        du = np.linalg.norm(np.diff(G, axis=0), axis=-1)
        dv = np.linalg.norm(np.diff(G, axis=1), axis=-1)
        su = np.vstack([np.zeros((1, nv)), np.cumsum(du, axis=0)])      # from the centreline column
        sv = np.hstack([np.zeros((nu, 1)), np.cumsum(dv, axis=1)])
        d_out = su[-1:, :] - su
        d_lo, d_hi = sv, sv[:, -1:] - sv
        lo_w, side_w, hi_w = widths
        inband = (d_out < side_w) | (d_lo < lo_w) | (d_hi < hi_w)
        # not in the lower outer corner, where the glass dips under the pillar base (the pillar trim
        # and the dash end cover it from inside)
        ii, jj = np.meshgrid(np.linspace(0, 1, nu), np.linspace(0, 1, nv), indexing="ij")
        inband &= ~((ii > 0.80) & (jj < 0.35))
        V = Gi.reshape(-1, 3)
        F = []
        for i in range(nu - 1):
            for j in range(nv - 1):
                if inband[i, j] and inband[i + 1, j] and inband[i + 1, j + 1] and inband[i, j + 1]:
                    F.append([i * nv + j, (i + 1) * nv + j, (i + 1) * nv + j + 1, i * nv + j + 1])
        F = tr._orient(V, F, -sgn * N.reshape(-1, 3)[F[len(F) // 2][0]])
        used = np.unique(np.array(F).ravel())
        remap = -np.ones(len(V), int)
        remap[used] = np.arange(len(used))
        Vr = V[used]
        Fr = [[int(remap[k]) for k in f] for f in F]
        half = Builder().add(Vr, Fr, 24)
        B.merge(half)
        B.merge(half.mirrored_x())
    return B


# ------------------------------------------------------------------------------------------------
# build
# ------------------------------------------------------------------------------------------------
SHELL_PARTS = ("CH_Roof", "CH_Pillars_L", "CH_Pillars_R", "CH_Glass_Windshield", "CH_Glass_Rear", "CH_Glass_Door_L",
               "CH_Glass_Door_R", "CH_Glass_Quarter_L", "CH_Glass_Quarter_R", "CH_Quarter_L", "CH_Quarter_R",
               "CH_Door_L", "CH_Door_R", "CH_Cowl", "CH_WheelLiners_L", "CH_WheelLiners_R", "CH_Fender_L", "CH_Fender_R",
               "CH_Hood")


def _object(name, Bld, col, mats, smooth_deg=40.0, origin=None, basis=None):
    """Builder -> Blender object (material slots compacted to the used ones). origin / basis: the
    object's transform (the builder's coordinates are local to it when basis is given, else world)."""
    from mathutils import Matrix
    from .ikit import to_blender_poly
    V, F, M, UV = Bld.arrays()
    used = sorted(set(M))
    slot_of = {s: k for k, s in enumerate(used)}
    if origin is not None and basis is None:
        V = V - np.asarray(origin)
    o = to_blender_poly(name, V, F, col=col, mats=[mats[s] for s in used], mat_idx=[slot_of[m] for m in M], uv=UV,
                        smooth_deg=smooth_deg)
    if origin is not None:
        Mx = np.eye(4)
        if basis is not None:
            Mx[:3, :3] = np.stack(basis, axis=1)
        Mx[:3, 3] = origin
        o.matrix_world = Matrix(Mx.tolist())
    return o


def _box_uv_keep_decals(o, box_uv):
    """World-metre box UVs on every face except those of decal materials (texture, no tiling)."""
    me = o.data
    layer = me.uv_layers.get("UVMap")
    keep = None
    if layer is not None:
        keep = np.empty(len(me.loops) * 2, np.float32)
        layer.data.foreach_get("uv", keep)
    box_uv(o)
    decal = [k for k, m in enumerate(me.materials) if m and m.get("hc_texture") and not m.get("hc_tiles_per_m")]
    if keep is None or not decal:
        return
    mi = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", mi)
    lt = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_total", lt)
    loop_dec = np.repeat(np.isin(mi, decal), lt)
    new = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers["UVMap"].data.foreach_get("uv", new)
    new = new.reshape(-1, 2)
    new[loop_dec] = keep.reshape(-1, 2)[loop_dec]
    me.uv_layers["UVMap"].data.foreach_set("uv", new.ravel())


def build_interior():
    """Whole interior from the tables into collection Car_Interior (about 30 s)."""
    import bpy
    from .assemble import _box_uv
    from .blend_util import collection
    t0 = time.time()
    col = collection("Car_Interior")
    for o in list(col.all_objects):
        bpy.data.objects.remove(o, do_unlink=True)
    mats = materials()
    shell = tr.Shell(SHELL_PARTS)
    made = []

    def add(name, Bld, smooth=40.0, **kw):
        o = _object(name, Bld, col, mats, smooth, **kw)
        made.append(o)
        return o

    add("CH_Int_Dash", dashboard(shell))
    add("CH_Int_ClusterHood", cluster_hood())
    add("CH_Int_Cluster", cluster(), smooth=35.0)
    nf = needle_frames()
    for key, (piv, R, U, A) in nf.items():
        add(f"CH_Int_Needle_{key.capitalize()}", needle_mesh(), smooth=None, origin=piv, basis=(R, U, A))
    C, X, U, A = wheel_frame()
    add("CH_Int_SteeringWheel", steering_wheel(), smooth=38.0, origin=C, basis=(X, U, A))
    add("CH_Int_SteeringColumn", steering_column())
    add("CH_Int_CentreStack", centre_stack(), smooth=35.0)
    add("CH_Int_Console", console())
    add("CH_Int_Shifter", shifter())
    add("CH_Int_Armrest", armrest())
    add("CH_Int_DashExtras", dash_extras(), smooth=35.0)
    for k, (piv, ax) in pedal_frames().items():
        add(f"CH_Int_Pedal_{k.capitalize()}", pedal_mesh(k), origin=piv)
    add("CH_Int_Footrest", footrest())
    add("CH_Int_Mirror", interior_mirror())
    seat_l = tr.front_seat(-1)
    add("CH_Int_Seat_FL", seat_l)
    add("CH_Int_Seat_FR", tr.front_seat(+1))
    add("CH_Int_Seat_Rear", tr.rear_seat())
    dl = tr.door_card(shell, -1)
    add("CH_Int_DoorCard_L", dl)
    add("CH_Int_DoorCard_R", dl.mirrored_x())
    ql = tr.quarter_trim(shell, -1)
    add("CH_Int_QuarterTrim_L", ql, smooth=50.0)
    add("CH_Int_QuarterTrim_R", tr.quarter_trim(shell, +1), smooth=50.0)
    bl = tr.b_pillar_trim(-1)
    add("CH_Int_BPillar_L", bl)
    add("CH_Int_BPillar_R", bl.mirrored_x())
    al = tr.a_pillar_trim(shell, -1)
    add("CH_Int_APillar_L", al)
    add("CH_Int_APillar_R", al.mirrored_x())
    hb, G_head = tr.headliner(shell)
    add("CH_Int_Headliner", hb, smooth=60.0)
    add("CH_Int_SunVisors", sun_visors(G_head))
    add("CH_Int_Carpet", tr.carpet(), smooth=60.0)
    sl = tr.sills_and_kicks(-1)
    add("CH_Int_Sill_L", sl)
    add("CH_Int_Sill_R", sl.mirrored_x())
    add("CH_Int_PackageShelf", tr.package_shelf())
    add("CH_Int_Belts", tr.belts())
    add("CH_Glass_Frit", windshield_frit(), smooth=None)
    # box UVs in metres for tiled materials; decal faces (dials, screens, badges) keep their own UVs
    for o in made:
        _box_uv_keep_decals(o, _box_uv)
    pose_cockpit()            # parked: needles on zero, wheel straight, pedals up
    tris = 0
    for o in made:
        o.data.calc_loop_triangles()
        tris += len(o.data.loop_triangles)
    return {"objects": len(made), "triangles": tris, "seconds": round(time.time() - t0, 1)}


def pose_cockpit(rpm=0.0, mph=0.0, steer_deg=0.0, throttle=0.0, brake=0.0):
    """Pose the animated parts for test renders: needles to the gauge values (clockwise as seen by the
    driver), steering wheel turned by steer_deg (positive = clockwise = right), pedals pressed (0..1)."""
    import bpy
    from mathutils import Matrix
    out = {}
    for key, (piv, R, U, A) in needle_frames().items():
        o = bpy.data.objects.get(f"CH_Int_Needle_{key.capitalize()}")
        if o is None:
            continue
        ang = it.gauge_angle(key, rpm if key == "tach" else mph)
        Mx = np.eye(4)
        Mx[:3, :3] = np.stack((R, U, A), axis=1)
        Mx[:3, 3] = piv
        o.matrix_world = Matrix(Mx.tolist()) @ Matrix.Rotation(math.radians(-ang), 4, "Z")
        out[key] = ang
    C, X, U, A = wheel_frame()
    o = bpy.data.objects.get("CH_Int_SteeringWheel")
    if o is not None:
        Mx = np.eye(4)
        Mx[:3, :3] = np.stack((X, U, A), axis=1)
        Mx[:3, 3] = C
        o.matrix_world = Matrix(Mx.tolist()) @ Matrix.Rotation(math.radians(-steer_deg), 4, "Z")
    for k, (piv, ax) in pedal_frames().items():
        o = bpy.data.objects.get(f"CH_Int_Pedal_{k.capitalize()}")
        if o is None:
            continue
        val = throttle if k == "accelerator" else brake
        Mx = np.eye(4)
        Mx[:3, 3] = piv
        o.matrix_world = Matrix(Mx.tolist()) @ Matrix.Rotation(math.radians(-it.PEDALS[k]["travel_deg"] * val), 4, "X")
    return out


def export_cockpit(path=None):
    """Cockpit description for Unity (car frame, Blender axes: x right, y forward, z up; metres)."""
    path = path or os.path.join(PROJECT_ROOT, "sim", "vehicle", "hellcat", "cockpit.json")
    C, X, U, A = wheel_frame()
    m, mr, mu, mn = mirror_frame()
    sc, sR, sU, sn = stack_frame()
    eye = _vec(it.EYE)
    c = _vec(it.CLUSTER_CENTRE)
    axis_c = _unit(eye - c)
    up_c = _unit(np.array([0, 0, 1.0]) - axis_c * axis_c[2])
    data = {
        "frame": "car frame, Blender axes (x right, y forward, z up), metres; Unity: (x, z, y)",
        "eye": eye.tolist(), "fov_h_deg": it.FOV_H_DEG,
        "steering_wheel": {"object": "CH_Int_SteeringWheel", "centre": C.tolist(), "axis_to_driver": A.tolist(),
                           "up": U.tolist(), "lock_to_lock_turns": it.STEER_LOCK_TO_LOCK_TURNS,
                           "positive": "clockwise as seen by the driver = steering right"},
        "needles": {k: {"object": f"CH_Int_Needle_{k.capitalize()}", "pivot": p.tolist(), "axis_to_eye": a.tolist(),
                        "rest_points_to": u.tolist(), "gauge": it.GAUGES[k]} for k, (p, r, u, a) in needle_frames().items()},
        "pedals": {k: {"object": f"CH_Int_Pedal_{k.capitalize()}", "pivot": p.tolist(), "axis": ax.tolist(),
                       "travel_deg": it.PEDALS[k]["travel_deg"], "positive": "pressed = rotation by -travel about +x"}
                   for k, (p, ax) in pedal_frames().items()},
        "interior_mirror": {"object": "CH_Int_Mirror", "centre": m.tolist(), "normal": mn.tolist(), "right": mr.tolist(),
                            "up": mu.tolist(), "glass_size": [0.232, 0.052]},
        "side_mirrors": {"left": "CH_Mirror_Glass_L", "right": "CH_Mirror_Glass_R"},
        "cluster_display": {"centre": (c - axis_c * 0.004).tolist(), "normal": axis_c.tolist(), "up": up_c.tolist(),
                            "size": [it.DISPLAY_W, it.DISPLAY_H], "material": "CH_Int_ClusterDisplay"},
        "touchscreen": {"centre": (sc + sn * 0.0222).tolist(), "normal": sn.tolist(), "up": sU.tolist(),
                        "size": [it.SCREEN_W, it.SCREEN_H], "material": "CH_Int_Touchscreen"},
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    return {"json": path}
