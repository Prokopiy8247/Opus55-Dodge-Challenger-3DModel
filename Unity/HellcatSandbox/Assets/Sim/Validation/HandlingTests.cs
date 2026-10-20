using System;
using System.Collections.Generic;
using Hellcat.Sim.Data;
using Hellcat.Sim.Vehicle;
using Unity.Mathematics;
using static Hellcat.Sim.Validation.ValidationSuite;

namespace Hellcat.Sim.Validation
{
    /// <summary>Validation tests 10 (suspension), 11 (steering) and 14 (drive tests on the map) of brief section 10.</summary>
    public static class HandlingTests
    {
        const double Kmh = 1.0 / 3.6;
        const double SkidpadRadius = 45.72;          // m: the 300-ft skidpad of the road tests

        // ------------------------------------------------------------------ shared

        /// <summary>Damped oscillation x(t) = x_end + exp(-s t) (a cos(w t) + b sin(w t)) fitted by a grid over (w, s) with
        /// linear least squares for (a, b); natural frequency (Hz) and damping ratio.</summary>
        static void FitDamped(IList<double> t, IList<double> x, out double fn, out double zeta, out double r2)
        {
            int n = t.Count;
            double xEnd = 0.0;
            int tail = math.max(1, n / 10);
            for (int i = n - tail; i < n; i++) xEnd += x[i];
            xEnd /= tail;
            double best = double.MaxValue, bw = 0, bs = 0, var0 = 0;
            for (int i = 0; i < n; i++) var0 += (x[i] - xEnd) * (x[i] - xEnd);
            for (double f = 0.4; f <= 4.0; f += 0.01)
            {
                double wd = 2.0 * math.PI * f;
                for (double z = 0.0; z <= 0.95; z += 0.01)
                {
                    double s = z / math.sqrt(math.max(1.0 - z * z, 1e-6)) * wd;
                    double saa = 0, sab = 0, sbb = 0, sxa = 0, sxb = 0;
                    for (int i = 0; i < n; i++)
                    {
                        double e = math.exp(-s * t[i]);
                        double ca = e * math.cos(wd * t[i]), cb = e * math.sin(wd * t[i]), y = x[i] - xEnd;
                        saa += ca * ca; sab += ca * cb; sbb += cb * cb; sxa += y * ca; sxb += y * cb;
                    }
                    double det = saa * sbb - sab * sab;
                    if (math.abs(det) < 1e-18)
                        continue;
                    double a = (sxa * sbb - sxb * sab) / det, b = (sxb * saa - sxa * sab) / det;
                    double res = 0;
                    for (int i = 0; i < n; i++)
                    {
                        double e = math.exp(-s * t[i]);
                        double d = x[i] - xEnd - e * (a * math.cos(wd * t[i]) + b * math.sin(wd * t[i]));
                        res += d * d;
                    }
                    if (res < best) { best = res; bw = wd; bs = s; }
                }
            }
            double wn = math.sqrt(bw * bw + bs * bs);
            fn = wn / (2.0 * math.PI);
            zeta = bs / math.max(wn, 1e-9);
            r2 = var0 > 0 ? 1.0 - best / var0 : 0.0;
        }

        static double Mean(Series s, int col, double t0, double t1)
        {
            double sum = 0; int n = 0;
            for (int i = 0; i < s.Count; i++)
                if (s[i][0] >= t0 && s[i][0] <= t1) { sum += s[i][col]; n++; }
            return n > 0 ? sum / n : double.NaN;
        }

        static double MaxAbs(Series s, int col, double t0, double t1 = double.MaxValue)
        {
            double m = 0;
            for (int i = 0; i < s.Count; i++)
                if (s[i][0] >= t0 && s[i][0] <= t1) m = math.max(m, math.abs(s[i][col]));
            return m;
        }

        static int[] WindupSet(SoftBodyWorld.Body b, int wheel)
        {
            var wd = b.def.wheels[wheel];
            var ids = new int[wd.windupBody.Length];
            for (int k = 0; k < ids.Length; k++) ids[k] = b.nodeStart + wd.windupBody[k];
            return ids;
        }

        static double MeanY(SoftBodyWorld w, IEnumerable<int> ids)
        {
            double y = 0; int n = 0;
            foreach (int i in ids) { y += w.pos[i].y; n++; }
            return n > 0 ? y / n : 0.0;
        }

        static bool IsSprung(VehicleDef d, int local) => !d.nodes[local].part.StartsWith("wheel_");

        /// <summary>Faces of a convex mesh wound so their normals point away from the centroid (AddConvexMesh takes the
        /// normal from the first three vertices).</summary>
        static List<int[]> OrientOutward(IReadOnlyList<float3> v, List<int[]> faces)
        {
            float3 c = float3.zero;
            foreach (var p in v) c += p;
            c /= v.Count;
            var outF = new List<int[]>();
            foreach (var f in faces)
            {
                float3 n = math.cross(v[f[1]] - v[f[0]], v[f[2]] - v[f[0]]);
                if (math.dot(n, v[f[0]] - c) < 0f)
                {
                    var g = (int[])f.Clone();
                    Array.Reverse(g);
                    outF.Add(g);
                }
                else outF.Add(f);
            }
            return outF;
        }

        /// <summary>Bump travel of a wheel (m, wheel up against the body): its hub along the cabin's up axis over the centroid
        /// of the body nodes that carry its suspension, against the model.</summary>
        static double Travel(SoftBodyWorld w, SoftBodyWorld.Body b, int wheel, in CarFrame f)
        {
            var wd = b.def.wheels[wheel];
            double3 hub = 0.5 * ((double3)w.pos[b.nodeStart + wd.axleInner] + (double3)w.pos[b.nodeStart + wd.axleOuter]);
            double3 c = double3.zero;
            foreach (int n in wd.windupBody) c += (double3)w.pos[b.nodeStart + n];
            c /= wd.windupBody.Length;
            double hubM = 0.5 * (b.def.nodes[wd.axleInner].p[1] + b.def.nodes[wd.axleOuter].p[1]);
            double cM = 0;
            foreach (int n in wd.windupBody) cM += b.def.nodes[n].p[1];
            cM /= wd.windupBody.Length;
            return math.dot(hub - c, f.up) - (hubM - cM);
        }

