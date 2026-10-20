"""One-off source patch (P3, D-033): deformation damping groups (data, build, reset, schedule, node force, metrics)."""
import sys
from pathlib import Path

SIM = Path(sys.argv[1])  # Unity/HellcatSandbox/Assets/Sim


def patch(path, reps):
    s = path.read_text(encoding="utf-8")
    for old, new in reps:
        if s.count(old) != 1:
            raise SystemExit(f"{path.name}: anchor found {s.count(old)} times:\n{old}")
        s = s.replace(old, new)
    path.write_text(s, encoding="utf-8")


patch(SIM / "Data" / "VehicleDef.cs", [
    ("""    [Serializable]
    public class PartDef""",
     """    [Serializable]
    public class DampGroupDef
    {
        public string name;
        public int[] nodes;        // each node in at most one damp group
        public string mat;         // params.json "dampGroupMaterials"
        public string bg;          // break group that ends the damping (a shattered pane), "" never
    }

    [Serializable]
    public class PartDef"""),
    ("""        public HingeDef[] hinges;  // shell bending elements of the panel skins (D-032)""",
     """        public HingeDef[] hinges;  // shell bending elements of the panel skins (D-032)
        public DampGroupDef[] dampGroups; // deformation damping relative to the group's rigid motion (D-033)"""),
    ("""            def.hinges ??= Array.Empty<HingeDef>();""",
     """            def.hinges ??= Array.Empty<HingeDef>();
            def.dampGroups ??= Array.Empty<DampGroupDef>();"""),
])

patch(SIM / "Data" / "SimParamsDef.cs", [
    ("""    [Serializable]
    public class ContactMaterialDef""",
     """    /// <summary>Deformation damping group material (D-033): velocity damping rate towards the group's rigid motion.</summary>
    [Serializable]
    public class DampGroupMaterialDef
    {
        public string name;
        public float rate;              // 1/s; a mode inside the group gets the damping ratio rate / (2 omega)
    }

    [Serializable]
    public class ContactMaterialDef"""),
    ("""        public HingeMaterialDef[] hingeMaterials;""",
     """        public HingeMaterialDef[] hingeMaterials;
        public DampGroupMaterialDef[] dampGroupMaterials;"""),
    ("""            hingeMaterials ??= Array.Empty<HingeMaterialDef>();""",
     """            hingeMaterials ??= Array.Empty<HingeMaterialDef>();
            dampGroupMaterials ??= Array.Empty<DampGroupMaterialDef>();"""),
    ("""        public HingeMaterialDef HingeMaterial(string name)""",
     """        public DampGroupMaterialDef DampGroupMaterial(string name)
        {
            foreach (var m in dampGroupMaterials)
                if (m.name == name)
                    return m;
            throw new InvalidDataException($"params.json: unknown damp group material '{name}'");
        }

        public HingeMaterialDef HingeMaterial(string name)"""),
])

