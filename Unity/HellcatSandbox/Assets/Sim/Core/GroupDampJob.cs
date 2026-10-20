using Unity.Burst;
using Unity.Collections;
using Unity.Collections.LowLevel.Unsafe;
using Unity.Jobs;
using Unity.Mathematics;

namespace Hellcat.Sim
{
    /// <summary>
    /// Deformation damping group (D-033): a set of nodes (one panel, one glass pane) whose velocities are damped
    /// towards the group's own rigid motion, F_i = rate m_i (v_cm + omega x r_i - v_i), with v_cm and omega from the
    /// group's momentum and angular momentum (Mueller et al. 2007, Position Based Dynamics, section 3.5). Linear and
    /// angular momentum are conserved, the rigid motion of the part is not damped, and the damping ratio of a mode
    /// inside the group is rate / (2 omega): strongest for the low panel modes that beam damping (axial,
    /// stiffness-proportional) cannot reach without costing stability.
    /// </summary>
    public struct DampGroupStatic
    {
        public int nodeStart, nodeCount;    // into the damp-group node list
        public float rate;                  // 1/s
        public int breakGroup;              // the damping stops once this break group fires (-1: never), e.g. a shattered pane
        public int body;
        public int refGroup;                // D-038: group whose rigid motion this one is also damped towards (-1: none)
        public float relRate;               // 1/s
        public int refBg0, refBg1;          // break groups that end the relative damping (-1: none)
        public float vCap;                  // m/s: above this mass-weighted RMS deformation speed the damping force is
                                            // scaled down to it (rate-independent, hysteresis-like losses, D-043); 0: none
        public int spin;                    // 1: a wheel: its ring beams carry the hoop tension of the rotation (D-044)
    }

    /// <summary>Rigid motion of a damp group in the current substep (written by GroupDampJob).</summary>
    public struct DampGroupRigid
    {
        public double3 xc, vc, w;
        public double mass;
        public double3x3 iInv;
        public int valid;
    }

    [BurstCompile(FloatMode = FloatMode.Strict, DisableSafetyChecks = true)]
    public struct GroupDampJob : IJobParallelFor
    {
        public float dt;
        public int trackEnergy;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> pos;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> vel;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float> invMass;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<byte> groupDone;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<DampGroupStatic> groups;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> groupNodes;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> groupNodeBg;  // -1: never detaches
        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> dampForce;      // per node
        [NativeDisableContainerSafetyRestriction] public NativeArray<double> groupDampEnergy; // J dissipated per group
        [NativeDisableContainerSafetyRestriction] public NativeArray<DampGroupRigid> rigid;  // per group, for GroupRelDampJob

        public void Execute(int gi)
        {
            DampGroupStatic g = groups[gi];
            int s = g.nodeStart, e = g.nodeStart + g.nodeCount;
            rigid[gi] = default;
            if (g.nodeCount == 0)
                return;
            if (g.breakGroup >= 0 && groupDone[g.breakGroup] != 0)
            {
                for (int k = s; k < e; k++)
                    dampForce[groupNodes[k]] = float3.zero;
                return;
            }
            // momentum, centre of mass (double: the group sits metres from the origin, the sums are small differences);
            // a node whose break group fired (a seat, the engine torn off its mounts) has left the group
            double mt = 0.0;
            double3 xc = double3.zero, p = double3.zero;
            for (int k = s; k < e; k++)
            {
                int i = groupNodes[k];
                float im = invMass[i];
                if (im <= 0f || Detached(k))
                    continue;
                double m = 1.0 / im;
                mt += m;
                xc += m * (double3)pos[i];
                p += m * (double3)vel[i];
            }
            if (mt <= 0.0)
                return;
            xc /= mt;
            double3 vc = p / mt;
            double3 L = double3.zero;
            double ixx = 0, iyy = 0, izz = 0, ixy = 0, ixz = 0, iyz = 0;
            for (int k = s; k < e; k++)
            {
                int i = groupNodes[k];
                float im = invMass[i];
                if (im <= 0f || Detached(k))
                    continue;
                double m = 1.0 / im;
                double3 r = (double3)pos[i] - xc;
                L += m * math.cross(r, (double3)vel[i] - vc);
                ixx += m * (r.y * r.y + r.z * r.z);
                iyy += m * (r.x * r.x + r.z * r.z);
                izz += m * (r.x * r.x + r.y * r.y);
                ixy -= m * r.x * r.y;
                ixz -= m * r.x * r.z;
                iyz -= m * r.y * r.z;
            }
            // omega = I^-1 L; a tiny isotropic term keeps a flat or collinear group's tensor invertible
            double reg = 1e-6 * (ixx + iyy + izz) + 1e-12;
            var I = new double3x3(ixx + reg, ixy, ixz, ixy, iyy + reg, iyz, ixz, iyz, izz + reg);
            double3x3 iInv = math.inverse(I);
            double3 w = math.mul(iInv, L);
            rigid[gi] = new DampGroupRigid { xc = xc, vc = vc, w = w, mass = mt, iInv = iInv, valid = 1 };
            double rate = g.rate;
            // D-043: a viscous damper dissipates per deformation cycle in proportion to the deformation rate, so a rolling
            // tire's losses grew with speed (C_rr 0.007 at 18 km/h, 0.31 at 288 km/h). Above vCap of mass-weighted RMS
            // deformation speed the group's damping is scaled down to it: viscous for the free vibration of a parked
            // car, friction-like (loss per cycle independent of the rate) for the contact patch of a rolling tire. A
            // common scale keeps the forces momentum and angular-momentum free.
            if (g.vCap > 0f)
            {
                double ms = 0.0;
                for (int k = s; k < e; k++)
                {
                    int i = groupNodes[k];
                    float im = invMass[i];
                    if (im <= 0f || Detached(k))
                        continue;
                    double3 r = (double3)pos[i] - xc;
                    ms += math.lengthsq(vc + math.cross(w, r) - (double3)vel[i]) / im;
                }
                double rms = math.sqrt(ms / mt);
                if (rms > g.vCap)
                    rate *= g.vCap / rms;
            }
            double diss = 0.0;
            for (int k = s; k < e; k++)
            {
                int i = groupNodes[k];
                float im = invMass[i];
                if (im <= 0f || Detached(k))
                {
                    dampForce[i] = float3.zero;
                    continue;
                }
                double3 r = (double3)pos[i] - xc;
                double3 dv = vc + math.cross(w, r) - (double3)vel[i];
                double3 f = (rate / im) * dv;
                diss += math.dot(f, dv);   // sum f.v = -rate sum m |dv|^2 (the rigid part does no work)
                dampForce[i] = (float3)f;
            }
            if (trackEnergy != 0)
                groupDampEnergy[gi] += diss * dt;
        }

