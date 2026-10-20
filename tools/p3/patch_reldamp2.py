"""One-off patch (P3, D-038), part 2: world wiring, stability term, skeleton export, parameters."""
from pathlib import Path

SIM = Path("Unity/HellcatSandbox/Assets/Sim")


def patch(path, reps):
    s = path.read_text(encoding="utf-8")
    for old, new in reps:
        assert s.count(old) == 1, (path.name, old[:160])
        s = s.replace(old, new)
    path.write_text(s, encoding="utf-8")


w = SIM / "Core" / "SoftBodyWorld.cs"
patch(w, [
    ('''        public NativeArray<double> dampGroupEnergy;
        // Pressure groups''',
     '''        public NativeArray<double> dampGroupEnergy;
        NativeArray<DampGroupRigid> dampRigid;          // per group rigid motion of the substep (D-038)
        NativeArray<double3> dampReactF, dampReactT;     // scratch of the relative damping pass
        // Pressure groups'''),
    ('''            dampGroupEnergy = Alloc<double>(math.max(nDampGroup, 1));''',
     '''            dampGroupEnergy = Alloc<double>(math.max(nDampGroup, 1));
            dampRigid = Alloc<DampGroupRigid>(math.max(nDampGroup, 1));
            dampReactF = Alloc<double3>(math.max(nDampGroup, 1));
            dampReactT = Alloc<double3>(math.max(nDampGroup, 1));'''),
    ('''                        breakGroup = string.IsNullOrEmpty(dg.bg) || !b.groupNames.Contains(dg.bg) ? -1
                            : b.groupStart + b.groupNames.IndexOf(dg.bg),
                        body = bi,
                    };''',
     '''                        breakGroup = string.IsNullOrEmpty(dg.bg) || !b.groupNames.Contains(dg.bg) ? -1
                            : b.groupStart + b.groupNames.IndexOf(dg.bg),
                        body = bi,
                        refGroup = -1,
                        relRate = 0f,
                        refBg0 = -1,
                        refBg1 = -1,
                    };
                    if (!string.IsNullOrEmpty(dg.reference))
                    {
                        int rg = Array.FindIndex(def.dampGroups, x => x.name == dg.reference);
                        if (rg < 0 || rg == t)
                            throw new InvalidDataException($"{b.name}: damp group {dg.name}: unknown reference '{dg.reference}'");
                        dgs.refGroup = b.dampGroupStart + rg;
                        dgs.relRate = math.max(b.prm.DampGroupMaterial(dg.mat).relRate, 0f);
                        var rb = dg.refBg ?? Array.Empty<string>();
                        if (rb.Length > 2)
                            throw new InvalidDataException($"{b.name}: damp group {dg.name}: at most 2 reference break groups");
                        dgs.refBg0 = rb.Length > 0 ? GroupIndex(b, rb[0]) : -1;
                        dgs.refBg1 = rb.Length > 1 ? GroupIndex(b, rb[1]) : -1;
                    }'''),
    ('''            groupNodeBg = dampGroupNodeBg,
            dampForce = dampForce,
            groupDampEnergy = dampGroupEnergy,
        };''',
     '''            groupNodeBg = dampGroupNodeBg,
            dampForce = dampForce,
            groupDampEnergy = dampGroupEnergy,
            rigid = dampRigid,
        };

        GroupRelDampJob MakeRelDampJob() => new GroupRelDampJob
        {
            dt = dt,
            trackEnergy = trackEnergy ? 1 : 0,
            pos = pos,
            vel = vel,
            invMass = invMass,
            groupDone = groupDone,
            groups = dampGroups,
            groupNodes = dampGroupNodes,
            groupNodeBg = dampGroupNodeBg,
            rigid = dampRigid,
            dampForce = dampForce,
            groupDampEnergy = dampGroupEnergy,
            reactF = dampReactF,
            reactT = dampReactT,
        };'''),
    ('''            var dampJob = MakeDampJob();''',
     '''            var dampJob = MakeDampJob();
            var relDampJob = MakeRelDampJob();'''),
    ('''                    dampJob = dampJob,''',
     '''                    dampJob = dampJob,
                    relDampJob = relDampJob,'''),
    ('''                    h = dampJob.Schedule(DampGroupCount, 1, h);''',
     '''                {
                    h = dampJob.Schedule(DampGroupCount, 1, h);
                    h = relDampJob.Schedule(h);
                }'''),
])
s = w.read_text(encoding="utf-8")
# the scheduling patch above replaced a single statement under an if: make sure the braces are right
assert "if (DampGroupCount > 0)\n                {\n                    h = dampJob.Schedule" in s, "if-block form"
w.write_text(s, encoding="utf-8")

patch(SIM / "Core" / "SerialPhaseJob.cs", [
    ('''        public GroupDampJob dampJob;''',
     '''        public GroupDampJob dampJob;
        public GroupRelDampJob relDampJob;'''),
    ('''                for (int g = 0; g < dampGroupCount; g++)
                    dampJob.Execute(g);''',
     '''                for (int g = 0; g < dampGroupCount; g++)
                    dampJob.Execute(g);
                if (dampGroupCount > 0)
                    relDampJob.Execute();'''),
])

patch(SIM / "Core" / "StabilityReport.cs", [
    ('''                    if (im > 0f)
                        dc[i] += 2.0 * dt * dg.rate / im;''',
     '''                    if (im > 0f)
                        dc[i] += 2.0 * dt * (dg.rate + (dg.refGroup >= 0 ? dg.relRate : 0f)) / im;'''),
])

