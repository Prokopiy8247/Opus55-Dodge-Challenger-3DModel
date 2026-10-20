"""One-off patch (P3, D-036 revised): the wind-up element replaces the single-anchor wind-up bars.

A single-anchor torsion bar puts a net force back on the knuckle (the sum of its gradients is zero, so the knuckle side
gets -tau g4), which the soft links must carry: in the solver the bars only lifted the wind-up stiffness from 7 / 5 to
14 / 17 kN m/rad. The wind-up element is a rotational spring-damper about the spin axis between two node sets, each
receiving a pure couple (radii from the set's centroid, zero net force): the knuckle reaction nodes and the body nodes
that carry the suspension (link pivots, their mounting nodes, the spring tower). Same construction as the brake holding
spring between the rim and the knuckle, whose knuckle couple also moves to centroid radii here (the axle-node force
balance of the old couple left a torque normal to the spin axis, about 10 % of the brake torque).

Also: brake hold and wind-up are budgeted on the knuckle's rotational inertia (mode value (dt^2 K + 2 dt C) / I <= 2),
counted in the exact S (StabilityReport), their energy in the ledger.
"""
from pathlib import Path

SIM = Path("Unity/HellcatSandbox/Assets/Sim")


def patch(path, reps):
    s = path.read_text(encoding="utf-8")
    for old, new in reps:
        assert s.count(old) == 1, (path.name, old[:160])
        s = s.replace(old, new)
    path.write_text(s, encoding="utf-8")


# ---------------------------------------------------------------- params
patch(SIM / "Data" / "SimParamsDef.cs", [
    ('''    [Serializable]
    public class PowertrainDef''',
     '''    /// <summary>Wind-up element of a wheel (D-036): knuckle rotation about the spin axis relative to the body.</summary>
    [Serializable]
    public class WindupDef
    {
        public string name;
        public float stiffness;              // N*m/rad
        public float damping;                // N*m*s/rad
        public float strength = -1f;         // N*m elastic torque that tears it (bushings), <= 0: never
    }

    [Serializable]
    public class PowertrainDef'''),
    ('''        public BrakeDef[] brakes;
        public PowertrainDef powertrain;''',
     '''        public BrakeDef[] brakes;
        public WindupDef[] windup;
        public PowertrainDef powertrain;'''),
    ('''            brakes ??= Array.Empty<BrakeDef>();''',
     '''            brakes ??= Array.Empty<BrakeDef>();
            windup ??= Array.Empty<WindupDef>();'''),
    ('''        public BrakeDef Brake(string name)
        {
            foreach (var b in brakes)
                if (b.name == name)
                    return b;
            return new BrakeDef { name = name };
        }''',
     '''        public BrakeDef Brake(string name)
        {
            foreach (var b in brakes)
                if (b.name == name)
                    return b;
            return new BrakeDef { name = name };
        }

        public WindupDef Windup(string name)
        {
            foreach (var w in windup)
                if (w.name == name)
                    return w;
            return null;
        }'''),
])

patch(SIM / "Data" / "VehicleDef.cs", [
    ('''        public int[] driveReaction;  // body nodes taking the drive torque reaction (the differential); empty: none driven
    }''',
     '''        public int[] driveReaction;  // body nodes taking the drive torque reaction (the differential); empty: none driven
        public string windup;        // wind-up element parameter set in params ("front"/"rear"), "" none (D-036)
        public int[] windupBody;     // body nodes taking the wind-up couple (link pivots, their mounts, the spring tower)
    }'''),
])

# ---------------------------------------------------------------- types
patch(SIM / "Vehicle" / "VehicleTypes.cs", [
    ('''        public int driveStart, driveCount;   // into driveNodes: the differential (drive torque reaction, D-036)''',
     '''        public int driveStart, driveCount;   // into driveNodes: the differential (drive torque reaction, D-036)
        public int windupStart, windupCount; // into windupNodes: body nodes of the wind-up couple (D-036), after the drive slots
        public float windupK, windupC, windupStrength; // N*m/rad, N*m*s/rad, N*m (float.MaxValue: never tears)
        public int wheelGroup;               // break group of the wheel's links (torn off: no wind-up couple), -1 none
        public float knuckleInertia;         // kg*m^2 of the knuckle reaction nodes about the axis (centroid radii)'''),
    ('''        public float slipSpeed;    // m/s, mean tread slip speed of loaded nodes
    }''',
     '''        public float slipSpeed;    // m/s, mean tread slip speed of loaded nodes
        public float windupAngle;  // rad, knuckle rotation about the axis relative to the body since spawn (D-036)
        public int windupBroken;   // 1 once torn (wheel off, or above the strength)
        public float windupTorque; // telemetry, N*m on the knuckle
        public double windupDamped; // J dissipated by the wind-up damper
    }'''),
])

