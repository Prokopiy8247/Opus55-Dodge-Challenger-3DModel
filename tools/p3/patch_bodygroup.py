"""One-off patch (P3, D-033): per-node detach break groups of damp groups, the body structure damp group."""
from pathlib import Path

SIM = Path("Unity/HellcatSandbox/Assets/Sim")


def patch(path, reps):
    s = path.read_text(encoding="utf-8")
    for old, new in reps:
        assert s.count(old) == 1, (path.name, old)
        s = s.replace(old, new)
    path.write_text(s, encoding="utf-8")


patch(SIM / "Data" / "VehicleDef.cs", [
    ('''        public string bg;          // break group that ends the damping (a shattered pane), "" never
    }''', '''        public string bg;          // break group that ends the damping (a shattered pane), "" never
        public string[] nodeBg;    // per node: break group that detaches the node from the group ("" never; may be absent)
    }'''),
])
patch(SIM / "Core" / "GroupDampJob.cs", [
    ('''        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> groupNodes;''',
     '''        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> groupNodes;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> groupNodeBg;  // -1: never detaches'''),
    ('''            // momentum, centre of mass (double: the group sits metres from the origin, the sums are small differences)
            double mt = 0.0;
            double3 xc = double3.zero, p = double3.zero;
            for (int k = s; k < e; k++)
            {
                int i = groupNodes[k];
                float im = invMass[i];
                if (im <= 0f)
                    continue;''',
     '''            // momentum, centre of mass (double: the group sits metres from the origin, the sums are small differences);
            // a node whose break group fired (a seat, the engine torn off its mounts) has left the group
            double mt = 0.0;
            double3 xc = double3.zero, p = double3.zero;
            for (int k = s; k < e; k++)
            {
                int i = groupNodes[k];
                float im = invMass[i];
                if (im <= 0f || Detached(k))
                    continue;'''),
    ('''            double3 L = double3.zero;
            double ixx = 0, iyy = 0, izz = 0, ixy = 0, ixz = 0, iyz = 0;
            for (int k = s; k < e; k++)
            {
                int i = groupNodes[k];
                float im = invMass[i];
                if (im <= 0f)
                    continue;''',
     '''            double3 L = double3.zero;
            double ixx = 0, iyy = 0, izz = 0, ixy = 0, ixz = 0, iyz = 0;
            for (int k = s; k < e; k++)
            {
                int i = groupNodes[k];
                float im = invMass[i];
                if (im <= 0f || Detached(k))
                    continue;'''),
    ('''                int i = groupNodes[k];
                float im = invMass[i];
                if (im <= 0f)
                {
                    dampForce[i] = float3.zero;
                    continue;
                }''',
     '''                int i = groupNodes[k];
                float im = invMass[i];
                if (im <= 0f || Detached(k))
                {
                    dampForce[i] = float3.zero;
                    continue;
                }'''),
    ('''            if (trackEnergy != 0)
                groupDampEnergy[gi] += diss * dt;
        }''',
     '''            if (trackEnergy != 0)
                groupDampEnergy[gi] += diss * dt;
        }

        bool Detached(int k)
        {
            int bg = groupNodeBg[k];
            return bg >= 0 && groupDone[bg] != 0;
        }'''),
])
patch(SIM / "Core" / "SoftBodyWorld.cs", [
    ('''        public NativeArray<int> dampGroupNodes;''',
     '''        public NativeArray<int> dampGroupNodes, dampGroupNodeBg;'''),
    ('''            dampGroupNodes = Alloc<int>(math.max(nDampNodes, 1));''',
     '''            dampGroupNodes = Alloc<int>(math.max(nDampNodes, 1));
            dampGroupNodeBg = Alloc<int>(math.max(nDampNodes, 1));'''),
    ('''                        inDampGroup[gn] = true;
                        dampGroupNodes[dgCursor++] = gn;''',
     '''                        inDampGroup[gn] = true;
                        string nbg = dg.nodeBg != null && k < dg.nodeBg.Length ? dg.nodeBg[k] : "";
                        dampGroupNodeBg[dgCursor] = string.IsNullOrEmpty(nbg) || !b.groupNames.Contains(nbg) ? -1
                            : b.groupStart + b.groupNames.IndexOf(nbg);
                        dampGroupNodes[dgCursor++] = gn;'''),
    ('''            groupNodes = dampGroupNodes,''',
     '''            groupNodes = dampGroupNodes,
            groupNodeBg = dampGroupNodeBg,'''),
])

