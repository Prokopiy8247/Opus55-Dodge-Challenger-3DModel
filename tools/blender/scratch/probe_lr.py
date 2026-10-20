"""For every *_L / *_R object: vertices on the wrong side of the centreline (split check)."""
import bpy
import json
import numpy as np

res = {}
for o in bpy.data.collections["Car_Visual"].all_objects:
    if o.type != "MESH" or not (o.name.endswith("_L") or o.name.endswith("_R")):
        continue
    me = o.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    M = np.array(o.matrix_world)
    V = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    wrong = (V[:, 0] > 0.001) if o.name.endswith("_L") else (V[:, 0] < -0.001)
    if wrong.any():
        res[o.name] = {"n_wrong": int(wrong.sum()), "of": len(V), "sample": V[wrong][:3].round(3).tolist()}
print(json.dumps(res))