# ---------------------------------------------------------------- world: counts, nodes, slots, parameters, budget
w = SIM / "Core" / "SoftBodyWorld.cs"
patch(w, [
    ('''                        int nd = wd.driven != 0 ? (wd.driveReaction?.Length ?? 0) : 0;
                        nDrive += nd;
                        nSlots += wd.rim.Length + b.knuckles[w].Count + 2 + nd;''',
     '''                        int nd = wd.driven != 0 ? (wd.driveReaction?.Length ?? 0) : 0;
                        int nw = string.IsNullOrEmpty(wd.windup) ? 0 : (wd.windupBody?.Length ?? 0);
                        nDrive += nd;
                        nWindup += nw;
                        nSlots += wd.rim.Length + b.knuckles[w].Count + 2 + nd + nw;'''),
    (''' int nDrive = 0;''', ''' int nDrive = 0, nWindup = 0;'''),
    ('''            driveNodes = Alloc<int>(math.max(nDrive, 1));''',
     '''            driveNodes = Alloc<int>(math.max(nDrive, 1));
            windupNodes = Alloc<int>(math.max(nWindup, 1));'''),
    ('''        NativeArray<int> driveNodes;   // differential nodes of the driven wheels (drive torque reaction, D-036)''',
     '''        NativeArray<int> driveNodes;   // differential nodes of the driven wheels (drive torque reaction, D-036)
        NativeArray<int> windupNodes;  // body nodes of the wind-up couples (D-036)'''),
    ("ref int knCursor, ref int drCursor)", "ref int knCursor, ref int drCursor, ref int wuCursor)"),
    ("BuildVehicle(b, slotOwner, ref rimCursor, ref treadCursor, ref slotCursor, ref refCursor, ref knCursor, ref drCursor)",
     "BuildVehicle(b, slotOwner, ref rimCursor, ref treadCursor, ref slotCursor, ref refCursor, ref knCursor, ref drCursor, ref wuCursor)"),
    (" int drCursor = 0;", " int drCursor = 0, wuCursor = 0;"),
    ('''                    driveStart = drCursor,
                    driveCount = wd.driven != 0 ? (wd.driveReaction?.Length ?? 0) : 0,''',
     '''                    driveStart = drCursor,
                    driveCount = wd.driven != 0 ? (wd.driveReaction?.Length ?? 0) : 0,
                    windupStart = wuCursor,
                    windupCount = string.IsNullOrEmpty(wd.windup) ? 0 : (wd.windupBody?.Length ?? 0),
                    wheelGroup = GroupIndex(b, def.nodes[wd.axleInner].part),'''),
    ('''                for (int k = 0; k < ws.driveCount; k++)
                {
                    driveNodes[drCursor++] = b.nodeStart + wd.driveReaction[k];
                    slotOwner[slotCursor++] = b.nodeStart + wd.driveReaction[k];
                }''',
     '''                for (int k = 0; k < ws.driveCount; k++)
                {
                    driveNodes[drCursor++] = b.nodeStart + wd.driveReaction[k];
                    slotOwner[slotCursor++] = b.nodeStart + wd.driveReaction[k];
                }
                for (int k = 0; k < ws.windupCount; k++)
                {
                    windupNodes[wuCursor++] = b.nodeStart + wd.windupBody[k];
                    slotOwner[slotCursor++] = b.nodeStart + wd.windupBody[k];
                }'''),
    ('''                knuckleNodes = knuckleNodes,
                    driveNodes = driveNodes,''',
     '''                knuckleNodes = knuckleNodes,
                    driveNodes = driveNodes,
                    windupNodes = windupNodes,
                    groupDone = groupDone,'''),
])

