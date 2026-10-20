using System.Runtime.CompilerServices;
using Unity.Burst;
using Unity.Collections;
using Unity.Collections.LowLevel.Unsafe;
using Unity.Jobs;
using Unity.Mathematics;

namespace Hellcat.Sim
{
    // Node-vs-triangle contact between bodies (and self-collision between parts), brief 4.4:
    //   CollisionGridPhase (serial, every rebuildEvery substeps): triangles of bodies that are near another
    //     colliding body (or have self-collision nodes) go into a uniform grid hashed into buckets; each
    //     triangle's box is inflated by the contact zone plus the motion until the next rebuild, so a node only
    //     looks at its own cell. Entries are filled in triangle order: deterministic.
    //   NodeContactJob (parallel over nodes): deepest triangle in the zone; penalty with the effective mass of
    //     node and triangle point, approach damping, regularised Coulomb friction. The side the node came from
    //     is remembered (also across neighbouring triangles with similar normals) and the zone is widened by
    //     the approach distance of one step (speculative), so a node cannot skip through a triangle.
    //   ContactScatterJob (serial): node force, -w * force onto the triangle nodes, deferred impulses.
    //   PostContactJob (serial, after integration): a node that still ended up behind its triangle's plane is
    //     put back on it and its inward relative velocity removed; the reaction impulse is applied to the
    //     triangle in the next substep (momentum conserving).

    public static class CollisionGrid
    {
        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public static ulong Key(int3 c)
        {
            const int off = 1 << 20;
            return ((ulong)(uint)(c.x + off) & 0x1FFFFFUL) | (((ulong)(uint)(c.y + off) & 0x1FFFFFUL) << 21) |
                   (((ulong)(uint)(c.z + off) & 0x1FFFFFUL) << 42);
        }

        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public static int Bucket(ulong key, ulong mask) => (int)(((key * 0x9E3779B97F4A7C15UL) >> 29) & mask);
    }

    public struct CollisionGridPhase
    {
        public const int MaxCellsPerTri = 64;
        public float dt;
        public CollisionParams prm;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> pos;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> vel;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int2> bodyNodes;   // start, count
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> bodyColl;     // bit 0: has Collision nodes, bit 1: SelfCollision
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<CollTri> tris;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<byte> groupDone;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> bodyLo, bodyHi;
        [NativeDisableContainerSafetyRestriction] public NativeArray<byte> bodyInsert;
        [NativeDisableContainerSafetyRestriction] public NativeArray<byte> bodyOthers;   // another body's triangles are near
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int2> bodySelf;     // start, count in selfNodes
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> selfNodes;     // self-colliding nodes by body
        [NativeDisableContainerSafetyRestriction] public NativeArray<int> bucketStart;  // buckets + 1
        [NativeDisableContainerSafetyRestriction] public NativeArray<int> bucketFill;
        [NativeDisableContainerSafetyRestriction] public NativeArray<ulong> entryKey;
        [NativeDisableContainerSafetyRestriction] public NativeArray<int> entryTri;
        [NativeDisableContainerSafetyRestriction] public NativeArray<int> counters;     // CollisionCounter

