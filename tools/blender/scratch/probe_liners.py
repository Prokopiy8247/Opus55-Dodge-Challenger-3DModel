"""Innermost |x| of the rear wheel liners and the quarter panel per (y, z) band (cabin side walls)."""
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


L = verts("CH_WheelLiners_L")
Q = verts("CH_Quarter_L")
out = {"liner_bbox_rear": None, "liner": [], "quarter": []}
m = L[:, 1] < 0
out["liner_bbox_rear"] = [L[m].min(0).round(3).tolist(), L[m].max(0).round(3).tolist()]
for y0 in (-1.0, -1.1, -1.2, -1.3, -1.4, -1.5):
    for z0 in (0.45, 0.55, 0.65, 0.75):
        mm = m & (np.abs(L[:, 1] - y0) < 0.03) & (np.abs(L[:, 2] - z0) < 0.03)
        if mm.any():
            out["liner"].append([y0, z0, round(float(np.abs(L[mm, 0]).min()), 3)])
        mq = (np.abs(Q[:, 1] - y0) < 0.03) & (np.abs(Q[:, 2] - z0) < 0.03)
        if mq.any():
            out["quarter"].append([y0, z0, round(float(np.abs(Q[mq, 0]).min()), 3)])
print(json.dumps(out))
