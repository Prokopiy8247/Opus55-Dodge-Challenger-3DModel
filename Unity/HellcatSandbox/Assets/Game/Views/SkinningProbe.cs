using System.Collections.Generic;
using Unity.Burst;
using Unity.Collections;
using Unity.Jobs;
using Unity.Mathematics;
using UnityEngine;

namespace Hellcat.Game.Views
{
    /// <summary>
    /// Checks of the skinned car (brief 7 validation, gate G-Crash): every frame the linear-blend skinning of all car meshes
    /// is reproduced on the CPU (Burst) from the same bones, weights and bind poses the GPU uses. Reports the largest vertex
    /// displacement in one frame and the spike: how far a vertex's displacement in one frame differs from the mean of its
    /// mesh neighbours' (the Laplacian of the displacement field: a vertex leaving its surface; the car's motion, the
    /// wheels' spin and a smoothly crumpling panel give none), the largest distance of a skinned vertex from the rigid
    /// motion of its main node (stretch), and the share of triangles whose normal turned over against the rigid motion of
    /// their main node (mesh inversion).
    /// </summary>
    public class SkinningProbe : MonoBehaviour
    {
        public SoftBodyCarView view;
        [Tooltip("Triangles sampled per mesh for the inversion check (0: all)")]
        public int triangleSample = 4000;

        struct MeshData
        {
            public string name;
            public int vStart, vCount, tStart, tCount, boneStart, boneCount;
        }

        // per mesh over the whole run, split into the cabin box (first measurement) and the rest: largest spike, largest
        // inverted share; per vertex / sampled triangle the cabin flag
        float[] runSpike, runInv, runSpikeOut, runInvOut, runInvA, runInvAOut, runInvAT, runInvATOut, runInvAPulse, runInvAPulseT;
        /// <summary>Simulation time of the next measurement (set by the caller; stamps the largest turned-over areas).</summary>
        public float time;
        /// <summary>The next measurement falls in the impact pulse (set by the caller): its cabin turned-over areas are kept
        /// apart, as transient folds of the trim while the structure is loaded, from the rest of the run.</summary>
        public bool inPulse;
        bool[] running;
        NativeArray<byte> vCabin, tCabin;
        float4x4[] prevBone;
        public float MaxFrameRotationDeg { get; private set; }
        /// <summary>Optional, per node: still joined to the cabin (set by the crash scenario before each measurement).</summary>
        public bool[] Connected;
        public string MaxFrameRotationNode { get; private set; } = "";

        readonly List<MeshData> meshes = new List<MeshData>();
        NativeArray<float3> restLocal;          // mesh-space vertices
        NativeArray<int4> vBones;               // global bone slots (into boneNode / bindpose), -1 unused
        NativeArray<float4> vWeights;
        NativeArray<int> slotNode;              // node bone index per slot
        NativeArray<float4x4> slotBind;         // bind pose per slot
        NativeArray<float3> skinned, previous;
        NativeArray<int3> tris;
        NativeArray<float4x4> boneMatrix;        // per node bone: current local-to-world
        NativeArray<float> vDisp, vSpike;
        NativeArray<float3> dispVec;             // per vertex: displacement since the last measurement
        NativeArray<float3> refPos;              // per vertex: skinned position at the first measurement
        bool haveRef;
        NativeArray<int> adjStart, adjIndex;     // mesh neighbours of every vertex (CSR over all triangles)
        NativeArray<float3> lapRest;             // per vertex: rest_v - mean of its neighbours' rest positions (mesh space)
        NativeArray<float4x4> prevBoneN;         // per node bone: local-to-world at the last measurement
        NativeArray<byte> triFlip;
        NativeArray<float> triArea;              // per sampled triangle: rest area (m^2) times the sampling step of its mesh
        bool ready, havePrev;

        public float MaxFrameDisplacement { get; private set; }
        public string MaxFrameDisplacementMesh { get; private set; } = "";
        public float MaxSpike { get; private set; }
        /// <summary>Last measurement: the largest vertex displacement minus the largest node displacement (m).</summary>
        public float SpikeExcess { get; private set; }
        public string SpikeExcessMesh { get; private set; } = "";
        public string MaxSpikeMesh { get; private set; } = "";
        public float MaxStretch { get; private set; }
        public float InvertedShare { get; private set; }
        public int VertexCount => restLocal.IsCreated ? restLocal.Length : 0;

