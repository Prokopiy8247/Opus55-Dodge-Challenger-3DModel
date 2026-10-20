"""Small numeric helpers for the parametric body (pure numpy; runs in Blender and in tools/.venv).

Splines
  CSpline(x, y)      C2 cubic spline (not-a-knot ends unless clamped slopes are given); y may be (n,) or (n, k)
  Pchip(x, y)        monotone C1 cubic (Fritsch-Carlson), no overshoot
Curves
  bezier(p0, p1, p2, p3, n)          sampled cubic Bezier
  polyline_arclen(p)                 cumulative arc length
  resample(p, n) / resample_at(p, u) arc-length resampling
  fillet_corner(a, k, b, r)          replace a polyline corner by a circular arc
"""
import math

import numpy as np


def _as2d(y):
    y = np.asarray(y, dtype=float)
    return (y[:, None], True) if y.ndim == 1 else (y, False)


class CSpline:
    """Cubic spline through (x_i, y_i). bc: 'natural', 'notaknot' or (slope_start, slope_end) arrays."""

    def __init__(self, x, y, bc="notaknot"):
        x = np.asarray(x, dtype=float)
        y, self._flat = _as2d(y)
        n = len(x)
        if n < 2:
            raise ValueError("need 2+ points")
        if np.any(np.diff(x) <= 0):
            raise ValueError("x must increase")
        self.x, self.y = x, y
        h = np.diff(x)
        k = y.shape[1]
        if n == 2:
            m = np.zeros((2, k))
        elif n == 3 and isinstance(bc, str) and bc == "notaknot":
            # parabola through 3 points
            m = np.zeros((3, k))
            d = np.diff(y, axis=0) / h[:, None]
            c2 = (d[1] - d[0]) / (x[2] - x[0])
            m[:] = 2 * c2
        else:
            A = np.zeros((n, n))
            r = np.zeros((n, k))
            d = np.diff(y, axis=0) / h[:, None]
            for i in range(1, n - 1):
                A[i, i - 1] = h[i - 1]
                A[i, i] = 2 * (h[i - 1] + h[i])
                A[i, i + 1] = h[i]
                r[i] = 6 * (d[i] - d[i - 1])
            if isinstance(bc, str) and bc == "natural":
                A[0, 0] = A[-1, -1] = 1.0
            elif isinstance(bc, str) and bc == "notaknot":
                A[0, 0], A[0, 1], A[0, 2] = h[1], -(h[0] + h[1]), h[0]
                A[-1, -3], A[-1, -2], A[-1, -1] = h[-1], -(h[-2] + h[-1]), h[-2]
            else:
                s0, s1 = (np.broadcast_to(np.asarray(v, float), (k,)) for v in bc)
                A[0, 0], A[0, 1] = 2 * h[0], h[0]
                r[0] = 6 * (d[0] - s0)
                A[-1, -2], A[-1, -1] = h[-1], 2 * h[-1]
                r[-1] = 6 * (s1 - d[-1])
            m = np.linalg.solve(A, r)
        self.m = m  # second derivatives at the knots

    def __call__(self, xq, der=0):
        xq = np.asarray(xq, dtype=float)
        scalar = xq.ndim == 0
        xq = np.atleast_1d(xq)
        x, y, m = self.x, self.y, self.m
        i = np.clip(np.searchsorted(x, xq) - 1, 0, len(x) - 2)
        h = (x[i + 1] - x[i])[:, None]
        a = ((x[i + 1] - xq)[:, None]) / h
        b = 1.0 - a
        if der == 0:
            v = a * y[i] + b * y[i + 1] + ((a ** 3 - a) * m[i] + (b ** 3 - b) * m[i + 1]) * h * h / 6.0
        elif der == 1:
            v = (y[i + 1] - y[i]) / h + ((1 - 3 * a * a) * m[i] + (3 * b * b - 1) * m[i + 1]) * h / 6.0
        elif der == 2:
            v = a * m[i] + b * m[i + 1]
        else:
            raise ValueError(der)
        if self._flat:
            v = v[:, 0]
        return v[0] if scalar else v


