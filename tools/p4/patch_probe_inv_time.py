"""One-off (P4): the time of each mesh's largest turned-over area, so the crash result says when a cabin mesh turned
over (before the impact, in the pulse or in the rebound)."""
from pathlib import Path

p = Path("Unity/HellcatSandbox/Assets/Game/Views/SkinningProbe.cs")
s = p.read_text(encoding="utf-8")
pairs = [
    ('''        float[] runSpike, runInv, runSpikeOut, runInvOut, runInvA, runInvAOut;''',
     '''        float[] runSpike, runInv, runSpikeOut, runInvOut, runInvA, runInvAOut, runInvAT, runInvATOut;
        /// <summary>Simulation time of the next measurement (set by the caller; stamps the largest turned-over areas).</summary>
        public float time;'''),
    ('''                runInvA = new float[meshes.Count];
                runInvAOut = new float[meshes.Count];''',
     '''                runInvA = new float[meshes.Count];
                runInvAOut = new float[meshes.Count];
                runInvAT = new float[meshes.Count];
                runInvATOut = new float[meshes.Count];'''),
    ('''                    runInvA[k] = math.max(runInvA[k], fl);
                    runInvAOut[k] = math.max(runInvAOut[k], flo);''',
     '''                    if (fl > runInvA[k]) { runInvA[k] = fl; runInvAT[k] = time; }
                    if (flo > runInvAOut[k]) { runInvAOut[k] = flo; runInvATOut[k] = time; }'''),
    ('''        public void InvertedAreaSummary(out float cabinArea, out string cabinMesh, out float otherArea, out string otherMesh)
        {
            cabinArea = otherArea = 0f;
            cabinMesh = otherMesh = "";
            if (runInvA == null)
                return;
            for (int k = 0; k < meshes.Count; k++)
            {
                if (runInvA[k] > cabinArea) { cabinArea = runInvA[k]; cabinMesh = meshes[k].name; }
                if (runInvAOut[k] > otherArea) { otherArea = runInvAOut[k]; otherMesh = meshes[k].name; }
            }
        }''',
     '''        public void InvertedAreaSummary(out float cabinArea, out string cabinMesh, out float otherArea, out string otherMesh)
        {
            InvertedAreaSummary(out cabinArea, out cabinMesh, out _, out otherArea, out otherMesh, out _);
        }

        /// <summary>As above, with the times of the two largest areas and the cabin meshes above 1 cm2 as text.</summary>
        public string InvertedAreaSummary(out float cabinArea, out string cabinMesh, out float cabinTime, out float otherArea,
            out string otherMesh, out float otherTime)
        {
            cabinArea = otherArea = cabinTime = otherTime = 0f;
            cabinMesh = otherMesh = "";
            if (runInvA == null)
                return "";
            var l = new List<(float a, string n, float t)>();
            for (int k = 0; k < meshes.Count; k++)
            {
                if (runInvA[k] > cabinArea) { cabinArea = runInvA[k]; cabinMesh = meshes[k].name; cabinTime = runInvAT[k]; }
                if (runInvAOut[k] > otherArea) { otherArea = runInvAOut[k]; otherMesh = meshes[k].name; otherTime = runInvATOut[k]; }
                if (runInvA[k] > 1e-4f) l.Add((runInvA[k], meshes[k].name, runInvAT[k]));
            }
            l.Sort((x, y) => y.a.CompareTo(x.a));
            var sb = new System.Text.StringBuilder();
            for (int k = 0; k < math.min(8, l.Count); k++)
                sb.Append(k > 0 ? ", " : "").Append($"{l[k].n} {l[k].a * 1e4f:F1} cm2 at {l[k].t:F2} s");
            return sb.ToString();
        }'''),
]
for o, n in pairs:
    assert s.count(o) == 1, o[:90]
    s = s.replace(o, n)
p.write_text(s, encoding="utf-8")

p = Path("Unity/HellcatSandbox/Assets/Game/Scenario/CarCrashScenario.cs")
s = p.read_text(encoding="utf-8")
o = '''                probe.InvertedAreaSummary(out float cia, out string cim, out float oia, out string oim);
                sb.Append($"  \\"skin_cabin_inverted_cm2\\": {F(cia * 1e4, "F2")},\n  \\"skin_cabin_inverted_cm2_mesh\\": \\"{cim}\\",\n");
                sb.Append($"  \\"skin_other_inverted_cm2\\": {F(oia * 1e4, "F1")},\n  \\"skin_other_inverted_cm2_mesh\\": \\"{oim}\\",\n");'''
n = '''                string cabinInv = probe.InvertedAreaSummary(out float cia, out string cim, out float cit, out float oia, out string oim, out float oit);
                sb.Append($"  \\"skin_cabin_inverted_cm2\\": {F(cia * 1e4, "F2")},\n  \\"skin_cabin_inverted_cm2_mesh\\": \\"{cim}\\",\n");
                sb.Append($"  \\"skin_cabin_inverted_cm2_time_s\\": {F(cit, "F3")},\n  \\"skin_cabin_inverted_list\\": \\"{cabinInv}\\",\n");
                sb.Append($"  \\"skin_other_inverted_cm2\\": {F(oia * 1e4, "F1")},\n  \\"skin_other_inverted_cm2_mesh\\": \\"{oim}\\",\n");
                sb.Append($"  \\"skin_other_inverted_cm2_time_s\\": {F(oit, "F3")},\n");'''
assert s.count(o) == 1, "summary"
s = s.replace(o, n)
o = "                probe.Measure();"
assert s.count(o) == 1, "measure"
s = s.replace(o, "                probe.time = time;\n                probe.Measure();")
p.write_text(s, encoding="utf-8")
print("patched")
