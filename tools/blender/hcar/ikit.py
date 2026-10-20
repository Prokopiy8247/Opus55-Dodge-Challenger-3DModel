"""Mesh kit for the interior (pure numpy, except to_blender_poly): mixed quad/triangle builder,
lofts, sweeps with parallel-transport frames, lathes, caps, stitch dashes, planar UVs and
angle-based sharp edges (no operators)."""
import numpy as np


class Builder:
    """Accumulates vertices and polygons (quads and triangles) with a material slot and optional
    per-vertex UVs."""

    def __init__(self):
        self.V, self.F, self.M, self.UV = [], [], [], []
        self.n = 0

    def add(self, V, F, mat=0, uv=None):
        V = np.asarray(V, float).reshape(-1, 3)
        uv = np.zeros((len(V), 2)) if uv is None else np.asarray(uv, float).reshape(-1, 2)
        for f in F:
            self.F.append([int(i) + self.n for i in f])
            self.M.append(mat)
        self.V.append(V)
        self.UV.append(uv)
        self.n += len(V)
        return self

    def merge(self, other, mat_map=None):
        V, F, M, UV = other.arrays()
        mm = [mat_map.get(m, m) if mat_map else m for m in M]
        base = self.n
        self.V.append(V)
        self.UV.append(UV)
        for f, m in zip(F, mm):
            self.F.append([i + base for i in f])
            self.M.append(m)
        self.n += len(V)
        return self

    def transform(self, fn):
        self.V = [fn(v) for v in self.V]
        return self

    def arrays(self):
        V = np.vstack(self.V) if self.V else np.zeros((0, 3))
        UV = np.vstack(self.UV) if self.UV else np.zeros((0, 2))
        return V, self.F, self.M, UV

    def mirrored_x(self):
        """Copy mirrored to the other side (x -> -x, winding reversed)."""
        out = Builder()
        for V, uv in zip(self.V, self.UV):
            out.V.append(V * np.array([-1.0, 1.0, 1.0]))
            out.UV.append(uv)
        out.F = [f[::-1] for f in self.F]
        out.M = list(self.M)
        out.n = self.n
        return out


# ------------------------------------------------------------------------------------------------
# surfaces
# ------------------------------------------------------------------------------------------------
def loft(S, closed_sec=True, closed_path=False):
    """Sections S (m, n, 3) -> (V, quads). Face winding: i along the path, j along the section; the
    normal is (dP/di) x (dP/dj) ... reversed by the caller with flip() when needed."""
    S = np.asarray(S, float)
    m, n = S.shape[:2]
    V = S.reshape(-1, 3)
    F = []
    jm = n if closed_sec else n - 1
    im = m if closed_path else m - 1
    for i in range(im):
        i1 = (i + 1) % m
        for j in range(jm):
            j1 = (j + 1) % n
            F.append([i * n + j, i * n + j1, i1 * n + j1, i1 * n + j])
    return V, F


def flip(F):
    return [f[::-1] for f in F]


def cap(V, idx, toward=None, rings=3):
    """Close a loop of vertex indices idx: (rings - 1) inner rings of quads shrinking towards the
    centroid, then a small triangle fan (smooth shading without the long-fan 'X' pattern).
    toward: optional direction the cap normal must point to. Returns (V_new, faces)."""
    P = V[idx]
    c = P.mean(axis=0)
    n = len(idx)
    k = len(V)
    blocks, F = [V], []
    prev = list(idx)
    for r in range(1, rings):
        s = (rings - r) / rings
        ids = list(range(k, k + n))
        blocks.append(c + (P - c) * s)
        k += n
        F += [[prev[t], ids[t], ids[(t + 1) % n], prev[(t + 1) % n]] for t in range(n)]
        prev = ids
    blocks.append(c[None])
    F += [[k, prev[(t + 1) % n], prev[t]] for t in range(n)]
    V2 = np.vstack(blocks)
    if toward is not None:
        a, b, cc = V2[F[-1]]
        if np.dot(np.cross(b - a, cc - a), toward) < 0:
            F = flip(F)
    return V2, F