s = w.read_text(encoding="utf-8")
# the brake holding spring block: centroid compliance for the knuckle, wind-up parameters, the mode budget
old_start = s.index("                ws.stickK = brake.stickStiffness > 0f ? brake.stickStiffness : 0.15f * ws.rimInertia / (dt * dt);")
old_end = s.index("                wheels[gw] = ws;", old_start)
new_block = '''                ws.stickK = brake.stickStiffness > 0f ? brake.stickStiffness : 0.15f * ws.rimInertia / (dt * dt);
                ws.stickC = brake.stickDamping > 0f ? brake.stickDamping : 2f * 0.3f * math.sqrt(ws.stickK * ws.rimInertia);
                // Wind-up element (D-036): knuckle rotation about the spin axis vs the body nodes that carry the suspension.
                if (ws.windupCount > 0)
                {
                    var wu = b.prm.Windup(wd.windup);
                    if (wu == null)
                        throw new InvalidDataException($"{b.name}: wheel {wd.name}: unknown wind-up set '{wd.windup}'");
                    ws.windupK = math.max(wu.stiffness, 0f);
                    ws.windupC = math.max(wu.damping, 0f);
                    ws.windupStrength = wu.strength > 0f ? wu.strength : float.MaxValue;
                }
                // Both couples act on the knuckle nodes as pure couples (radii from the knuckle centroid). Budget: per node
                // dt^2 k_i / m_i + 2 dt c_i / m_i <= 1 with k_i = K r_i^2 / (sum r^2)^2 (a factor 4 below the explicit
                // limit), and the knuckle's rotation mode (dt^2 (K_b + K_w) + 2 dt (C_b + C_w)) / I_knuckle <= 2.
                var kn = b.knuckles[w].ToArray();
                float qk = CoupleCompliance(b, kn, Centroid(b, kn), axis, out float iK);
                float qr = CoupleCompliance(b, wd.rim, Centroid(b, wd.rim), axis, out _);
                ws.knuckleInertia = iK;
                float kTot = ws.stickK + ws.windupK, cTot = ws.stickC + ws.windupC;
                float load = math.max(qr * (dt * dt * ws.stickK + 2f * dt * ws.stickC), qk * (dt * dt * kTot + 2f * dt * cTot));
                load = math.max(load, (dt * dt * kTot + 2f * dt * cTot) / math.max(iK, 1e-6f) / 2f);
                if (load > 1f)
                {
                    ws.stickK /= load;
                    ws.stickC /= load;
                    ws.windupK /= load;
                    ws.windupC /= load;
                    b.couplingScale = math.min(b.couplingScale, 1f / load);
                }
'''
s = s[:old_start] + new_block + s[old_end:]
# helpers: Centroid and a centroid-based CoupleCompliance with the set's inertia
old_cc_start = s.index("        /// <summary>max_i r_i^2 / ((sum_j r_j^2)^2 m_i) of a set of nodes around the axis (couple compliance per node).</summary>")
old_cc_end = s.index("        void BuildVehicle(", old_cc_start)
s = s[:old_cc_start] + '''        /// <summary>max_i r_i^2 / ((sum_j r_j^2)^2 m_i) of a set of nodes around an axis through <paramref name="centre"/>
        /// (couple compliance per node: a pure couple T puts k_i = K r_i^2 / (sum r^2)^2 on node i), and the set's
        /// moment of inertia about that axis.</summary>
        float CoupleCompliance(Body b, int[] local, float3 centre, float3 axis, out float inertia)
        {
            float sum = 0f;
            inertia = 0f;
            var r2 = new float[local.Length];
            for (int k = 0; k < local.Length; k++)
            {
                float3 r = pos0[b.nodeStart + local[k]] - centre;
                r -= math.dot(r, axis) * axis;
                r2[k] = math.lengthsq(r);
                sum += r2[k];
                float im = invMass[b.nodeStart + local[k]];
                inertia += im > 0f ? r2[k] / im : 0f;
            }
            float q = 0f;
            for (int k = 0; k < local.Length; k++)
                if (sum > 0f)
                    q = math.max(q, r2[k] * invMass[b.nodeStart + local[k]] / (sum * sum));
            return q;
        }

        static int GroupIndex(Body b, string name)
        {
            int g = string.IsNullOrEmpty(name) ? -1 : b.groupNames.IndexOf(name);
            return g >= 0 ? b.groupStart + g : -1;
        }

        float3 Centroid(Body b, int[] local)
        {
            float3 c = float3.zero;
            foreach (int n in local)
                c += pos0[b.nodeStart + n];
            return local.Length > 0 ? c / local.Length : c;
        }

''' + s[old_cc_end:]
# body telemetry field
s = s.replace('''            public float pretensionResidual;         // N, worst force imbalance at spawn after form finding''',
              '''            public float pretensionResidual;         // N, worst force imbalance at spawn after form finding
            public float couplingScale = 1f;         // brake hold / wind-up scale-down by the stability budget (1: none)''')