        public void Execute()
        {
            int nb = bodyNodes.Length;
            float vmax2 = 0f;
            for (int b = 0; b < nb; b++)
            {
                float3 lo = new float3(float.MaxValue), hi = new float3(float.MinValue);
                int2 r = bodyNodes[b];
                for (int i = r.x; i < r.x + r.y; i++)
                {
                    lo = math.min(lo, pos[i]);
                    hi = math.max(hi, pos[i]);
                    vmax2 = math.max(vmax2, math.lengthsq(vel[i]));
                }
                bodyLo[b] = lo;
                bodyHi[b] = hi;
            }
            float vmax = math.min(math.sqrt(vmax2), 400f);
            float margin = prm.frontBias + vmax * dt * (2f * prm.rebuildEvery + 1f) + 0.01f;
            int any = 0;
            // 1: all of the body's triangles (another colliding body is near); 2: only those near its own self-colliding
            // nodes (D-058: a car's few self-colliding parts must not make every substep hash all its triangles)
            for (int b = 0; b < nb; b++)
            {
                byte ins = 0;
                for (int c = 0; c < nb; c++)
                {
                    if (c == b || (bodyColl[c] & 1) == 0)
                        continue;
                    if (math.all(bodyLo[b] - margin <= bodyHi[c] + margin) && math.all(bodyLo[c] - margin <= bodyHi[b] + margin))
                    {
                        ins = 1;
                        break;
                    }
                }
                if (ins == 0 && (bodyColl[b] & 2) != 0)
                    ins = 2;
                bodyInsert[b] = ins;
                any |= ins;
            }
            // per body: is another body inserted near it? Without one, its nodes that only collide with other bodies skip
            // the grid (a car with a few self-colliding parts inserts its own triangles; its 1,500 ordinary colliding
            // nodes would otherwise walk them every substep for nothing, D-058)
            for (int b = 0; b < nb; b++)
            {
                byte o = 0;
                for (int c = 0; c < nb && o == 0; c++)
                    if (c != b && bodyInsert[c] != 0 &&
                        math.all(bodyLo[b] - margin <= bodyHi[c] + margin) && math.all(bodyLo[c] - margin <= bodyHi[b] + margin))
                        o = 1;
                bodyOthers[b] = o;
            }
            counters[CollisionCounter.Rebuilds] = counters[CollisionCounter.Rebuilds] + 1;
            int buckets = bucketFill.Length;
            if (any == 0)
            {
                counters[CollisionCounter.Entries] = 0;
                counters[CollisionCounter.InsertedTris] = 0;
                return;
            }

            float inv = 1f / prm.cellSize;
            ulong mask = prm.bucketMask;
            for (int k = 0; k < buckets; k++)
                bucketFill[k] = 0;
            int inserted = 0;
            for (int t = 0; t < tris.Length; t++)
            {
                CollTri tr = tris[t];
                if (!Wanted(tr, margin))
                    continue;
                CellRange(tr, margin, inv, out int3 c0, out int3 c1);
                int cells = 0;
                for (int x = c0.x; x <= c1.x; x++)
                for (int y = c0.y; y <= c1.y; y++)
                for (int z = c0.z; z <= c1.z; z++)
                {
                    if (++cells > MaxCellsPerTri)
                        break;
                    int bk = CollisionGrid.Bucket(CollisionGrid.Key(new int3(x, y, z)), mask);
                    bucketFill[bk] = bucketFill[bk] + 1;
                }
                inserted++;
            }
            int total = 0;
            for (int k = 0; k < buckets; k++)
            {
                bucketStart[k] = total;
                total += bucketFill[k];
                bucketFill[k] = 0;
            }
            bucketStart[buckets] = total;
            int cap = entryKey.Length;
            int overflow = 0;
            for (int t = 0; t < tris.Length; t++)
            {
                CollTri tr = tris[t];
                if (!Wanted(tr, margin))
                    continue;
                CellRange(tr, margin, inv, out int3 c0, out int3 c1);
                int cells = 0;
                for (int x = c0.x; x <= c1.x; x++)
                for (int y = c0.y; y <= c1.y; y++)
                for (int z = c0.z; z <= c1.z; z++)
                {
                    if (++cells > MaxCellsPerTri)
                        break;
                    ulong key = CollisionGrid.Key(new int3(x, y, z));
                    int bk = CollisionGrid.Bucket(key, mask);
                    int e = bucketStart[bk] + bucketFill[bk];
                    bucketFill[bk] = bucketFill[bk] + 1;
                    if (e < cap)
                    {
                        entryKey[e] = key;
                        entryTri[e] = t;
                    }
                    else
                    {
                        overflow++;
                    }
                }
            }
            if (overflow > 0)
            {
                // Out of capacity: keep the table consistent (entries past the end are dropped).
                for (int k = 0; k <= buckets; k++)
                    bucketStart[k] = math.min(bucketStart[k], cap);
                counters[CollisionCounter.Overflow] = counters[CollisionCounter.Overflow] + overflow;
            }
            counters[CollisionCounter.Entries] = math.min(total, cap);
            counters[CollisionCounter.InsertedTris] = inserted;
        }

