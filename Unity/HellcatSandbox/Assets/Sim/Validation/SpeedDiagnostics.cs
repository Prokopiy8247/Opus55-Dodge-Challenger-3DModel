using System;
using System.Collections.Generic;
using Hellcat.Sim.Data;
using Hellcat.Sim.Vehicle;
using Unity.Mathematics;
using static Hellcat.Sim.Validation.ValidationSuite;

namespace Hellcat.Sim.Validation
{
    /// <summary>Diagnostics of the car at speed (not in the gate): resistance and straight-line behaviour without the
    /// driver robot, at fixed inputs.</summary>
    public static class SpeedDiagnostics
    {
        const double Kmh = 1.0 / 3.6;

        public static TestResult StraightLine(ValidationContext ctx)
        {
            var r = new TestResult();
            void Run(string tag, double kmh, DriverInput input, double seconds, Action<SimParamsDef> tweak = null, Action<SoftBodyWorld> push = null)
            {
                using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f, tweak);
                var b = w.bodies[0];
                var probe = new CarProbe(w, 0);
                Dyn.LaunchAt(w, kmh * Kmh);
                push?.Invoke(w);
                var f0 = probe.Frame();
                w.trackEnergy = true;
                for (int j = 0; j < w.BeamCount; j++) w.dampEnergy[j] = 0.0;
                var s = new Series("t", "speed_kmh", "accel", "lateral", "heading_deg", "yaw_rate_dps", "rpm", "gear", "slip_RR", "slip_RL",
                    "load_FR", "load_FL", "load_RR", "load_RL", "fy_total", "dissipated_J",
                    "rwa_FR", "rwa_FL", "rwa_RR", "rwa_RL", "sa_FR", "sa_FL", "sa_RR", "sa_RL", "fx_RR", "fx_RL", "fy_RR", "fy_RL", "fz_RR", "fz_RL");
                int[] wi4 = { probe.WheelIndex("FR"), probe.WheelIndex("FL"), probe.WheelIndex("RR"), probe.WheelIndex("RL") };
                double vPrev = f0.speed, tPrev = 0, hPrev = f0.heading, yawSq = 0;
                int n = 0;
                double e0 = 0;
                Dyn.Drive(w, seconds, 20, (t, f) => input, (t, f) =>
                {
                    var st = w.vehicleState[b.vehicleIndex];
                    double dtS = math.max(t - tPrev, 1e-6);
                    double acc = (f.speed - vPrev) / dtS;
                    double yaw = Dyn.WrapDeg(math.degrees(f.heading - hPrev)) / dtS;
                    vPrev = f.speed; tPrev = t; hPrev = f.heading;
                    if (t > 0.5) { yawSq += yaw * yaw; n++; }
                    var m = w.Metrics(0, false);
                    if (e0 == 0) e0 = m.Dissipated;
                    double fy = 0;
                    for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                        fy += math.dot((double3)w.contactImp[i], f.right);
                    double3 jRR = probe.TreadImpulse(wi4[2]) / dtS, jRL = probe.TreadImpulse(wi4[3]) / dtS;
                    w.ClearContactImp();
                    int i0 = b.wheelStart;
                    s.Add(t, f.speed / Kmh, acc, math.dot(f.com - f0.com, f0.right), Dyn.WrapDeg(math.degrees(f.heading - f0.heading)), yaw,
                        st.engineRpm, st.gear, w.wheelState[i0 + 2].slipRatio, w.wheelState[i0 + 3].slipRatio,
                        w.wheelState[i0].load, w.wheelState[i0 + 1].load, w.wheelState[i0 + 2].load, w.wheelState[i0 + 3].load,
                        fy / dtS, m.Dissipated - e0,
                        probe.RoadWheelDeg(wi4[0], f), probe.RoadWheelDeg(wi4[1], f), probe.RoadWheelDeg(wi4[2], f), probe.RoadWheelDeg(wi4[3], f),
                        probe.SlipAngleDeg(wi4[0], f), probe.SlipAngleDeg(wi4[1], f), probe.SlipAngleDeg(wi4[2], f), probe.SlipAngleDeg(wi4[3], f),
                        math.dot(jRR, f.forward), math.dot(jRL, f.forward), math.dot(jRR, f.right), math.dot(jRL, f.right), math.dot(jRR, f.up), math.dot(jRL, f.up));
                    return true;
                }, probe);
                s.Write(ctx.FilePath(r, $"{tag}.csv"));
                // mean deceleration over the run and the resistance it means
                var last = s[s.Count - 1];
                double dv = (last[1] - s[5][1]) * Kmh, dt = last[0] - s[5][0];
                double vm = 0.5 * (last[1] + s[5][1]) * Kmh;
                double aero = 0.5 * 1.204 * 0.99 * vm * vm;
                double force = -b.totalMass * dv / dt;
                r.Info($"{tag}: mean acceleration", dv / dt, "m/s^2",
                    $"{s[5][1]:F1} -> {last[1]:F1} km/h in {dt:F1} s; resistance {force:F0} N at {vm / Kmh:F0} km/h (aero {aero:F0} N, rest {force - aero:F0} N = C_rr {(force - aero) / (b.totalMass * 9.81):F4})");
                r.Info($"{tag}: lateral drift / heading change", last[3], "m", $"heading {last[4]:F2} deg, yaw rate RMS {math.sqrt(yawSq / math.max(n, 1)):F2} deg/s");
                double dE = last[15];
                r.Info($"{tag}: dissipated energy (beams, groups, hinges, wind-up, driveline)", dE / dt, "W", "");
                // where: beam damping by material, damp groups, hinges, wind-up, driveline
                var byMat = new Dictionary<string, double>();
                for (int j = b.beamStart; j < b.beamStart + b.beamCount; j++)
                {
                    string mat = b.def.beams[j - b.beamStart].mat;
                    byMat[mat] = (byMat.TryGetValue(mat, out double e) ? e : 0.0) + w.dampEnergy[j];
                }
                double groups = 0, hingesE = 0, windup = 0;
                for (int g = b.dampGroupStart; g < b.dampGroupStart + b.dampGroupCount; g++)
                {
                    string name = b.def.dampGroups[g - b.dampGroupStart].name;
                    byMat["group:" + name] = w.dampGroupEnergy[g];
                    groups += w.dampGroupEnergy[g];
                }
                for (int h = b.hingeStart; h < b.hingeStart + b.hingeCount; h++)
                {
                    string hm = "hinge:" + b.def.hinges[h - b.hingeStart].mat;
                    byMat[hm] = (byMat.TryGetValue(hm, out double e) ? e : 0.0) + w.hingeDampEnergy[h];
                    hingesE += w.hingeDampEnergy[h];
                }
                for (int k = b.wheelStart; k < b.wheelStart + b.wheelCount; k++)
                    windup += w.wheelState[k].windupDamped;
                byMat["windup"] = windup;
                byMat["driveline"] = w.vehicleState[b.vehicleIndex].drivelineDamped;
                double fric = 0;
                var list = new List<KeyValuePair<string, double>>(byMat);
                list.Sort((x, y) => y.Value.CompareTo(x.Value));
                var top = new List<string>();
                for (int k = 0; k < math.min(12, list.Count); k++)
                    top.Add($"{list[k].Key} {list[k].Value / seconds / 1000.0:F1} kW");
                r.notes.Add($"{tag}: dissipation by source (mean over the run, from launch): " + string.Join(", ", top));
                _ = fric;
            }
            Action<SimParamsDef> T(Action<ContactMaterialDef> f) => p => { foreach (var c in p.contactMaterials) if (c.name == "tire") f(c); };
            var wot = new DriverInput { throttle = 1f, gear = DriverInput.Drive };
            Action<SimParamsDef> Scale(string[] names, float k) => p =>
            {
                foreach (var m in p.materials)
                    if (Array.IndexOf(names, m.name) >= 0) { m.spring *= k; if (m.springExp > 0f) m.springExp *= k; }
            };
            var front = new[] { "arm", "tierod", "knuckle", "subframe", "subframe_mount", "rail_f_brace" };
            var rear = new[] { "link", "knuckle", "subframe", "subframe_mount", "rail_r_brace" };
            Action<SimParamsDef> Damp(string[] names, float k) => p =>
            {
                foreach (var m in p.materials)
                    if (Array.IndexOf(names, m.name) >= 0)
                    {
                        m.damp *= k;
                        if (m.dampRebound > 0f) m.dampRebound *= k;
                        if (m.dampFast > 0f) m.dampFast *= k;
                        if (m.dampReboundFast > 0f) m.dampReboundFast *= k;
                    }
            };
            var susp = new[] { "link", "arm", "tierod", "subframe_mount", "knuckle" };
            // the drive force without the drive torque: coasting in neutral, a forward force on the rear axle nodes (the
            // suspension loaded as by traction) or on every node (towing)
            void AxlePush(SoftBodyWorld w, float perWheel)
            {
                var b = w.bodies[0];
                var fw = (float3)new CarProbe(w, 0).Frame().forward;
                for (int k = 0; k < b.wheelCount; k++)
                    if (w.wheels[b.wheelStart + k].driven != 0)
                    {
                        var wd = b.def.wheels[k];
                        w.extForce[b.nodeStart + wd.axleInner] = 0.5f * perWheel * fw;
                        w.extForce[b.nodeStart + wd.axleOuter] = 0.5f * perWheel * fw;
                    }
            }
            void Tow(SoftBodyWorld w, float total)
            {
                var b = w.bodies[0];
                var fw = (float3)new CarProbe(w, 0).Frame().forward;
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                    if (w.invMass[i] > 0f)
                        w.extForce[i] = total / b.totalMass / w.invMass[i] * fw;
            }
            var coast = new DriverInput { gear = 0 };
            Action<SimParamsDef> Belt(float damp, float cap) => p =>
            {
                foreach (var h in p.hingeMaterials)
                    if (h.name == "tire_belt") { h.damp = damp; h.dampCap = cap; }
            };
            Run("wot_270", 270.0, wot, 20.0);
            Run("wot_270_belt0.04", 270.0, wot, 20.0, Belt(0.04f, 0f));
            Run("wot_270_belt0.02", 270.0, wot, 20.0, Belt(0.02f, 0f));
            Run("wot_270_belt_cap20", 270.0, wot, 20.0, Belt(0.08f, 20f));
            return r;
        }

