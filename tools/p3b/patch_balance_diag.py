"""One-off (P3b): CircleRamp records the axle slip angles, the wheel loads and the rear slip ratio; diagnostics X18 (balance
on the skidpad ramp: anti-roll-bar share, rear toe, traction control) and X19 (driver robot variants on the slalom)."""
from pathlib import Path

V = Path("Unity/HellcatSandbox/Assets/Sim/Validation")


def patch(path, pairs):
    p = V / path
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, s.count(old), old[:120])
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")


patch("HandlingTests.cs", [
    ('''        /// front), body slip angle (deg).</summary>
        static Series CircleRamp(ValidationContext ctx, Action<SimParamsDef> tweak, double radius, double aStart, double aEnd,
            double rampSeconds, double holdSeconds = 0.0)
        {
            using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f, tweak);''',
     '''        /// front), body slip angle (deg), pitch (deg), mean front / rear slip angle (deg, positive: velocity to the right of the
        /// wheel), wheel loads FL FR RL RR (N), mean rear slip ratio.</summary>
        static Series CircleRamp(ValidationContext ctx, Action<SimParamsDef> tweak, double radius, double aStart, double aEnd,
            double rampSeconds, double holdSeconds = 0.0, Action<DriverRobot> robotTweak = null)
        {
            using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f, tweak);'''),
    ('''            int iFL = probe.WheelIndex("FL"), iFR = probe.WheelIndex("FR");
            var s = new Series("t", "speed", "ay_g", "roll_deg", "path_error", "yaw_dps", "steer", "rwa_deg", "beta_deg", "pitch_deg");''',
     '''            robotTweak?.Invoke(robot);
            int iFL = probe.WheelIndex("FL"), iFR = probe.WheelIndex("FR"), iRL = probe.WheelIndex("RL"), iRR = probe.WheelIndex("RR");
            var s = new Series("t", "speed", "ay_g", "roll_deg", "path_error", "yaw_dps", "steer", "rwa_deg", "beta_deg", "pitch_deg",
                "alpha_f_deg", "alpha_r_deg", "fz_FL", "fz_FR", "fz_RL", "fz_RR", "slip_r");'''),
    ('''                s.Add(t, f.speed, -ay, f.rollDeg, robot.lateral, math.degrees(yaw), w.vehicleState[b.vehicleIndex].steer, rwa, beta, f.pitchDeg);''',
     '''                var ws = w.wheelState;
                int w0 = b.wheelStart;
                s.Add(t, f.speed, -ay, f.rollDeg, robot.lateral, math.degrees(yaw), w.vehicleState[b.vehicleIndex].steer, rwa, beta, f.pitchDeg,
                    0.5 * (probe.SlipAngleDeg(iFL, f) + probe.SlipAngleDeg(iFR, f)), 0.5 * (probe.SlipAngleDeg(iRL, f) + probe.SlipAngleDeg(iRR, f)),
                    ws[w0 + iFL].load, ws[w0 + iFR].load, ws[w0 + iRL].load, ws[w0 + iRR].load, 0.5 * (ws[w0 + iRL].slipRatio + ws[w0 + iRR].slipRatio));'''),
    ('''        // ------------------------------------------------------------------ T10

        public static TestResult Suspension(ValidationContext ctx)''',
     '''        /// <summary>Skidpad limit: the highest 2 s mean of a_y with the path error below 1.5 m and the body slip below 6 deg.</summary>
        static double SkidpadLimit(Series s, out double tBest)
        {
            double best = 0;
            tBest = 0;
            for (int i = 0; i < s.Count; i++)
            {
                if (s[i][0] < 4.0) continue;
                double t1 = s[i][0], sum = 0, errMax = 0, betaMax = 0;
                int n = 0;
                for (int k = i; k >= 0 && s[k][0] >= t1 - 2.0; k--)
                {
                    sum += s[k][2]; errMax = math.max(errMax, math.abs(s[k][4])); betaMax = math.max(betaMax, math.abs(s[k][8])); n++;
                }
                if (errMax < 1.5 && betaMax < 6.0 && n > 0 && sum / n > best) { best = sum / n; tBest = t1; }
            }
            return best;
        }

        /// <summary>X18 (diagnostic): balance on the skidpad ramp for variants - anti-roll-bar share, rear toe-in, traction control.
        /// Per variant: the limit, the understeer gradient (road-wheel angle minus L / R over a_y) and the axle slip angles at
        /// 0.5 / 0.7 / 0.8 g.</summary>
        public static TestResult Balance(ValidationContext ctx)
        {
            var r = new TestResult();
            Action<SimParamsDef> Bars(float f, float rr) => p =>
            {
                foreach (var m in p.materials)
                {
                    if (m.name == "arb_front") m.spring *= f;
                    if (m.name == "arb_rear") m.spring *= rr;
                }
            };
            var variants = new List<(string name, Action<SimParamsDef> tweak, Action<DriverRobot> robot)>
            {
                ("base", null, null),
                ("front bar x1.5", Bars(1.5f, 1f), null),
                ("rear bar x0.5", Bars(1f, 0.5f), null),
                ("front x1.5 rear x0.5", Bars(1.5f, 0.5f), null),
                ("rear toe-in 0.3 deg", p => { foreach (var wu in p.windup) if (wu.name == "rear") wu.toeStatic = 0.3f; }, null),
                ("traction control off", null, d => d.flags = 0),
            };
            foreach (var (name, tweak, robot) in variants)
            {
                var s = CircleRamp(ctx, tweak, SkidpadRadius, 0.5, 1.1, 30.0, 0.0, robot);
                s.Write(ctx.FilePath(r, $"balance_{name.Replace(' ', '_').Replace('.', 'p')}.csv"));
                double lim = SkidpadLimit(s, out double tl);
                string Band(double a)
                {
                    double rw = 0, af = 0, ar = 0, be = 0; int n = 0;
                    for (int i = 0; i < s.Count; i++)
                        if (s[i][0] > 3.0 && math.abs(s[i][2] - a) < 0.025 && math.abs(s[i][8]) < 8.0)
                        { rw += -s[i][7]; af += s[i][10]; ar += s[i][11]; be += s[i][8]; n++; }
                    if (n == 0) return $"{a:F1} g: -";
                    double us = (rw / n - math.degrees(2.951 / SkidpadRadius)) / a;
                    return $"{a:F1} g: K {us:F1} deg/g, alpha f {af / n:F1} r {ar / n:F1}, beta {be / n:F1}";
                }
                r.Info($"{name}: skidpad limit (2 s, path < 1.5 m, beta < 6 deg)", lim, "g", $"at {tl:F1} s; {Band(0.5)}; {Band(0.7)}; {Band(0.8)}");
            }
            r.notes.Add("K = (road-wheel angle - L / R) / a_y; alpha: mean axle slip angle (velocity right of the wheel positive); left turn.");
            return r;
        }

        /// <summary>X19 (diagnostic): driver robot variants on the 18 m slalom (+-1 m) at 50 and 60 km/h.</summary>
        public static TestResult SlalomRobot(ValidationContext ctx)
        {
            var r = new TestResult();
            var variants = new List<(string name, Action<DriverRobot> tweak)>
            {
                ("default", null),
                ("look 0.4 v, min 5", d => { d.lookGain = 0.4; d.lookMin = 5.0; }),
                ("look 0.7 v", d => { d.lookGain = 0.7; }),
                ("no integral", d => { d.kCross = 0.0; }),
                ("yaw damping 0.3", d => { d.kYaw = 0.3; }),
                ("look 0.7 v, yaw 0.3", d => { d.lookGain = 0.7; d.kYaw = 0.3; }),
            };
            foreach (double kmh in new[] { 50.0, 60.0 })
                foreach (var (name, tweak) in variants)
                {
                    var s = SlalomRun(ctx, kmh, tweak);
                    s.Write(ctx.FilePath(r, $"slalom_{kmh:F0}_{name.Replace(' ', '_').Replace(',', '').Replace('.', 'p')}.csv"));
                    r.Info($"slalom {kmh:F0} km/h, {name}: largest path error", MaxAbs(s, 2, 1.0), "m",
                        $"beta {MaxAbs(s, 6, 1.0):F1} deg, a_y {MaxAbs(s, 3, 1.0):F2} g, yaw {MaxAbs(s, 4, 1.0):F0} deg/s, last 2 s error {MaxAbs(s, 2, s[s.Count - 1][0] - 2.0):F2} m");
                }
            return r;
        }

        /// <summary>The 18 m / +-1 m slalom (6 gates, 20 m run-in, 40 m run-out) at a speed; columns t, speed, path error, a_y, yaw
        /// rate, roll, body slip.</summary>
        static Series SlalomRun(ValidationContext ctx, double kmh, Action<DriverRobot> tweak)
        {
            using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f);
            var b = w.bodies[0];
            var probe = new CarProbe(w, 0);
            var f0 = probe.Frame();
            double v = kmh * Kmh;
            Dyn.LaunchAt(w, v);
            var path = PolyPath.Slalom(f0.rearAxle.z + 20.0, 18.0, 1.0, 6, 40.0, 40.0);
            var robot = new DriverRobot(b.prm) { path = path, targetSpeed = (t, a) => v };
            tweak?.Invoke(robot);
            var s = new Series("t", "speed_kmh", "path_error", "ay_g", "yaw_dps", "roll_deg", "beta_deg");
            double hPrev = f0.heading, tPrev = 0;
            double3 velPrev = f0.vel;
            Dyn.Drive(w, (20.0 + 18.0 * 6 + 40.0) / v, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
            {
                double dtS = math.max(t - tPrev, 1e-6);
                double yaw = Dyn.WrapDeg(math.degrees(f.heading - hPrev)) / dtS;
                double ay = math.dot((f.vel - velPrev) / dtS, f.right) / Dyn.G;
                s.Add(t, f.speed / Kmh, robot.lateral, ay, yaw, f.rollDeg, math.degrees(math.atan2(f.lateralVel, math.max(f.speed, 0.1))));
                hPrev = f.heading; tPrev = t; velPrev = f.vel;
                return true;
            }, probe);
            return s;
        }

        // ------------------------------------------------------------------ T10

        public static TestResult Suspension(ValidationContext ctx)'''),
])

patch("ValidationSuite.cs", [
    ('''            ("X17", "Diagnostic: elastokinematics of the parked car (toe and camber under hub forces)", SpeedDiagnostics.Elastokinematics),''',
     '''            ("X17", "Diagnostic: elastokinematics of the parked car (toe and camber under hub forces)", SpeedDiagnostics.Elastokinematics),
            ("X18", "Diagnostic: skidpad balance for anti-roll-bar, rear toe and traction-control variants", HandlingTests.Balance),
            ("X19", "Diagnostic: driver robot variants on the slalom", HandlingTests.SlalomRobot),'''),
])
print("patched")
