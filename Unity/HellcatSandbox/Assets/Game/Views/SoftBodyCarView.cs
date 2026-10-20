using System;
using System.Collections.Generic;
using System.IO;
using Hellcat.Game.Core;
using Hellcat.Sim;
using Unity.Burst;
using Unity.Collections;
using Unity.Jobs;
using Unity.Mathematics;
using UnityEngine;
using UnityEngine.Jobs;

namespace Hellcat.Game.Views
{
    /// <summary>
    /// Skinned visuals of a soft-body car (brief 7): every node of the skeleton is a bone at the node whose rotation is the
    /// best-fit rotation of its neighbourhood (up to 8 neighbours of its part, Horn's quaternion method, D-062: identity
    /// at the model pose); each visual vertex is bound to up to 4 nodes of its part(s) with inverse-distance weights
    /// (Tools/Hellcat/Import Car, <c>*.skin.bytes</c> next to every FBX), so a vertex follows the weighted sum of its nodes'
    /// local-frame reconstructions - rotations included - and Unity skins it on the GPU. Detached parts carry their own
    /// nodes and fly free with them.
    /// </summary>
    [DefaultExecutionOrder(100)]
    public class SoftBodyCarView : MonoBehaviour
    {
        public SimRunner runner;
        [Tooltip("Node bone transforms, index = node index of the vehicle definition")]
        public Transform[] nodeBones;
        [Tooltip("Frame neighbours per node (local indices, CSR): frameNbr[frameNbrStart[i] .. frameNbrStart[i + 1]]")]
        public int[] frameNbrStart, frameNbr;

        TransformAccessArray access;
        NativeArray<int> nbrStart, nbr;      // world node indices of the frame neighbours
        NativeArray<float3> restOff;         // neighbour offsets at the model pose
        NativeArray<quaternion> rot;         // last frame rotation per node (warm start)
        int nodeStart;
        bool ready;

        // pre-fractured glass (brief 7): per pane the intact renderer, its shards and the pane's own glass beams
        sealed class Pane
        {
            public string name;
            public Renderer intact, shards;
            public int[] beams;      // global beam indices of the pane's glass / glass_side beams
            public bool broken;
        }
        readonly List<Pane> panes = new List<Pane>();

        /// <summary>Panes shattered so far (shards shown).</summary>
        public int BrokenPanes { get; private set; }

        /// <summary>Rotation R that best carries the rest offsets X onto the current offsets x (least squares, Horn 1987):
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
        }

        void Start()
        {
            if (runner == null || runner.World == null || nodeBones == null || nodeBones.Length == 0)
                return;
            int start = runner.World.bodies[runner.VehicleBody].nodeStart;
            if (nodeBones.Length != runner.World.bodies[runner.VehicleBody].nodeCount)
            {
                Debug.LogError($"[SoftBodyCarView] {nodeBones.Length} bones for {runner.World.bodies[runner.VehicleBody].nodeCount} nodes: re-run Tools/Hellcat/Import Car");
                return;
            }
            if (frameNbrStart == null || frameNbrStart.Length != nodeBones.Length + 1)
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
            SetupGlass();
            ready = true;
            UpdateBones();
        }

        void LateUpdate()
        {
            if (ready)
                UpdateBones();
        }

        void OnEnable()
        {
            if (runner) runner.Respawned += ResetVisualState;
        }

        void OnDisable()
        {
            if (runner) runner.Respawned -= ResetVisualState;
        }

        /// <summary>After a respawn: the frames' warm start from the car's new heading (a teleport may turn it by any angle)
        /// and the glass back in one piece.</summary>
        public void ResetVisualState()
        {
            if (!ready)
                return;
            var st = runner.World.vehicleState[runner.VehicleIndex];
            float3 fwd = math.normalizesafe(new float3(st.forward.x, 0f, st.forward.z), new float3(0f, 0f, 1f));
            quaternion q0 = quaternion.LookRotationSafe(fwd, new float3(0f, 1f, 0f));
            for (int i = 0; i < rot.Length; i++) rot[i] = q0;
            foreach (var p in panes)
            {
                p.broken = false;
                p.intact.enabled = true;
                p.shards.enabled = false;
            }
            BrokenPanes = 0;
            UpdateBones();
        }

        public void UpdateBones()
        {
            new BoneJob { pos = runner.World.pos, nodeStart = nodeStart, nbrStart = nbrStart, nbr = nbr, restOff = restOff, rot = rot }
                .Schedule(access).Complete();
            CheckGlass();
        }

