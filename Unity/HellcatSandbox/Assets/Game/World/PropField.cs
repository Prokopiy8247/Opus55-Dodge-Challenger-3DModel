using System;
using System.Collections.Generic;
using Hellcat.Game.Core;
using Hellcat.Game.Views;
using Hellcat.Sim;
using Hellcat.Sim.Props;
using Unity.Mathematics;
using UnityEngine;

namespace Hellcat.Game.World
{
    /// <summary>
    /// A field of debris bodies (test map O8, D-081): each entry becomes a node-beam body of <see cref="PropFactory"/> in the
    /// car's world, drawn as a rigid mesh on the best-fit frame of its movable nodes. <see cref="ResetAll"/> puts every
    /// prop back where it started (Ctrl+R).
    /// </summary>
    [DefaultExecutionOrder(110)]   // after the solver has stepped, with the car's views
    public class PropField : MonoBehaviour, IDynamicBodySource
    {
        [Serializable]
        public struct Spot
        {
            public PropFactory.Kind kind;
            public Vector3 position;   // in this object's frame, on the ground
            public float yawDeg;
        }

        public SimRunner runner;
        public List<Spot> props = new List<Spot>();
        public Material barrelMaterial, boxMaterial, coneMaterial, fenceMaterial;

        int[] bodies = Array.Empty<int>();
        /// <summary>Spawn height above the surface below (m); stacked props add it per layer.</summary>
        public const float SpawnGap = 0.012f;

        sealed class View
        {
            public Transform t;
            public int[] nodes;          // world indices of the movable nodes
            public float3[] rest;        // their model positions minus the centroid
            public float3 restCentroid;
            public quaternion rot;
        }
        readonly List<View> views = new List<View>();

        public IReadOnlyList<int> Bodies => bodies;
        public int Count => props.Count;

        public void AddBodies(SoftBodyWorld world)
        {
            bodies = new int[props.Count];
            for (int i = 0; i < props.Count; i++)
            {
                var s = props[i];
                var (def, prm) = PropFactory.Build(s.kind);
                var rot = transform.rotation * Quaternion.Euler(0f, s.yawDeg, 0f);
                // 12 mm above the surface: a node inside the 10 mm contact zone at spawn would be kicked off it
                bodies[i] = world.AddBody($"{s.kind}_{i}", def, prm, transform.TransformPoint(s.position + new Vector3(0f, SpawnGap, 0f)), rot, float3.zero, false);
                world.MarkSleepable(bodies[i]);   // asleep while at rest and far from the car (D-098)
            }
        }

        void Start()
        {
            if (runner == null || runner.World == null)
                return;
            for (int i = 0; i < props.Count; i++)
                views.Add(MakeView(i));
            runner.Respawned += WarmStart;
            runner.Rebuilt += WarmStart;
            WarmStart();
        }

        void OnDestroy()
        {
            if (!runner) return;
            runner.Respawned -= WarmStart;
            runner.Rebuilt -= WarmStart;
        }

        View MakeView(int i)
        {
            var s = props[i];
            var b = runner.World.bodies[bodies[i]];
            var go = new GameObject($"{s.kind}_{i}");
            go.transform.SetParent(transform, false);
            AddShape(go.transform, s.kind);
            var ids = new List<int>();
            for (int k = 0; k < b.nodeCount; k++)
                if (b.def.nodes[k].m > 0f)
                    ids.Add(k);
            var v = new View { t = go.transform, nodes = new int[ids.Count], rest = new float3[ids.Count] };
            float3 c = float3.zero;
            for (int k = 0; k < ids.Count; k++)
            {
                var p = b.def.nodes[ids[k]].p;
                v.rest[k] = new float3(p[0], p[1], p[2]);
                c += v.rest[k];
                v.nodes[k] = b.nodeStart + ids[k];
            }
            c /= math.max(ids.Count, 1);
            for (int k = 0; k < ids.Count; k++)
                v.rest[k] -= c;
            v.restCentroid = c;
            return v;
        }

