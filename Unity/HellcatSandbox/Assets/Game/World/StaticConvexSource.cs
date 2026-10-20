using System.Collections.Generic;
using Hellcat.Sim;
using Unity.Mathematics;
using UnityEngine;

namespace Hellcat.Game.World
{
    /// <summary>Convex solid from this object's mesh (each triangle gives a face plane; coplanar planes merged).</summary>
    [RequireComponent(typeof(MeshFilter))]
    public class StaticConvexSource : MonoBehaviour, IStaticGeometrySource
    {
        public string surface = "concrete";

        public void AddTo(StaticWorldBuilder builder)
        {
            var mesh = GetComponent<MeshFilter>().sharedMesh;
            var verts = mesh.vertices;
            var tris = mesh.triangles;
            var world = new List<float3>(verts.Length);
            foreach (var v in verts)
                world.Add(transform.TransformPoint(v));
            var planes = new List<float4>();
            for (int t = 0; t < tris.Length; t += 3)
            {
                // Unity winding is clockwise seen from outside: outward normal = cross(c - a, b - a).
                float3 a = world[tris[t]], b = world[tris[t + 1]], c = world[tris[t + 2]];
                float3 n = math.cross(c - a, b - a);
                float len = math.length(n);
                if (len < 1e-9f)
                    continue;
                n /= len;
                float d = math.dot(n, a);
                bool dup = false;
                foreach (var p in planes)
                    if (math.dot(p.xyz, n) > 0.9999f && math.abs(p.w - d) < 1e-4f)
                    {
                        dup = true;
                        break;
                    }
                if (!dup)
                    planes.Add(new float4(n, d));
            }
            builder.AddConvex(world, planes, surface, name);
        }
    }
}
