using System;
using System.Collections.Generic;
using Unity.Collections;
using Unity.Mathematics;
using Random = Unity.Mathematics.Random;

namespace Hellcat.Sim.Benchmark
{
    /// <summary>
    /// Synthetic structure for the P0 micro-benchmark: a braced, car-sized box lattice with an exact
    /// beam count (all axial edges plus evenly selected face diagonals), stored as structure-of-arrays
    /// NativeArrays. Optionally shuffles node and beam order to model worst-case memory locality.
    /// </summary>
    public sealed class BenchmarkWorld : IDisposable
    {
        public readonly int nodeCount;
        public readonly int beamCount;
        public readonly float maxOmegaDt;
        public readonly int omegaViolations;   // nodes with omega * dt >= 0.5
        public readonly int maxValence;

        // Static data.
        public NativeArray<float> invMass;
        public NativeArray<int2> beamNodes;
        public NativeArray<float4> beamCoef;
        public NativeArray<float2> beamBounds;
        public NativeArray<byte> beamKind;
        public NativeArray<int> adjStart;
        public NativeArray<int> adjCode;       // (beam << 1) | (1 when the node is the beam's end b)

        // Working state.
        public NativeArray<float3> pos;
        public NativeArray<float3> vel;
        public NativeArray<float3> force;
        public NativeArray<float3> beamForce;
        public NativeArray<float> restLength;
        public NativeArray<float> yieldForce;  // current deform threshold (grows with plastic flow)
        public NativeArray<byte> broken;
        public NativeArray<int> burstFlag;

        // Initial state for Reset().
        NativeArray<float3> pos0;
        NativeArray<float3> vel0;
        NativeArray<float> rest0;
        NativeArray<float> yield0;

        public BenchmarkWorld(LatticeConfig c, float dt)
        {
            int nx = c.dims.x, ny = c.dims.y, nz = c.dims.z;
            nodeCount = nx * ny * nz;
            var rng = new Random(c.seed == 0 ? 1u : c.seed);

            // Lattice id -> storage index.
            var perm = new int[nodeCount];
            for (int i = 0; i < nodeCount; i++)
                perm[i] = i;
            if (c.shuffle)
                Shuffle(perm, ref rng);
            int Id(int x, int y, int z) => perm[x + nx * (y + ny * z)];

            var positions = new float3[nodeCount];
            float halfWidth = 0.5f * (nz - 1) * c.spacing;
            for (int z = 0; z < nz; z++)
                for (int y = 0; y < ny; y++)
                    for (int x = 0; x < nx; x++)
                        positions[Id(x, y, z)] = new float3(x * c.spacing, c.lift + y * c.spacing, z * c.spacing - halfWidth);

            // All axial edges, then one diagonal per lattice face with checkerboard orientation.
            var axial = new List<int2>();
            var diagonals = new List<int2>();
            for (int z = 0; z < nz; z++)
                for (int y = 0; y < ny; y++)
                    for (int x = 0; x < nx; x++)
                    {
                        bool even = ((x + y + z) & 1) == 0;
                        if (x + 1 < nx) axial.Add(new int2(Id(x, y, z), Id(x + 1, y, z)));
                        if (y + 1 < ny) axial.Add(new int2(Id(x, y, z), Id(x, y + 1, z)));
                        if (z + 1 < nz) axial.Add(new int2(Id(x, y, z), Id(x, y, z + 1)));
                        if (x + 1 < nx && y + 1 < ny)
                            diagonals.Add(even ? new int2(Id(x, y, z), Id(x + 1, y + 1, z)) : new int2(Id(x + 1, y, z), Id(x, y + 1, z)));
                        if (x + 1 < nx && z + 1 < nz)
                            diagonals.Add(even ? new int2(Id(x, y, z), Id(x + 1, y, z + 1)) : new int2(Id(x + 1, y, z), Id(x, y, z + 1)));
                        if (y + 1 < ny && z + 1 < nz)
                            diagonals.Add(even ? new int2(Id(x, y, z), Id(x, y + 1, z + 1)) : new int2(Id(x, y + 1, z), Id(x, y, z + 1)));
                    }
            int need = c.targetBeams - axial.Count;
            if (need < 0 || need > diagonals.Count)
                throw new ArgumentException($"targetBeams {c.targetBeams} not reachable: {axial.Count} axial + up to {diagonals.Count} diagonals");
            var beams = new List<int2>(axial);
            for (int i = 0; i < need; i++)
                beams.Add(diagonals[(int)((long)i * diagonals.Count / need)]);
            if (c.shuffle)
                Shuffle(beams, ref rng);
            beamCount = beams.Count;

            var a = Allocator.Persistent;
            invMass = new NativeArray<float>(nodeCount, a);
            pos0 = new NativeArray<float3>(positions, a);
            vel0 = new NativeArray<float3>(nodeCount, a);
            beamNodes = new NativeArray<int2>(beams.ToArray(), a);
            beamCoef = new NativeArray<float4>(beamCount, a);
            beamBounds = new NativeArray<float2>(beamCount, a);
            beamKind = new NativeArray<byte>(beamCount, a);
            rest0 = new NativeArray<float>(beamCount, a);
            yield0 = new NativeArray<float>(beamCount, a);

            float nodeInvMass = nodeCount / c.totalMass;
            for (int i = 0; i < nodeCount; i++)
            {
                invMass[i] = nodeInvMass;
                vel0[i] = c.initialVelocity;
            }
            for (int b = 0; b < beamCount; b++)
            {
                int2 n = beamNodes[b];
                rest0[b] = math.distance(positions[n.x], positions[n.y]);
                yield0[b] = c.deform;
                beamCoef[b] = new float4(c.spring, c.damp, c.hardening, c.strength);
                beamBounds[b] = new float2(0.2f, 0.2f);
                beamKind[b] = BeamKind.Normal;
            }

            // Node -> beam adjacency (CSR), filled in beam order so every node sums its forces in
            // the same order as the single-threaded scatter.
            var counts = new int[nodeCount];
            for (int b = 0; b < beamCount; b++)
            {
                counts[beamNodes[b].x]++;
                counts[beamNodes[b].y]++;
            }
            adjStart = new NativeArray<int>(nodeCount + 1, a);
            for (int i = 0; i < nodeCount; i++)
                adjStart[i + 1] = adjStart[i] + counts[i];
            adjCode = new NativeArray<int>(2 * beamCount, a);
            var fill = new int[nodeCount];
            for (int b = 0; b < beamCount; b++)
            {
                int2 n = beamNodes[b];
                adjCode[adjStart[n.x] + fill[n.x]++] = b << 1;
                adjCode[adjStart[n.y] + fill[n.y]++] = (b << 1) | 1;
            }

            // Explicit-integration stability guideline from the brief: omega * dt < 0.5.
            for (int i = 0; i < nodeCount; i++)
            {
                float sumK = 0f;
                for (int k = adjStart[i]; k < adjStart[i + 1]; k++)
                    sumK += beamCoef[adjCode[k] >> 1].x;
                float omegaDt = math.sqrt(sumK * invMass[i]) * dt;
                maxOmegaDt = math.max(maxOmegaDt, omegaDt);
                if (omegaDt >= 0.5f)
                    omegaViolations++;
                maxValence = math.max(maxValence, counts[i]);
            }

            pos = new NativeArray<float3>(nodeCount, a);
            vel = new NativeArray<float3>(nodeCount, a);
            force = new NativeArray<float3>(nodeCount, a);
            beamForce = new NativeArray<float3>(beamCount, a);
            restLength = new NativeArray<float>(beamCount, a);
            yieldForce = new NativeArray<float>(beamCount, a);
            broken = new NativeArray<byte>(beamCount, a);
            burstFlag = new NativeArray<int>(1, a);
            Reset();
        }