        /// <summary>Quasi-steady circle (left turn) with the target lateral acceleration rising from aStart to aEnd (g) over
        /// rampSeconds: the robot steers the circle and holds v = sqrt(a g R). Columns: t, speed, a_y (g, speed x yaw rate),
        /// roll (deg, outer side down positive), path error (m), yaw rate (deg/s), steer input, road-wheel angle (deg, mean
        /// front), body slip angle (deg), pitch (deg), mean front / rear slip angle (deg, positive: velocity to the right of the
        /// wheel), wheel loads FL FR RL RR (N), mean rear slip ratio.</summary>
        static Series CircleRamp(ValidationContext ctx, Action<SimParamsDef> tweak, double radius, double aStart, double aEnd,
            double rampSeconds, double holdSeconds = 0.0, Action<DriverRobot> robotTweak = null)
        {
            using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f, tweak);
            var b = w.bodies[0];
            var probe = new CarProbe(w, 0);
            var f0 = probe.Frame();
            double v0 = math.sqrt(aStart * Dyn.G * radius);
            Dyn.LaunchAt(w, v0);
            var path = PolyPath.Circle(new double2(f0.rearAxle.x - radius, f0.rearAxle.z), radius, 0.0, true);
            double T = rampSeconds + holdSeconds;
            var robot = new DriverRobot(b.prm)
            {
                path = path,
                targetSpeed = (t, a) => math.sqrt(math.lerp(aStart, aEnd, math.saturate(t / math.max(rampSeconds, 1e-6))) * Dyn.G * radius),
            };
            robotTweak?.Invoke(robot);
            int iFL = probe.WheelIndex("FL"), iFR = probe.WheelIndex("FR"), iRL = probe.WheelIndex("RL"), iRR = probe.WheelIndex("RR");
            var s = new Series("t", "speed", "ay_g", "roll_deg", "path_error", "yaw_dps", "steer", "rwa_deg", "beta_deg", "pitch_deg",
                "alpha_f_deg", "alpha_r_deg", "fz_FL", "fz_FR", "fz_RL", "fz_RR", "slip_r");
            double hPrev = f0.heading, tPrev = 0.0;
            var yawWin = new Queue<(double t, double h)>();
            Dyn.Drive(w, T, 20, (t, f) => robot.Control(t, 20 * w.dt, f), (t, f) =>
            {
                // yaw rate over a 0.5 s window (the 10 ms heading difference carries the cabin's vibration)
                yawWin.Enqueue((t, f.heading));
                while (yawWin.Count > 1 && yawWin.Peek().t < t - 0.5) yawWin.Dequeue();
                var first = yawWin.Peek();
                double yaw = t > first.t ? Dyn.WrapRad(f.heading - first.h) / (t - first.t) : 0.0;
                double ay = f.speed * yaw / Dyn.G;
                double rwa = 0.5 * (probe.RoadWheelDeg(iFL, f) + probe.RoadWheelDeg(iFR, f));
                double beta = math.degrees(math.atan2(f.lateralVel, math.max(f.speed, 0.1)));
                // left turn: the outer (right) side goes down, roll positive; yaw positive is a right turn
                var ws = w.wheelState;
                int w0 = b.wheelStart;
                s.Add(t, f.speed, -ay, f.rollDeg, robot.lateral, math.degrees(yaw), w.vehicleState[b.vehicleIndex].steer, rwa, beta, f.pitchDeg,
                    0.5 * (probe.SlipAngleDeg(iFL, f) + probe.SlipAngleDeg(iFR, f)), 0.5 * (probe.SlipAngleDeg(iRL, f) + probe.SlipAngleDeg(iRR, f)),
                    ws[w0 + iFL].load, ws[w0 + iFR].load, ws[w0 + iRL].load, ws[w0 + iRR].load, 0.5 * (ws[w0 + iRL].slipRatio + ws[w0 + iRR].slipRatio));
                hPrev = f.heading; tPrev = t;
                return f.speed > 1.0;
            }, probe);
            return s;
        }

        /// <summary>Roll angle against the lateral acceleration on the quasi-steady circle: slope over the given band of a_y.</summary>
        static double RollGradient(Series s, double aLo, double aHi, double tFrom, out double r2)
        {
            var xs = new List<double>();
            var ys = new List<double>();
            for (int i = 0; i < s.Count; i++)
                if (s[i][0] >= tFrom && s[i][2] >= aLo && s[i][2] <= aHi)
                {
                    xs.Add(s[i][2]);
                    ys.Add(s[i][3]);
                }
            if (xs.Count < 10) { r2 = 0; return double.NaN; }
            var fit = Dyn.Fit(xs, ys);
            r2 = fit.r2;
            return fit.slope;
        }

        /// <summary>Damage bookkeeping of a run: the peak stress of every beam and the time it broke (sampled by the caller),
        /// then the broken and plastically deformed beams and hinges by material, the worst ones by node names.</summary>
        sealed class DamageWatch
        {
            readonly SoftBodyWorld w;
            readonly SoftBodyWorld.Body b;
            readonly float[] peak;
            readonly double[] brokeAt;

            public DamageWatch(SoftBodyWorld w, SoftBodyWorld.Body b)
            {
                this.w = w;
                this.b = b;
                peak = new float[b.beamCount];
                brokeAt = new double[b.beamCount];
                for (int j = 0; j < b.beamCount; j++) brokeAt[j] = w.broken[b.beamStart + j] != 0 ? 0.0 : double.NaN;
            }

            public void Sample(double t)
            {
                for (int j = 0; j < b.beamCount; j++)
                {
                    int gj = b.beamStart + j;
                    peak[j] = math.max(peak[j], w.stress[gj]);
                    if (double.IsNaN(brokeAt[j]) && w.broken[gj] != 0) brokeAt[j] = t;
                }
            }

            static readonly HashSet<string> RunningGearMats = new HashSet<string>
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
            {
                var bd = b.def.beams[j];
                return $"{b.def.nodes[bd.a].name}-{b.def.nodes[bd.b].name}";
            }

