"""One-off (P3b): tire params section (mesh rolling-resistance share) and X10 variants for lateral stiffness/friction."""
from pathlib import Path

ROOT = Path("Unity/HellcatSandbox/Assets/Sim")


def patch(path, pairs):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:100])
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")


patch("Data/SimParamsDef.cs", [(
    """    [Serializable]
    public class PressureParamsDef""",
    """    /// <summary>Tire model values that are not beam, hinge, damp-group or contact materials.</summary>
    [Serializable]
    public class TireDef
    {
        // rolling resistance the tire mesh produces by itself at moderate speed (carcass hysteresis, contact, D-043):
        // the wheel couple adds only the rest of the surface's coefficient
        public float meshRollingResistance = 0f;
    }

    [Serializable]
    public class PressureParamsDef"""), (
    """        public AeroDef aero;
        public PressureParamsDef pressure;""",
    """        public AeroDef aero;
        public TireDef tire;
        public PressureParamsDef pressure;"""), (
    """            aero ??= new AeroDef();
            pressure ??= new PressureParamsDef();""",
    """            aero ??= new AeroDef();
            tire ??= new TireDef();
            pressure ??= new PressureParamsDef();""")])

patch("Vehicle/VehicleTypes.cs", [(
    """        public float rollingResistance;      // coefficient (multiplied by the surface value)""",
    """        public float meshRollingResistance;  // C_rr the tire mesh produces itself (subtracted from the surface value, D-043)""")])

patch("Core/SoftBodyWorld.cs", [(
    """                    rollingResistance = 1f,""",
    """                    meshRollingResistance = math.max(b.prm.tire.meshRollingResistance, 0f),""")])

patch("Vehicle/VehicleControlJob.cs", [(
    """                float crr = load > 1f ? rr / load * ws.rollingResistance : 0f;""",
    """                // the surface's rolling resistance minus what the tire mesh dissipates by itself (D-043)
                float crr = load > 1f ? math.max(rr / load - ws.meshRollingResistance, 0f) : 0f;""")])

patch("Validation/TireTests.cs", [(
    """        static List<TireVariant> TuningVariants()
        {
            var list = new List<TireVariant>
            {""",
    """        /// <summary>Cross-section braces of the tire (bead to the opposite shoulder, both ways): lateral shear stiffness of
        /// the carcass (the inflated carcass of a real tire is laterally much stiffer than the radial sidewall cords).</summary>
        public static void AddCrossBraces(VehicleDef d, string mat)
        {
            var index = new Dictionary<string, int>();
            for (int i = 0; i < d.nodes.Length; i++)
                index[d.nodes[i].name] = i;
            var list = new List<BeamDef>(d.beams);
            foreach (var w in new[] { "FR", "FL", "RR", "RL" })
                for (int k = 0; index.ContainsKey($"{w}_trC{k}"); k++)
                {
                    list.Add(new BeamDef { a = index[$"{w}_rimI{k}"], b = index[$"{w}_trO{k}"], type = "NORMAL", mat = mat, bg = "", pre = 1f, hydro = "" });
                    list.Add(new BeamDef { a = index[$"{w}_rimO{k}"], b = index[$"{w}_trI{k}"], type = "NORMAL", mat = mat, bg = "", pre = 1f, hydro = "" });
                }
            d.beams = list.ToArray();
        }

        static void AddCrossMaterial(SimParamsDef p, float k)
        {
            var list = new List<BeamMaterialDef>(p.materials);
            list.RemoveAll(m => m.name == "tire_side_x");
            list.Add(new BeamMaterialDef { name = "tire_side_x", spring = k, damp = 12.5f, velSplit = 0.3f, dampFast = 0f, dampReboundFast = 0f, inflationShare = 0.95f });
            p.materials = list.ToArray();
        }

        static void Mu(SimParamsDef p, float muS, float muK)
        {
            foreach (var c in p.contactMaterials)
                if (c.name == "tire") { c.muStatic = muS; c.muSliding = muK; }
        }

        static List<TireVariant> TuningVariants()
        {
            var list = new List<TireVariant>
            {
                new TireVariant { name = "base" },
                new TireVariant { name = "xbrace_40k", prm = p => AddCrossMaterial(p, 40000f), def = d => AddCrossBraces(d, "tire_side_x") },
                new TireVariant { name = "xbrace_100k", prm = p => AddCrossMaterial(p, 100000f), def = d => AddCrossBraces(d, "tire_side_x") },
                new TireVariant { name = "mu_1.3_1.05", prm = p => Mu(p, 1.3f, 1.05f) },
                new TireVariant { name = "xbrace_100k_mu_1.3_1.05", prm = p => { AddCrossMaterial(p, 100000f); Mu(p, 1.3f, 1.05f); }, def = d => AddCrossBraces(d, "tire_side_x") },
            };
            return list;
        }

        static List<TireVariant> TuningVariantsOld()
        {
            var list = new List<TireVariant>
            {""")])
print("patched")