        void AddShape(Transform parent, PropFactory.Kind kind)
        {
            GameObject Part(PrimitiveType type, Vector3 pos, Vector3 scale, Material mat)
            {
                var g = GameObject.CreatePrimitive(type);
                Destroy(g.GetComponent<Collider>());
                g.transform.SetParent(parent, false);
                g.transform.localPosition = pos;
                g.transform.localScale = scale;
                if (mat) g.GetComponent<MeshRenderer>().sharedMaterial = mat;
                return g;
            }
            switch (kind)
            {
                case PropFactory.Kind.Barrel:
                    Part(PrimitiveType.Cylinder, new Vector3(0f, 0.5f * PropFactory.BarrelHeight, 0f),
                        new Vector3(2f * PropFactory.BarrelRadius, 0.5f * PropFactory.BarrelHeight, 2f * PropFactory.BarrelRadius), barrelMaterial);
                    break;
                case PropFactory.Kind.Box:
                    Part(PrimitiveType.Cube, new Vector3(0f, 0.5f * PropFactory.BoxSize, 0f), Vector3.one * PropFactory.BoxSize, boxMaterial);
                    break;
                case PropFactory.Kind.Cone:
                {
                    Part(PrimitiveType.Cube, new Vector3(0f, 0.015f, 0f), new Vector3(PropFactory.ConeBase, 0.03f, PropFactory.ConeBase), coneMaterial);
                    var g = new GameObject("cone");
                    g.transform.SetParent(parent, false);
                    g.AddComponent<MeshFilter>().sharedMesh = ConeMesh();
                    var mr = g.AddComponent<MeshRenderer>();
                    if (coneMaterial) mr.sharedMaterial = coneMaterial;
                    break;
                }
                case PropFactory.Kind.FencePanel:
                    Part(PrimitiveType.Cube, new Vector3(0f, 0.62f, 0f), new Vector3(PropFactory.FenceWidth - 0.1f, 1.0f, 0.03f), fenceMaterial);
                    Part(PrimitiveType.Cube, new Vector3(-0.5f * PropFactory.FenceWidth + 0.05f, 0.6f, 0f), new Vector3(0.1f, 1.3f, 0.1f), fenceMaterial);
                    Part(PrimitiveType.Cube, new Vector3(0.5f * PropFactory.FenceWidth - 0.05f, 0.6f, 0f), new Vector3(0.1f, 1.3f, 0.1f), fenceMaterial);
                    Part(PrimitiveType.Cube, new Vector3(0f, 1.15f, 0f), new Vector3(PropFactory.FenceWidth, 0.08f, 0.06f), fenceMaterial);
                    Part(PrimitiveType.Cube, new Vector3(0f, 0.2f, 0f), new Vector3(PropFactory.FenceWidth, 0.08f, 0.06f), fenceMaterial);
                    break;
            }
        }

        static Mesh coneMesh;

        /// <summary>Truncated cone 0.05-0.70 m, foot radius 0.14 m, tip radius 0.025 m, 24 sides.</summary>
        static Mesh ConeMesh()
        {
            if (coneMesh != null)
                return coneMesh;
            const int n = 24;
            var v = new List<Vector3>();
            var nrm = new List<Vector3>();
            var tri = new List<int>();
            float r0 = 0.14f, r1 = 0.025f, y0 = 0.03f, y1 = PropFactory.ConeHeight;
            float slope = (r0 - r1) / (y1 - y0);
            for (int k = 0; k <= n; k++)
            {
                float a = 2f * Mathf.PI * k / n;
                var d = new Vector3(Mathf.Cos(a), 0f, Mathf.Sin(a));
                var nn = (d + Vector3.up * slope).normalized;
                v.Add(d * r0 + Vector3.up * y0); nrm.Add(nn);
                v.Add(d * r1 + Vector3.up * y1); nrm.Add(nn);
            }
            for (int k = 0; k < n; k++)
            {
                int a = 2 * k;
                tri.AddRange(new[] { a, a + 1, a + 2, a + 1, a + 3, a + 2 });
            }
            coneMesh = new Mesh { name = "TrafficCone" };
            coneMesh.SetVertices(v);
            coneMesh.SetNormals(nrm);
            coneMesh.SetTriangles(tri, 0);
            coneMesh.RecalculateBounds();
            return coneMesh;
        }

        void WarmStart()
        {
            for (int i = 0; i < views.Count; i++)
                views[i].rot = transform.rotation * Quaternion.Euler(0f, props[i].yawDeg, 0f);
            LateUpdate();
        }

        void LateUpdate()
        {
            if (runner == null || runner.World == null || !runner.World.IsBuilt)
                return;
            var pos = runner.World.pos;
            foreach (var v in views)
            {
                float3 c = float3.zero;
                foreach (int n in v.nodes) c += pos[n];
                c /= v.nodes.Length;
                float3x3 s = float3x3.zero;
                for (int k = 0; k < v.nodes.Length; k++)
                {
                    float3 x = pos[v.nodes[k]] - c, X = v.rest[k];
                    s += new float3x3(X * x.x, X * x.y, X * x.z);
                }
                v.rot = SoftBodyCarView.BestRotation(s, v.rot);
                v.t.SetPositionAndRotation(c - math.mul(v.rot, v.restCentroid), v.rot);
            }
        }

        /// <summary>Every prop back at its start, at rest (Ctrl+R).</summary>
        public void ResetAll()
        {
            if (runner == null || runner.World == null)
                return;
            foreach (int b in bodies)
                runner.World.ResetBody(b);
            runner.World.WakeTail();   // settle again before they may sleep
            WarmStart();
        }

        /// <summary>Largest displacement of a prop's centroid from its start (m) and how many moved more than
        /// <paramref name="threshold"/>.</summary>
        public float Displacement(float threshold, out int moved)
        {
            moved = 0;
            float worst = 0f;
            var w = runner.World;
            foreach (int bi in bodies)
            {
                var b = w.bodies[bi];
                float3 c = float3.zero, c0 = float3.zero;
                int n = 0;
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                {
                    if (w.invMass[i] <= 0f) continue;
                    c += w.pos[i];
                    c0 += w.SpawnPosition(i);
                    n++;
                }
                float d = n > 0 ? math.distance(c / n, c0 / n) : 0f;
                worst = math.max(worst, d);
                if (d > threshold) moved++;
            }
            return worst;
        }
    }
}