            /// <summary>Info lines: broken beams (with the time), plastic beams (rest-length change), plastic hinges, and the
            /// intact beams that came closest to their limit (peak stress: force over the yield or the break strength).</summary>
            public void Report(TestResult r, string what)
            {
                var broken = new SortedDictionary<string, List<string>>();
                var plastic = new SortedDictionary<string, List<(double mm, string s)>>();
                var close = new List<(float s, int j)>();
                for (int j = 0; j < b.beamCount; j++)
                {
                    int gj = b.beamStart + j;
                    string mat = b.def.beams[j].mat;
                    if (w.broken[gj] != 0)
                    {
                        if (!broken.TryGetValue(mat, out var l)) broken[mat] = l = new List<string>();
                        l.Add($"{Beam(j)} at {brokeAt[j]:F2} s");
                        continue;
                    }
                    double d = (w.rest[gj] - w.SpawnRest(gj)) * 1000.0;
                    if (math.abs(d) > 0.01)
                    {
                        if (!plastic.TryGetValue(mat, out var l)) plastic[mat] = l = new List<(double, string)>();
                        l.Add((math.abs(d), $"{Beam(j)} {d:+0.00;-0.00} mm"));
                    }
                    var bs = w.beams[gj];
                    if (peak[j] > 0.7f && (bs.flags & (BeamFlag.Deformable | BeamFlag.Breakable)) != 0) close.Add((peak[j], j));
                }
                foreach (var kv in broken)
                    r.Info($"{what}: broken {kv.Key}", kv.Value.Count, "beams", string.Join("; ", kv.Value.GetRange(0, math.min(6, kv.Value.Count))));
                foreach (var kv in plastic)
                {
                    kv.Value.Sort((x, y) => y.mm.CompareTo(x.mm));
                    var top = kv.Value.GetRange(0, math.min(4, kv.Value.Count)).ConvertAll(x => x.s);
                    r.Info($"{what}: plastic {kv.Key}", kv.Value.Count, "beams", $"largest {kv.Value[0].mm:F2} mm: " + string.Join("; ", top));
                }
                var hinges = new SortedDictionary<string, int>();
                for (int t = 0; t < b.hingeCount; t++)
                {
                    int gt = b.hingeStart + t;
                    if (math.abs(TorsionKernel.Wrap(w.hingeRest[gt] - w.hinges[gt].phi0)) > 1e-4f)
                    {
                        string mat = b.def.hinges[t].mat;
                        hinges.TryGetValue(mat, out int n);
                        hinges[mat] = n + 1;
                    }
                }
                foreach (var kv in hinges)
                    r.Info($"{what}: plastic hinges {kv.Key}", kv.Value, "hinges");
                close.Sort((x, y) => y.s.CompareTo(x.s));
                if (close.Count > 0)
                {
                    var top = close.GetRange(0, math.min(8, close.Count)).ConvertAll(x => $"{b.def.beams[x.j].mat} {Beam(x.j)} {x.s:F2}");
                    r.Info($"{what}: intact beams above 70 % of their limit", close.Count, "beams", string.Join("; ", top));
                }
            }
        }