# ---------------------------------------------------------------- skeleton export
patch(Path("tools/blender/hcar/sk.py"), [
    ('''    def damp_group(self, name, nodes, mat, bg="", node_bg=None):
        """Nodes whose velocities are damped towards the group's own rigid motion (one panel, one pane, the body).
        node_bg: node -> break group that detaches that node from the group (a seat, the engine)."""
        ids = sorted({self.idx(n) for n in nodes})
        node_bg = node_bg or {}
        self.damp_groups.append({"name": name, "nodes": ids, "mat": mat, "bg": bg,
                                 "nodeBg": [node_bg.get(i, "") for i in ids]})''',
     '''    def damp_group(self, name, nodes, mat, bg="", node_bg=None, reference="", ref_bg=()):
        """Nodes whose velocities are damped towards the group's own rigid motion (one panel, one pane, the body).
        node_bg: node -> break group that detaches that node from the group (a seat, the engine). reference: damp
        group whose rigid motion the part is also damped towards (D-038), ref_bg: break groups that end that."""
        ids = sorted({self.idx(n) for n in nodes})
        node_bg = node_bg or {}
        self.damp_groups.append({"name": name, "nodes": ids, "mat": mat, "bg": bg,
                                 "nodeBg": [node_bg.get(i, "") for i in ids], "reference": reference,
                                 "refBg": list(ref_bg)})'''),
])

h = Path("tools/blender/hcar/hskel.py")
s = h.read_text(encoding="utf-8")
old_start = s.index("DAMP_GROUPS = [   # (group, node-name prefixes, material, break group that ends the damping)")
old_end = s.index("def add_damp_groups(B):")
s = s[:old_start] + '''DAMP_GROUPS = [   # (group, node-name prefixes, material, break group that ends the damping, reference, reference ends)
    # attached parts are also damped towards the body's (side glass: the door's) rigid motion until their latch / hinges /
    # clips / hangers break (D-038)
    ("roof", ("roof_",), "skin", "", "body", ()), ("hood", ("hood_o_", "hood_i_"), "skin", "", "body", ("hood", "hood_latch")),
    ("trunk", ("trunk_o_", "trunk_i_"), "skin", "", "body", ("trunk", "trunk_latch")),
    ("door_FL", ("door_FL_o_", "door_FL_i_"), "skin", "", "body", ("door_FL", "door_FL_latch")),
    ("door_FR", ("door_FR_o_", "door_FR_i_"), "skin", "", "body", ("door_FR", "door_FR_latch")),
    ("fender_L", ("fender_L_",), "skin", "", "body", ()), ("fender_R", ("fender_R_",), "skin", "", "body", ()),
    ("quarter_L", ("quarter_L_",), "skin", "", "body", ()), ("quarter_R", ("quarter_R_",), "skin", "", "body", ()),
    ("fascia", ("fascia_",), "plastic", "", "body", ("bumper_F",)), ("rbumper", ("rbumper_",), "plastic", "", "body", ("bumper_R",)),
    ("glass_windshield", ("glass_windshield_",), "glass", "glass_windshield", "body", ()),
    ("glass_rear", ("glass_rear_",), "glass", "glass_rear", "body", ()),
    ("glass_side_FL", ("glass_side_FL_",), "glass", "glass_side_FL", "door_FL", ()),
    ("glass_side_FR", ("glass_side_FR_",), "glass", "glass_side_FR", "door_FR", ()),
    ("glass_quarter_L", ("glass_quarter_L_",), "glass", "glass_quarter_L", "body", ()),
    ("glass_quarter_R", ("glass_quarter_R_",), "glass", "glass_quarter_R", "body", ()),
    ("exhaust", ("exh",), "exhaust", "", "body", ("exhaust",)),
    # wheels (D-033, P3): rim rings + tread, damped towards the wheel's own rigid motion (translation and spin are not
    # damped): tire carcass hysteresis. Without it a front-tire tread mode rang for seconds after a drop (zeta ~0.005)
    ("wheel_FL", ("FL_rim", "FL_tr"), "tire", "", "", ()), ("wheel_FR", ("FR_rim", "FR_tr"), "tire", "", "", ()),
    ("wheel_RL", ("RL_rim", "RL_tr"), "tire", "", "", ()), ("wheel_RR", ("RR_rim", "RR_tr"), "tire", "", "", ()),
]


''' + s[old_end:]
old = '''    for g, prefixes, mat, bg in DAMP_GROUPS:
        ids = [i for i, nm in enumerate(names) if nm.startswith(prefixes)]
        if len(ids) >= 4:
            B.sk.damp_group(g, ids, mat, bg)
            used.update(ids)'''
new = '''    for g, prefixes, mat, bg, ref, ref_bg in DAMP_GROUPS:
        ids = [i for i, nm in enumerate(names) if nm.startswith(prefixes)]
        if len(ids) >= 4:
            B.sk.damp_group(g, ids, mat, bg, reference=ref, ref_bg=ref_bg)
            used.update(ids)'''
assert s.count(old) == 1
s = s.replace(old, new)
h.write_text(s, encoding="utf-8")

patch(Path("sim/vehicle/hellcat/params.json"), [
    ('''    { "name": "skin",    "rate": 8 },
    { "name": "plastic", "rate": 14 },
    { "name": "glass",   "rate": 6 },
    { "name": "exhaust", "rate": 6 },''',
     '''    // relRate (D-038): towards the reference group's rigid motion (latch, hinge, clip, seal and hanger damping)
    { "name": "skin",    "rate": 8,  "relRate": 15 },
    { "name": "plastic", "rate": 14, "relRate": 15 },
    { "name": "glass",   "rate": 6,  "relRate": 15 },
    { "name": "exhaust", "rate": 6,  "relRate": 10 },'''),
])
print("patched")
