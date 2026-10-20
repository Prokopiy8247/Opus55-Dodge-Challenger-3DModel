using Hellcat.Game.Core;
using Hellcat.Sim;
using Unity.Burst;
using Unity.Collections;
using Unity.Jobs;
using Unity.Mathematics;
using UnityEngine;
using UnityEngine.Rendering;

namespace Hellcat.Game.Views
{
    /// <summary>
    /// Node-beam view (N) and beam stress heat-map (H, brief 16): one line per beam, colour = |elastic force| / deform
    /// threshold with the heat-map (blue 0 -> yellow 0.5 -> red >= 1), neutral grey without; broken beams vanish; every
    /// node is a small three-axis cross, white, orange while it touches something. Drawn with depth (the paint hidden by
    /// <see cref="DebugViews"/>) or as an x-ray overlay over the paint. Vertex data is filled by a Burst job straight into
    /// the mesh buffers, only while the view is shown.
    /// </summary>
    [RequireComponent(typeof(MeshFilter), typeof(MeshRenderer))]
    public class SkeletonDebugView : MonoBehaviour
    {
        public SimRunner runner;
        public bool showStress = true;
        public bool showNodes = true;
        public float nodeSize = 0.012f;
        public Color neutralColor = new Color(0.85f, 0.85f, 0.85f, 1f);
        public Color nodeColor = new Color(0.92f, 0.92f, 0.92f, 1f);
        public Color contactColor = new Color(1f, 0.55f, 0.1f, 1f);

        Mesh mesh;
        MeshRenderer mr;
        Material mat;
        NativeArray<float3> verts;
        NativeArray<Color32> colors;
        int beamCount, nodeCount;
        bool overlay;

        public bool Visible => mr != null && mr.enabled;

        [BurstCompile]
        struct BeamJob : IJobParallelFor
        {
            [ReadOnly] public NativeArray<float3> pos;
            [ReadOnly] public NativeArray<BeamStatic> beams;
            [ReadOnly] public NativeArray<byte> broken;
            [ReadOnly] public NativeArray<float> stress;
            public bool showStress;
            public Color32 neutral;
            [NativeDisableParallelForRestriction] public NativeArray<float3> verts;
            [NativeDisableParallelForRestriction] public NativeArray<Color32> colors;

            public void Execute(int i)
            {
                var b = beams[i];
                float3 pa = pos[b.a], pb = pos[b.b];
                if (broken[i] != 0)
                    pb = pa;
                verts[2 * i] = pa;
                verts[2 * i + 1] = pb;
                Color32 c = neutral;
                if (showStress)
                {
                    float s = math.saturate(stress[i]);
                    float3 rgb = s < 0.5f
                        ? math.lerp(new float3(0.1f, 0.35f, 1f), new float3(1f, 0.9f, 0.1f), s * 2f)
                        : math.lerp(new float3(1f, 0.9f, 0.1f), new float3(1f, 0.08f, 0.05f), (s - 0.5f) * 2f);
                    c = new Color32((byte)(rgb.x * 255f), (byte)(rgb.y * 255f), (byte)(rgb.z * 255f), 255);
                }
                colors[2 * i] = c;
                colors[2 * i + 1] = c;
            }
        }

        [BurstCompile]
        struct NodeJob : IJobParallelFor
        {
            [ReadOnly] public NativeArray<float3> pos;
            [ReadOnly] public NativeArray<float> contactFn;
            public int offset;     // first vertex of the node crosses
            public float size;
            public Color32 normal, contact;
            [NativeDisableParallelForRestriction] public NativeArray<float3> verts;
            [NativeDisableParallelForRestriction] public NativeArray<Color32> colors;

            public void Execute(int i)
            {
                float3 p = pos[i];
                int v = offset + 6 * i;
                verts[v] = p - new float3(size, 0f, 0f);
                verts[v + 1] = p + new float3(size, 0f, 0f);
                verts[v + 2] = p - new float3(0f, size, 0f);
                verts[v + 3] = p + new float3(0f, size, 0f);
                verts[v + 4] = p - new float3(0f, 0f, size);
                verts[v + 5] = p + new float3(0f, 0f, size);
                var c = contactFn[i] > 0f ? contact : normal;
                for (int k = 0; k < 6; k++)
                    colors[v + k] = c;
            }
        }

        void Start()
        {
            mr = GetComponent<MeshRenderer>();
            mat = mr.material;   // own instance: the depth test changes with the overlay mode
            var w = runner.World;
            beamCount = w.BeamCount;
            nodeCount = showNodes ? w.NodeCount : 0;
            int nv = beamCount * 2 + nodeCount * 6;
            verts = new NativeArray<float3>(nv, Allocator.Persistent);
            colors = new NativeArray<Color32>(nv, Allocator.Persistent);
            var idx = new int[nv];
            for (int i = 0; i < idx.Length; i++)
                idx[i] = i;
            mesh = new Mesh { name = "SkeletonLines", indexFormat = IndexFormat.UInt32 };
            mesh.MarkDynamic();
            Fill();
            mesh.SetIndices(idx, MeshTopology.Lines, 0);
            mesh.bounds = new Bounds(Vector3.zero, Vector3.one * 1e5f);
            GetComponent<MeshFilter>().sharedMesh = mesh;
            runner.Stepped += OnStepped;
            runner.Respawned += Fill;
            SetOverlay(overlay);
        }

        /// <summary>Shows or hides the lines; showing refreshes them at once.</summary>
        public void Show(bool on)
        {
            if (mr == null)
                return;
            mr.enabled = on;
            if (on && verts.IsCreated)
                Fill();
        }

        /// <summary>X-ray: drawn over everything (paint visible), or with depth.</summary>
        public void SetOverlay(bool on)
        {
            overlay = on;
            if (mat == null)
                return;
            mat.SetFloat("_ZTest", on ? (float)CompareFunction.Always : (float)CompareFunction.LessEqual);
            mat.renderQueue = on ? (int)RenderQueue.Overlay : (int)RenderQueue.Geometry + 10;
        }

        void OnStepped(int n)
        {
            if (mr != null && mr.enabled)
                Fill();
        }

        void Fill()
        {
            var w = runner.World;
            var h = new BeamJob
            {
                pos = w.pos,
                beams = w.beams,
                broken = w.broken,
                stress = w.stress,
                showStress = showStress,
                neutral = neutralColor,
                verts = verts,
                colors = colors,
            }.Schedule(beamCount, 512);
            if (nodeCount > 0)
                h = new NodeJob
                {
                    pos = w.pos,
                    contactFn = w.contactFn,
                    offset = beamCount * 2,
                    size = nodeSize,
                    normal = nodeColor,
                    contact = contactColor,
                    verts = verts,
                    colors = colors,
                }.Schedule(nodeCount, 256, h);
            h.Complete();
            mesh.SetVertices(verts);
            mesh.SetColors(colors);
        }

        void OnDestroy()
        {
            if (runner)
            {
                runner.Stepped -= OnStepped;
                runner.Respawned -= Fill;
            }
            if (verts.IsCreated) verts.Dispose();
            if (colors.IsCreated) colors.Dispose();
        }
    }
}