class Pchip:
    """Monotone piecewise cubic Hermite interpolation (Fritsch-Carlson); y may be (n,) or (n, k)."""

    def __init__(self, x, y):
        x = np.asarray(x, dtype=float)
        y, self._flat = _as2d(y)
        if np.any(np.diff(x) <= 0):
            raise ValueError("x must increase")
        n = len(x)
        h = np.diff(x)
        d = np.diff(y, axis=0) / h[:, None]
        m = np.zeros_like(y)
        if n == 2:
            m[:] = d[0]
        else:
            for i in range(1, n - 1):
                ok = d[i - 1] * d[i] > 0
                w1 = 2 * h[i] + h[i - 1]
                w2 = h[i] + 2 * h[i - 1]
                with np.errstate(divide="ignore", invalid="ignore"):
                    hm = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
                m[i] = np.where(ok, hm, 0.0)
            # one-sided three-point ends (shape preserving)
            for e, (i0, i1, s) in enumerate(((0, 1, 1), (n - 1, n - 2, -1))):
                h0, h1 = (h[0], h[1]) if e == 0 else (h[-1], h[-2])
                d0, d1 = (d[0], d[1]) if e == 0 else (d[-1], d[-2])
                me = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
                me = np.where(np.sign(me) != np.sign(d0), 0.0, me)
                me = np.where((np.sign(d0) != np.sign(d1)) & (np.abs(me) > 3 * np.abs(d0)), 3 * d0, me)
                m[i0] = me
        self.x, self.y, self.m = x, y, m

    def __call__(self, xq, der=0):
        xq = np.asarray(xq, dtype=float)
        scalar = xq.ndim == 0
        xq = np.atleast_1d(xq)
        x, y, m = self.x, self.y, self.m
        i = np.clip(np.searchsorted(x, xq) - 1, 0, len(x) - 2)
        h = (x[i + 1] - x[i])[:, None]
        t = ((xq - x[i])[:, None]) / h
        if der == 0:
            h00 = 2 * t ** 3 - 3 * t ** 2 + 1
            h10 = t ** 3 - 2 * t ** 2 + t
            h01 = -2 * t ** 3 + 3 * t ** 2
            h11 = t ** 3 - t ** 2
            v = h00 * y[i] + h10 * h * m[i] + h01 * y[i + 1] + h11 * h * m[i + 1]
        elif der == 1:
            d00 = (6 * t ** 2 - 6 * t) / h
            d10 = 3 * t ** 2 - 4 * t + 1
            d01 = (-6 * t ** 2 + 6 * t) / h
            d11 = 3 * t ** 2 - 2 * t
            v = d00 * y[i] + d10 * m[i] + d01 * y[i + 1] + d11 * m[i + 1]
        else:
            raise ValueError(der)
        if self._flat:
            v = v[:, 0]
        return v[0] if scalar else v


def bezier(p0, p1, p2, p3, n):
    t = np.linspace(0.0, 1.0, n)[:, None]
    u = 1.0 - t
    return u ** 3 * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t ** 3 * p3


def polyline_arclen(p):
    return np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]


def resample_at(p, u, s=None):
    """Points at normalised arc-length positions u (0..1) along polyline p."""
    if s is None:
        s = polyline_arclen(p)
    q = np.asarray(u) * s[-1]
    out = np.empty((len(np.atleast_1d(q)), p.shape[1]))
    for k in range(p.shape[1]):
        out[:, k] = np.interp(q, s, p[:, k])
    return out


def resample(p, n):
    return resample_at(p, np.linspace(0.0, 1.0, n))


def unit(v):
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.where(n == 0, 1, n)


def dir2(deg):
    a = math.radians(deg)
    return np.array([math.cos(a), math.sin(a)])


def fillet_corner(a, b, r, n=9):
    """Round the corner where polyline a (ending at the corner) meets polyline b (starting there).

    Returns (a_trimmed, arc, b_trimmed); the arc is tangent to both sides (tangent directions taken
    from the polylines near the corner). With r <= 0 or no turn the corner is kept."""
    c = a[-1]
    ta = unit(a[-1] - a[-2])
    tb = unit(b[1] - b[0])
    cosang = float(np.clip(np.dot(ta, tb), -1.0, 1.0))
    turn = math.acos(cosang)
    if r <= 0 or turn < 1e-4:
        return a, np.zeros((0, 2)), b
    L = r * math.tan(turn / 2)
    sa = polyline_arclen(a)
    sb = polyline_arclen(b)
    L = min(L, 0.45 * sa[-1], 0.45 * sb[-1])
    # trim points
    pa = resample_at(a, [(sa[-1] - L) / sa[-1]], sa)[0]
    pb = resample_at(b, [L / sb[-1]], sb)[0]
    keep_a = a[sa < sa[-1] - L]
    keep_b = b[sb > L]
    # quadratic-Bezier-like arc approximated by a circular arc through tangents at pa and pb
    ua = unit(c - pa)
    ub = unit(pb - c)
    t = np.linspace(0.0, 1.0, n)[:, None]
    # rational quadratic Bezier with weight cos(turn/2) gives an exact circle arc
    w = math.cos(turn / 2)
    num = (1 - t) ** 2 * pa + 2 * w * t * (1 - t) * c + t ** 2 * pb
    den = (1 - t) ** 2 + 2 * w * t * (1 - t) + t ** 2
    arc = num / den
    _ = ua, ub
    return np.vstack([keep_a, pa[None]]), arc, np.vstack([pb[None], keep_b])
