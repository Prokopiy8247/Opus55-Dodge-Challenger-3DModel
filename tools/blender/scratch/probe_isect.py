"""Where do given object pairs intersect? Bounding box and a few sample points of the overlapping
triangles (of the first object of each pair)."""
import bpy
import json
import numpy as np
from mathutils.bvhtree import BVHTree
from hcar.gate_model import _world_tris

PAIRS = [("CH_Int_Seat_FL", "CH_FloorPan"), ("CH_Int_Console", "CH_FloorPan"), ("CH_Int_Carpet", "CH_FloorPan"),
         ("CH_Int_Carpet", "CH_Subframe_Front"), ("CH_Int_QuarterTrim_L", "CH_Quarter_L"),
         ("CH_Int_QuarterTrim_L", "CH_Susp_Rear_Spring_L"), ("CH_Int_QuarterTrim_L", "CH_Glass_Quarter_L"),
         ("CH_Int_APillar_L", "CH_Glass_Windshield"), ("CH_Glass_Frit", "CH_Glass_Windshield"), ("CH_Int_Mirror", "CH_Roof"),
         ("CH_Int_Seat_Rear", "CH_Int_QuarterTrim_L"), ("CH_Int_QuarterTrim_L", "CH_FloorPan")]
dg = bpy.context.evaluated_depsgraph_get()
cache = {}


def tree(name):
    if name not in cache:
        co, t = _world_tris(bpy.data.objects[name], dg)
        cache[name] = (BVHTree.FromPolygons(co.tolist(), t.tolist(), all_triangles=True), co, t)
    return cache[name]


out = {}
for a, b in PAIRS:
    ta, ca, fa = tree(a)
    tb, cb, fb = tree(b)
    ov = ta.overlap(tb)
    if not ov:
        out[f"{a}|{b}"] = 0
        continue
    ia = np.array([p[0] for p in ov])
    ib = np.array([p[1] for p in ov])
    P = ca[fa[ia]].mean(axis=1)
    Q = cb[fb[ib]].mean(axis=1)
    out[f"{a}|{b}"] = {"n": len(ov), "a_bbox": [P.min(0).round(3).tolist(), P.max(0).round(3).tolist()],
                       "b_bbox": [Q.min(0).round(3).tolist(), Q.max(0).round(3).tolist()],
                       "samples": P[:: max(1, len(P) // 4)][:4].round(3).tolist()}
print(json.dumps(out, indent=0))
