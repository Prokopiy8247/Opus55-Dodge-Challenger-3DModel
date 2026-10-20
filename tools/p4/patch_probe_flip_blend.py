"""One-off (P4): mesh inversion measured against the vertex's own blended skinning transform (sum of w_k * bone_k), not
its main bone's rigid motion, and as an absolute area as well as a share. Against the main bone, a triangle that simply
follows a blend of differently turned bones read as turned over; as a share, one sliver of the ~10-triangle tachometer
needle read as 10 % of the mesh. A triangle is turned over when its normal opposes that of its rest shape carried by
the linear part of the blended transform at its first vertex (what an undistorted triangle there would show)."""
from pathlib import Path

p = Path("Unity/HellcatSandbox/Assets/Game/Views/SkinningProbe.cs")
s = p.read_text(encoding="utf-8")
pairs = [
    # per-triangle weight: rest area times the sampling step (the mesh area the sample stands for)
    ('''        NativeArray<float> triArea;              // per sampled triangle: rest area (mesh space), the weight of the inverted shares''',
     '''        NativeArray<float> triArea;              // per sampled triangle: rest area (m^2) times the sampling step of its mesh'''),
    ('''                int step = triangleSample > 0 ? math.max(1, nt / triangleSample) : 1;
                for (int k = 0; k < nt; k += step)
                    tr.Add(new int3(md.vStart + t[3 * k], md.vStart + t[3 * k + 1], md.vStart + t[3 * k + 2]));''',
     '''                int step = triangleSample > 0 ? math.max(1, nt / triangleSample) : 1;
                for (int k = 0; k < nt; k += step)
                {
                    tr.Add(new int3(md.vStart + t[3 * k], md.vStart + t[3 * k + 1], md.vStart + t[3 * k + 2]));
                    trStep.Add(step);
                }'''),
    ('''            var tr = new List<int3>();''',
     '''            var tr = new List<int3>();
            var trStep = new List<int>();'''),
    ('''                triArea[k] = 0.5f * math.length(math.cross(rl[q.y] - rl[q.x], rl[q.z] - rl[q.x]));''',
     '''                triArea[k] = 0.5f * math.length(math.cross(rl[q.y] - rl[q.x], rl[q.z] - rl[q.x])) * trStep[k];'''),
    # flip test against the blended transform
    ('''            new FlipJob { tris = tris, skinned = skinned, rest = restLocal, bones = vBones, slotNode = slotNode, slotBind = slotBind, boneMatrix = boneMatrix, flip = triFlip }''',
     '''            new FlipJob { tris = tris, skinned = skinned, rest = restLocal, bones = vBones, weights = vWeights, slotNode = slotNode, slotBind = slotBind, boneMatrix = boneMatrix, flip = triFlip }'''),
    ('''            [ReadOnly] public NativeArray<int4> bones;
            [ReadOnly] public NativeArray<int> slotNode;
            [ReadOnly] public NativeArray<float4x4> slotBind, boneMatrix;
            [WriteOnly] public NativeArray<byte> flip;

            public void Execute(int t)
            {
                int3 i = tris[t];
                float3 n = math.cross(skinned[i.y] - skinned[i.x], skinned[i.z] - skinned[i.x]);
                // the original normal carried by the rigid motion of the first vertex's main node
                int s = bones[i.x].x;
                if (s < 0) { flip[t] = 0; return; }
                float4x4 m = math.mul(boneMatrix[slotNode[s]], slotBind[s]);''',
     '''            [ReadOnly] public NativeArray<int4> bones;
            [ReadOnly] public NativeArray<float4> weights;
            [ReadOnly] public NativeArray<int> slotNode;
            [ReadOnly] public NativeArray<float4x4> slotBind, boneMatrix;
            [WriteOnly] public NativeArray<byte> flip;

            public void Execute(int t)
            {
                int3 i = tris[t];
                float3 n = math.cross(skinned[i.y] - skinned[i.x], skinned[i.z] - skinned[i.x]);
                // the rest triangle carried by the blended skinning transform of its first vertex
                int4 bi = bones[i.x];
                float4 wi = weights[i.x];
                if (bi.x < 0) { flip[t] = 0; return; }
                float4x4 m = float4x4.zero;
                for (int k = 0; k < 4; k++)
                    if (bi[k] >= 0 && wi[k] > 0f)
                        m += wi[k] * math.mul(boneMatrix[slotNode[bi[k]]], slotBind[bi[k]]);'''),
    # per-mesh absolute flipped area over the run
    ('''        float[] runSpike, runInv, runSpikeOut, runInvOut;''',
     '''        float[] runSpike, runInv, runSpikeOut, runInvOut, runInvA, runInvAOut;'''),
    ('''                runInvOut = new float[meshes.Count];''',
     '''                runInvOut = new float[meshes.Count];
                runInvA = new float[meshes.Count];
                runInvAOut = new float[meshes.Count];'''),
    ('''                    runInvOut[k] = math.max(runInvOut[k], nto > 0f ? flo / nto : 0f);''',
     '''                    runInvOut[k] = math.max(runInvOut[k], nto > 0f ? flo / nto : 0f);
                    runInvA[k] = math.max(runInvA[k], fl);
                    runInvAOut[k] = math.max(runInvAOut[k], flo);'''),
    ('''        /// <summary>Per mesh: the largest distance of a vertex from where a rigid motion x = c + R (x_ref - c0) (the cabin's)''',
     '''        /// <summary>Largest turned-over area (m^2) of any one mesh over the run, in the cabin and elsewhere, with the mesh.</summary>
        public void InvertedAreaSummary(out float cabinArea, out string cabinMesh, out float otherArea, out string otherMesh)
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
        }

        /// <summary>Per mesh: the largest distance of a vertex from where a rigid motion x = c + R (x_ref - c0) (the cabin's)'''),
]
for o, n in pairs:
    assert s.count(o) == 1, o[:100]
    s = s.replace(o, n)
p.write_text(s, encoding="utf-8")

p = Path("Unity/HellcatSandbox/Assets/Game/Scenario/CarCrashScenario.cs")
s = p.read_text(encoding="utf-8")
o = '''                sb.Append($"  \\"skin_cabin_worst\\": \\"{wc}\\",\\n  \\"skin_other_worst\\": \\"{wo}\\",\\n");'''
n = '''                sb.Append($"  \\"skin_cabin_worst\\": \\"{wc}\\",\\n  \\"skin_other_worst\\": \\"{wo}\\",\\n");
                probe.InvertedAreaSummary(out float cia, out string cim, out float oia, out string oim);
                sb.Append($"  \\"skin_cabin_inverted_cm2\\": {F(cia * 1e4, "F2")},\\n  \\"skin_cabin_inverted_cm2_mesh\\": \\"{cim}\\",\\n");
                sb.Append($"  \\"skin_other_inverted_cm2\\": {F(oia * 1e4, "F1")},\\n  \\"skin_other_inverted_cm2_mesh\\": \\"{oim}\\",\\n");'''
assert s.count(o) == 1
s = s.replace(o, n)
p.write_text(s, encoding="utf-8")
print("patched")
