"""One-off (P4): SkinningProbe spikes from the mesh Laplacian of the per-frame vertex displacement (a vertex that moves
unlike its mesh neighbours), instead of the change of its offset from the main node frame (that flagged every crushed
wheel well)."""
from pathlib import Path

p = Path("Unity/HellcatSandbox/Assets/Game/Views/SkinningProbe.cs")
s = p.read_text(encoding="utf-8")
pairs = [
    ('''    /// is reproduced on the CPU (Burst) from the same bones, weights and bind poses the GPU uses. Reports the largest vertex
    /// displacement in one frame and the spike: how much a vertex's offset from the rigid motion of its main node changed
    /// in one frame (a skinning artefact; the car's motion, 23 cm per frame at 50 km/h, and the wheels' spin are rigid
    /// motions of the nodes' frames and give none), the largest distance of a skinned vertex from the rigid motion of its
    /// main node (stretch), and the share of triangles whose normal turned over against the rigid motion of their main node
    /// (mesh inversion).''',
     '''    /// is reproduced on the CPU (Burst) from the same bones, weights and bind poses the GPU uses. Reports the largest vertex
    /// displacement in one frame and the spike: how far a vertex's displacement in one frame differs from the mean of its
    /// mesh neighbours' (the Laplacian of the displacement field: a vertex leaving its surface; the car's motion, the
    /// wheels' spin and a smoothly crumpling panel give none), the largest distance of a skinned vertex from the rigid
    /// motion of its main node (stretch), and the share of triangles whose normal turned over against the rigid motion of
    /// their main node (mesh inversion).'''),
    ('''        NativeArray<float> vDisp, vSpike;
        NativeArray<float3> devPrev;             // per vertex: offset from its main node's rigid motion, last measurement''',
     '''        NativeArray<float> vDisp, vSpike;
        NativeArray<float3> dispVec;             // per vertex: displacement since the last measurement
        NativeArray<int> adjStart, adjIndex;     // mesh neighbours of every vertex (CSR over all triangles)'''),
    ('''            var tr = new List<int3>();''',
     '''            var tr = new List<int3>();
            var edges = new List<long>();'''),
    ('''                var t = mesh.triangles;
                int nt = t.Length / 3;''',
     '''                var t = mesh.triangles;
                int nt = t.Length / 3;
                for (int k = 0; k < t.Length; k += 3)
                    for (int e = 0; e < 3; e++)
                    {
                        long x = md.vStart + t[k + e], y = md.vStart + t[k + (e + 1) % 3];
                        edges.Add(x << 32 | y);
                        edges.Add(y << 32 | x);
                    }'''),
    ('''            devPrev = new NativeArray<float3>(rl.Count, Allocator.Persistent);''',
     '''            dispVec = new NativeArray<float3>(rl.Count, Allocator.Persistent);
            edges.Sort();
            var starts = new int[rl.Count + 1];
            var idx = new List<int>(edges.Count);
            long last = -1;
            foreach (long e in edges)
            {
                if (e == last) continue;
                last = e;
                starts[(int)(e >> 32) + 1]++;
                idx.Add((int)(e & 0xffffffffL));
            }
            for (int v = 0; v < rl.Count; v++) starts[v + 1] += starts[v];
            adjStart = new NativeArray<int>(starts, Allocator.Persistent);
            adjIndex = new NativeArray<int>(idx.ToArray(), Allocator.Persistent);'''),
    ('''                skinned = skinned, previous = previous, havePrev = havePrev, disp = vDisp, devPrev = devPrev, spike = vSpike,
            }.Schedule(restLocal.Length, 1024).Complete();''',
     '''                skinned = skinned, previous = previous, havePrev = havePrev, disp = vDisp, dispVec = dispVec,
            }.Schedule(restLocal.Length, 1024).Complete();
            new LaplaceJob { dispVec = dispVec, adjStart = adjStart, adjIndex = adjIndex, havePrev = havePrev, spike = vSpike }
                .Schedule(restLocal.Length, 1024).Complete();'''),
    ('''            if (devPrev.IsCreated) devPrev.Dispose();''',
     '''            if (dispVec.IsCreated) dispVec.Dispose();
            if (adjStart.IsCreated) adjStart.Dispose();
            if (adjIndex.IsCreated) adjIndex.Dispose();'''),
    ('''            [ReadOnly] public NativeArray<float3> previous;
            public NativeArray<float3> devPrev;
            public bool havePrev;
            [WriteOnly] public NativeArray<float3> skinned;
            [WriteOnly] public NativeArray<float> disp, spike;

            public void Execute(int v)
            {
                float3 x = rest[v], s = float3.zero, rigid = float3.zero;
                int4 b = bones[v];
                float4 w = weights[v];
                for (int q = 0; q < 4; q++)
                {
                    if (b[q] < 0) continue;
                    float3 t = math.transform(math.mul(boneMatrix[slotNode[b[q]]], slotBind[b[q]]), x);
                    s += w[q] * t;
                    if (q == 0) rigid = t;
                }
                skinned[v] = s;
                float3 dev = s - rigid;
                disp[v] = havePrev ? math.distance(s, previous[v]) : 0f;
                spike[v] = havePrev ? math.distance(dev, devPrev[v]) : 0f;
                devPrev[v] = dev;
            }''',
     '''            [ReadOnly] public NativeArray<float3> previous;
            public bool havePrev;
            [WriteOnly] public NativeArray<float3> skinned, dispVec;
            [WriteOnly] public NativeArray<float> disp;

            public void Execute(int v)
            {
                float3 x = rest[v], s = float3.zero;
                int4 b = bones[v];
                float4 w = weights[v];
                for (int q = 0; q < 4; q++)
                {
                    if (b[q] < 0) continue;
                    s += w[q] * math.transform(math.mul(boneMatrix[slotNode[b[q]]], slotBind[b[q]]), x);
                }
                skinned[v] = s;
                float3 d = havePrev ? s - previous[v] : float3.zero;
                dispVec[v] = d;
                disp[v] = math.length(d);
            }
        }

        [BurstCompile]
        struct LaplaceJob : IJobParallelFor
        {
            [ReadOnly] public NativeArray<float3> dispVec;
            [ReadOnly] public NativeArray<int> adjStart, adjIndex;
            public bool havePrev;
            [WriteOnly] public NativeArray<float> spike;

            public void Execute(int v)
            {
                int a = adjStart[v], e = adjStart[v + 1];
                if (!havePrev || e == a)
                {
                    spike[v] = 0f;
                    return;
                }
                float3 m = float3.zero;
                for (int k = a; k < e; k++) m += dispVec[adjIndex[k]];
                spike[v] = math.distance(dispVec[v], m / (e - a));
            }'''),
]
for o, n in pairs:
    assert s.count(o) == 1, o[:80]
    s = s.replace(o, n)
p.write_text(s, encoding="utf-8")
print("patched")
