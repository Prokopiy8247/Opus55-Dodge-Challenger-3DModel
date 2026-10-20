"""One-off patch (P3, D-036): exact pure couples. Every couple of the wheel model (rim, knuckle, wind-up body set,
differential) is applied as a rigid-body angular acceleration f_i = alpha x r_i with alpha = J^-1 tau (J: the set's
unweighted inertia tensor about its centroid, full 3x3), so the torque is exactly tau = T e and the net force zero; the
rates use the matching least-squares angular velocity w = J^-1 sum r x (v - v_mean), so the power of a couple is exactly
T e.w. Projected radii (r perpendicular to e) left a torque normal to e for sets with products of inertia (the knuckle,
the wind-up body set): E1 lost angular momentum (error 1.28). Vehicle couplings count in the 'extras' S only (the beams
S is compared with tools/skeleton/stability.py)."""
from pathlib import Path

SIM = Path("Unity/HellcatSandbox/Assets/Sim")


def patch(path, reps):
    s = path.read_text(encoding="utf-8")
    for old, new in reps:
        assert s.count(old) == 1, (path.name, old[:160])
        s = s.replace(old, new)
    path.write_text(s, encoding="utf-8")


cj = SIM / "Vehicle" / "VehicleControlJob.cs"
s = cj.read_text(encoding="utf-8")

# helpers at the end of the struct
anchor = '''            st.driveTorqueTotal = totalDrive;
            vehicleState[vi] = st;
        }'''
assert s.count(anchor) == 1
s = s.replace(anchor, anchor + '''

        /// <summary>Centroid, inverse unweighted inertia tensor and least-squares angular velocity of a node set.</summary>
        void SetFrame(NativeArray<int> list, int start, int count, out float3 c, out float3x3 jInv, out float3 omega)
        {
            c = float3.zero;
            float3 vm = float3.zero;
            for (int k = 0; k < count; k++)
            {
                int n = list[start + k];
                c += pos[n];
                vm += vel[n];
            }
            float inv = 1f / math.max(count, 1);
            c *= inv;
            vm *= inv;
            float xx = 0f, yy = 0f, zz = 0f, xy = 0f, xz = 0f, yz = 0f;
            float3 l = float3.zero;
            for (int k = 0; k < count; k++)
            {
                int n = list[start + k];
                float3 r = pos[n] - c;
                xx += r.y * r.y + r.z * r.z;
                yy += r.x * r.x + r.z * r.z;
                zz += r.x * r.x + r.y * r.y;
                xy -= r.x * r.y;
                xz -= r.x * r.z;
                yz -= r.y * r.z;
                l += math.cross(r, vel[n] - vm);
            }
            float reg = 1e-6f * (xx + yy + zz) + 1e-12f;
            var j = new float3x3(xx + reg, xy, xz, xy, yy + reg, yz, xz, yz, zz + reg);
            jInv = count > 0 ? math.inverse(j) : float3x3.identity;
            omega = count > 0 ? math.mul(jInv, l) : float3.zero;
        }

        /// <summary>Pure couple tau on a node set: f_i = (J^-1 tau) x r_i (zero net force, torque exactly tau).</summary>
        void ApplyCouple(NativeArray<int> list, int start, int count, float3 c, float3x3 jInv, float3 tau, int slot0)
        {
            float3 alpha = math.mul(jInv, tau);
            for (int k = 0; k < count; k++)
                slotForce[slot0 + k] = math.cross(alpha, pos[list[start + k]] - c);
        }''')

# rim rate
old = '''                // Rim centroid and angular velocity about the axis.
                float3 cSum = float3.zero, vcSum = float3.zero;
                for (int k = 0; k < ws.rimCount; k++)
                {
                    int n = rimNodes[ws.rimStart + k];
                    cSum += pos[n];
                    vcSum += vel[n];
                }
                float3 c = cSum / ws.rimCount;
                float3 vc = vcSum / ws.rimCount;
                float num = 0f, den = 0f;
                for (int k = 0; k < ws.rimCount; k++)
                {
                    int n = rimNodes[ws.rimStart + k];
                    float3 r = pos[n] - c;
                    r -= math.dot(r, axis) * axis;
                    num += math.dot(math.cross(r, vel[n] - vc), axis);
                    den += math.lengthsq(r);
                }
                float omegaWheel = den > 1e-9f ? num / den : 0f;'''
new = '''                // Rim, knuckle and wind-up body set: centroid, inverse inertia tensor, least-squares angular velocity
                // (every couple below is f_i = (J^-1 tau) x r_i: torque exactly tau, zero net force).
                SetFrame(rimNodes, ws.rimStart, ws.rimCount, out float3 c, out float3x3 jRim, out float3 wRim);
                float omegaWheel = math.dot(wRim, axis);'''
assert s.count(old) == 1
s = s.replace(old, new)

old_start = s.index("                // Knuckle rotation about the same axis: least squares over the knuckle reaction nodes, radii from their")
old_end = s.index("                float omega = omegaWheel - omegaKnuckle;")
s = s[:old_start] + '''                SetFrame(knuckleNodes, ws.knuckleStart, ws.knuckleCount, out float3 kc, out float3x3 jKn, out float3 wKn);
                float omegaKnuckle = math.dot(wKn, axis);
                float3 bc = float3.zero, wBd = float3.zero;
                float3x3 jBd = float3x3.identity;
                if (ws.windupCount > 0)
                    SetFrame(windupNodes, ws.windupStart, ws.windupCount, out bc, out jBd, out wBd);
                float omegaBody = math.dot(wBd, axis);
''' + s[old_end:]

