"""One-off patch (P3): knuckle wind-up logging in T7 and a temporary static fore-aft push diagnostic (WD)."""
from pathlib import Path

p = Path("Unity/HellcatSandbox/Assets/Sim/Validation/VehicleTests.cs")
s = p.read_text(encoding="utf-8")

anchor = '''        // ------------------------------------------------------------------ T7
'''
helper = '''        /// <summary>Knuckle wind-up of every wheel: rotation of the knuckle about the wheel's spin axis relative to the
        /// body's pitch since the reference (rad, + = top of the knuckle forward). Reference node: the upper ball joint
        /// (front) or the upper knuckle node (rear). With phi0 = null returns the absolute angles (the reference).</summary>
        static double[] Windup(SoftBodyWorld w, double[] phi0)
        {
            var b = w.bodies[0];
            var def = b.def;
            BodyPose(w, out _, out _, out double pitchDeg, out _, out _);
            double alpha = -math.tan(math.radians(pitchDeg));    // body rotation about +x (dy = c z -> alpha = -c)
            var res = new double[b.wheelCount];
            for (int k = 0; k < b.wheelCount; k++)
            {
                var wd = def.wheels[k];
                int top = KnuckleTop(def, wd);
                float3 a = w.pos[b.nodeStart + wd.axleInner], c = w.pos[b.nodeStart + wd.axleOuter];
                float3 e = math.normalize(c - a);
                float3 r = w.pos[b.nodeStart + top] - 0.5f * (a + c);
                r -= math.dot(r, e) * e;
                double phi = math.atan2(r.z, r.y);
                res[k] = phi0 != null ? (phi - phi0[k]) - alpha : phi + alpha;
            }
            return res;
        }

        static int KnuckleTop(VehicleDef def, WheelDef wd)
        {
            string up = wd.name + "_ubj", kup = wd.name + "_kup";
            for (int i = 0; i < def.nodes.Length; i++)
                if (def.nodes[i].name == up || def.nodes[i].name == kup)
                    return i;
            return wd.arm;
        }

'''
assert s.count(anchor) == 1
s = s.replace(anchor, helper + anchor)

old = '''                var s = new Series("t", "speed", "distance", "decel_law", "normal_N", "pitch_deg", "decel_applied");
                Run(w, 6.0, chunk, t =>
                {
                    var m = w.Metrics(0, false);'''
new = '''                var s = new Series("t", "speed", "distance", "decel_law", "normal_N", "pitch_deg", "decel_applied",
                                   "windup_FR_deg", "windup_FL_deg", "windup_RR_deg", "windup_RL_deg");
                var phi0 = Windup(w, null);
                Run(w, 6.0, chunk, t =>
                {
                    var m = w.Metrics(0, false);
                    var wu = Windup(w, phi0);'''
assert s.count(old) == 1
s = s.replace(old, new)
old = '''                    s.Add(t, sp, math.dot(m.centerOfMass - c0, dir), f / b.totalMass, n, pitch, imp);'''
new = '''                    s.Add(t, sp, math.dot(m.centerOfMass - c0, dir), f / b.totalMass, n, pitch, imp,
                          math.degrees(wu[0]), math.degrees(wu[1]), math.degrees(wu[2]), math.degrees(wu[3]));'''
assert s.count(old) == 1
s = s.replace(old, new)
old = '''                distance = s[s.Count - 1][2];
                fullStop = s[s.Count - 1][0];'''
new = '''                distance = s[s.Count - 1][2];
                fullStop = s[s.Count - 1][0];
                double wf = 0.0, wr = 0.0;
                for (int i = 0; i < s.Count; i++)
                {
                    wf = math.max(wf, math.max(math.abs(s[i][7]), math.abs(s[i][8])));
                    wr = math.max(wr, math.max(math.abs(s[i][9]), math.abs(s[i][10])));
                }
                r.Info($"{tag}: peak knuckle wind-up front / rear", wf, "deg", $"rear {wr:F2} deg");'''
assert s.count(old) == 1
s = s.replace(old, new)

