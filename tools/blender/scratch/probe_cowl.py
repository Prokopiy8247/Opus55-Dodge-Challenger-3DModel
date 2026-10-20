"""Cowl and windshield near the dash: z range of the cowl per y band, and the windshield's inner surface."""
import bpy
import json
import numpy as np

dg = bpy.context.evaluated_depsgraph_get()


def verts(name):
    o = bpy.data.objects[name]
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    oe.to_mesh_clear()
    M = np.array(o.matrix_world)
    return co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]


C = verts("CH_Cowl")
W = verts("CH_Glass_Windshield")
out = {"cowl": [], "glass": []}
for y0 in np.arange(0.84, 1.17, 0.03):
    m = np.abs(C[:, 1] - y0) < 0.015
    if m.any():
        P = C[m]
        out["cowl"].append([round(float(y0), 3), round(float(P[:, 2].min()), 4), round(float(P[:, 2].max()), 4),
                            round(float(np.abs(P[:, 0]).max()), 3)])
for x0 in (0.0, -0.375, -0.6, -0.7):
    for y0 in (0.80, 0.85, 0.90, 0.95):
        m = (np.abs(W[:, 0] - x0) < 0.03) & (np.abs(W[:, 1] - y0) < 0.015)
        if m.any():
            out["glass"].append([x0, round(float(y0), 3), round(float(W[m, 2].min()), 4)])
print(json.dumps(out))