        /// <summary>Insert this triangle? Its body must be inserted, the triangle not broken off, and for a body inserted
        /// only for its own self-colliding nodes one of them must lie within the margin of the triangle's box.</summary>
        bool Wanted(in CollTri tr, float margin)
        {
            byte ins = bodyInsert[tr.body];
            if (ins == 0 || (tr.breakGroup >= 0 && groupDone[tr.breakGroup] != 0))
                return false;
            if (ins == 1)
                return true;
            float3 a = pos[tr.a], b = pos[tr.b], c = pos[tr.c];
            float3 lo = math.min(a, math.min(b, c)) - margin, hi = math.max(a, math.max(b, c)) + margin;
            int2 r = bodySelf[tr.body];
            for (int k = r.x; k < r.x + r.y; k++)
            {
                float3 p = pos[selfNodes[k]];
                if (math.all(p >= lo) && math.all(p <= hi))
                    return true;
            }
            return false;
        }

        void CellRange(in CollTri tr, float margin, float inv, out int3 c0, out int3 c1)
        {
            float3 a = pos[tr.a], b = pos[tr.b], c = pos[tr.c];
            float3 lo = math.min(a, math.min(b, c)) - margin;
            float3 hi = math.max(a, math.max(b, c)) + margin;
            c0 = (int3)math.floor(lo * inv);
            c1 = (int3)math.floor(hi * inv);
        }
    }

    [BurstCompile(FloatMode = FloatMode.Strict, DisableSafetyChecks = true)]
    public struct NodeContactJob : IJobParallelFor
    {
        public float dt;
        public CollisionParams prm;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> pos;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> vel;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float> invMass;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> flags;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> nodeBody;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> nodePart;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> nodeCmat;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<ContactMaterial> cmats;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<CollTri> tris;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<byte> groupDone;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> bucketStart;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<ulong> entryKey;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> entryTri;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> counters;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<byte> bodyOthers;
        [NativeDisableContainerSafetyRestriction] public NativeArray<NodeContact> contacts;
        [NativeDisableContainerSafetyRestriction] public NativeArray<int> lastTri;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float> lastSide;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> lastNormal;
        [NativeDisableContainerSafetyRestriction] public NativeArray<int> lastBody;
        [NativeDisableContainerSafetyRestriction] public NativeArray<int> tested;       // candidates per node (stats)
        public int tailNodeStart;                                                     // sleeping debris (D-098)
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> tailSleep;

