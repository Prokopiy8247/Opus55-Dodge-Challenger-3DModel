"""Body panels as Coons patches in the parameter space of a surface (pure numpy).

A panel is bounded by four parameter-space curves (bottom, right, top, left; bottom/top run left to
right, left/right run bottom to top) and may contain crease rows (iso-parameter lines that run from
its left to its right boundary). The panel is split into sub-strips at the crease rows; each
sub-strip is a Coons patch, all with the same number of columns, so the mesh is conforming and every
crease is an edge loop. Normals come from the analytic surface (per face corner, evaluated slightly
inside the face), which keeps creases sharp and everything else smooth.

Panel edges: the boundary is inset by half the panel gap and the panel gets a rolled edge and a
flange that turn under the surface (the visible inside of the gap).

Surfaces implement SurfaceAdapter: P(a, b) -> (..., 3), N(a, b) -> (..., 3), both vectorised.
"""
import numpy as np

from .geom import polyline_arclen


def _catmull_rom_weights(f):
    """Weights of the 4 neighbours (-1, 0, 1, 2) for fractional positions f in [0, 1)."""
    f2, f3 = f * f, f * f * f
    return np.stack([-0.5 * f3 + f2 - 0.5 * f, 1.5 * f3 - 2.5 * f2 + 1.0,
                     -1.5 * f3 + 2.0 * f2 + 0.5 * f, 0.5 * f3 - 0.5 * f2], axis=-1)


class GridSurface:
    """Precomputed parameter grid with C1 (Catmull-Rom) interpolation: fast P(a, b)."""

    def __init__(self, fn, a_range, b_range, na, nb):
        self.a_range, self.b_range = a_range, b_range
        self.A = np.linspace(a_range[0], a_range[1], na)
        self.B = np.linspace(b_range[0], b_range[1], nb)
        aa, bb = np.meshgrid(self.A, self.B, indexing="ij")
        self.G = fn(aa, bb).reshape(na, nb, 3)

    def P(self, a, b):
        a, b = np.broadcast_arrays(np.asarray(a, float), np.asarray(b, float))
        shp = a.shape
        a, b = a.ravel(), b.ravel()
        na, nb = len(self.A), len(self.B)
        fa = np.clip((a - self.A[0]) / (self.A[1] - self.A[0]), 0, na - 1 - 1e-9)
        fb = np.clip((b - self.B[0]) / (self.B[1] - self.B[0]), 0, nb - 1 - 1e-9)
        ia, ib = np.floor(fa).astype(int), np.floor(fb).astype(int)
        wa = _catmull_rom_weights(fa - ia)
        wb = _catmull_rom_weights(fb - ib)
        out = np.zeros((len(a), 3))
        for di in range(4):
            ii = np.clip(ia + di - 1, 0, na - 1)
            for dj in range(4):
                jj = np.clip(ib + dj - 1, 0, nb - 1)
                out += (wa[:, di] * wb[:, dj])[:, None] * self.G[ii, jj]
        return out.reshape(shp + (3,))


class StripSurface:
    """Adapter for shape.Strip (a = s, b = t), evaluated through a cached dense grid."""

    _cache = {}

    def __init__(self, strip, ds=0.004, nt=1201):
        self.st = strip
        self.a_range = (0.0, strip.O.S)
        self.b_range = (0.0, 1.0)
        key = (id(strip), ds, nt)
        g = StripSurface._cache.get(key)
        if g is None:
            na = int(np.ceil(strip.O.S / ds)) + 1
            g = GridSurface(lambda a, b: strip.point(a, b), self.a_range, self.b_range, na, nt)
            if len(StripSurface._cache) >= 3:
                StripSurface._cache.pop(next(iter(StripSurface._cache)))
            StripSurface._cache[key] = g
        self.grid = g

    def P(self, a, b):
        return self.grid.P(a, b)

    def N(self, a, b, ea=1.5e-3, eb=6e-4):
        a, b = np.broadcast_arrays(np.asarray(a, float), np.asarray(b, float))
        A0 = np.clip(a - ea, *self.a_range)
        A1 = np.clip(a + ea, *self.a_range)
        B0 = np.clip(b - eb, *self.b_range)
        B1 = np.clip(b + eb, *self.b_range)
        n = np.cross(self.P(A1, b) - self.P(A0, b), self.P(a, B1) - self.P(a, B0))
        ln = np.linalg.norm(n, axis=-1, keepdims=True)
        return n / np.where(ln < 1e-12, 1.0, ln)


class CapSurface:
    """Adapter for caps.HeightCap (a = x, b = y)."""

    def __init__(self, cap, x_range=(-1.2, 1.2), y_range=(-3.0, 3.0)):
        self.cap = cap
        self.a_range, self.b_range = x_range, y_range

    def P(self, a, b):
        a, b = np.broadcast_arrays(np.asarray(a, float), np.asarray(b, float))
        return np.stack([a, b, self.cap.z(a, b)], axis=-1)

    def N(self, a, b):
        return self.cap.normal(*np.broadcast_arrays(np.asarray(a, float), np.asarray(b, float)))


