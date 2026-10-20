"""Mesh diagnostics used while fixing G-Model findings (non-manifold edges, winding, visibility)."""
import bpy
import numpy as np


def _eval_arrays(o, dg=None):
    dg = dg or bpy.context.evaluated_depsgraph_get()
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    ev = np.empty(len(me.edges) * 2, np.int32)
    me.edges.foreach_get("vertices", ev)
    le = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("edge_index", le)
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    ls = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_total", lt)
    oe.to_mesh_clear()
    M = np.array(o.matrix_world)
    co = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    return co, ev.reshape(-1, 2), le, lv, ls, lt


def nonmanifold(name, evaluated=True, limit=40):
    """Edge face-count histogram and the positions of edges whose face count is not 2."""
    o = bpy.data.objects[name]
    if evaluated:
        co, ev, le, lv, ls, lt = _eval_arrays(o)
    else:
        me = o.data
        co = np.array([o.matrix_world @ v.co for v in me.vertices])
        ev = np.array([e.vertices[:] for e in me.edges])
        le = np.array([lp.edge_index for lp in me.loops])
        lv = np.array([lp.vertex_index for lp in me.loops])
        ls = np.array([p.loop_start for p in me.polygons])
        lt = np.array([p.loop_total for p in me.polygons])
    fc = np.bincount(le, minlength=len(ev))
    hist = {int(k): int((fc == k).sum()) for k in np.unique(fc)}
    bad = np.nonzero(fc != 2)[0]
    pts = [[round(float(c), 4) for c in (co[ev[i, 0]] + co[ev[i, 1]]) / 2] + [int(fc[i])] for i in bad[:limit]]
    # winding consistency: an interior edge must be used once in each direction
    nl = len(lv)
    poly_of_loop = np.repeat(np.arange(len(ls)), lt)
    nxt = np.arange(nl) + 1
    last = ls + lt - 1
    nxt[last] = ls
    a, b = lv, lv[nxt]
    fwd = ev[le, 0] == a
    same = np.zeros(len(ev), np.int32)
    np.add.at(same, le, np.where(fwd, 1, -1))
    inconsistent = int(((fc == 2) & (np.abs(same) == 2)).sum())
    zero_len = int((np.linalg.norm(co[ev[:, 0]] - co[ev[:, 1]], axis=1) < 1e-7).sum())
    _ = poly_of_loop, b
    return {"verts": len(co), "edges": len(ev), "faces": int(len(ls)), "face_count_hist": hist,
            "inconsistent_winding_edges": inconsistent, "zero_length_edges": zero_len, "bad_edges": pts}


def winding_report(names):
    return {n: nonmanifold(n, evaluated=False, limit=0) for n in names}
