"""Fast mesh creation from numpy arrays (Blender side) and structured-grid helpers (pure numpy)."""
import numpy as np


def grid_faces(nu, nv, offset=0, flip=False):
    """Quad faces of an nu x nv vertex grid stored row-major (index = i * nv + j)."""
    i, j = np.meshgrid(np.arange(nu - 1), np.arange(nv - 1), indexing="ij")
    a = i * nv + j
    q = np.stack([a, a + nv, a + nv + 1, a + 1], axis=-1).reshape(-1, 4) + offset
    return q[:, ::-1] if flip else q


def mirror_x(verts, faces):
    """Left-half copy of a right-half part: x -> -x with reversed winding."""
    v = verts.copy()
    v[:, 0] *= -1.0
    return v, faces[:, ::-1]


def weld_mirror_pairs(verts, faces, n_right, tol=1e-6):
    """After merge([(right), (mirror_x(right))]): join every right-half vertex lying on x = 0 with
    its own mirror copy (index n_right + i). Only these pairs are merged (never other coincident
    vertices such as loft poles), so no face degenerates and the loop order (custom normals) is
    kept. Returns (verts, faces) without the redundant copies."""
    faces = np.asarray(faces)
    on = np.nonzero(np.abs(verts[:n_right, 0]) < tol)[0]
    if not len(on):
        return verts, faces
    remap = np.arange(len(verts))
    remap[n_right + on] = on
    keep = np.ones(len(verts), bool)
    keep[n_right + on] = False
    new_index = np.cumsum(keep) - 1
    return verts[keep], new_index[remap[faces]]


def merge(parts):
    """[(verts, faces), ...] -> (verts, faces) with offset indices."""
    vs, fs, off = [], [], 0
    for v, f in parts:
        vs.append(v)
        fs.append(np.asarray(f) + off)
        off += len(v)
    return np.vstack(vs), np.vstack(fs)


def weld(verts, faces, tol=1e-6):
    """Merge coincident vertices (e.g. along the centreline after mirroring)."""
    key = np.round(verts / tol).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.ravel()
    order = np.argsort(first)
    remap = np.empty_like(order)
    remap[order] = np.arange(len(order))
    new_verts = verts[first[order]]
    new_faces = remap[inv[faces]]
    # drop faces that collapsed
    ok = np.array([len(set(f)) == len(f) for f in new_faces])
    return new_verts, new_faces[ok]


def rounded_rect(w, h, r, n_corner=8):
    """Closed polygon (m, 2) of a w x h rectangle centred at the origin with corner radius r."""
    r = min(r, w / 2 - 1e-6, h / 2 - 1e-6)
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0.0), (-w / 2 + r, h / 2 - r, 90.0),
                       (-w / 2 + r, -h / 2 + r, 180.0), (w / 2 - r, -h / 2 + r, 270.0)):
        for a in np.radians(np.linspace(a0, a0 + 90.0, n_corner)):
            pts.append((cx + r * np.cos(a), cy + r * np.sin(a)))
    return np.array(pts)


def prism(poly, depth, bevel=0.0):
    """Extrude a closed 2D polygon (in the local XY plane) from z = 0 to z = -depth.
    Returns (V, faces) with ngon caps (faces is a list of index lists)."""
    poly = np.asarray(poly, float)
    n = len(poly)
    top = np.c_[poly, np.zeros(n)]
    if bevel > 0:
        c = poly.mean(axis=0)
        shrink = poly + (c - poly) * (bevel / np.maximum(np.linalg.norm(c - poly, axis=1, keepdims=True), 1e-9))
        top_in = np.c_[shrink, np.full(n, bevel * 0.5)]
        bot = np.c_[poly, np.full(n, -depth)]
        V = np.vstack([top_in, top, bot])
        faces = [list(range(n))[::-1]]
        faces += [[k, (k + 1) % n, n + (k + 1) % n, n + k][::-1] for k in range(n)]
        faces += [[n + k, n + (k + 1) % n, 2 * n + (k + 1) % n, 2 * n + k][::-1] for k in range(n)]
        faces += [list(range(2 * n, 3 * n))]
        return V, faces
    bot = np.c_[poly, np.full(n, -depth)]
    V = np.vstack([top, bot])
    faces = [list(range(n))[::-1]]
    faces += [[k, (k + 1) % n, n + (k + 1) % n, n + k][::-1] for k in range(n)]
    faces += [list(range(n, 2 * n))]
    return V, faces


