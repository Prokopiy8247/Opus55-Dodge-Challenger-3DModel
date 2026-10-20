"""Widebody fender flares as displaced panels on the body strip (pure numpy)."""
import math

import numpy as np

from . import body_tables as bt
from .caps import table_fn
from .panels import Panel, StripSurface
from .sidemap import side_curve


def _polar_curve(f, r_of_theta, thetas):
    th = np.radians(thetas)
    r = r_of_theta(thetas)
    return np.stack([f["y"] + r * np.cos(th), f["z"] + r * np.sin(th)], axis=1)


def flare_panel(strip, key, n=48, edge=0.022):
    f = bt.FLARES[key]
    band = table_fn(f["band"])
    t0, t1 = f["theta"]
    th = np.linspace(t1, t0, n)                 # rear end -> over the top -> front end (s increasing)
    lip = _polar_curve(f, lambda t: np.full_like(np.asarray(t, float), f["lip_r"]), th)
    seam = _polar_curve(f, lambda t: f["lip_r"] + band(t), th)
    ends = []
    for tt in (t1, t0):
        rr = np.linspace(f["lip_r"], f["lip_r"] + float(band(tt)), 8)
        a = math.radians(tt)
        ends.append(np.stack([f["y"] + rr * math.cos(a), f["z"] + rr * math.sin(a)], axis=1))
    surf = StripSurface(strip)
    kw = dict(t_lo=0.0, t_hi=0.75)
    c_bot = side_curve(strip, lip, **kw)
    c_top = side_curve(strip, seam, **kw)
    c_left = side_curve(strip, ends[0], **kw)
    c_right = side_curve(strip, ends[1], **kw)
    for c in (c_bot, c_top, c_left, c_right):
        c[:, 1] = np.maximum(c[:, 1], 0.0)
    H = f["height"]

    def offset(a, b):
        P = surf.P(a, b)
        dy = P[..., 1] - f["y"]
        dz = P[..., 2] - f["z"]
        r = np.hypot(dy, dz)
        theta = np.degrees(np.arctan2(dz, dy))
        theta = np.where(theta < t0 - 5, theta + 360.0, theta)
        u = np.clip((f["lip_r"] + band(theta) - r) / band(theta), 0.0, 1.0)   # 0 at the seam, 1 at the lip
        return H * u * u * (3 - 2 * u) + 0.0015   # small step at the seam
    return Panel(f"CH_Flare_{key}", surf, c_bot, c_right, c_top, c_left, edge=edge, gap=0.0,
                 flange=(0.008, 0.045), offset=offset)