w.write_text(s, encoding="utf-8")

# ---------------------------------------------------------------- energy ledger
patch(w, [
    ('''            for (int t = b.dampGroupStart; t < b.dampGroupStart + b.dampGroupCount; t++)
                r.damping += dampGroupEnergy[t];''',
     '''            for (int t = b.dampGroupStart; t < b.dampGroupStart + b.dampGroupCount; t++)
                r.damping += dampGroupEnergy[t];
            // wind-up elements (D-036): spring energy 1/2 K theta^2, damper dissipation
            for (int k = b.wheelStart; k < b.wheelStart + b.wheelCount && b.vehicleIndex >= 0; k++)
            {
                var wst = wheelState[k];
                r.damping += wst.windupDamped;
                if (energies && wst.windupBroken == 0)
                    r.torsion += 0.5 * wheels[k].windupK * wst.windupAngle * wst.windupAngle;
            }'''),
])

# ---------------------------------------------------------------- vehicle couplings for the stability report
s = w.read_text(encoding="utf-8")
anchor = "        // ------------------------------------------------------------------ metrics"
assert s.count(anchor) == 1
s = s.replace(anchor, '''        /// <summary>Rank-one couplings of the vehicles for the exact stability S (D-024, D-036): per wheel the brake holding
        /// spring (rim vs knuckle) and the wind-up element (knuckle vs body) about the spin axis, as node lists with the
        /// gradient of the relative angle (e x r_i / sum r^2 per set, centroid radii) and the weight dt^2 K + 2 dt C.</summary>
        public List<(int[] nodes, double3[] grads, double weight)> VehicleCouplings()
        {
            var list = new List<(int[], double3[], double)>();
            for (int wi = 0; wi < wheels.Length && IsBuilt; wi++)
            {
                var ws = wheels[wi];
                if (ws.rimCount == 0)
                    continue;
                float3 axis = ws.axisSign * math.normalizesafe(pos[ws.axleOuter] - pos[ws.axleInner], new float3(1f, 0f, 0f));
                int[] Set(NativeArray<int> src, int start, int count)
                {
                    var a = new int[count];
                    for (int k = 0; k < count; k++)
                        a[k] = src[start + k];
                    return a;
                }
                double3[] Grad(int[] set, double sign)
                {
                    float3 c = float3.zero;
                    foreach (int n in set)
                        c += pos[n];
                    c /= math.max(set.Length, 1);
                    var r = new double3[set.Length];
                    double den = 0.0;
                    for (int k = 0; k < set.Length; k++)
                    {
                        float3 d = pos[set[k]] - c;
                        d -= math.dot(d, axis) * axis;
                        r[k] = d;
                        den += math.lengthsq(d);
                    }
                    var g = new double3[set.Length];
                    for (int k = 0; k < set.Length; k++)
                        g[k] = den > 1e-12 ? sign * math.cross((double3)axis, r[k]) / den : double3.zero;
                    return g;
                }
                (int[], double3[], double) Pair(int[] a, int[] bset, double weight)
                {
                    var n = new int[a.Length + bset.Length];
                    var g = new double3[n.Length];
                    var ga = Grad(a, 1.0);
                    var gb = Grad(bset, -1.0);
                    for (int k = 0; k < a.Length; k++) { n[k] = a[k]; g[k] = ga[k]; }
                    for (int k = 0; k < bset.Length; k++) { n[a.Length + k] = bset[k]; g[a.Length + k] = gb[k]; }
                    return (n, g, weight);
                }
                var rim = Set(rimNodes, ws.rimStart, ws.rimCount);
                var kn = Set(knuckleNodes, ws.knuckleStart, ws.knuckleCount);
                if (kn.Length > 0)
                    list.Add(Pair(rim, kn, dt * dt * ws.stickK + 2.0 * dt * ws.stickC));
                if (ws.windupCount > 0 && wheelState[wi].windupBroken == 0 && kn.Length > 0)
                    list.Add(Pair(kn, Set(windupNodes, ws.windupStart, ws.windupCount), dt * dt * ws.windupK + 2.0 * dt * ws.windupC));
            }
            return list;
        }

''' + anchor)
w.write_text(s, encoding="utf-8")