def closed_loft(S, cap_ends=True):
    """Loft of closed sections with fan caps at both ends; outward winding checked numerically."""
    S = np.asarray(S, float)
    m, n = S.shape[:2]
    V, F = loft(S, closed_sec=True)
    # orient the side wall outwards: compare with the direction from the axis to the section
    c0 = S.mean(axis=1)
    f = F[len(F) // 2]
    a, b, c = V[f[0]], V[f[1]], V[f[2]]
    nrm = np.cross(b - a, c - a)
    i = (f[0] // n)
    if np.dot(nrm, a - c0[i]) < 0:
        F = flip(F)
    if cap_ends:
        d0 = c0[0] - c0[1]
        V, F0 = cap(V, list(range(n)), toward=d0)
        d1 = c0[-1] - c0[-2]
        V, F1 = cap(V, list(range((m - 1) * n, m * n)), toward=d1)
        F = F + F0 + F1
    return V, F


def frames(path, up=(0.0, 0.0, 1.0), closed=False):
    """Parallel-transport frames (T, N, B) along a polyline (m, 3)."""
    P = np.asarray(path, float)
    m = len(P)
    if closed:
        T = np.roll(P, -1, axis=0) - np.roll(P, 1, axis=0)
    else:
        T = np.gradient(P, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    up = np.asarray(up, float)
    N = np.zeros_like(P)
    n0 = up - T[0] * np.dot(up, T[0])
    if np.linalg.norm(n0) < 1e-6:
        n0 = np.cross(T[0], [1.0, 0.0, 0.0])
    N[0] = n0 / np.linalg.norm(n0)
    for i in range(1, m):
        v = N[i - 1] - T[i] * np.dot(N[i - 1], T[i])
        N[i] = v / max(np.linalg.norm(v), 1e-12)
    B = np.cross(T, N)
    return T, N, B


def sweep(path, profile, up=(0.0, 0.0, 1.0), closed_path=False, cap_ends=True, scale=None):
    """Closed 2D profile (n, 2) in the (N, B) plane swept along path (m, 3). scale: optional (m,)
    or (m, 2) factors. Returns (V, F) with outward winding (and fan caps on open paths)."""
    P = np.asarray(path, float)
    T, N, B = frames(P, up, closed_path)
    prof = np.asarray(profile, float)
    m = len(P)
    if scale is None:
        sc = np.ones((m, 2))
    else:
        sc = np.asarray(scale, float)
        sc = np.stack([sc, sc], axis=1) if sc.ndim == 1 else sc
    S = P[:, None, :] + (prof[None, :, 0:1] * sc[:, None, 0:1]) * N[:, None, :] + \
        (prof[None, :, 1:2] * sc[:, None, 1:2]) * B[:, None, :]
    if closed_path:
        V, F = loft(S, closed_sec=True, closed_path=True)
        # outward: normal points away from the path
        f = F[0]
        nrm = np.cross(V[f[1]] - V[f[0]], V[f[2]] - V[f[0]])
        if np.dot(nrm, V[f[0]] - P[0]) < 0:
            F = flip(F)
        return V, F
    return closed_loft(S, cap_ends=cap_ends)


def lathe(profile, centre, axis, n=48, ref=None, a0=0.0, a1=2 * np.pi, close=True):
    """Surface of revolution of profile [(axial, radius), ...] about axis through centre."""
    axis = np.asarray(axis, float) / np.linalg.norm(axis)
    ref = np.asarray(ref if ref is not None else ([0, 0, 1.0] if abs(axis[2]) < 0.9 else [1.0, 0, 0]), float)
    u = ref - axis * np.dot(ref, axis)
    u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    prof = np.asarray(profile, float)
    full = close and abs((a1 - a0) - 2 * np.pi) < 1e-9
    ang = np.linspace(a0, a1, n, endpoint=not full)
    S = np.asarray(centre, float) + prof[None, :, 0:1] * axis + prof[None, :, 1:2] * (
        np.cos(ang)[:, None, None] * u + np.sin(ang)[:, None, None] * v)
    V, F = loft(S, closed_sec=False, closed_path=full)
    # winding: outward from the axis on the first band
    f = F[0]
    nrm = np.cross(V[f[1]] - V[f[0]], V[f[2]] - V[f[0]])
    rad = V[f[0]] - np.asarray(centre) - axis * np.dot(V[f[0]] - np.asarray(centre), axis)
    if np.linalg.norm(rad) > 1e-9 and np.dot(nrm, rad) < 0:
        F = flip(F)
    return V, F


def disc(centre, axis, r, n=48, ref=None, uv=True):
    """Flat disc facing +axis (triangle fan) with planar UVs in [0, 1]."""
    axis = np.asarray(axis, float) / np.linalg.norm(axis)
    ref = np.asarray(ref if ref is not None else ([0, 0, 1.0] if abs(axis[2]) < 0.9 else [0, 1.0, 0]), float)
    up = ref - axis * np.dot(ref, axis)
    up /= np.linalg.norm(up)
    right = np.cross(up, axis)
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = np.asarray(centre) + r * (np.sin(a)[:, None] * right + np.cos(a)[:, None] * up)
    V = np.vstack([ring, centre])
    F = [[n, (k + 1) % n, k] for k in range(n)]
    nrm = np.cross(V[F[0][1]] - V[F[0][0]], V[F[0][2]] - V[F[0][0]])
    if np.dot(nrm, axis) < 0:
        F = flip(F)
    UV = np.vstack([np.c_[0.5 + 0.5 * np.sin(a), 0.5 + 0.5 * np.cos(a)], [0.5, 0.5]])
    return V, F, UV


def quad(centre, right, up, w, h, nu=1, nv=1):
    """Planar w x h grid facing right x up, UVs in [0, 1]."""
    right = np.asarray(right, float) / np.linalg.norm(right)
    up = np.asarray(up, float) / np.linalg.norm(up)
    us, vs = np.linspace(-0.5, 0.5, nu + 1), np.linspace(-0.5, 0.5, nv + 1)
    V = np.array([np.asarray(centre) + u * w * right + v * h * up for v in vs for u in us])
    UV = np.array([(u + 0.5, v + 0.5) for v in vs for u in us])
    F = [[j * (nu + 1) + i, j * (nu + 1) + i + 1, (j + 1) * (nu + 1) + i + 1, (j + 1) * (nu + 1) + i]
         for j in range(nv) for i in range(nu)]
    return V, F, UV


def box(c, size, axes=None):
    """Oriented box (6 quads)."""
    c = np.asarray(c, float)
    ax = np.eye(3) if axes is None else np.asarray(axes, float)
    h = np.asarray(size, float) / 2
    corners = np.array([(sx, sy, sz) for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)], float)
    V = c + (corners * h) @ ax
    F = [[0, 2, 3, 1], [4, 5, 7, 6], [0, 1, 5, 4], [2, 6, 7, 3], [0, 4, 6, 2], [1, 3, 7, 5]]
    return V, F


def rounded_box(c, size, r, axes=None, n=4):
    """Box with rounded vertical edges and a rounded top/bottom edge, as a lofted superellipse stack."""
    c = np.asarray(c, float)
    ax = np.eye(3) if axes is None else np.asarray(axes, float)
    sx, sy, sz = (s / 2 for s in size)
    from .meshkit import rounded_rect
    zs = []
    for k in range(n + 1):
        a = -np.pi / 2 + np.pi * k / n
        zs.append((np.sin(a) * sz, np.cos(a)))
    S = []
    for z, f in zs:
        inset = r * (1 - f)
        rr = rounded_rect(2 * max(sx - inset, 1e-4), 2 * max(sy - inset, 1e-4), max(r - inset, 1e-4) if r > inset else 1e-4, 6)
        S.append(np.c_[rr, np.full(len(rr), z)])
    S = np.array(S)
    V, F = closed_loft(S)
    return c + V @ ax, F


def superellipse(a, b, p=4.0, n=32):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    x = a * np.sign(np.cos(t)) * np.abs(np.cos(t)) ** (2 / p)
    y = b * np.sign(np.sin(t)) * np.abs(np.sin(t)) ** (2 / p)
    return np.c_[x, y]


def resample(P, n, closed=False):
    """Polyline resampled to n points by arc length."""
    P = np.asarray(P, float)
    if closed:
        P = np.vstack([P, P[:1]])
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    t = np.linspace(0, s[-1], n + (1 if closed else 0))
    out = np.stack([np.interp(t, s, P[:, k]) for k in range(P.shape[1])], axis=1)
    return out[:-1] if closed else out


def stitches(path, normal_fn, pitch=0.008, length=0.0045, width=0.0011, lift=0.0006):
    """Dashed stitch line along a polyline: one quad per dash lying on the surface (normal_fn(p)
    gives the outward surface normal at p)."""
    P = np.asarray(path, float)
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    V, F = [], []
    t = pitch / 2
    while t + length < s[-1]:
        a = np.array([np.interp(t, s, P[:, k]) for k in range(3)])
        b = np.array([np.interp(t + length, s, P[:, k]) for k in range(3)])
        nrm = np.asarray(normal_fn((a + b) / 2), float)
        nrm /= max(np.linalg.norm(nrm), 1e-12)
        d = b - a
        side = np.cross(nrm, d)
        side *= width / 2 / max(np.linalg.norm(side), 1e-12)
        k = len(V)
        V += [a - side + lift * nrm, b - side + lift * nrm, b + side + lift * nrm, a + side + lift * nrm]
        F.append([k, k + 1, k + 2, k + 3])
        t += pitch
    if not V:
        return np.zeros((0, 3)), []
    V = np.array(V)
    # winding facing the normal
    f = F[0]
    nrm = np.cross(V[f[1]] - V[f[0]], V[f[2]] - V[f[0]])
    if np.dot(nrm, normal_fn(V[0])) < 0:
        F = flip(F)
    return V, F


def offset_surface_grid(G, d):
    """Offset a structured grid (nu, nv, 3) along its numeric normals by d."""
    du = np.gradient(G, axis=0)
    dv = np.gradient(G, axis=1)
    N = np.cross(du, dv)
    N /= np.maximum(np.linalg.norm(N, axis=-1, keepdims=True), 1e-12)
    return G + d * N, N


# ------------------------------------------------------------------------------------------------
# Blender
# ------------------------------------------------------------------------------------------------
def sharp_by_angle(me, angle_deg):
    """Mark edges sharper than angle_deg as sharp (attribute sharp_edge) and shade all faces smooth."""
    import bpy  # noqa: F401
    npoly = len(me.polygons)
    if not npoly:
        return
    pn = np.empty(npoly * 3, np.float32)
    me.polygons.foreach_get("normal", pn)
    pn = pn.reshape(-1, 3)
    le = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("edge_index", le)
    ls = np.empty(npoly, np.int32)
    lt = np.empty(npoly, np.int32)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    poly_of_loop = np.repeat(np.arange(npoly), lt)
    ne = len(me.edges)
    first = np.full(ne, -1, np.int64)
    second = np.full(ne, -1, np.int64)
    order = np.argsort(le, kind="stable")
    le_s, pl_s = le[order], poly_of_loop[order]
    starts = np.r_[0, np.nonzero(np.diff(le_s))[0] + 1]
    counts = np.diff(np.r_[starts, len(le_s)])
    e_ids = le_s[starts]
    first[e_ids] = pl_s[starts]
    has2 = counts >= 2
    second[e_ids[has2]] = pl_s[starts[has2] + 1]
    sharp = np.zeros(ne, bool)
    both = (first >= 0) & (second >= 0)
    cosang = np.einsum("ij,ij->i", pn[first[both]], pn[second[both]])
    sharp[np.nonzero(both)[0]] = cosang < np.cos(np.radians(angle_deg))
    sharp |= counts_full(ne, e_ids, counts) > 2
    attr = me.attributes.get("sharp_edge") or me.attributes.new("sharp_edge", "BOOLEAN", "EDGE")
    attr.data.foreach_set("value", sharp)
    me.polygons.foreach_set("use_smooth", np.ones(npoly, bool))


def counts_full(ne, e_ids, counts):
    c = np.zeros(ne, np.int64)
    c[e_ids] = counts
    return c


def to_blender_poly(name, V, F, col=None, mats=None, mat_idx=None, uv=None, smooth_deg=40.0, replace=True):
    """Mesh object from vertices and variable-size polygons. uv: per-vertex UVs (n, 2) or None.
    smooth_deg: None for flat shading, else smooth with edges sharper than this angle kept hard."""
    import bpy
    from .blend_util import remove_object
    if replace:
        remove_object(name)
    V = np.asarray(V, float)
    keep = [len(set(f)) == len(f) for f in F]
    F = [list(map(int, f)) for f, k in zip(F, keep) if k]
    if mat_idx is not None:
        mat_idx = [m for m, k in zip(mat_idx, keep) if k]
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(V))
    me.vertices.foreach_set("co", V.astype(np.float32).ravel())
    lt = np.array([len(f) for f in F], np.int32)
    ls = np.r_[0, np.cumsum(lt)[:-1]].astype(np.int32)
    flat = np.array([i for f in F for i in f], np.int32)
    me.loops.add(len(flat))
    me.loops.foreach_set("vertex_index", flat)
    me.polygons.add(len(F))
    me.polygons.foreach_set("loop_start", ls)
    me.polygons.foreach_set("loop_total", lt)
    me.update(calc_edges=True)
    if mat_idx is not None:
        mi = np.asarray(mat_idx, np.int32)
        if len(mi) == len(F):
            me.polygons.foreach_set("material_index", mi)
    if uv is not None:
        layer = me.uv_layers.new(name="UVMap")
        layer.data.foreach_set("uv", np.asarray(uv, np.float32)[flat].ravel())
    me.validate(clean_customdata=False)
    me.update()
    if smooth_deg is not None:
        sharp_by_angle(me, smooth_deg)
    obj = bpy.data.objects.new(name, me)
    (col or bpy.context.scene.collection).objects.link(obj)
    for m in (mats or []):
        obj.data.materials.append(m)
    return obj