        public void Execute(int i)
        {
            var rec = new NodeContact { tri = -1 };
            int fl = flags[i];
            if (counters[CollisionCounter.Entries] == 0 || (fl & (NodeFlag.Collision | NodeFlag.SelfCollision)) == 0 || invMass[i] <= 0f ||
                ((fl & NodeFlag.SelfCollision) == 0 && bodyOthers[nodeBody[i]] == 0) || (i >= tailNodeStart && tailSleep[0] != 0))
            {
                contacts[i] = rec;
                lastTri[i] = -1;
                tested[i] = 0;
                return;
            }
            float3 p = pos[i], v = vel[i];
            int body = nodeBody[i], part = nodePart[i];
            ulong key = CollisionGrid.Key((int3)math.floor(p * (1f / prm.cellSize)));
            int bk = CollisionGrid.Bucket(key, prm.bucketMask);
            int prevTri = lastTri[i], prevBody = lastBody[i];
            float prevSide = lastSide[i];
            float3 prevN = lastNormal[i];

            int best = -1, nTested = 0;
            float bestDepth = float.MinValue, bestSd = 0f, bestSide = 1f, bestZone = 0f, bestVn = 0f;
            float3 bestN = float3.zero, bestW = float3.zero, bestVt = float3.zero;
            for (int e = bucketStart[bk]; e < bucketStart[bk + 1]; e++)
            {
                if (entryKey[e] != key)
                    continue;
                int t = entryTri[e];
                CollTri tr = tris[t];
                if (tr.body == body)
                {
                    if ((fl & NodeFlag.SelfCollision) == 0 || tr.part == part)
                        continue;
                }
                else if ((fl & NodeFlag.Collision) == 0)
                {
                    continue;
                }
                if (tr.a == i || tr.b == i || tr.c == i || (tr.breakGroup >= 0 && groupDone[tr.breakGroup] != 0))
                    continue;
                nTested++;
                if (!TriangleKernel.Project(p, pos[tr.a], pos[tr.b], pos[tr.c], out float s, out float3 n, out float3 bary) ||
                    !TriangleKernel.Inside(bary, prm.footprintTolerance))
                    continue;
                float side;
                if (t == prevTri || (prevTri >= 0 && prevBody == tr.body && math.dot(prevN, n) > 0.5f))
                    side = prevSide;
                else
                    side = s >= 0f ? 1f : -1f;
                float sd = s * side;
                if (sd < -0.05f)
                    continue; // far on the other side: not a contact of this side (stale memory)
                float zone = side > 0f ? prm.frontBias : prm.backBias;
                float3 w = TriangleKernel.Weights(bary);
                float3 vt = w.x * vel[tr.a] + w.y * vel[tr.b] + w.z * vel[tr.c];
                float vn = math.dot(v - vt, n) * side; // < 0: approaching
                if (sd >= zone + math.max(0f, -vn) * dt)
                    continue;
                float depth = zone - sd;
                if (depth > bestDepth)
                {
                    bestDepth = depth;
                    best = t;
                    bestSd = sd;
                    bestSide = side;
                    bestZone = zone;
                    bestN = n;
                    bestW = w;
                    bestVt = vt;
                    bestVn = vn;
                }
            }
            tested[i] = nTested;
            if (best < 0)
            {
                contacts[i] = rec;
                lastTri[i] = -1;
                return;
            }

            CollTri bt = tris[best];
            float invTri = bestW.x * bestW.x * invMass[bt.a] + bestW.y * bestW.y * invMass[bt.b] + bestW.z * bestW.z * invMass[bt.c];
            float mEff = 1f / (invMass[i] + invTri);
            float pen = bestZone - bestSd;
            float3 nS = bestN * bestSide;
            float fn = 0f;
            float3 force = float3.zero;
            if (pen > 0f)
            {
                float kc = prm.alpha * mEff / (dt * dt);
                float cc = 2f * prm.zeta * mEff * math.sqrt(prm.alpha) / dt;
                fn = math.max(0f, kc * pen - cc * bestVn);
                float3 vrel = v - bestVt;
                float3 vtan = vrel - math.dot(vrel, nS) * nS;
                float vtl = math.length(vtan);
                float mu = cmats[nodeCmat[i]].muSliding * prm.frictionScale;
                float ft = math.min(mu * fn, 0.5f * mEff / dt * vtl); // Coulomb, viscous below the stable slope
                force = nS * fn - (vtl > 1e-9f ? vtan * (ft / vtl) : float3.zero);
            }
            rec.tri = best;
            rec.w = bestW;
            rec.force = force;
            rec.fn = fn;
            rec.side = bestSide;
            contacts[i] = rec;
            lastTri[i] = best;
            lastSide[i] = bestSide;
            lastNormal[i] = bestN;
            lastBody[i] = bt.body;
        }
    }

