using System;
using System.Collections.Generic;
using Hellcat.Sim.Data;
using Hellcat.Sim.Vehicle;
using Unity.Mathematics;
using static Hellcat.Sim.Validation.ValidationSuite;

namespace Hellcat.Sim.Validation
{
    /// <summary>Validation tests 12 (powertrain) and 13 (brakes) of brief section 10 on the Hellcat (D-042).</summary>
    public static class PowertrainTests
    {
        const double Kmh = 1.0 / 3.6;
        const double RpmPerRad = 60.0 / (2.0 * math.PI);

        static double DrivenOmega(SoftBodyWorld w)
        {
            var b = w.bodies[0];
            double s = 0;
            int n = 0;
            for (int k = 0; k < b.wheelCount; k++)
                if (w.wheels[b.wheelStart + k].driven != 0)
                {
                    s += w.wheelState[b.wheelStart + k].omegaAbs;
                    n++;
                }
            return n > 0 ? s / n : 0.0;
        }

        static double MaxDrivenSlip(SoftBodyWorld w)
        {
            var b = w.bodies[0];
            double s = 0;
            for (int k = 0; k < b.wheelCount; k++)
                if (w.wheels[b.wheelStart + k].driven != 0)
                    s = math.max(s, w.wheelState[b.wheelStart + k].slipRatio);
            return s;
        }

        static double MinSlip(SoftBodyWorld w, bool front)
        {
            var b = w.bodies[0];
            double s = 0;
            for (int k = 0; k < b.wheelCount; k++)
                if ((w.wheels[b.wheelStart + k].front != 0) == front)
                    s = math.min(s, w.wheelState[b.wheelStart + k].slipRatio);
            return s;
        }

        static PolyPath Straight(in CarFrame f, double length = 3000.0) =>
            PolyPath.Line(new double2(f.rearAxle.x, f.rearAxle.z), math.normalize(new double2(f.forward.x, f.forward.z)), length);

        // ------------------------------------------------------------------ T12