# ------------------------------------------------------------------------------------------------
def coons(c_bottom, c_top, c_left, c_right):
    """Bilinear Coons patch; returns (nu, nv, d)."""
    nu, nv = len(c_bottom), len(c_left)
    u = np.linspace(0, 1, nu)[:, None, None]
    v = np.linspace(0, 1, nv)[None, :, None]
    B, T = c_bottom[:, None, :], c_top[:, None, :]
    L, R = c_left[None, :, :], c_right[None, :, :]
    P00, P10, P01, P11 = c_bottom[0], c_bottom[-1], c_top[0], c_top[-1]
    return ((1 - v) * B + v * T + (1 - u) * L + u * R
            - ((1 - u) * (1 - v) * P00 + u * (1 - v) * P10 + (1 - u) * v * P01 + u * v * P11))


def _folded(G):
    """Cells of a (nu, nv, 2) parameter grid whose orientation differs from the majority (or that
    have collapsed)."""
    d1 = G[1:, :-1] - G[:-1, :-1]
    d2 = G[:-1, 1:] - G[:-1, :-1]
    c = d1[..., 0] * d2[..., 1] - d1[..., 1] * d2[..., 0]
    s = np.sign(np.median(c))
    return c * s <= 1e-14


def winslow(G, scale=(1.0, 1.0), iters=4000, min_iters=200, check=50):
    """Elliptic (Winslow) grid smoothing with fixed boundary rows/columns: the inverse-Laplace
    equations keep cells unfolded on non-convex domains. scale: metric scale of the two
    parameters (metres per unit), so the smoothing works in surface lengths."""
    sc = np.asarray(scale, float)
    X = G * sc
    for it in range(iters):
        xe = 0.5 * (X[2:, 1:-1] - X[:-2, 1:-1])
        xn = 0.5 * (X[1:-1, 2:] - X[1:-1, :-2])
        a = (xn * xn).sum(-1)[..., None]
        g = (xe * xe).sum(-1)[..., None]
        b = (xe * xn).sum(-1)[..., None]
        xen = 0.25 * (X[2:, 2:] - X[2:, :-2] - X[:-2, 2:] + X[:-2, :-2])
        X[1:-1, 1:-1] = (a * (X[2:, 1:-1] + X[:-2, 1:-1]) + g * (X[1:-1, 2:] + X[1:-1, :-2])
                         - 2.0 * b * xen) / np.maximum(2.0 * (a + g), 1e-30)
        if it >= min_iters and it % check == 0 and not _folded(X).any():
            break
    return X / sc


def resample_param_curve(surf, c, n, dense=200):
    """n points along the parameter curve c (m, 2), evenly spaced by 3D arc length on the surface."""
    c = np.asarray(c, float)
    s = polyline_arclen(c)
    q = np.linspace(0, s[-1], dense)
    cd = np.stack([np.interp(q, s, c[:, 0]), np.interp(q, s, c[:, 1])], axis=1)
    P = surf.P(cd[:, 0], cd[:, 1])
    L = polyline_arclen(P)
    w = np.linspace(0, L[-1], n)
    return np.stack([np.interp(w, L, cd[:, 0]), np.interp(w, L, cd[:, 1])], axis=1), float(L[-1])


def curve_length(surf, c, dense=200):
    return resample_param_curve(surf, c, 2, dense)[1]


def split_curve(c, at_b=None, at_a=None):
    """Split a parameter curve where its b (or a) coordinate crosses each value of at_b (or at_a)."""
    c = np.asarray(c, float)
    k = 1 if at_b is not None else 0
    vals = at_b if at_b is not None else at_a
    cuts = []
    for v in vals:
        d = c[:, k] - v
        i = np.where(np.sign(d[:-1]) * np.sign(d[1:]) <= 0)[0]
        if len(i) == 0:
            raise ValueError(f"curve does not reach {v}")
        i = i[0]
        f = 0.0 if d[i] == d[i + 1] else d[i] / (d[i] - d[i + 1])
        cuts.append((i, c[i] + f * (c[i + 1] - c[i])))
    pieces, start, prev = [], 0, None
    for i, p in cuts:
        seg = c[start:i + 1]
        if prev is not None:
            seg = np.vstack([prev[None], seg])
        pieces.append(np.vstack([seg, p[None]]))
        prev, start = p, i + 1
    tail = c[start:]
    pieces.append(np.vstack([prev[None], tail]) if prev is not None else tail)
    return pieces


