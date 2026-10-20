using System;
using Unity.Mathematics;

namespace Hellcat.Sim.Benchmark
{
    /// <summary>Beam kinds handled by the benchmark kernel (mirrors the planned solver).</summary>
    public static class BeamKind
    {
        public const byte Normal = 0;
        public const byte Bounded = 1;
        public const byte Support = 2;
    }

    /// <summary>Global simulation parameters, SI units (Unity axes: +Y up).</summary>
    [Serializable]
    public struct SimParams
    {
        public float dt;
        public float3 gravity;
        public float contactBias;       // contact force starts this far in front of a surface (m)
        public float contactStiffness;  // penalty stiffness per node (N/m)
        public float contactDamping;    // penalty damping per node (N/(m/s))
        public float friction;          // Coulomb coefficient
        public float wallX;             // static wall plane at x = wallX, facing -X
    }

    /// <summary>Synthetic structure for the P0 micro-benchmark.</summary>
    [Serializable]
    public struct LatticeConfig
    {
        public int3 dims;               // nodes along x (length), y (height), z (width)
        public float spacing;           // m
        public int targetBeams;         // exact beam count to generate
        public float totalMass;         // kg, spread evenly over the nodes
        public float spring;            // N/m
        public float damp;              // N/(m/s)
        public float deform;            // N, initial plastic threshold
        public float hardening;         // N/m, threshold increase per metre of plastic flow
        public float strength;          // N, break threshold
        public float lift;              // initial height of the lowest node layer (m)
        public float3 initialVelocity;  // m/s
        public bool shuffle;            // random node/beam order = worst-case memory locality
        public uint seed;
    }
}