        public void Init()
        {
            if (ready || view == null || view.nodeBones == null)
                return;
            var smrs = GetComponentsInChildren<SkinnedMeshRenderer>(true);
            var boneIndex = new Dictionary<Transform, int>();
            for (int i = 0; i < view.nodeBones.Length; i++)
                boneIndex[view.nodeBones[i]] = i;
            var rl = new List<float3>();
            var vb = new List<int4>();
            var vw = new List<float4>();
            var sn = new List<int>();
            var sb = new List<float4x4>();
            var tr = new List<int3>();
            var trStep = new List<int>();
            var edges = new List<long>();
            foreach (var smr in smrs)
            {
                var mesh = smr.sharedMesh;
                if (mesh == null || !mesh.isReadable)
                    continue;
                var md = new MeshData { name = smr.name, vStart = rl.Count, vCount = mesh.vertexCount, tStart = tr.Count, boneStart = sn.Count, boneCount = smr.bones.Length };
                var bp = mesh.bindposes;
                for (int k = 0; k < smr.bones.Length; k++)
                {
                    sn.Add(boneIndex[smr.bones[k]]);
                    sb.Add(bp[k]);
                }
                foreach (var v in mesh.vertices) rl.Add(v);
                var bpv = mesh.GetBonesPerVertex();
                var bw = mesh.GetAllBoneWeights();
                int o = 0;
                for (int v = 0; v < mesh.vertexCount; v++)
                {
                    var b4 = new int4(-1);
                    var w4 = float4.zero;
                    for (int q = 0; q < bpv[v]; q++, o++)
                    {
                        if (q < 4)
                        {
                            b4[q] = md.boneStart + bw[o].boneIndex;
                            w4[q] = bw[o].weight;
                        }
                    }
                    vb.Add(b4);
                    vw.Add(w4);
                }
                var t = mesh.triangles;
                int nt = t.Length / 3;
                for (int k = 0; k < t.Length; k += 3)
                    for (int e = 0; e < 3; e++)
                    {
                        long x = md.vStart + t[k + e], y = md.vStart + t[k + (e + 1) % 3];
                        edges.Add(x << 32 | y);
                        edges.Add(y << 32 | x);
                    }
                int step = triangleSample > 0 ? math.max(1, nt / triangleSample) : 1;
                for (int k = 0; k < nt; k += step)
                {
                    tr.Add(new int3(md.vStart + t[3 * k], md.vStart + t[3 * k + 1], md.vStart + t[3 * k + 2]));
                    trStep.Add(step);
                }
                md.tCount = tr.Count - md.tStart;
                meshes.Add(md);
            }
            restLocal = new NativeArray<float3>(rl.ToArray(), Allocator.Persistent);
            vBones = new NativeArray<int4>(vb.ToArray(), Allocator.Persistent);
            vWeights = new NativeArray<float4>(vw.ToArray(), Allocator.Persistent);
            slotNode = new NativeArray<int>(sn.ToArray(), Allocator.Persistent);
            slotBind = new NativeArray<float4x4>(sb.ToArray(), Allocator.Persistent);
            skinned = new NativeArray<float3>(rl.Count, Allocator.Persistent);
            previous = new NativeArray<float3>(rl.Count, Allocator.Persistent);
            vDisp = new NativeArray<float>(rl.Count, Allocator.Persistent);
            vSpike = new NativeArray<float>(rl.Count, Allocator.Persistent);
            dispVec = new NativeArray<float3>(rl.Count, Allocator.Persistent);
            refPos = new NativeArray<float3>(rl.Count, Allocator.Persistent);
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
            prevBoneN = new NativeArray<float4x4>(view.nodeBones.Length, Allocator.Persistent);
            tris = new NativeArray<int3>(tr.ToArray(), Allocator.Persistent);
            triFlip = new NativeArray<byte>(tr.Count, Allocator.Persistent);
            triArea = new NativeArray<float>(tr.Count, Allocator.Persistent);
            for (int k = 0; k < tr.Count; k++)
            {
                int3 q = tr[k];
                triArea[k] = 0.5f * math.length(math.cross(rl[q.y] - rl[q.x], rl[q.z] - rl[q.x])) * trStep[k];
            }
            boneMatrix = new NativeArray<float4x4>(view.nodeBones.Length, Allocator.Persistent);
            ready = true;
            Debug.Log($"[SkinningProbe] {meshes.Count} meshes, {rl.Count} vertices, {tr.Count} sampled triangles");
        }

