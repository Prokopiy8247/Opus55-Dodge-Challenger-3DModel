"""Where do the front bumper, hood and core support sit around the radiator shroud (x in +-0.65)?"""
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


out = {}
B = verts("CH_Bumper_F")
H = verts("CH_Hood")
S = verts("CH_RadiatorShroud")
C = verts("CH_CoreSupport")
out["shroud_bbox"] = [S.min(0).round(4).tolist(), S.max(0).round(4).tolist()]
out["core_bbox"] = [C.min(0).round(4).tolist(), C.max(0).round(4).tolist()]
for x0 in (0.0, 0.3, 0.5, 0.65):
    selb = (np.abs(np.abs(B[:, 0]) - x0) < 0.03) & (B[:, 2] > 0.78) & (B[:, 2] < 0.90)
    selh = (np.abs(np.abs(H[:, 0]) - x0) < 0.03) & (H[:, 1] > 1.9)
    row = {}
    if selb.any():
        bb = B[selb]
        # bumper: lowest y of its vertices per 1 cm z band (the inside of the top return)
        for z0 in np.arange(0.80, 0.89, 0.01):
            m = np.abs(bb[:, 2] - z0) < 0.005
            if m.any():
                row[f"bump_z{z0:.2f}_ymin"] = round(float(bb[m, 1].min()), 4)
    if selh.any():
        hh = H[selh]
        for y0 in np.arange(2.00, 2.32, 0.04):
            m = np.abs(hh[:, 1] - y0) < 0.02
            if m.any():
                row[f"hood_y{y0:.2f}_zmin"] = round(float(hh[m, 2].min()), 4)
    out[f"x{x0}"] = row
print(json.dumps(out, indent=1))
