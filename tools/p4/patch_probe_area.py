"""One-off (P4): the inverted shares of the skinning probe weighted by the triangles' rest area instead of their count
(a small mesh such as the shifter has ~70 sampled triangles, so one millimetre sliver turning over read as 1.4 %), and the
time of the largest node-frame rotation in the crash result."""
from pathlib import Path

p = Path("Unity/HellcatSandbox/Assets/Game/Views/SkinningProbe.cs")
s = p.read_text(encoding="utf-8")
pairs = [
    ('''        NativeArray<byte> triFlip;''',
     '''        NativeArray<byte> triFlip;
        NativeArray<float> triArea;              // per sampled triangle: rest area (mesh space), the weight of the inverted shares'''),
    ('''            triFlip = new NativeArray<byte>(tr.Count, Allocator.Persistent);''',
     '''            triFlip = new NativeArray<byte>(tr.Count, Allocator.Persistent);
            triArea = new NativeArray<float>(tr.Count, Allocator.Persistent);
            for (int k = 0; k < tr.Count; k++)
            {
                int3 q = tr[k];
                triArea[k] = 0.5f * math.length(math.cross(rl[q.y] - rl[q.x], rl[q.z] - rl[q.x]));
            }'''),
    ('''            int flips = 0;
            for (int t = 0; t < triFlip.Length; t++) flips += triFlip[t];
            InvertedShare = tris.Length > 0 ? flips / (float)tris.Length : 0f;''',
     '''            float flipA = 0f, allA = 0f;
            for (int t = 0; t < triFlip.Length; t++)
            {
                flipA += triFlip[t] * triArea[t];
                allA += triArea[t];
            }
            InvertedShare = allA > 0f ? flipA / allA : 0f;'''),
    ('''                    int fl = 0, nt = 0, flo = 0, nto = 0;
                    for (int t = md.tStart; t < md.tStart + md.tCount; t++)
                    {
                        if (tCabin[t] != 0) { fl += triFlip[t]; nt++; }
                        else { flo += triFlip[t]; nto++; }
                    }
                    runSpike[k] = math.max(runSpike[k], sp);
                    runInv[k] = math.max(runInv[k], nt > 0 ? fl / (float)nt : 0f);
                    runSpikeOut[k] = math.max(runSpikeOut[k], spo);
                    runInvOut[k] = math.max(runInvOut[k], nto > 0 ? flo / (float)nto : 0f);''',
     '''                    float fl = 0f, nt = 0f, flo = 0f, nto = 0f;      // turned-over area / sampled area
                    for (int t = md.tStart; t < md.tStart + md.tCount; t++)
                    {
                        if (tCabin[t] != 0) { fl += triFlip[t] * triArea[t]; nt += triArea[t]; }
                        else { flo += triFlip[t] * triArea[t]; nto += triArea[t]; }
                    }
                    runSpike[k] = math.max(runSpike[k], sp);
                    runInv[k] = math.max(runInv[k], nt > 0f ? fl / nt : 0f);
                    runSpikeOut[k] = math.max(runSpikeOut[k], spo);
                    runInvOut[k] = math.max(runInvOut[k], nto > 0f ? flo / nto : 0f);'''),
    ('''                int fl = 0;
                for (int t = md.tStart; t < md.tStart + md.tCount; t++) fl += triFlip[t];
                rows.Add((md.name, st, jp, md.tCount > 0 ? fl / (float)md.tCount : 0f));''',
     '''                float fl = 0f, at = 0f;
                for (int t = md.tStart; t < md.tStart + md.tCount; t++)
                {
                    fl += triFlip[t] * triArea[t];
                    at += triArea[t];
                }
                rows.Add((md.name, st, jp, at > 0f ? fl / at : 0f));'''),
    ('''            if (triFlip.IsCreated) triFlip.Dispose();''',
     '''            if (triFlip.IsCreated) triFlip.Dispose();
            if (triArea.IsCreated) triArea.Dispose();'''),
]
for o, n in pairs:
    assert s.count(o) == 1, o[:90]
    s = s.replace(o, n)
s = s.replace("the share of sampled triangles turned over", "the share of the sampled triangles' area turned over")
p.write_text(s, encoding="utf-8")

p = Path("Unity/HellcatSandbox/Assets/Game/Scenario/CarCrashScenario.cs")
s = p.read_text(encoding="utf-8")
pairs = [
    ('''        float maxVertexJump, maxVertexJumpT, maxInverted, maxStretch, maxSpike, maxSpikeT, maxExcess, maxExcessT;''',
     '''        float maxVertexJump, maxVertexJumpT, maxInverted, maxStretch, maxSpike, maxSpikeT, maxExcess, maxExcessT, maxRot, maxRotT;'''),
    ('''                    maxSpike = probe.MaxSpike; maxSpikeT = time; maxSpikeMesh = probe.MaxSpikeMesh;
                }''',
     '''                    maxSpike = probe.MaxSpike; maxSpikeT = time; maxSpikeMesh = probe.MaxSpikeMesh;
                }
                if (probe.MaxFrameRotationDeg > maxRot)
                {
                    maxRot = probe.MaxFrameRotationDeg; maxRotT = time;
                }'''),
    ('''                sb.Append($"  \\"skin_max_frame_rotation_node\\": \\"{probe.MaxFrameRotationNode}\\",\\n");''',
     '''                sb.Append($"  \\"skin_max_frame_rotation_node\\": \\"{probe.MaxFrameRotationNode}\\",\\n");
                sb.Append($"  \\"skin_max_frame_rotation_time_s\\": {F(maxRotT, "F3")},\\n");'''),
]
for o, n in pairs:
    assert s.count(o) == 1, o[:90]
    s = s.replace(o, n)
p.write_text(s, encoding="utf-8")
print("patched")
