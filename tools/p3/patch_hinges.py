"""One-off source patch (P3, D-032): shell bending hinges in SoftBodyWorld.cs (arrays, build, reset, schedule, metrics),
the single-thread step job and the stability report."""
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


patch(SIM / "Core" / "SoftBodyWorld.cs", [
    ("""            public int torsionStart, torsionCount;
            public int pressureStart, pressureCount;""",
     """            public int torsionStart, torsionCount;
            public int hingeStart, hingeCount;
            public int pressureStart, pressureCount;"""),
    ("""        public int TorsionBarCount { get; private set; }
        public int PressureGroupCount { get; private set; }""",
     """        public int TorsionBarCount { get; private set; }
        public int HingeCount { get; private set; }
        public int PressureGroupCount { get; private set; }
        public int hingeBatch = 128;"""),
    ("""        public NativeArray<double> torsionDampEnergy;
        // Pressure groups""",
     """        public NativeArray<double> torsionDampEnergy;
        // Shell bending hinges (D-032)
        public NativeArray<HingeStatic> hinges;
        public NativeArray<float> hingeRest, hingeYield, hingeAngle, hingePlastic;
        public NativeArray<byte> hingeBroken;
        public NativeArray<double> hingeDampEnergy;
        // Pressure groups"""),
    ("""            int nTorsion = 0, nPressure = 0, nPressureTris = 0, nCollTris = 0;""",
     """            int nTorsion = 0, nHinge = 0, nPressure = 0, nPressureTris = 0, nCollTris = 0;"""),
    ("""                nSlots += 4 * b.torsionCount;
                b.pressureStart = nPressure;""",
     """                nSlots += 4 * b.torsionCount;
                b.hingeStart = nHinge;
                b.hingeCount = b.def.hinges.Length;
                nHinge += b.hingeCount;
                nSlots += 4 * b.hingeCount;
                b.pressureStart = nPressure;"""),
    ("""            TorsionBarCount = nTorsion;
            PressureGroupCount = nPressure;""",
     """            TorsionBarCount = nTorsion;
            HingeCount = nHinge;
            PressureGroupCount = nPressure;"""),
    ("""            torsionDampEnergy = Alloc<double>(nTorsion);
            pressureGroups = Alloc<PressureGroupStatic>(nPressure);""",
     """            torsionDampEnergy = Alloc<double>(nTorsion);
            hinges = Alloc<HingeStatic>(math.max(nHinge, 1));
            hingeRest = Alloc<float>(math.max(nHinge, 1));
            hingeYield = Alloc<float>(math.max(nHinge, 1));
            hingeAngle = Alloc<float>(math.max(nHinge, 1));
            hingePlastic = Alloc<float>(math.max(nHinge, 1));
            hingeBroken = Alloc<byte>(math.max(nHinge, 1));
            hingeDampEnergy = Alloc<double>(math.max(nHinge, 1));
            pressureGroups = Alloc<PressureGroupStatic>(nPressure);"""),
    ("""                // Pressure groups (tire cavities), with cord pre-tension so the spawn shape is in equilibrium.""",
     """                // Shell bending hinges of the panel skins (D-032).
                for (int t = 0; t < b.hingeCount; t++)
                    hinges[b.hingeStart + t] = BuildHinge(b, bi, t, pairBeam, slotOwner, ref slotCursor);

                // Pressure groups (tire cavities), with cord pre-tension so the spawn shape is in equilibrium."""),
    ("""        static bool IsCollisionTri(TriDef td)""",
     """        /// <summary>
        /// One panel hinge: the plate values of its material scaled by the geometry of the two triangles,
        /// k = D |e|^2 / (A1 + A2) * HingeConst.Geometry (the same for the damping), yield = m_y |e|.
        /// </summary>
        HingeStatic BuildHinge(Body b, int bi, int t, Dictionary<long, int> pairBeam, int[] slotOwner, ref int slotCursor)
        {
            var hd = b.def.hinges[t];
            if (hd.n == null || hd.n.Length != 4)
                throw new InvalidDataException($"{b.name}: hinge {t} needs 4 nodes");
            var mat = b.prm.HingeMaterial(hd.mat);
            var h = new HingeStatic
            {
                n1 = b.nodeStart + hd.n[0], n2 = b.nodeStart + hd.n[1], n3 = b.nodeStart + hd.n[2], n4 = b.nodeStart + hd.n[3],
                slotStart = slotCursor,
                body = bi,
            };
            float3 x1 = pos0[h.n1], x2 = pos0[h.n2], x3 = pos0[h.n3], x4 = pos0[h.n4];
            float e2 = math.distancesq(x2, x3);
            float area = 0.5f * (math.length(math.cross(x2 - x1, x3 - x1)) + math.length(math.cross(x3 - x4, x2 - x4)));
            if (area < 1e-8f || !TorsionKernel.Gradient(x1, x2, x3, x4, out h.phi0, out _, out _, out _, out _))
                throw new InvalidDataException($"{b.name}: hinge {t} is degenerate");
            float geo = HingeConst.Geometry * e2 / area;
            h.k = mat.bend * geo;
            h.c = math.max(mat.damp, 0f) * geo;
            float len = math.sqrt(e2);
            h.yield0 = mat.yieldMoment > 0f ? mat.yieldMoment * len : float.MaxValue;
            h.hardening = math.max(mat.hardening, 0f) * len;
            h.yieldCap = mat.yieldCap > 0f ? math.max(mat.yieldCap * len, h.yield0) : float.MaxValue;
            h.beam12 = pairBeam.TryGetValue(PairKey(h.n1, h.n2), out int b12) ? b12 : -1;
            h.beam23 = pairBeam.TryGetValue(PairKey(h.n2, h.n3), out int b23) ? b23 : -1;
            h.beam34 = pairBeam.TryGetValue(PairKey(h.n3, h.n4), out int b34) ? b34 : -1;
            slotOwner[slotCursor++] = h.n1;
            slotOwner[slotCursor++] = h.n2;
            slotOwner[slotCursor++] = h.n3;
            slotOwner[slotCursor++] = h.n4;
            return h;
        }

        static bool IsCollisionTri(TriDef td)"""),
    ("""            for (int g = b.pressureStart; g < b.pressureStart + b.pressureCount; g++)
            {
                var pg = pressureGroups[g];""",
     """            for (int t = b.hingeStart; t < b.hingeStart + b.hingeCount; t++)
            {
                hingeRest[t] = hinges[t].phi0;
                hingeYield[t] = hinges[t].yield0;
                hingeBroken[t] = 0;
                hingeAngle[t] = 0f;
                hingePlastic[t] = 0f;
                hingeDampEnergy[t] = 0.0;
            }
            for (int g = b.pressureStart; g < b.pressureStart + b.pressureCount; g++)
            {
                var pg = pressureGroups[g];"""),
    ("""            var serial = MakeSerialJob();
            var beamJob = MakeBeamJob();""",
     """            var serial = MakeSerialJob();
            var beamJob = MakeBeamJob();
            var hingeJob = MakeHingeJob();"""),
    ("""                    beamCount = BeamCount,
                    nodeCount = NodeCount,""",
     """                    beamCount = BeamCount,
                    hingeCount = HingeCount,
                    nodeCount = NodeCount,"""),
    ("""                    beams = beamJob,
                    contact = contactJob,""",
     """                    beams = beamJob,
                    hingeJob = hingeJob,
                    contact = contactJob,"""),
    ("""                h = beamJob.Schedule(BeamCount, beamBatch, h);
                if (coll != 0)""",
     """                h = beamJob.Schedule(BeamCount, beamBatch, h);
                if (HingeCount > 0)
                    h = hingeJob.Schedule(HingeCount, hingeBatch, h);
                if (coll != 0)"""),
    ("""        BeamForceJob MakeBeamJob() => new BeamForceJob""",
     """        HingeForceJob MakeHingeJob() => new HingeForceJob
        {
            dt = dt,
            trackEnergy = trackEnergy ? 1 : 0,
            pos = pos,
            vel = vel,
            broken = broken,
            hinges = hinges,
            hingeRest = hingeRest,
            hingeYield = hingeYield,
            hingeBroken = hingeBroken,
            hingeAngle = hingeAngle,
            hingePlastic = hingePlastic,
            hingeDampEnergy = hingeDampEnergy,
            slotForce = slotForce,
        };

        BeamForceJob MakeBeamJob() => new BeamForceJob"""),
    ("""            public double kinetic, gravity, elastic, torsion, pressure;   // J, stored / potential (relative to spawn)""",
     """            public double kinetic, gravity, elastic, torsion, pressure;   // J, stored / potential (relative to spawn);
                                                                          // torsion includes the panel hinges"""),
    ("""            public int brokenBeams, plasticBeams;""",
     """            public int brokenBeams, plasticBeams, plasticHinges;"""),
    ("""            for (int pg = b.pressureStart; pg < b.pressureStart + b.pressureCount && energies; pg++)""",
     """            for (int t = b.hingeStart; t < b.hingeStart + b.hingeCount; t++)
            {
                r.damping += hingeDampEnergy[t];
                r.plastic += hingePlastic[t];
                if (math.abs(TorsionKernel.Wrap(hingeRest[t] - hinges[t].phi0)) > 1e-4f)
                    r.plasticHinges++;
                if (hingeBroken[t] != 0 || !energies)
                    continue;
                var h = hinges[t];
                if (TorsionKernel.Gradient(pos[h.n1], pos[h.n2], pos[h.n3], pos[h.n4], out float phi, out _, out _, out _, out _))
                {
                    float d = TorsionKernel.Wrap(phi - hingeRest[t]);
                    r.torsion += 0.5 * h.k * d * d;
                }
            }
            for (int pg = b.pressureStart; pg < b.pressureStart + b.pressureCount && energies; pg++)"""),
])

