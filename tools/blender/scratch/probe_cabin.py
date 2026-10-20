"""Cabin envelope from the finished exterior: bounding boxes and sections of the parts around the cabin."""
import bpy
import json
import numpy as np

dg = bpy.context.evaluated_depsgraph_get()


def verts(name, evaluated=False):
    o = bpy.data.objects[name]
    if evaluated:
        oe = o.evaluated_get(dg)
        me = oe.to_mesh()
    else:
        me = o.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    if evaluated:
        oe.to_mesh_clear()
    M = np.array(o.matrix_world)
    return co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]


out = {}
for n in ("CH_Glass_Windshield", "CH_Glass_Rear", "CH_Glass_Door_L", "CH_Glass_Quarter_L", "CH_Roof", "CH_Pillars_L",
          "CH_Door_L", "CH_Rocker_L", "CH_Cowl", "CH_FloorPan", "CH_Quarter_L", "CH_Fender_L"):
    V = verts(n)
    out[n] = [V.min(0).round(3).tolist(), V.max(0).round(3).tolist()]
# windshield: lower and upper edge at x = 0 and x = -0.5
W = verts("CH_Glass_Windshield")
for x0 in (0.0, -0.3, -0.5, -0.6):
    m = np.abs(W[:, 0] - x0) < 0.02
    if m.any():
        P = W[m]
        out[f"ws_x{x0}"] = {"lo": P[np.argmin(P[:, 2])].round(3).tolist(), "hi": P[np.argmax(P[:, 2])].round(3).tolist()}
# roof inner: lowest z of the roof per y (centre)
R = verts("CH_Roof")
out["roof_z_by_y"] = []
for y0 in np.arange(-1.0, 0.6, 0.1):
    m = (np.abs(R[:, 1] - y0) < 0.03) & (np.abs(R[:, 0]) < 0.1)
    if m.any():
        out["roof_z_by_y"].append([round(float(y0), 2), round(float(R[m, 2].min()), 3)])
# door: x of the door skin per z at y = 0 (outer skin; the inner surface ~ 0.12-0.15 m further in)
D = verts("CH_Door_L")
out["door_x_by_z_y0"] = []
for z0 in np.arange(0.25, 1.05, 0.05):
    m = (np.abs(D[:, 2] - z0) < 0.02) & (np.abs(D[:, 1] - 0.0) < 0.05)
    if m.any():
        out["door_x_by_z_y0"].append([round(float(z0), 2), round(float(D[m, 0].max()), 3)])
# door glass: x per z at y = 0
G = verts("CH_Glass_Door_L")
out["glass_x_by_z_y0"] = []
for z0 in np.arange(0.9, 1.45, 0.05):
    m = (np.abs(G[:, 2] - z0) < 0.02) & (np.abs(G[:, 1]) < 0.06)
    if m.any():
        out["glass_x_by_z_y0"].append([round(float(z0), 2), round(float(G[m, 0].max()), 3)])
# door y extent at the belt line
m = np.abs(D[:, 2] - 0.95) < 0.03
out["door_y_range_belt"] = [round(float(D[m, 1].min()), 3), round(float(D[m, 1].max()), 3)]
m = np.abs(D[:, 2] - 0.40) < 0.03
out["door_y_range_low"] = [round(float(D[m, 1].min()), 3), round(float(D[m, 1].max()), 3)]
# A-pillar: pillars object points with y > 0.3
Pp = verts("CH_Pillars_L")
m = Pp[:, 1] > 0.3
out["a_pillar_bbox"] = [Pp[m].min(0).round(3).tolist(), Pp[m].max(0).round(3).tolist()]
m = Pp[:, 1] < -0.3
out["c_pillar_bbox"] = [Pp[m].min(0).round(3).tolist(), Pp[m].max(0).round(3).tolist()]
print(json.dumps(out))
