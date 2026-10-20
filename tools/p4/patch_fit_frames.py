"""One-off (P4, D-062): node bone frames as the best-fit rotation of the node's neighbourhood (Horn's quaternion method,
power iteration warm-started from the last frame) instead of a Gram-Schmidt frame from two neighbours, which flipped by
up to 175 deg in one frame when the two neighbours fell in line during a crush."""
from pathlib import Path

ROOT = Path("Unity/HellcatSandbox/Assets")


def edit(name, pairs):
    p = ROOT / name
    s = p.read_text(encoding="utf-8")
    for o, n in pairs:
        assert s.count(o) == 1, (name, o[:90])
        s = s.replace(o, n)
    p.write_text(s, encoding="utf-8")


edit("Game/Views/SoftBodyCarView.cs", [
    ('''    /// <summary>
    /// Skinned visuals of a soft-body car (brief 7): every node of the skeleton is a bone whose frame is built from the
    /// node and two neighbours of its part (origin, Gram-Schmidt axes); each visual vertex is bound to up to 4 nodes of
    /// its part(s) with inverse-distance weights (Tools/Hellcat/Import Car, <c>*.skin.bytes</c> next to every FBX), so a
    /// vertex follows the weighted sum of its nodes' local-frame reconstructions - rotations included - and Unity skins
    /// it on the GPU. Detached parts carry their own nodes and fly free with them.
    /// </summary>''',
     '''    /// <summary>
    /// Skinned visuals of a soft-body car (brief 7): every node of the skeleton is a bone at the node whose rotation is the
    /// best-fit rotation of its neighbourhood (up to 8 neighbours of its part, Horn's quaternion method, D-062: identity
    /// at the model pose); each visual vertex is bound to up to 4 nodes of its part(s) with inverse-distance weights
    /// (Tools/Hellcat/Import Car, <c>*.skin.bytes</c> next to every FBX), so a vertex follows the weighted sum of its nodes'
    /// local-frame reconstructions - rotations included - and Unity skins it on the GPU. Detached parts carry their own
    /// nodes and fly free with them.
    /// </summary>'''),
    ('''        [Tooltip("Frame axis nodes per node (local indices): x = first axis node, y = second axis node")]
        public Vector2Int[] frameAxes;

        TransformAccessArray access;
        NativeArray<int3> frames;   // world node indices: origin, axis a, axis b
        bool ready;''',
     '''        [Tooltip("Frame neighbours per node (local indices, CSR): frameNbr[frameNbrStart[i] .. frameNbrStart[i + 1]]")]
        public int[] frameNbrStart, frameNbr;

        TransformAccessArray access;
        NativeArray<int> nbrStart, nbr;      // world node indices of the frame neighbours
        NativeArray<float3> restOff;         // neighbour offsets at the model pose
        NativeArray<quaternion> rot;         // last frame rotation per node (warm start)
        int nodeStart;
        bool ready;'''),
    ('''        public static quaternion Frame(float3 p, float3 pa, float3 pb)
        {
            float3 e1 = math.normalizesafe(pa - p, new float3(0f, 0f, 1f));
            float3 d = pb - p;
            float3 e2 = math.normalizesafe(d - math.dot(d, e1) * e1, new float3(0f, 1f, 0f));
            return quaternion.LookRotationSafe(e1, e2);
        }''',
     '''        /// <summary>Rotation R that best carries the rest offsets X onto the current offsets x (least squares, Horn 1987):
        /// s = sum X x^T; the quaternion is the dominant eigenvector of Horn's 4x4 matrix, found by power iteration from
        /// <paramref name="guess"/> (the last frame), so an undetermined rotation (neighbours in a line) stays put instead of
        /// spinning.</summary>
        public static quaternion BestRotation(float3x3 s, quaternion guess)
        {
            float sxx = s.c0.x, sxy = s.c1.x, sxz = s.c2.x, syx = s.c0.y, syy = s.c1.y, syz = s.c2.y;
            float szx = s.c0.z, szy = s.c1.z, szz = s.c2.z;
            float shift = math.sqrt(math.dot(s.c0, s.c0) + math.dot(s.c1, s.c1) + math.dot(s.c2, s.c2));
            if (!(shift > 1e-12f))
                return guess;
            var n = new float4x4(
                new float4(sxx + syy + szz, syz - szy, szx - sxz, sxy - syx),
                new float4(syz - szy, sxx - syy - szz, sxy + syx, szx + sxz),
                new float4(szx - sxz, sxy + syx, -sxx + syy - szz, syz + szy),
                new float4(sxy - syx, szx + sxz, syz + szy, -sxx - syy + szz));
            float4 v = new float4(guess.value.w, guess.value.x, guess.value.y, guess.value.z);
            for (int it = 0; it < 16; it++)
                v = math.normalizesafe(math.mul(n, v) + shift * v, v);
            return new quaternion(v.y, v.z, v.w, v.x);
        }

        /// <summary>Cross-covariance of a node's neighbourhood: sum over the neighbours of rest offset (x) current offset.</summary>
        public static float3x3 Covariance(float3 p, NativeArray<float3> pos, NativeArray<int> nbr, NativeArray<float3> restOff, int a, int e)
        {
            float3x3 s = float3x3.zero;
            for (int k = a; k < e; k++)
            {
                float3 x = pos[nbr[k]] - p, X = restOff[k];
                s += new float3x3(X * x.x, X * x.y, X * x.z);
            }
            return s;
        }'''),
    ('''            access = new TransformAccessArray(nodeBones);
            foreach (var smr in GetComponentsInChildren<SkinnedMeshRenderer>(true))
                smr.updateWhenOffscreen = true;   // skinned for every camera (see CarImporter)
            frames = new NativeArray<int3>(nodeBones.Length, Allocator.Persistent);
            for (int i = 0; i < nodeBones.Length; i++)
                frames[i] = new int3(start + i, start + frameAxes[i].x, start + frameAxes[i].y);
            SetupGlass();''',
     '''            if (frameNbrStart == null || frameNbrStart.Length != nodeBones.Length + 1)
            {
                Debug.LogError("[SoftBodyCarView] no frame neighbours: re-run Tools/Hellcat/Import Car");
                return;
            }
            access = new TransformAccessArray(nodeBones);
            foreach (var smr in GetComponentsInChildren<SkinnedMeshRenderer>(true))
                smr.updateWhenOffscreen = true;   // skinned for every camera (see CarImporter)
            nodeStart = start;
            var def = runner.World.bodies[runner.VehicleBody].def;
            nbrStart = new NativeArray<int>(frameNbrStart, Allocator.Persistent);
            nbr = new NativeArray<int>(frameNbr.Length, Allocator.Persistent);
            restOff = new NativeArray<float3>(frameNbr.Length, Allocator.Persistent);
            for (int i = 0; i < nodeBones.Length; i++)
                for (int k = frameNbrStart[i]; k < frameNbrStart[i + 1]; k++)
                {
                    int j = frameNbr[k];
                    nbr[k] = start + j;
                    restOff[k] = new float3(def.nodes[j].p[0] - def.nodes[i].p[0], def.nodes[j].p[1] - def.nodes[i].p[1], def.nodes[j].p[2] - def.nodes[i].p[2]);
                }
            // warm start: the spawn rotation of the car
            quaternion q0 = runner.spawnPoint ? (quaternion)runner.spawnPoint.rotation : quaternion.identity;
            rot = new NativeArray<quaternion>(nodeBones.Length, Allocator.Persistent);
            for (int i = 0; i < rot.Length; i++) rot[i] = q0;
            SetupGlass();'''),
    ('''            new BoneJob { pos = runner.World.pos, frames = frames }.Schedule(access).Complete();''',
     '''            new BoneJob { pos = runner.World.pos, nodeStart = nodeStart, nbrStart = nbrStart, nbr = nbr, restOff = restOff, rot = rot }
                .Schedule(access).Complete();'''),
    ('''            if (access.isCreated) access.Dispose();
            if (frames.IsCreated) frames.Dispose();''',
     '''            if (access.isCreated) access.Dispose();
            if (nbrStart.IsCreated) nbrStart.Dispose();
            if (nbr.IsCreated) nbr.Dispose();
            if (restOff.IsCreated) restOff.Dispose();
            if (rot.IsCreated) rot.Dispose();'''),
    ('''        struct BoneJob : IJobParallelForTransform
        {
            [ReadOnly] public NativeArray<float3> pos;
            [ReadOnly] public NativeArray<int3> frames;

            public void Execute(int i, TransformAccess t)
            {
                int3 f = frames[i];
                float3 p = pos[f.x];
                t.SetPositionAndRotation(p, Frame(p, pos[f.y], pos[f.z]));
            }
        }''',
     '''        struct BoneJob : IJobParallelForTransform
        {
            [ReadOnly] public NativeArray<float3> pos;
            public int nodeStart;
            [ReadOnly] public NativeArray<int> nbrStart, nbr;
            [ReadOnly] public NativeArray<float3> restOff;
            public NativeArray<quaternion> rot;

            public void Execute(int i, TransformAccess t)
            {
                float3 p = pos[nodeStart + i];
                quaternion q = BestRotation(Covariance(p, pos, nbr, restOff, nbrStart[i], nbrStart[i + 1]), rot[i]);
                rot[i] = q;
                t.SetPositionAndRotation(p, q);
            }
        }'''),
])