        /// <summary>Forget the previous measurement (after a respawn: the next frame is compared with nothing).</summary>
        public void ResetHistory()
        {
            havePrev = false;
            prevBone = null;
        }

        /// <summary>Skins every vertex for the current bone transforms and updates the per-frame statistics.</summary>
        public void Measure()
        {
            if (!ready)
                Init();
            if (!ready)
                return;
            for (int i = 0; i < view.nodeBones.Length; i++)
                boneMatrix[i] = view.nodeBones[i].localToWorldMatrix;
            new SkinJob
            {
                rest = restLocal, bones = vBones, weights = vWeights, slotNode = slotNode, slotBind = slotBind, boneMatrix = boneMatrix,
                skinned = skinned, previous = previous, havePrev = havePrev, disp = vDisp, dispVec = dispVec,
            }.Schedule(restLocal.Length, 1024).Complete();
            new LaplaceJob
            {
                dispVec = dispVec, adjStart = adjStart, adjIndex = adjIndex, havePrev = havePrev, spike = vSpike, lapRest = lapRest,
                bones = vBones, slotNode = slotNode, slotBind = slotBind, boneMatrix = boneMatrix, prevBone = prevBoneN,
            }.Schedule(restLocal.Length, 1024).Complete();
            new FlipJob { tris = tris, skinned = skinned, rest = restLocal, bones = vBones, weights = vWeights, slotNode = slotNode, slotBind = slotBind, boneMatrix = boneMatrix, flip = triFlip }
                .Schedule(tris.Length, 1024).Complete();
            float maxD = 0f;
            int maxV = -1;
            for (int v = 0; v < vDisp.Length; v++)
                if (vDisp[v] > maxD) { maxD = vDisp[v]; maxV = v; }
            MaxFrameDisplacement = havePrev ? maxD : 0f;
            MaxFrameDisplacementMesh = maxV >= 0 ? MeshOf(maxV) : "";
            float maxS = 0f;
            int maxSv = -1;
            for (int v = 0; v < vSpike.Length; v++)
                if (vSpike[v] > maxS) { maxS = vSpike[v]; maxSv = v; }
            MaxSpike = havePrev ? maxS : 0f;
            MaxSpikeMesh = maxSv >= 0 ? MeshOf(maxSv) : "";
            float maxNode = 0f;
            if (havePrev)
                for (int i = 0; i < boneMatrix.Length; i++)
                    maxNode = math.max(maxNode, math.distance(boneMatrix[i].c3.xyz, prevBoneN[i].c3.xyz));
            SpikeExcess = havePrev ? math.max(0f, MaxFrameDisplacement - maxNode) : 0f;
            SpikeExcessMesh = MaxFrameDisplacementMesh;
            float flipA = 0f, allA = 0f;
            for (int t = 0; t < triFlip.Length; t++)
            {
                flipA += triFlip[t] * triArea[t];
                allA += triArea[t];
            }
            InvertedShare = allA > 0f ? flipA / allA : 0f;
            NativeArray<float3>.Copy(skinned, previous);
            if (prevBone == null)
            {
                prevBone = new float4x4[boneMatrix.Length];
                for (int i = 0; i < boneMatrix.Length; i++) prevBone[i] = boneMatrix[i];
            }
            if (!haveRef)
            {
                NativeArray<float3>.Copy(skinned, refPos);
                haveRef = true;
                // the cabin box: between the C-pillar and the A-pillar base, inside the sills (car at its spawn, +z forward)
                runSpike = new float[meshes.Count];
                runInv = new float[meshes.Count];
                runSpikeOut = new float[meshes.Count];
                runInvOut = new float[meshes.Count];
                runInvA = new float[meshes.Count];
                runInvAOut = new float[meshes.Count];
                runInvAT = new float[meshes.Count];
                runInvATOut = new float[meshes.Count];
                runInvAPulse = new float[meshes.Count];
                runInvAPulseT = new float[meshes.Count];
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
                }
            }
            else
            {
                for (int k = 0; k < meshes.Count; k++)
                {
                    var md = meshes[k];
                    float sp = 0f, spo = 0f;
                    for (int v = md.vStart; v < md.vStart + md.vCount; v++)
                    {
                        if (vCabin[v] != 0) sp = math.max(sp, vSpike[v]);
                        else spo = math.max(spo, vSpike[v]);
                    }
                    float fl = 0f, nt = 0f, flo = 0f, nto = 0f;      // turned-over area / sampled area
                    for (int t = md.tStart; t < md.tStart + md.tCount; t++)
                    {
                        if (tCabin[t] != 0) { fl += triFlip[t] * triArea[t]; nt += triArea[t]; }
                        else { flo += triFlip[t] * triArea[t]; nto += triArea[t]; }
                    }
                    runSpike[k] = math.max(runSpike[k], sp);
                    runInv[k] = math.max(runInv[k], nt > 0f ? fl / nt : 0f);
                    runSpikeOut[k] = math.max(runSpikeOut[k], spo);
                    runInvOut[k] = math.max(runInvOut[k], nto > 0f ? flo / nto : 0f);
                    if (inPulse) { if (fl > runInvAPulse[k]) { runInvAPulse[k] = fl; runInvAPulseT[k] = time; } }
                    else if (fl > runInvA[k]) { runInvA[k] = fl; runInvAT[k] = time; }
                    if (flo > runInvAOut[k]) { runInvAOut[k] = flo; runInvATOut[k] = time; }
                }
                // node frames: largest rotation since the last measurement (the wheels' and suspension nodes turn by design)
                for (int i = 0; i < boneMatrix.Length; i++)
                {
                    string bn = view.nodeBones[i].name;
                    if (bn.Length > 5 && bn[4] == '_' && char.IsDigit(bn[0]))
                        bn = bn.Substring(5);            // bones are named '<node index>_<node name>'
                    if (bn.StartsWith("FR_") || bn.StartsWith("FL_") || bn.StartsWith("RR_") || bn.StartsWith("RL_")) continue;
                    if (Connected != null && !Connected[i]) continue;
                    float3x3 a = new float3x3(prevBone[i]), b = new float3x3(boneMatrix[i]);
                    float3x3 rel = math.mul(b, math.transpose(a));
                    float tr = rel.c0.x + rel.c1.y + rel.c2.z;
                    float ang = math.degrees(math.acos(math.clamp(0.5f * (tr - 1f), -1f, 1f)));
                    if (ang > MaxFrameRotationDeg)
                    {
                        MaxFrameRotationDeg = ang;
                        MaxFrameRotationNode = view.nodeBones[i].name;
                    }
                }
            }
            for (int i = 0; i < boneMatrix.Length; i++) prevBone[i] = boneMatrix[i];
            NativeArray<float4x4>.Copy(boneMatrix, prevBoneN);
            havePrev = true;
        }

