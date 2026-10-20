using System;
using System.Collections.Generic;
using Hellcat.Sim;
using Hellcat.Sim.Data;
using Unity.Mathematics;

namespace Hellcat.Game.Scenario
{
    /// <summary>
    /// Crash metrics of a car body (brief 9, gate G-Crash): the passenger-cell centre of mass (body nodes of the cabin box at
    /// the model pose), parts detached from the cabin (no path of intact beams), the gap to an obstacle and colliding nodes
    /// inside or through it (tunnelling), the crush of the front structure, and the deformation of the body against the
    /// rigid pose of the rear cabin (intrusion into the passenger cell, deepest dent).
    /// </summary>
    public sealed class CrashMetrics
    {
        readonly SoftBodyWorld w;
        readonly SoftBodyWorld.Body b;
        readonly VehicleDef def;
        readonly int[] cabin;
        readonly List<int>[] adj;               // local node -> beam indices (global)
        readonly Dictionary<string, List<int>> partNodes = new Dictionary<string, List<int>>();
        public readonly float cabinMass;

        // rigid reference: the rear cabin (floor, sills, B pillars and behind, below the belt line), which the frontal and
        // side crashes leave undeformed; intrusion is measured from where it puts the model (IIHS-style)
        readonly int[] refNodes;
        readonly double3[] refModel;            // model positions minus their centroid
        readonly double3 refCentroid;
        /// <summary>Structure nodes (body part, not the suspension's moving nodes) for the deformation measures.</summary>
        public readonly int[] structure;
        /// <summary>Named measuring groups of the passenger cell's front (IIHS-like intrusion points), per side.</summary>
        public readonly List<(string name, int[] nodes)> intrusionGroups = new List<(string, int[])>();

        public CrashMetrics(SoftBodyWorld world, int body)
        {
            w = world;
            b = world.bodies[body];
            def = b.def;
            var cab = new List<int>();
            var rf = new List<int>();
            var st = new List<int>();
            for (int i = 0; i < def.nodes.Length; i++)
            {
                var n = def.nodes[i];
                // the cell between the A and C pillars, below the belt line
                if (n.part == "body" && n.p[2] > -1.05f && n.p[2] < 0.85f && n.p[1] < 1.0f && math.abs(n.p[0]) < 0.95f)
                    cab.Add(i);
                if (n.part == "body" && n.p[2] > -1.05f && n.p[2] < 0.05f && n.p[1] < 1.0f && math.abs(n.p[0]) < 0.95f)
                    rf.Add(i);
                if (n.part == "body" && !Moving(n.name))
                    st.Add(i);
                if (!partNodes.TryGetValue(n.part, out var l)) partNodes[n.part] = l = new List<int>();
                l.Add(i);
            }
            cabin = cab.ToArray();
            structure = st.ToArray();
            foreach (int i in cabin)
                cabinMass += def.nodes[i].m;
            refNodes = rf.ToArray();
            refModel = new double3[refNodes.Length];
            for (int k = 0; k < refNodes.Length; k++)
            {
                var p = def.nodes[refNodes[k]].p;
                refModel[k] = new double3(p[0], p[1], p[2]);
                refCentroid += refModel[k];
            }
            refCentroid /= math.max(1, refNodes.Length);
            for (int k = 0; k < refModel.Length; k++)
                refModel[k] -= refCentroid;
            adj = new List<int>[def.nodes.Length];
            for (int i = 0; i < adj.Length; i++) adj[i] = new List<int>();
            for (int j = 0; j < b.beamCount; j++)
            {
                var bd = def.beams[j];
                adj[bd.a].Add(b.beamStart + j);
                adj[bd.b].Add(b.beamStart + j);
            }
            // intrusion points (IIHS-like; model names of tools/blender/hcar/hskel.py): lower and upper door hinge pillar
            // (z 0.80), rocker front (sill station 0), toe pan (front floor), firewall (z 0.975), upper dash (z 0.64),
            // steering column top; left (driver) and right side
            void Group(string name, Func<string, bool> pick)
            {
                foreach (var side in new[] { ("L", -1f), ("R", 1f) })
                {
                    var l = new List<int>();
                    for (int i = 0; i < def.nodes.Length; i++)
                        if (def.nodes[i].part == "body" && pick(def.nodes[i].name) && def.nodes[i].p[0] * side.Item2 >= -0.05f)
                            l.Add(i);
                    if (l.Count > 0) intrusionGroups.Add(($"{name}_{side.Item1}", l.ToArray()));
                }
            }
            Group("hinge_pillar_lower", s => s.StartsWith("hinge0"));
            Group("hinge_pillar_upper", s => s.StartsWith("hinge2"));
            Group("rocker", s => s.StartsWith("sill0_"));
            Group("toe_pan", s => s.StartsWith("floor0"));
            Group("firewall", s => s.StartsWith("fw"));
            Group("dash", s => s.StartsWith("dash"));
            Group("steering_column", s => s.StartsWith("column_top"));
        }

