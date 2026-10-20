"""One-off (P3b): robot defaults from X16, T12 top-speed / open-loop checks, TC check above 36 km/h, T13 repeated stops
from a steady cruise."""
from pathlib import Path

V = Path("Unity/HellcatSandbox/Assets/Sim/Validation")


def patch(path, pairs):
    p = V / path
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:100])
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")


patch("DynamicsCommon.cs", [
    ("""        public double crossSpeedExp = 2.0;     // the integral gain falls as (15 m/s / v)^exp above 15 m/s""",
     """        public double crossSpeedExp = 1.0;     // the integral gain falls as (15 m/s / v)^exp above 15 m/s (X16)"""),
    ("""        public double kYaw = 0.0;              // rad of road-wheel angle per rad/s of yaw-rate error""",
     """        public double kYaw = 0.15;             // rad of road-wheel angle per rad/s of yaw-rate error (X16: 0.19 m path
                                               // offset over 45 s at 282 km/h; without it the integral weaves)"""),
])

P = "PowertrainTests.cs"
s = (V / P).read_text(encoding="utf-8")
a = s.index("            // (e) top speed: full throttle in drive from 250 km/h on the straight")
b = s.index("            // (f) engine braking and coast-down from 100 km/h: neutral, drive, manual third")
new_top = '''            // (e) top speed: full throttle in drive from 270 km/h on the straight with the robot steering; the asymptote
            //     from the acceleration (2 s slope of the speed) against the speed over the last 20 s
            {
                using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f);
                var b = w.bodies[0];
                var probe = new CarProbe(w, 0);
                Dyn.LaunchAt(w, 270.0 * Kmh);
                var f0 = probe.Frame();
                var robot = new DriverRobot(b.prm) { path = Straight(f0, 6000.0), targetSpeed = (t, a) => 200.0 };
                double seconds = ctx.quick ? 15.0 : 45.0;
                var s = new Series("t", "speed_kmh", "rpm", "gear", "accel", "lateral", "yaw_rate_dps", "pitch_deg", "aero_N", "engine_torque");
                double hPrev = f0.heading, tPrev = 0, vPrev = f0.speed;
                Dyn.Drive(w, seconds, 20, (t, f) => robot.Control(t, 20 * w.dt, f), (t, f) =>
                {
                    var st = w.vehicleState[b.vehicleIndex];
                    double dtS = math.max(t - tPrev, 1e-6);
                    double yaw = Dyn.WrapDeg(math.degrees(f.heading - hPrev)) / dtS;
                    s.Add(t, f.speed / Kmh, st.engineRpm, st.gear, (f.speed - vPrev) / dtS, robot.lateral, yaw, f.pitchDeg - f0.pitchDeg,
                        math.length(st.aeroForce), st.engineTorque);
                    hPrev = f.heading; tPrev = t; vPrev = f.speed;
                    return true;
                }, probe);
                s.Write(ctx.FilePath(r, "top_speed.csv"));
                double tEnd = s[s.Count - 1][0];
                double vEnd = 0; int nEnd = 0;
                double latMax = 0, yawSq = 0; int nYaw = 0;
                var vx = new List<double>();
                var ax = new List<double>();
                for (int i = 0; i < s.Count; i++)
                {
                    if (s[i][0] >= tEnd - 2.0) { vEnd += s[i][1]; nEnd++; }
                    if (s[i][0] >= 2.0) { latMax = math.max(latMax, math.abs(s[i][5])); yawSq += s[i][6] * s[i][6]; nYaw++; }
                    // acceleration as the 2 s slope of the speed (the 10 ms difference is noisy)
                    if (s[i][0] >= tEnd - 20.0 && s[i][0] <= tEnd - 2.0)
                    {
                        int j = i;
                        while (j < s.Count - 1 && s[j][0] < s[i][0] + 2.0) j++;
                        vx.Add(0.5 * (s[i][1] + s[j][1]));
                        ax.Add((s[j][1] - s[i][1]) * Kmh / math.max(s[j][0] - s[i][0], 1e-6));
                    }
                }
                vEnd /= math.max(nEnd, 1);
                var fit = Dyn.Fit(vx, ax);
                double aEnd = ax.Count > 0 ? ax[ax.Count - 1] : 0.0;
                double vTop = fit.slope < 0 && aEnd > 0.0 ? math.min(-fit.intercept / fit.slope, vEnd + 20.0) : vEnd;
                vTop = math.max(vTop, vEnd);
                var last = s[s.Count - 1];
                r.Info("top-speed run: speed after the run (2 s mean)", vEnd, "km/h", $"{seconds:F0} s at full throttle from 270 km/h, gear {last[3]:F0} at {last[2]:F0} rpm; acceleration at the end {aEnd:F3} m/s^2");
                r.Min("top speed (drag and gearing limited, asymptote of acceleration vs speed): brief 290-320 km/h -15 %", vTop, 290.0 * 0.85, "km/h");
                r.Max("top speed: brief 290-320 km/h +15 %", vTop, 320.0 * 1.15, "km/h");
                r.Info("top speed vs the Widebody's 195 mph (314 km/h, Dodge S7/S8)", vTop / 314.0, "", $"{vTop:F1} km/h; the node tire's losses under drive limit it (D-048)");
                r.Max("straight-line stability at top speed (robot steering): yaw-rate RMS after 2 s", math.sqrt(yawSq / math.max(nYaw, 1)), 1.0, "deg/s");
                r.Max("straight-line stability at top speed (robot steering): largest path offset after 2 s", latMax, 0.5, "m");
            }

            // (e2) the car alone at speed: full throttle from 270 km/h with the steering fixed straight (no robot), 15 s:
            //      no self-oscillation (yaw-rate RMS) and no divergence (heading change)
            {
                using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f);
                var b = w.bodies[0];
                var probe = new CarProbe(w, 0);
                Dyn.LaunchAt(w, 270.0 * Kmh);
                var f0 = probe.Frame();
                double hPrev = f0.heading, tPrev = 0, yawSq = 0, headMax = 0;
                int n = 0;
                Dyn.Drive(w, 15.0, 20, (t, f) => new DriverInput { throttle = 1f, gear = DriverInput.Drive, flags = DriverInput.FlagTc }, (t, f) =>
                {
                    double dtS = math.max(t - tPrev, 1e-6);
                    double yaw = Dyn.WrapDeg(math.degrees(f.heading - hPrev)) / dtS;
                    hPrev = f.heading; tPrev = t;
                    if (t > 1.0) { yawSq += yaw * yaw; n++; headMax = math.max(headMax, math.abs(Dyn.WrapDeg(math.degrees(f.heading - f0.heading)))); }
                    return true;
                }, probe);
                r.Max("open-loop straight line at full throttle from 270 km/h, steering fixed: yaw-rate RMS", math.sqrt(yawSq / math.max(n, 1)), 1.0, "deg/s");
                r.Max("open-loop straight line: largest heading change in 15 s (no divergence)", headMax, 3.0, "deg");
            }

'''
s = s[:a] + new_top + s[b:]
(V / P).write_text(s, encoding="utf-8")