        /// <summary>Largest distance of a skinned vertex from the rigid motion of its main node (from the bind pose).</summary>
        public float Stretch()
        {
            if (!ready)
                return 0f;
            float m = 0f;
            for (int v = 0; v < restLocal.Length; v += 7)
            {
                int s = vBones[v].x;
                if (s < 0) continue;
                float3 rigid = math.transform(math.mul(boneMatrix[slotNode[s]], slotBind[s]), restLocal[v]);
                m = math.max(m, math.distance(rigid, skinned[v]));
            }
            MaxStretch = m;
            return m;
        }

        /// <summary>Per mesh: the largest stretch (as <see cref="Stretch"/>), the largest spike of the last measured frame
        /// and the share of the sampled triangles' area turned over; the worst few as text.</summary>
        public string MeshReport(int top = 6)
        {
            if (!ready)
                return "";
            var rows = new List<(string name, float stretch, float jump, float inv)>();
            foreach (var md in meshes)
            {
                float st = 0f, jp = 0f;
                for (int v = md.vStart; v < md.vStart + md.vCount; v++)
                {
                    jp = math.max(jp, vSpike[v]);
                    int s = vBones[v].x;
                    if (s < 0) continue;
                    float3 rigid = math.transform(math.mul(boneMatrix[slotNode[s]], slotBind[s]), restLocal[v]);
                    st = math.max(st, math.distance(rigid, skinned[v]));
                }
                float fl = 0f, at = 0f;
                for (int t = md.tStart; t < md.tStart + md.tCount; t++)
                {
                    fl += triFlip[t] * triArea[t];
                    at += triArea[t];
                }
                rows.Add((md.name, st, jp, at > 0f ? fl / at : 0f));
            }
            string Top(System.Comparison<(string name, float stretch, float jump, float inv)> c, System.Func<(string name, float stretch, float jump, float inv), string> f)
            {
                rows.Sort(c);
                var sb = new System.Text.StringBuilder();
                for (int k = 0; k < math.min(top, rows.Count); k++) sb.Append(k > 0 ? ", " : "").Append(f(rows[k]));
                return sb.ToString();
            }
            return "stretch: " + Top((a, b) => b.stretch.CompareTo(a.stretch), r => $"{r.name} {r.stretch:F3} m") +
                   " | inverted: " + Top((a, b) => b.inv.CompareTo(a.inv), r => $"{r.name} {r.inv * 100:F1} %") +
                   " | spike: " + Top((a, b) => b.jump.CompareTo(a.jump), r => $"{r.name} {r.jump * 1000:F0} mm");
        }

