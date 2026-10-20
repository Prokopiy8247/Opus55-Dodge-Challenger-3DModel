"""One-off patch (P3, D-038): relative deformation damping of attached parts.

A damp group (D-033) damps a part's deformation relative to its own rigid motion, so the rigid motion of a closure
relative to the body (a hood or door flapping on its hinges and latch, a bumper on its clips, the exhaust on its hangers)
is only damped by its few attachment beams, whose damping the light skin nodes cannot carry (explicit stability): after a
drop the hood still rang at zeta ~0.005. A reference group adds F_i = relRate m_i (v_ref(x_i) - v_i) towards the
reference group's rigid motion (v_cm + w x r, the body), with the reaction applied to the reference group as a
rigid-body distribution m_j (a + alpha x r_j): linear and angular momentum are conserved, the power is
-relRate sum m |dv|^2. It ends when one of the part's attachment break groups fires (latch or hinges), so a hood popping
open in a crash is not held back. Stability cost 2 dt relRate per node.
"""
from pathlib import Path

SIM = Path("Unity/HellcatSandbox/Assets/Sim")


def patch(path, reps):
    s = path.read_text(encoding="utf-8")
    for old, new in reps:
        assert s.count(old) == 1, (path.name, old[:160])
        s = s.replace(old, new)
    path.write_text(s, encoding="utf-8")


# ---------------------------------------------------------------- data
patch(SIM / "Data" / "VehicleDef.cs", [
    ('''        public string[] nodeBg;    // per node: break group that detaches the node from the group ("" never; may be absent)
    }''',
     '''        public string[] nodeBg;    // per node: break group that detaches the node from the group ("" never; may be absent)
        public string reference;   // damp group whose rigid motion the part is also damped towards (D-038), "" none
        public string[] refBg;     // break groups that end the relative damping (the part's latch / hinges / clips)
    }'''),
])
s = (SIM / "Data" / "SimParamsDef.cs").read_text(encoding="utf-8")
i = s.index("class DampGroupMaterialDef")
j = s.index("}", s.index("{", i))
block = s[i:j]
assert "public float rate" in block, block
s = s[:j] + "        public float relRate;                // 1/s towards the reference group's rigid motion (D-038)\n    " + s[j:]
(SIM / "Data" / "SimParamsDef.cs").write_text(s, encoding="utf-8")

# ---------------------------------------------------------------- job
patch(SIM / "Core" / "GroupDampJob.cs", [
    ('''        public int breakGroup;              // the damping stops once this break group fires (-1: never), e.g. a shattered pane
        public int body;
    }''',
     '''        public int breakGroup;              // the damping stops once this break group fires (-1: never), e.g. a shattered pane
        public int body;
        public int refGroup;                // D-038: group whose rigid motion this one is also damped towards (-1: none)
        public float relRate;               // 1/s
        public int refBg0, refBg1;          // break groups that end the relative damping (-1: none)
    }

    /// <summary>Rigid motion of a damp group in the current substep (written by GroupDampJob).</summary>
    public struct DampGroupRigid
    {
        public double3 xc, vc, w;
        public double mass;
        public double3x3 iInv;
        public int valid;
    }'''),
    ('''        [NativeDisableContainerSafetyRestriction] public NativeArray<double> groupDampEnergy; // J dissipated per group''',
     '''        [NativeDisableContainerSafetyRestriction] public NativeArray<double> groupDampEnergy; // J dissipated per group
        [NativeDisableContainerSafetyRestriction] public NativeArray<DampGroupRigid> rigid;  // per group, for GroupRelDampJob'''),
    ('''            DampGroupStatic g = groups[gi];
            int s = g.nodeStart, e = g.nodeStart + g.nodeCount;
            if (g.nodeCount == 0)
                return;''',
     '''            DampGroupStatic g = groups[gi];
            int s = g.nodeStart, e = g.nodeStart + g.nodeCount;
            rigid[gi] = default;
            if (g.nodeCount == 0)
                return;'''),
    ('''            var I = new double3x3(ixx + reg, ixy, ixz, ixy, iyy + reg, iyz, ixz, iyz, izz + reg);
            double3 w = math.mul(math.inverse(I), L);''',
     '''            var I = new double3x3(ixx + reg, ixy, ixz, ixy, iyy + reg, iyz, ixz, iyz, izz + reg);
            double3x3 iInv = math.inverse(I);
            double3 w = math.mul(iInv, L);
            rigid[gi] = new DampGroupRigid { xc = xc, vc = vc, w = w, mass = mt, iInv = iInv, valid = 1 };'''),
])
s = (SIM / "Core" / "GroupDampJob.cs").read_text(encoding="utf-8")
s = s.rstrip()
assert s.endswith("}")
s = s[:-1] + '''
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
'''
(SIM / "Core" / "GroupDampJob.cs").write_text(s, encoding="utf-8")
print("job written")
