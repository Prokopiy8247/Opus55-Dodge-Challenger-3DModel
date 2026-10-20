"""P6: material zones in params.json - the plastic and break thresholds of one part's beams inside a model-space box,
scaled (crease initiators, softened or reinforced sections) without regenerating the skeleton. Springs and dampers
are untouched, so the stability criterion S does not change."""
import io
from pathlib import Path

A = Path(r"W:/YouTube/3D Model Dodge Challenger/Unity/HellcatSandbox/Assets")


def patch(rel, pairs):
    p = A / rel
    raw = io.open(p, encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in raw else "\n"
    s = raw.replace("\r\n", "\n")
    for a, b in pairs:
        if s.count(a) != 1:
            raise SystemExit(f"{rel}: {s.count(a)} x {a[:70]!r}")
        s = s.replace(a, b)
    io.open(p, "w", encoding="utf-8", newline="").write(s.replace("\n", nl))
    print("patched", rel)


patch("Sim/Data/SimParamsDef.cs", [
    ("    [Serializable]\n    public class PressureParamsDef\n",
     "    /// <summary>The plastic and break thresholds of one part's beams whose midpoint (model space) lies in a box, scaled:\n"
     "    /// crease initiators and softened or reinforced sections tuned without regenerating the skeleton (P6). Springs and\n"
     "    /// dampers are left alone (the stability criterion does not change).</summary>\n"
     "    [Serializable]\n    public class MaterialZoneDef\n    {\n"
     "        public string part;                  // both nodes of the beam in this part\n"
     "        public string[] materials;           // only these beam materials (empty: all)\n"
     "        public float[] min, max;             // model-space box of the beam's midpoint (m)\n"
     "        public float deformScale = 1f, hardeningScale = 1f, capScale = 1f, strengthScale = 1f;\n"
     "    }\n\n"
     "    [Serializable]\n    public class PressureParamsDef\n"),
    ("        public PressureParamsDef pressure;\n",
     "        public PressureParamsDef pressure;\n        public MaterialZoneDef[] materialZones;\n"),
    ("            pressure ??= new PressureParamsDef();\n",
     "            pressure ??= new PressureParamsDef();\n            materialZones ??= Array.Empty<MaterialZoneDef>();\n"),
])

patch("Sim/Core/SoftBodyWorld.cs", [
    ("                    var s = Resolve(bd, mat, math.distance(pa, pb));\n",
     "                    var s = Resolve(bd, mat, math.distance(pa, pb));\n                    ApplyZones(b.prm, def, bd, ref s);\n"),
    ("        /// <summary>Material + beam definition -> runtime parameters (lengths resolved from the spawn length).</summary>\n",
     "        /// <summary>Material zones (params.materialZones): the thresholds of a part's beams inside a model-space box, scaled.</summary>\n"
     "        static void ApplyZones(SimParamsDef prm, VehicleDef def, BeamDef bd, ref BeamStatic s)\n"
     "        {\n"
     "            if (prm.materialZones == null || prm.materialZones.Length == 0)\n"
     "                return;\n"
     "            var na = def.nodes[bd.a];\n"
     "            var nb = def.nodes[bd.b];\n"
     "            foreach (var z in prm.materialZones)\n"
     "            {\n"
     "                if (na.part != z.part || nb.part != z.part) continue;\n"
     "                if (z.materials != null && z.materials.Length > 0 && Array.IndexOf(z.materials, bd.mat) < 0) continue;\n"
     "                bool inside = z.min != null && z.max != null && z.min.Length == 3 && z.max.Length == 3;\n"
     "                for (int k = 0; k < 3 && inside; k++)\n"
     "                {\n"
     "                    float mid = 0.5f * (na.p[k] + nb.p[k]);\n"
     "                    inside = mid >= z.min[k] && mid <= z.max[k];\n"
     "                }\n"
     "                if (!inside) continue;\n"
     "                if (s.yield0 < float.MaxValue) s.yield0 *= z.deformScale;\n"
     "                s.hardening *= z.hardeningScale;\n"
     "                if (s.yieldCap < float.MaxValue) s.yieldCap *= z.capScale;\n"
     "                if (s.strength < float.MaxValue) s.strength *= z.strengthScale;\n"
     "            }\n"
     "        }\n\n"
     "        /// <summary>Material + beam definition -> runtime parameters (lengths resolved from the spawn length).</summary>\n"),
])
