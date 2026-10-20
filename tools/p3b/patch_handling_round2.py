"""One-off (P3b): T10 / T11 / T14 round 2 - curbs end outboard of the exhaust (only the right wheels meet them), roll
gradient against the design plus the tire compliance, understeer gradient on the circle; on-centre ratio from the
first input step; the speed-sensitive reduction checked on the command (the road-wheel angle reported); slalom at
50 km/h; the skidpad window also needs a small body slip angle; the ramp jump checks the running gear (body damage is
reported). Driver robot: stronger cross-track integral at low speed, falling with the speed squared above 15 m/s."""
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
    # curbs: inner end at x 0.55 (the exhaust runs at x 0.22-0.54, 155 mm up)
    ('''                // 6 m long along (sin 45, 0, cos 45) from x 0.1 to 4.3 m: only the right wheels (x 0.83) meet it, at z ~6.6 m
                statics.AddBox(new float3(2.2f, 0.12f - 0.5f, 8.0f), quaternion.RotateY(math.radians(45f)), new float3(0.15f, 0.5f, 3.0f), "concrete", "curb");''',
     '''                // 5.3 m long along (sin 45, 0, cos 45) from x 0.55 to 4.3 m: only the right wheels (x 0.83) meet it, at z ~6.6 m
                // (further in it ran under the exhaust, 155 mm up at x 0.22-0.54, and tore its hangers)
                statics.AddBox(new float3(2.424f, 0.12f - 0.5f, 8.19f), quaternion.RotateY(math.radians(45f)), new float3(0.15f, 0.5f, 2.65f), "concrete", "curb");'''),
    ('''                    statics.AddBox(new float3(2.2f, 0.12f - 0.5f, 12.0f), quaternion.RotateY(math.radians(45f)), new float3(0.15f, 0.5f, 3.0f), "concrete", "curb");''',
     '''                    statics.AddBox(new float3(2.424f, 0.12f - 0.5f, 12.22f), quaternion.RotateY(math.radians(45f)), new float3(0.15f, 0.5f, 2.65f), "concrete", "curb");'''),
    # roll gradient: design + tires; understeer gradient
    ('''                r.Info("roll gradient in steady cornering (cabin floor vs the ground, 0.25-0.6 g)", grad, "deg/g",
                    $"fit R^2 {r2:F2}; design 2.3 deg/g (springs + bars, tool suspension_design.py); without the anti-roll bars {gradNo:F2} deg/g (R^2 {r2n:F2})");
                r.Near("roll gradient vs the design 2.3 deg/g (+-30 %: tire compliance and the roll centres add)", grad, 2.3, 0.3, "deg/g");
                r.Min("anti-roll bars: the roll gradient without them over with them (design ~2.1)", gradNo / math.max(grad, 1e-6), 1.5);''',
     '''                r.Info("roll gradient in steady cornering (cabin floor vs the ground, 0.25-0.6 g)", grad, "deg/g",
                    $"fit R^2 {r2:F2}; without the anti-roll bars {gradNo:F2} deg/g (R^2 {r2n:F2})");
                // design: 2.3 deg/g of the suspension (suspension_design.py, D-025) plus the tires: the whole car's load
                // transfer (2040 kg x 0.52 m) on the tire roll stiffness (310 kN/m x 1.67 m^2 / 2 per axle) is 0.7 deg/g
                r.Near("roll gradient vs the design 2.3 + 0.7 (tires) = 3.0 deg/g (+-15 %)", grad, 3.0, 0.15, "deg/g");
                r.Min("anti-roll bars: the roll gradient without them over with them (design 5.5 / 3.0 = 1.8)", gradNo / math.max(grad, 1e-6), 1.5);
                // understeer gradient: road-wheel angle against a_y on the circle (the Ackermann angle L / R is constant)
                var xs = new List<double>(); var ys = new List<double>();
                for (int i = 0; i < s.Count; i++)
                    if (s[i][0] >= 3.0 && s[i][2] >= 0.25 && s[i][2] <= 0.6) { xs.Add(s[i][2]); ys.Add(-s[i][7]); }
                if (xs.Count > 10)
                {
                    var fu = Dyn.Fit(xs, ys);
                    r.Info("understeer gradient on the circle (road-wheel angle vs a_y, 0.25-0.6 g; > 0 understeer)", fu.slope, "deg/g",
                        $"fit R^2 {fu.r2:F2}; Ackermann angle {math.degrees(2.951 / SkidpadRadius):F2} deg; passenger cars 1-4 deg/g");
                }'''),
    # on-centre slope relative to the angle at zero input
    ('''                double flMax = 0, frMax = 0, flMin = 0, frMin = 0, slope = double.NaN;''',
     '''                double flMax = 0, frMax = 0, flMin = 0, frMin = 0, slope = double.NaN, mean0 = double.NaN;'''),
    ('''                    if (math.abs(u - 0.1) < 1e-6 && double.IsNaN(slope)) slope = 0.5 * (fl + fr) / 0.1;''',
     '''                    if (math.abs(u) < 1e-6 && double.IsNaN(mean0)) mean0 = 0.5 * (fl + fr);
                    if (math.abs(u - 0.1) < 1e-6 && double.IsNaN(slope)) slope = (0.5 * (fl + fr) - mean0) / 0.1;'''),
    # speed-sensitive reduction: the command
    ('''                var s = new Series("speed", "rwa_deg", "expected_scale", "measured_scale");
                double rwa5 = double.NaN, worst = 0;''',
     '''                var s = new Series("speed", "rwa_deg", "expected_scale", "command_scale", "rwa_scale");
                double rwa5 = double.NaN, worst = 0;'''),
    ('''                    double peak = 0;
                    Dyn.Drive(w, 0.6, 10, (t, f) => new DriverInput { steer = t < 0.4 ? 0.15f : 0f, throttle = 0.3f, gear = DriverInput.Drive }, (t, f) =>
                    {
                        peak = math.max(peak, 0.5 * (probe.RoadWheelDeg(iFL, f) + probe.RoadWheelDeg(iFR, f)));
                        return true;
                    }, probe);
                    if (double.IsNaN(rwa5)) rwa5 = peak;
                    double expected = v > st.speedReductionStart ? math.lerp(1.0, st.speedReductionAt60, math.saturate((v - st.speedReductionStart) / (60.0 - st.speedReductionStart))) : 1.0;
                    double measured = peak / math.max(rwa5, 1e-6);
                    worst = math.max(worst, math.abs(measured / expected - 1.0));
                    s.Add(v, peak, expected, measured);
                    r.Info($"speed-sensitive steering at {v / Kmh:F0} km/h: road-wheel angle for a 0.15 input", peak, "deg", $"scale {measured:F2} vs the design {expected:F2}");''',
     '''                    double peak = 0, cmd = 0;
                    Dyn.Drive(w, 0.6, 10, (t, f) => new DriverInput { steer = t < 0.4 ? 0.15f : 0f, throttle = 0.3f, gear = DriverInput.Drive }, (t, f) =>
                    {
                        peak = math.max(peak, 0.5 * (probe.RoadWheelDeg(iFL, f) + probe.RoadWheelDeg(iFR, f)));
                        cmd = math.max(cmd, w.vehicleState[b.vehicleIndex].steer);
                        return true;
                    }, probe);
                    if (double.IsNaN(rwa5)) rwa5 = peak;
                    double expected = v > st.speedReductionStart ? math.lerp(1.0, st.speedReductionAt60, math.saturate((v - st.speedReductionStart) / (60.0 - st.speedReductionStart))) : 1.0;
                    double measured = cmd / 0.15, rwaScale = peak / math.max(rwa5, 1e-6);
                    worst = math.max(worst, math.abs(measured / expected - 1.0));
                    s.Add(v, peak, expected, measured, rwaScale);
                    r.Info($"speed-sensitive steering at {v / Kmh:F0} km/h: road-wheel angle for a 0.15 input", peak, "deg",
                        $"command scale {measured:F3} vs the design {expected:F3}; road-wheel angle {rwaScale:F2} of the 5 m/s value (the tires' aligning torque on the steering compliance)");'''),
    ('''                r.Max("speed-sensitive reduction: measured scale vs the design curve (worst)", worst, 0.15);''',
     '''                r.Max("speed-sensitive reduction: steering command vs the design curve (worst)", worst, 0.02);'''),
    # slalom at 50 km/h, robot look-ahead
    ('''            // (a) slalom: 6 gates 18 m apart, +-1.0 m, 60 km/h''',
     '''            // (a) slalom: 6 gates 18 m apart, +-1.0 m, 50 km/h (peak 0.6 g on the path; at 60 km/h it is 0.86 g, the limit)'''),
    ('''                double v = 60.0 * Kmh;
                Dyn.LaunchAt(w, v);
                var path = PolyPath.Slalom(f0.rearAxle.z + 20.0, 18.0, 1.0, 6, 40.0, 40.0);
                var robot = new DriverRobot(b.prm) { path = path, targetSpeed = (t, a) => v };
                var s = new Series("t", "speed_kmh", "path_error", "ay_g", "yaw_dps", "roll_deg");''',
     '''                double v = 50.0 * Kmh;
                Dyn.LaunchAt(w, v);
                var path = PolyPath.Slalom(f0.rearAxle.z + 20.0, 18.0, 1.0, 6, 40.0, 40.0);
                var robot = new DriverRobot(b.prm) { path = path, targetSpeed = (t, a) => v, lookMin = 5.0, lookGain = 0.4 };
                var s = new Series("t", "speed_kmh", "path_error", "ay_g", "yaw_dps", "roll_deg", "beta_deg");'''),
    ('''                    s.Add(t, f.speed / Kmh, robot.lateral, ay, yaw, f.rollDeg);
                    hPrev = f.heading; tPrev = t; velPrev = f.vel;
                    return true;
                }, probe);
                s.Write(ctx.FilePath(r, "slalom_60.csv"));
                r.Max("slalom 18 m / +-1.0 m at 60 km/h: largest path error", MaxAbs(s, 2, 1.0), 0.8, "m");
                r.Info("slalom: peak lateral acceleration / roll", MaxAbs(s, 3, 1.0), "g", $"roll {MaxAbs(s, 5, 1.0):F2} deg, yaw rate {MaxAbs(s, 4, 1.0):F1} deg/s");
                r.Min("slalom: speed held (lowest)", Mean(s, 1, s[s.Count - 1][0] - 0.5, s[s.Count - 1][0]), 55.0, "km/h");''',
     '''                    s.Add(t, f.speed / Kmh, robot.lateral, ay, yaw, f.rollDeg, math.degrees(math.atan2(f.lateralVel, math.max(f.speed, 0.1))));
                    hPrev = f.heading; tPrev = t; velPrev = f.vel;
                    return true;
                }, probe);
                s.Write(ctx.FilePath(r, "slalom_50.csv"));
                r.Max("slalom 18 m / +-1.0 m at 50 km/h: largest path error", MaxAbs(s, 2, 1.0), 0.8, "m");
                r.Max("slalom: largest body slip angle (no slide)", MaxAbs(s, 6, 1.0), 4.0, "deg");
                r.Info("slalom: peak lateral acceleration / roll", MaxAbs(s, 3, 1.0), "g", $"roll {MaxAbs(s, 5, 1.0):F2} deg, yaw rate {MaxAbs(s, 4, 1.0):F1} deg/s");
                r.Min("slalom: speed held (lowest)", Mean(s, 1, s[s.Count - 1][0] - 0.5, s[s.Count - 1][0]), 45.0, "km/h");'''),
    # skidpad window: steady (small body slip)
    ('''            // (b) skidpad R 45.72 m: lateral acceleration rising 0.6 -> 1.15 g over 40 s; the limit is the highest 2 s
            //     mean of a_y while the path error stays below 1.5 m''',
     '''            // (b) skidpad R 45.72 m: lateral acceleration rising 0.6 -> 1.15 g over 40 s; the limit is the highest 2 s
            //     mean of a_y while the car holds the circle (path error below 1.5 m) without sliding (body slip below 6 deg)'''),
    ('''                    double sum = 0, errMax = 0; int n = 0;
                    for (int k = i; k >= 0 && s[k][0] >= t1 - 2.0; k--) { sum += s[k][2]; errMax = math.max(errMax, math.abs(s[k][4])); n++; }
                    if (errMax < 1.5 && n > 0 && sum / n > best) { best = sum / n; tBest = t1; }''',
     '''                    double sum = 0, errMax = 0, betaMax = 0; int n = 0;
                    for (int k = i; k >= 0 && s[k][0] >= t1 - 2.0; k--)
                    {
                        sum += s[k][2]; errMax = math.max(errMax, math.abs(s[k][4])); betaMax = math.max(betaMax, math.abs(s[k][8])); n++;
                    }
                    if (errMax < 1.5 && betaMax < 6.0 && n > 0 && sum / n > best) { best = sum / n; tBest = t1; }'''),
    # ramp: running gear
    ('''                r.Max("ramp jump: broken beams", m.brokenBeams, 0);
                r.Info("ramp jump: plastically deformed beams after the landing", m.plasticBeams, "", $"take-off at {tAir:F2} s of flight, landing at {tLand:F2} s");
                dmg.Report(r, "ramp jump");''',
     '''                // a 0.75 m fall nose down 13 deg (the front wheels leave the edge first): the fascia meets the ground, body
                // damage is expected (scenario S5); the running gear must survive and the tires keep their air
                r.Max("ramp jump: broken beams of the running gear (wheels, suspension, steering, subframes)", dmg.RunningGearBroken(), 0);
                r.Max("ramp jump: plastically deformed beams of the running gear", dmg.RunningGearPlastic(), 0);
                double pMinJ = double.MaxValue;
                for (int gq = b.pressureStart; gq < b.pressureStart + b.pressureCount; gq++)
                    pMinJ = math.min(pMinJ, (w.pressureState[gq].pAbs - w.pressureGroups[gq].pAtm) / (w.pressureGroups[gq].gas0 / w.pressureGroups[gq].volume0 - w.pressureGroups[gq].pAtm));
                r.Min("ramp jump: lowest tire gauge pressure vs spawn (no puncture)", pMinJ, 0.95);
                r.Info("ramp jump: broken / plastic beams in all (body included)", m.brokenBeams, "", $"{m.plasticBeams} plastic; take-off flight {tAir:F2} s, landing at {tLand:F2} s");
                dmg.Report(r, "ramp jump");'''),
    # DamageWatch: running gear
    ('''            string Beam(int j)
            {''',
     '''            static readonly HashSet<string> RunningGearMats = new HashSet<string>
            {
                "subframe", "subframe_mount", "kmember", "arm", "link", "tierod", "knuckle", "knuckle_f", "arb_link", "arb_lever",
                "spring_f", "spring_r", "damper_f", "damper_r", "bumpstop_f", "bumpstop_r",
            };

            bool IsRunningGear(int j)
            {
                var bd = b.def.beams[j];
                return RunningGearMats.Contains(bd.mat) || b.def.nodes[bd.a].part.StartsWith("wheel_") || b.def.nodes[bd.b].part.StartsWith("wheel_");
            }

            public int RunningGearBroken()
            {
                int n = 0;
                for (int j = 0; j < b.beamCount; j++)
                    if (w.broken[b.beamStart + j] != 0 && IsRunningGear(j)) n++;
                return n;
            }

            public int RunningGearPlastic()
            {
                int n = 0;
                for (int j = 0; j < b.beamCount; j++)
                {
                    int gj = b.beamStart + j;
                    if (w.broken[gj] == 0 && math.abs(w.rest[gj] - w.SpawnRest(gj)) > 1e-5f && IsRunningGear(j)) n++;
                }
                return n;
            }

            string Beam(int j)
            {'''),
    # peak-stress list: only beams with a limit (deformable or breakable)
    ('''                    if (peak[j] > 0.7f) close.Add((peak[j], j));''',
     '''                    var bs = w.beams[gj];
                    if (peak[j] > 0.7f && (bs.flags & (BeamFlag.Deformable | BeamFlag.Breakable)) != 0) close.Add((peak[j], j));'''),
])

patch("DynamicsCommon.cs", [
    ('''        public double kCross = 0.004;          // rad per m*s of the cross-track integral
        public double crossSpeedExp = 1.0;     // the integral gain falls as (15 m/s / v)^exp above 15 m/s (X16)''',
     '''        public double kCross = 0.012;          // rad per m*s of the cross-track integral (time constant ~5 s on the skidpad)
        public double crossSpeedExp = 2.0;     // the integral gain falls as (15 m/s / v)^exp above 15 m/s (X16: at speed it
                                               // only adds phase lag; this is below the former 0.004 x 15 / v above 45 m/s)'''),
])
print("patched")