        /// <summary>Largest spike and inverted share over the run in the cabin and elsewhere, with the worst meshes.</summary>
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
                cab.Add((meshes[k].name, runSpike[k], runInv[k]));
                oth.Add((meshes[k].name, runSpikeOut[k], runInvOut[k]));
                cabinSpike = math.max(cabinSpike, runSpike[k]);
                cabinInv = math.max(cabinInv, runInv[k]);
                otherSpike = math.max(otherSpike, runSpikeOut[k]);
                otherInv = math.max(otherInv, runInvOut[k]);
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
            cab.Sort((a, b) => b.Item3.CompareTo(a.Item3));
            var sbi = new System.Text.StringBuilder(" | by inverted share:");
            for (int k = 0; k < math.min(6, cab.Count); k++)
                sbi.Append($" {cab[k].Item1} {cab[k].Item3 * 100:F2} %");
            worstCabin += sbi.ToString();
        }

        /// <summary>Largest turned-over area (m^2) of any one mesh over the run, in the cabin and elsewhere, with the mesh.</summary>
        public void InvertedAreaSummary(out float cabinArea, out string cabinMesh, out float otherArea, out string otherMesh)
        {
            InvertedAreaSummary(out cabinArea, out cabinMesh, out _, out otherArea, out otherMesh, out _);
        }

        /// <summary>Largest turned-over area of a cabin mesh within the impact pulse, with its mesh and time.</summary>
        public void PulseInvertedArea(out float area, out string mesh, out float when)
        {
            area = when = 0f;
            mesh = "";
            if (runInvAPulse == null)
                return;
            for (int k = 0; k < meshes.Count; k++)
                if (runInvAPulse[k] > area) { area = runInvAPulse[k]; mesh = meshes[k].name; when = runInvAPulseT[k]; }
        }

        /// <summary>As above (cabin: outside the impact pulse), with the times of the two largest areas and the cabin meshes
        /// above 1 cm2 as text.</summary>
        public string InvertedAreaSummary(out float cabinArea, out string cabinMesh, out float cabinTime, out float otherArea,
            out string otherMesh, out float otherTime)
        {
            cabinArea = otherArea = cabinTime = otherTime = 0f;
            cabinMesh = otherMesh = "";
            if (runInvA == null)
                return "";
            var l = new List<(float a, string n, float t)>();
            for (int k = 0; k < meshes.Count; k++)
            {
                if (runInvA[k] > cabinArea) { cabinArea = runInvA[k]; cabinMesh = meshes[k].name; cabinTime = runInvAT[k]; }
                if (runInvAOut[k] > otherArea) { otherArea = runInvAOut[k]; otherMesh = meshes[k].name; otherTime = runInvATOut[k]; }
                if (runInvA[k] > 1e-4f) l.Add((runInvA[k], meshes[k].name, runInvAT[k]));
            }
            l.Sort((x, y) => y.a.CompareTo(x.a));
            var sb = new System.Text.StringBuilder();
            for (int k = 0; k < math.min(8, l.Count); k++)
                sb.Append(k > 0 ? ", " : "").Append($"{l[k].n} {l[k].a * 1e4f:F1} cm2 at {l[k].t:F2} s");
            return sb.ToString();
        }

        /// <summary>Per mesh: the largest distance of a vertex from where a rigid motion x = c + R (x_ref - c0) (the cabin's)
        /// would carry its first measured position, and the largest rise along R up; the worst few as text.</summary>
        public string RigidOffsetReport(double3x3 r, double3 c, double3 c0, int top = 8)
        {
            if (!ready || !haveRef)
                return "";
            double3 up = math.mul(r, new double3(0, 1, 0));
            var rows = new List<(string name, double off, double rise)>();
            foreach (var md in meshes)
            {
                // spinning parts move away from any body-fixed reference
                if (md.name.EndsWith("_Tire") || md.name.EndsWith("_Rim") || md.name.EndsWith("_Disc") || md.name.Contains("Shaft"))
                    continue;
                double off = 0, rise = 0;
                for (int v = md.vStart; v < md.vStart + md.vCount; v += 3)
                {
                    double3 d = (double3)skinned[v] - (c + math.mul(r, (double3)refPos[v] - c0));
                    off = math.max(off, math.length(d));
                    rise = math.max(rise, math.dot(d, up));
                }
                rows.Add((md.name, off, rise));
            }
            rows.Sort((a, b) => b.off.CompareTo(a.off));
            var sb = new System.Text.StringBuilder("offset from the cabin's rigid motion:");
            for (int k = 0; k < math.min(top, rows.Count); k++)
                sb.Append($" {rows[k].name} {rows[k].off:F3} m (rise {rows[k].rise:F3})");
            return sb.ToString();
        }

        string MeshOf(int v)
        {
            foreach (var md in meshes)
                if (v >= md.vStart && v < md.vStart + md.vCount)
                    return md.name;
            return "";
        }

        void OnDestroy()
        {
            if (restLocal.IsCreated) restLocal.Dispose();
            if (skinned.IsCreated) skinned.Dispose();
            if (previous.IsCreated) previous.Dispose();
            if (vBones.IsCreated) vBones.Dispose();
            if (vWeights.IsCreated) vWeights.Dispose();
            if (slotNode.IsCreated) slotNode.Dispose();
            if (slotBind.IsCreated) slotBind.Dispose();
            if (tris.IsCreated) tris.Dispose();
            if (boneMatrix.IsCreated) boneMatrix.Dispose();
            if (vDisp.IsCreated) vDisp.Dispose();
            if (vSpike.IsCreated) vSpike.Dispose();
            if (dispVec.IsCreated) dispVec.Dispose();
            if (vCabin.IsCreated) vCabin.Dispose();
            if (tCabin.IsCreated) tCabin.Dispose();
            if (refPos.IsCreated) refPos.Dispose();
            if (adjStart.IsCreated) adjStart.Dispose();
            if (adjIndex.IsCreated) adjIndex.Dispose();
            if (lapRest.IsCreated) lapRest.Dispose();
            if (prevBoneN.IsCreated) prevBoneN.Dispose();
            if (triFlip.IsCreated) triFlip.Dispose();
            if (triArea.IsCreated) triArea.Dispose();
        }

        [BurstCompile]
        struct SkinJob : IJobParallelFor
        {
            [ReadOnly] public NativeArray<float3> rest;
            [ReadOnly] public NativeArray<int4> bones;
            [ReadOnly] public NativeArray<float4> weights;
            [ReadOnly] public NativeArray<int> slotNode;
            [ReadOnly] public NativeArray<float4x4> slotBind, boneMatrix;
            [ReadOnly] public NativeArray<float3> previous;
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
            [ReadOnly] public NativeArray<float3> dispVec, lapRest;
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
                spike[v] = math.length(dispVec[v] - m / (e - a));
            }
        }

        [BurstCompile]
        struct FlipJob : IJobParallelFor
        {
            [ReadOnly] public NativeArray<int3> tris;
            [ReadOnly] public NativeArray<float3> skinned, rest;
            [ReadOnly] public NativeArray<int4> bones;
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
                        m += wi[k] * math.mul(boneMatrix[slotNode[bi[k]]], slotBind[bi[k]]);
                float3 a = math.transform(m, rest[i.x]), b = math.transform(m, rest[i.y]), c = math.transform(m, rest[i.z]);
                float3 n0 = math.cross(b - a, c - a);
                flip[t] = (byte)(math.dot(n, n0) < -1e-12f && math.lengthsq(n) > 1e-12f ? 1 : 0);
            }
        }
    }
}