        public void Reset()
        {
            pos.CopyFrom(pos0);
            vel.CopyFrom(vel0);
            restLength.CopyFrom(rest0);
            yieldForce.CopyFrom(yield0);
            for (int i = 0; i < nodeCount; i++)
                force[i] = float3.zero;
            for (int b = 0; b < beamCount; b++)
            {
                broken[b] = 0;
                beamForce[b] = float3.zero;
            }
            burstFlag[0] = -1;
        }

        /// <summary>FNV-1a hash over the raw bits of all positions and velocities.</summary>
        public string StateHash()
        {
            ulong h = 14695981039346656037UL;
            void Mix(uint v)
            {
                for (int i = 0; i < 4; i++)
                {
                    h ^= (v >> (8 * i)) & 0xFFu;
                    h *= 1099511628211UL;
                }
            }
            for (int i = 0; i < nodeCount; i++)
            {
                uint3 p = math.asuint(pos[i]);
                uint3 v = math.asuint(vel[i]);
                Mix(p.x); Mix(p.y); Mix(p.z);
                Mix(v.x); Mix(v.y); Mix(v.z);
            }
            return h.ToString("x16");
        }

        public int CountBroken()
        {
            int n = 0;
            for (int b = 0; b < beamCount; b++)
                n += broken[b] != 0 ? 1 : 0;
            return n;
        }

        public int CountPlastic()
        {
            int n = 0;
            for (int b = 0; b < beamCount; b++)
                n += math.abs(restLength[b] - rest0[b]) > 1e-6f ? 1 : 0;
            return n;
        }

        public void Dispose()
        {
            invMass.Dispose(); beamNodes.Dispose(); beamCoef.Dispose(); beamBounds.Dispose(); beamKind.Dispose();
            adjStart.Dispose(); adjCode.Dispose();
            pos.Dispose(); vel.Dispose(); force.Dispose(); beamForce.Dispose();
            restLength.Dispose(); yieldForce.Dispose(); broken.Dispose(); burstFlag.Dispose();
            pos0.Dispose(); vel0.Dispose(); rest0.Dispose(); yield0.Dispose();
        }

        static void Shuffle<T>(IList<T> list, ref Random rng)
        {
            for (int i = list.Count - 1; i > 0; i--)
            {
                int j = rng.NextInt(0, i + 1);
                (list[i], list[j]) = (list[j], list[i]);
            }
        }
    }
}