anchor = '''        // ------------------------------------------------------------------ T8D (temporary diagnostic, T8 case a)'''
diag = '''        // ------------------------------------------------------------------ WD (temporary diagnostic: wind-up)

        /// <summary>Parked Hellcat on flat ground, a forward body force of 0.25 g ramped in and held: static knuckle
        /// wind-up per wheel, hub fore-aft displacement relative to the CoM, brake torques.</summary>
        public static TestResult WindupDiag(ValidationContext ctx)
        {
            var r = new TestResult();
            using var w = Hellcat(ctx, Ground(), float3.zero, float3.zero, 0.01f);
            var b = w.bodies[0];
            w.SetInput(b.vehicleIndex, Parked);
            var s = new Series("t", "push_N", "com_z", "windup_FR", "windup_FL", "windup_RR", "windup_RL",
                               "brakeT_FR", "brakeT_RR", "hubdz_FR", "hubdz_RR", "pitch_deg");
            Run(w, 2.0, 20);
            var phi0 = Windup(w, null);
            float3 hub0F = Hub(w, 0), hub0R = Hub(w, 2);
            float3 com0 = w.Metrics(0, false).centerOfMass;
            double bodyMass = 0.0;
            foreach (var nd in b.def.nodes)
                if (nd.part == "body")
                    bodyMass += nd.m;
            double push = 0.25 * 9.81 * b.totalMass;
            Run(w, 3.0, 20, t =>
            {
                double f = push * math.saturate((t - 2.0) / 0.5);
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                {
                    var nd = b.def.nodes[i - b.nodeStart];
                    w.extForce[i] = nd.part == "body" ? new float3(0f, 0f, (float)(f * nd.m / bodyMass)) : float3.zero;
                }
                var wu = Windup(w, phi0);
                var m = w.Metrics(0, false);
                float3 hF = Hub(w, 0), hR = Hub(w, 2);
                BodyPose(w, out _, out _, out double pitch, out _, out _);
                double dc = m.centerOfMass.z - com0.z;
                s.Add(t, f, dc, wu[0], wu[1], wu[2], wu[3],
                      w.wheelState[b.wheelStart].brakeTorque, w.wheelState[b.wheelStart + 2].brakeTorque,
                      (hF.z - hub0F.z) - dc, (hR.z - hub0R.z) - dc, pitch);
                return true;
            });
            s.Write(ctx.FilePath(r, "push.csv"));
            var last = s[s.Count - 1];
            r.Info("push force (0.25 g on the body)", last[1], "N");
            r.Info("CoM forward displacement", last[2] * 1000, "mm");
            r.Info("knuckle wind-up FR / RR", math.degrees(last[3]), "deg", $"RR {math.degrees(last[5]):F3} deg");
            r.Info("brake torque FR / RR", last[7], "N m", $"RR {last[8]:F0} N m");
            r.Info("wind-up stiffness FR (brake torque / wind-up)", math.abs(last[7] / last[3]) / 1000, "kN m/rad",
                   $"RR {math.abs(last[8] / last[5]) / 1000:F1} kN m/rad");
            r.Info("hub fore-aft vs CoM FR / RR", last[9] * 1000, "mm", $"RR {last[10] * 1000:F2} mm");
            r.Info("pitch", last[11], "deg");
            return r;
        }

        static float3 Hub(SoftBodyWorld w, int k)
        {
            var b = w.bodies[0];
            var wd = b.def.wheels[k];
            return 0.5f * (w.pos[b.nodeStart + wd.axleInner] + w.pos[b.nodeStart + wd.axleOuter]);
        }

'''
assert s.count(anchor) == 1
s = s.replace(anchor, diag + anchor)
p.write_text(s, encoding="utf-8")

p = Path("Unity/HellcatSandbox/Assets/Sim/Validation/ValidationSuite.cs")
s = p.read_text(encoding="utf-8")
a = '''            ("T8D", "TEMPORARY diagnostic: Hellcat vs the 20 cm wall, per-frame", VehicleTests.WallDiag),'''
assert s.count(a) == 1
s = s.replace(a, a + '''
            ("WD", "TEMPORARY diagnostic: knuckle wind-up under a static fore-aft push", VehicleTests.WindupDiag),''')
p.write_text(s, encoding="utf-8")
print("patched")