        public static TestResult Powertrain(ValidationContext ctx)
        {
            var r = new TestResult();
            var prm0 = LoadHellcat(ctx).prm;
            var pt = prm0.powertrain;

            // (a) idle in neutral and in drive against the brakes, (b) rev limiter: full throttle in neutral
            {
                using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f);
                var b = w.bodies[0];
                var s = new Series("t", "phase", "rpm", "gear", "throttle", "engine_torque", "converter_sr", "speed");
                double[] phaseEnd = { 2.0, 4.0, 7.0, 10.0 };
                var probe = new CarProbe(w, 0);
                Dyn.Drive(w, phaseEnd[3], 10, (t, f) =>
                {
                    if (t < phaseEnd[0]) return new DriverInput { brake = 1f, handbrake = 1f, gear = 0 };
                    if (t < phaseEnd[1]) return new DriverInput { brake = 1f, handbrake = 1f, gear = DriverInput.Drive };
                    if (t < phaseEnd[2]) return new DriverInput { throttle = 1f, brake = 1f, handbrake = 1f, gear = 0 };
                    return new DriverInput { brake = 1f, handbrake = 1f, gear = 0 };
                }, (t, f) =>
                {
                    var st = w.vehicleState[b.vehicleIndex];
                    int ph = t <= phaseEnd[0] ? 0 : t <= phaseEnd[1] ? 1 : t <= phaseEnd[2] ? 2 : 3;
                    s.Add(t, ph, st.engineRpm, st.gear, st.throttle, st.engineTorque, st.converterSR, f.speed);
                    return true;
                }, probe);
                s.Write(ctx.FilePath(r, "idle_limiter.csv"));
                double Mean(int ph, double from, double to, int col, out double min, out double max)
                {
                    double sum = 0; int n = 0; min = double.MaxValue; max = double.MinValue;
                    for (int i = 0; i < s.Count; i++)
                        if ((int)s[i][1] == ph && s[i][0] >= from && s[i][0] <= to)
                        {
                            sum += s[i][col]; n++; min = math.min(min, s[i][col]); max = math.max(max, s[i][col]);
                        }
                    return n > 0 ? sum / n : double.NaN;
                }
                double idleN = Mean(0, 1.0, 2.0, 2, out double nMin, out double nMax);
                r.NearAbs("idle in neutral: mean engine speed (1-2 s)", idleN, pt.idleRpm, 25.0, "rpm");
                r.Max("idle in neutral: speed band (max - min)", nMax - nMin, 30.0, "rpm");
                double idleD = Mean(1, 3.0, 4.0, 2, out double dMin, out double dMax);
                r.NearAbs("idle in drive against the brakes (converter load): mean engine speed", idleD, pt.idleRpm, 50.0, "rpm");
                r.Info("idle in drive: speed band", dMax - dMin, "rpm");
                double limMax = Mean(2, 4.0, 7.0, 2, out _, out double limPeak);
                double limMean = Mean(2, 6.0, 7.0, 2, out double limLo, out double limHi);
                r.Max("full throttle in neutral: peak engine speed (fuel cut 6,200 rpm)", limPeak, pt.revLimitRpm + 150.0, "rpm");
                r.NearAbs("rev limiter: mean engine speed over the last second", limMean, pt.revLimitRpm - 50.0, 120.0, "rpm");
                r.Info("rev limiter: bounce band over the last second", limHi - limLo, "rpm", $"mean of the run {limMax:F0} rpm");
                // free-revving time 1,000 -> 6,000 rpm
                double t1 = double.NaN, t6 = double.NaN;
                for (int i = 0; i < s.Count; i++)
                    if ((int)s[i][1] == 2)
                    {
                        if (double.IsNaN(t1) && s[i][2] >= 1000) t1 = s[i][0];
                        if (double.IsNaN(t6) && s[i][2] >= 6000) t6 = s[i][0];
                    }
                r.Info("free revving in neutral: 1,000 -> 6,000 rpm", t6 - t1, "s", "engine inertia 0.30 kg m^2");
                double back = Mean(3, 9.5, 10.0, 2, out _, out _);
                double tIdle = double.NaN;
                for (int i = 0; i < s.Count; i++)
                    if ((int)s[i][1] == 3 && double.IsNaN(tIdle) && s[i][2] <= pt.idleRpm + 50.0)
                        tIdle = s[i][0] - phaseEnd[2];
                r.NearAbs("throttle released in neutral: back to idle (2.5-3 s after the release)", back, pt.idleRpm, 40.0, "rpm");
                r.Info("throttle released in neutral: time from the rev limiter to idle + 50 rpm", tIdle, "s", "friction and pumping torque only, then the idle controller");
            }

            // (c) gear ratios: steady cruise in each manual gear at about 2,500 rpm; measured engine (turbine) speed over
            //     the measured driven-wheel rotation, and road speed per 1,000 rpm
            {
                var s = new Series("gear", "speed_kmh", "rpm", "converter_sr", "locked", "wheel_omega", "ratio_measured", "ratio_nominal", "kmh_per_1000");
                double worst = 0.0;
                for (int g = 1; g <= pt.gearRatios.Length; g++)
                {
                    double gNom = pt.gearRatios[g - 1] * pt.finalDrive;
                    double v = math.max(2500.0 / RpmPerRad / gNom * pt.rollingRadius, 6.0);
                    using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f);
                    var b = w.bodies[0];
                    var probe = new CarProbe(w, 0);
                    Dyn.LaunchAt(w, v);
                    var f0 = probe.Frame();
                    var robot = new DriverRobot(w.bodies[0].prm) { path = Straight(f0), targetSpeed = (t, a) => v, gear = g };
                    double sumR = 0, sumW = 0, sumE = 0, sumV = 0, sumSr = 0, sumL = 0;
                    int n = 0;
                    Dyn.Drive(w, 3.0, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
                    {
                        if (t < 1.5) return true;
                        var st = w.vehicleState[b.vehicleIndex];
                        double we = st.engineOmega, sr = st.locked != 0 ? 1.0 : math.max(st.converterSR, 0.0);
                        double ww = DrivenOmega(w);
                        sumR += ww > 1e-3 ? we * sr / ww : 0; sumW += ww; sumE += st.engineRpm; sumV += f.speed; sumSr += sr; sumL += st.locked;
                        n++;
                        return true;
                    }, probe);
                    double ratio = sumR / n, rpm = sumE / n, kmh = sumV / n / Kmh;
                    s.Add(g, kmh, rpm, sumSr / n, sumL / n, sumW / n, ratio, gNom, kmh / rpm * 1000.0);
                    worst = math.max(worst, math.abs(ratio / gNom - 1.0));
                    r.Info($"gear {g}: turbine / driven wheel speed ratio (nominal {gNom:F3})", ratio, "",
                        $"{kmh:F1} km/h at {rpm:F0} rpm, {kmh / rpm * 1000.0:F2} km/h per 1,000 rpm, lock-up {(sumL / n > 0.5 ? "closed" : $"open, SR {sumSr / n:F3}")}");
                }
                s.Write(ctx.FilePath(r, "gear_ratios.csv"));
                r.Max("gear ratios 1-8: worst deviation of the measured ratio from gearbox x final drive", worst, 0.015);
            }

