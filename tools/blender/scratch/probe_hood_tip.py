"""Hood front edge near the centreline: base mesh vertices (x < 3 cm, y > 2.24) per x column."""
import bpy
import json
import numpy as np

o = bpy.data.objects["CH_Hood"]
me = o.data
co = np.empty(len(me.vertices) * 3, np.float32)
me.vertices.foreach_get("co", co)
M = np.array(o.matrix_world)
V = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
sel = (V[:, 0] > -0.001) & (V[:, 0] < 0.03) & (V[:, 1] > 2.25)
P = V[sel]
cols = {}
for p in P[np.argsort(P[:, 0])]:
    k = round(float(p[0]), 4)
    cols.setdefault(k, []).append([round(float(p[1]), 4), round(float(p[2]), 4)])
out = {k: sorted(v, key=lambda t: -t[0])[:8] for k, v in list(cols.items())[:12]}
print(json.dumps(out))