patch(SIM / "Core" / "SoftBodyWorld.cs", [
    ("""            public int hingeStart, hingeCount;""",
     """            public int hingeStart, hingeCount;
            public int dampGroupStart, dampGroupCount;"""),
    ("""        public int HingeCount { get; private set; }""",
     """        public int HingeCount { get; private set; }
        public int DampGroupCount { get; private set; }"""),
    ("""        public NativeArray<double> hingeDampEnergy;
        // Pressure groups""",
     """        public NativeArray<double> hingeDampEnergy;
        // Deformation damping groups (D-033)
        public NativeArray<DampGroupStatic> dampGroups;
        public NativeArray<int> dampGroupNodes;
        public NativeArray<float3> dampForce;
        public NativeArray<double> dampGroupEnergy;
        // Pressure groups"""),
    ("""            int nTorsion = 0, nHinge = 0, nPressure = 0, nPressureTris = 0, nCollTris = 0;""",
     """            int nTorsion = 0, nHinge = 0, nDampGroup = 0, nDampNodes = 0, nPressure = 0, nPressureTris = 0, nCollTris = 0;"""),
    ("""                nSlots += 4 * b.hingeCount;
                b.pressureStart = nPressure;""",
     """                nSlots += 4 * b.hingeCount;
                b.dampGroupStart = nDampGroup;
                b.dampGroupCount = b.def.dampGroups.Length;
                nDampGroup += b.dampGroupCount;
                foreach (var dg in b.def.dampGroups)
                    nDampNodes += dg.nodes?.Length ?? 0;
                b.pressureStart = nPressure;"""),
    ("""            HingeCount = nHinge;""",
     """            HingeCount = nHinge;
            DampGroupCount = nDampGroup;"""),
    ("""            hingeDampEnergy = Alloc<double>(math.max(nHinge, 1));""",
     """            hingeDampEnergy = Alloc<double>(math.max(nHinge, 1));
            dampGroups = Alloc<DampGroupStatic>(math.max(nDampGroup, 1));
            dampGroupNodes = Alloc<int>(math.max(nDampNodes, 1));
            dampForce = Alloc<float3>(math.max(nNodes, 1));
            dampGroupEnergy = Alloc<double>(math.max(nDampGroup, 1));
            int dgCursor = 0;
            var inDampGroup = new bool[nNodes];"""),
    ("""                // Pressure groups (tire cavities), with cord pre-tension so the spawn shape is in equilibrium.""",
     """                // Deformation damping groups (D-033).
                for (int t = 0; t < b.dampGroupCount; t++)
                {
                    var dg = def.dampGroups[t];
                    var dgs = new DampGroupStatic
                    {
                        nodeStart = dgCursor,
                        nodeCount = dg.nodes?.Length ?? 0,
                        rate = math.max(b.prm.DampGroupMaterial(dg.mat).rate, 0f),
                        breakGroup = string.IsNullOrEmpty(dg.bg) || !b.groupNames.Contains(dg.bg) ? -1
                            : b.groupStart + b.groupNames.IndexOf(dg.bg),
                        body = bi,
                    };
                    for (int k = 0; k < dgs.nodeCount; k++)
                    {
                        int gn = b.nodeStart + dg.nodes[k];
                        if (inDampGroup[gn])
                            throw new InvalidDataException($"{b.name}: node {def.nodes[dg.nodes[k]].name} is in two damp groups");
                        inDampGroup[gn] = true;
                        dampGroupNodes[dgCursor++] = gn;
                    }
                    dampGroups[b.dampGroupStart + t] = dgs;
                }

                // Pressure groups (tire cavities), with cord pre-tension so the spawn shape is in equilibrium."""),
    ("""            for (int t = b.hingeStart; t < b.hingeStart + b.hingeCount; t++)
            {
                hingeRest[t] = hinges[t].phi0;""",
     """            for (int t = b.dampGroupStart; t < b.dampGroupStart + b.dampGroupCount; t++)
            {
                dampGroupEnergy[t] = 0.0;
                var dg = dampGroups[t];
                for (int k = dg.nodeStart; k < dg.nodeStart + dg.nodeCount; k++)
                    dampForce[dampGroupNodes[k]] = float3.zero;
            }
            for (int t = b.hingeStart; t < b.hingeStart + b.hingeCount; t++)
            {
                hingeRest[t] = hinges[t].phi0;"""),
    ("""            var hingeJob = MakeHingeJob();""",
     """            var hingeJob = MakeHingeJob();
            var dampJob = MakeDampJob();"""),
    ("""                    hingeCount = HingeCount,
                    nodeCount = NodeCount,""",
     """                    hingeCount = HingeCount,
                    dampGroupCount = DampGroupCount,
                    nodeCount = NodeCount,"""),
    ("""                    hingeJob = hingeJob,
                    contact = contactJob,""",
     """                    hingeJob = hingeJob,
                    dampJob = dampJob,
                    contact = contactJob,"""),
    ("""                if (HingeCount > 0)
                    h = hingeJob.Schedule(HingeCount, hingeBatch, h);""",
     """                if (HingeCount > 0)
                    h = hingeJob.Schedule(HingeCount, hingeBatch, h);
                if (DampGroupCount > 0)
                    h = dampJob.Schedule(DampGroupCount, 1, h);"""),
    ("""        HingeForceJob MakeHingeJob() => new HingeForceJob""",
     """        GroupDampJob MakeDampJob() => new GroupDampJob
        {
            dt = dt,
            trackEnergy = trackEnergy ? 1 : 0,
            pos = pos,
            vel = vel,
            invMass = invMass,
            groupDone = groupDone,
            groups = dampGroups,
            groupNodes = dampGroupNodes,
            dampForce = dampForce,
            groupDampEnergy = dampGroupEnergy,
        };

        HingeForceJob MakeHingeJob() => new HingeForceJob"""),
    ("""            useDynamic = CollisionEnabled ? 1 : 0,
            dynForce = dynForce,
            contactWork = contactWork,""",
     """            useDynamic = CollisionEnabled ? 1 : 0,
            dynForce = dynForce,
            dampForce = dampForce,
            contactWork = contactWork,"""),
    ("""            for (int t = b.hingeStart; t < b.hingeStart + b.hingeCount; t++)
            {
                r.damping += hingeDampEnergy[t];""",
     """            for (int t = b.dampGroupStart; t < b.dampGroupStart + b.dampGroupCount; t++)
                r.damping += dampGroupEnergy[t];
            for (int t = b.hingeStart; t < b.hingeStart + b.hingeCount; t++)
            {
                r.damping += hingeDampEnergy[t];"""),
])

patch(SIM / "Core" / "SimJobs.cs", [
    ("""        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> dynForce;""",
     """        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> dynForce;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> dampForce;  // deformation damping (D-033)"""),
    ("""            float3 f = prm.gravity * m + extForce[i];""",
     """            float3 f = prm.gravity * m + extForce[i] + dampForce[i];"""),
])

patch(SIM / "Core" / "SerialPhaseJob.cs", [
    ("""        public int beamCount, hingeCount, nodeCount;""",
     """        public int beamCount, hingeCount, dampGroupCount, nodeCount;"""),
    ("""        public HingeForceJob hingeJob;""",
     """        public HingeForceJob hingeJob;
        public GroupDampJob dampJob;"""),
    ("""                for (int h = 0; h < hingeCount; h++)
                    hingeJob.Execute(h);""",
     """                for (int h = 0; h < hingeCount; h++)
                    hingeJob.Execute(h);
                for (int g = 0; g < dampGroupCount; g++)
                    dampJob.Execute(g);"""),
])
print("patched")