class Panel:
    """See the module docstring.

    bottom, top: (m, 2) parameter curves from left to right; left, right: bottom to top.
    creases: list of b values (iso-b rows across the panel, e.g. strip knots).
    edge: target edge length (m). gap: full panel gap (m), applied as gap/2 on each inset side
    (inset = dict(bottom=, right=, top=, left=) of booleans, default all).
    offset(a, b): optional outward displacement (m) along the surface normal (flares)."""

    def __init__(self, name, surf, bottom, right, top, left, creases=(), edge=0.025, gap=0.005,
                 inset=None, flange=(0.0025, 0.008), offset=None, min_rows=2, holes=(), hole_flange=(0.003, 0.02),
                 flange_sides=None):
        self.name, self.surf = name, surf
        self.bottom, self.right, self.top, self.left = (np.asarray(c, float) for c in (bottom, right, top, left))
        self.creases = sorted(creases)
        self.edge, self.gap = edge, gap
        self.inset = inset or dict(bottom=True, right=True, top=True, left=True)
        self.flange = flange
        self.offset = offset
        self.min_rows = min_rows
        self.holes = [np.asarray(h, float) for h in holes]   # closed parameter-space polygons
        self.hole_flange = hole_flange
        # no flange where there is no gap (unless given per side)
        self.flange_sides = dict(flange_sides) if flange_sides is not None else {k: v for k, v in self.inset.items()}

    # --- parameter grid ----------------------------------------------------------------------------
    def grid(self):
        surf = self.surf
        L_b = curve_length(surf, self.bottom)
        L_t = curve_length(surf, self.top)
        nu = max(int(np.ceil(max(L_b, L_t) / self.edge)) + 1, 3)
        rows = [self.bottom]
        # the Coons patch spreads any corner mismatch along the whole bottom/top row: bend the side
        # curves onto the bottom/top end points, only over the 20 % of their length next to each
        # corner (the rest of a side is a shut line shared with a neighbour and must stay put)
        left, right = self.left.copy(), self.right.copy()
        for c, p0, p1 in ((left, self.bottom[0], self.top[0]), (right, self.bottom[-1], self.top[-1])):
            w = polyline_arclen(c)
            w = w / max(w[-1], 1e-12)
            w0 = np.clip(1.0 - w / 0.2, 0.0, 1.0)[:, None]
            w1 = np.clip((w - 0.8) / 0.2, 0.0, 1.0)[:, None]
            c += w0 * w0 * (3 - 2 * w0) * (p0 - c[0]) + w1 * w1 * (3 - 2 * w1) * (p1 - c[-1])
        lefts = split_curve(left, at_b=self.creases) if self.creases else [left]
        rights = split_curve(right, at_b=self.creases) if self.creases else [right]
        for cb in self.creases:
            a0 = lefts[len(rows) - 1][-1, 0]
            a1 = rights[len(rows) - 1][-1, 0]
            rows.append(np.stack([np.linspace(a0, a1, 64), np.full(64, cb)], axis=1))
        rows.append(self.top)
        grids = []
        for k in range(len(rows) - 1):
            cb_, ct_ = rows[k], rows[k + 1]
            cl_, cr_ = lefts[k], rights[k]
            Lh = max(curve_length(surf, cl_), curve_length(surf, cr_))
            # interior columns may be longer than the sides (e.g. a band with pointed ends)
            Bc, _ = resample_param_curve(surf, cb_, 9)
            Tc, _ = resample_param_curve(surf, ct_, 9)
            Lc, _ = resample_param_curve(surf, cl_, 12)
            Rc, _ = resample_param_curve(surf, cr_, 12)
            Gc = coons(Bc, Tc, Lc, Rc)
            Pc = surf.P(Gc[..., 0], Gc[..., 1])
            Lh = max(Lh, float(np.linalg.norm(np.diff(Pc, axis=1), axis=-1).sum(axis=1).max()))
            nv = max(int(np.ceil(Lh / self.edge)) + 1, self.min_rows)
            B, _ = resample_param_curve(surf, cb_, nu)
            T, _ = resample_param_curve(surf, ct_, nu)
            Lc, _ = resample_param_curve(surf, cl_, nv)
            Rc, _ = resample_param_curve(surf, cr_, nv)
            G = coons(B, T, Lc, Rc)
            grids.append(G if k == 0 else G[:, 1:])
        G = np.concatenate(grids, axis=1)  # (nu, nv_total, 2)
        # sub-strip row ranges (crease rows are shared boundaries)
        self._bands, j0 = [], 0
        for g in grids:
            j1 = j0 + g.shape[1] - (1 if j0 == 0 else 0)
            self._bands.append((j0, j1))
            j0 = j1
        return self._untangle(G)

    def _untangle(self, G):
        """Winslow-smooth every sub-strip whose Coons grid folds over (a bottom boundary that bulges
        up to the next crease, e.g. the fender over the wheel arch); boundaries stay fixed."""
        for j0, j1 in getattr(self, "_bands", [(0, G.shape[1] - 1)]):
            sub = G[:, j0:j1 + 1]
            if sub.shape[1] < 3 or not _folded(sub).any():
                continue
            P = self.surf.P(sub[..., 0], sub[..., 1])
            da = np.abs(np.diff(sub[..., 0], axis=0)) + 1e-12
            db = np.abs(np.diff(sub[..., 1], axis=1)) + 1e-12
            sa = np.median(np.linalg.norm(np.diff(P, axis=0), axis=-1) / da)
            sb = np.median(np.linalg.norm(np.diff(P, axis=1), axis=-1) / db)
            G[:, j0:j1 + 1] = winslow(sub, scale=(sa, sb))
        return G

    def inset_grid(self, G):
        """Move the outer rows/columns inward by gap/2, perpendicular to the border inside the
        tangent plane (moving towards the next grid row instead slides the border along skewed
        grid lines, under the neighbouring panel)."""
        h = self.gap / 2.0
        if h <= 0:
            return G
        G = G.copy()
        surf = self.surf
        ea = 1e-4 * (surf.a_range[1] - surf.a_range[0])
        eb = 1e-4 * (surf.b_range[1] - surf.b_range[0])
        # global handedness of the grid in parameter space: the interior side of each border follows
        # from it (the next grid row is unreliable where rows bunch up)
        d1 = G[1:, :-1] - G[:-1, :-1]
        d2 = G[:-1, 1:] - G[:-1, :-1]
        orient = np.sign(np.median(d1[..., 0] * d2[..., 1] - d1[..., 1] * d2[..., 0]))
        bands = getattr(self, "_bands", [(0, G.shape[1] - 1)])
        for side, sl, far, sgn in (("bottom", (slice(None), 0), (slice(None), bands[0][1]), orient),
                                   ("top", (slice(None), -1), (slice(None), bands[-1][0]), -orient),
                                   ("left", (0, slice(None)), (-1, slice(None)), -orient),
                                   ("right", (-1, slice(None)), (0, slice(None)), orient)):
            if not self.inset.get(side, True):
                continue
            e = G[sl]
            t2 = np.gradient(e, axis=0)
            n2 = sgn * np.stack([-t2[:, 1], t2[:, 0]], axis=1)          # inward, parameter space
            Pe = surf.P(e[:, 0], e[:, 1])
            if np.linalg.norm(np.diff(Pe, axis=0), axis=1).sum() < max(4 * h, 0.03):
                continue                                  # collapsed side (pointed corner): no gap
            Pf = surf.P(G[far][:, 0], G[far][:, 1])
            # surface Jacobian (central differences, clipped to the parameter range)
            a0, a1 = np.clip(e[:, 0] - ea, *surf.a_range), np.clip(e[:, 0] + ea, *surf.a_range)
            b0, b1 = np.clip(e[:, 1] - eb, *surf.b_range), np.clip(e[:, 1] + eb, *surf.b_range)
            Pa = (surf.P(a1, e[:, 1]) - surf.P(a0, e[:, 1])) / np.maximum(a1 - a0, 1e-12)[:, None]
            Pb = (surf.P(e[:, 0], b1) - surf.P(e[:, 0], b0)) / np.maximum(b1 - b0, 1e-12)[:, None]
            J = np.stack([Pa, Pb], axis=-1)                       # (n, 3, 2)
            T = np.gradient(Pe, axis=0)
            N = surf.N(e[:, 0], e[:, 1])
            d = np.cross(N, T)
            d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-12)
            d[((J @ n2[..., None])[..., 0] * d).sum(-1) < 0] *= -1.0
            # never more than 40 % of the way to the opposite boundary of the first band
            step = np.minimum(h, 0.4 * np.linalg.norm(Pf - Pe, axis=1))
            JT = J.transpose(0, 2, 1)
            A = JT @ J
            A += 1e-9 * np.trace(A, axis1=1, axis2=2)[:, None, None] * np.eye(2)   # near-singular loft poles
            x = np.linalg.solve(A, JT @ (step[:, None] * d)[..., None])[..., 0]
            # the parameter step may not move a point farther than twice the intended distance, nor
            # (where the surface degenerates, e.g. a loft pole) 40 % of the way across the band in
            # parameter space
            moved = np.linalg.norm((J @ x[..., None])[..., 0], axis=1)
            x *= np.minimum(1.0, 2.0 * step / np.maximum(moved, 1e-15))[:, None]
            span = np.linalg.norm(G[far] - e, axis=1)
            x *= np.minimum(1.0, 0.4 * span / np.maximum(np.linalg.norm(x, axis=1), 1e-15))[:, None]
            G[sl] = e + x
        return self._untangle(G)

    # --- mesh ----------------------------------------------------------------------------------------
    def mesh(self, du=0.02):
        cached = getattr(self, "_mesh_cache", None)
        if cached is not None and cached[0] == du:
            return cached[1]
        out = self._mesh(du)
        self._mesh_cache = (du, out)
        return out

    def _mesh(self, du):
        G = self.inset_grid(self.grid())
        nu, nv = G.shape[:2]
        a, b = G[..., 0], G[..., 1]
        P = self.surf.P(a, b)
        if self.offset is not None:
            N0 = self.surf.N(a, b)
            P = P + self.offset(a, b)[..., None] * N0
        # a border side on the mirror plane lies exactly on it (the interpolated surface puts it a few
        # microns off: no weld with the mirror copy, a flange corner bent sideways, a shading seam)
        for sl in ((slice(None), 0), (slice(None), -1), (0, slice(None)), (-1, slice(None))):
            if np.abs(P[sl][:, 0]).max() < 5e-4:
                P[sl + (0,)] = 0.0
        i, j = np.meshgrid(np.arange(nu - 1), np.arange(nv - 1), indexing="ij")
        i, j = i.ravel(), j.ravel()
        idx = lambda ii, jj: ii * nv + jj  # noqa: E731
        F = np.stack([idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)], axis=1)
        # per-corner normals, evaluated slightly inside each face
        corners = [(0, 0), (1, 0), (1, 1), (0, 1)]
        ac = (a[i, j] + a[i + 1, j] + a[i + 1, j + 1] + a[i, j + 1]) / 4
        bc = (b[i, j] + b[i + 1, j] + b[i + 1, j + 1] + b[i, j + 1]) / 4
        NL = np.empty((len(F), 4, 3))
        for c, (di, dj) in enumerate(corners):
            av = a[i + di, j + dj] + du * (ac - a[i + di, j + dj])
            bv = b[i + di, j + dj] + du * (bc - b[i + di, j + dj])
            NL[:, c] = self._normal(av, bv)
        V = P.reshape(-1, 3)
        uvs = self._uv(P)
        flange = self._flange(P, G)
        NL = NL.reshape(-1, 3)
        hole_parts = []
        if self.holes:
            V, F, NL, hole_parts = self._cut_holes(G, V, F, NL)
            if flange is not None:
                flange = _prune_flange(flange, F)
        return dict(V=V, F=F, N=NL, grid=G, P=P, nu=nu, nv=nv, uv=uvs, flange=flange, holes=hole_parts,
                    plugs=getattr(self, "plugs", []))

    # --- openings ----------------------------------------------------------------------------------
    def _cut_holes(self, G, V, F, NL):
        """Remove faces inside the hole polygons (parameter space), snap the rim vertices onto the
        polygon outline and add a flange (return) around each opening."""
        nu, nv = G.shape[:2]
        a = G[..., 0].ravel()
        b = G[..., 1].ravel()
        pts = np.stack([a, b], axis=1)
        V = V.copy()
        # grid vertices on the mirror plane stay there whatever is snapped or offset below (they weld
        # with their mirror copies; 0.05 mm off the plane leaves a visible seam)
        on_plane0 = np.abs(V[:, 0]) < 1e-6
        fc = pts[F].mean(axis=1)                      # face centres in parameter space
        inside = np.zeros(len(F), bool)
        for poly in self.holes:
            inside |= _points_in_polygon(fc, poly)
        # a face on the panel border is removed only where the opening really crosses the border
        # (a notch, e.g. the tail-lamp opening or an opening continued across the mirror plane);
        # an opening that merely comes close keeps the border row, so the border flange and the
        # opening flange never share an edge
        fi, fj = F[:, 0] // nv, F[:, 0] % nv
        border_sides = ((fj == 0, (0, 1)), (fj == nv - 2, (3, 2)), (fi == 0, (0, 3)), (fi == nu - 2, (1, 2)))
        for on_side, (c0, c1) in border_sides:
            sel = inside & on_side
            if not sel.any():
                continue
            mid = (pts[F[sel, c0]] + pts[F[sel, c1]]) / 2
            crosses = np.zeros(len(mid), bool)
            for poly in self.holes:
                crosses |= _points_in_polygon(mid, poly)
            inside[np.nonzero(sel)[0][~crosses]] = False
        keep = ~inside
        F2, N2 = F[keep], NL.reshape(len(F), 4, 3)[keep].reshape(-1, 3)
        # boundary edges of the kept mesh, without the panel border (that one has the edge flange)
        e = np.sort(np.stack([F2, np.roll(F2, -1, axis=1)], axis=-1).reshape(-1, 2), axis=1)
        uniq, cnt = np.unique(e, axis=0, return_counts=True)
        bnd = uniq[cnt == 1]
        gi, gj = bnd // nv, bnd % nv
        on_border = (((gj[:, 0] == 0) & (gj[:, 1] == 0)) | ((gj[:, 0] == nv - 1) & (gj[:, 1] == nv - 1))
                     | ((gi[:, 0] == 0) & (gi[:, 1] == 0)) | ((gi[:, 0] == nu - 1) & (gi[:, 1] == nu - 1)))
        bnd = bnd[~on_border]
        # cell size in parameter space (for the rim tolerance)
        cell = np.median(np.linalg.norm(pts[F[:, 1]] - pts[F[:, 0]], axis=1)) + \
            np.median(np.linalg.norm(pts[F[:, 3]] - pts[F[:, 0]], axis=1))
        parts = []
        self.plugs = []
        hf = self.hole_flange
        flanges = list(hf) if hf and isinstance(hf[0], (tuple, list)) else [hf] * len(self.holes)
        Vg = V.reshape(nu, nv, 3)
        for hk, (poly, (r, depth)) in enumerate(zip(self.holes, flanges)):
            in_k = inside & _points_in_polygon(fc, poly)
            # a notch through a flanged border (the tail-lamp opening under the deck lid): the recess
            # rises to the surface over the last 30 mm before that border
            ramp = np.ones(len(V))
            for (on_side, _), side, ref in zip(border_sides, ("bottom", "top", "left", "right"),
                                              (Vg[:, :1], Vg[:, -1:], Vg[:1, :], Vg[-1:, :])):
                if self.flange_sides.get(side, True) and (in_k & on_side).any():
                    # distance to the nearest vertex of that border (smooth along the outline)
                    Bv = ref.reshape(-1, 3)
                    d = np.min(np.linalg.norm(V[:, None, :] - Bv[None, :, :], axis=-1), axis=1)
                    w = np.clip(d / 0.03, 0.0, 1.0)
                    ramp = np.minimum(ramp, np.maximum(w * w * (3 - 2 * w), 0.12))
            # rim edges: boundary edges whose endpoints lie inside the opening or next to its outline
            ins = _points_in_polygon(pts, poly)
            near = _dist_to_polygon(pts, poly) < 0.75 * cell
            ok = (ins | near)
            rim = bnd[ok[bnd[:, 0]] & ok[bnd[:, 1]]]
            if len(rim) == 0:
                self.plugs.append(None)
                continue
            idx = np.unique(rim.ravel())
            q = _closest_on_polygon(pts[idx], poly)
            Pq = self.surf.P(q[:, 0], q[:, 1])
            if self.offset is not None:
                Pq = Pq + self.offset(q[:, 0], q[:, 1])[..., None] * self.surf.N(q[:, 0], q[:, 1])
            V[idx] = Pq
            V[idx[on_plane0[idx]], 0] = 0.0
            pts[idx] = q
            chains = [np.array(L) for L in _chains(rim) if len(L) >= 3]
            if not chains:
                self.plugs.append(None)
                continue
            # a deep opening's tunnel runs straight back along the opening's mean normal (following
            # the local normals it would fan out up and down a curved fascia; openings across the
            # mirror plane keep it in the plane); a shallow recess (tail-lamp bezel, plate) simply
            # follows the local normal, parallel to the skin
            deep = depth >= 0.03
            Lall = np.concatenate(chains)
            D = self.surf.N(pts[Lall, 0], pts[Lall, 1]).mean(axis=0)
            if abs(D[1]) > 0.5:
                D = np.array([0.0, np.sign(D[1]), 0.0])     # front / rear face: straight along the car
            if (np.abs(V[Lall, 0]) < 1e-6).any():
                D[0] = 0.0
            D /= max(np.linalg.norm(D), 1e-12)
            end = {}
            for L in chains:
                E = V[L]
                Nn = self.surf.N(pts[L, 0], pts[L, 1])
                # away from the opening, perpendicular to the rim inside the tangent plane (the
                # direction from the rim's centroid runs along the rim at the corners of a long
                # opening)
                closed = len(L) > 3 and np.linalg.norm(E[0] - E[-1]) < 3 * np.median(
                    np.linalg.norm(np.diff(E, axis=0), axis=1))
                if closed:
                    T = np.roll(E, -1, axis=0) - np.roll(E, 1, axis=0)
                    t2 = np.roll(pts[L], -1, axis=0) - np.roll(pts[L], 1, axis=0)
                else:
                    T = np.gradient(E, axis=0)
                    t2 = np.gradient(pts[L], axis=0)
                out = np.cross(T, Nn)
                out /= np.maximum(np.linalg.norm(out, axis=-1, keepdims=True), 1e-9)
                n2 = np.stack([-t2[:, 1], t2[:, 0]], axis=1)
                n2 /= np.maximum(np.linalg.norm(n2, axis=1, keepdims=True), 1e-12)
                probe = _points_in_polygon(pts[L] + 1e-3 * n2, poly)     # n2 points into the opening?
                # orient out like the parameter normal n2 (mapped through the surface), then away
                a_, b_ = pts[L, 0], pts[L, 1]
                ea_ = 1e-4 * (self.surf.a_range[1] - self.surf.a_range[0])
                eb_ = 1e-4 * (self.surf.b_range[1] - self.surf.b_range[0])
                Pa_ = self.surf.P(a_ + ea_, b_) - self.surf.P(a_ - ea_, b_)
                Pb_ = self.surf.P(a_, b_ + eb_) - self.surf.P(a_, b_ - eb_)
                m3 = Pa_ * (n2[:, :1] / ea_) + Pb_ * (n2[:, 1:] / eb_)
                sgn = np.sign((out * m3).sum(-1))
                sgn[sgn == 0] = 1.0
                out *= (sgn * np.where(probe, -1.0, 1.0))[:, None]
                dk = depth * ramp[L][:, None]
                rk = np.minimum(r, dk)
                Dl = np.broadcast_to(D, Nn.shape) if deep else Nn
                R1 = E - Nn * rk + out * (0.3 * r)                 # rolled edge (local normal)
                R2 = R1 - Dl * (dk - rk) + out * (0.3 * r)        # wall
                on = np.abs(E[:, 0]) < 1e-6                 # chain end on the mirror plane
                R1[on, 0] = 0.0
                R2[on, 0] = 0.0
                parts.append(dict(loop=L, R1=R1, R2=R2, hole=hk, depth=depth))
                end.update({int(v): R2[k] - 0.003 * Dl[k] - 0.006 * out[k] for k, v in enumerate(L)})
            # plug: the removed faces of this opening moved back along the same direction, 3 mm behind
            # the end of its return flange; the rim vertices 6 mm inside the flange's end loop (a
            # closed recess for grilles / bezels; the two thicknesses never touch)
            fk = F[in_k]
            used = np.unique(fk)
            Dp = D[None, :] if deep else self.surf.N(pts[used, 0], pts[used, 1])
            Vp = V[used] - (depth * ramp[used] + 0.003)[:, None] * Dp
            for k, v in enumerate(used):
                if int(v) in end:
                    Vp[k] = end[int(v)]
            Vp[on_plane0[used], 0] = 0.0                    # stays on the mirror plane (welds there)
            remap = -np.ones(len(V), int)
            remap[used] = np.arange(len(used))
            self.plugs.append(dict(V=Vp, F=remap[fk]))
        return V, F2, N2, parts

    def _normal(self, a, b, e=2e-4):
        N = self.surf.N(a, b)
        if self.offset is None:
            return N
        # displaced surface: finite differences of P + offset * N
        def Q(aa, bb):
            return self.surf.P(aa, bb) + self.offset(aa, bb)[..., None] * self.surf.N(aa, bb)
        ea = e * (self.surf.a_range[1] - self.surf.a_range[0])
        eb = e * (self.surf.b_range[1] - self.surf.b_range[0])
        n = np.cross(Q(a + ea, b) - Q(a - ea, b), Q(a, b + eb) - Q(a, b - eb))
        n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-12)
        return np.where((n * N).sum(-1, keepdims=True) < 0, -n, n)

    def _uv(self, P):
        """Per-vertex UVs: normalised arc length along both grid directions (for paint flakes)."""
        du = np.linalg.norm(np.diff(P, axis=0), axis=-1)
        dv = np.linalg.norm(np.diff(P, axis=1), axis=-1)
        u = np.vstack([np.zeros((1, P.shape[1])), np.cumsum(du, axis=0)])
        v = np.hstack([np.zeros((P.shape[0], 1)), np.cumsum(dv, axis=1)])
        return np.stack([u, v], axis=-1).reshape(-1, 2)

    def _flange(self, P, G):
        """Rolled edge + flange ring under the panel border: returns (V, F, N) or None."""
        r, depth = self.flange
        if depth <= 0:
            return None
        nu, nv = P.shape[:2]
        # border loop (counter-clockwise in (i, j)): bottom row, right column, top row reversed, left reversed
        loop = ([(i, 0) for i in range(nu)] + [(nu - 1, j) for j in range(1, nv)]
                + [(i, nv - 1) for i in range(nu - 2, -1, -1)] + [(0, j) for j in range(nv - 2, 0, -1)])
        ii = np.array([p[0] for p in loop])
        jj = np.array([p[1] for p in loop])
        E = P[ii, jj]
        a, b = G[ii, jj, 0], G[ii, jj, 1]
        N = self._normal(a, b)
        # inward direction in the tangent plane: towards the nearest interior grid point (the panel
        # centroid is wrong for panels wrapped around an opening, e.g. the fender over the arch)
        towards = P[np.clip(ii, 1, nu - 2), np.clip(jj, 1, nv - 2)] - E
        towards -= (towards * N).sum(-1, keepdims=True) * N
        towards /= np.maximum(np.linalg.norm(towards, axis=-1, keepdims=True), 1e-9)
        R1 = E - N * r + towards * (0.3 * r)            # rolled edge
        R2 = E - N * depth + towards * (0.8 * r)        # flange bottom
        # border vertices on the mirror plane: keep the flange in the plane, so it welds with its
        # mirror copy (no bow-tie vertex at x = 0)
        on = np.abs(E[:, 0]) < 1e-6
        R1[on, 0] = 0.0
        R2[on, 0] = 0.0
        V = np.vstack([R1, R2])
        m = len(loop)
        k = np.arange(m)
        k1 = (k + 1) % m
        # faces: border row (from the panel mesh indices) -> R1 -> R2; panel vertex index = i * nv + j
        pv = ii * nv + jj
        # which loop edges get a flange (per side; e.g. not along a mirror plane)
        side_of = (["bottom"] * (nu - 1) + ["right"] * (nv - 1) + ["top"] * (nu - 1) + ["left"] * (nv - 1))
        on = np.array([self.flange_sides.get(sd, True) for sd in side_of])
        # winding: the border loop runs counter-clockwise seen from outside, so (k1, k) faces outwards
        F1 = np.stack([pv[k1], pv[k], k + 0, k1 + 0], axis=1)[on]   # columns 2-3 index the ring block
        F2 = np.stack([k1 + 0, k + 0, k + m, k1 + m], axis=1)[on]
        return dict(V=V, ring=pv, F_border=F1, F_flange=F2, m=m)