            // (d) 0-100 km/h: traction control on and off; (g) wheelspin on launch (traction control off)
            double best = double.MaxValue, bestRoll = double.MaxValue;
            foreach (bool tc in new[] { true, false })
            {
                // without traction control the tires spin up to a slip ratio of ~6 and the car needs longer to 100 km/h
                var L = Launch(ctx, r, tc ? "launch_tc" : "launch_no_tc", tc, null, tc ? 7.0 : 12.0);
                string label = tc ? "traction control on" : "traction control off";
                r.Info($"0-100 km/h, full throttle, {label}", L.t100, "s", $"0-60 mph {L.t60mph:F2} s; with a 1-ft rollout (magazine timing) 0-100 {L.t100Roll:F2} s, 0-60 mph {L.t60Roll:F2} s");
                r.Info($"launch, {label}: peak driven-wheel slip ratio", L.slipPeak, "", $"mean acceleration over the first second {L.a1 / Dyn.G:F2} g, peak squat {L.squat:F2} deg");
                r.Info($"launch, {label}: peak squat (cabin floor, nose up)", L.squat, "deg");
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
                    r.Max("traction control: driven-wheel slip ratio above 36 km/h, 95th percentile", L.slipAfter, 0.35);
                    r.Info("traction control: peak slip ratio above 36 km/h (gearshifts)", L.slipAfterPeak, "", "target 0.30 at 18 km/h -> 0.20 at 90 km/h (D-047)");
                }
            }
            // the brief's 3.5-4.0 s are road-test figures, timed with the 1-ft rollout (D-048); from the throttle as info
            r.Info("0-100 km/h best, timed from the throttle application", best, "s", "the rollout figure adds the first 0.3 m");
            r.Max("0-100 km/h best, 1-ft rollout like the published figures (brief 4.13: 3.5-4.0 s, +15 %)", bestRoll, 4.0 * 1.15, "s");
            r.Min("0-100 km/h best not faster than the brief's range (-15 %)", bestRoll, 3.5 * 0.85, "s");

            // (e) top speed: full throttle in drive from 270 km/h on the straight with the robot steering; the asymptote
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

            // (f) engine braking and coast-down from 100 km/h: neutral, drive, manual third
            {
                double DecelRun(string tag, int gear, out double meanSpeed)
                {
                    using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f);
                    var b = w.bodies[0];
                    var probe = new CarProbe(w, 0);
                    Dyn.LaunchAt(w, 102.0 * Kmh);
                    var f0 = probe.Frame();
                    var robot = new DriverRobot(b.prm) { path = Straight(f0), pedalOverride = (t, f) => new DriverInput { gear = gear } };
                    var s = new Series("t", "speed_kmh", "rpm", "gear", "engine_torque", "shaft_torque");
                    double tA = double.NaN, tB = double.NaN, sumV = 0; int n = 0;
                    // 100 -> 80 km/h: the neutral coast-down takes ~20 s (100 -> 60 km/h would take ~40 s)
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
                    return (100.0 - 80.0) * Kmh / (tB - tA);
                }
                double aN = DecelRun("neutral", 0, out double vN);
                double aD = DecelRun("drive", DriverInput.Drive, out _);
                double a3 = DecelRun("third", 3, out double v3);
                var b0 = LoadHellcat(ctx);
                double mass = 2040.0;
                double rho = b0.prm.aero.airDensity, cda = b0.prm.aero.dragArea;
                // effective rolling resistance from the neutral coast-down (aero removed at the mean speed of the window)
                double fAero = 0.5 * rho * cda * vN * vN;
                double crr = (mass * aN - fAero) / (mass * Dyn.G);
                r.Info("coast-down in neutral 100 -> 80 km/h: mean deceleration", aN / Dyn.G, "g", $"{aN:F3} m/s^2 at {vN / Kmh:F0} km/h mean");
                r.Info("coast-down: effective rolling resistance coefficient (aero CdA removed)", crr, "",
                    $"aero {fAero:F0} N at {vN / Kmh:F0} km/h; explicit surface term 0.012 x {b0.prm.surfaces[0].rollingResistance / 0.012:F2} plus tire hysteresis");
                r.Min("coast-down: effective rolling resistance at least a tire's (0.007)", crr, 0.007);
                r.Max("coast-down: effective rolling resistance at most 0.025 (no hidden drag)", crr, 0.025);
                r.Info("coast in drive (throttle off, automatic) 100 -> 80 km/h", aD / Dyn.G, "g", $"{aD:F3} m/s^2");
                // engine braking in third at the mean speed: friction torque x overall ratio / efficiency / rolling radius
                double g3 = pt.gearRatios[2] * pt.finalDrive;
                double rpm3 = v3 / pt.rollingRadius * g3 * RpmPerRad;
                double tFric = pt.frictionTorque0 + pt.frictionTorquePerRpm * rpm3;
                double fModel = tFric * g3 / pt.efficiency / pt.rollingRadius;
                double fMeas = mass * (a3 - aN);
                r.Info("engine braking in third, 100 -> 80 km/h: deceleration", a3 / Dyn.G, "g", $"{a3:F3} m/s^2");
                r.Near("engine braking in third: extra retarding force over neutral vs friction torque x ratio / efficiency / radius", fMeas, fModel, 0.3, "N");
            }
            r.notes.Add("Inputs come from the driver robot (DriverRobot: PI speed control, pure pursuit on the rear axle). " +
                        "0-100 km/h is timed from the throttle application on a settled car held on the brakes in drive; the 1-ft rollout figures follow the magazine convention (Car and Driver).");
            return r;
        }

        public struct LaunchResult
        {
            public double t100, t100Roll, t60mph, t60Roll, slipPeak, slipAfter, slipAfterPeak, a1, squat;
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
                "shaft_torque", "tc_factor", "locked", "converter_sr", "lateral", "slip_speed",
                "load_RR", "load_RL", "slip_RR", "slip_RL", "fx_RR", "fx_RL", "fz_RR", "fz_RL");
            int iRR = probe.WheelIndex("RR"), iRL = probe.WheelIndex("RL");
            w.ClearContactImp();
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
                double chunkT = 10 * w.dt;
                double3 jr = probe.TreadImpulse(iRR) / chunkT, jl = probe.TreadImpulse(iRL) / chunkT;
                w.ClearContactImp();
                var wsR = w.wheelState[b.wheelStart + iRR];
                var wsL = w.wheelState[b.wheelStart + iRL];
                s.Add(t, f.speed / Kmh, dist, st.engineRpm, st.gear, slip, acc / Dyn.G, f.pitchDeg - f0.pitchDeg, st.engineTorque,
                    st.shaftTorque, st.tcFactor, st.locked, st.converterSR, robot.lateral, st.tcSlipSpeed,
                    wsR.load, wsL.load, wsR.slipRatio, wsL.slipRatio, math.dot(jr, f.forward), math.dot(jl, f.forward), math.dot(jr, f.up), math.dot(jl, f.up));
                return double.IsNaN(res.t100) || t < res.t100 + 0.5;
            }, probe);
            if (r != null && tag != null)
                s.Write(ctx.FilePath(r, $"{tag}.csv"));
            // the slip ratio the traction control holds, above 5 m/s (below, the tire grips best at slip speeds of ~1-2 m/s,
            // a slip ratio of 0.3-1, and the target has a slip-speed floor, D-047)
            // 95th percentile and peak above 10 m/s (short peaks at the shifts are the gearbox's inertia phase)
            var above = new List<double>();
            for (int i = 0; i < s.Count; i++)
                if (s[i][1] * Kmh > 10.0)
                    above.Add(s[i][5]);
            above.Sort();
            res.slipAfter = above.Count > 0 ? above[(int)(0.95 * (above.Count - 1))] : double.NaN;
            res.slipAfterPeak = above.Count > 0 ? above[above.Count - 1] : double.NaN;
            res.squat = -pitchMin;
            return res;
        }

        static double MaxAfter(Series s, int col, double t0)
        {
            double v = double.MinValue;
            for (int i = 0; i < s.Count; i++)
                if (s[i][0] >= t0)
                    v = math.max(v, s[i][col]);
            return v;
        }

        // ------------------------------------------------------------------ T13

        public struct StopResult
        {
            public double distance, meanDecel, lateral, lockedTime, peakDive;
        }

        /// <summary>One stop from 100 km/h (full pedal in 0.1 s, the robot holding 100 km/h before it): ABS on / off, an
        /// optional fixed steering input after 0.3 s (else the robot steers).</summary>
        public static StopResult Stop(ValidationContext ctx, TestResult r, string tag, bool abs, double steer, Action<SimParamsDef> tweak = null)
        {
            {
                using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f, tweak);
                var b = w.bodies[0];
                var probe = new CarProbe(w, 0);
                Dyn.LaunchAt(w, 100.0 * Kmh);
                var f0 = probe.Frame();
                var path = Straight(f0);
                var robot = new DriverRobot(b.prm) { path = path, targetSpeed = (t, a) => 100.0 * Kmh };
                double tBrake = double.NaN, vBrake = 100.0 * Kmh, d = 0, locked = 0, dive = 0;
                double3 pBrake = double3.zero;
                double pitch0 = f0.pitchDeg;
                var s = new Series("t", "speed_kmh", "distance", "decel_g", "slip_FR", "slip_FL", "slip_RR", "slip_RL",
                    "abs_FR", "abs_FL", "abs_RR", "abs_RL", "pitch_deg", "lateral", "steer");
                double vPrev = f0.speed, tPrev = 0;
                Dyn.Drive(w, 9.0, 10, (t, f) =>
                {
                    if (double.IsNaN(tBrake))
                        return robot.Control(t, 10 * w.dt, f);
                    double tb = t - tBrake;
                    var inp = new DriverInput
                    {
                        brake = (float)math.saturate(tb / 0.1),
                        gear = DriverInput.Drive,
                        flags = abs ? DriverInput.FlagAbs : 0,
                        steer = tb > 0.3 ? (float)steer : 0f,
                    };
                    if (steer == 0.0)
                        inp.steer = robot.Control(t, 10 * w.dt, f).steer;
                    return inp;
                }, (t, f) =>
                {
                    if (double.IsNaN(tBrake) && t > 0.6 && math.abs(f.speed - 100.0 * Kmh) < 0.3 * Kmh)
                    {
                        tBrake = t;
                        vBrake = f.speed;
                        pBrake = f.com;
                        pitch0 = f.pitchDeg;
                    }
                    double dtS = math.max(t - tPrev, 1e-6);
                    double acc = (vPrev - f.speed) / dtS;
                    vPrev = f.speed;
                    tPrev = t;
                    if (!double.IsNaN(tBrake))
                    {
                        d = math.length(new double2(f.com.x - pBrake.x, f.com.z - pBrake.z));
                        bool anyLocked = false;
                        for (int k = 0; k < b.wheelCount; k++)
                            anyLocked |= w.wheelState[b.wheelStart + k].slipRatio < -0.9f;
                        if (anyLocked && f.speed > 1.0) locked += dtS;
                        dive = math.max(dive, f.pitchDeg - pitch0);
                    }
                    var ws = w.wheelState;
                    int i0 = b.wheelStart;
                    s.Add(t, f.speed / Kmh, d, acc / Dyn.G, ws[i0].slipRatio, ws[i0 + 1].slipRatio, ws[i0 + 2].slipRatio, ws[i0 + 3].slipRatio,
                        ws[i0].absFactor, ws[i0 + 1].absFactor, ws[i0 + 2].absFactor, ws[i0 + 3].absFactor, f.pitchDeg - pitch0,
                        math.dot(f.com - f0.com, f0.right), w.vehicleState[b.vehicleIndex].steer);
                    return double.IsNaN(tBrake) || f.speed > 0.05;
                }, probe);
                if (r != null && tag != null)
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
            double dAbs = sa.distance, aAbs = sa.meanDecel, lockAbs = sa.lockedTime, diveAbs = sa.peakDive;
            r.Max("100-0 km/h with ABS: stopping distance (brief 4.13: 33-38 m, +15 %)", dAbs, 38.0 * 1.15, "m");
            r.Min("100-0 km/h with ABS: stopping distance not shorter than the brief's range (-15 %)", dAbs, 33.0 * 0.85, "m");
            r.Info("100-0 km/h with ABS: mean deceleration", aAbs / Dyn.G, "g", $"vs the Widebody's 70-0 mph 46.9 m (1.06 g, S11) -> about 37 m from 100 km/h");
            r.Max("ABS: time with a wheel locked (slip ratio below -0.9) above 1 m/s", lockAbs, 0.25, "s");
            r.Info("braking dive at 100-0 km/h (cabin floor, nose down)", diveAbs, "deg");
            var sn = Stop(ctx, r, "noabs_100_0", false, 0.0);
            double dNo = sn.distance, aNo = sn.meanDecel, lockNo = sn.lockedTime;
            r.Info("100-0 km/h without ABS: stopping distance", dNo, "m", $"mean deceleration {aNo / Dyn.G:F3} g, {lockNo:F2} s with a wheel locked");
            r.Min("ABS toggle: ABS shortens the stop", dNo - dAbs, 0.0, "m");
            r.Min("ABS toggle: without ABS the wheels lock", lockNo, 0.5, "s");
            double latAbs = Stop(ctx, r, "abs_steer", true, 0.3).lateral;
            double latNo = Stop(ctx, r, "noabs_steer", false, 0.3).lateral;
            r.Info("steering while braking (input 0.3 after 0.3 s): lateral displacement with / without ABS", latAbs, "m", $"without {latNo:F2} m");
            r.Min("ABS keeps the car steerable: lateral displacement with ABS over without", latAbs / math.max(latNo, 0.05), 2.0);

            // handbrake at 50 km/h: the rear wheels lock, the fronts keep rolling
            {
                using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f);
                var b = w.bodies[0];
                var probe = new CarProbe(w, 0);
                Dyn.LaunchAt(w, 50.0 * Kmh);
                var f0 = probe.Frame();
                var robot = new DriverRobot(b.prm) { path = Straight(f0), pedalOverride = (t, f) => new DriverInput { handbrake = t > 0.3 ? 1f : 0f, gear = 0 } };
                var s = new Series("t", "speed_kmh", "slip_front_min", "slip_rear_min", "decel_g", "yaw_dps");
                double tLock = double.NaN, vPrev = f0.speed, tPrev = 0, frontMin = 0, sumA = 0; int nA = 0;
                double hPrev = f0.heading;
                Dyn.Drive(w, 3.0, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
                {
                    double dtS = math.max(t - tPrev, 1e-6);
                    double acc = (vPrev - f.speed) / dtS;
                    double yaw = Dyn.WrapDeg(math.degrees(f.heading - hPrev)) / dtS;
                    vPrev = f.speed; tPrev = t; hPrev = f.heading;
                    double sf = MinSlip(w, true), sr = MinSlip(w, false);
                    if (t > 0.3 && double.IsNaN(tLock) && sr < -0.9) tLock = t - 0.3;
                    if (t > 0.8 && f.speed > 2.0) { frontMin = math.min(frontMin, sf); sumA += acc; nA++; }
                    s.Add(t, f.speed / Kmh, sf, sr, acc / Dyn.G, yaw);
                    return f.speed > 0.5;
                }, probe);
                s.Write(ctx.FilePath(r, "handbrake_50.csv"));
                r.Max("handbrake at 50 km/h: rear wheels locked (slip ratio < -0.9) within", double.IsNaN(tLock) ? 99.0 : tLock, 0.5, "s");
                r.Min("handbrake: front wheels keep rolling (lowest front slip ratio)", frontMin, -0.15);
                double aHb = nA > 0 ? sumA / nA / Dyn.G : 0;
                r.NearAbs("handbrake: deceleration on the rear axle alone (43 % of the weight x sliding friction)", aHb, 0.43 * 0.95, 0.12, "g");
            }

            // fade-free: three stops from 100 km/h in a row, accelerating back in between
            {
                using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f);
                var b = w.bodies[0];
                var probe = new CarProbe(w, 0);
                Dyn.LaunchAt(w, 100.0 * Kmh);
                var f0 = probe.Frame();
                var robot = new DriverRobot(b.prm) { path = Straight(f0, 6000.0), targetSpeed = (t, a) => 100.0 * Kmh };
                var dists = new List<double>();
                double vStart = 100.0 * Kmh;
                int phase = 0;   // 0 cruise to 100, 1 braking
                double steady = 0.0;
                double3 p0 = double3.zero;
                double tPhase = 0;
                var s = new Series("t", "speed_kmh", "phase", "stops");
                Dyn.Drive(w, 60.0, 10, (t, f) =>
                {
                    if (phase == 1)
                    {
                        var inp = robot.Control(t, 10 * w.dt, f);
                        return new DriverInput { brake = (float)math.saturate((t - tPhase) / 0.1), steer = inp.steer, gear = DriverInput.Drive, flags = DriverInput.FlagAbs };
                    }
                    return robot.Control(t, 10 * w.dt, f);
                }, (t, f) =>
                {
                    // brake from a steady cruise: 1.5 s within 1 km/h of 100 km/h (like the first stop, launched at 100 km/h)
                    if (phase == 0)
                        steady = math.abs(f.speed - 100.0 * Kmh) < 1.0 * Kmh ? steady + 10 * w.dt : 0.0;
                    if (phase == 0 && t - tPhase > 1.0 && steady >= 1.5 && math.abs(f.speed - 100.0 * Kmh) < 0.3 * Kmh)
                    {
                        phase = 1;
                        tPhase = t;
                        p0 = f.com;
                        vStart = f.speed;
                    }
                    else if (phase == 1 && f.speed < 0.05)
                    {
                        dists.Add(math.length(new double2(f.com.x - p0.x, f.com.z - p0.z)) * math.pow(100.0 * Kmh / vStart, 2.0));
                        phase = 0;
                        tPhase = t;
                    }
                    s.Add(t, f.speed / Kmh, phase, dists.Count);
                    return dists.Count < 3;
                }, probe);
                s.Write(ctx.FilePath(r, "repeated_stops.csv"));
                double lo = double.MaxValue, hi = 0;
                foreach (double dd in dists) { lo = math.min(lo, dd); hi = math.max(hi, dd); }
                r.Min("fade-free: stops completed", dists.Count, 3);
                r.Info("repeated stops from 100 km/h: distances", dists.Count > 0 ? dists[0] : double.NaN, "m", string.Join(" / ", dists.ConvertAll(x => x.ToString("F2"))));
                r.Max("fade-free: spread of the three stopping distances", dists.Count > 0 ? (hi - lo) / lo : 1.0, 0.03);
            }
            r.notes.Add("No brake thermal model: the brakes cannot fade, the repeated stops check that the stop is repeatable after the drive cycle (C&D: 'with no fade').");
            return r;
        }
    }
}