# ---------------------------------------------------------------- control job
patch(SIM / "Vehicle" / "VehicleControlJob.cs", [
    ('''        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> driveNodes;''',
     '''        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> driveNodes;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> windupNodes;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<byte> groupDone;'''),
    ('''                // Knuckle rotation about the same axis: least squares over the knuckle reaction nodes.
                float numK = 0f, denK = 0f;
                for (int k = 0; k < ws.knuckleCount; k++)
                {
                    int n = knuckleNodes[ws.knuckleStart + k];
                    float3 r = pos[n] - pIn;
                    r -= math.dot(r, axis) * axis;
                    numK += math.dot(math.cross(r, vel[n] - vAxle), axis);
                    denK += math.lengthsq(r);
                }
                float omegaKnuckle = denK > 1e-9f ? numK / denK : 0f;''',
     '''                // Knuckle rotation about the same axis: least squares over the knuckle reaction nodes, radii from their
                // centroid (the reaction couple below is then a pure couple).
                float3 kc = float3.zero, kv = float3.zero;
                for (int k = 0; k < ws.knuckleCount; k++)
                {
                    int n = knuckleNodes[ws.knuckleStart + k];
                    kc += pos[n];
                    kv += vel[n];
                }
                kc /= math.max(ws.knuckleCount, 1);
                kv /= math.max(ws.knuckleCount, 1);
                float numK = 0f, denK = 0f;
                for (int k = 0; k < ws.knuckleCount; k++)
                {
                    int n = knuckleNodes[ws.knuckleStart + k];
                    float3 r = pos[n] - kc;
                    r -= math.dot(r, axis) * axis;
                    numK += math.dot(math.cross(r, vel[n] - kv), axis);
                    denK += math.lengthsq(r);
                }
                float omegaKnuckle = denK > 1e-9f ? numK / denK : 0f;
                // Body nodes of the wind-up element: their rotation about the same axis.
                float3 bc = float3.zero, bv = float3.zero;
                for (int k = 0; k < ws.windupCount; k++)
                {
                    int n = windupNodes[ws.windupStart + k];
                    bc += pos[n];
                    bv += vel[n];
                }
                bc /= math.max(ws.windupCount, 1);
                bv /= math.max(ws.windupCount, 1);
                float numB = 0f, denB = 0f;
                for (int k = 0; k < ws.windupCount; k++)
                {
                    int n = windupNodes[ws.windupStart + k];
                    float3 r = pos[n] - bc;
                    r -= math.dot(r, axis) * axis;
                    numB += math.dot(math.cross(r, vel[n] - bv), axis);
                    denB += math.lengthsq(r);
                }
                float omegaBody = denB > 1e-9f ? numB / denB : 0f;'''),
    ('''                float roll = -crr * load * ws.radius * math.tanh(omega / 0.5f);''',
     '''                // Wind-up element (D-036): rotational spring-damper between the knuckle and the body about the axis.
                float windupT = 0f;
                if (ws.windupCount > 0 && wst.windupBroken == 0)
                {
                    if (ws.wheelGroup >= 0 && groupDone[ws.wheelGroup] != 0)
                        wst.windupBroken = 1;
                    else
                    {
                        float rel = omegaKnuckle - omegaBody;
                        wst.windupAngle += rel * dt;
                        float tS = -ws.windupK * wst.windupAngle;
                        if (math.abs(tS) > ws.windupStrength)
                            wst.windupBroken = 1;
                        else
                        {
                            float tD = -ws.windupC * rel;
                            windupT = tS + tD;
                            wst.windupDamped += (double)(-tD * rel) * dt;
                        }
                    }
                }
                wst.windupTorque = windupT;

                float roll = -crr * load * ws.radius * math.tanh(omega / 0.5f);'''),
    ('''                float kscale = denK > 1e-9f ? -(total - driveReact) / denK : 0f;
                float3 fSum = float3.zero;
                for (int k = 0; k < ws.knuckleCount; k++)
                {
                    int n = knuckleNodes[ws.knuckleStart + k];
                    float3 r = pos[n] - pIn;
                    r -= math.dot(r, axis) * axis;
                    float3 f = kscale * math.cross(axis, r);
                    slotForce[ws.slotStart + ws.rimCount + k] = f;
                    fSum += f;
                }
                slotForce[ws.slotStart + ws.rimCount + ws.knuckleCount] = -0.5f * fSum;
                slotForce[ws.slotStart + ws.rimCount + ws.knuckleCount + 1] = -0.5f * fSum;''',
     '''                // (pure couple: radii from the knuckle centroid; the two axle slots stay at zero)
                float kscale = denK > 1e-9f ? (-(total - driveReact) + windupT) / denK : 0f;
                for (int k = 0; k < ws.knuckleCount; k++)
                {
                    int n = knuckleNodes[ws.knuckleStart + k];
                    float3 r = pos[n] - kc;
                    r -= math.dot(r, axis) * axis;
                    slotForce[ws.slotStart + ws.rimCount + k] = kscale * math.cross(axis, r);
                }
                slotForce[ws.slotStart + ws.rimCount + ws.knuckleCount] = float3.zero;
                slotForce[ws.slotStart + ws.rimCount + ws.knuckleCount + 1] = float3.zero;
                if (ws.windupCount > 0)
                {
                    float bscale = denB > 1e-9f ? -windupT / denB : 0f;
                    int w0 = ws.slotStart + ws.rimCount + ws.knuckleCount + 2 + ws.driveCount;
                    for (int k = 0; k < ws.windupCount; k++)
                    {
                        float3 r = pos[windupNodes[ws.windupStart + k]] - bc;
                        r -= math.dot(r, axis) * axis;
                        slotForce[w0 + k] = bscale * math.cross(axis, r);
                    }
                }'''),
])