        /// <summary>Body-part nodes that move with the suspension or sit on mounts (anti-roll bar tips, rear links, driveline,
        /// battery): left out of the deformation measures.</summary>
        static bool Moving(string name) =>
            name.StartsWith("arb") || name.StartsWith("RL_link") || name.StartsWith("RR_link") || name.StartsWith("dshaft") ||
            name.StartsWith("diff") || name.StartsWith("batt");

        public int CabinNodes => cabin.Length;
        public string NodeName(int local) => local >= 0 && local < def.nodes.Length ? def.nodes[local].name : "-";

        /// <summary>Mass-weighted centre and velocity of the cabin nodes.</summary>
        public void Cabin(out float3 com, out float3 vel)
        {
            double3 p = double3.zero, v = double3.zero;
            double m = 0;
            foreach (int i in cabin)
            {
                int g = b.nodeStart + i;
                float im = w.invMass[g];
                if (im <= 0f) continue;
                double mi = 1.0 / im;
                p += mi * (double3)w.pos[g];
                v += mi * (double3)w.vel[g];
                m += mi;
            }
            com = (float3)(p / math.max(m, 1e-9));
            vel = (float3)(v / math.max(m, 1e-9));
        }

        /// <summary>Parts with no node connected to the cabin through intact beams.</summary>
        public List<string> Detached()
        {
            var seen = Connected();
            var outList = new List<string>();
            foreach (var kv in partNodes)
            {
                bool any = false;
                foreach (int i in kv.Value)
                    if (seen[i]) { any = true; break; }
                if (!any) outList.Add(kv.Key);
            }
            outList.Sort(string.CompareOrdinal);
            return outList;
        }

        /// <summary>Per node (local index): still connected to the cabin through intact beams.</summary>
        public bool[] Connected()
        {
            var seen = new bool[def.nodes.Length];
            var stack = new Stack<int>();
            foreach (int c in cabin) { seen[c] = true; stack.Push(c); }
            while (stack.Count > 0)
            {
                int i = stack.Pop();
                foreach (int gj in adj[i])
                {
                    if (w.broken[gj] != 0) continue;
                    var bs = w.beams[gj];
                    int o = (bs.a - b.nodeStart) == i ? bs.b - b.nodeStart : bs.a - b.nodeStart;
                    if (!seen[o]) { seen[o] = true; stack.Push(o); }
                }
            }
            return seen;
        }

        /// <summary>Signed distance (m) from the car's nearest static-colliding node to the obstacle's primitives (negative:
        /// inside), and that node; float.MaxValue when no node is within <paramref name="reach"/> of them.</summary>
        public float Gap(int[] prims, float reach, out int nearest)
        {
            nearest = -1;
            float best = float.MaxValue;
            if (prims == null || prims.Length == 0)
                return best;
            float3 lo = float.MaxValue, hi = float.MinValue;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
            {
                if ((w.nodeFlags[i] & NodeFlag.StaticCollision) == 0) continue;
                lo = math.min(lo, w.pos[i]);
                hi = math.max(hi, w.pos[i]);
            }
            foreach (int p in prims)
            {
                var prim = w.prims[p];
                float3 pmin = prim.aabbMin - reach, pmax = prim.aabbMax + reach;
                if (math.any(hi < pmin) || math.any(lo > pmax)) continue;
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                {
                    if ((w.nodeFlags[i] & NodeFlag.StaticCollision) == 0) continue;
                    float3 x = w.pos[i];
                    if (math.any(x < pmin) || math.any(x > pmax)) continue;
                    float s = StaticSdf.Distance(prim, w.planes, x, out _);
                    if (s < best)
                    {
                        best = s;
                        nearest = i - b.nodeStart;
                    }
                }
            }
            return best;
        }

