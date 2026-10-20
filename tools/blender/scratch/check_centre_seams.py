"""Find mesh objects of the car whose vertices near the mirror plane are not welded (open edges at x ~ 0)."""
import bpy
import json
import numpy as np

res = {}
for o in bpy.data.objects:
    if o.type != "MESH" or not o.name.startswith("CH_"):
        continue
    me = o.data
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(o.matrix_world)
    w = co @ M[:3, :3].T + M[:3, 3]
    if w[:, 0].min() > -0.01 or w[:, 0].max() < 0.01:
        continue      # does not span the centreline
    ev = np.empty(len(me.edges) * 2, np.int32)
    me.edges.foreach_get("vertices", ev)
    ev = ev.reshape(-1, 2)
    le = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("edge_index", le)
    fc = np.bincount(le, minlength=len(ev))
    open_e = ev[fc == 1]
    mid = (w[open_e[:, 0]] + w[open_e[:, 1]]) / 2
    near = np.abs(mid[:, 0]) < 2e-3
    # vertices close to (but not on) the plane
    close = (np.abs(w[:, 0]) < 1e-3) & (np.abs(w[:, 0]) > 1e-6)
    if near.any() or close.any():
        res[o.name] = {"open_edges_near_plane": int(near.sum()), "verts_off_plane_lt1mm": int(close.sum()),
                       "max_abs_x_close": float(np.abs(w[close, 0]).max()) if close.any() else 0.0,
                       "sample": [[round(float(c), 4) for c in p] for p in mid[near][:4]]}
print(json.dumps(res, indent=1))