        /// <summary>Skidpad limit: the highest 2 s mean of a_y with the path error below 1.5 m and the body slip below 6 deg.</summary>
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
                    s.Write(ctx.FilePath(r, $"slalom_{kmh:F0}_{name.Replace(' ', '_').Replace(",", "").Replace('.', 'p')}.csv"));
                    r.Info($"slalom {kmh:F0} km/h, {name}: largest path error", MaxAbs(s, 2, 1.0), "m",
                        $"beta {MaxAbs(s, 6, 1.0):F1} deg, a_y {MaxAbs(s, 3, 1.0):F2} g, yaw {MaxAbs(s, 4, 1.0):F0} deg/s, last 2 s error {MaxAbs(s, 2, s[s.Count - 1][0] - 2.0):F2} m");
                }
            return r;
        }

        /// <summary>The 18 m / +-1 m slalom (6 gates, 20 m run-in, 70 m run-out) at a speed; columns t, speed, path error, a_y, yaw
        /// rate, roll, body slip, centre of mass x and z (world; the slalom line runs along x = 0 from z0), z0.</summary>
        static Series SlalomRun(ValidationContext ctx, double kmh, Action<DriverRobot> tweak)
        {
            using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f);
            var b = w.bodies[0];
            var probe = new CarProbe(w, 0);
            var f0 = probe.Frame();
            double v = kmh * Kmh;
            Dyn.LaunchAt(w, v);
            var path = PolyPath.Slalom(f0.rearAxle.z + 20.0, 18.0, 1.0, 6, 40.0, 80.0);
            var robot = new DriverRobot(b.prm) { path = path, targetSpeed = (t, a) => v };
            tweak?.Invoke(robot);
            var s = new Series("t", "speed_kmh", "path_error", "ay_g", "yaw_dps", "roll_deg", "beta_deg", "x", "z", "z0");
            double hPrev = f0.heading, tPrev = 0;
            double3 velPrev = f0.vel;
            Dyn.Drive(w, (20.0 + 18.0 * 6 + 70.0) / v, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
            {
                double dtS = math.max(t - tPrev, 1e-6);
                double yaw = Dyn.WrapDeg(math.degrees(f.heading - hPrev)) / dtS;
                double ay = math.dot((f.vel - velPrev) / dtS, f.right) / Dyn.G;
                s.Add(t, f.speed / Kmh, robot.lateral, ay, yaw, f.rollDeg, math.degrees(math.atan2(f.lateralVel, math.max(f.speed, 0.1))),
                    f.com.x, f.com.z, f0.rearAxle.z + 20.0);
                hPrev = f.heading; tPrev = t; velPrev = f.vel;
                return true;
            }, probe);
            return s;
        }

        // ------------------------------------------------------------------ T10

        public static TestResult Suspension(ValidationContext ctx)
        {
            var r = new TestResult();
            var (def0, prm0) = LoadHellcat(ctx);

            // (a) static setup at rest: corner loads (contact impulses) against the centre of mass, ride height and
            //     alignment per corner, the springs' static compression
            {
                using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f);
                var b = w.bodies[0];
                var probe = new CarProbe(w, 0);
                w.ClearContactImp();
                Run(w, 0.5, 20);
                var f = probe.Frame();
                double total = 0;
                var fz = new double[b.wheelCount];
                for (int k = 0; k < b.wheelCount; k++) { fz[k] = probe.TreadImpulse(k).y / 0.5; total += fz[k]; }
                // centre of mass share from the model: front share = (z_com - z_rear) / (z_front - z_rear)
                double zf = 0, zr = 0; int nf = 0, nr = 0;
                for (int k = 0; k < b.wheelCount; k++)
                {
                    var wd = b.def.wheels[k];
                    double z = 0.5 * (b.def.nodes[wd.axleInner].p[2] + b.def.nodes[wd.axleOuter].p[2]);
                    if (wd.steered != 0) { zf += z; nf++; } else { zr += z; nr++; }
                }
                zf /= nf; zr /= nr;
                double mz = 0, mt = 0;
                foreach (var nd in b.def.nodes) { mz += nd.m * nd.p[2]; mt += nd.m; }
                double share = (mz / mt - zr) / (zf - zr);
                var s = new Series("wheel", "fz_N", "target_N", "travel_mm", "camber_deg", "toe_deg");
                double worst = 0;
                for (int k = 0; k < b.wheelCount; k++)
                {
                    var wd = b.def.wheels[k];
                    double target = 0.5 * mt * Dyn.G * (wd.steered != 0 ? share : 1.0 - share);
                    worst = math.max(worst, math.abs(fz[k] / target - 1.0));
                    double tr = Travel(w, b, k, f);
                    s.Add(k, fz[k], target, tr * 1000.0, probe.CamberDeg(k, f), probe.RoadWheelDeg(k, f));
                    r.Info($"static {wd.name}: corner load (contact impulses) vs centre of mass", fz[k], "N",
                        $"target {target:F0} N; travel {tr * 1000:F1} mm from the model ride height; camber {probe.CamberDeg(k, f):F2} deg, toe {probe.RoadWheelDeg(k, f):F2} deg (right positive)");
                }
                s.Write(ctx.FilePath(r, "static.csv"));
                r.Max("static: worst corner load vs the centre-of-mass split", worst, 0.05);
                r.Near("static: total of the corner loads vs m g", total, mt * Dyn.G, 0.01, "N");
                double sagF = 0, sagR = 0;
                foreach (var m in prm0.materials)
                {
                    if (m.name == "spring_f") sagF = m.preload / m.spring;
                    if (m.name == "spring_r") sagR = m.preload / m.spring;
                }
                r.Info("static sag of the springs (design, preload / rate): front", sagF * 1000.0, "mm", $"rear {sagR * 1000.0:F0} mm (ride height = the model pose, D-026)");
                double tMax = 0;
                for (int k = 0; k < b.wheelCount; k++)
                    tMax = math.max(tMax, math.abs(Travel(w, b, k, f)));
                r.Max("static: ride height within 15 mm of the model at every corner", tMax * 1000.0, 15.0, "mm");
            }

            // (b) bounce tests: the sprung nodes pushed down (2.5 m/s^2) for 1.5 s, released; body height at the axles
            foreach (var (tag, front, rear) in new[] { ("heave", true, true), ("front", true, false), ("rear", false, true) })
            {
                using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f);
                var b = w.bodies[0];
                var probe = new CarProbe(w, 0);
                var upF = new List<int>();
                var upR = new List<int>();
                for (int k = 0; k < b.wheelCount; k++)
                    (b.def.wheels[k].steered != 0 ? upF : upR).AddRange(WindupSet(b, k));
                double zMid = 0.0;
                for (int i = 0; i < b.nodeCount; i++)
                {
                    if (!IsSprung(b.def, i) || w.invMass[b.nodeStart + i] <= 0f)
                        continue;
                    bool isFront = b.def.nodes[i].p[2] > zMid;
                    if ((isFront && front) || (!isFront && rear))
                        w.extForce[b.nodeStart + i] = new float3(0f, -2.5f, 0f) / w.invMass[b.nodeStart + i];
                }
                Run(w, 1.5, 20);
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                    w.extForce[i] = float3.zero;
                var s = new Series("t", "front_y_mm", "rear_y_mm", "pitch_deg");
                double y0f = MeanY(w, upF), y0r = MeanY(w, upR);
                double t0 = w.StepsTaken * (double)w.dt;
                Run(w, 3.0, 10, t =>
                {
                    s.Add(t - t0, (MeanY(w, upF) - y0f) * 1000.0, (MeanY(w, upR) - y0r) * 1000.0, probe.Frame().pitchDeg);
                    return true;
                });
                s.Write(ctx.FilePath(r, $"bounce_{tag}.csv"));
                var tt = new List<double>();
                var xf = new List<double>();
                var xr = new List<double>();
                for (int i = 0; i < s.Count; i++) { tt.Add(s[i][0]); xf.Add(s[i][1]); xr.Add(s[i][2]); }
                FitDamped(tt, xf, out double ff, out double zf, out double r2f);
                FitDamped(tt, xr, out double fr, out double zr, out double r2r);
                r.Info($"bounce {tag}: front body frequency / damping ratio", ff, "Hz", $"zeta {zf:F2} (fit R^2 {r2f:F2}); rear {fr:F2} Hz, zeta {zr:F2} (R^2 {r2r:F2})");
                if (tag == "front")
                {
                    r.Near("ride frequency front (front bounce; brief 1.2-1.5 Hz, +-15 %)", ff, 1.35, (1.5 * 1.15 - 1.35) / 1.35, "Hz");
                    r.Min("damping ratio front (brief 0.25-0.4; -15 %)", zf, 0.25 * 0.85);
                    r.Max("damping ratio front (+15 %)", zf, 0.4 * 1.15 + 0.1);
                }
                if (tag == "rear")
                {
                    r.Near("ride frequency rear (rear bounce; brief 1.4-1.7 Hz, +-15 %)", fr, 1.55, (1.7 * 1.15 - 1.55) / 1.55, "Hz");
                    r.Min("damping ratio rear (brief 0.25-0.4; -15 %)", zr, 0.25 * 0.85);
                    r.Max("damping ratio rear (+15 %)", zr, 0.4 * 1.15 + 0.1);
                }
            }

            // (c) step input: a 50 mm step across the road at 10 km/h
            {
                var statics = Ground();
                statics.AddBox(new float3(0f, 0.05f - 1.0f, 3.0f + 25.0f), quaternion.identity, new float3(5f, 1.0f, 25f), "asphalt", "step");
                using var w = Dyn.Car(ctx, statics, float3.zero, 0f);
                var b = w.bodies[0];
                var probe = new CarProbe(w, 0);
                var f0 = probe.Frame();
                Dyn.LaunchAt(w, 10.0 * Kmh);
                var robot = new DriverRobot(b.prm) { path = PolyPath.Line(new double2(f0.rearAxle.x, f0.rearAxle.z), new double2(0, 1), 100), targetSpeed = (t, a) => 10.0 * Kmh };
                int iFR = probe.WheelIndex("FR"), iRR = probe.WheelIndex("RR");
                var s = new Series("t", "travel_FR_mm", "travel_RR_mm", "pitch_deg", "com_y_mm", "fz_FR", "fz_RR");
                double y0 = f0.com.y;
                var dmg = new DamageWatch(w, b);
                w.ClearContactImp();
                Dyn.Drive(w, 4.0, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
                {
                    dmg.Sample(t);
                    double span = 10 * w.dt;
                    s.Add(t, Travel(w, b, iFR, f) * 1000.0, Travel(w, b, iRR, f) * 1000.0, f.pitchDeg,
                        (f.com.y - y0) * 1000.0, probe.TreadImpulse(iFR).y / span, probe.TreadImpulse(iRR).y / span);
                    w.ClearContactImp();
                    return true;
                }, probe);
                s.Write(ctx.FilePath(r, "step_50mm.csv"));
                var m = w.Metrics(0, false);
                double peakF = 0, peakFz = 0;
                for (int i = 0; i < s.Count; i++) { peakF = math.max(peakF, s[i][1]); peakFz = math.max(peakFz, s[i][5]); }
                r.Info("step 50 mm at 10 km/h: peak front-right bump travel", peakF, "mm", $"peak tire load {peakFz:F0} N");
                r.Max("step 50 mm at 10 km/h: broken beams", m.brokenBeams, 0);
                dmg.Report(r, "step 50 mm");
                r.NearAbs("step 50 mm: the body ends 50 mm higher (both axles on the step)", s[s.Count - 1][4], 50.0, 10.0, "mm");
            }

            // (d) curb strike at 20 km/h: a 120 mm curb at 45 deg under the right wheels
            {
                var statics = Ground();
                // 5.3 m long along (sin 45, 0, cos 45) from x 0.55 to 4.3 m: only the right wheels (x 0.83) meet it, at z ~6.6 m
                // (further in it ran under the exhaust, 155 mm up at x 0.22-0.54, and tore its hangers)
                statics.AddBox(new float3(2.424f, 0.12f - 0.5f, 8.19f), quaternion.RotateY(math.radians(45f)), new float3(0.15f, 0.5f, 2.65f), "concrete", "curb");
                using var w = Dyn.Car(ctx, statics, float3.zero, 0f);
                var b = w.bodies[0];
                var probe = new CarProbe(w, 0);
                var f0 = probe.Frame();
                Dyn.LaunchAt(w, 20.0 * Kmh);
                var robot = new DriverRobot(b.prm) { path = PolyPath.Line(new double2(f0.rearAxle.x, f0.rearAxle.z), new double2(0, 1), 100), targetSpeed = (t, a) => 20.0 * Kmh };
                int iFR = probe.WheelIndex("FR"), iRR = probe.WheelIndex("RR");
                var s = new Series("t", "travel_FR_mm", "travel_RR_mm", "roll_deg", "heading_deg", "fz_FR");
                var dmg = new DamageWatch(w, b);
                w.ClearContactImp();
                Dyn.Drive(w, 4.0, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
                {
                    dmg.Sample(t);
                    s.Add(t, Travel(w, b, iFR, f) * 1000.0, Travel(w, b, iRR, f) * 1000.0, f.rollDeg,
                        Dyn.WrapDeg(math.degrees(f.heading - f0.heading)), probe.TreadImpulse(iFR).y / (10 * w.dt));
                    w.ClearContactImp();
                    return true;
                }, probe);
                s.Write(ctx.FilePath(r, "curb_20kmh.csv"));
                var m = w.Metrics(0, false);
                double peakFz = 0, peakT = 0;
                for (int i = 0; i < s.Count; i++) { peakFz = math.max(peakFz, s[i][5]); peakT = math.max(peakT, s[i][1]); }
                r.Info("curb strike at 20 km/h: peak front-right tire load / bump travel", peakFz, "N", $"travel {peakT:F1} mm, peak roll {MaxAbs(s, 3, 0):F2} deg");
                r.Max("curb strike at 20 km/h: broken beams", m.brokenBeams, 0);
                r.Max("curb strike at 20 km/h: plastically deformed beams", m.plasticBeams, 0);
                dmg.Report(r, "curb strike 20 km/h");
                double pMin = double.MaxValue;
                for (int g = b.pressureStart; g < b.pressureStart + b.pressureCount; g++)
                    pMin = math.min(pMin, (w.pressureState[g].pAbs - w.pressureGroups[g].pAtm) / (w.pressureGroups[g].gas0 / w.pressureGroups[g].volume0 - w.pressureGroups[g].pAtm));
                r.Min("curb strike at 20 km/h: lowest tire gauge pressure vs spawn (no puncture)", pMin, 0.95);
                r.Max("curb strike at 20 km/h: heading change after the curb", MaxAbs(s, 4, 2.5), 3.0, "deg");
            }

            // (e) roll in steady cornering, (f) anti-roll bar effect: quasi-steady circle R 45.72 m, 0.2 -> 0.6 g over 20 s
            {
                var s = CircleRamp(ctx, null, SkidpadRadius, 0.2, 0.62, 20.0);
                s.Write(ctx.FilePath(r, "roll_circle.csv"));
                double grad = RollGradient(s, 0.25, 0.6, 3.0, out double r2);
                var noBars = CircleRamp(ctx, p =>
                {
                    foreach (var m in p.materials)
                        if (m.name == "arb_front" || m.name == "arb_rear") m.spring = 0f;
                }, SkidpadRadius, 0.2, 0.62, 20.0);
                noBars.Write(ctx.FilePath(r, "roll_circle_no_bars.csv"));
                double gradNo = RollGradient(noBars, 0.25, 0.6, 3.0, out double r2n);
                r.Info("roll gradient in steady cornering (cabin floor vs the ground, 0.25-0.6 g)", grad, "deg/g",
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
                }
            }
            r.notes.Add("Bounce: the sprung nodes pushed down with 2.5 m/s^2 for 1.5 s and released; the body height at the axles " +
                        "(the suspension's body mounts) fitted with a damped sine. Step and curb: the robot holds the speed and the line.");
            return r;
        }

        // ------------------------------------------------------------------ T11

        public static TestResult Steering(ValidationContext ctx)
        {
            var r = new TestResult();
            var (_, prm0) = LoadHellcat(ctx);
            var st = prm0.steering;

            // (a) angle vs input at rest on turntables (ice patches under the front wheels), (b) ratio
            {
                var statics = Ground();
                Action<SimParamsDef> ice = p =>
                {
                    var list = new List<SurfaceDef>(p.surfaces) { new SurfaceDef { name = "ice", frictionScale = 0.02f, rollingResistance = 0.01f } };
                    p.surfaces = list.ToArray();
                };
                statics.AddBox(new float3(0f, 0.002f - 0.5f, 1.476f), quaternion.identity, new float3(1.5f, 0.5f, 0.8f), "ice", "turntables");
                using var w = Dyn.Car(ctx, statics, float3.zero, 0f, ice);
                var b = w.bodies[0];
                var probe = new CarProbe(w, 0);
                int iFL = probe.WheelIndex("FL"), iFR = probe.WheelIndex("FR");
                var s = new Series("input", "fl_deg", "fr_deg");
                var inputs = new List<double>();
                for (int k = 0; k <= 10; k++) inputs.Add(k * 0.1);
                for (int k = 9; k >= -10; k--) inputs.Add(k * 0.1);
                for (int k = -9; k <= 0; k++) inputs.Add(k * 0.1);
                double flMax = 0, frMax = 0, flMin = 0, frMin = 0, slope = double.NaN, mean0 = double.NaN;
                foreach (double u in inputs)
                {
                    var inp = new DriverInput { steer = (float)u, brake = 1f, gear = 0 };
                    for (int k = 0; k < 100; k++)
                    {
                        w.SetInput(b.vehicleIndex, inp);
                        w.UpdateNearLists(10 * w.dt + 0.05f);
                        w.Step(10);
                    }
                    var f = probe.Frame();
                    double fl = probe.RoadWheelDeg(iFL, f), fr = probe.RoadWheelDeg(iFR, f);
                    s.Add(u, fl, fr);
                    flMax = math.max(flMax, fl); frMax = math.max(frMax, fr); flMin = math.min(flMin, fl); frMin = math.min(frMin, fr);
                    if (math.abs(u) < 1e-6 && double.IsNaN(mean0)) mean0 = 0.5 * (fl + fr);
                    if (math.abs(u - 0.1) < 1e-6 && double.IsNaN(slope)) slope = (0.5 * (fl + fr) - mean0) / 0.1;
                }
                s.Write(ctx.FilePath(r, "angle_vs_input.csv"));
                // right lock: the right wheel is the inner one (steering right positive)
                double innerR = frMax, outerR = flMax, innerL = -flMin, outerL = -frMin;
                r.Info("full right lock: inner (right) / outer (left) road-wheel angle", innerR, "deg", $"outer {outerR:F1} deg; full left lock inner {innerL:F1}, outer {outerL:F1} deg");
                r.Near("maximum road-wheel angle (inner, brief about 30-35 deg)", 0.5 * (innerR + innerL), 32.5, 0.15, "deg");
                r.Min("Ackermann: the inner wheel turns more than the outer", 0.5 * (innerR + innerL) - 0.5 * (outerR + outerL), 0.0, "deg");
                r.Near("left / right lock symmetry", innerL / math.max(innerR, 1e-6), 1.0, 0.05);
                double swLock = 0.5 * st.steeringWheelTurnsLockToLock * 360.0;   // steering-wheel degrees at full input
                double ratioLock = swLock / (0.25 * (innerR + outerR + innerL + outerL));
                double ratioCentre = swLock * 0.1 / math.max(slope * 0.1, 1e-6);
                r.Info("steering ratio: on centre (first 10 % of the input) / at lock (mean road-wheel angle)", ratioCentre, ":1",
                    $"at lock {ratioLock:F1}:1; {st.steeringWheelTurnsLockToLock:F1} turns lock to lock ({swLock:F0} deg of steering wheel each way)");
                r.Near("lock to lock (brief 2.5-3 turns)", st.steeringWheelTurnsLockToLock, 2.75, 0.1, "turns");
                r.Near("on-centre steering ratio plausible (13-17:1 for this class)", ratioCentre, 15.0, 0.2, ":1");
            }

            // (c) speed-sensitive reduction: road-wheel angle for a 0.15 input pulse at several speeds
            {
                var s = new Series("speed", "rwa_deg", "expected_scale", "command_scale", "rwa_scale");
                double rwa5 = double.NaN, worst = 0;
                foreach (double v in new[] { 5.0, 15.0, 25.0, 40.0, 55.0 })
                {
                    using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f);
                    var b = w.bodies[0];
                    var probe = new CarProbe(w, 0);
                    Dyn.LaunchAt(w, v);
                    int iFL = probe.WheelIndex("FL"), iFR = probe.WheelIndex("FR");
                    double peak = 0, cmd = 0;
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
                        $"command scale {measured:F3} vs the design {expected:F3}; road-wheel angle {rwaScale:F2} of the 5 m/s value (the tires' aligning torque on the steering compliance)");
                }
                s.Write(ctx.FilePath(r, "speed_reduction.csv"));
                r.Max("speed-sensitive reduction: steering command vs the design curve (worst)", worst, 0.02);
            }

            // (d) return to centre: 30 km/h, input 0.5 for 2 s, released
            {
                using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f);
                var b = w.bodies[0];
                var probe = new CarProbe(w, 0);
                Dyn.LaunchAt(w, 30.0 * Kmh);
                int iFL = probe.WheelIndex("FL"), iFR = probe.WheelIndex("FR");
                var s = new Series("t", "input", "rwa_deg");
                double tRet = double.NaN, over = 0;
                Dyn.Drive(w, 3.5, 10, (t, f) => new DriverInput { steer = t < 2.0 ? 0.5f : 0f, throttle = 0.2f, gear = DriverInput.Drive }, (t, f) =>
                {
                    double a = 0.5 * (probe.RoadWheelDeg(iFL, f) + probe.RoadWheelDeg(iFR, f));
                    s.Add(t, t < 2.0 ? 0.5 : 0.0, a);
                    if (t > 2.0 && double.IsNaN(tRet) && math.abs(a) < 1.0) tRet = t - 2.0;
                    if (t > 2.0) over = math.min(over, a);
                    return true;
                }, probe);
                s.Write(ctx.FilePath(r, "return_to_centre.csv"));
                r.Max("return to centre after releasing a 0.5 input at 30 km/h: time to within 1 deg", double.IsNaN(tRet) ? 99.0 : tRet, 0.6, "s");
                r.Max("return to centre: overshoot past centre", -over, 1.0, "deg");
            }
            r.notes.Add("Road-wheel angles relative to the cabin (steering right positive). Turntables: an ice patch (friction 0.02) under the front wheels.");
            return r;
        }

        // ------------------------------------------------------------------ T14

        public static TestResult DriveTests(ValidationContext ctx)
        {
            var r = new TestResult();

            // (a) slalom: 6 gates 18 m apart, +-1.0 m, 50 km/h (peak 0.6 g on the line; at 60 km/h it is 0.86 g, the limit).
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
                // settled on the 70 m run-out: the last 1.5 s are 3.5 s after the last gate
                r.Max("slalom: path error over the last 1.5 s of the 70 m run-out (settled, no residual weave)", MaxAbs(s, 2, s[s.Count - 1][0] - 1.5), 0.3, "m");
                r.Info("slalom: largest path error of the robot (pure pursuit cuts the line)", MaxAbs(s, 2, 1.0), "m",
                    $"peak a_y {MaxAbs(s, 3, 1.0):F2} g, roll {MaxAbs(s, 5, 1.0):F2} deg, yaw rate {MaxAbs(s, 4, 1.0):F1} deg/s");
                r.Min("slalom: speed held (lowest)", Mean(s, 1, s[s.Count - 1][0] - 0.5, s[s.Count - 1][0]), 45.0, "km/h");
            }

            // (b) skidpad R 45.72 m: lateral acceleration rising 0.6 -> 1.15 g over 40 s; the limit is the highest 2 s
            //     mean of a_y while the car holds the circle (path error below 1.5 m) without sliding (body slip below 6 deg)
            {
                var s = CircleRamp(ctx, null, SkidpadRadius, 0.6, 1.15, 40.0);
                s.Write(ctx.FilePath(r, "skidpad.csv"));
                double best = 0, tBest = 0;
                for (int i = 0; i < s.Count; i++)
                {
                    if (s[i][0] < 4.0) continue;
                    double t1 = s[i][0];
                    // 2 s window ending here: a_y mean, path error max
                    double sum = 0, errMax = 0, betaMax = 0; int n = 0;
                    for (int k = i; k >= 0 && s[k][0] >= t1 - 2.0; k--)
                    {
                        sum += s[k][2]; errMax = math.max(errMax, math.abs(s[k][4])); betaMax = math.max(betaMax, math.abs(s[k][8])); n++;
                    }
                    if (errMax < 1.5 && betaMax < 6.0 && n > 0 && sum / n > best) { best = sum / n; tBest = t1; }
                }
                // steering and body slip at the limit, understeer gradient over 0.6-0.8 g
                var xs = new List<double>(); var ys = new List<double>();
                for (int i = 0; i < s.Count; i++)
                    if (s[i][0] > 4.0 && s[i][2] >= 0.6 && s[i][2] <= 0.8 && math.abs(s[i][4]) < 1.0) { xs.Add(s[i][2]); ys.Add(-s[i][7]); }
                double kus = xs.Count > 10 ? Dyn.Fit(xs, ys).slope : double.NaN;
                r.Info("skidpad R 45.72 m: steady lateral acceleration at the limit (2 s mean)", best, "g", $"at {tBest:F1} s; road-wheel angle vs a_y over 0.6-0.8 g {kus:F1} deg/g (understeer > 0)");
                r.Min("skidpad: brief 0.85-1.0 g, -15 %", best, 0.85 * 0.85, "g");
                r.Max("skidpad: brief 0.85-1.0 g, +15 %", best, 1.0 * 1.15, "g");
            }

            // (c) figure eight of two 20 m circles at 40 km/h, two laps
            {
                using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f);
                var b = w.bodies[0];
                var probe = new CarProbe(w, 0);
                var f0 = probe.Frame();
                double v = 40.0 * Kmh;
                Dyn.LaunchAt(w, v);
                var path = PolyPath.FigureEight(20.0);
                var shifted = new PolyPath { closed = true };
                for (int i = 0; i < path.pts.Count; i++) shifted.Add(path.pts[i] + new double2(f0.rearAxle.x, f0.rearAxle.z));
                var robot = new DriverRobot(b.prm) { path = shifted, targetSpeed = (t, a) => v };
                var s = new Series("t", "speed_kmh", "path_error", "yaw_dps", "roll_deg", "beta_deg");
                double hPrev = f0.heading, tPrev = 0;
                Dyn.Drive(w, 2.0 * shifted.Length / v, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
                {
                    double dtS = math.max(t - tPrev, 1e-6);
                    double yaw = Dyn.WrapDeg(math.degrees(f.heading - hPrev)) / dtS;
                    s.Add(t, f.speed / Kmh, robot.lateral, yaw, f.rollDeg, math.degrees(math.atan2(f.lateralVel, math.max(f.speed, 0.1))));
                    hPrev = f.heading; tPrev = t;
                    return true;
                }, probe);
                s.Write(ctx.FilePath(r, "figure8_40.csv"));
                r.Max("figure eight 2 x 20 m at 40 km/h: largest path error after 3 s", MaxAbs(s, 2, 3.0), 1.5, "m");
                r.Max("figure eight: largest body slip angle (no spin)", MaxAbs(s, 5, 3.0), 6.0, "deg");
                r.Info("figure eight: peak roll", MaxAbs(s, 4, 3.0), "deg");
            }

            // (d) speed bump (75 mm, 30 and 50 km/h) and a 120 mm curb under the right wheels at 30 km/h
            foreach (var (tag, kmh, curb) in new[] { ("bump_30", 30.0, false), ("bump_50", 50.0, false), ("curb_30", 30.0, true) })
            {
                var statics = Ground();
                if (curb)
                    statics.AddBox(new float3(2.424f, 0.12f - 0.5f, 12.22f), quaternion.RotateY(math.radians(45f)), new float3(0.15f, 0.5f, 2.65f), "concrete", "curb");
                else
                    statics.AddCylinder(new float3(0f, 0.075f - 0.3f, 12.0f), quaternion.RotateZ(math.radians(90f)), 0.3f, 3.0f, "asphalt", "bump");
                using var w = Dyn.Car(ctx, statics, float3.zero, 0f);
                var b = w.bodies[0];
                var probe = new CarProbe(w, 0);
                var f0 = probe.Frame();
                Dyn.LaunchAt(w, kmh * Kmh);
                var robot = new DriverRobot(b.prm) { path = PolyPath.Line(new double2(f0.rearAxle.x, f0.rearAxle.z), new double2(0, 1), 200), targetSpeed = (t, a) => kmh * Kmh };
                var s = new Series("t", "speed_kmh", "path_error", "pitch_deg", "roll_deg", "heading_deg", "acc_y_g");
                double tPrev = 0; double3 velPrev = f0.vel;
                var dmg = new DamageWatch(w, b);
                Dyn.Drive(w, 30.0 / (kmh * Kmh) + 1.0, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
                {
                    dmg.Sample(t);
                    double dtS = math.max(t - tPrev, 1e-6);
                    s.Add(t, f.speed / Kmh, robot.lateral, f.pitchDeg, f.rollDeg, Dyn.WrapDeg(math.degrees(f.heading - f0.heading)), (f.vel.y - velPrev.y) / dtS / Dyn.G);
                    tPrev = t; velPrev = f.vel;
                    return true;
                }, probe);
                s.Write(ctx.FilePath(r, $"{tag}.csv"));
                var m = w.Metrics(0, false);
                string what = curb ? "120 mm curb under the right wheels" : "75 mm speed bump";
                r.Max($"{what} at {kmh:F0} km/h: broken beams", m.brokenBeams, 0);
                r.Max($"{what} at {kmh:F0} km/h: largest path error (controllable)", MaxAbs(s, 2, 0.5), 0.5, "m");
                r.Info($"{what} at {kmh:F0} km/h: peak pitch / roll", MaxAbs(s, 3, 0.5), "deg", $"roll {MaxAbs(s, 4, 0.5):F2} deg, peak vertical acceleration of the body {MaxAbs(s, 6, 0.5):F2} g, {m.plasticBeams} plastic beams");
                dmg.Report(r, $"{tag}");
            }

            // (e) ramp jump: a 0.45 m high, 4 m long ramp at 60 km/h, landing on flat ground
            {
                var statics = Ground();
                float z0 = 15f, len = 4f, h = 0.45f, hw = 2.5f;
                var verts = new List<float3>
                {
                    new float3(-hw, 0f, z0), new float3(hw, 0f, z0), new float3(-hw, h, z0 + len), new float3(hw, h, z0 + len),
                    new float3(-hw, 0f, z0 + len), new float3(hw, 0f, z0 + len),
                };
                var faces = new List<int[]> { new[] { 0, 1, 3, 2 }, new[] { 2, 3, 5, 4 }, new[] { 0, 4, 5, 1 }, new[] { 0, 2, 4 }, new[] { 1, 5, 3 } };
                statics.AddConvexMesh(verts, OrientOutward(verts, faces), "asphalt", "ramp");
                using var w = Dyn.Car(ctx, statics, float3.zero, 0f);
                var b = w.bodies[0];
                var probe = new CarProbe(w, 0);
                var f0 = probe.Frame();
                double v = 60.0 * Kmh;
                Dyn.LaunchAt(w, v);
                var robot = new DriverRobot(b.prm) { path = PolyPath.Line(new double2(f0.rearAxle.x, f0.rearAxle.z), new double2(0, 1), 300), targetSpeed = (t, a) => v };
                var s = new Series("t", "speed_kmh", "com_y", "pitch_deg", "roll_deg", "heading_deg", "airborne");
                double tAir = 0, tLand = double.NaN, maxH = 0;
                var dmg = new DamageWatch(w, b);
                Dyn.Drive(w, 4.5, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
                {
                    dmg.Sample(t);
                    double air = 0;
                    for (int k = 0; k < b.wheelCount; k++) air += w.wheelState[b.wheelStart + k].load > 1.0 ? 0 : 1;
                    bool flying = air == b.wheelCount;
                    if (flying) tAir += 10 * w.dt;
                    if (!flying && tAir > 0.1 && double.IsNaN(tLand)) tLand = t;
                    maxH = math.max(maxH, f.com.y - f0.com.y);
                    s.Add(t, f.speed / Kmh, f.com.y - f0.com.y, f.pitchDeg, f.rollDeg, Dyn.WrapDeg(math.degrees(f.heading - f0.heading)), flying ? 1 : 0);
                    return true;
                }, probe);
                s.Write(ctx.FilePath(r, "ramp_jump_60.csv"));
                var m = w.Metrics(0, false);
                r.Info("ramp jump at 60 km/h: time with all four wheels off the ground", tAir, "s", $"peak rise of the centre of mass {maxH:F2} m");
                r.Min("ramp jump: the car leaves the ground", tAir, 0.15, "s");
                r.Max("ramp jump: largest roll over the run (no flip)", MaxAbs(s, 4, 0.0), 15.0, "deg");
                r.Max("ramp jump: largest pitch over the run (no flip)", MaxAbs(s, 3, 0.0), 25.0, "deg");
                double tEnd = s[s.Count - 1][0];
                r.Max("ramp jump: heading change 1 s after the landing (controllable)", MaxAbs(s, 5, double.IsNaN(tLand) ? tEnd : tLand + 1.0), 5.0, "deg");
                // a 0.75 m fall nose down 13 deg (the front wheels leave the edge first): the fascia meets the ground, body
                // damage is expected (scenario S5); the running gear must survive and the tires keep their air
                r.Max("ramp jump: broken beams of the running gear (wheels, suspension, steering, subframes)", dmg.RunningGearBroken(), 0);
                r.Max("ramp jump: plastically deformed beams of the running gear", dmg.RunningGearPlastic(), 0);
                double pMinJ = double.MaxValue;
                for (int gq = b.pressureStart; gq < b.pressureStart + b.pressureCount; gq++)
                    pMinJ = math.min(pMinJ, (w.pressureState[gq].pAbs - w.pressureGroups[gq].pAtm) / (w.pressureGroups[gq].gas0 / w.pressureGroups[gq].volume0 - w.pressureGroups[gq].pAtm));
                r.Min("ramp jump: lowest tire gauge pressure vs spawn (no puncture)", pMinJ, 0.95);
                r.Info("ramp jump: broken / plastic beams in all (body included)", m.brokenBeams, "", $"{m.plasticBeams} plastic; take-off flight {tAir:F2} s, landing at {tLand:F2} s");
                dmg.Report(r, "ramp jump");
            }
            r.notes.Add("The driver robot steers (pure pursuit with a cross-track integral and yaw damping) and holds the speed; traction control on.");
            return r;
        }
    }
}
