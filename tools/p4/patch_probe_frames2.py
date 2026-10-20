"""One-off (P4): finishes patch_probe_frames.py (wheel and suspension nodes excluded from the frame-rotation record, the
previous bone matrices kept)."""
from pathlib import Path

p = Path("Unity/HellcatSandbox/Assets/Game/Views/SkinningProbe.cs")
s = p.read_text(encoding="utf-8")
pairs = [
    ('''                // node frames: largest rotation since the last measurement
                for (int i = 0; i < boneMatrix.Length; i++)
                {
                    float3x3 a''',
     '''                // node frames: largest rotation since the last measurement (the wheels' and suspension nodes turn by design)
                for (int i = 0; i < boneMatrix.Length; i++)
                {
                    string bn = view.nodeBones[i].name;
                    if (bn.StartsWith("FR_") || bn.StartsWith("FL_") || bn.StartsWith("RR_") || bn.StartsWith("RL_")) continue;
                    float3x3 a'''),
    ('''            if (prevBone == null) prevBone = new float4x4[boneMatrix.Length];
            if (!haveRef)''',
     '''            if (prevBone == null)
            {
                prevBone = new float4x4[boneMatrix.Length];
                for (int i = 0; i < boneMatrix.Length; i++) prevBone[i] = boneMatrix[i];
            }
            if (!haveRef)'''),
    ('''            havePrev = true;
        }

        /// <summary>Largest distance of a skinned vertex from the rigid motion of its main node (from the bind pose).</summary>''',
     '''            for (int i = 0; i < boneMatrix.Length; i++) prevBone[i] = boneMatrix[i];
            havePrev = true;
        }

        /// <summary>Largest distance of a skinned vertex from the rigid motion of its main node (from the bind pose).</summary>'''),
]
for o, n in pairs:
    assert s.count(o) == 1, o[:80]
    s = s.replace(o, n)
p.write_text(s, encoding="utf-8")
print("patched")
