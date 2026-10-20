"""One-off (P4): SkinningProbe keeps per mesh the largest spike and inverted share of the whole run and splits them into
the cabin (meshes centred between the C-pillar and the A-pillar base, wheels and running gear excluded) and the rest
(crush zones, wheels): gate G-Crash holds the cabin to "no spikes, no inversion"; folded crush-zone sheet is reported."""
from pathlib import Path


def edit(path, pairs):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    for o, n in pairs:
        assert s.count(o) == 1, (path, o[:80])
        s = s.replace(o, n)
    p.write_text(s, encoding="utf-8")


edit("Unity/HellcatSandbox/Assets/Game/Views/SkinningProbe.cs", [
    ('''        struct MeshData
        {
            public string name;
            public int vStart, vCount, tStart, tCount, boneStart, boneCount;
        }''',
     '''        struct MeshData
        {
            public string name;
            public int vStart, vCount, tStart, tCount, boneStart, boneCount;
        }

        // per mesh over the whole run: largest spike, largest inverted share; cabin flag from the first measurement
        float[] runSpike, runInv;
        bool[] cabin;'''),
    ('''            if (!haveRef)
            {
                NativeArray<float3>.Copy(skinned, refPos);
                haveRef = true;
            }''',
     '''            if (!haveRef)
            {
                NativeArray<float3>.Copy(skinned, refPos);
                haveRef = true;
                // the cabin: meshes centred between the C-pillar and the A-pillar base (car at its spawn, +z forward)
                runSpike = new float[meshes.Count];
                runInv = new float[meshes.Count];
                cabin = new bool[meshes.Count];
                for (int k = 0; k < meshes.Count; k++)
                {
                    var md = meshes[k];
                    double z = 0;
                    for (int v = md.vStart; v < md.vStart + md.vCount; v++) z += refPos[v].z;
                    z /= math.max(md.vCount, 1);
                    bool running = md.name.Contains("Wheel_") || md.name.Contains("Susp_") || md.name.Contains("Shaft") ||
                                   md.name.Contains("Knuckles") || md.name.Contains("Exhaust");
                    cabin[k] = !running && z > -1.1 && z < 0.9;
                }
            }
            else
            {
                for (int k = 0; k < meshes.Count; k++)
                {
                    var md = meshes[k];
                    float sp = 0f;
                    for (int v = md.vStart; v < md.vStart + md.vCount; v++) sp = math.max(sp, vSpike[v]);
                    int fl = 0;
                    for (int t = md.tStart; t < md.tStart + md.tCount; t++) fl += triFlip[t];
                    runSpike[k] = math.max(runSpike[k], sp);
                    runInv[k] = math.max(runInv[k], md.tCount > 0 ? fl / (float)md.tCount : 0f);
                }
            }'''),
    ('''        /// <summary>Per mesh: the largest distance of a vertex from where a rigid motion''',
     '''        /// <summary>Largest spike and inverted share over the run in the cabin and elsewhere, with the worst meshes.</summary>
        public void RegionSummary(out float cabinSpike, out float cabinInv, out float otherSpike, out float otherInv,
            out string worstCabin, out string worstOther)
        {
            cabinSpike = cabinInv = otherSpike = otherInv = 0f;
            worstCabin = worstOther = "";
            if (runSpike == null)
                return;
            var cab = new List<(string, float, float)>();
            var oth = new List<(string, float, float)>();
            for (int k = 0; k < meshes.Count; k++)
            {
                (cabin[k] ? cab : oth).Add((meshes[k].name, runSpike[k], runInv[k]));
                if (cabin[k]) { cabinSpike = math.max(cabinSpike, runSpike[k]); cabinInv = math.max(cabinInv, runInv[k]); }
                else { otherSpike = math.max(otherSpike, runSpike[k]); otherInv = math.max(otherInv, runInv[k]); }
            }
            string Top(List<(string n, float s, float i)> l)
            {
                l.Sort((a, b) => b.s.CompareTo(a.s));
                var sb = new System.Text.StringBuilder();
                for (int k = 0; k < math.min(6, l.Count); k++)
                    sb.Append(k > 0 ? ", " : "").Append($"{l[k].n} {l[k].s * 1000:F0} mm / {l[k].i * 100:F1} %");
                return sb.ToString();
            }
            worstCabin = Top(cab);
            worstOther = Top(oth);
        }

        /// <summary>Per mesh: the largest distance of a vertex from where a rigid motion'''),
])

edit("Unity/HellcatSandbox/Assets/Game/Scenario/CarCrashScenario.cs", [
    ('''            sb.Append($"  \\"skin_max_inverted_share\\": {F(maxInverted, "F5")},\\n  \\"skin_stretch_m\\": {F(maxStretch, "F4")},\\n");''',
     '''            sb.Append($"  \\"skin_max_inverted_share\\": {F(maxInverted, "F5")},\\n  \\"skin_stretch_m\\": {F(maxStretch, "F4")},\\n");
            if (probe)
            {
                probe.RegionSummary(out float cs, out float ci, out float os, out float oi, out string wc, out string wo);
                sb.Append($"  \\"skin_cabin_spike_mm\\": {F(cs * 1000.0, "F2")},\\n  \\"skin_cabin_inverted_share\\": {F(ci, "F5")},\\n");
                sb.Append($"  \\"skin_other_spike_mm\\": {F(os * 1000.0, "F2")},\\n  \\"skin_other_inverted_share\\": {F(oi, "F5")},\\n");
                sb.Append($"  \\"skin_cabin_worst\\": \\"{wc}\\",\\n  \\"skin_other_worst\\": \\"{wo}\\",\\n");
            }'''),
])
print("patched")
