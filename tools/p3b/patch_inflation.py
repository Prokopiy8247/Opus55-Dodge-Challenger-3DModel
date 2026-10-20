"""One-off (P3b): inflation-dependent carcass stiffness (D-045), spin tension in the stability report, reset of the
damp-group rigid motion."""
from pathlib import Path

ROOT = Path("Unity/HellcatSandbox/Assets/Sim")


def patch(path, pairs):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:90])
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")


patch("Core/SimTypes.cs", [(
    """        public int spinGroup;                 // -1: none; else a ring beam of a spinning wheel group: tension spinCoef |w|^2""",
    """        public float inflationShare;          // share of k that comes from the inflation: k (1 - share (1 - inflation))
                                              // for a cavity beam (D-045); the flat tire keeps the carcass part
        public int spinGroup;                 // -1: none; else a ring beam of a spinning wheel group: tension spinCoef |w|^2""")])

patch("Data/SimParamsDef.cs", [(
    """        public float preload = 0;       // N, compression the beam carries at its spawn length (suspension springs at""",
    """        public float inflationShare = 0; // tire cavity beams: share of the spring that comes from the inflation pressure
                                        // (D-045): k_eff = k (1 - share (1 - inflation)), inflation = gas content / spawn
        public float preload = 0;       // N, compression the beam carries at its spawn length (suspension springs at""")])

patch("Core/Kernels.cs", [(
    """        public static float3 Compute(in BeamStatic s, float3 pa, float3 pb, float3 va, float3 vb,
            float hydroInput, float spawnBlend, float pretension, ref float rest, ref float yield, ref byte broken,
            ref float plasticWork, ref float breakEnergy, out float stress, out byte triggered, out float dampPower)
        {""",
    """        /// <param name="stiffScale">spring scale (inflation-dependent carcass stiffness of tire beams, D-045; 1 otherwise)</param>
        public static float3 Compute(in BeamStatic s, float3 pa, float3 pb, float3 va, float3 vb,
            float hydroInput, float spawnBlend, float pretension, float stiffScale, ref float rest, ref float yield, ref byte broken,
            ref float plasticWork, ref float breakEnergy, out float stress, out byte triggered, out float dampPower)
        {"""), (
    """            float kE = (s.type == BeamType.Anisotropic && extended) ? s.kExp : s.k;""",
    """            float kE = ((s.type == BeamType.Anisotropic && extended) ? s.kExp : s.k) * stiffScale;""")])

patch("Core/SimJobs.cs", [(
    """            float pre = s.pressureGroup >= 0 ? s.pretension * pressureScale[s.pressureGroup] : 0f;""",
    """            float pre = 0f, stiff = 1f;
            if (s.pressureGroup >= 0)
            {
                float inflation = pressureScale[s.pressureGroup];
                pre = s.pretension * inflation;
                stiff = 1f - s.inflationShare * (1f - inflation);
            }"""), (
    """            float3 f = BeamKernel.Compute(s, pos[s.a], pos[s.b], vel[s.a], vel[s.b], h, spawnBlend[s.body], pre,""",
    """            float3 f = BeamKernel.Compute(s, pos[s.a], pos[s.b], vel[s.a], vel[s.b], h, spawnBlend[s.body], pre, stiff,""")])

patch("Core/SoftBodyWorld.cs", [(
    """            s.pressureGroup = -1;
            s.spinGroup = -1;
            return s;
        }""",
    """            s.pressureGroup = -1;
            s.inflationShare = math.saturate(m.inflationShare);
            s.spinGroup = -1;
            return s;
        }"""), (
    # every cavity cord belongs to the pressure group (inflation scale), also without pre-tension
    """                if (s.type != BeamType.Hydro && s.type != BeamType.Support && s.k > 0f)
                    cords.Add(j);
            }""",
    """                if (s.type != BeamType.Hydro && s.type != BeamType.Support && s.k > 0f)
                {
                    cords.Add(j);
                    s.pressureGroup = (short)gg;
                    beams[j] = s;
                }
            }"""), (
    """            double k = s.type == BeamType.Anisotropic && x > 0.0 ? s.kExp : s.k;
            e += 0.5 * k * x * x;""",
    """            double k = s.type == BeamType.Anisotropic && x > 0.0 ? s.kExp : s.k;
            if (s.pressureGroup >= 0)
                k *= 1.0 - s.inflationShare * (1.0 - pressureScale[s.pressureGroup]);
            e += 0.5 * k * x * x;"""), (
    """            for (int t = b.dampGroupStart; t < b.dampGroupStart + b.dampGroupCount; t++)
            {
                dampGroupEnergy[t] = 0.0;""",
    """            for (int t = b.dampGroupStart; t < b.dampGroupStart + b.dampGroupCount; t++)
            {
                dampGroupEnergy[t] = 0.0;
                dampRigid[t] = default;"""), (
    """        /// <summary>Rest length of a beam at spawn (for deformation displays).</summary>""",
    """        /// <summary>Hoop tension (N) a ring beam of a spinning wheel carries now (D-044): spinCoef |w|^2 of its group's
        /// rigid rotation in the last substep; 0 for other beams.</summary>
        public float SpinTension(int beam)
        {
            var s = beams[beam];
            if (s.spinGroup < 0)
                return 0f;
            var rg = dampRigid[s.spinGroup];
            return rg.valid != 0 ? s.spinCoef * (float)math.lengthsq(rg.w) : 0f;
        }

        /// <summary>Rest length of a beam at spawn (for deformation displays).</summary>""")])

patch("Core/StabilityReport.cs", [(
    """                double t = b.pressureGroup >= 0 ? b.pretension * w.pressureScale[b.pressureGroup] : 0.0;""",
    """                // geometric stiffness of tensioned beams: tire cord pre-tension (D-028) and the hoop tension of a
                // spinning wheel's rings (D-044, state dependent: zero at rest)
                double t = (b.pressureGroup >= 0 ? b.pretension * w.pressureScale[b.pressureGroup] : 0.0) + w.SpinTension(j);""")])
print("patched")