        bool Detached(int k)
        {
            int bg = groupNodeBg[k];
            return bg >= 0 && groupDone[bg] != 0;
        }
    }

    /// <summary>
    /// Relative deformation damping (D-038), after GroupDampJob: each group with a reference group is also damped towards
    /// the reference group's rigid motion, F_i = relRate m_i (v_ref(x_i) - v_i), and the sum of these forces and their
    /// torque about the reference centre of mass goes back onto the reference group as a rigid-body distribution
    /// m_j (a + alpha x r_j) (momentum conserving). Serial and in group order: deterministic.
    /// </summary>
    [BurstCompile(FloatMode = FloatMode.Strict, DisableSafetyChecks = true)]
    public struct GroupRelDampJob : IJob
    {
        public float dt;
        public int trackEnergy;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> pos;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> vel;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float> invMass;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<byte> groupDone;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<DampGroupStatic> groups;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> groupNodes;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> groupNodeBg;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<DampGroupRigid> rigid;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> dampForce;
        [NativeDisableContainerSafetyRestriction] public NativeArray<double> groupDampEnergy;
        [NativeDisableContainerSafetyRestriction] public NativeArray<double3> reactF, reactT;   // per group (scratch)

        public void Execute()
        {
            int n = groups.Length;
            for (int gi = 0; gi < n; gi++)
            {
                reactF[gi] = double3.zero;
                reactT[gi] = double3.zero;
            }
            bool any = false;
            for (int gi = 0; gi < n; gi++)
            {
                DampGroupStatic g = groups[gi];
                if (g.refGroup < 0 || g.relRate <= 0f || g.nodeCount == 0)
                    continue;
                if ((g.breakGroup >= 0 && groupDone[g.breakGroup] != 0) || (g.refBg0 >= 0 && groupDone[g.refBg0] != 0) ||
                    (g.refBg1 >= 0 && groupDone[g.refBg1] != 0))
                    continue;
                DampGroupRigid rf = rigid[g.refGroup];
                if (rf.valid == 0)
                    continue;
                double3 fSum = double3.zero, tSum = double3.zero;
                double diss = 0.0;
                for (int k = g.nodeStart; k < g.nodeStart + g.nodeCount; k++)
                {
                    int i = groupNodes[k];
                    float im = invMass[i];
                    if (im <= 0f || (groupNodeBg[k] >= 0 && groupDone[groupNodeBg[k]] != 0))
                        continue;
                    double3 r = (double3)pos[i] - rf.xc;
                    double3 dv = rf.vc + math.cross(rf.w, r) - (double3)vel[i];
                    double3 f = (g.relRate / im) * dv;
                    dampForce[i] += (float3)f;
                    fSum += f;
                    tSum += math.cross(r, f);
                    diss += math.dot(f, dv);
                }
                reactF[g.refGroup] = reactF[g.refGroup] - fSum;
                reactT[g.refGroup] = reactT[g.refGroup] - tSum;
                if (trackEnergy != 0)
                    groupDampEnergy[gi] += diss * dt;
                any = true;
            }
            if (!any)
                return;
            for (int gi = 0; gi < n; gi++)
            {
                double3 F = reactF[gi], T = reactT[gi];
                if (math.all(F == double3.zero) && math.all(T == double3.zero))
                    continue;
                DampGroupStatic g = groups[gi];
                DampGroupRigid rf = rigid[gi];
                double3 a = F / rf.mass;
                double3 alpha = math.mul(rf.iInv, T);
                for (int k = g.nodeStart; k < g.nodeStart + g.nodeCount; k++)
                {
                    int i = groupNodes[k];
                    float im = invMass[i];
                    if (im <= 0f || (groupNodeBg[k] >= 0 && groupDone[groupNodeBg[k]] != 0))
                        continue;
                    double3 r = (double3)pos[i] - rf.xc;
                    dampForce[i] += (float3)((a + math.cross(alpha, r)) / im);
                }
            }
        }
    }
}
