"""Quarter trim coverage: faces, bbox, and which shell part the side rays hit on a (y, z) grid."""
import bpy
import json
import numpy as np
from hcar import interior as I
from hcar import interior_trim as tr

o = bpy.data.objects["CH_Int_QuarterTrim_L"]
co = np.empty(len(o.data.vertices) * 3, np.float32)
o.data.vertices.foreach_get("co", co)
V = co.reshape(-1, 3)
out = {"faces": len(o.data.polygons), "bbox": [V.min(0).round(3).tolist(), V.max(0).round(3).tolist()]}
shell = tr.Shell(I.SHELL_PARTS)
grid = {}
for y in (-0.65, -0.75, -0.90, -1.05, -1.20, -1.35, -1.50):
    row = []
    for z in (0.45, 0.55, 0.65, 0.75, 0.85, 0.95, 1.05, 1.15, 1.25):
        h = shell.cast((-0.25, y, z), (-1, 0, 0), 1.0)
        row.append("-" if h is None else f"{h[2].replace('CH_', '')[:10]}@{abs(h[0][0]):.2f}")
    grid[str(y)] = row
out["hits"] = grid
print(json.dumps(out, indent=0))