# rim couple
old_start = s.index("                // Couple on the rim nodes (net force zero: radii are measured from the rim centroid).")
old_end = s.index("                // Reaction couples (D-036): the drive torque comes through the half-shaft from the differential, so the")
s = s[:old_start] + '''                // Couple on the rim nodes.
                ApplyCouple(rimNodes, ws.rimStart, ws.rimCount, c, jRim, total * axis, ws.slotStart);
''' + s[old_end:]

# knuckle, body and differential couples
old_start = s.index("                // Reaction couple on the knuckle nodes (f_i = -T (axis x r_i) / sum r^2: torque -T about the axis);")
old_end = s.index("            st.driveTorqueTotal = totalDrive;")
s = s[:old_start] + '''                ApplyCouple(knuckleNodes, ws.knuckleStart, ws.knuckleCount, kc, jKn, (-(total - driveReact) + windupT) * axis,
                    ws.slotStart + ws.rimCount);
                slotForce[ws.slotStart + ws.rimCount + ws.knuckleCount] = float3.zero;       // axle slots: unused
                slotForce[ws.slotStart + ws.rimCount + ws.knuckleCount + 1] = float3.zero;
                if (ws.driveCount > 0)
                {
                    SetFrame(driveNodes, ws.driveStart, ws.driveCount, out float3 dc, out float3x3 jDr, out _);
                    ApplyCouple(driveNodes, ws.driveStart, ws.driveCount, dc, jDr, -driveReact * axis,
                        ws.slotStart + ws.rimCount + ws.knuckleCount + 2);
                }
                if (ws.windupCount > 0)
                    ApplyCouple(windupNodes, ws.windupStart, ws.windupCount, bc, jBd, -windupT * axis,
                        ws.slotStart + ws.rimCount + ws.knuckleCount + 2 + ws.driveCount);
            }

''' + s[old_end:]
cj.write_text(s, encoding="utf-8")

# the old drive couple block (radii projected) is gone with the replaced section; check nothing references denK / vAxle
s = cj.read_text(encoding="utf-8")
for name in ("denK", "denB", "kscale", "bscale", "dscale"):
    assert name not in s, name

# stability report: the exact-S couplings use the same tensor gradients; and only in the extras S
w = SIM / "Core" / "SoftBodyWorld.cs"
patch(w, [
    ('''                double3[] Grad(int[] set, double sign)
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
                }''',
     '''                double3[] Grad(int[] set, double sign)
                {
                    // d(e.w)/dx_i of the least-squares rotation w = J^-1 sum r x v: (J^-1 e) x r_i (as the couples)
                    double3 c = double3.zero;
                    foreach (int n in set)
                        c += (double3)pos[n];
                    c /= math.max(set.Length, 1);
                    double xx = 0, yy = 0, zz = 0, xy = 0, xz = 0, yz = 0;
                    var r = new double3[set.Length];
                    for (int k = 0; k < set.Length; k++)
                    {
                        double3 d = (double3)pos[set[k]] - c;
                        r[k] = d;
                        xx += d.y * d.y + d.z * d.z;
                        yy += d.x * d.x + d.z * d.z;
                        zz += d.x * d.x + d.y * d.y;
                        xy -= d.x * d.y;
                        xz -= d.x * d.z;
                        yz -= d.y * d.z;
                    }
                    double reg = 1e-6 * (xx + yy + zz) + 1e-12;
                    var jm = new double3x3(xx + reg, xy, xz, xy, yy + reg, yz, xz, yz, zz + reg);
                    double3 a = math.mul(math.inverse(jm), (double3)axis);
                    var g = new double3[set.Length];
                    for (int k = 0; k < set.Length; k++)
                        g[k] = sign * math.cross(a, r[k]);
                    return g;
                }'''),
])
patch(SIM / "Core" / "StabilityReport.cs", [
    ('''            var cpl = w.VehicleCouplings();''',
     '''            var cpl = extras ? w.VehicleCouplings() : new List<(int[] nodes, double3[] grads, double weight)>();'''),
])
s = (SIM / "Core" / "StabilityReport.cs").read_text(encoding="utf-8")
if "using System.Collections.Generic;" not in s:
    s = "using System.Collections.Generic;\n" + s
    (SIM / "Core" / "StabilityReport.cs").write_text(s, encoding="utf-8")

# WD: log the element's own angle and torque
patch(SIM / "Validation" / "VehicleTests.cs", [
    ('''            r.Info("pitch", last[11], "deg");
            return r;''',
     '''            r.Info("pitch", last[11], "deg");
            for (int k = 0; k < b.wheelCount; k++)
            {
                var wst = w.wheelState[b.wheelStart + k];
                r.Info($"wind-up element {b.def.wheels[k].name}: angle (knuckle vs its body set)", math.degrees(wst.windupAngle), "deg",
                       $"torque {wst.windupTorque:F0} N m, brake {wst.brakeTorque:F0} N m, broken {wst.windupBroken}");
            }
            return r;'''),
])
print("patched")
