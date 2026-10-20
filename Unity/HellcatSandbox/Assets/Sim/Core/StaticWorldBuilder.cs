using System;
using System.Collections.Generic;
using Unity.Mathematics;

namespace Hellcat.Sim
{
    /// <summary>
    /// Collects the static colliders of a map (ground, walls, poles, barriers, ramps) before the
    /// world is built. Surfaces are referenced by name and resolved against the world parameters.
    /// </summary>
    public sealed class StaticWorldBuilder
    {
        public readonly List<StaticPrimitive> prims = new List<StaticPrimitive>();
        public readonly List<float4> planes = new List<float4>();
        public readonly List<string> primSurfaceNames = new List<string>();
        public readonly List<string> primNames = new List<string>();

        static readonly float3 Huge = new float3(1e9f);

        public int AddPlane(float3 normal, float offset, string surface, string name = "ground")
        {
            var p = new StaticPrimitive
            {
                type = PrimType.Plane,
                axis = math.normalize(normal),
                halfExtents = new float3(offset, 0f, 0f),
                rotation = quaternion.identity,
                aabbMin = -Huge,
                aabbMax = Huge,
            };
            return Add(p, surface, name);
        }

        public int AddBox(float3 center, quaternion rotation, float3 halfExtents, string surface, string name)
        {
            var p = new StaticPrimitive
            {
                type = PrimType.Box,
                center = center,
                rotation = rotation,
                halfExtents = halfExtents,
            };
            BoundsOfBox(center, rotation, halfExtents, out p.aabbMin, out p.aabbMax);
            return Add(p, surface, name);
        }

        public int AddCylinder(float3 center, quaternion rotation, float radius, float halfHeight, string surface, string name)
        {
            var p = new StaticPrimitive
            {
                type = PrimType.Cylinder,
                center = center,
                rotation = rotation,
                halfExtents = new float3(radius, halfHeight, radius),
            };
            BoundsOfBox(center, rotation, new float3(radius, halfHeight, radius), out p.aabbMin, out p.aabbMax);
            return Add(p, surface, name);
        }

        /// <summary>Convex solid from its vertices and outward face planes (normal, offset) in world space.</summary>
        public int AddConvex(IReadOnlyList<float3> vertices, IReadOnlyList<float4> facePlanes, string surface, string name)
        {
            var p = new StaticPrimitive { type = PrimType.Convex, rotation = quaternion.identity };
            p.planeStart = planes.Count;
            p.planeCount = facePlanes.Count;
            foreach (var pl in facePlanes)
                planes.Add(pl);
            float3 lo = new float3(float.MaxValue), hi = new float3(float.MinValue);
            foreach (var v in vertices)
            {
                lo = math.min(lo, v);
                hi = math.max(hi, v);
            }
            p.aabbMin = lo;
            p.aabbMax = hi;
            p.center = 0.5f * (lo + hi);
            return Add(p, surface, name);
        }

        /// <summary>Convex solid from vertices and faces given as vertex index loops (counter-clockwise seen from outside).</summary>
        public int AddConvexMesh(IReadOnlyList<float3> vertices, IReadOnlyList<int[]> faces, string surface, string name)
        {
            var pls = new List<float4>();
            foreach (var f in faces)
            {
                float3 a = vertices[f[0]], b = vertices[f[1]], c = vertices[f[2]];
                float3 n = math.normalize(math.cross(b - a, c - a));
                pls.Add(new float4(n, math.dot(n, a)));
            }
            return AddConvex(vertices, pls, surface, name);
        }

        int Add(StaticPrimitive p, string surface, string name)
        {
            prims.Add(p);
            primSurfaceNames.Add(surface);
            primNames.Add(name);
            return prims.Count - 1;
        }

        static void BoundsOfBox(float3 c, quaternion r, float3 h, out float3 lo, out float3 hi)
        {
            float3x3 m = new float3x3(r);
            float3 e = math.abs(m.c0) * h.x + math.abs(m.c1) * h.y + math.abs(m.c2) * h.z;
            lo = c - e;
            hi = c + e;
        }

        public void ResolveSurfaces(Func<string, int> surfaceIndex)
        {
            for (int i = 0; i < prims.Count; i++)
            {
                var p = prims[i];
                p.surface = surfaceIndex(primSurfaceNames[i]);
                prims[i] = p;
            }
        }
    }
}