def _prune_flange(fl, F):
    """Drop the border-flange faces whose panel edge no longer belongs to a panel face (the border
    inside a notch opening)."""
    e = np.sort(np.stack([F, np.roll(F, -1, axis=1)], axis=-1).reshape(-1, 2), axis=1)
    have = set(map(tuple, e))
    fb = np.sort(fl["F_border"][:, :2], axis=1)
    ok = np.array([tuple(x) in have for x in fb], bool)
    return dict(fl, F_border=fl["F_border"][ok], F_flange=fl["F_flange"][ok])


def panel_to_arrays(mesh, with_flange=True, kinds=False):
    """(V, F, N_loops) of a panel mesh including its edge flange and opening flanges; with
    kinds=True also K (per face): 0 skin, 1 edge flange, 2 opening roll, 3 opening wall, and D
    (per face): the depth of the opening a wall belongs to (0 elsewhere)."""
    V, F, N = mesh["V"], mesh["F"], mesh["N"]
    Vall, Fall, Nall = [V], [F], [N]
    Kall, Dall = [np.zeros(len(F), int)], [np.zeros(len(F))]
    nV = len(V)

    def face_normals(VV, FF):
        p = VV[FF]
        n = np.cross(p[:, 1] - p[:, 0], p[:, 3] - p[:, 0]) + np.cross(p[:, 2] - p[:, 1], p[:, 0] - p[:, 1])
        return n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-12)

    fl = mesh.get("flange")
    if with_flange and fl is not None and len(fl["F_border"]):
        Fb = fl["F_border"].copy()
        Fb[:, 2:] += nV
        Ff = fl["F_flange"] + nV
        Vcat = np.vstack([V, fl["V"]])
        Vall.append(fl["V"])
        Fall += [Fb, Ff]
        Nall += [np.repeat(face_normals(Vcat, Fb), 4, axis=0), np.repeat(face_normals(Vcat, Ff), 4, axis=0)]
        Kall += [np.ones(len(Fb), int), np.ones(len(Ff), int)]
        Dall += [np.zeros(len(Fb)), np.zeros(len(Ff))]
        nV += len(fl["V"])
    for hp in (mesh.get("holes") or []) if with_flange else []:
        L, R1, R2 = hp["loop"], hp["R1"], hp["R2"]
        n = len(L)
        E = V[L]
        closed = np.linalg.norm(E[0] - E[-1]) < 3 * np.median(np.linalg.norm(np.diff(E, axis=0), axis=1))
        k = np.arange(n if closed else n - 1)
        k1 = (k + 1) % n
        base = nV
        Fh1 = np.stack([L[k], L[k1], base + k1, base + k], axis=1)
        Fh2 = np.stack([base + k, base + k1, base + n + k1, base + n + k], axis=1)
        Vcat = np.vstack([np.vstack(Vall), R1, R2])
        # orient the walls towards the opening's centre
        cen = E.mean(axis=0)
        nh = face_normals(Vcat, Fh1)
        fc = Vcat[Fh1].mean(axis=1)
        if np.mean(((cen - fc) * nh).sum(-1)) < 0:
            Fh1, Fh2 = Fh1[:, ::-1], Fh2[:, ::-1]
        Vall += [R1, R2]
        Fall += [Fh1, Fh2]
        Nall += [np.repeat(face_normals(Vcat, Fh1), 4, axis=0), np.repeat(face_normals(Vcat, Fh2), 4, axis=0)]
        Kall += [np.full(len(Fh1), 2), np.full(len(Fh2), 3)]
        Dall += [np.zeros(len(Fh1)), np.full(len(Fh2), float(hp.get("depth", 0.0)))]
        nV += 2 * n
    if kinds:
        return np.vstack(Vall), np.vstack(Fall), np.vstack(Nall), np.concatenate(Kall), np.concatenate(Dall)
    return np.vstack(Vall), np.vstack(Fall), np.vstack(Nall)