        /// <summary>Diagnostic X17: elastokinematics of the parked car (brakes held): toe and camber of every wheel
        /// relative to the cabin under 2 kN longitudinal and lateral forces at the hubs (axle nodes).</summary>
        public static TestResult Elastokinematics(ValidationContext ctx)
        {
            var r = new TestResult();
            var cases = new List<(string name, float3 dir, bool front, bool rear)>
            {
                ("drive, rear free, align 100k/40", new float3(0, 0, 1), false, true),
                ("drive, rear free, align 120k/40", new float3(0, 0, 1), false, true),
                ("drive, rear free, align 0k/0", new float3(0, 0, 1), false, true),
                ("rear forward, rear brakes free (drive)", new float3(0, 0, 1), false, true),
                ("rear forward (brakes held)", new float3(0, 0, 1), false, true),
                ("rear backward (brake)", new float3(0, 0, -1), false, true),
                ("rear lateral left", new float3(-1, 0, 0), false, true),
                ("front backward (brake)", new float3(0, 0, -1), true, false),
                ("front lateral left", new float3(-1, 0, 0), true, false),
            };
            var s = new Series("case", "wheel", "toe0_deg", "dtoe_deg", "camber0_deg", "dcamber_deg", "dx_mm", "dz_mm");
            for (int ci = 0; ci < cases.Count; ci++)
            {
                var (name, dir, front, rear) = cases[ci];
                bool rearFree = name.Contains("rear brakes free") || name.Contains("rear free");
                float aK = -1f, aC = -1f;
                var mt = System.Text.RegularExpressions.Regex.Match(name, @"align (\d+)k/(\d+)");
                if (mt.Success) { aK = float.Parse(mt.Groups[1].Value) * 1000f; aC = float.Parse(mt.Groups[2].Value); }
                using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f, p =>
                {
                    if (rearFree)
                        foreach (var bd in p.brakes)
                            if (bd.name == "rear") { bd.maxTorque = 0f; bd.handbrakeTorque = 0f; }
                    if (aK >= 0f)
                        foreach (var wu in p.windup)
                            if (wu.name == "rear") { wu.toeStiffness = aK; wu.camberStiffness = aK; wu.toeDamping = aC; wu.camberDamping = aC; }
                });
                var b = w.bodies[0];
                var probe = new CarProbe(w, 0);
                var f0 = probe.Frame();
                var toe0 = new double[b.wheelCount];
                var cam0 = new double[b.wheelCount];
                var hub0 = new double3[b.wheelCount];
                for (int k = 0; k < b.wheelCount; k++)
                {
                    toe0[k] = probe.RoadWheelDeg(k, f0);
                    cam0[k] = probe.CamberDeg(k, f0);
                    if (ci == 0)
                    {
                        var ws0 = w.wheelState[b.wheelStart + k];
                        r.Info($"settled: {b.def.wheels[k].name} alignment element toe-in / camber", math.degrees(ws0.toe), "deg",
                            $"camber {math.degrees(ws0.camber):+0.000;-0.000} deg, travel {ws0.travel * 1000:F1} mm; probe toe {toe0[k]:+0.000;-0.000} (right positive), camber {cam0[k]:+0.000;-0.000}");
                    }
                    var wd = b.def.wheels[k];
                    hub0[k] = 0.5 * ((double3)w.pos[b.nodeStart + wd.axleInner] + (double3)w.pos[b.nodeStart + wd.axleOuter]) - f0.com;
                }
                w.SetInput(b.vehicleIndex, new DriverInput { brake = 1f, handbrake = 1f, gear = 0 });
                // ramp the force over 0.5 s, hold 1.5 s; toe statistics over the last 0.5 s (mean, RMS deviation)
                var tSum = new double[b.wheelCount];
                var tSq = new double[b.wheelCount];
                int tN = 0;
                for (int step = 0; step < 4000; step++)
                {
                    if (step >= 3000 && step % 10 == 0)
                    {
                        var fs = probe.Frame();
                        for (int k = 0; k < b.wheelCount; k++)
                        {
                            double tv = probe.RoadWheelDeg(k, fs);
                            tSum[k] += tv;
                            tSq[k] += tv * tv;
                        }
                        tN++;
                    }
                    float ramp = math.saturate(step / 1000f);
                    for (int k = 0; k < b.wheelCount; k++)
                    {
                        var wd = b.def.wheels[k];
                        bool isFront = w.wheels[b.wheelStart + k].steered != 0;
                        float3 fw = ((isFront && front) || (!isFront && rear)) ? 1000f * ramp * dir : float3.zero;
                        w.extForce[b.nodeStart + wd.axleInner] = fw;
                        w.extForce[b.nodeStart + wd.axleOuter] = fw;
                    }
                    if (step % 10 == 0)
                        w.UpdateNearLists(10 * w.dt + 0.05f);
                    w.Step(1);
                }
                var f1 = probe.Frame();
                for (int k = 0; k < b.wheelCount; k++)
                {
                    var wd = b.def.wheels[k];
                    double3 hub = 0.5 * ((double3)w.pos[b.nodeStart + wd.axleInner] + (double3)w.pos[b.nodeStart + wd.axleOuter]) - f1.com;
                    double tMean = tSum[k] / math.max(tN, 1), tRms = math.sqrt(math.max(tSq[k] / math.max(tN, 1) - tMean * tMean, 0.0));
                    double dt = tMean - toe0[k], dc = probe.CamberDeg(k, f1) - cam0[k];
                    double3 dh = hub - hub0[k];
                    s.Add(ci, k, toe0[k], dt, cam0[k], dc, math.dot(dh, f1.right) * 1000.0, math.dot(dh, f1.forward) * 1000.0);
                    var wsk = w.wheelState[b.wheelStart + k];
                    r.Info($"{name}: {wd.name} toe / camber change (2 kN per wheel)", dt, "deg",
                        $"(mean of the last 0.5 s, oscillation RMS {tRms:F3} deg); camber {dc:+0.000;-0.000} deg; static toe {toe0[k]:+0.000;-0.000} (right positive), camber {cam0[k]:+0.000;-0.000} deg; hub moved {math.dot(dh, f1.right) * 1000:F2} mm right, {math.dot(dh, f1.forward) * 1000:F2} mm forward (vs the cabin); " +
                        $"alignment element: toe-in {math.degrees(wsk.toe):+0.000;-0.000} camber {math.degrees(wsk.camber):+0.000;-0.000} deg, travel {wsk.travel * 1000:F1} mm");
                }
            }
            s.Write(ctx.FilePath(r, "elastokinematics.csv"));
            r.notes.Add("Road-wheel angle relative to the cabin, steering right positive: a right wheel toes in when it turns left (negative), a left wheel when it turns right (positive).");
            return r;
        }

        /// <summary>Diagnostic X16: the driver robot on a straight at full throttle from 250 km/h, with variants of its
        /// high-speed steering (look-ahead, yaw damping, command filter).</summary>
        public static TestResult RobotAtSpeed(ValidationContext ctx)
        {
            var r = new TestResult();
            var variants = new List<(string name, Action<DriverRobot> set)>
            {
                ("base_yaw0.05", d => { d.kYaw = 0.05; }),
                ("exp1.5_yaw0.05", d => { d.crossSpeedExp = 1.5; d.kYaw = 0.05; }),
                ("exp1_yaw0.1", d => { d.crossSpeedExp = 1.0; d.kYaw = 0.1; }),
                ("exp1_yaw0.05_f0.1", d => { d.crossSpeedExp = 1.0; d.kYaw = 0.05; d.steerTau = 0.1; }),
                ("exp1_yaw0.15", d => { d.crossSpeedExp = 1.0; d.kYaw = 0.15; }),
            };
            foreach (var (name, set) in variants)
            {
                using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f);
                var b = w.bodies[0];
                var probe = new CarProbe(w, 0);
                Dyn.LaunchAt(w, 250.0 * Kmh);
                var f0 = probe.Frame();
                var robot = new DriverRobot(b.prm)
                {
                    path = PolyPath.Line(new double2(f0.rearAxle.x, f0.rearAxle.z), math.normalize(new double2(f0.forward.x, f0.forward.z)), 6000.0),
                    targetSpeed = (t, a) => 200.0,
                };
                set(robot);
                var s = new Series("t", "speed_kmh", "lateral", "yaw_rate_dps", "steer");
                double hPrev = f0.heading, tPrev = 0, latMax = 0, yawMax = 0, yawSq = 0;
                int n = 0;
                Dyn.Drive(w, 45.0, 20, (t, f) => robot.Control(t, 20 * w.dt, f), (t, f) =>
                {
                    double dtS = math.max(t - tPrev, 1e-6);
                    double yaw = Dyn.WrapDeg(math.degrees(f.heading - hPrev)) / dtS;
                    hPrev = f.heading; tPrev = t;
                    if (t > 2.0) { latMax = math.max(latMax, math.abs(robot.lateral)); yawMax = math.max(yawMax, math.abs(yaw)); yawSq += yaw * yaw; n++; }
                    s.Add(t, f.speed / Kmh, robot.lateral, yaw, w.vehicleState[b.vehicleIndex].steer);
                    return f.speed > 30.0;
                }, probe);
                s.Write(ctx.FilePath(r, $"robot_{name}.csv"));
                var last = s[s.Count - 1];
                r.Info($"{name}: largest path offset after 2 s", latMax, "m",
                    $"peak yaw rate {yawMax:F2} deg/s, RMS {math.sqrt(yawSq / math.max(n, 1)):F2} deg/s; {last[0]:F1} s, {last[1]:F0} km/h at the end");
            }
            return r;
        }

        /// <summary>Every substep for 0.3 s after 1 s of coasting: hub heights, wheel loads, rim spin of the front right
        /// wheel (wheel hop and the once-per-revolution content).</summary>
        static void Hop(ValidationContext ctx, TestResult r, double kmh)
        {
            using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f);
            var b = w.bodies[0];
            var probe = new CarProbe(w, 0);
            Dyn.LaunchAt(w, kmh * Kmh);
            w.SetInput(b.vehicleIndex, new DriverInput { gear = 0 });
            for (int k = 0; k < 100; k++)
            {
                w.UpdateNearLists(10 * w.dt + 0.05f);
                w.Step(10);
            }
            var s = new Series("t", "hub_FR", "hub_RR", "load_FR", "load_RR", "omega_FR", "lowest_FR", "body_y");
            int fr = probe.WheelIndex("FR"), rr = probe.WheelIndex("RR");
            double y0 = probe.HubY(fr), y1 = probe.HubY(rr);
            double minL = double.MaxValue, maxL = 0, sumL = 0, sumL2 = 0, minH = double.MaxValue, maxH = double.MinValue;
            int n = 0;
            for (int k = 0; k < 600; k++)
            {
                if (k % 10 == 0)
                    w.UpdateNearLists(10 * w.dt + 0.05f);
                w.Step(1);
                double lf = w.wheelState[b.wheelStart + fr].load;
                double h = probe.HubY(fr) - y0;
                s.Add(k * w.dt, h * 1000.0, (probe.HubY(rr) - y1) * 1000.0, lf, w.wheelState[b.wheelStart + rr].load,
                    w.wheelState[b.wheelStart + fr].omegaAbs, probe.LowestTread(fr) * 1000.0, w.Metrics(0, false).centerOfMass.y);
                minL = math.min(minL, lf); maxL = math.max(maxL, lf); sumL += lf; sumL2 += lf * lf; n++;
                minH = math.min(minH, h); maxH = math.max(maxH, h);
            }
            s.Write(ctx.FilePath(r, $"hop_{kmh:F0}.csv"));
            double mean = sumL / n;
            r.Info($"hop {kmh:F0} km/h: front right load per substep mean / RMS ripple", mean, "N",
                $"min {minL:F0} max {maxL:F0} N, RMS {math.sqrt(math.max(sumL2 / n - mean * mean, 0)):F0} N; hub height range {(maxH - minH) * 1000:F2} mm");
        }
    }
}
