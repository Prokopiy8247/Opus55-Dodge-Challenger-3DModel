"""One-off (P3b): driver robot at speed, T12 / T13 timing fixes, launch and stop runs as reusable functions (for the
assist tuning sweep X13), 0-100 km/h gated with the 1-ft rollout of the published figures (D-048)."""
from pathlib import Path

ROOT = Path("Unity/HellcatSandbox/Assets/Sim/Validation")


def patch(path, pairs):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:120])
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")


patch("DynamicsCommon.cs", [(
    """        public int gear = DriverInput.Drive;
        public int flags;""",
    """        public int gear = DriverInput.Drive;
        public int flags = DriverInput.FlagTc;  // a driver with traction control on (tests that want it off say so)"""), (
    """                cross = math.clamp(cross + lateral * dt, -50.0, 50.0);
                delta -= kCross * cross;""",
    """                // cross-track integral (the steady understeer offset on circles); its gain falls with the speed squared
                // above 15 m/s: on a straight at speed it only adds phase lag (a 5 s weave grew into a spin at 250 km/h)
                double kc = kCross * math.min(1.0, 225.0 / math.max(v * v, 1.0));
                cross = math.clamp(cross + lateral * dt, -50.0, 50.0);
                delta -= kc * cross;""")])

P = "PowertrainTests.cs"
patch(P, [
    # (a) idle: a 3 s window after the throttle release
    ("""                double[] phaseEnd = { 2.0, 4.0, 7.0, 9.0 };""",
     """                double[] phaseEnd = { 2.0, 4.0, 7.0, 10.0 };"""),
    ("""                double back = Mean(3, 8.5, 9.0, 2, out _, out _);
                r.NearAbs("throttle released in neutral: back to idle (8.5-9 s)", back, pt.idleRpm, 40.0, "rpm");""",
     """                double back = Mean(3, 9.5, 10.0, 2, out _, out _);
                double tIdle = double.NaN;
                for (int i = 0; i < s.Count; i++)
                    if ((int)s[i][1] == 3 && double.IsNaN(tIdle) && s[i][2] <= pt.idleRpm + 50.0)
                        tIdle = s[i][0] - phaseEnd[2];
                r.NearAbs("throttle released in neutral: back to idle (2.5-3 s after the release)", back, pt.idleRpm, 40.0, "rpm");
                r.Info("throttle released in neutral: time from the rev limiter to idle + 50 rpm", tIdle, "s", "friction and pumping torque only, then the idle controller");"""),
    # (d) launch as a reusable run
    ("""            // (d) 0-100 km/h: traction control on and off; (g) wheelspin on launch (traction control off)
            double best = double.MaxValue;
            foreach (bool tc in new[] { true, false })
            {
                using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f, null, true, new DriverInput { brake = 1f, gear = DriverInput.Drive });
                var b = w.bodies[0];
                var probe = new CarProbe(w, 0);
                var f0 = probe.Frame();
                var robot = new DriverRobot(b.prm)
                {
                    path = Straight(f0),
                    pedalOverride = (t, f) => new DriverInput { throttle = 1f, gear = DriverInput.Drive, flags = tc ? DriverInput.FlagTc : 0 },
                };
                string tag = tc ? "launch_tc" : "launch_no_tc";
                var s = new Series("t", "speed_kmh", "distance", "rpm", "gear", "slip_driven", "accel_g", "pitch_deg", "engine_torque",
                    "shaft_torque", "tc_factor", "locked", "converter_sr", "lateral");
                double t100 = double.NaN, t60mph = double.NaN, tRoll = double.NaN, t100Roll = double.NaN, slipPeak = 0.0, a1 = double.NaN;
                double vPrev = 0, tPrev = 0, pitchMin = 0;
                double3 c0 = f0.com;
                Dyn.Drive(w, 7.0, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
                {
                    var st = w.vehicleState[b.vehicleIndex];
                    double dist = math.dot(f.com - c0, f0.forward);
                    double acc = (f.speed - vPrev) / math.max(t - tPrev, 1e-6);
                    vPrev = f.speed;
                    tPrev = t;
                    double slip = MaxDrivenSlip(w);
                    slipPeak = math.max(slipPeak, slip);
                    pitchMin = math.min(pitchMin, f.pitchDeg - f0.pitchDeg);
                    if (double.IsNaN(tRoll) && dist >= 0.3048) tRoll = t;
                    if (double.IsNaN(t60mph) && f.speed >= 26.8224) t60mph = t;
                    if (double.IsNaN(t100) && f.speed >= 100.0 * Kmh) { t100 = t; t100Roll = t - tRoll; }
                    if (double.IsNaN(a1) && t >= 1.0) a1 = f.speed / t;
                    s.Add(t, f.speed / Kmh, dist, st.engineRpm, st.gear, slip, acc / Dyn.G, f.pitchDeg - f0.pitchDeg, st.engineTorque,
                        st.shaftTorque, st.tcFactor, st.locked, st.converterSR, robot.lateral);
                    return double.IsNaN(t100) || t < t100 + 0.5;
                }, probe);
                s.Write(ctx.FilePath(r, $"{tag}.csv"));
                string label = tc ? "traction control on" : "traction control off";
                r.Info($"0-100 km/h, full throttle, {label}", t100, "s", $"0-60 mph {t60mph:F2} s; with a 1-ft rollout (magazine timing) 0-100 {t100Roll:F2} s, 0-60 mph {t60mph - tRoll:F2} s");
                r.Info($"launch, {label}: peak driven-wheel slip ratio", slipPeak, "", $"mean acceleration over the first second {a1 / Dyn.G:F2} g, peak squat {-pitchMin:F2} deg");
                if (!double.IsNaN(t100))
                    best = math.min(best, t100);
                if (!tc)
                {
                    r.Min("wheelspin on launch (traction control off): peak driven-wheel slip ratio", slipPeak, 0.25);
                    r.Min("wheelspin on launch: the car still pulls (mean acceleration over the first second)", a1, 3.0, "m/s^2");
                }
                else
                {
                    r.Max("traction control: driven-wheel slip held below 0.3 after the first 0.3 s", MaxAfter(s, 5, 0.3), 0.3);
                }
            }
            r.Max("0-100 km/h best (brief 4.13: 3.5-4.0 s, +15 %)", best, 4.0 * 1.15, "s");
            r.Min("0-100 km/h best not faster than the brief's range (-15 %)", best, 3.5 * 0.85, "s");""",
     """            // (d) 0-100 km/h: traction control on and off; (g) wheelspin on launch (traction control off)
            double best = double.MaxValue, bestRoll = double.MaxValue;
            foreach (bool tc in new[] { true, false })
            {
                var L = Launch(ctx, r, tc ? "launch_tc" : "launch_no_tc", tc);
                string label = tc ? "traction control on" : "traction control off";
                r.Info($"0-100 km/h, full throttle, {label}", L.t100, "s", $"0-60 mph {L.t60mph:F2} s; with a 1-ft rollout (magazine timing) 0-100 {L.t100Roll:F2} s, 0-60 mph {L.t60Roll:F2} s");
                r.Info($"launch, {label}: peak driven-wheel slip ratio", L.slipPeak, "", $"mean acceleration over the first second {L.a1 / Dyn.G:F2} g, peak squat {L.squat:F2} deg");
                if (!double.IsNaN(L.t100))
                {
                    best = math.min(best, L.t100);
                    bestRoll = math.min(bestRoll, L.t100Roll);
                }
                if (!tc)
                {
                    r.Min("wheelspin on launch (traction control off): peak driven-wheel slip ratio", L.slipPeak, 0.25);
                    r.Min("wheelspin on launch: the car still pulls (mean acceleration over the first second)", L.a1, 3.0, "m/s^2");
                }
                else
                {
                    r.Max("traction control: driven-wheel slip held below 0.3 after the first 0.3 s", L.slipAfter, 0.3);
                }
            }
            // the brief's 3.5-4.0 s are road-test figures, timed with the 1-ft rollout (D-048); from the throttle as info
            r.Info("0-100 km/h best, timed from the throttle application", best, "s", "the rollout figure adds the first 0.3 m");
            r.Max("0-100 km/h best, 1-ft rollout like the published figures (brief 4.13: 3.5-4.0 s, +15 %)", bestRoll, 4.0 * 1.15, "s");
            r.Min("0-100 km/h best not faster than the brief's range (-15 %)", bestRoll, 3.5 * 0.85, "s");"""),
    # (f) coast-down window 100 -> 80 km/h, up to 60 s
    ("""                    Dyn.Drive(w, 30.0, 20, (t, f) => robot.Control(t, 20 * w.dt, f), (t, f) =>
                    {
                        var st = w.vehicleState[b.vehicleIndex];
                        s.Add(t, f.speed / Kmh, st.engineRpm, st.gear, st.engineTorque, st.shaftTorque);
                        if (double.IsNaN(tA) && f.speed <= 100.0 * Kmh) tA = t;
                        if (!double.IsNaN(tA) && double.IsNaN(tB)) { sumV += f.speed; n++; }
                        if (double.IsNaN(tB) && f.speed <= 60.0 * Kmh) tB = t;
                        return double.IsNaN(tB);
                    }, probe);
                    s.Write(ctx.FilePath(r, $"coast_{tag}.csv"));
                    meanSpeed = n > 0 ? sumV / n : 0;
                    return (100.0 - 60.0) * Kmh / (tB - tA);""",
     """                    // 100 -> 80 km/h: the neutral coast-down takes ~20 s (100 -> 60 km/h would take ~40 s)
                    Dyn.Drive(w, 60.0, 20, (t, f) => robot.Control(t, 20 * w.dt, f), (t, f) =>
                    {
                        var st = w.vehicleState[b.vehicleIndex];
                        s.Add(t, f.speed / Kmh, st.engineRpm, st.gear, st.engineTorque, st.shaftTorque);
                        if (double.IsNaN(tA) && f.speed <= 100.0 * Kmh) tA = t;
                        if (!double.IsNaN(tA) && double.IsNaN(tB)) { sumV += f.speed; n++; }
                        if (double.IsNaN(tB) && f.speed <= 80.0 * Kmh) tB = t;
                        return double.IsNaN(tB);
                    }, probe);
                    s.Write(ctx.FilePath(r, $"coast_{tag}.csv"));
                    meanSpeed = n > 0 ? sumV / n : 0;
                    return (100.0 - 80.0) * Kmh / (tB - tA);"""),
    ("""                r.Info("coast-down in neutral 100 -> 60 km/h: mean deceleration", aN / Dyn.G, "g", $"{aN:F3} m/s^2 at {vN / Kmh:F0} km/h mean");""",
     """                r.Info("coast-down in neutral 100 -> 80 km/h: mean deceleration", aN / Dyn.G, "g", $"{aN:F3} m/s^2 at {vN / Kmh:F0} km/h mean");"""),
    ("""                r.Info("coast in drive (throttle off, automatic) 100 -> 60 km/h", aD / Dyn.G, "g", $"{aD:F3} m/s^2");""",
     """                r.Info("coast in drive (throttle off, automatic) 100 -> 80 km/h", aD / Dyn.G, "g", $"{aD:F3} m/s^2");"""),
    ("""                r.Info("engine braking in third, 100 -> 60 km/h: deceleration", a3 / Dyn.G, "g", $"{a3:F3} m/s^2");""",
     """                r.Info("engine braking in third, 100 -> 80 km/h: deceleration", a3 / Dyn.G, "g", $"{a3:F3} m/s^2");"""),
    # launch function
    ("""        static double MaxAfter(Series s, int col, double t0)""",
     """        public struct LaunchResult
        {
            public double t100, t100Roll, t60mph, t60Roll, slipPeak, slipAfter, a1, squat;
        }

        /// <summary>Full-throttle start in drive from a car settled on the brakes (the brake released at t = 0), the robot
        /// steering on the straight; times from the throttle application and with the 1-ft rollout.</summary>
        public static LaunchResult Launch(ValidationContext ctx, TestResult r, string tag, bool tc, Action<SimParamsDef> tweak = null,
            double seconds = 7.0)
        {
            using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f, tweak, true, new DriverInput { brake = 1f, gear = DriverInput.Drive });
            var b = w.bodies[0];
            var probe = new CarProbe(w, 0);
            var f0 = probe.Frame();
            var robot = new DriverRobot(b.prm)
            {
                path = Straight(f0),
                pedalOverride = (t, f) => new DriverInput { throttle = 1f, gear = DriverInput.Drive, flags = tc ? DriverInput.FlagTc : 0 },
            };
            var s = new Series("t", "speed_kmh", "distance", "rpm", "gear", "slip_driven", "accel_g", "pitch_deg", "engine_torque",
                "shaft_torque", "tc_factor", "locked", "converter_sr", "lateral", "slip_speed");
            var res = new LaunchResult { t100 = double.NaN, t100Roll = double.NaN, t60mph = double.NaN, t60Roll = double.NaN, a1 = double.NaN };
            double tRoll = double.NaN, vPrev = 0, tPrev = 0, pitchMin = 0;
            double3 c0 = f0.com;
            Dyn.Drive(w, seconds, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
            {
                var st = w.vehicleState[b.vehicleIndex];
                double dist = math.dot(f.com - c0, f0.forward);
                double acc = (f.speed - vPrev) / math.max(t - tPrev, 1e-6);
                vPrev = f.speed;
                tPrev = t;
                double slip = MaxDrivenSlip(w);
                res.slipPeak = math.max(res.slipPeak, slip);
                pitchMin = math.min(pitchMin, f.pitchDeg - f0.pitchDeg);
                if (double.IsNaN(tRoll) && dist >= 0.3048) tRoll = t;
                if (double.IsNaN(res.t60mph) && f.speed >= 26.8224) { res.t60mph = t; res.t60Roll = t - tRoll; }
                if (double.IsNaN(res.t100) && f.speed >= 100.0 * Kmh) { res.t100 = t; res.t100Roll = t - tRoll; }
                if (double.IsNaN(res.a1) && t >= 1.0) res.a1 = f.speed / t;
                s.Add(t, f.speed / Kmh, dist, st.engineRpm, st.gear, slip, acc / Dyn.G, f.pitchDeg - f0.pitchDeg, st.engineTorque,
                    st.shaftTorque, st.tcFactor, st.locked, st.converterSR, robot.lateral, st.tcSlipSpeed);
                return double.IsNaN(res.t100) || t < res.t100 + 0.5;
            }, probe);
            if (r != null && tag != null)
                s.Write(ctx.FilePath(r, $"{tag}.csv"));
            res.slipAfter = MaxAfter(s, 5, 0.3);
            res.squat = -pitchMin;
            return res;
        }

        static double MaxAfter(Series s, int col, double t0)"""),
])