        void SetupGlass()
        {
            var byName = new Dictionary<string, Renderer>();
            foreach (var r in GetComponentsInChildren<SkinnedMeshRenderer>(true))
                byName[r.name] = r;
            var w = runner.World;
            var b = w.bodies[runner.VehicleBody];
            var def = b.def;
            foreach (var part in def.parts ?? new Hellcat.Sim.Data.PartDef[0])
            {
                if (part.visuals == null) continue;
                foreach (var vis in part.visuals)
                {
                    if (!vis.EndsWith("_Shards") || !byName.TryGetValue(vis, out var shards)) continue;
                    string paneName = vis.Substring(0, vis.Length - "_Shards".Length);
                    if (!byName.TryGetValue(paneName, out var intact)) continue;
                    var inPart = new HashSet<int>(part.nodes);
                    var beams = new List<int>();
                    for (int k = 0; k < b.beamCount; k++)
                    {
                        var bd = def.beams[k];
                        if ((bd.mat == "glass" || bd.mat == "glass_side") && inPart.Contains(bd.a) && inPart.Contains(bd.b))
                            beams.Add(b.beamStart + k);
                    }
                    shards.enabled = false;
                    panes.Add(new Pane { name = paneName, intact = intact, shards = shards, beams = beams.ToArray() });
                }
            }
        }

        /// <summary>A pane shatters (its shards replace it) as soon as one of its glass beams has broken.</summary>
        void CheckGlass()
        {
            var broken = runner.World.broken;
            foreach (var p in panes)
            {
                if (p.broken) continue;
                foreach (int j in p.beams)
                    if (broken[j] != 0)
                    {
                        p.broken = true;
                        p.intact.enabled = false;
                        p.shards.enabled = true;
                        BrokenPanes++;
                        break;
                    }
            }
        }

        void OnDestroy()
        {
            if (access.isCreated) access.Dispose();
            if (nbrStart.IsCreated) nbrStart.Dispose();
            if (nbr.IsCreated) nbr.Dispose();
            if (restOff.IsCreated) restOff.Dispose();
            if (rot.IsCreated) rot.Dispose();
        }

        [BurstCompile]
        struct BoneJob : IJobParallelForTransform
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
        }
    }

    /// <summary>Binary skin data of one FBX (Tools/Hellcat/Import Car): per mesh its bone list (node indices of the vehicle
    /// definition), bind poses and up to 4 weighted bones per vertex.</summary>
    public sealed class CarSkinData
    {
        public const uint Magic = 0x4E494B53; // "SKIN"
        public const int Version = 1;

        public sealed class MeshSkin
        {
            public string name;
            public int vertexCount;
            public int[] boneNodes;
            public Matrix4x4[] bindposes;
            public byte[] bonesPerVertex;        // per vertex, 1-4
            public BoneWeight1[] weights;        // flattened, sorted by weight descending per vertex
        }

        public readonly List<MeshSkin> meshes = new List<MeshSkin>();
        public string geometryHash = "";

        public void Write(string path)
        {
            using var w = new BinaryWriter(File.Create(path));
            w.Write(Magic);
            w.Write(Version);
            w.Write(geometryHash);
            w.Write(meshes.Count);
            foreach (var m in meshes)
            {
                w.Write(m.name);
                w.Write(m.vertexCount);
                w.Write(m.boneNodes.Length);
                foreach (var b in m.boneNodes) w.Write(b);
                foreach (var bp in m.bindposes)
                    for (int k = 0; k < 16; k++) w.Write(bp[k]);
                w.Write(m.bonesPerVertex);
                w.Write(m.weights.Length);
                foreach (var bw in m.weights)
                {
                    w.Write((ushort)bw.boneIndex);
                    w.Write(bw.weight);
                }
            }
        }

        public static CarSkinData Read(byte[] bytes)
        {
            var d = new CarSkinData();
            using var r = new BinaryReader(new MemoryStream(bytes));
            if (r.ReadUInt32() != Magic)
                throw new InvalidDataException("not a skin file");
            int ver = r.ReadInt32();
            if (ver != Version)
                throw new InvalidDataException($"skin file version {ver}, expected {Version}");
            d.geometryHash = r.ReadString();
            int n = r.ReadInt32();
            for (int i = 0; i < n; i++)
            {
                var m = new MeshSkin { name = r.ReadString(), vertexCount = r.ReadInt32() };
                int nb = r.ReadInt32();
                m.boneNodes = new int[nb];
                for (int k = 0; k < nb; k++) m.boneNodes[k] = r.ReadInt32();
                m.bindposes = new Matrix4x4[nb];
                for (int k = 0; k < nb; k++)
                {
                    var bp = new Matrix4x4();
                    for (int q = 0; q < 16; q++) bp[q] = r.ReadSingle();
                    m.bindposes[k] = bp;
                }
                m.bonesPerVertex = r.ReadBytes(m.vertexCount);
                int nw = r.ReadInt32();
                m.weights = new BoneWeight1[nw];
                for (int k = 0; k < nw; k++)
                    m.weights[k] = new BoneWeight1 { boneIndex = r.ReadUInt16(), weight = r.ReadSingle() };
                d.meshes.Add(m);
            }
            return d;
        }
    }
}
