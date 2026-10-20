"""One-off (P4): back to the plain displacement Laplacian (the main-bone rotation correction of patch_probe_rigidlap.py
blew up where a vertex blends four bones), and the gate's spike measure: how far the fastest vertex outran the fastest
node of the car in the same frame (brief 7: "report max vertex displacement per frame to catch spikes"; a correctly
skinned vertex never moves much faster than every node)."""
from pathlib import Path

p = Path("Unity/HellcatSandbox/Assets/Game/Views/SkinningProbe.cs")
s = p.read_text(encoding="utf-8")
pairs = [
    ('''                // the rotation increment of the main bone applied to the rest Laplacian: what a rigid turn alone gives
                float3x3 now = new float3x3(math.mul(boneMatrix[slotNode[sl]], slotBind[sl]));
                float3x3 before = new float3x3(math.mul(prevBone[slotNode[sl]], slotBind[sl]));
                float3 rigid = math.mul(now - before, lapRest[v]);
                spike[v] = math.length(dispVec[v] - m / (e - a) - rigid);''',
     '''                spike[v] = math.length(dispVec[v] - m / (e - a));'''),
    ('''        public float MaxSpike { get; private set; }''',
     '''        public float MaxSpike { get; private set; }
        /// <summary>Last measurement: the largest vertex displacement minus the largest node displacement (m).</summary>
        public float SpikeExcess { get; private set; }
        public string SpikeExcessMesh { get; private set; } = "";'''),
    ('''            MaxSpike = havePrev ? maxS : 0f;
            MaxSpikeMesh = maxSv >= 0 ? MeshOf(maxSv) : "";''',
     '''            MaxSpike = havePrev ? maxS : 0f;
            MaxSpikeMesh = maxSv >= 0 ? MeshOf(maxSv) : "";
            float maxNode = 0f;
            if (havePrev)
                for (int i = 0; i < boneMatrix.Length; i++)
                    maxNode = math.max(maxNode, math.distance(boneMatrix[i].c3.xyz, prevBoneN[i].c3.xyz));
            SpikeExcess = havePrev ? math.max(0f, MaxFrameDisplacement - maxNode) : 0f;
            SpikeExcessMesh = MaxFrameDisplacementMesh;'''),
]
for o, n in pairs:
    assert s.count(o) == 1, o[:80]
    s = s.replace(o, n)
# prevBoneN must still hold the previous frame when the excess is computed: copy after it
o = '''            }.Schedule(restLocal.Length, 1024).Complete();
            NativeArray<float4x4>.Copy(boneMatrix, prevBoneN);'''
n = '''            }.Schedule(restLocal.Length, 1024).Complete();'''
assert s.count(o) == 1
s = s.replace(o, n)
o = '''            for (int i = 0; i < boneMatrix.Length; i++) prevBone[i] = boneMatrix[i];
            havePrev = true;'''
n = '''            for (int i = 0; i < boneMatrix.Length; i++) prevBone[i] = boneMatrix[i];
            NativeArray<float4x4>.Copy(boneMatrix, prevBoneN);
            havePrev = true;'''
assert s.count(o) == 1
s = s.replace(o, n)
p.write_text(s, encoding="utf-8")

p = Path("Unity/HellcatSandbox/Assets/Game/Scenario/CarCrashScenario.cs")
s = p.read_text(encoding="utf-8")
o = '''                if (probe.MaxSpike > maxSpike)
                {
                    maxSpike = probe.MaxSpike; maxSpikeT = time; maxSpikeMesh = probe.MaxSpikeMesh;
                }'''
n = '''                if (probe.MaxSpike > maxSpike)
                {
                    maxSpike = probe.MaxSpike; maxSpikeT = time; maxSpikeMesh = probe.MaxSpikeMesh;
                }
                if (probe.SpikeExcess > maxExcess)
                {
                    maxExcess = probe.SpikeExcess; maxExcessT = time; maxExcessMesh = probe.SpikeExcessMesh;
                }'''
assert s.count(o) == 1
s = s.replace(o, n)
o = '''        float maxVertexJump, maxVertexJumpT, maxInverted, maxStretch, maxSpike, maxSpikeT;'''
n = '''        float maxVertexJump, maxVertexJumpT, maxInverted, maxStretch, maxSpike, maxSpikeT, maxExcess, maxExcessT;
        string maxExcessMesh = "";'''
assert s.count(o) == 1
s = s.replace(o, n)
p.write_text(s, encoding="utf-8")
print("patched")