def _points_in_polygon(pts, poly):
    """Even-odd test, vectorised over points."""
    x, y = pts[:, 0][:, None], pts[:, 1][:, None]
    px, py = poly[:, 0][None, :], poly[:, 1][None, :]
    qx, qy = np.roll(poly[:, 0], -1)[None, :], np.roll(poly[:, 1], -1)[None, :]
    cond = (py > y) != (qy > y)
    with np.errstate(divide="ignore", invalid="ignore"):
        xin = (qx - px) * (y - py) / (qy - py) + px
    return (cond & (x < xin)).sum(axis=1) % 2 == 1


def _dist_to_polygon(pts, poly):
    return np.linalg.norm(_closest_on_polygon(pts, poly) - pts, axis=1)


def _chains(edges):
    """Split an edge list into ordered vertex chains (closed chains repeat no vertex)."""
    from collections import defaultdict
    adj = defaultdict(list)
    for u, v in edges:
        adj[int(u)].append(int(v))
        adj[int(v)].append(int(u))
    seen_e = set()
    out = []
    # start open chains at endpoints, then closed loops anywhere
    starts = [u for u in adj if len(adj[u]) != 2] + list(adj)
    for s0 in starts:
        for v0 in adj[s0]:
            if (min(s0, v0), max(s0, v0)) in seen_e:
                continue
            chain = [s0]
            prev, cur = s0, v0
            seen_e.add((min(s0, v0), max(s0, v0)))
            while True:
                chain.append(cur)
                if cur == s0:
                    chain.pop()
                    break
                nxt = [w for w in adj[cur] if (min(cur, w), max(cur, w)) not in seen_e]
                if len(adj[cur]) != 2 or not nxt:
                    break
                w = nxt[0]
                seen_e.add((min(cur, w), max(cur, w)))
                prev, cur = cur, w
            out.append(chain)
    return out


