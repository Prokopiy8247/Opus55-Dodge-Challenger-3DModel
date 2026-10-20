"""Hood underside height along a line 6 cm behind the radiator shroud's front edge."""
import bpy
import json
import numpy as np

dg = bpy.context.evaluated_depsgraph_get()
o = bpy.data.objects["CH_Hood"]
oe = o.evaluated_get(dg)
me = oe.to_mesh()
co = np.empty(len(me.vertices) * 3, np.float32)
me.vertices.foreach_get("co", co)
oe.to_mesh_clear()
M = np.array(o.matrix_world)
H = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
xs = np.linspace(0.0, 0.65, 14)
y_front = np.interp(xs, [0.0, 0.3, 0.5, 0.65], [2.286, 2.265, 2.2335, 2.2037])
rows = []
for x, yf in zip(xs, y_front):
    for back in (0.04, 0.06, 0.08):
        y = yf - back
        m = (np.abs(H[:, 0] - x) < 0.03) & (np.abs(H[:, 1] - y) < 0.012)
        rows.append([round(float(x), 3), back, round(float(y), 4), round(float(H[m, 2].min()), 4) if m.any() else None])
print(json.dumps(rows))