def frame(origin, x_axis, y_axis):
    """Local -> world transform for points in a plane frame (z along x_axis x y_axis)."""
    o = np.asarray(origin, float)
    ex = np.asarray(x_axis, float)
    ex = ex / np.linalg.norm(ex)
    ey = np.asarray(y_axis, float)
    ey = ey - ex * np.dot(ex, ey)
    ey = ey / np.linalg.norm(ey)
    ez = np.cross(ex, ey)
    M = np.stack([ex, ey, ez], axis=1)
    return lambda P: o + np.asarray(P, float) @ M.T


def to_blender_ngons(name, verts, faces, col=None, smooth=False, replace=True, auto_smooth_deg=None):
    """Mesh object from vertices and a list of variable-size faces."""
    import bpy
    from .blend_util import remove_object
    if replace:
        remove_object(name)
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in verts], [], [list(map(int, f)) for f in faces])
    me.validate(clean_customdata=False)
    me.update()
    for p in me.polygons:
        p.use_smooth = smooth
    obj = bpy.data.objects.new(name, me)
    (col or bpy.context.scene.collection).objects.link(obj)
    if auto_smooth_deg is not None:
        try:
            with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj],
                                           selected_editable_objects=[obj]):
                bpy.ops.object.shade_smooth_by_angle(angle=np.radians(auto_smooth_deg))
        except Exception:
            pass
    return obj


def to_blender(name, verts, faces, col=None, normals=None, uv=None, smooth=True, replace=True, mat_idx=None):
    """Create (or replace) a mesh object from numpy arrays.

    normals: optional per-loop normals (n_faces * 4, 3) in face-corner order (custom split normals).
    uv: optional per-loop UVs (n_faces * 4, 2)."""
    import bpy
    from .blend_util import remove_object
    if replace:
        remove_object(name)
    verts = np.asarray(verts, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    # never hand degenerate polygons (repeated corners) to Blender: custom normals crash on them
    srt = np.sort(faces, axis=1)
    ok = (np.diff(srt, axis=1) != 0).all(axis=1) & (faces.min(axis=1) >= 0) & (faces.max(axis=1) < len(verts))
    if not ok.all():
        nl = faces.shape[1]
        faces = faces[ok]
        if normals is not None:
            normals = np.asarray(normals).reshape(-1, nl, 3)[ok].reshape(-1, 3)
        if uv is not None:
            uv = np.asarray(uv).reshape(-1, nl, 2)[ok].reshape(-1, 2)
        if mat_idx is not None:
            mat_idx = np.asarray(mat_idx)[ok]
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.astype(np.float32).ravel())
    nl = faces.shape[1]
    me.loops.add(len(faces) * nl)
    me.loops.foreach_set("vertex_index", faces.astype(np.int32).ravel())
    me.polygons.add(len(faces))
    me.polygons.foreach_set("loop_start", (np.arange(len(faces)) * nl).astype(np.int32))
    me.polygons.foreach_set("loop_total", np.full(len(faces), nl, dtype=np.int32))
    me.update(calc_edges=True)
    me.polygons.foreach_set("use_smooth", np.full(len(faces), smooth, dtype=bool))
    if mat_idx is not None:
        me.polygons.foreach_set("material_index", np.asarray(mat_idx, dtype=np.int32))
    if uv is not None:
        layer = me.uv_layers.new(name="UVMap")
        layer.data.foreach_set("uv", np.asarray(uv, dtype=np.float32).ravel())
    me.validate(clean_customdata=False)
    me.update()
    if normals is not None:
        nrm = np.asarray(normals, dtype=np.float32).reshape(-1, 3)
        if len(nrm) == len(me.loops) and np.isfinite(nrm).all():
            me.normals_split_custom_set(nrm.tolist())
            me.update()
    obj = bpy.data.objects.new(name, me)
    (col or bpy.context.scene.collection).objects.link(obj)
    return obj
