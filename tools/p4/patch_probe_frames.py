"""One-off (P4): SkinningProbe classifies spikes and inversions per vertex / triangle (cabin box at the first measurement,
running gear excluded) instead of per mesh, and records the largest rotation of a node frame between two measurements
(a frame whose two axis neighbours fell in line spins: the vertices on it swing)."""
from pathlib import Path


def edit(path, pairs):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    for o, n in pairs:
        assert s.count(o) == 1, (path, o[:80])
        s = s.replace(o, n)
    p.write_text(s, encoding="utf-8")


edit("Unity/HellcatSandbox/Assets/Game/Views/SkinningProbe.cs", [
    ('''        // per mesh over the whole run: largest spike, largest inverted share; cabin flag from the first measurement
        float[] runSpike, runInv;
        bool[] cabin;''',
     '''        // per mesh over the whole run, split into the cabin box (first measurement) and the rest: largest spike, largest
        // inverted share; per vertex / sampled triangle the cabin flag
        float[] runSpike, runInv, runSpikeOut, runInvOut;
        bool[] running;
        NativeArray<byte> vCabin, tCabin;
        float4x4[] prevBone;
        public float MaxFrameRotationDeg { get; private set; }
        public string MaxFrameRotationNode { get; private set; } = "";'''),
    ('''                // the cabin: meshes centred between the C-pillar and the A-pillar base (car at its spawn, +z forward)
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
                }''',
     '''                // the cabin box: between the C-pillar and the A-pillar base, inside the sills (car at its spawn, +z forward)
                runSpike = new float[meshes.Count];
                runInv = new float[meshes.Count];
                runSpikeOut = new float[meshes.Count];
                runInvOut = new float[meshes.Count];
                running = new bool[meshes.Count];
                vCabin = new NativeArray<byte>(restLocal.Length, Allocator.Persistent);
                tCabin = new NativeArray<byte>(tris.Length, Allocator.Persistent);
                for (int k = 0; k < meshes.Count; k++)
                {
                    var md = meshes[k];
                    running[k] = md.name.Contains("Wheel_") || md.name.Contains("Susp_") || md.name.Contains("Shaft") ||
                                 md.name.Contains("Knuckles") || md.name.Contains("Exhaust");
                    for (int v = md.vStart; v < md.vStart + md.vCount; v++)
                    {
                        float3 r = refPos[v];
                        vCabin[v] = (byte)(!running[k] && r.z > -1.1f && r.z < 0.9f && math.abs(r.x) < 0.95f ? 1 : 0);
                    }
                    for (int t = md.tStart; t < md.tStart + md.tCount; t++)
                        tCabin[t] = vCabin[tris[t].x];
                }'''),
    ('''                for (int k = 0; k < meshes.Count; k++)
                {
                    var md = meshes[k];
                    float sp = 0f;
                    for (int v = md.vStart; v < md.vStart + md.vCount; v++) sp = math.max(sp, vSpike[v]);
                    int fl = 0;
                    for (int t = md.tStart; t < md.tStart + md.tCount; t++) fl += triFlip[t];
                    runSpike[k] = math.max(runSpike[k], sp);
                    runInv[k] = math.max(runInv[k], md.tCount > 0 ? fl / (float)md.tCount : 0f);
                }''',
     '''                for (int k = 0; k < meshes.Count; k++)
                {
                    var md = meshes[k];
                    float sp = 0f, spo = 0f;
                    for (int v = md.vStart; v < md.vStart + md.vCount; v++)
                    {
                        if (vCabin[v] != 0) sp = math.max(sp, vSpike[v]);
                        else spo = math.max(spo, vSpike[v]);
                    }
                    int fl = 0, nt = 0, flo = 0, nto = 0;
                    for (int t = md.tStart; t < md.tStart + md.tCount; t++)
                    {
                        if (tCabin[t] != 0) { fl += triFlip[t]; nt++; }
                        else { flo += triFlip[t]; nto++; }
                    }
                    runSpike[k] = math.max(runSpike[k], sp);
                    runInv[k] = math.max(runInv[k], nt > 0 ? fl / (float)nt : 0f);
                    runSpikeOut[k] = math.max(runSpikeOut[k], spo);
                    runInvOut[k] = math.max(runInvOut[k], nto > 0 ? flo / (float)nto : 0f);
                }
                // node frames: largest rotation since the last measurement
                for (int i = 0; i < boneMatrix.Length; i++)
                {
                    float3x3 a = new float3x3(prevBone[i]), b = new float3x3(boneMatrix[i]);
                    float3x3 rel = math.mul(b, math.transpose(a));
                    float tr = rel.c0.x + rel.c1.y + rel.c2.z;
                    float ang = math.degrees(math.acos(math.clamp(0.5f * (tr - 1f), -1f, 1f)));
                    if (ang > MaxFrameRotationDeg)
                    {
                        MaxFrameRotationDeg = ang;
                        MaxFrameRotationNode = view.nodeBones[i].name;
                    }
                }'''),
    ('''            NativeArray<float3>.Copy(skinned, previous);
            if (!haveRef)''',
     '''            NativeArray<float3>.Copy(skinned, previous);
            if (prevBone == null) prevBone = new float4x4[boneMatrix.Length];
            if (!haveRef)'''),
    ('''            MaxSpike = havePrev ? maxS : 0f;
            MaxSpikeMesh = maxSv >= 0 ? MeshOf(maxSv) : "";''',
     '''            MaxSpike = havePrev ? maxS : 0f;
            MaxSpikeMesh = maxSv >= 0 ? MeshOf(maxSv) : "";'''),
    ('''            if (dispVec.IsCreated) dispVec.Dispose();''',
     '''            if (dispVec.IsCreated) dispVec.Dispose();
            if (vCabin.IsCreated) vCabin.Dispose();
            if (tCabin.IsCreated) tCabin.Dispose();'''),
    ('''            for (int k = 0; k < meshes.Count; k++)
            {
                (cabin[k] ? cab : oth).Add((meshes[k].name, runSpike[k], runInv[k]));
                if (cabin[k]) { cabinSpike = math.max(cabinSpike, runSpike[k]); cabinInv = math.max(cabinInv, runInv[k]); }
                else { otherSpike = math.max(otherSpike, runSpike[k]); otherInv = math.max(otherInv, runInv[k]); }
            }''',
     '''            for (int k = 0; k < meshes.Count; k++)
            {
                cab.Add((meshes[k].name, runSpike[k], runInv[k]));
                oth.Add((meshes[k].name, runSpikeOut[k], runInvOut[k]));
                cabinSpike = math.max(cabinSpike, runSpike[k]);
                cabinInv = math.max(cabinInv, runInv[k]);
                otherSpike = math.max(otherSpike, runSpikeOut[k]);
                otherInv = math.max(otherInv, runInvOut[k]);
            }'''),
])
print("patched")
