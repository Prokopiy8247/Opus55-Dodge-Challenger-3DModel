"""Physics skeleton container and geometry.json writer (format "hellcat-softbody" v1).

Positions are given in the Blender authoring frame (X right, Y forward, Z up) and converted to
the Unity simulation frame on export: u = (x, z, y). That mirror swaps handedness, so triangle
vertices b and c are swapped on export to keep cross(b - a, c - a) pointing out of the body.
"""
import json
import math
import os

# Node flags (must match Hellcat.Sim.NodeFlag)
COLLISION = 1
SELF_COLLISION = 2
STATIC_COLLISION = 4
FIXED = 8
TIRE = 16
DEFAULT_FLAGS = COLLISION | STATIC_COLLISION

BEAM_TYPES = ("NORMAL", "ANISOTROPIC", "BOUNDED", "SUPPORT", "HYDRO")
TRI_TYPES = ("COLLIDE", "NONCOLLIDABLE", "PRESSURE", "AERO")


def to_unity(p):
    return [float(p[0]), float(p[2]), float(p[1])]


class Skeleton:
    def __init__(self, name):
        self.name = name
        self.nodes = []        # dicts: name, p (blender frame), m, flags, cmat, group, part
        self.node_index = {}
        self.beams = []        # dicts: a, b, type, mat, bg, bgt, pre, hydro, hf
        self.beam_pairs = {}
        self.tris = []
        self.wheels = []
        self.pressure_groups = []
        self.torsion_bars = []
        self.hinges = []       # shell bending elements: {"n": [wing, edge, edge, wing], "mat"} (D-032)
        self.damp_groups = []  # deformation damping groups: {"name", "nodes", "mat", "bg"} (D-033)
        self.parts = {}        # name -> {"nodes": set, "visuals": []}
        self.cameras = []
        self.hydros = []
        self.notes = []

    # ------------------------------------------------------------------ building
    def node(self, name, p, m, flags=DEFAULT_FLAGS, cmat="body", group="", part=""):
        if name in self.node_index:
            raise ValueError(f"duplicate node name {name}")
        idx = len(self.nodes)
        self.nodes.append({"name": name, "p": [float(v) for v in p], "m": float(m), "flags": int(flags),
                           "cmat": cmat, "group": group or part, "part": part})
        self.node_index[name] = idx
        if part:
            self.parts.setdefault(part, {"nodes": set(), "visuals": []})["nodes"].add(idx)
        return idx

    def idx(self, n):
        return self.node_index[n] if isinstance(n, str) else int(n)     # names, ints or numpy integers

    def beam(self, a, b, mat, type="NORMAL", bg="", bgt=0, pre=1.0, hydro="", hf=0.0, allow_duplicate=False):
        a, b = self.idx(a), self.idx(b)
        if a == b:
            raise ValueError(f"beam with identical ends {a}")
        if type not in BEAM_TYPES:
            raise ValueError(f"unknown beam type {type}")
        key = (min(a, b), max(a, b))
        if key in self.beam_pairs and not allow_duplicate:
            return self.beam_pairs[key]
        if type == "HYDRO" and hydro not in self.hydros:
            self.hydros.append(hydro)
        self.beams.append({"a": a, "b": b, "type": type, "mat": mat, "bg": bg, "bgt": int(bgt),
                           "pre": float(pre), "hydro": hydro, "hf": float(hf)})
        self.beam_pairs[key] = len(self.beams) - 1
        return len(self.beams) - 1

    def tri(self, a, b, c, type="COLLIDE", group="", bg="", drag=10.0, lift=10.0):
        if type not in TRI_TYPES:
            raise ValueError(f"unknown triangle type {type}")
        self.tris.append({"a": self.idx(a), "b": self.idx(b), "c": self.idx(c), "type": type,
                          "group": group, "bg": bg, "drag": float(drag), "lift": float(lift)})
        return len(self.tris) - 1

    def hinge(self, a, b, c, d, mat):
        """Shell bending hinge across the edge b-c shared by the triangles (a, b, c) and (b, c, d)."""
        self.hinges.append({"n": [self.idx(a), self.idx(b), self.idx(c), self.idx(d)], "mat": mat})
        return len(self.hinges) - 1

    def damp_group(self, name, nodes, mat, bg="", node_bg=None, reference="", ref_bg=()):
        """Nodes whose velocities are damped towards the group's own rigid motion (one panel, one pane, the body).
        node_bg: node -> break group that detaches that node from the group (a seat, the engine). reference: damp
        group whose rigid motion the part is also damped towards (D-038), ref_bg: break groups that end that."""
        ids = sorted({self.idx(n) for n in nodes})
        node_bg = node_bg or {}
        self.damp_groups.append({"name": name, "nodes": ids, "mat": mat, "bg": bg,
                                 "nodeBg": [node_bg.get(i, "") for i in ids], "reference": reference,
                                 "refBg": list(ref_bg)})
        return len(self.damp_groups) - 1

    def wheel(self, name, axle_inner, axle_outer, rim, tread, arm, driven, steered, brake, radius, pressure_group="",
              drive_reaction=(), windup="", windup_body=(), kingpin=()):
        """drive_reaction: body nodes taking the drive torque reaction (the differential, D-036); windup: wind-up element
        parameter set, windup_body: the body nodes of its couple (D-036); kingpin: the lower and the upper ball joint of a
        steered knuckle (the steering axis of the alignment element, D-051)."""
        self.wheels.append({"name": name, "axleInner": self.idx(axle_inner), "axleOuter": self.idx(axle_outer),
                            "rim": [self.idx(n) for n in rim], "tread": [self.idx(n) for n in tread],
                            "arm": self.idx(arm), "driven": int(driven), "steered": int(steered),
                            "brake": brake, "radius": float(radius), "pressureGroup": pressure_group,
                            "driveReaction": [self.idx(n) for n in drive_reaction],
                            "windup": windup, "windupBody": [self.idx(n) for n in windup_body],
                            "kingpin": [self.idx(n) for n in kingpin]})

    def camera(self, name, nodes, offset):
        self.cameras.append({"name": name, "nodes": [self.idx(n) for n in nodes], "offset": [float(v) for v in offset]})

    def link_visual(self, part, visual_name):
        self.parts.setdefault(part, {"nodes": set(), "visuals": []})["visuals"].append(visual_name)

    # ------------------------------------------------------------------ checks
    def stats(self):
        mass = sum(n["m"] for n in self.nodes if not n["flags"] & FIXED)
        com = [0.0, 0.0, 0.0]
        for n in self.nodes:
            for k in range(3):
                com[k] += n["m"] * n["p"][k]
        com = [c / mass for c in com] if mass > 0 else com
        degree = [0] * len(self.nodes)
        for b in self.beams:
            degree[b["a"]] += 1
            degree[b["b"]] += 1
        # connected components (union-find)
        parent = list(range(len(self.nodes)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for b in self.beams:
            ra, rb = find(b["a"]), find(b["b"])
            if ra != rb:
                parent[ra] = rb
        components = len({find(i) for i in range(len(self.nodes))})
        # duplicates within 1 cm
        dup = 0
        pts = [n["p"] for n in self.nodes]
        cell = {}
        for i, p in enumerate(pts):
            key = tuple(int(math.floor(v / 0.01)) for v in p)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        for j in cell.get((key[0] + dx, key[1] + dy, key[2] + dz), ()):
                            if math.dist(p, pts[j]) < 0.01:
                                dup += 1
            cell.setdefault(key, []).append(i)
        return {"nodes": len(self.nodes), "beams": len(self.beams), "triangles": len(self.tris),
                "hinges": len(self.hinges), "damp_groups": len(self.damp_groups),
                "wheels": len(self.wheels), "mass_kg": round(mass, 3), "com_blender": [round(c, 4) for c in com],
                "min_degree": min(degree) if degree else 0, "isolated_nodes": degree.count(0),
                "components": components, "duplicate_pairs_1cm": dup, "hydros": list(self.hydros)}

    # ------------------------------------------------------------------ export
    def to_dict(self):
        parts = [{"name": k, "nodes": sorted(v["nodes"]), "visuals": list(v["visuals"])} for k, v in sorted(self.parts.items())]
        tris = [{"a": t["a"], "b": t["c"], "c": t["b"], "type": t["type"], "group": t["group"], "bg": t["bg"],
                 "drag": t["drag"], "lift": t["lift"]} for t in self.tris]
        cams = [{"name": c["name"], "nodes": c["nodes"], "offset": to_unity(c["offset"])} for c in self.cameras]
        return {
            "format": "hellcat-softbody",
            "version": 1,
            "name": self.name,
            "units": "SI; frame x right, y up, z forward (Unity); triangles wound outward",
            # positions rounded to 1 um and masses to 1e-9 kg: Blender's and the venv's numpy sum in different orders
            # (1e-15 differences), and the export must not depend on where it was built
            "nodes": [{"name": n["name"], "p": [round(v, 6) for v in to_unity(n["p"])], "m": round(n["m"], 9), "flags": n["flags"],
                       "cmat": n["cmat"], "group": n["group"], "part": n["part"]} for n in self.nodes],
            "beams": self.beams,
            "triangles": tris,
            "wheels": self.wheels,
            "pressureGroups": self.pressure_groups,
            "torsionBars": self.torsion_bars,
            "hinges": self.hinges,
            "dampGroups": self.damp_groups,
            "parts": parts,
            "cameras": cams,
            "hydros": self.hydros,
        }

    def write(self, *paths):
        data = self.to_dict()
        text = json.dumps(data, separators=(",", ":"))
        for path in paths:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        return len(text)
