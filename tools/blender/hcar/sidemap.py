"""Mapping between design coordinates and strip parameters (pure numpy).

Panel cut lines are designed in view coordinates: side view (y, z) on the right side of the car,
front/rear views (x, z). These helpers find the strip parameters (s, t) of the surface point that
has those coordinates (Newton iterations on s, monotone section inversion for t).
"""
import numpy as np


def t_of_z(st, s, z, t_lo=0.0, t_hi=1.0):
    """t on the section at s where the section height equals z (z increases with t on [t_lo, t_hi])."""
    sec = st.section(s)
    t, p = sec["t"], sec["p"]
    m = (t >= t_lo) & (t <= t_hi)
    tt, zz = t[m], p[m, 1]
    zz = np.maximum.accumulate(zz)   # guard against tiny non-monotone wiggles
    return float(np.interp(z, zz, tt))


def side_param(st, y, z, t_lo=0.0, t_hi=0.93, iters=4):
    """(s, t) of the surface point with world y and height z on the right side."""
    s = st.O.s_side_y(y)
    for _ in range(iters):
        t = t_of_z(st, s, z, t_lo, t_hi)
        P = st.point(np.array([s]), np.array([t]))[0]
        P2 = st.point(np.array([s + 1e-3]), np.array([t]))[0]
        dyds = (P2[1] - P[1]) / 1e-3
        if abs(dyds) < 1e-6:
            break
        s = float(np.clip(s + (y - P[1]) / dyds, 0.0, st.O.S))
    return s, t_of_z(st, s, z, t_lo, t_hi)


def face_param(st, x, z, face, t_lo=0.0, t_hi=0.93, iters=4):
    """(s, t) of the surface point with world x and height z on the front or rear face."""
    s = st.O.s_face_x(x, face)
    for _ in range(iters):
        t = t_of_z(st, s, z, t_lo, t_hi)
        P = st.point(np.array([s]), np.array([t]))[0]
        P2 = st.point(np.array([s + 1e-3]), np.array([t]))[0]
        dxds = (P2[0] - P[0]) / 1e-3
        if abs(dxds) < 1e-6:
            break
        s = float(np.clip(s + (x - P[0]) / dxds, 0.0, st.O.S))
    return s, t_of_z(st, s, z, t_lo, t_hi)


def side_curve(st, yz, n=None, **kw):
    """Parameter curve (m, 2) for a side-view polyline (y, z) (resampled to n points if given)."""
    yz = np.asarray(yz, float)
    if n is not None:
        from .geom import resample
        yz = resample(yz, n)
    return np.array([side_param(st, y, z, **kw) for y, z in yz])


def face_curve(st, xz, face, n=None, **kw):
    xz = np.asarray(xz, float)
    if n is not None:
        from .geom import resample
        xz = resample(xz, n)
    return np.array([face_param(st, x, z, face, **kw) for x, z in xz])


def iso_t(s0, s1, t, n=64):
    return np.stack([np.linspace(s0, s1, n), np.full(n, t)], axis=1)


def iso_s(s, t0, t1, n=64):
    return np.stack([np.full(n, s), np.linspace(t0, t1, n)], axis=1)
