"""P0.5 vertical slice: a box-shaped car (60 nodes, 4 simple wheels) through the whole pipeline.

Body: 3 stations x 2 sides x 2 heights = 12 nodes; front bay (stations 0-1) is a crush zone,
the rest is a rigid cabin. Wheels: two axle nodes on the rotation axis + 10 rim nodes (contact
nodes, compliant spokes act as the tire). Suspension per axle node: two longitudinal links, one
lateral link, one spring-damper. Front wheels steer through HYDRO tie rods (input "steering").

Run: python -I tools/blender/blender_bridge.py call hcar.boxcar:main
"""
import math
import os

from . import PROJECT_ROOT
from . import sk as S
from . import debugviz

OUT_SIM = os.path.join(PROJECT_ROOT, "sim", "vehicle", "boxcar", "geometry.json")
OUT_UNITY = os.path.join(PROJECT_ROOT, "Unity", "HellcatSandbox", "Assets", "StreamingAssets", "Vehicles", "boxcar", "geometry.json")

BODY_STATIONS = [2.0, 0.8, -2.0]   # y, front to rear
BODY_HALF_WIDTH = 0.8
BODY_Z = [0.35, 1.15]
# Light crush face, heavy cabin: a heavy front face would be stopped inelastically by the wall.
BODY_NODE_MASS = [25.0, 160.0, 102.5]
WHEELS = {  # name: (y, side)
    "FL": (1.30, -1), "FR": (1.30, 1), "RL": (-1.30, -1), "RR": (-1.30, 1),
}
WHEEL_RADIUS = 0.33
WHEEL_PLANE_X = 0.92
AXLE_INNER_X = 0.72
AXLE_OUTER_X = 1.12
RIM_NODES = 10
RIM_NODE_MASS = 2.2
AXLE_NODE_MASS = 12.0
CONTACT_BIAS_OFFSET = 0.012   # nodes sit inside the contact zone at rest
SPRING_PRECOMPRESSION = 1.05  # rest = 1.05 x spawn length: the spring carries the corner load at spawn height


def side_name(side):
    return "L" if side < 0 else "R"


def build():
    sk = S.Skeleton("boxcar")
    body = {}
    for si, y in enumerate(BODY_STATIONS):
        for side in (-1, 1):
            for zi, z in enumerate(BODY_Z):
                name = f"b{si}{side_name(side)}{'lo' if zi == 0 else 'hi'}"
                body[(si, side, zi)] = sk.node(name, (side * BODY_HALF_WIDTH, y, z), BODY_NODE_MASS[si],
                                               cmat="body", part="body")
    # Body beams: each station fully braced, each bay fully braced.
    for si in range(len(BODY_STATIONS)):
        ids = [body[(si, s, z)] for s in (-1, 1) for z in (0, 1)]
        for i in range(4):
            for j in range(i + 1, 4):
                sk.beam(ids[i], ids[j], "bumper_face" if si == 0 else "cabin")
    for si in range(len(BODY_STATIONS) - 1):
        a_ids = [body[(si, s, z)] for s in (-1, 1) for z in (0, 1)]
        b_ids = [body[(si + 1, s, z)] for s in (-1, 1) for z in (0, 1)]
        mat = "crush" if si == 0 else "cabin"
        for a in a_ids:
            for b in b_ids:
                sk.beam(a, b, mat)

    zc = WHEEL_RADIUS + CONTACT_BIAS_OFFSET
    for wname, (y, side) in WHEELS.items():
        front = y > 0
        sn = side_name(side)
        inner = sk.node(f"{wname}_axle_in", (side * AXLE_INNER_X, y, zc), AXLE_NODE_MASS, cmat="body", part=f"wheel_{wname}")
        outer = sk.node(f"{wname}_axle_out", (side * AXLE_OUTER_X, y, zc), AXLE_NODE_MASS, cmat="body", part=f"wheel_{wname}")
        rim = []
        for k in range(RIM_NODES):
            a = 2.0 * math.pi * k / RIM_NODES
            p = (side * WHEEL_PLANE_X, y + WHEEL_RADIUS * math.sin(a), zc - WHEEL_RADIUS * math.cos(a))
            rim.append(sk.node(f"{wname}_rim{k}", p, RIM_NODE_MASS, flags=S.DEFAULT_FLAGS | S.TIRE,
                               cmat="tire", part=f"wheel_{wname}"))
        sk.beam(inner, outer, "axle")
        for k in range(RIM_NODES):
            sk.beam(rim[k], inner, "tire_spoke")
            sk.beam(rim[k], outer, "tire_spoke")
            sk.beam(rim[k], rim[(k + 1) % RIM_NODES], "tire_ring")
            sk.beam(rim[k], rim[(k + 2) % RIM_NODES], "tire_ring")

        # Suspension: stations around the axle (front axle sits between stations 0 and 1).
        s_front, s_back = (0, 1) if front else (1, 2)
        lo_f, lo_b = body[(s_front, side, 0)], body[(s_back, side, 0)]
        hi_near = body[(s_front if abs(BODY_STATIONS[s_front] - y) < abs(BODY_STATIONS[s_back] - y) else s_back, side, 1)]
        lo_opp = body[(s_front if front else s_back, -side, 0)]
        for axle_node in (inner, outer):
            if axle_node == outer and front:
                continue
            sk.beam(axle_node, lo_f, "arm")
            sk.beam(axle_node, lo_b, "arm")
            sk.beam(axle_node, lo_opp, "arm")
            sk.beam(axle_node, hi_near, "spring", pre=SPRING_PRECOMPRESSION)
            sk.beam(axle_node, hi_near, "damper", allow_duplicate=True)
        if front:
            # Outer node of a steered wheel: axle beam (radius about the inner node) + tie rod (hydro)
            # leave one degree of freedom, carried by the spring/damper (wheel travel).
            sk.beam(outer, body[(0, side, 0)], "tierod", type="HYDRO", hydro="steering",
                    hf=(-0.25 if side < 0 else 0.25))
            sk.beam(outer, hi_near, "spring", pre=SPRING_PRECOMPRESSION)
            sk.beam(outer, hi_near, "damper", allow_duplicate=True)
        arm_node = hi_near
        sk.wheel(wname, inner, outer, rim, rim, arm_node, driven=not front, steered=front,
                 brake="front" if front else "rear", radius=WHEEL_RADIUS)

    sk.camera("chase_target", [body[(1, -1, 0)], body[(1, 1, 0)], body[(2, -1, 0)]], (0.0, 0.0, 1.0))
    return sk


def category(mat, btype):
    if btype == "HYDRO":
        return "hydro"
    return {"cabin": "rigid", "bumper_face": "crush", "crush": "crush", "tire_spoke": "tire", "tire_ring": "tire",
            "axle": "rim", "arm": "suspension", "spring": "suspension", "damper": "suspension",
            "tierod": "hydro"}.get(mat, "other")


def main(viz=True, save=True):
    sk = build()
    size = sk.write(OUT_SIM, OUT_UNITY)
    result = {"stats": sk.stats(), "bytes": size, "out": [OUT_SIM, OUT_UNITY]}
    if viz:
        import bpy
        from . import blend_util as bu
        root = bu.collection("P05_Slice")
        result["viz"] = debugviz.build(sk, "P05_BoxCar_Physics", category, parent=root)
        if save:
            result["blend"] = bu.save_version("P0.5 box car skeleton")
    return result