edit("Editor/Car/CarImporter.cs", [
    ('''            // node frames (two neighbours in the same part) and their bind transforms
            var axes = FrameAxes(def);
            var bind = new Matrix4x4[def.nodes.Length];
            for (int i = 0; i < def.nodes.Length; i++)
            {
                Vector3 p = P(def, i), pa = P(def, axes[i].x), pb = P(def, axes[i].y);
                var q = SoftBodyCarView.Frame(p, pa, pb);
                bind[i] = Matrix4x4.TRS(p, q, Vector3.one);
            }''',
     '''            // node frames: best-fit rotation of the node's neighbourhood (D-062), the identity at the model pose
            var nbrs = FrameNeighbors(def, out int[] nbrStart);
            var bind = new Matrix4x4[def.nodes.Length];
            for (int i = 0; i < def.nodes.Length; i++)
                bind[i] = Matrix4x4.Translate(P(def, i));'''),
    ('''        static void BuildPrefab(VehicleDef def, PartsFile parts, Vector2Int[] axes, Matrix4x4[] bind)''',
     '''        static void BuildPrefab(VehicleDef def, PartsFile parts, int[] nbrStart, int[] nbrs, Matrix4x4[] bind)'''),
    ('''            view.nodeBones = bones;
            view.frameAxes = axes;''',
     '''            view.nodeBones = bones;
            view.frameNbrStart = nbrStart;
            view.frameNbr = nbrs;'''),
])
print("patched")
