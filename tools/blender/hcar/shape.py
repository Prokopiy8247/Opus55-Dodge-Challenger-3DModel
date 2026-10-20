"""Parametric exterior surfaces of the Challenger body (pure numpy; runs in Blender and tools/.venv).

Frame: x right, y forward, z up, metres; origin on the ground at mid-wheelbase, centreline.
Only the right half (x >= 0) is modelled; Blender mirrors the parts.

Waist and guide outlines
    The waist is the plan-view curve of the largest half-width at any height (right half, rear
    centre -> front centre). Its corners are tight (radius about 0.1 m), smaller than the inward
    offsets of the upper key lines, so sections are not placed along the waist normals but along
    the normals of a guide outline O(s): the waist with its corners rounded to radius GUIDE_R
    (morphological opening). s is the arc length of the guide from the rear centre (s = 0) to the
    front centre (s = S); n = (t_y, -t_x) is the outward normal, its angle phi is -90 deg on the
    rear face, 0 on the side, +90 deg on the front face. w(s) >= 0 is the waist offset from the
    guide along n.

Strip P(s, t)
    The band around the car from the bottom edge (t = 0) to the top edge (t = 1, the hood, belt and
    deck-lid shut lines). Each section lies in the vertical plane through O(s) along n(s); in local
    coordinates (h = outward offset from O, z = height) it is a chain of cubic Bezier segments
    through six key points
        K0 bottom edge, K1 waist (h = w), K2 character line, K3 upper mid point,
        K4 shoulder crease, K5 top edge,
    with tangent directions on both sides of every key point (a crease when they differ, rounded by
    a fillet radius). Key point data are tabulated at anchor stations (body_tables.py) relative to
    the waist (dh = h - w) and interpolated along s. t is piecewise arc length between the key
    points, which sit at fixed knots KNOTS, so every crease is an iso-t line.
"""
import math

import numpy as np

from .geom import CSpline, Pchip, bezier, dir2, fillet_corner, polyline_arclen, unit

KNOTS = np.array([0.0, 0.58, 0.70, 0.80, 0.92, 1.0])
NKEY = len(KNOTS)


# ----------------------------------------------------------------------------------------------
# Outline
# ----------------------------------------------------------------------------------------------
def waist_polyline(pts, n_dense=6000):
    """Dense C2 spline through the waist table (clamped tangents perpendicular to the centreline)."""
    p = np.asarray(pts, dtype=float)
    if abs(p[0, 0]) > 1e-9 or abs(p[-1, 0]) > 1e-9:
        raise ValueError("outline must start and end on the centreline")
    u = polyline_arclen(p)
    sp = CSpline(u, p, bc=(np.array([1.0, 0.0]), np.array([-1.0, 0.0])))
    return sp(np.linspace(0.0, u[-1], n_dense))


def _seg_intersections(a, b):
    """First intersection between polyline pieces a[i]-a[i+1] and b[j]-b[j+1] (brute force)."""
    p, r = a[:-1], a[1:] - a[:-1]
    q, s = b[:-1], b[1:] - b[:-1]
    rxs = r[:, None, 0] * s[None, :, 1] - r[:, None, 1] * s[None, :, 0]
    qp = q[None, :, :] - p[:, None, :]
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (qp[..., 0] * s[None, :, 1] - qp[..., 1] * s[None, :, 0]) / rxs
        u = (qp[..., 0] * r[:, None, 1] - qp[..., 1] * r[:, None, 0]) / rxs
    ok = (np.abs(rxs) > 1e-15) & (t >= 0) & (t <= 1) & (u >= 0) & (u <= 1)
    idx = np.argwhere(ok)
    if len(idx) == 0:
        return None
    i, j = idx[0]
    return i, j, p[i] + t[i, j] * r[i]