    [BurstCompile(FloatMode = FloatMode.Strict, DisableSafetyChecks = true)]
    public struct ContactScatterJob : IJob
    {
        public float dt;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<CollTri> tris;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<NodeContact> contacts;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> tested;
        [NativeDisableContainerSafetyRestriction] public NativeArray<NodeImpulse> deferred;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> dynForce;
        [NativeDisableContainerSafetyRestriction] public NativeArray<int> counters;

        public void Execute()
        {
            int n = dynForce.Length;
            for (int i = 0; i < n; i++)
                dynForce[i] = float3.zero;
            int touching = 0, cand = 0;
            for (int i = 0; i < n; i++)
            {
                cand += tested[i];
                NodeContact c = contacts[i];
                if (c.tri >= 0 && c.fn > 0f)
                {
                    touching++;
                    CollTri t = tris[c.tri];
                    dynForce[i] += c.force;
                    dynForce[t.a] -= c.w.x * c.force;
                    dynForce[t.b] -= c.w.y * c.force;
                    dynForce[t.c] -= c.w.z * c.force;
                }
                NodeImpulse d = deferred[i];
                if (d.tri >= 0)
                {
                    CollTri t = tris[d.tri];
                    float3 f = d.impulse * (1f / dt);
                    dynForce[t.a] -= d.w.x * f;
                    dynForce[t.b] -= d.w.y * f;
                    dynForce[t.c] -= d.w.z * f;
                    d.tri = -1;
                    deferred[i] = d;
                }
            }
            counters[CollisionCounter.Contacts] = touching;
            counters[CollisionCounter.Candidates] = cand;
        }
    }

    [BurstCompile(FloatMode = FloatMode.Strict, DisableSafetyChecks = true)]
    public struct PostContactJob : IJob
    {
        public CollisionParams prm;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> pos;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> vel;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float> invMass;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<CollTri> tris;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<NodeContact> contacts;
        [NativeDisableContainerSafetyRestriction] public NativeArray<NodeImpulse> deferred;
        [NativeDisableContainerSafetyRestriction] public NativeArray<int> counters;

        public void Execute()
        {
            int n = pos.Length;
            int proj = 0;
            for (int i = 0; i < n; i++)
            {
                NodeContact c = contacts[i];
                if (c.tri < 0)
                    continue;
                CollTri t = tris[c.tri];
                float3 p = pos[i];
                if (!TriangleKernel.Project(p, pos[t.a], pos[t.b], pos[t.c], out float s, out float3 nrm, out float3 bary) ||
                    !TriangleKernel.Inside(bary, prm.footprintTolerance))
                    continue;
                float sd = s * c.side;
                if (sd >= 0f)
                    continue;
                float3 nS = nrm * c.side;
                pos[i] = p - nS * (sd - 1e-4f);
                float3 w = TriangleKernel.Weights(bary);
                float3 vt = w.x * vel[t.a] + w.y * vel[t.b] + w.z * vel[t.c];
                float3 v = vel[i];
                float vn = math.dot(v - vt, nS);
                if (vn < 0f)
                {
                    // perfectly inelastic impulse of the pair: J = mEff (-vn), mEff = 1 / (1/m_node + sum w^2 / m_k), so node
                    // and triangle point end with the same normal velocity. Stopping the node as if the triangle were fixed
                    // and handing the triangle m_node |vn| shot a tire's 0.3 kg tread nodes to 400 m/s when the 8.5 kg
                    // radiator nodes (self-colliding, D-058) struck the wheel at 120 km/h (D-061).
                    float imTri = w.x * w.x * invMass[t.a] + w.y * w.y * invMass[t.b] + w.z * w.z * invMass[t.c];
                    float imSum = invMass[i] + imTri;
                    float j = imSum > 0f ? -vn / imSum : 0f;
                    vel[i] = v + (j * invMass[i]) * nS;
                    deferred[i] = new NodeImpulse { tri = c.tri, w = w, impulse = j * nS };
                }
                proj++;
            }
            if (proj > 0)
                counters[CollisionCounter.Projections] = counters[CollisionCounter.Projections] + proj;
        }
    }
}