# T13: the stop as a reusable run
patch(P, [
    ("""        public static TestResult Brakes(ValidationContext ctx)
        {
            var r = new TestResult();

            // one stop from 100 km/h: ABS on / off, optional steering input during the stop
            void Stop(string tag, bool abs, double steer, out double distance, out double meanDecel, out double lateral,
                out double lockedTime, out double peakDive)
            {
                using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f);""",
     """        public struct StopResult
        {
            public double distance, meanDecel, lateral, lockedTime, peakDive;
        }

        /// <summary>One stop from 100 km/h (full pedal in 0.1 s, the robot holding 100 km/h before it): ABS on / off, an
        /// optional fixed steering input after 0.3 s (else the robot steers).</summary>
        public static StopResult Stop(ValidationContext ctx, TestResult r, string tag, bool abs, double steer, Action<SimParamsDef> tweak = null)
        {
            {
                using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f, tweak);"""),
    ("""                s.Write(ctx.FilePath(r, $"{tag}.csv"));
                // scaled to exactly 100 km/h at the brake application (constant deceleration: d ~ v^2)
                distance = d * math.pow(100.0 * Kmh / vBrake, 2.0);
                double tStop = s[s.Count - 1][0] - tBrake;
                meanDecel = 100.0 * Kmh / math.max(tStop, 1e-6);
                lateral = math.abs(s[s.Count - 1][13]);
                lockedTime = locked;
                peakDive = dive;
            }

            Stop("abs_100_0", true, 0.0, out double dAbs, out double aAbs, out _, out double lockAbs, out double diveAbs);""",
     """                if (r != null && tag != null)
                    s.Write(ctx.FilePath(r, $"{tag}.csv"));
                // scaled to exactly 100 km/h at the brake application (constant deceleration: d ~ v^2)
                double tStop = s[s.Count - 1][0] - tBrake;
                return new StopResult
                {
                    distance = d * math.pow(100.0 * Kmh / vBrake, 2.0),
                    meanDecel = 100.0 * Kmh / math.max(tStop, 1e-6),
                    lateral = math.abs(s[s.Count - 1][13]),
                    lockedTime = locked,
                    peakDive = dive,
                };
            }
        }

        public static TestResult Brakes(ValidationContext ctx)
        {
            var r = new TestResult();
            var sa = Stop(ctx, r, "abs_100_0", true, 0.0);
            double dAbs = sa.distance, aAbs = sa.meanDecel, lockAbs = sa.lockedTime, diveAbs = sa.peakDive;"""),
    ("""            Stop("noabs_100_0", false, 0.0, out double dNo, out double aNo, out _, out double lockNo, out _);""",
     """            var sn = Stop(ctx, r, "noabs_100_0", false, 0.0);
            double dNo = sn.distance, aNo = sn.meanDecel, lockNo = sn.lockedTime;"""),
    ("""            Stop("abs_steer", true, 0.3, out _, out _, out double latAbs, out _, out _);
            Stop("noabs_steer", false, 0.3, out _, out _, out double latNo, out _, out _);""",
     """            double latAbs = Stop(ctx, r, "abs_steer", true, 0.3).lateral;
            double latNo = Stop(ctx, r, "noabs_steer", false, 0.3).lateral;"""),
])
print("patched")
