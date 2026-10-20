"""One-off (P4): the spike is the Laplacian of the frame displacement minus what the rotation increment of the vertex's
main bone does to the rest-pose Laplacian (rest_v - mean(rest_u)): a rigidly turning part (a fuel tank, a gearbox) gave
up to 5 cm at the mesh boundary, where a vertex is not the mean of its neighbours."""
from pathlib import Path

p = Path("Unity/HellcatSandbox/Assets/Game/Views/SkinningProbe.cs")
s = p.read_text(encoding="utf-8")
pairs = [
    ('''        NativeArray<int> adjStart, adjIndex;     // mesh neighbours of every vertex (CSR over all triangles)''',
     '''        NativeArray<int> adjStart, adjIndex;     // mesh neighbours of every vertex (CSR over all triangles)
        NativeArray<float3> lapRest;             // per vertex: rest_v - mean of its neighbours' rest positions (mesh space)
        NativeArray<float4x4> prevBoneN;         // per node bone: local-to-world at the last measurement'''),
    ('''            adjStart = new NativeArray<int>(starts, Allocator.Persistent);
            adjIndex = new NativeArray<int>(idx.ToArray(), Allocator.Persistent);''',
     '''            adjStart = new NativeArray<int>(starts, Allocator.Persistent);
            adjIndex = new NativeArray<int>(idx.ToArray(), Allocator.Persistent);
            lapRest = new NativeArray<float3>(rl.Count, Allocator.Persistent);
            for (int v = 0; v < rl.Count; v++)
            {
                int a = starts[v], e = starts[v + 1];
                if (e == a) continue;
                float3 m = float3.zero;
                for (int k = a; k < e; k++) m += rl[idx[k]];
                lapRest[v] = rl[v] - m / (e - a);
            }
            prevBoneN = new NativeArray<float4x4>(view.nodeBones.Length, Allocator.Persistent);'''),
    ('''            new LaplaceJob { dispVec = dispVec, adjStart = adjStart, adjIndex = adjIndex, havePrev = havePrev, spike = vSpike }
                .Schedule(restLocal.Length, 1024).Complete();''',
     '''            new LaplaceJob
            {
                dispVec = dispVec, adjStart = adjStart, adjIndex = adjIndex, havePrev = havePrev, spike = vSpike, lapRest = lapRest,
                bones = vBones, slotNode = slotNode, slotBind = slotBind, boneMatrix = boneMatrix, prevBone = prevBoneN,
            }.Schedule(restLocal.Length, 1024).Complete();
            NativeArray<float4x4>.Copy(boneMatrix, prevBoneN);'''),
    ('''            if (adjIndex.IsCreated) adjIndex.Dispose();''',
     '''            if (adjIndex.IsCreated) adjIndex.Dispose();
            if (lapRest.IsCreated) lapRest.Dispose();
            if (prevBoneN.IsCreated) prevBoneN.Dispose();'''),
    ('''            [ReadOnly] public NativeArray<float3> dispVec;
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
            }''',
     '''            [ReadOnly] public NativeArray<float3> dispVec, lapRest;
            [ReadOnly] public NativeArray<int> adjStart, adjIndex;
            [ReadOnly] public NativeArray<int4> bones;
            [ReadOnly] public NativeArray<int> slotNode;
            [ReadOnly] public NativeArray<float4x4> slotBind, boneMatrix, prevBone;
            public bool havePrev;
            [WriteOnly] public NativeArray<float> spike;

            public void Execute(int v)
            {
                int a = adjStart[v], e = adjStart[v + 1];
                int sl = bones[v].x;
                if (!havePrev || e == a || sl < 0)
                {
                    spike[v] = 0f;
                    return;
                }
                float3 m = float3.zero;
                for (int k = a; k < e; k++) m += dispVec[adjIndex[k]];
                // the rotation increment of the main bone applied to the rest Laplacian: what a rigid turn alone gives
                float3x3 now = new float3x3(math.mul(boneMatrix[slotNode[sl]], slotBind[sl]));
                float3x3 before = new float3x3(math.mul(prevBone[slotNode[sl]], slotBind[sl]));
                float3 rigid = math.mul(now - before, lapRest[v]);
                spike[v] = math.length(dispVec[v] - m / (e - a) - rigid);
            }'''),
]
for o, n in pairs:
    assert s.count(o) == 1, o[:80]
    s = s.replace(o, n)
p.write_text(s, encoding="utf-8")
print("patched")
