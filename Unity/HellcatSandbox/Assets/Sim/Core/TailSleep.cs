using Unity.Collections;
using Unity.Collections.LowLevel.Unsafe;
using Unity.Mathematics;

namespace Hellcat.Sim
{
    /// <summary>
    /// Sleeping debris (D-098): the bodies marked sleepable (the test map's props, added after the car) form the tail of
    /// the node and beam arrays. Every <see cref="checkEvery"/> substeps (on the world's step counter, so the same
    /// substeps for any frame partition: replays stay bit-identical) the serial phase compares the tail with the rest of
    /// the world: once every tail node has been slower than <see cref="sleepSpeed"/> for <see cref="quietChecks"/> checks
    /// in a row while the tail's bounding box stays more than <see cref="sleepGap"/> from the head's (the car), the tail
    /// sleeps: the beam, contact and node passes skip its elements, so it costs nothing and stays exactly where it was. It
    /// wakes as soon as the head comes within <see cref="wakeGap"/> of it (or <see cref="SoftBodyWorld.WakeTail"/> is
    /// called), well before any contact. state[0]: asleep, state[1]: quiet checks in a row.
    /// </summary>
    public struct TailSleepPhase
    {
        public int tailNodeStart, nodeCount;
        public int checkEvery, quietChecks;
        public float wakeGap, sleepGap, sleepSpeed;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> pos;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> vel;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float> invMass;
        [NativeDisableContainerSafetyRestriction] public NativeArray<int> state;

        public void Execute(long step)
        {
            if (tailNodeStart <= 0 || tailNodeStart >= nodeCount || step % checkEvery != 0)
                return;
            float3 hl = new float3(float.MaxValue), hh = new float3(-float.MaxValue);
            for (int i = 0; i < tailNodeStart; i++)
            {
                if (invMass[i] <= 0f)
                    continue;
                hl = math.min(hl, pos[i]);
                hh = math.max(hh, pos[i]);
            }
            float3 tl = new float3(float.MaxValue), th = new float3(-float.MaxValue);
            for (int i = tailNodeStart; i < nodeCount; i++)
            {
                tl = math.min(tl, pos[i]);
                th = math.max(th, pos[i]);
            }
            float gap = math.length(math.max(0f, math.max(tl - hh, hl - th)));
            if (state[0] != 0)
            {
                if (gap < wakeGap)
                {
                    state[0] = 0;
                    state[1] = 0;
                }
                return;
            }
            float v2 = 0f;
            for (int i = tailNodeStart; i < nodeCount; i++)
                if (invMass[i] > 0f)
                    v2 = math.max(v2, math.lengthsq(vel[i]));
            if (gap > sleepGap && v2 < sleepSpeed * sleepSpeed)
            {
                state[1] = state[1] + 1;
                if (state[1] >= quietChecks)
                    state[0] = 1;
            }
            else
            {
                state[1] = 0;
            }
        }
    }
}
