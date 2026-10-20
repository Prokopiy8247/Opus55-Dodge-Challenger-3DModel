using System.Collections.Generic;
using Hellcat.Sim;
using Unity.Mathematics;
using UnityEngine;

namespace Hellcat.Game.World
{
    /// <summary>
    /// A static convex prism (test map, D-081): a convex profile in the local x-y plane (x across, y up) extruded along the
    /// local z axis over <see cref="length"/>, centred. Collides as a convex solid of the soft-body world (face planes,
    /// oriented outward from the centroid) and draws itself with flat-shaded faces. Ramps, jersey-barrier halves, the
    /// speed bump's arc and the bank are prisms.
    /// </summary>
    [RequireComponent(typeof(MeshFilter), typeof(MeshRenderer))]
    public class StaticPrismSource : MonoBehaviour, IStaticGeometrySource
    {
        public string surface = "concrete";
        public Vector2[] profile = new Vector2[0];
        public float length = 1f;

        /// <summary>Vertices (local) and faces (vertex loops whose (v1 - v0) x (v2 - v0) points outward).</summary>
        void Geometry(out List<Vector3> verts, out List<int[]> faces)
        {
            verts = new List<Vector3>();
            faces = new List<int[]>();
            int n = profile.Length;
            float h = 0.5f * length;
            for (int k = 0; k < n; k++) verts.Add(new Vector3(profile[k].x, profile[k].y, -h));
            for (int k = 0; k < n; k++) verts.Add(new Vector3(profile[k].x, profile[k].y, h));
            var back = new int[n];
            var front = new int[n];
            for (int k = 0; k < n; k++)
            {
                back[k] = k;
                front[k] = n + k;
            }
            faces.Add(back);
            faces.Add(front);
            for (int k = 0; k < n; k++)
            {
                int k1 = (k + 1) % n;
                faces.Add(new[] { k, k1, n + k1, n + k });
            }
            Vector3 centroid = Vector3.zero;
            foreach (var v in verts) centroid += v;
            centroid /= verts.Count;
            for (int f = 0; f < faces.Count; f++)
            {
                var loop = faces[f];
                Vector3 c = Vector3.zero;
                foreach (int i in loop) c += verts[i];
                c /= loop.Length;
                Vector3 nrm = Vector3.Cross(verts[loop[1]] - verts[loop[0]], verts[loop[2]] - verts[loop[0]]);
                if (Vector3.Dot(nrm, c - centroid) < 0f)
                    System.Array.Reverse(loop);
            }
        }

        public void AddTo(StaticWorldBuilder builder)
        {
            Geometry(out var verts, out var faces);
            var world = new List<float3>(verts.Count);
            foreach (var v in verts)
                world.Add(transform.TransformPoint(v));
            builder.AddConvexMesh(world, faces, surface, name);
        }

        /// <summary>The render mesh (flat faces); the scene builder calls it so the prism shows in the editor too.</summary>
        public void BuildMesh()
        {
            Geometry(out var verts, out var faces);
            var v = new List<Vector3>();
            var nrm = new List<Vector3>();
            var uv = new List<Vector2>();
            var tri = new List<int>();
            foreach (var loop in faces)
            {
                Vector3 n = Vector3.Cross(verts[loop[1]] - verts[loop[0]], verts[loop[2]] - verts[loop[0]]).normalized;
                int start = v.Count;
                foreach (int i in loop)
                {
                    v.Add(verts[i]);
                    nrm.Add(n);
                    // box projection in metres (asphalt / concrete textures tile per metre)
                    var p = verts[i];
                    uv.Add(Mathf.Abs(n.y) > 0.7f ? new Vector2(p.x, p.z) : Mathf.Abs(n.x) > 0.7f ? new Vector2(p.z, p.y) : new Vector2(p.x, p.y));
                }
                for (int k = 1; k + 1 < loop.Length; k++)
                    tri.AddRange(new[] { start, start + k, start + k + 1 });
            }
            var mesh = new Mesh { name = name + "_Prism" };
            mesh.SetVertices(v);
            mesh.SetNormals(nrm);
            mesh.SetUVs(0, uv);
            mesh.SetTriangles(tri, 0);
            mesh.RecalculateBounds();
            GetComponent<MeshFilter>().sharedMesh = mesh;
        }

        void Awake()
        {
            var mf = GetComponent<MeshFilter>();
            if (mf.sharedMesh == null)
                BuildMesh();
        }
    }
}