patch(Path("tools/blender/hcar/sk.py"), [
    ('''    def damp_group(self, name, nodes, mat, bg=""):
        """Nodes whose velocities are damped towards the group's own rigid motion (one panel, one pane)."""
        ids = sorted({self.idx(n) for n in nodes})
        self.damp_groups.append({"name": name, "nodes": ids, "mat": mat, "bg": bg})
        return len(self.damp_groups) - 1''',
     '''    def damp_group(self, name, nodes, mat, bg="", node_bg=None):
        """Nodes whose velocities are damped towards the group's own rigid motion (one panel, one pane, the body).
        node_bg: node -> break group that detaches that node from the group (a seat, the engine)."""
        ids = sorted({self.idx(n) for n in nodes})
        node_bg = node_bg or {}
        self.damp_groups.append({"name": name, "nodes": ids, "mat": mat, "bg": bg,
                                 "nodeBg": [node_bg.get(i, "") for i in ids]})
        return len(self.damp_groups) - 1'''),
])

patch(Path("tools/blender/hcar/hskel.py"), [
    ('''def add_damp_groups(B):
    """Deformation damping groups (D-033): one per panel / pane, damped towards its own rigid motion."""
    names = [n["name"] for n in B.sk.nodes]
    for g, prefixes, mat, bg in DAMP_GROUPS:
        ids = [i for i, nm in enumerate(names) if nm.startswith(prefixes)]
        if len(ids) >= 4:
            B.sk.damp_group(g, ids, mat, bg)''',
     '''def add_damp_groups(B):
    """Deformation damping groups (D-033): one per panel / pane, damped towards its own rigid motion, and the body
    structure (cell, frame, interior, powertrain, body-side suspension mounts) as one group, so its low flexible
    modes get mass-proportional damping (beam damping is stiffness-proportional: together Rayleigh damping) while the
    rigid body, the suspension and the wheels are not damped. Detachable parts leave the body group when their
    break group fires."""
    names = [n["name"] for n in B.sk.nodes]
    used = set()
    for g, prefixes, mat, bg in DAMP_GROUPS:
        ids = [i for i, nm in enumerate(names) if nm.startswith(prefixes)]
        if len(ids) >= 4:
            B.sk.damp_group(g, ids, mat, bg)
            used.update(ids)
    detach = {"engine": "engine_mount", "mirror_L": "mirror_L", "mirror_R": "mirror_R", "headlight_L": "headlight_L",
              "headlight_R": "headlight_R"}
    body, node_bg = [], {}
    for i, n in enumerate(B.sk.nodes):
        if i in used or n["part"] not in ("body", "engine", "mirror_L", "mirror_R", "headlight_L", "headlight_R"):
            continue
        if "_tip_" in n["name"]:                       # anti-roll bar levers move with the wheels
            continue
        body.append(i)
        if n["part"] in detach:
            node_bg[i] = detach[n["part"]]
        elif n["name"].startswith(("seatFL", "seatFR")):
            node_bg[i] = "seat_" + n["name"][4:6]
    B.sk.damp_group("body", body, "structure", "", node_bg)'''),
])

patch(Path("sim/vehicle/hellcat/params.json"), [
    ('''    { "name": "exhaust", "rate": 6 }
  ],''', '''    { "name": "exhaust", "rate": 6 },
    { "name": "structure", "rate": 5 }
  ],'''),
])
print("patched")
