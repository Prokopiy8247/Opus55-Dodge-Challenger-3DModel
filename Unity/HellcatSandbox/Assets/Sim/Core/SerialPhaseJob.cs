using Unity.Burst;
using Unity.Collections;
using Unity.Collections.LowLevel.Unsafe;
using Unity.Jobs;
using Unity.Mathematics;

namespace Hellcat.Sim
{
    /// <summary>
    /// Serial work at the start of every substep: apply break groups triggered by the previous
    /// beam pass, advance the clock and spawn ramps, run the vehicle controllers, the force elements
    /// (torsion bars, pressure groups) and, every few substeps, rebuild the node-vs-triangle grid.
    /// </summary>
    [BurstCompile(FloatMode = FloatMode.Strict, DisableSafetyChecks = true)]
    public struct SerialPhaseJob : IJob
    {
        public int substepIndex;
        public int hasVehicles;
        public int hasForceElements;
        public int collisionEnabled;
        public int rebuildEvery;
        public float dt;
        public float spawnRamp;
        [NativeDisableContainerSafetyRestriction] public NativeArray<byte> groupTrigger;
        [NativeDisableContainerSafetyRestriction] public NativeArray<byte> groupDone;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> groupBeamStart;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> groupBeams;
        [NativeDisableContainerSafetyRestriction] public NativeArray<byte> broken;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float> bodyAge;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float> spawnBlend;
        [NativeDisableContainerSafetyRestriction] public NativeArray<long> clock;   // [0] steps since build, [1] grid schedule origin
        [NativeDisableContainerSafetyRestriction] public NativeArray<int> counters; // [0] groups fired
        public Vehicle.VehicleControlJob control;
        public ForceElementPhase forces;
        public CollisionGridPhase grid;
        public TailSleepPhase sleep;   // sleeping debris (D-098)
        // lateral friction axes of the anisotropic contact nodes (D-048): (node, a, b), axis along pos[b] - pos[a]
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int3> frictionAxes;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> axisPos;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> nodeLat;
        public int frictionAxisCount;

        public void Execute()
        {
            for (int k = 0; k < frictionAxisCount; k++)
            {
                int3 e = frictionAxes[k];
                nodeLat[e.x] = math.normalizesafe(axisPos[e.z] - axisPos[e.y]);
            }
            for (int g = 0; g < groupTrigger.Length; g++)
            {
                if (groupTrigger[g] == 0 || groupDone[g] != 0)
                    continue;
                groupDone[g] = 1;
                counters[0] = counters[0] + 1;
                for (int k = groupBeamStart[g]; k < groupBeamStart[g + 1]; k++)
                    broken[groupBeams[k]] = 1;
            }

            for (int b = 0; b < bodyAge.Length; b++)
            {
                float age = bodyAge[b] + dt;
                bodyAge[b] = age;
                spawnBlend[b] = spawnRamp > 0f ? math.saturate(age / spawnRamp) : 1f;
            }
            long step = clock[0];
            clock[0] = step + 1;
            sleep.Execute(step);

            if (hasVehicles != 0)
            {
                control.substepIndex = substepIndex;
                control.Execute();
            }
            if (hasForceElements != 0)
                forces.Execute();
            if (collisionEnabled != 0 && (step - clock[1]) % rebuildEvery == 0)
                grid.Execute();
        }
    }

    /// <summary>Runs whole substeps on one thread (small worlds, validation tests): same kernels, same order.</summary>
    [BurstCompile(FloatMode = FloatMode.Strict, DisableSafetyChecks = true)]
    public struct SingleThreadStepJob : IJob
    {
        public int substeps;
        public int beamCount, hingeCount, dampGroupCount, nodeCount;
        public int collisionEnabled;
        public SerialPhaseJob serial;
        public BeamForceJob beams;
        public HingeForceJob hingeJob;
        public GroupDampJob dampJob;
        public GroupRelDampJob relDampJob;
        public NodeContactJob contact;
        public ContactScatterJob scatter;
        public NodeIntegrateJob nodes;
        public PostContactJob post;

        public void Execute()
        {
            for (int s = 0; s < substeps; s++)
            {
                serial.substepIndex = s;
                serial.Execute();
                for (int b = 0; b < beamCount; b++)
                    beams.Execute(b);
                for (int h = 0; h < hingeCount; h++)
                    hingeJob.Execute(h);
                for (int g = 0; g < dampGroupCount; g++)
                    dampJob.Execute(g);
                if (dampGroupCount > 0)
                    relDampJob.Execute();
                if (collisionEnabled != 0)
                {
                    for (int i = 0; i < nodeCount; i++)
                        contact.Execute(i);
                    scatter.Execute();
                }
                for (int i = 0; i < nodeCount; i++)
                    nodes.Execute(i);
                if (collisionEnabled != 0)
                    post.Execute();
            }
        }
    }
}
