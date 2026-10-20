"""Height-field caps of the body (pure numpy): hood, roof, deck lid.

A cap is z = H(x, y) over a plan region (right half). H = F + C where
    F(x, y)  design function (centreline profile, crown, bulges, edge rolls)
    C(x, y)  boundary correction: Shepard-weighted blend of per-sample corrections
             c_k(p) = (z_k - F(b_k)) + g_k * (grad_k - grad F(b_k)) . (p - b_k)
             faded out by w(d / D_k) with w(0) = 1, w'(0) = 0, w(1) = w'(1) = 0.
so the cap meets its boundary curve exactly, with the neighbouring surface's tangent plane where
g_k = 1 (G1 across a shut line or a paint line) and with its own slope where g_k = 0.

Meshing uses a Coons patch in the plan: corners rear-centre, rear-corner, front-corner, front-centre.
"""
import numpy as np

from .geom import CSpline, Pchip, polyline_arclen


def _w(u):
    u = np.clip(u, 0.0, 1.0)
    return (1 - u) ** 3 * (1 + 3 * u)


class BoundarySamples:
    """Dense boundary samples b_k (x, y), z_k, target gradient grad_k (dz/dx, dz/dy), G1 weight g_k,
    and fall-off distance D_k."""

    def __init__(self):
        self.b, self.z, self.grad, self.g, self.D = [], [], [], [], []

    def add(self, xy, z, grad=None, g=0.0, D=0.12):
        xy = np.atleast_2d(xy)
        n = len(xy)
        self.b.append(xy)
        self.z.append(np.broadcast_to(np.asarray(z, float), (n,)))
        self.grad.append(np.zeros((n, 2)) if grad is None else np.broadcast_to(np.asarray(grad, float), (n, 2)))
        self.g.append(np.broadcast_to(np.asarray(g, float), (n,)))
        self.D.append(np.broadcast_to(np.asarray(D, float), (n,)))

    def arrays(self):
        return (np.vstack(self.b), np.concatenate(self.z), np.vstack(self.grad), np.concatenate(self.g),
                np.concatenate(self.D))


class HeightCap:
    def __init__(self, design, boundary, eps=1e-4):
        self.F = design
        b, z, grad, g, D = boundary.arrays()
        self.b, self.zb, self.gradb, self.gb, self.Db = b, z, grad, g, D
        Fb = design(b[:, 0], b[:, 1])
        dF = self._gradF(b[:, 0], b[:, 1], eps)
        self.off = z - Fb                      # value correction per sample
        self.dgrad = (grad - dF) * g[:, None]  # slope correction per sample

    def _gradF(self, x, y, eps=1e-4):
        fx = (self.F(x + eps, y) - self.F(x - eps, y)) / (2 * eps)
        fy = (self.F(x, y + eps) - self.F(x, y - eps)) / (2 * eps)
        return np.stack([fx, fy], axis=-1)

    def z(self, x, y, chunk=2048):
        x = np.asarray(x, float)
        y = np.asarray(y, float)
        shp = x.shape
        xf, yf = x.ravel(), y.ravel()
        out = self.F(xf, yf).astype(float)
        b, D = self.b, self.Db
        for a in range(0, len(xf), chunk):
            px, py = xf[a:a + chunk], yf[a:a + chunk]
            dx = px[:, None] - b[None, :, 0]
            dy = py[:, None] - b[None, :, 1]
            d = np.sqrt(dx * dx + dy * dy)
            u = d / D[None, :]
            near = u < 1.0
            if not near.any():
                continue
            wfall = _w(u) * near
            shep = near / (d ** 4 + 1e-12)
            c = self.off[None, :] + self.dgrad[None, :, 0] * dx + self.dgrad[None, :, 1] * dy
            sw = shep.sum(axis=1)
            ok = sw > 0
            corr = np.zeros(len(px))
            fall = np.zeros(len(px))
            corr[ok] = (shep[ok] * c[ok]).sum(axis=1) / sw[ok]
            fall[ok] = (shep[ok] * wfall[ok]).sum(axis=1) / sw[ok]
            out[a:a + chunk] += fall * corr
        return out.reshape(shp)

    def normal(self, x, y, eps=2e-4):
        x = np.asarray(x, float)
        y = np.asarray(y, float)
        zx = (self.z(x + eps, y) - self.z(x - eps, y)) / (2 * eps)
        zy = (self.z(x, y + eps) - self.z(x, y - eps)) / (2 * eps)
        n = np.stack([-zx, -zy, np.ones_like(zx)], axis=-1)
        return n / np.linalg.norm(n, axis=-1, keepdims=True)


# ------------------------------------------------------------------------------------------------
# plan-domain helpers
# ------------------------------------------------------------------------------------------------
def polyline_param(p, n):
    """n points evenly spaced by arc length along polyline p (any dimension)."""
    s = polyline_arclen(p)
    q = np.linspace(0, s[-1], n)
    return np.stack([np.interp(q, s, p[:, k]) for k in range(p.shape[1])], axis=1)


def coons(c_bottom, c_top, c_left, c_right):
    """Bilinearly blended Coons patch from four boundary point arrays.
    c_bottom/c_top: (nu, d) from left to right; c_left/c_right: (nv, d) from bottom to top.
    Returns (nu, nv, d)."""
    nu, nv = len(c_bottom), len(c_left)
    u = np.linspace(0, 1, nu)[:, None, None]
    v = np.linspace(0, 1, nv)[None, :, None]
    B = c_bottom[:, None, :]
    T = c_top[:, None, :]
    L = c_left[None, :, :]
    R = c_right[None, :, :]
    P00, P10, P01, P11 = c_bottom[0], c_bottom[-1], c_top[0], c_top[-1]
    return ((1 - v) * B + v * T + (1 - u) * L + u * R
            - ((1 - u) * (1 - v) * P00 + u * (1 - v) * P10 + (1 - u) * v * P01 + u * v * P11))


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def table_fn(pairs, kind="pchip"):
    a = np.asarray(pairs, float)
    f = (Pchip if kind == "pchip" else CSpline)(a[:, 0], a[:, 1])
    lo, hi = a[0, 0], a[-1, 0]
    return lambda x: f(np.clip(x, lo, hi))
