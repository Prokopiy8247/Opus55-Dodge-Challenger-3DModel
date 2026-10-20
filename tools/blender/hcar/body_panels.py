"""Panels of the body strip (right side): door, front fender, quarter panel, rocker.

Cut lines come from body_tables.CUTS (side view y, z) and the flare seams (body_tables.FLARES);
they are converted to strip parameters (s, t) and every panel is a panels.Panel.
"""
import math

import numpy as np

from . import body_tables as bt
from .caps import table_fn
from .panels import Panel, StripSurface
from .shape import KNOTS
from .sidemap import face_curve, side_curve, side_param

CREASES = [KNOTS[2], KNOTS[4]]   # character line and shoulder crease


def flare_seam_yz(key, th0=None, th1=None, n=60):
    """Seam (outer edge) of a flare in side view, from angle th0 to th1 (deg)."""
    f = bt.FLARES[key]
    band = table_fn(f["band"])
    a0, a1 = f["theta"]
    th = np.linspace(a0 if th0 is None else th0, a1 if th1 is None else th1, n)
    r = f["lip_r"] + band(th)
    return np.stack([f["y"] + r * np.cos(np.radians(th)), f["z"] + r * np.sin(np.radians(th))], axis=1)


def seam_angle_at_z(key, z, rear_side):
    """Angle where the flare seam crosses height z on the rear (theta > 90) or front side."""
    f = bt.FLARES[key]
    a0, a1 = f["theta"]
    th = np.linspace(90, a1, 2000) if rear_side else np.linspace(90, a0, 2000)
    yz = flare_seam_yz(key, th[0], th[-1], len(th))
    i = int(np.argmin(np.abs(yz[:, 1] - z)))
    return float(th[i])


def seam_angle_at_point(key, y, z):
    """Angle of the flare seam point closest to (y, z)."""
    f = bt.FLARES[key]
    yz = flare_seam_yz(key, n=3000)
    i = int(np.argmin(np.hypot(yz[:, 0] - y, yz[:, 1] - z)))
    a0, a1 = f["theta"]
    return float(np.linspace(a0, a1, 3000)[i])


def _pc(st, yz, t_hi=1.0, force_top=False):
    c = side_curve(st, np.asarray(yz, float), t_lo=0.0, t_hi=t_hi)
    if force_top:
        c[-1, 1] = 1.0
    return c


def _top(st, s0, s1, n=80):
    return np.stack([np.linspace(s0, s1, n), np.ones(n)], axis=1)


def _bottom_t0(st, s0, s1, n=80):
    return np.stack([np.linspace(s0, s1, n), np.zeros(n)], axis=1)


def side_panels(m, edge=0.025, gap=0.005):
    st = m["strip"]
    surf = StripSurface(st)
    C = bt.CUTS
    out = {}
    z_sill_f, z_sill_r = C["door_bottom_z"]
    # ---------------- door
    front = _pc(st, C["door_front"], force_top=True)
    rear = _pc(st, C["door_rear"], force_top=True)
    bottom = _pc(st, [C["door_rear"][0], C["door_front"][0]])
    top = _top(st, rear[-1, 0], front[-1, 0])
    out["CH_Door"] = Panel("CH_Door", surf, bottom, front, top, rear, creases=CREASES, edge=edge, gap=gap)
    # ---------------- front fender: bottom = sill line + flare seam (rear end -> fascia seam)
    th_sill = seam_angle_at_z("front", z_sill_f, rear_side=True)
    y_sill = flare_seam_yz("front", th_sill, th_sill, 1)[0, 0]
    fs = C["fascia_seam"]
    th_fs = seam_angle_at_point("front", *fs[0])
    seam = flare_seam_yz("front", th_sill, th_fs, 70)
    sill = np.array([C["door_front"][0], (y_sill, z_sill_f)])
    bottom = _pc(st, np.vstack([sill, seam[1:]]))
    # the fascia seam starts on the flare seam (same corner as the fascia's own boundary)
    right = _pc(st, np.vstack([seam[-1:], fs[1:]]), force_top=True)
    left = front.copy()
    top = _top(st, left[-1, 0], right[-1, 0])
    out["CH_Fender"] = Panel("CH_Fender", surf, bottom, right, top, left, creases=CREASES, edge=edge, gap=gap)
    # ---------------- quarter panel: bottom = sill line (door rear cut -> rear flare seam) + seam
    th_q = seam_angle_at_z("rear", z_sill_r, rear_side=False)
    y_q = flare_seam_yz("rear", th_q, th_q, 1)[0, 0]
    bs = C["bumper_seam"]
    th_bs = seam_angle_at_point("rear", *bs[0])
    seam_r = flare_seam_yz("rear", th_bs, th_q, 70)          # rear end -> front end
    sill_r = np.array([(y_q, z_sill_r), C["door_rear"][0]])
    bottom = _pc(st, np.vstack([seam_r[:-1], sill_r]))
    left = _pc(st, np.vstack([seam_r[:1], bs[1:]]), force_top=True)   # same corner as the bumper's
    right = rear.copy()
    top = _top(st, left[-1, 0], right[-1, 0])
    out["CH_Quarter"] = Panel("CH_Quarter", surf, bottom, right, top, left, creases=CREASES, edge=edge, gap=gap)
    # ---------------- rocker (sill): between the flares, from the bottom edge up to the sill line
    th_rf = bt.FLARES["rear"]["theta"][0]
    th_ff = bt.FLARES["front"]["theta"][1]
    rr = flare_seam_yz("rear", th_rf, th_q, 12)              # rear flare front end, bottom -> sill
    ff = flare_seam_yz("front", th_ff, th_sill, 12)          # front flare rear end, bottom -> sill
    left = _pc(st, rr)
    right = _pc(st, ff)
    left[0, 1] = 0.0
    right[0, 1] = 0.0
    bottom = _bottom_t0(st, left[0, 0], right[0, 0])
    top = _pc(st, [(y_q, z_sill_r), C["door_rear"][0], C["door_front"][0], (y_sill, z_sill_f)])
    out["CH_Rocker"] = Panel("CH_Rocker", surf, bottom, right, top, left, edge=edge, gap=gap)
    return out


