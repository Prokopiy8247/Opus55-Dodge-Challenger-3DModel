using Unity.Burst;
using Unity.Collections;
using Unity.Collections.LowLevel.Unsafe;
using Unity.Jobs;
using Unity.Mathematics;

namespace Hellcat.Sim
{
    public static class HingeConst
    {
        /// <summary>
        /// k_e = D |e|^2 / (A1 + A2) * Geometry: discrete-shell scaling of the plate bending stiffness D to one edge
        /// hinge (calibrated by tools/skeleton/hinges.py --calibrate against the simply supported square plate).
        /// </summary>
        public const float Geometry = 0.56f;
    }

    /// <summary>
    /// Shell bending of the panel skins (D-032), parallel over hinges, after the beam pass of the same substep (so the
    /// broken flags it reads are final for the substep and the result does not depend on the thread count).
    /// A hinge resists the change of the dihedral angle across a skin edge: tau = -k (phi - phi0) - c dphi/dt, forces
    /// F_i = tau dphi/dx_i (momentum and angular momentum conserving, <see cref="TorsionKernel"/>). Above the yield
    /// moment the rest angle phi0 follows (1-D return mapping with linear hardening), so dents and creases stay.
    /// </summary>
    [BurstCompile(FloatMode = FloatMode.Strict, DisableSafetyChecks = true)]
    public struct HingeForceJob : IJobParallelFor
    {
        public float dt;
        public int trackEnergy;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> pos;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> vel;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<byte> broken;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<HingeStatic> hinges;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float> hingeRest;      // phi0 (rad), plastic
        [NativeDisableContainerSafetyRestriction] public NativeArray<float> hingeYield;     // N*m
        [NativeDisableContainerSafetyRestriction] public NativeArray<byte> hingeBroken;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float> hingeAngle;     // phi - phi0 (rad)
        [NativeDisableContainerSafetyRestriction] public NativeArray<float> hingePlastic;   // J of plastic work
        [NativeDisableContainerSafetyRestriction] public NativeArray<double> hingeDampEnergy; // J dissipated
        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> slotForce;

        public void Execute(int i)
        {
            HingeStatic h = hinges[i];
            int s0 = h.slotStart;
            if (hingeBroken[i] == 0 &&
                ((h.beam12 >= 0 && broken[h.beam12] != 0) || (h.beam23 >= 0 && broken[h.beam23] != 0) ||
                 (h.beam34 >= 0 && broken[h.beam34] != 0)))
                hingeBroken[i] = 1;
            if (hingeBroken[i] != 0 ||
                !TorsionKernel.Gradient(pos[h.n1], pos[h.n2], pos[h.n3], pos[h.n4], out float phi,
                    out float3 g1, out float3 g2, out float3 g3, out float3 g4))
            {
                slotForce[s0] = slotForce[s0 + 1] = slotForce[s0 + 2] = slotForce[s0 + 3] = float3.zero;
                hingeAngle[i] = 0f;
                return;
            }
            // A crushed panel squeezes or shears its triangles and the dihedral gradient grows (1 / wing height, times
            // the wing's lever along the edge for the edge nodes): the hinge is softened by (g0 / g)^2, so its force and
            // stiffness stay bounded (no effect while the largest gradient is at most its spawn value).
            float gm = math.max(math.max(math.lengthsq(g1), math.lengthsq(g2)), math.max(math.lengthsq(g3), math.lengthsq(g4)));
            float sc = math.min(1f, h.g0sq / math.max(gm, 1e-12f));
            float kEff = h.k * sc;
            float rest = hingeRest[i];
            float dphi = TorsionKernel.Wrap(phi - rest);
            float tauS = -kEff * dphi;
            float y = hingeYield[i];
            float ab = math.abs(tauS);
            if (ab > y)
            {
                // Return mapping: plastic rotation dp with k (|dphi| - dp) = y + H dp.
                float dp = (ab - y) / (kEff + h.hardening);
                float sgn = dphi >= 0f ? 1f : -1f;
                float yNew = math.min(y + h.hardening * dp, h.yieldCap);
                hingePlastic[i] += 0.5f * (y + yNew) * dp;
                rest = TorsionKernel.Wrap(rest + sgn * dp);
                hingeRest[i] = rest;
                hingeYield[i] = yNew;
                dphi = TorsionKernel.Wrap(phi - rest);
                tauS = -kEff * dphi;
            }
            float rate = math.dot(g1, vel[h.n1]) + math.dot(g2, vel[h.n2]) + math.dot(g3, vel[h.n3]) + math.dot(g4, vel[h.n4]);
            // damping saturates above dampCap rad/s (D-043: a belt hinge bends once a revolution, in ~1.4 ms at 250 km/h;
            // viscous damping of that pass cost 8 kW per wheel, while its small vibrations still need the full damping)
            float rateD = h.dampCap > 0f ? math.clamp(rate, -h.dampCap, h.dampCap) : rate;
            float tauD = -h.c * sc * rateD;
            float tau = tauS + tauD;
            slotForce[s0] = tau * g1;
            slotForce[s0 + 1] = tau * g2;
            slotForce[s0 + 2] = tau * g3;
            slotForce[s0 + 3] = tau * g4;
            hingeAngle[i] = dphi;
            if (trackEnergy != 0)
                hingeDampEnergy[i] += (double)(-tauD * rate) * dt;
        }
    }
}
