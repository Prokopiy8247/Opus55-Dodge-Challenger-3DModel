using Unity.Collections;
using Unity.Collections.LowLevel.Unsafe;
using Unity.Mathematics;

namespace Hellcat.Sim
{
    /// <summary>
    /// Force elements evaluated once per substep in the serial phase, before the beam pass: torsion bars
    /// (anti-roll bars) and pressure groups (tire cavities). Forces go to the world's force slots, which the
    /// node job gathers in a fixed order. Embedded in <see cref="SerialPhaseJob"/>.
    /// </summary>
    public struct ForceElementPhase
    {
        public const float MaxTwist = 1.0472f;   // rad (60 deg): a torsion bar twisted further has failed (D-060)
        public float dt;
        public int trackEnergy;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> pos;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> vel;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<byte> broken;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<byte> groupDone;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> slotForce;
        // torsion bars
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<TorsionBarStatic> torsionBars;
        [NativeDisableContainerSafetyRestriction] public NativeArray<byte> torsionBroken;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float> torsionAngle;      // phi - phi0 (rad)
        [NativeDisableContainerSafetyRestriction] public NativeArray<double> torsionDampEnergy; // J dissipated
        // pressure groups
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<PressureGroupStatic> pressureGroups;
        [NativeDisableContainerSafetyRestriction] public NativeArray<PressureState> pressureState;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int3> pressureTris;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> leakBeams;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float> pressureScale;

        public void Execute()
        {
            for (int t = 0; t < torsionBars.Length; t++)
                Torsion(t);
            for (int g = 0; g < pressureGroups.Length; g++)
                Pressure(g);
        }

        void Torsion(int t)
        {
            TorsionBarStatic tb = torsionBars[t];
            if (tb.n1 < 0)
                return; // padding entry of an empty array
            int s0 = tb.slotStart;
            if (torsionBroken[t] == 0 &&
                ((tb.beam12 >= 0 && broken[tb.beam12] != 0) || (tb.beam23 >= 0 && broken[tb.beam23] != 0) ||
                 (tb.beam34 >= 0 && broken[tb.beam34] != 0) || (tb.breakGroup >= 0 && groupDone[tb.breakGroup] != 0)))
                torsionBroken[t] = 1;
            // D-060: the dihedral gradient grows as 1 / (lever distance from the axis); a crushed front laid an anti-roll
            // bar's lever along its axis and the bar shot its nodes away at 180 m/s (+56 kJ in one step). A bar whose
            // lever has lost half its arm, whose axis changed by a quarter or which is twisted past 60 deg has lost its
            // links and bushings: it is gone.
            if (torsionBroken[t] == 0 && tb.axis > 0f)
            {
                TorsionKernel.Levers(pos[tb.n1], pos[tb.n2], pos[tb.n3], pos[tb.n4], out float r1, out float r4, out float ax);
                if (r1 < 0.5f * tb.lever1 || r4 < 0.5f * tb.lever2 || math.abs(ax - tb.axis) > 0.25f * tb.axis)
                    torsionBroken[t] = 1;
            }
            if (torsionBroken[t] != 0 ||
                !TorsionKernel.Gradient(pos[tb.n1], pos[tb.n2], pos[tb.n3], pos[tb.n4], out float phi,
                    out float3 g1, out float3 g2, out float3 g3, out float3 g4))
            {
                slotForce[s0] = slotForce[s0 + 1] = slotForce[s0 + 2] = slotForce[s0 + 3] = float3.zero;
                return;
            }
            float dphi = TorsionKernel.Wrap(phi - tb.phi0);
            float rate = math.dot(g1, vel[tb.n1]) + math.dot(g2, vel[tb.n2]) + math.dot(g3, vel[tb.n3]) + math.dot(g4, vel[tb.n4]);
            float tauS = -tb.k * dphi;
            float tauD = -tb.c * rate;
            if (math.abs(tauS) > tb.strength || (tb.axis > 0f && math.abs(dphi) > MaxTwist))
            {
                torsionBroken[t] = 1;
                slotForce[s0] = slotForce[s0 + 1] = slotForce[s0 + 2] = slotForce[s0 + 3] = float3.zero;
                return;
            }
            float tau = tauS + tauD; // generalized force along phi: F_i = tau * dphi/dx_i
            slotForce[s0] = tau * g1;
            slotForce[s0 + 1] = tau * g2;
            slotForce[s0 + 2] = tau * g3;
            slotForce[s0 + 3] = tau * g4;
            torsionAngle[t] = dphi;
            if (trackEnergy != 0)
                torsionDampEnergy[t] += (double)(-tauD * rate) * dt;
        }

        void Pressure(int g)
        {
            PressureGroupStatic pg = pressureGroups[g];
            if (pg.triCount == 0)
                return;
            PressureState st = pressureState[g];
            // Cavity volume: signed tetrahedra relative to a cavity node (small numbers far from the origin).
            float3 o = pos[pressureTris[pg.triStart].x];
            float vol = 0f;
            for (int t = pg.triStart; t < pg.triStart + pg.triCount; t++)
            {
                int3 tri = pressureTris[t];
                vol += math.dot(pos[tri.x] - o, math.cross(pos[tri.y] - o, pos[tri.z] - o));
            }
            vol *= 1f / 6f;
            int nb = 0;
            for (int k = pg.leakBeamStart; k < pg.leakBeamStart + pg.leakBeamCount; k++)
                nb += broken[leakBeams[k]];
            float vEff = math.max(vol, pg.minVolume);
            float rate = math.min(pg.leakMax, pg.leakPerBeam * nb + st.puncture);
            if (rate > 0f)
                st.gas = math.max(st.gas - dt * rate * math.max(st.gas - pg.pAtm * vEff, 0f), pg.pAtm * vEff * 0.999f);
            float pAbs = math.min(st.gas / vEff, pg.maxAbs);
            float pGauge = math.max(pAbs - pg.pAtm, 0f);
            // Cord pre-tension follows the gas content (constant while sealed, so the system stays conservative).
            float full = pg.gas0 - pg.pAtm * pg.volume0;
            pressureScale[g] = full > 0f ? math.saturate((st.gas - pg.pAtm * pg.volume0) / full) : 0f;
            float f = pGauge * (0.5f / 3f);
            int slot = pg.slotStart;
            for (int t = pg.triStart; t < pg.triStart + pg.triCount; t++)
            {
                int3 tri = pressureTris[t];
                float3 a = pos[tri.x];
                float3 fv = f * math.cross(pos[tri.y] - a, pos[tri.z] - a);
                slotForce[slot] = fv;
                slotForce[slot + 1] = fv;
                slotForce[slot + 2] = fv;
                slot += 3;
            }
            st.volume = vol;
            st.pAbs = pAbs;
            st.brokenBeams = nb;
            pressureState[g] = st;
        }
    }
}