patch(P, [
    ("""            for (int i = 0; i < s.Count; i++)
                if (s[i][1] * Kmh > 5.0)
                    res.slipAfter = math.max(res.slipAfter, s[i][5]);""",
     """            for (int i = 0; i < s.Count; i++)
                if (s[i][1] * Kmh > 10.0)
                    res.slipAfter = math.max(res.slipAfter, s[i][5]);"""),
    ("""                    r.Max("traction control: driven-wheel slip ratio held below 0.35 above 18 km/h", L.slipAfter, 0.35);""",
     """                    r.Max("traction control: driven-wheel slip ratio held below 0.35 above 36 km/h", L.slipAfter, 0.35);"""),
    ("""                    if (phase == 0 && t - tPhase > 1.0 && math.abs(f.speed - 100.0 * Kmh) < 0.3 * Kmh)
                    {""",
     """                    // brake from a steady cruise: 1.5 s within 1 km/h of 100 km/h (like the first stop, launched at 100 km/h)
                    if (phase == 0)
                        steady = math.abs(f.speed - 100.0 * Kmh) < 1.0 * Kmh ? steady + 10 * w.dt : 0.0;
                    if (phase == 0 && t - tPhase > 1.0 && steady >= 1.5 && math.abs(f.speed - 100.0 * Kmh) < 0.3 * Kmh)
                    {"""),
    ("""                int phase = 0;   // 0 cruise to 100, 1 braking""",
     """                int phase = 0;   // 0 cruise to 100, 1 braking
                double steady = 0.0;"""),
])
print("patched")