def _hole_param(st, pts, face):
    """Opening polygon (view x, z) -> closed parameter polygon; points beyond the mirror plane are
    pushed past the strip end so the opening continues across it."""
    c = face_curve(st, pts, face, t_lo=0.0, t_hi=1.0)
    S = st.O.S
    beyond = np.array([p[0] < 0 for p in pts])
    c[beyond, 0] = (S + 0.05) if face == "front" else -0.05
    return c


def bumper_panels(m, edge=0.016, gap=0.005):
    st = m["strip"]
    surf = StripSurface(st)
    C = bt.CUTS
    S = st.O.S
    out = {}
    # ---------------- front fascia: left = front flare seam (bottom -> fascia seam) + fascia seam
    fs = C["fascia_seam"]
    th_fs = seam_angle_at_point("front", *fs[0])
    th0 = bt.FLARES["front"]["theta"][0]
    seam = flare_seam_yz("front", th0, th_fs, 30)               # bottom front end -> fascia seam
    left = _pc(st, np.vstack([seam, fs[1:]]), force_top=True)
    left[0, 1] = 0.0
    right = np.stack([np.full(80, S), np.linspace(0, 1, 80)], axis=1)
    bottom = _bottom_t0(st, left[0, 0], S)
    top = _top(st, left[-1, 0], S)
    holes = [_hole_param(st, h, "front") for h in bt.FASCIA_HOLES.values()]
    # each opening's return flange is a tunnel down to its back plate (the plug, Panel.plugs)
    hfl = [(0.003, bt.OPENING_DEPTH[k]) for k in bt.FASCIA_HOLES]
    out["CH_Fascia"] = Panel("CH_Fascia", surf, bottom, right, top, left, creases=[KNOTS[4]], edge=edge,
                             gap=gap, inset=dict(right=False), holes=holes, hole_flange=hfl)
    # ---------------- rear bumper cover: right = rear flare seam (bottom rear end -> bumper seam) + seam
    bs = C["bumper_seam"]
    th_bs = seam_angle_at_point("rear", *bs[0])
    th1 = bt.FLARES["rear"]["theta"][1]
    seam_r = flare_seam_yz("rear", th1, th_bs, 30)             # bottom rear end -> bumper seam
    right = _pc(st, np.vstack([seam_r, bs[1:]]), force_top=True)
    right[0, 1] = 0.0
    left = np.stack([np.zeros(80), np.linspace(0, 1, 80)], axis=1)
    bottom = _bottom_t0(st, 0.0, right[0, 0])
    top = _top(st, 0.0, right[-1, 0])
    holes = [_hole_param(st, h, "rear") for h in bt.REAR_HOLES.values()]
    hfl = [(0.003, bt.OPENING_DEPTH[k]) for k in bt.REAR_HOLES]
    out["CH_RearBumper"] = Panel("CH_RearBumper", surf, bottom, right, top, left, edge=edge, gap=gap,
                                 inset=dict(left=False), holes=holes, hole_flange=hfl)
    return out