        // plate crossings (TrackPlates): each colliding node's position at the previous check and the plate it came through
        float3[] prevPos;
        int[] throughPrim;

        /// <summary>The obstacle's plates (boxes with one thin axis: a wall, a guardrail beam, a slab): thin axis and the
        /// sign of the side <paramref name="from"/> lies on (-1 at the box's negative face), or axis -1.</summary>
        void Plates(int[] prims, float3 from, out int[] axis, out float[] side)
        {
            axis = new int[prims.Length];
            side = new float[prims.Length];
            for (int k = 0; k < prims.Length; k++)
            {
                var prim = w.prims[prims[k]];
                axis[k] = -1;
                if (prim.type != PrimType.Box) continue;
                float3 h = prim.halfExtents;
                int ax = h.x <= h.y && h.x <= h.z ? 0 : (h.y <= h.z ? 1 : 2);
                float mid = ax == 0 ? math.min(h.y, h.z) : ax == 1 ? math.min(h.x, h.z) : math.min(h.x, h.y);
                if (h[ax] >= 0.6f * mid) continue;
                axis[k] = ax;
                float3 qf = math.rotate(math.conjugate(prim.rotation), from - prim.center);
                side[k] = qf[ax] < 0f ? -1f : 1f;
            }
        }

        /// <summary>Call every chunk near the obstacle: a colliding node whose path since the last call crosses a plate's
        /// far face inside its outline came through the plate; it counts as tunnelled while it stays behind. A node that
        /// went round an edge (over a guardrail's top, past its end) crosses the far face's plane outside the outline.</summary>
        public void TrackPlates(int[] prims, float3 from)
        {
            if (prims == null || prims.Length == 0)
                return;
            if (prevPos == null)
            {
                prevPos = new float3[b.nodeCount];
                throughPrim = new int[b.nodeCount];
                for (int i = 0; i < b.nodeCount; i++)
                {
                    prevPos[i] = w.pos[b.nodeStart + i];
                    throughPrim[i] = -1;
                }
                return;
            }
            Plates(prims, from, out var axis, out var side);
            for (int i = 0; i < b.nodeCount; i++)
            {
                int g = b.nodeStart + i;
                float3 x1 = w.pos[g], x0 = prevPos[i];
                prevPos[i] = x1;
                if ((w.nodeFlags[g] & NodeFlag.StaticCollision) == 0) continue;
                for (int k = 0; k < prims.Length; k++)
                {
                    int ax = axis[k];
                    if (ax < 0) continue;
                    var prim = w.prims[prims[k]];
                    var inv = math.conjugate(prim.rotation);
                    float3 q0 = math.rotate(inv, x0 - prim.center), q1 = math.rotate(inv, x1 - prim.center);
                    float3 h = prim.halfExtents;
                    float a0 = q0[ax] * side[k], a1 = q1[ax] * side[k];   // > -h: in front of the far face
                    if (throughPrim[i] == prims[k] && a1 > -h[ax])
                        throughPrim[i] = -1;                              // back in front: no longer through
                    if (!(a0 > -h[ax] && a1 < -h[ax]))
                        continue;
                    float t = (-h[ax] - a0) / (a1 - a0);
                    float3 qc = q0 + t * (q1 - q0);
                    bool inside = true;
                    for (int a = 0; a < 3; a++)
                        if (a != ax && math.abs(qc[a]) >= h[a]) inside = false;
                    if (inside)
                        throughPrim[i] = prims[k];
                }
            }
        }