def _closest_on_polygon(pts, poly):
    a = poly
    b = np.roll(poly, -1, axis=0)
    ab = b - a
    t = ((pts[:, None, :] - a[None]) * ab[None]).sum(-1) / np.maximum((ab * ab).sum(-1)[None], 1e-18)
    t = np.clip(t, 0, 1)
    c = a[None] + t[..., None] * ab[None]
    d = np.linalg.norm(c - pts[:, None, :], axis=-1)
    k = np.argmin(d, axis=1)
    return c[np.arange(len(pts)), k]


def _boundary_loop(F, rim):
    """Longest closed (or open) chain of boundary edges whose vertices are all in `rim`."""
    from collections import defaultdict
    cnt = defaultdict(int)
    for f in F:
        for k in range(4):
            e = (min(f[k], f[(k + 1) % 4]), max(f[k], f[(k + 1) % 4]))
            cnt[e] += 1
    adj = defaultdict(list)
    for (u, v), c in cnt.items():
        if c == 1 and u in rim and v in rim:
            adj[u].append(v)
            adj[v].append(u)
    if not adj:
        return None
    seen, best = set(), []
    for start in adj:
        if start in seen:
            continue
        # walk from an endpoint if the chain is open
        comp = [start]
        stack = [start]
        seen_c = {start}
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if v not in seen_c:
                    seen_c.add(v)
                    stack.append(v)
                    comp.append(v)
        seen |= seen_c
        ends = [u for u in comp if len(adj[u]) == 1]
        cur = ends[0] if ends else comp[0]
        order, prev = [cur], None
        while True:
            nxt = [v for v in adj[cur] if v != prev and v not in order]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            order.append(cur)
        if len(order) > len(best):
            best = order
    return best