# ---------------------------------------------------------------- stability report: add the couplings
patch(SIM / "Core" / "StabilityReport.cs", [
    ('''            var z = new double3[n];
            var y = new double3[n];
            void Apply(double[] x, double[] outv)''',
     '''            // vehicle couplings (D-036): brake holding springs and wind-up elements as rank-one terms
            var cpl = w.VehicleCouplings();
            var z = new double3[n];
            var y = new double3[n];
            void Apply(double[] x, double[] outv)'''),
    ('''                for (int i = 0; i < n; i++)
                {
                    double3 v = y[i] * sInv[i];''',
     '''                foreach (var (cn, cg, cw) in cpl)
                {
                    if (cw == 0.0)
                        continue;
                    double proj = 0.0;
                    for (int q = 0; q < cn.Length; q++)
                        proj += math.dot(cg[q], z[cn[q]]);
                    for (int q = 0; q < cn.Length; q++)
                        y[cn[q]] += cw * proj * cg[q];
                }
                for (int i = 0; i < n; i++)
                {
                    double3 v = y[i] * sInv[i];'''),
])

# ---------------------------------------------------------------- E1: the undamped variant also drops the wind-up damping
patch(SIM / "Validation" / "VehicleTests.cs", [
    ('''                    if (!damping)
                        foreach (var m in prm.materials)
                        {''',
     '''                    if (!damping)
                        foreach (var wu in prm.windup)
                            wu.damping = 0f;
                    if (!damping)
                        foreach (var m in prm.materials)
                        {'''),
])

# ---------------------------------------------------------------- skeleton: remove the wind-up bars, add the wind-up sets
patch(Path("tools/blender/hcar/hskel.py"), [
    ('''        windup_bar(B, ubj, w, f"apron2_{s}", "windup_f", part)
''', ''),
    ('''        windup_bar(B, k_up, w, f"shelf68_{s}", "windup_r", part)
''', ''),
])
h = Path("tools/blender/hcar/hskel.py")
s = h.read_text(encoding="utf-8")
a = s.index("def windup_bar(B, wing, w, anchor, mat, part):")
e = s.index("def anti_roll_levers(B, prefix, axR, axL, tip_pos, group, pick):")
s = s[:a] + s[e:]
old = '''def register_wheels(B, st):
    for name, w in list(st["wheels_front"].items()) + list(st["wheels_rear"].items()):
        front = name[0] == "F"
        B.sk.wheel(name, w["ax_in"], w["ax_out"], w["rim_i"] + w["rim_o"], w["tread"], w["arm"], driven=not front,
                   steered=front, brake="front" if front else "rear", radius=0.352, pressure_group=f"tire_{name}",
                   drive_reaction=() if front else st["diff"])'''