        /// <summary>Colliding nodes inside one of the obstacle's primitives deeper than <paramref name="tol"/>, or behind a
        /// plate they came through (<see cref="TrackPlates"/>).</summary>
        public int Tunnelled(int[] prims, float3 from, float tol, List<string> names = null)
        {
            if (prims == null || prims.Length == 0)
                return 0;
            int n = 0;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
            {
                if ((w.nodeFlags[i] & NodeFlag.StaticCollision) == 0) continue;
                float3 x = w.pos[i];
                int via = throughPrim != null ? throughPrim[i - b.nodeStart] : -1;
                float depth = -1f;
                int hit = via;
                if (via < 0)
                    foreach (int p in prims)
                    {
                        var prim = w.prims[p];
                        if (!(math.all(x > prim.aabbMin - 0.01f) && math.all(x < prim.aabbMax + 0.01f))) continue;
                        float s = StaticSdf.Distance(prim, w.planes, x, out _);
                        if (s < -tol)
                        {
                            depth = -s;
                            hit = p;
                            break;
                        }
                    }
                if (via < 0 && depth < 0f) continue;
                n++;
                names?.Add(via >= 0 ? $"{def.nodes[i - b.nodeStart].name} (y {x.y:F2}, through primitive {via})"
                                    : $"{def.nodes[i - b.nodeStart].name} (y {x.y:F2}, {depth:F3} m inside primitive {hit})");
            }
            return n;
        }

        /// <summary>Front of the cabin (the cabin nodes' largest coordinate along <paramref name="f"/> from
        /// <paramref name="o"/>) and of the car (any non-tire node).</summary>
        public void Fronts(float3 o, float3 f, out float cabinFront, out float carFront)
        {
            cabinFront = float.MinValue;
            carFront = float.MinValue;
            foreach (int i in cabin)
                cabinFront = math.max(cabinFront, math.dot(w.pos[b.nodeStart + i] - o, f));
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                if ((w.nodeFlags[i] & NodeFlag.Tire) == 0)
                    carFront = math.max(carFront, math.dot(w.pos[i] - o, f));
        }

        /// <summary>Rigid pose of the rear cabin: where an undeformed car would put model point p, <c>origin + R p</c>
        /// (polar factor of the cross-covariance, Higham's iteration).</summary>
        public double3x3 ReferencePose(out double3 origin)
        {
            double3 c = double3.zero;
            foreach (int i in refNodes)
                c += (double3)w.pos[b.nodeStart + i];
            c /= math.max(1, refNodes.Length);
            var a = double3x3.zero;
            for (int k = 0; k < refNodes.Length; k++)
            {
                double3 q = (double3)w.pos[b.nodeStart + refNodes[k]] - c;
                double3 p = refModel[k];
                a += new double3x3(q.x * p.x, q.x * p.y, q.x * p.z, q.y * p.x, q.y * p.y, q.y * p.z, q.z * p.x, q.z * p.y, q.z * p.z);
            }
            var x = a;
            for (int it = 0; it < 30; it++)
            {
                var next = 0.5 * (x + math.transpose(math.inverse(x)));
                double d = 0;
                for (int r = 0; r < 3; r++)
                    d += math.lengthsq(next[r] - x[r]);
                x = next;
                if (d < 1e-24)
                    break;
            }
            origin = c - math.mul(x, refCentroid);
            return x;
        }

        /// <summary>Displacement of a node (local index) from where the rigid rear cabin puts it.</summary>
        public double3 Displacement(int local, in double3x3 rot, in double3 origin)
        {
            var p = def.nodes[local].p;
            double3 rigid = origin + math.mul(rot, new double3(p[0], p[1], p[2]));
            return (double3)w.pos[b.nodeStart + local] - rigid;
        }

        /// <summary>Largest displacement of the connected structure nodes from the rigid pose (m) and that node.</summary>
        public double MaxDeformation(bool[] connected, out int node)
        {
            var rot = ReferencePose(out double3 origin);
            double best = 0;
            node = -1;
            foreach (int i in structure)
            {
                if (connected != null && !connected[i]) continue;
                double d = math.length(Displacement(i, rot, origin));
                if (d > best) { best = d; node = i; }
            }
            return best;
        }

        /// <summary>Rearward intrusion (m, along the rigid cabin's -forward) of each measuring group: its largest value.</summary>
        public double[] Intrusions()
        {
            var rot = ReferencePose(out double3 origin);
            double3 fwd = math.normalize(math.mul(rot, new double3(0, 0, 1)));
            var res = new double[intrusionGroups.Count];
            for (int g = 0; g < res.Length; g++)
            {
                double best = 0;
                foreach (int i in intrusionGroups[g].nodes)
                    best = math.max(best, -math.dot(Displacement(i, rot, origin), fwd));
                res[g] = best;
            }
            return res;
        }
    }
}