patch(SIM / "Core" / "SerialPhaseJob.cs", [
    ("""        public int beamCount, nodeCount;""",
     """        public int beamCount, hingeCount, nodeCount;"""),
    ("""        public BeamForceJob beams;
        public NodeContactJob contact;""",
     """        public BeamForceJob beams;
        public HingeForceJob hingeJob;
        public NodeContactJob contact;"""),
    ("""                for (int b = 0; b < beamCount; b++)
                    beams.Execute(b);""",
     """                for (int b = 0; b < beamCount; b++)
                    beams.Execute(b);
                for (int h = 0; h < hingeCount; h++)
                    hingeJob.Execute(h);"""),
])

patch(SIM / "Core" / "StabilityReport.cs", [
    ("""    ///     (axial k, limit springs), the torsion bars (k_t g g^T) and the geometric stiffness of pre-tensioned""",
     """    ///     (axial k, limit springs), the torsion bars and panel hinges (k_t g g^T, D-032) and the geometric stiffness of pre-tensioned"""),
    ("""            int nt = extras ? w.TorsionBarCount : 0;
            var tg = new double3[nt * 4];
            var tn = new int[nt * 4];
            var tw = new double[nt];
            for (int t = 0; t < nt; t++)
            {
                var tb = w.torsionBars[t];
                tn[4 * t] = tb.n1;
                tn[4 * t + 1] = tb.n2;
                tn[4 * t + 2] = tb.n3;
                tn[4 * t + 3] = tb.n4;
                if (TorsionKernel.Gradient(w.pos[tb.n1], w.pos[tb.n2], w.pos[tb.n3], w.pos[tb.n4], out _,
                        out float3 g1, out float3 g2, out float3 g3, out float3 g4) && w.torsionBroken[t] == 0)
                {
                    tg[4 * t] = g1;
                    tg[4 * t + 1] = g2;
                    tg[4 * t + 2] = g3;
                    tg[4 * t + 3] = g4;
                    tw[t] = dt * dt * tb.k + 2.0 * dt * tb.c;
                }
            }""",
     """            // dihedral elements: the torsion bars (with extras) and the panel hinges (always: they are panel stiffness)
            int ntb = extras ? w.TorsionBarCount : 0;
            int nt = ntb + w.HingeCount;
            var tg = new double3[nt * 4];
            var tn = new int[nt * 4];
            var tw = new double[nt];
            for (int t = 0; t < nt; t++)
            {
                int4 q4;
                float k, c;
                bool off;
                if (t < ntb)
                {
                    var tb = w.torsionBars[t];
                    q4 = new int4(tb.n1, tb.n2, tb.n3, tb.n4);
                    k = tb.k;
                    c = tb.c;
                    off = w.torsionBroken[t] != 0;
                }
                else
                {
                    var hb = w.hinges[t - ntb];
                    q4 = new int4(hb.n1, hb.n2, hb.n3, hb.n4);
                    k = hb.k;
                    c = hb.c;
                    off = w.hingeBroken[t - ntb] != 0;
                }
                tn[4 * t] = q4.x;
                tn[4 * t + 1] = q4.y;
                tn[4 * t + 2] = q4.z;
                tn[4 * t + 3] = q4.w;
                if (!off && TorsionKernel.Gradient(w.pos[q4.x], w.pos[q4.y], w.pos[q4.z], w.pos[q4.w], out _,
                        out float3 g1, out float3 g2, out float3 g3, out float3 g4))
                {
                    tg[4 * t] = g1;
                    tg[4 * t + 1] = g2;
                    tg[4 * t + 2] = g3;
                    tg[4 * t + 3] = g4;
                    tw[t] = dt * dt * k + 2.0 * dt * c;
                }
            }"""),
])

# hinge constant next to the job
hj = SIM / "Core" / "HingeJob.cs"
s = hj.read_text(encoding="utf-8")
if "class HingeConst" not in s:
    s = s.replace("""namespace Hellcat.Sim
{""", """namespace Hellcat.Sim
{
    public static class HingeConst
    {
        /// <summary>
        /// k_e = D |e|^2 / (A1 + A2) * Geometry: discrete-shell scaling of the plate bending stiffness D to one edge
        /// hinge (calibrated by tools/skeleton/hinges.py --calibrate against the simply supported square plate).
        /// </summary>
        public const float Geometry = 1f;
    }
""", 1)
    hj.write_text(s, encoding="utf-8")
print("patched")