new = '''def windup_body(B, name):
    """Body nodes of a wheel's wind-up element (D-036): the inner pivots of its links (body-side ends of the arm, link and
    tie-rod beams from the knuckle nodes), the body nodes those pivots are mounted on, and the spring tower."""
    sk = B.sk
    names = [n["name"] for n in sk.nodes]
    knuckle = {sk.node_index[f"{name}_{k}"] for k in (("lbj", "ubj", "tre") if name[0] == "F" else ("klf", "klr", "kup"))}
    adj = {}
    for bm in sk.beams:
        adj.setdefault(bm["a"], []).append(bm)
        adj.setdefault(bm["b"], []).append(bm)
    body = lambda i: sk.nodes[i]["part"] == "body"
    other = lambda bm, i: bm["b"] if bm["a"] == i else bm["a"]
    pivots, mounts, tower = set(), set(), set()
    for k in knuckle:
        for bm in adj.get(k, []):
            j = other(bm, k)
            if body(j) and bm["mat"] in ("arm", "link", "tierod"):
                pivots.add(j)
            if body(j) and bm["mat"].startswith("spring_"):
                tower.add(j)
    for p in pivots:
        for bm in adj.get(p, []):
            j = other(bm, p)
            if body(j) and j not in pivots and bm["mat"] in ("subframe", "subframe_mount"):
                mounts.add(j)
    ids = sorted(pivots | mounts | tower)
    assert len(ids) >= 6, (name, [names[i] for i in ids])
    return ids


def register_wheels(B, st):
    for name, w in list(st["wheels_front"].items()) + list(st["wheels_rear"].items()):
        front = name[0] == "F"
        B.sk.wheel(name, w["ax_in"], w["ax_out"], w["rim_i"] + w["rim_o"], w["tread"], w["arm"], driven=not front,
                   steered=front, brake="front" if front else "rear", radius=0.352, pressure_group=f"tire_{name}",
                   drive_reaction=() if front else st["diff"], windup="front" if front else "rear",
                   windup_body=windup_body(B, name))'''
assert s.count(old) == 1
s = s.replace(old, new)
h.write_text(s, encoding="utf-8")

patch(Path("tools/blender/hcar/sk.py"), [
    ('''    def wheel(self, name, axle_inner, axle_outer, rim, tread, arm, driven, steered, brake, radius, pressure_group="",
              drive_reaction=()):
        """drive_reaction: body nodes taking the drive torque reaction (the differential, D-036)."""''',
     '''    def wheel(self, name, axle_inner, axle_outer, rim, tread, arm, driven, steered, brake, radius, pressure_group="",
              drive_reaction=(), windup="", windup_body=()):
        """drive_reaction: body nodes taking the drive torque reaction (the differential, D-036); windup: wind-up element
        parameter set, windup_body: the body nodes of its couple (D-036)."""'''),
    ('''                            "driveReaction": [self.idx(n) for n in drive_reaction]})''',
     '''                            "driveReaction": [self.idx(n) for n in drive_reaction],
                            "windup": windup, "windupBody": [self.idx(n) for n in windup_body]})'''),
])

# ---------------------------------------------------------------- params.json
patch(Path("sim/vehicle/hellcat/params.json"), [
    ('''    // wind-up bars (D-036): knuckle rotation about the spin axis vs the body, N m/rad; strength = bushing tear-out torque
    { "name": "windup_f",      "spring": 100000, "damp": 15, "strength": 15000 },
    { "name": "windup_r",      "spring": 80000,  "damp": 10, "strength": 12000 },
''', ''),
    ('''  "brakes": [
    { "name": "front", "maxTorque": 3600 },
    { "name": "rear",  "maxTorque": 2400, "handbrakeTorque": 2600 }
  ],''',
     '''  // brake holding spring while stuck (rim vs knuckle, N m/rad, N m s/rad): ~1 deg of rim creep at full torque; budgeted
  // with the wind-up element on the knuckle's rotational inertia (D-036)
  "brakes": [
    { "name": "front", "maxTorque": 3600, "stickStiffness": 300000, "stickDamping": 220 },
    { "name": "rear",  "maxTorque": 2400, "handbrakeTorque": 2600, "stickStiffness": 150000, "stickDamping": 100 }
  ],
  // wind-up elements (D-036): knuckle rotation about the spin axis vs the body nodes carrying the suspension (link pivots,
  // their mounts, the spring tower). Real corners 50-300 kN m/rad; strength = bushing tear-out torque
  "windup": [
    { "name": "front", "stiffness": 200000, "damping": 300, "strength": 15000 },
    { "name": "rear",  "stiffness": 200000, "damping": 150, "strength": 12000 }
  ],'''),
])
print("patched")
