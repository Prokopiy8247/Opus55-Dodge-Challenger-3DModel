using Unity.Burst;
using Unity.Collections;
using Unity.Jobs;
using Unity.Mathematics;

namespace Hellcat.Sim.Benchmark
{
    static class BurstProbe
    {
        /// <summary>Clears the flag only when running as managed code; Burst removes this call.</summary>
        [BurstDiscard]
        public static void MarkManaged(ref int flag)
        {
            flag = 0;
        }
    }

    /// <summary>
    /// Single-threaded variant: runs a whole frame of substeps inside one job and scatters beam
    /// forces directly into the node force buffer.
    /// </summary>
    [BurstCompile(CompileSynchronously = true, DisableSafetyChecks = true)]
    public struct SingleThreadStepJob : IJob
    {
        public int substeps;
        public SimParams prm;
        public NativeArray<float3> pos;
        public NativeArray<float3> vel;
        public NativeArray<float3> force;
        [ReadOnly] public NativeArray<float> invMass;
        [ReadOnly] public NativeArray<int2> beamNodes;
        [ReadOnly] public NativeArray<float4> beamCoef;
        [ReadOnly] public NativeArray<float2> beamBounds;
        [ReadOnly] public NativeArray<byte> beamKind;
        public NativeArray<float> restLength;
        public NativeArray<float> yieldForce;
        public NativeArray<byte> broken;
        public NativeArray<int> burstFlag;

        public void Execute()
        {
            int flag = 1;
            BurstProbe.MarkManaged(ref flag);
            burstFlag[0] = flag;

            int beamCount = beamNodes.Length;
            int nodeCount = pos.Length;
            for (int s = 0; s < substeps; s++)
            {
                for (int b = 0; b < beamCount; b++)
                {
                    byte br = broken[b];
                    if (br != 0)
                        continue;
                    int2 n = beamNodes[b];
                    float rest = restLength[b];
                    float yield = yieldForce[b];
                    float f = BenchmarkMath.BeamForce(pos[n.x], pos[n.y], vel[n.x], vel[n.y],
                        beamCoef[b], beamBounds[b], beamKind[b], ref rest, ref yield, ref br, out float3 dir);
                    restLength[b] = rest;
                    yieldForce[b] = yield;
                    broken[b] = br;
                    float3 fv = f * dir;
                    force[n.x] += fv;
                    force[n.y] -= fv;
                }
                for (int i = 0; i < nodeCount; i++)
                {
                    float3 p = pos[i];
                    float3 v = vel[i];
                    BenchmarkMath.IntegrateNode(ref p, ref v, force[i], invMass[i], prm);
                    pos[i] = p;
                    vel[i] = v;
                    force[i] = float3.zero;
                }
            }
        }
    }

    /// <summary>
    /// Multi-threaded variant, pass 1: one force vector per beam (the force on node a; node b
    /// receives the negative). Every beam writes only its own slots, so no atomics are needed.
    /// </summary>
    [BurstCompile(CompileSynchronously = true, DisableSafetyChecks = true)]
    public struct BeamForceJob : IJobParallelFor
    {
        [ReadOnly] public NativeArray<float3> pos;
        [ReadOnly] public NativeArray<float3> vel;
        [ReadOnly] public NativeArray<int2> beamNodes;
        [ReadOnly] public NativeArray<float4> beamCoef;
        [ReadOnly] public NativeArray<float2> beamBounds;
        [ReadOnly] public NativeArray<byte> beamKind;
        public NativeArray<float> restLength;
        public NativeArray<float> yieldForce;
        public NativeArray<byte> broken;
        [WriteOnly] public NativeArray<float3> beamForce;

        public void Execute(int b)
        {
            byte br = broken[b];
            if (br != 0)
            {
                beamForce[b] = float3.zero;
                return;
            }
            int2 n = beamNodes[b];
            float rest = restLength[b];
            float yield = yieldForce[b];
            float f = BenchmarkMath.BeamForce(pos[n.x], pos[n.y], vel[n.x], vel[n.y],
                beamCoef[b], beamBounds[b], beamKind[b], ref rest, ref yield, ref br, out float3 dir);
            restLength[b] = rest;
            yieldForce[b] = yield;
            broken[b] = br;
            beamForce[b] = f * dir;
        }
    }

    /// <summary>
    /// Multi-threaded variant, pass 2: each node gathers its beam forces in a fixed order (by beam
    /// index), so the result does not depend on the thread count, then integrates.
    /// </summary>
    [BurstCompile(CompileSynchronously = true, DisableSafetyChecks = true)]
    public struct NodeGatherIntegrateJob : IJobParallelFor
    {
        public SimParams prm;
        public NativeArray<float3> pos;
        public NativeArray<float3> vel;
        [ReadOnly] public NativeArray<float> invMass;
        [ReadOnly] public NativeArray<int> adjStart;
        [ReadOnly] public NativeArray<int> adjCode;
        [ReadOnly] public NativeArray<float3> beamForce;
        [NativeDisableParallelForRestriction] public NativeArray<int> burstFlag;

        public void Execute(int i)
        {
            if (i == 0)
            {
                int flag = 1;
                BurstProbe.MarkManaged(ref flag);
                burstFlag[0] = flag;
            }
            float3 f = float3.zero;
            int end = adjStart[i + 1];
            for (int k = adjStart[i]; k < end; k++)
            {
                int code = adjCode[k];
                float3 bf = beamForce[code >> 1];
                f += (code & 1) == 0 ? bf : -bf;
            }
            float3 p = pos[i];
            float3 v = vel[i];
            BenchmarkMath.IntegrateNode(ref p, ref v, f, invMass[i], prm);
            pos[i] = p;
            vel[i] = v;
        }
    }
}
