"""One-off (P3b): T14 slalom with the default driver robot (SlalomRun, centre-of-mass track recorded): the car weaves
through every gate (centre of mass on the gate's side, at least half the amplitude), no slide, settled on the run-out,
speed held; the robot's largest path error is reported. Anti-roll bars x1.5 front / x0.5 rear (X18: skidpad limit
0.83 -> 0.93 g, understeer kept through 0.8 g)."""
from pathlib import Path

V = Path("Unity/HellcatSandbox/Assets/Sim/Validation")


def patch(path, pairs, root=V):
    p = root / path
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, s.count(old), old[:120])
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")


patch("HandlingTests.cs", [
    ('''        /// <summary>The 18 m / +-1 m slalom (6 gates, 20 m run-in, 40 m run-out) at a speed; columns t, speed, path error, a_y, yaw
        /// rate, roll, body slip.</summary>''',
     '''        /// <summary>The 18 m / +-1 m slalom (6 gates, 20 m run-in, 40 m run-out) at a speed; columns t, speed, path error, a_y, yaw
        /// rate, roll, body slip, centre of mass x and z (world; the slalom line runs along x = 0 from z0), z0.</summary>'''),
    ('''            var s = new Series("t", "speed_kmh", "path_error", "ay_g", "yaw_dps", "roll_deg", "beta_deg");
            double hPrev = f0.heading, tPrev = 0;
            double3 velPrev = f0.vel;
            Dyn.Drive(w, (20.0 + 18.0 * 6 + 40.0) / v, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
            {
                double dtS = math.max(t - tPrev, 1e-6);
                double yaw = Dyn.WrapDeg(math.degrees(f.heading - hPrev)) / dtS;
                double ay = math.dot((f.vel - velPrev) / dtS, f.right) / Dyn.G;
                s.Add(t, f.speed / Kmh, robot.lateral, ay, yaw, f.rollDeg, math.degrees(math.atan2(f.lateralVel, math.max(f.speed, 0.1))));''',
     '''            var s = new Series("t", "speed_kmh", "path_error", "ay_g", "yaw_dps", "roll_deg", "beta_deg", "x", "z", "z0");
            double hPrev = f0.heading, tPrev = 0;
            double3 velPrev = f0.vel;
            Dyn.Drive(w, (20.0 + 18.0 * 6 + 40.0) / v, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
            {
                double dtS = math.max(t - tPrev, 1e-6);
                double yaw = Dyn.WrapDeg(math.degrees(f.heading - hPrev)) / dtS;
                double ay = math.dot((f.vel - velPrev) / dtS, f.right) / Dyn.G;
                s.Add(t, f.speed / Kmh, robot.lateral, ay, yaw, f.rollDeg, math.degrees(math.atan2(f.lateralVel, math.max(f.speed, 0.1))),
                    f.com.x, f.com.z, f0.rearAxle.z + 20.0);'''),
    ('''            // (a) slalom: 6 gates 18 m apart, +-1.0 m, 50 km/h (peak 0.6 g on the path; at 60 km/h it is 0.86 g, the limit)
            {
                using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f);
                var b = w.bodies[0];
                var probe = new CarProbe(w, 0);
                var f0 = probe.Frame();
                double v = 50.0 * Kmh;
                Dyn.LaunchAt(w, v);
                var path = PolyPath.Slalom(f0.rearAxle.z + 20.0, 18.0, 1.0, 6, 40.0, 40.0);
                var robot = new DriverRobot(b.prm) { path = path, targetSpeed = (t, a) => v, lookMin = 5.0, lookGain = 0.4 };
                var s = new Series("t", "speed_kmh", "path_error", "ay_g", "yaw_dps", "roll_deg", "beta_deg");
                double hPrev = f0.heading, tPrev = 0, vPrev = f0.speed;
                double3 velPrev = f0.vel;
                Dyn.Drive(w, (20.0 + 18.0 * 6 + 20.0) / v, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
                {
                    double dtS = math.max(t - tPrev, 1e-6);
                    double yaw = Dyn.WrapDeg(math.degrees(f.heading - hPrev)) / dtS;
                    double ay = math.dot((f.vel - velPrev) / dtS, f.right) / Dyn.G;
                    s.Add(t, f.speed / Kmh, robot.lateral, ay, yaw, f.rollDeg, math.degrees(math.atan2(f.lateralVel, math.max(f.speed, 0.1))));
                    hPrev = f.heading; tPrev = t; velPrev = f.vel;
                    return true;
                }, probe);
                s.Write(ctx.FilePath(r, "slalom_50.csv"));
                r.Max("slalom 18 m / +-1.0 m at 50 km/h: largest path error", MaxAbs(s, 2, 1.0), 0.8, "m");
                r.Max("slalom: largest body slip angle (no slide)", MaxAbs(s, 6, 1.0), 4.0, "deg");
                r.Info("slalom: peak lateral acceleration / roll", MaxAbs(s, 3, 1.0), "g", $"roll {MaxAbs(s, 5, 1.0):F2} deg, yaw rate {MaxAbs(s, 4, 1.0):F1} deg/s");
                r.Min("slalom: speed held (lowest)", Mean(s, 1, s[s.Count - 1][0] - 0.5, s[s.Count - 1][0]), 45.0, "km/h");
            }''',
     '''            // (a) slalom: 6 gates 18 m apart, +-1.0 m, 50 km/h (peak 0.6 g on the line; at 60 km/h it is 0.86 g, the limit).
            //     The pure-pursuit robot cuts the line (its error is reported); the car has to weave through every gate
            {
                var s = SlalomRun(ctx, 50.0, null);
                s.Write(ctx.FilePath(r, "slalom_50.csv"));
                // gate k at z0 + 9 + 18 k on the side (-1)^k of the line
                double z0 = s[0][9], worstGate = double.MaxValue;
                var gates = new List<string>();
                for (int k = 0; k < 6; k++)
                {
                    double zg = z0 + 9.0 + 18.0 * k, side = k % 2 == 0 ? 1.0 : -1.0;
                    double xg = double.NaN;
                    for (int i = 1; i < s.Count; i++)
                        if (s[i - 1][8] < zg && s[i][8] >= zg)
                        {
                            double u = (zg - s[i - 1][8]) / math.max(s[i][8] - s[i - 1][8], 1e-9);
                            xg = s[i - 1][7] + u * (s[i][7] - s[i - 1][7]);
                            break;
                        }
                    double reach = double.IsNaN(xg) ? -1.0 : side * xg / 1.0;
                    worstGate = math.min(worstGate, reach);
                    gates.Add($"{reach:F2}");
                }
                r.Min("slalom 18 m / +-1.0 m at 50 km/h: the centre of mass reaches each gate's side (worst share of the 1 m amplitude)", worstGate, 0.5);
                r.Info("slalom: share of the amplitude at the gates", worstGate, "", string.Join(" ", gates));
                r.Max("slalom: largest body slip angle (no slide)", MaxAbs(s, 6, 1.0), 4.0, "deg");
                r.Max("slalom: path error over the last 2 s of the run-out (settled, no residual weave)", MaxAbs(s, 2, s[s.Count - 1][0] - 2.0), 0.5, "m");
                r.Info("slalom: largest path error of the robot (pure pursuit cuts the line)", MaxAbs(s, 2, 1.0), "m",
                    $"peak a_y {MaxAbs(s, 3, 1.0):F2} g, roll {MaxAbs(s, 5, 1.0):F2} deg, yaw rate {MaxAbs(s, 4, 1.0):F1} deg/s");
                r.Min("slalom: speed held (lowest)", Mean(s, 1, s[s.Count - 1][0] - 0.5, s[s.Count - 1][0]), 45.0, "km/h");
            }'''),
])
print("patched tests")

P = Path("sim/vehicle/hellcat/params.json")
s = P.read_text(encoding="utf-8")
old = '''    // D-051: torsion rates for the design bar contributions (75.9 / 36.7 kN m/rad at the wheels) through the real link /
    // lever / mount compliance (tools/p3b/arb_tune.py; the rigid-chain design gave 1960 / 550 and half the effect)
    { "name": "arb_front",     "spring": 1500, "damp": 0 },
    { "name": "arb_rear",      "spring": 1650, "damp": 0 },'''
new = '''    // D-051: torsion rates through the real link / lever / mount compliance (tools/p3b/arb_tune.py; the rigid-chain design
    // 1960 / 550 gave half the effect); 1500 / 1650 hit the D-025 bar rates (60 % front share) but the car oversteered from
    // 0.8 g on the skidpad (limit 0.83 g); 75 % front share keeps it understeering to the limit, 0.93 g (X18)
    { "name": "arb_front",     "spring": 2250, "damp": 0 },
    { "name": "arb_rear",      "spring": 825, "damp": 0 },'''
assert s.count(old) == 1
P.write_text(s.replace(old, new), encoding="utf-8")
print("patched params")