def _self_intersection(c, step=6):
    """Self-intersection of polyline c with the largest index separation (the loop of an inward
    offset around a tight corner). Returns (i, j, point) with sample indices of c, or None."""
    q = c[::step]
    p, r = q[:-1], q[1:] - q[:-1]
    rxs = r[:, None, 0] * r[None, :, 1] - r[:, None, 1] * r[None, :, 0]
    qp = p[None, :, :] - p[:, None, :]
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (qp[..., 0] * r[None, :, 1] - qp[..., 1] * r[None, :, 0]) / rxs
        u = (qp[..., 0] * r[:, None, 1] - qp[..., 1] * r[:, None, 0]) / rxs
    i, j = np.meshgrid(np.arange(len(p)), np.arange(len(p)), indexing="ij")
    ok = (np.abs(rxs) > 1e-15) & (t >= 0) & (t <= 1) & (u >= 0) & (u <= 1) & (j > i + 2)
    idx = np.argwhere(ok)
    if len(idx) == 0:
        return None
    k = int(np.argmax(idx[:, 1] - idx[:, 0]))
    a, b = idx[k]
    pt = p[a] + t[a, b] * r[a]
    return a * step, b * step, pt


def guide_polyline(waist, R, smooth=0.04):
    """Waist with convex corners of curvature radius < R replaced by tangent arcs of radius R,
    then lightly smoothed (Gaussian, sigma = smooth metres) to soften the curvature steps.
    R may be a pair (rear corner, front corner)."""
    tan = unit(np.gradient(waist, axis=0))
    nrm = np.c_[tan[:, 1], -tan[:, 0]]
    Rs = tuple(R) if isinstance(R, (tuple, list)) else (R, R)
    n = len(waist)
    # look for self-intersections of the inward offset in two windows (rear and front corners)
    pieces = []
    for (lo, hi), Rw in zip(((0, n // 2), (n // 2, n)), Rs):
        off = waist - Rw * nrm
        best = _self_intersection(off[lo:hi], step=6)
        if best is not None:
            best = (lo + best[0], lo + best[1], best[2])
        if best is None:
            # no corner tighter than R in this window: keep the waist
            continue
        pieces.append(best + (Rw,))
    if not pieces:
        return waist
    res = []
    start = 0
    for i1, i2, C, R in pieces:
        off = waist - R * nrm
        # contact points: waist samples whose inward normal passes closest to C
        d1 = np.linalg.norm(off[max(i1 - 8, 0):i1 + 9] - C, axis=1)
        d2 = np.linalg.norm(off[max(i2 - 8, 0):i2 + 9] - C, axis=1)
        j1 = max(i1 - 8, 0) + int(np.argmin(d1))
        j2 = max(i2 - 8, 0) + int(np.argmin(d2))
        a1 = math.atan2(*(waist[j1] - C)[::-1])
        a2 = math.atan2(*(waist[j2] - C)[::-1])
        # walk the short way round (convex corner, counter-clockwise for this outline direction)
        da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
        k = max(int(abs(da) * R / 0.002), 8)
        ang = a1 + da * np.linspace(0, 1, k)
        arc = C + R * np.c_[np.cos(ang), np.sin(ang)]
        res.append(waist[start:j1])
        res.append(arc)
        start = j2 + 1
    res.append(waist[start:])
    g = np.vstack(res)
    # resample uniformly, Gaussian-smooth (ends pinned to the centreline), resample again
    g = _resample_uniform(g, 0.002)
    if smooth > 0:
        sig = smooth / 0.002
        r = int(3 * sig)
        ker = np.exp(-0.5 * (np.arange(-r, r + 1) / sig) ** 2)
        ker /= ker.sum()
        # mirror-extend across the centreline (x -> -x) so the ends stay perpendicular to it
        ext = np.vstack([g[1:r + 1][::-1] * [-1, 1], g, g[-r - 1:-1][::-1] * [-1, 1]])
        gs = np.stack([np.convolve(ext[:, k], ker, mode="valid") for k in range(2)], axis=1)
        gs[0, 0] = 0.0
        gs[-1, 0] = 0.0
        g = gs
    return _resample_uniform(g, 0.001)


def _resample_uniform(p, step):
    s = polyline_arclen(p)
    n = max(int(math.ceil(s[-1] / step)) + 1, 2)
    q = np.linspace(0, s[-1], n)
    return np.stack([np.interp(q, s, p[:, 0]), np.interp(q, s, p[:, 1])], axis=1)


def stadium_guide(waist, y_rear, y_front, smooth=0.04):
    """Guide made of two quarter circles centred on the centreline at y_rear and y_front (radius =
    the waist half-width there) joined by the waist's side between them. All corner sections then
    radiate from the two centres, which must lie beyond every key line (inside the roof)."""
    side = np.abs(unit(np.gradient(waist, axis=0))[:, 1]) > 0.7  # side branch: tangent mostly along y
    idx = np.where(side)[0]
    ys = waist[idx, 1]
    xr = float(np.interp(y_rear, ys, waist[idx, 0]))
    xf = float(np.interp(y_front, ys, waist[idx, 0]))
    k = np.where((waist[:, 1] > y_rear) & (waist[:, 1] < y_front) & side)[0]
    a = np.linspace(-np.pi / 2, 0.0, max(int(xr * np.pi / 2 / 0.002), 16))
    rear = np.c_[xr * np.cos(a), y_rear + xr * np.sin(a)]
    a = np.linspace(0.0, np.pi / 2, max(int(xf * np.pi / 2 / 0.002), 16))
    front = np.c_[xf * np.cos(a), y_front + xf * np.sin(a)]
    g = np.vstack([rear, waist[k], front])
    g = _resample_uniform(g, 0.002)
    if smooth > 0:
        sig = smooth / 0.002
        r = int(3 * sig)
        ker = np.exp(-0.5 * (np.arange(-r, r + 1) / sig) ** 2)
        ker /= ker.sum()
        ext = np.vstack([g[1:r + 1][::-1] * [-1, 1], g, g[-r - 1:-1][::-1] * [-1, 1]])
        g = np.stack([np.convolve(ext[:, j], ker, mode="valid") for j in range(2)], axis=1)
        g[0, 0] = g[-1, 0] = 0.0
    return _resample_uniform(g, 0.001)


class Outline:
    """Guide outline (see the module docstring) with the waist offset w(s).

    R: corner radius (or (rear, front) pair) of the morphological-opening guide, or
    fan=(y_rear, y_front) for a stadium guide whose corner sections radiate from centreline points."""

    def __init__(self, pts, R=0.3, smooth=0.04, fan=None):
        waist = waist_polyline(pts)
        if fan is not None:
            g = stadium_guide(waist, fan[0], fan[1], smooth)
        else:
            has_r = (max(R) if isinstance(R, (tuple, list)) else R) > 0
            g = guide_polyline(waist, R, smooth) if has_r else _resample_uniform(waist, 0.001)
        self.waist = waist
        s = polyline_arclen(g)
        self.S = float(s[-1])
        self._s = s
        self._pts = g
        tan = unit(np.gradient(g, axis=0))
        tan[0] = (1.0, 0.0)    # perpendicular to the centreline at both ends (mirror symmetry)
        tan[-1] = (-1.0, 0.0)
        self._tan = tan
        self._nrm = np.c_[tan[:, 1], -tan[:, 0]]
        self._phi = np.degrees(np.arctan2(self._nrm[:, 1], self._nrm[:, 0]))
        self._w = self._waist_offset(waist)

    def _waist_offset(self, waist):
        """Distance along the guide normal to the waist polyline (0 where they coincide)."""
        g, n = self._pts, self._nrm
        nw = len(waist)
        # nearest waist sample per guide sample (chunked brute force)
        near = np.empty(len(g), dtype=int)
        for a in range(0, len(g), 512):
            d = np.linalg.norm(g[a:a + 512, None, :] - waist[None, ::2, :], axis=2)
            near[a:a + 512] = np.argmin(d, axis=1) * 2
        # within a window around it, the waist sample closest to the guide normal line
        win = np.arange(-150, 151)
        idx = np.clip(near[:, None] + win[None, :], 0, nw - 1)
        v = waist[idx] - g[:, None, :]
        along = v[..., 0] * n[:, None, 0] + v[..., 1] * n[:, None, 1]
        perp = np.abs(v[..., 0] * n[:, None, 1] - v[..., 1] * n[:, None, 0])
        perp = np.where(along > -0.05, perp, 1e9)
        k = np.argmin(perp, axis=1)
        w = along[np.arange(len(g)), k]
        self.w_min = float(w.min())  # < 0 means the guide pokes outside the waist (check!)
        return w

    def waist_offset(self, s):
        return np.interp(s, self._s, self._w)

    def _interp(self, arr, s):
        s = np.asarray(s, dtype=float)
        out = np.stack([np.interp(s, self._s, arr[:, k]) for k in range(arr.shape[1])], axis=-1)
        return out

    def point(self, s):
        return self._interp(self._pts, s)

    def normal(self, s):
        return unit(self._interp(self._nrm, s))

    def tangent(self, s):
        return unit(self._interp(self._tan, s))

    def phi(self, s):
        return np.interp(s, self._s, self._phi)

    # --- locating anchors --------------------------------------------------------------------
    def s_side_y(self, y):
        """s on the side branch (|phi| < 45 deg) where the outline has the given y."""
        m = np.abs(self._phi) < 45
        idx = np.where(m)[0]
        ys = self._pts[idx, 1]
        return float(np.interp(y, ys, self._s[idx]))

    def s_face_x(self, x, face):
        """s on the front (phi > 45) or rear (phi < -45) face where the outline has the given x."""
        m = self._phi > 45 if face == "front" else self._phi < -45
        idx = np.where(m)[0]
        xs = self._pts[idx, 0]
        ss = self._s[idx]
        if face == "front":  # x decreases with s on the front face
            xs, ss = xs[::-1], ss[::-1]
        return float(np.interp(x, xs, ss))

    def s_phi(self, phi):
        return float(np.interp(phi, self._phi, self._s))

    def project(self, xy):
        """s of the outline point nearest to each xy (brute force on the dense samples)."""
        xy = np.atleast_2d(xy)
        d = np.linalg.norm(self._pts[None, :, :] - xy[:, None, :], axis=2)
        i = np.argmin(d, axis=1)
        return self._s[i]


# ----------------------------------------------------------------------------------------------
# Strip
# ----------------------------------------------------------------------------------------------
class FeatureCurve:
    """3D polyline (x, y, z) splined by chord length and sampled densely."""

    def __init__(self, pts, step=0.002):
        p = np.asarray(pts, dtype=float)
        ends_on_axis = abs(p[0, 0]) < 1e-9 and abs(p[-1, 0]) < 1e-9
        if ends_on_axis:
            # mirror two neighbours across x = 0 at each end so the curve meets the centreline
            # perpendicularly (mirror symmetry of the full body)
            m = np.array([-1.0, 1.0, 1.0])
            ext = np.vstack([p[2:0:-1] * m, p, p[-2:-4:-1] * m])
        else:
            ext = p
        u = polyline_arclen(ext)
        sp = CSpline(u, ext, bc="natural")
        u0, u1 = (u[2], u[-3]) if ends_on_axis else (u[0], u[-1])
        n = max(int((u1 - u0) / step), 50)
        q = sp(np.linspace(u0, u1, n))
        if ends_on_axis:
            q[0, 0] = q[-1, 0] = 0.0
        self.p = q

    def cut(self, g, t, n, h_range=(-0.40, 0.25)):
        """Point where the curve crosses the vertical plane through g with normal t (2D).
        Returns (h, z) in the section frame, choosing the crossing with h in h_range nearest to 0."""
        q = self.p
        d = (q[:, 0] - g[0]) * t[0] + (q[:, 1] - g[1]) * t[1]
        d[np.abs(d) < 1e-6] = 0.0
        sgn = np.sign(d)
        idx = np.where(sgn[:-1] * sgn[1:] <= 0)[0]
        best = None
        for i in idx:
            a, b = d[i], d[i + 1]
            f = 0.0 if a == b else a / (a - b)
            pt = q[i] + f * (q[i + 1] - q[i])
            h = (pt[0] - g[0]) * n[0] + (pt[1] - g[1]) * n[1]
            if h_range[0] <= h <= h_range[1] and (best is None or abs(h) < abs(best[0])):
                best = (h, pt[2])
        if best is None:
            raise ValueError(f"feature curve does not cross the section plane at {g}")
        return best


class LineGuide:
    """Straight guide x = x0 along y (sections in the planes y = const, outward = +x): turns a
    Strip into a loft over y. s = y - y0."""

    def __init__(self, x0, y0, y1):
        self.x0, self.y0, self.S = float(x0), float(y0), float(y1 - y0)

    def y_of_s(self, s):
        return self.y0 + np.asarray(s, float)

    def point(self, s):
        s = np.asarray(s, float)
        return np.stack(np.broadcast_arrays(np.full_like(s, self.x0), self.y0 + s), axis=-1)

    def normal(self, s):
        s = np.asarray(s, float)
        return np.stack(np.broadcast_arrays(np.ones_like(s), np.zeros_like(s)), axis=-1)

    def tangent(self, s):
        s = np.asarray(s, float)
        return np.stack(np.broadcast_arrays(np.zeros_like(s), np.ones_like(s)), axis=-1)

    def phi(self, s):
        return np.zeros_like(np.asarray(s, float))

    def waist_offset(self, s):
        return np.zeros_like(np.asarray(s, float))

    def s_side_y(self, y):
        return float(y - self.y0)


BODY_KEYS = [  # key definitions of the body strip (see body_tables.FEATURE_CURVES)
    dict(curve=0), dict(waist=True), dict(curve=2), dict(rule=(2, 4)), dict(curve=4), dict(curve=5)]


class Strip:
    """Perimeter band; see the module docstring.

    keys: list of key definitions, bottom to top:
        dict(curve=id)       position from the feature curve `id` cut by the section plane
        dict(waist=True)     h = waist offset w(s), z from the anchors' 'z' table
        dict(rule=(i, j))    K = K_i + a (K_j - K_i) + b * outward normal of that chord,
                             (a, b) from the anchors' 'rule' table
    anchors: dict(kind, at, th=[per key: angle | (in, out, fillet_r)], z=height of the waist key,
                  rule=(a, b), handles={(segment, 0|1): factor})
    """

    def __init__(self, outline, curves, anchors, keys=None, knots=None, handle=0.36, n_seg=40,
                 h_range=(-0.40, 0.25), centres=None):
        self.O = outline
        self.n_seg = n_seg
        self.keydefs = keys or BODY_KEYS
        self.knots = np.asarray(knots if knots is not None else KNOTS, dtype=float)
        self.nkey = len(self.keydefs)
        if len(self.knots) != self.nkey:
            raise ValueError("one knot per key")
        self.h_range = h_range
        self.curves = {k: FeatureCurve(v) for k, v in curves.items()}
        # centreline profiles (y, z) for 'centre' keys, as functions of s (line guides only)
        self.centre_z = {}
        for k, tab in (centres or {}).items():
            a = np.asarray(sorted(tab), float)
            f = Pchip(a[:, 0], a[:, 1])
            lo, hi = a[0, 0], a[-1, 0]
            self.centre_z[k] = (lambda ff, l, h: (lambda s: float(ff(np.clip(outline.y_of_s(s), l, h)))))(f, lo, hi)
        rows = []
        for a in anchors:
            kind, at = a["kind"], a["at"]
            if kind == "side":
                s = outline.s_side_y(at)
            elif kind in ("front", "rear"):
                s = outline.s_face_x(at, kind)
            elif kind == "phi":
                s = outline.s_phi(at)
            elif kind == "s":
                s = float(at)
            else:
                raise ValueError(kind)
            th = a["th"]
            if len(th) != self.nkey:
                raise ValueError(f"anchor {kind}:{at}: {len(th)} angles for {self.nkey} keys")
            ang = np.zeros((self.nkey, 3))  # th_in, th_out, r
            for k, v in enumerate(th):
                ang[k] = v if isinstance(v, (tuple, list)) else (v, v, 0.0)
            hd = np.full((self.nkey - 1, 2), handle)
            for (k, side), v in a.get("handles", {}).items():
                hd[k, side] = v
            z = a.get("z", a.get("z1", 0.0))
            rule = a.get("rule", a.get("k3", (0.5, 0.0)))
            row = np.r_[z, rule[0], rule[1], ang.ravel()]
            rows.append((s, row, hd, a.get("name", f"{kind}:{at}")))
        rows.sort(key=lambda r: r[0])
        self.anchor_s = np.array([r[0] for r in rows])
        self.anchor_names = [r[3] for r in rows]
        self._Af = Pchip(self.anchor_s, np.stack([r[1] for r in rows]))
        self._Hf = Pchip(self.anchor_s, np.stack([r[2] for r in rows]).reshape(len(rows), -1))
        self._cache = {}

    # --- section ---------------------------------------------------------------------------------
    def keys(self, s):
        """Key points K (nkey x [h, z, th_in, th_out, r]) and handle factors at s."""
        sc = float(np.clip(s, self.anchor_s[0], self.anchor_s[-1]))
        a = self._Af(sc)
        zw, ka, kb = a[0], a[1], a[2]
        ang = a[3:].reshape(self.nkey, 3)
        g = self.O.point(s)
        n = self.O.normal(s)
        t = np.array([-n[1], n[0]])
        K = np.zeros((self.nkey, 5))
        pending = []
        for k, kd in enumerate(self.keydefs):
            if "curve" in kd:
                try:
                    K[k, :2] = self.curves[kd["curve"]].cut(g, t, n, self.h_range)
                except ValueError:
                    if "fallback" not in kd:
                        raise
                    K[k, :2] = K[kd["fallback"], :2]   # curve ends before this station: collapse
            elif "centre" in kd:
                K[k, :2] = (-g[0] / n[0], self.centre_z[kd["centre"]](float(s)))
            elif kd.get("waist"):
                K[k, :2] = (float(self.O.waist_offset(s)), zw)
            else:
                pending.append(k)
        for k in pending:
            i, j = self.keydefs[k]["rule"]
            c = K[j, :2] - K[i, :2]
            perp = np.array([c[1], -c[0]]) / max(np.linalg.norm(c), 1e-9)
            K[k, :2] = K[i, :2] + ka * c + kb * perp
        K[:, 2:] = ang
        for k, kd in enumerate(self.keydefs):
            if kd.get("auto_out") and k + 1 < self.nkey:
                # parabola towards the next key that arrives there level (e.g. the centreline):
                # start slope = 2 dz / dh
                dh = K[k, 0] - K[k + 1, 0]
                dz = K[k + 1, 1] - K[k, 1]
                if dh > 1e-6:
                    K[k, 3] = 180.0 - np.degrees(np.arctan2(2.0 * dz, dh))
        H = self._Hf(sc).reshape(self.nkey - 1, 2)
        return K, H

    def section(self, s):
        """Section polyline in local (h, z) with its t value per vertex, and fillet t-extents.

        Returns dict(p=(m,2), t=(m,), fillet=[(t_lo, t_k, t_hi) or None per key])."""
        key = round(float(s), 7)
        c = self._cache.get(key)
        if c is not None:
            return c
        K, H = self.keys(s)
        KNOTS = self.knots
        nkey = self.nkey
        P = K[:, :2]
        segs = []
        for k in range(nkey - 1):
            p0, p3 = P[k], P[k + 1]
            ch = np.linalg.norm(p3 - p0)
            p1 = p0 + H[k, 0] * ch * dir2(K[k, 3])
            p2 = p3 - H[k, 1] * ch * dir2(K[k + 1, 2])
            segs.append(bezier(p0, p1, p2, p3, self.n_seg))
        arcs = [None] * nkey
        seglen = [float(np.linalg.norm(P[k + 1] - P[k])) for k in range(nkey - 1)]
        for j in range(1, nkey - 1):
            r = K[j, 4]
            if r > 0 and abs(K[j, 3] - K[j, 2]) > 0.5 and min(seglen[j - 1], seglen[j]) > 4 * r:
                a, arc, b = fillet_corner(segs[j - 1], segs[j], r)
                segs[j - 1], segs[j] = a, b
                arcs[j] = arc
        # assemble pieces between key representatives
        pts, ts = [], []
        fil = [None] * nkey
        for k in range(nkey - 1):
            piece = []
            lo_arc = arcs[k]
            hi_arc = arcs[k + 1]
            if lo_arc is not None and len(lo_arc):
                m = len(lo_arc) // 2
                piece.append(lo_arc[m:])
                piece.append(segs[k][1:])
            else:
                piece.append(segs[k])
            if hi_arc is not None and len(hi_arc):
                m = len(hi_arc) // 2
                piece.append(hi_arc[1:m + 1])
            q = np.vstack(piece)
            sl = polyline_arclen(q)
            if sl[-1] < 1e-9:   # collapsed segment (a key line ended before this station)
                sl = np.linspace(0.0, 1.0, len(q))
            tt = KNOTS[k] + (KNOTS[k + 1] - KNOTS[k]) * sl / sl[-1]
            # fillet extents inside this piece
            if lo_arc is not None and len(lo_arc):
                la = polyline_arclen(lo_arc[len(lo_arc) // 2:])[-1]
                fil_hi = KNOTS[k] + (KNOTS[k + 1] - KNOTS[k]) * la / sl[-1]
                fil[k] = (fil[k][0] if fil[k] else KNOTS[k], KNOTS[k], fil_hi)
            if hi_arc is not None and len(hi_arc):
                la = polyline_arclen(hi_arc[:len(hi_arc) // 2 + 1])[-1]
                fil_lo = KNOTS[k + 1] - (KNOTS[k + 1] - KNOTS[k]) * la / sl[-1]
                fil[k + 1] = (fil_lo, KNOTS[k + 1], KNOTS[k + 1])
            if k > 0:
                q, tt = q[1:], tt[1:]
            pts.append(q)
            ts.append(tt)
        p = np.vstack(pts)
        t = np.concatenate(ts)
        t = np.maximum.accumulate(t)
        out = {"p": p, "t": t, "fillet": fil, "K": K}
        if len(self._cache) > 4000:
            self._cache.clear()
        self._cache[key] = out
        return out

    def local(self, s, t):
        """(h, z) at parameter t (array) on the section at s."""
        sec = self.section(s)
        t = np.asarray(t, dtype=float)
        return np.stack([np.interp(t, sec["t"], sec["p"][:, 0]), np.interp(t, sec["t"], sec["p"][:, 1])], axis=-1)

    def point(self, s, t):
        """3D points for arrays s, t of equal shape (exact: one section build per distinct s)."""
        s = np.atleast_1d(np.asarray(s, dtype=float))
        t = np.atleast_1d(np.asarray(t, dtype=float))
        s, t = np.broadcast_arrays(s, t)
        out = np.empty(s.shape + (3,))
        o = self.O.point(s.ravel()).reshape(s.shape + (2,))
        n = self.O.normal(s.ravel()).reshape(s.shape + (2,))
        hz = np.empty(s.shape + (2,))
        flat_s, flat_t = s.ravel(), t.ravel()
        flat_hz = hz.reshape(-1, 2)
        for sv in np.unique(flat_s):
            m = flat_s == sv
            flat_hz[m] = self.local(sv, flat_t[m])
        out[..., 0] = o[..., 0] + hz[..., 0] * n[..., 0]
        out[..., 1] = o[..., 1] + hz[..., 0] * n[..., 1]
        out[..., 2] = hz[..., 1]
        return out

    # --- dense grid for fast evaluation ---------------------------------------------------------
    def build_grid(self, ds=0.004, nt=1201):
        S = self.O.S
        ns = int(math.ceil(S / ds)) + 1
        self.gs = np.linspace(0.0, S, ns)
        self.gt = np.linspace(0.0, 1.0, nt)
        G = np.empty((ns, nt, 3))
        for i, sv in enumerate(self.gs):
            G[i] = self.point(np.full(nt, sv), self.gt)
        self.G = G
        return G

    def eval(self, s, t):
        """Bilinear interpolation on the dense grid (build_grid first)."""
        s = np.asarray(s, dtype=float)
        t = np.asarray(t, dtype=float)
        gs, gt, G = self.gs, self.gt, self.G
        fs = np.clip((s - gs[0]) / (gs[1] - gs[0]), 0, len(gs) - 1.000001)
        ft = np.clip((t - gt[0]) / (gt[1] - gt[0]), 0, len(gt) - 1.000001)
        i = np.floor(fs).astype(int)
        j = np.floor(ft).astype(int)
        a = (fs - i)[..., None]
        b = (ft - j)[..., None]
        return ((1 - a) * (1 - b) * G[i, j] + a * (1 - b) * G[i + 1, j]
                + (1 - a) * b * G[i, j + 1] + a * b * G[i + 1, j + 1])

    def normal(self, s, t, eps_s=0.003, eps_t=0.0008):
        """Outward unit normal by central differences (one-sided at the ends)."""
        s = np.asarray(s, dtype=float)
        t = np.asarray(t, dtype=float)
        s0 = np.clip(s - eps_s, 0, self.O.S)
        s1 = np.clip(s + eps_s, 0, self.O.S)
        t0 = np.clip(t - eps_t, 0, 1)
        t1 = np.clip(t + eps_t, 0, 1)
        ds_ = self.eval(s1, t) - self.eval(s0, t)
        dt_ = self.eval(s, t1) - self.eval(s, t0)
        n = np.cross(ds_, dt_)
        return unit(n)


def _spec(spec):
    """(pos, z, th) | (pos, z, th_in, th_out, r) -> (pos, z, th_in, th_out, r)."""
    if len(spec) == 3:
        pos, z, th = spec
        return pos, z, th, th, 0.0
    if len(spec) == 5:
        return spec
    raise ValueError(spec)
