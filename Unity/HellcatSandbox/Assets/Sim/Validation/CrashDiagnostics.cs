using System;
using System.Collections.Generic;
using Hellcat.Sim.Data;
using Hellcat.Sim.Vehicle;
using Unity.Mathematics;
using static Hellcat.Sim.Validation.ValidationSuite;

namespace Hellcat.Sim.Validation
{
    /// <summary>X21 (diagnostic, P4 crash): the settled Hellcat launched rolling at 50 km/h into a rigid concrete wall (the
    /// S1 full frontal) for contact and structure variants. Per millisecond: the cabin pulse (mass-weighted velocity of the
    /// passenger-cell nodes), the wall force (contact impulses of the nodes at the wall), the energy ledger and the pose.
    /// Reports the dynamic crush (cabin travel from the first wall force to its stop), pulse duration, peak and mean cabin
    /// deceleration, rebound speed, pitch and rear lift, and the energy balance (stored + dissipated - contact work, which
    /// must stay constant: a rise is energy the solver created).</summary>
    public static class CrashDiagnostics
    {
        public const float Kmh = 50f;
        const float Gap = 2.0f;          // m from the front-most node to the wall face at the launch

        public sealed class Variant
        {
            public string name;
            public Action<SimParamsDef> tweak;
            public Action<VehicleDef> defTweak;
            public Action<DriverRobot> robot;   // X24: driver robot settings; openLoop: steering held at zero, full throttle
            public bool openLoop;
            public double cruiseKmh, startKmh = 270.0;   // X24: hold this speed with the steering at zero (0: full throttle)
            public bool coast;                  // X24: neutral, steering at zero
            public float kmh = Kmh;
        }

        public sealed class Outcome
        {
            public string name;
            public double entryKmh, crush, pulseMs, peakG1ms, peakG10ms, meanG, reboundMps, maxPitchDeg, maxRearLift,
                maxCabinRise, excessJ, reboundKeJ, brokenBeams, plasticBeams, maxNodeSpeed, wallPeakKN, tunnelled, nonFinite,
                plasticJ, breakingJ, dampingJ, contactJ, elasticJ, keAtContact, stepUs;
            public string csv;
            public string atStop = "", atEnd = "";
        }

        /// <summary>Elastic energy (now) and plastic work (so far) of the body's beams summed by material, largest first.</summary>
        public static string ByMaterial(SoftBodyWorld w, int bi, bool elastic, int top = 10)
        {
            var b = w.bodies[bi];
            var sum = new Dictionary<string, double>();
            for (int k = 0; k < b.beamCount; k++)
            {
                int j = b.beamStart + k;
                double e = elastic ? w.BeamElasticEnergy(j) : w.plasticWork[j];
                string mat = b.def.beams[k].mat;
                sum.TryGetValue(mat, out double acc);
                sum[mat] = acc + e;
            }
            var l = new List<KeyValuePair<string, double>>(sum);
            l.Sort((x, y) => y.Value.CompareTo(x.Value));
            var sb = new System.Text.StringBuilder();
            for (int k = 0; k < math.min(top, l.Count); k++)
                sb.Append(k > 0 ? ", " : "").Append($"{l[k].Key} {l[k].Value / 1000.0:F2}");
            return sb.ToString();
        }

        static Action<SimParamsDef> HardContact(bool on, float bias = -1f) => p =>
        {
            foreach (var c in p.contactMaterials)
                if (c.name != "tire" && c.name != "default")
                {
                    c.hardContact = on;
                    if (bias > 0f) c.bias = bias;
                }
        };

        /// <summary>Removes the rigidifiers (D-040) with an end ahead of z = zf or behind z = zr (the crush zones) and gives the
        /// designed braces (D-030) inside the crush zones their own material brace_crush.</summary>
        public static Action<VehicleDef> CrushZones(float zf = 1.6f, float zr = -2.0f) => d =>
        {
            var l = new List<BeamDef>();
            foreach (var bm in d.beams)
            {
                float za = d.nodes[bm.a].p[2], zb = d.nodes[bm.b].p[2];
                if (bm.mat == "rigidifier" && (math.max(za, zb) > zf || math.min(za, zb) < zr))
                    continue;
                if (bm.mat == "brace" && (0.5f * (za + zb) > zf || 0.5f * (za + zb) < zr))
                    bm.mat = "brace_crush";
                l.Add(bm);
            }
            d.beams = l.ToArray();
        };

        public static BeamMaterialDef Mat(SimParamsDef p, string name) => Array.Find(p.materials, m => m.name == name);

        /// <summary>Adds a copy of material <paramref name="from"/> named <paramref name="name"/> unless it exists.</summary>
        public static void AddMat(SimParamsDef p, string from, string name)
        {
            if (Mat(p, name) != null) return;
            var s = Mat(p, from);
            var c = new BeamMaterialDef
            {
                name = name, spring = s.spring, damp = s.damp, dampRebound = s.dampRebound, dampFast = s.dampFast, dampReboundFast = s.dampReboundFast,
                velSplit = s.velSplit, velSplitRebound = s.velSplitRebound, springExp = s.springExp, dampExp = s.dampExp, deform = s.deform,
                hardening = s.hardening, deformCap = s.deformCap, strength = s.strength, deformLimitMin = s.deformLimitMin,
                deformLimitMax = s.deformLimitMax, inflationShare = s.inflationShare, preload = s.preload, shortBound = s.shortBound,
                longBound = s.longBound, boundZone = s.boundZone, limitSpring = s.limitSpring, limitDamp = s.limitDamp,
                limitDampRebound = s.limitDampRebound, hydroMinRatio = s.hydroMinRatio, hydroMaxRatio = s.hydroMaxRatio,
            };
            var l = new List<BeamMaterialDef>(p.materials) { c };
            p.materials = l.ToArray();
        }

        /// <summary>Elastic energy now and plastic work so far by region (beam midpoint at the model pose): front of the
        /// firewall (z &gt; 1.0), cabin, rear of the rear seat bulkhead (z &lt; -1.1); and the part of the elastic energy held by
        /// beams that have yielded.</summary>
        public static string ByRegion(SoftBodyWorld w, int bi)
        {
            var b = w.bodies[bi];
            double[] el = new double[3], pl = new double[3];
            double yielded = 0;
            for (int k = 0; k < b.beamCount; k++)
            {
                int j = b.beamStart + k;
                var bd = b.def.beams[k];
                float z = 0.5f * (b.def.nodes[bd.a].p[2] + b.def.nodes[bd.b].p[2]);
                int r = z > 1.0f ? 0 : z < -1.1f ? 2 : 1;
                double e = w.BeamElasticEnergy(j);
                el[r] += e;
                pl[r] += w.plasticWork[j];
                if (w.plasticWork[j] > 0f) yielded += e;
            }
            return $"elastic front {el[0] / 1000:F1} / cabin {el[1] / 1000:F1} / rear {el[2] / 1000:F1} (yielded beams {yielded / 1000:F1}), " +
                   $"plastic front {pl[0] / 1000:F1} / cabin {pl[1] / 1000:F1} / rear {pl[2] / 1000:F1}";
        }

        /// <summary>Broken beams by material and the nodes cut off from the cabin (no path of intact beams) by name family.</summary>
        public static string Damage(SoftBodyWorld w, int bi)
        {
            var b = w.bodies[bi];
            var d = b.def;
            var brokenBy = new Dictionary<string, int>();
            var adj = new List<int>[d.nodes.Length];
            for (int i = 0; i < adj.Length; i++) adj[i] = new List<int>();
            for (int k = 0; k < b.beamCount; k++)
            {
                var bd = d.beams[k];
                if (w.broken[b.beamStart + k] != 0)
                {
                    brokenBy.TryGetValue(bd.mat, out int c);
                    brokenBy[bd.mat] = c + 1;
                    continue;
                }
                adj[bd.a].Add(bd.b);
                adj[bd.b].Add(bd.a);
            }
            var seen = new bool[d.nodes.Length];
            var stack = new Stack<int>();
            foreach (int c in CabinNodes(d)) { seen[c] = true; stack.Push(c); }
            while (stack.Count > 0)
                foreach (int o in adj[stack.Pop()])
                    if (!seen[o]) { seen[o] = true; stack.Push(o); }
            var cut = new Dictionary<string, int>();
            for (int i = 0; i < seen.Length; i++)
                if (!seen[i])
                {
                    string fam = System.Text.RegularExpressions.Regex.Replace(d.nodes[i].name, @"\d+", "#");
                    string key = d.nodes[i].part + ":" + fam;
                    cut.TryGetValue(key, out int c);
                    cut[key] = c + 1;
                }
            string Fmt(Dictionary<string, int> m)
            {
                var l = new List<KeyValuePair<string, int>>(m);
                l.Sort((x, y) => y.Value.CompareTo(x.Value));
                return string.Join(", ", l.ConvertAll(kv => $"{kv.Key} {kv.Value}"));
            }
            return $"broken by material: {Fmt(brokenBy)} | cut off from the cabin: {Fmt(cut)}";
        }

        /// <summary>Closures and skins during a crash: per door the hinge-pillar to latch-pillar distance on the body (the
        /// door aperture), the largest latch force and when the latch broke, and per part (roof skin, doors, hood) the
        /// largest distance of a node from where the cabin's rigid motion would carry it.</summary>
        public sealed class ClosureWatch
        {
            readonly SoftBodyWorld w;
            readonly SoftBodyWorld.Body b;
            readonly int[] cabin;
            readonly double3[] cab0, rest;
            readonly double3 c0;
            readonly List<(string name, int[] nodes)> parts = new List<(string, int[])>();
            readonly List<(string door, int[] hingeBody, int[] latchBody, double len0, List<int> latchBeams)> doors =
                new List<(string, int[], int[], double, List<int>)>();
            public readonly Dictionary<string, double> maxOffset = new Dictionary<string, double>();
            public readonly Dictionary<string, double> maxRise = new Dictionary<string, double>();
            public readonly Dictionary<string, double> maxApertureChange = new Dictionary<string, double>();
            public readonly Dictionary<string, double> maxLatchForce = new Dictionary<string, double>();
            public readonly Dictionary<string, double> latchBreak = new Dictionary<string, double>();

            public ClosureWatch(SoftBodyWorld world, int bi, int[] cabinNodes)
            {
                w = world;
                b = world.bodies[bi];
                cabin = cabinNodes;
                var d = b.def;
                rest = new double3[b.nodeCount];
                for (int i = 0; i < b.nodeCount; i++) rest[i] = (double3)w.pos[b.nodeStart + i];
                cab0 = new double3[cabin.Length];
                for (int k = 0; k < cabin.Length; k++) { cab0[k] = rest[cabin[k]]; c0 += cab0[k]; }
                c0 /= cabin.Length;
                if (d.dampGroups != null)
                    foreach (var g in d.dampGroups)
                        if (g.name == "roof") parts.Add(("roof skin", g.nodes));
                foreach (var part in new[] { "door_FL", "door_FR", "hood" })
                {
                    var l = new List<int>();
                    for (int i = 0; i < d.nodes.Length; i++) if (d.nodes[i].part == part) l.Add(i);
                    parts.Add((part, l.ToArray()));
                }
                foreach (var door in new[] { "door_FL", "door_FR" })
                {
                    var hinge = new List<int>();
                    var latch = new List<int>();
                    var beams = new List<int>();
                    for (int k = 0; k < b.beamCount; k++)
                    {
                        var bd = d.beams[k];
                        bool aIn = d.nodes[bd.a].part == door, bIn = d.nodes[bd.b].part == door;
                        if (aIn == bIn) continue;
                        int body = aIn ? bd.b : bd.a;
                        if (bd.mat == "hinge") hinge.Add(body);
                        if (bd.mat == "latch") { latch.Add(body); beams.Add(b.beamStart + k); }
                    }
                    if (hinge.Count == 0 || latch.Count == 0) continue;
                    doors.Add((door, hinge.ToArray(), latch.ToArray(), math.distance(Mean(hinge.ToArray()), Mean(latch.ToArray())), beams));
                }
            }

            double3 Mean(int[] ids)
            {
                double3 s = 0;
                foreach (int i in ids) s += (double3)w.pos[b.nodeStart + i];
                return s / ids.Length;
            }

            /// <summary>The cabin's rigid motion since the start: x_now = c + R (x_start - c0).</summary>
            public double3x3 CabinFrame(out double3 c, out double3 start)
            {
                start = c0;
                return CabinRotation(out c);
            }

            /// <summary>Rotation of the cabin since the start: polar factor of the cross-covariance (Higham iteration).</summary>
            double3x3 CabinRotation(out double3 c)
            {
                c = 0;
                for (int k = 0; k < cabin.Length; k++) c += (double3)w.pos[b.nodeStart + cabin[k]];
                c /= cabin.Length;
                double3x3 a = double3x3.zero;
                for (int k = 0; k < cabin.Length; k++)
                {
                    double3 p = (double3)w.pos[b.nodeStart + cabin[k]] - c, q = cab0[k] - c0;
                    a += new double3x3(q.x * p, q.y * p, q.z * p);   // columns: sum of p q^T
                }
                double3x3 r = a;
                for (int it = 0; it < 30; it++)
                    r = 0.5 * (r + math.transpose(math.inverse(r)));
                return r;
            }

            public void Sample(double t)
            {
                var r = CabinRotation(out double3 c);
                double3 up = math.mul(r, new double3(0, 1, 0));
                foreach (var (name, nodes) in parts)
                {
                    double m = 0, rise = 0;
                    foreach (int i in nodes)
                    {
                        double3 rigid = c + math.mul(r, rest[i] - c0);
                        double3 d = (double3)w.pos[b.nodeStart + i] - rigid;
                        m = math.max(m, math.length(d));
                        rise = math.max(rise, math.dot(d, up));
                    }
                    maxOffset.TryGetValue(name, out double old);
                    maxOffset[name] = math.max(old, m);
                    maxRise.TryGetValue(name, out double oldR);
                    maxRise[name] = math.max(oldR, rise);
                }
                foreach (var (door, hinge, latch, len0, beams) in doors)
                {
                    double dl = math.abs(math.distance(Mean(hinge), Mean(latch)) - len0);
                    maxApertureChange.TryGetValue(door, out double o1);
                    maxApertureChange[door] = math.max(o1, dl);
                    double f = 0;
                    bool broken = false;
                    foreach (int j in beams)
                    {
                        if (w.broken[j] != 0) { broken = true; continue; }
                        f = math.max(f, w.stress[j] * w.beams[j].strength);
                    }
                    maxLatchForce.TryGetValue(door, out double o2);
                    maxLatchForce[door] = math.max(o2, f);
                    if (broken && !latchBreak.ContainsKey(door)) latchBreak[door] = t;
                }
            }

            public string Report()
            {
                var sb = new System.Text.StringBuilder("offsets from the cabin rigid motion (m):");
                foreach (var kv in maxOffset) sb.Append($" {kv.Key} {kv.Value:F3} (rise {maxRise[kv.Key]:F3})");
                foreach (var (door, _, _, len0, _) in doors)
                {
                    maxApertureChange.TryGetValue(door, out double ap);
                    maxLatchForce.TryGetValue(door, out double lf);
                    sb.Append($" | {door}: aperture {len0:F3} m changed by up to {ap * 1000:F0} mm, latch force up to {lf / 1000:F1} kN");
                    if (latchBreak.TryGetValue(door, out double tb)) sb.Append($", latch broke at {tb * 1000:F0} ms");
                }
                return sb.ToString();
            }
        }

        public static readonly string[] FrontCrush = { "rail_f", "rail_f_brace", "crush_can", "core", "apron", "brace_crush" };

        /// <summary>Scales the yield (deform, cap, hardening) of the crush-zone materials.</summary>
        public static Action<SimParamsDef> CrushYield(float scale, float hardScale = -1f) => p =>
        {
            AddMat(p, "brace", "brace_crush");
            foreach (var name in FrontCrush)
            {
                var m = Mat(p, name);
                if (m == null) continue;
                if (m.deform > 0f) m.deform *= scale;
                if (m.deformCap > 0f) m.deformCap *= scale;
                m.hardening *= hardScale >= 0f ? hardScale : scale;
            }
        };

        public static readonly string[] Structural =
        {
            "rail_f", "rail_f_brace", "crush_can", "core", "apron", "apron_brace", "brace_crush", "bumper_beam", "subframe", "kmember",
            "subframe_mount", "mount_engine", "mount_trans", "rail_r", "rail_r_brace", "brace", "rigidifier", "cell", "cell_brace", "floor",
            "floor_brace", "pillar", "pillar_brace", "dash", "arm", "link",
        };

        /// <summary>Spring-back suppression (D-056) on the structural materials.</summary>
        public static Action<SimParamsDef> Relax(float rate) => p =>
        {
            AddMat(p, "brace", "brace_crush");
            foreach (var name in Structural)
            {
                var m = Mat(p, name);
                if (m != null) m.unloadRelax = rate;
            }
        };

        static Action<SimParamsDef> GroupRate(string name, float rate) => p =>
        {
            foreach (var g in p.dampGroupMaterials)
                if (g.name == name) g.rate = rate;
        };

        static Action<SimParamsDef> All(params Action<SimParamsDef>[] a) => p => { foreach (var x in a) x?.Invoke(p); };

        /// <summary>X24 (diagnostic, P4): T12's top-speed run (full throttle from 270 km/h on a straight, the driver robot
        /// steering, 45 s) with the P4 solver changes switched off one at a time. Reports the cabin floor's pitch drift
        /// (from 30 s to the end) and the robot's path offset, and at the end where the structure crept: the change of the
        /// beams' rest lengths since the launch, the plastic work and the armed (relaxing) beams, by material.</summary>
        public static TestResult TopSpeedDrift(ValidationContext ctx)
        {
            var r = new TestResult();
            bool longRun = ctx.quick;   // -valQuick 1: one 120 s run of the P4 configuration with the wheel loads
            WindupDef Wu(SimParamsDef q, string n) { foreach (var x in q.windup) if (x.name == n) return x; return null; }
            var variants = longRun ? new List<Variant>
            {
                new Variant { name = "steering at zero, cruise 150 km/h, 120 s", openLoop = true, cruiseKmh = 150.0, startKmh = 150.0 },
                new Variant { name = "steering at zero, cruise 150 km/h, integrated wind-up angle, 120 s", openLoop = true, cruiseKmh = 150.0,
                    startKmh = 150.0, tweak = q => { Wu(q, "front").geometricAngle = false; Wu(q, "rear").geometricAngle = false; } },
                new Variant { name = "steering at zero, cruise 150 km/h, wind-up spring off, 120 s", openLoop = true, cruiseKmh = 150.0,
                    startKmh = 150.0, tweak = q => { Wu(q, "front").stiffness = 0f; Wu(q, "rear").stiffness = 0f; } },
                new Variant { name = "steering at zero, neutral from 282 km/h, 60 s", coast = true, startKmh = 282.0 },
            } : new List<Variant>
            {
                new Variant { name = "P4 configuration" },
                new Variant { name = "without spring-back suppression (D-056)", tweak = Relax(0f) },
                new Variant { name = "structure damp group rate 5 (as P3b)", tweak = GroupRate("structure", 5f) },
                new Variant { name = "without hard contact (D-055)", tweak = HardContact(false) },
                new Variant { name = "without self-collision of the detachables (D-058)", defTweak = d =>
                {
                    foreach (var n in d.nodes) n.flags &= ~NodeFlag.SelfCollision;
                } },
            };
            foreach (var v in variants)
            {
                using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f, v.tweak, defTweak: v.defTweak);
                var b = w.bodies[0];
                var probe = new CarProbe(w, 0);
                Dyn.LaunchAt(w, v.startKmh / 3.6);
                var f0 = probe.Frame();
                var rest0 = new float[b.beamCount];
                for (int k = 0; k < b.beamCount; k++) rest0[k] = w.rest[b.beamStart + k];
                var robot = new DriverRobot(b.prm)
                {
                    path = PolyPath.Line(new double2(f0.rearAxle.x, f0.rearAxle.z), math.normalize(new double2(f0.forward.x, f0.forward.z)), 6000.0),
                    targetSpeed = (t, a) => v.cruiseKmh > 0.0 ? v.cruiseKmh / 3.6 : 200.0,
                };
                v.robot?.Invoke(robot);
                var s = new Series("t", "speed_kmh", "lateral", "pitch_deg", "roll_deg", "load_FR", "load_FL", "load_RR", "load_RL", "com_y",
                    "hub_FR", "hub_FL", "hub_RR", "hub_RL", "heading_deg", "steer", "rwa_FR", "rwa_FL", "rwa_RR", "rwa_RL",
                    "wu_FR", "wu_FL", "wu_RR", "wu_RL");
                int[] wi4 = { probe.WheelIndex("FR"), probe.WheelIndex("FL"), probe.WheelIndex("RR"), probe.WheelIndex("RL") };
                double[] hub0 = { probe.HubY(wi4[0]), probe.HubY(wi4[1]), probe.HubY(wi4[2]), probe.HubY(wi4[3]) };
                double latMax = 0, pitch30 = double.NaN, pitchEnd = 0;
                int i0 = b.wheelStart;
                Dyn.Drive(w, longRun ? (v.coast ? 60.0 : 120.0) : 45.0, 20, (t, f) =>
                {
                    var inp = robot.Control(t, 20 * w.dt, f);
                    if (v.coast) inp = new DriverInput { gear = 0 };
                    else if (v.openLoop && v.cruiseKmh > 0.0) inp.steer = 0f;
                    else if (v.openLoop) inp = new DriverInput { throttle = 1f, gear = DriverInput.Drive, flags = DriverInput.FlagTc };
                    return inp;
                }, (t, f) =>
                {
                    double p = f.pitchDeg - f0.pitchDeg;
                    if (t > 2.0) latMax = math.max(latMax, math.abs(robot.lateral));
                    if (double.IsNaN(pitch30) && t >= 30.0) pitch30 = p;
                    pitchEnd = p;
                    s.Add(t, f.speed * 3.6, robot.lateral, p, f.rollDeg, w.wheelState[i0].load, w.wheelState[i0 + 1].load,
                        w.wheelState[i0 + 2].load, w.wheelState[i0 + 3].load, f.com.y - f0.com.y,
                        probe.HubY(wi4[0]) - hub0[0], probe.HubY(wi4[1]) - hub0[1], probe.HubY(wi4[2]) - hub0[2], probe.HubY(wi4[3]) - hub0[3],
                        math.degrees(f.heading - f0.heading), w.vehicleState[b.vehicleIndex].steer,
                        probe.RoadWheelDeg(wi4[0], f), probe.RoadWheelDeg(wi4[1], f), probe.RoadWheelDeg(wi4[2], f), probe.RoadWheelDeg(wi4[3], f),
                        math.degrees(w.wheelState[b.wheelStart + wi4[0]].windupAngle), math.degrees(w.wheelState[b.wheelStart + wi4[1]].windupAngle),
                        math.degrees(w.wheelState[b.wheelStart + wi4[2]].windupAngle), math.degrees(w.wheelState[b.wheelStart + wi4[3]].windupAngle));
                    return true;
                }, probe);
                s.Write(ctx.FilePath(r, $"top_speed_{variants.IndexOf(v)}{(longRun ? "_long" : "")}.csv"));
                var creep = new Dictionary<string, double>();
                var plastic = new Dictionary<string, double>();
                var armed = new Dictionary<string, int>();
                int broken = 0;
                for (int k = 0; k < b.beamCount; k++)
                {
                    int j = b.beamStart + k;
                    string mat = b.def.beams[k].mat;
                    if (w.broken[j] != 0) { broken++; continue; }
                    double dr = math.abs(w.rest[j] - rest0[k]);
                    if (dr > 1e-6) { creep.TryGetValue(mat, out double c); creep[mat] = c + dr; }
                    if (w.plasticWork[j] > 0f) { plastic.TryGetValue(mat, out double pw); plastic[mat] = pw + w.plasticWork[j]; }
                    if (w.RelaxArmed(j)) { armed.TryGetValue(mat, out int a); armed[mat] = a + 1; }
                }
                string Top<T>(Dictionary<string, T> d, Func<T, double> key, Func<T, string> fmt)
                {
                    var l = new List<KeyValuePair<string, T>>(d);
                    l.Sort((x, y) => key(y.Value).CompareTo(key(x.Value)));
                    var sb = new System.Text.StringBuilder();
                    for (int k = 0; k < math.min(8, l.Count); k++) sb.Append(k > 0 ? ", " : "").Append($"{l[k].Key} {fmt(l[k].Value)}");
                    return sb.Length > 0 ? sb.ToString() : "none";
                }
                r.Info($"{v.name}: pitch drift from 30 s to the end (nose up negative)", pitchEnd - pitch30, "deg",
                    $"pitch at 30 s {pitch30:F2} deg, at the end {pitchEnd:F2} deg; path offset {latMax:F2} m; broken beams {broken}");
                r.notes.Add($"{v.name}: rest-length change since the launch (sum, mm): {Top(creep, x => x, x => (x * 1000).ToString("F1"))} | " +
                       $"plastic work (J): {Top(plastic, x => x, x => x.ToString("F1"))} | armed beams: {Top(armed, x => x, x => x.ToString())}");
            }
            return r;
        }

        public static TestResult WallVariants(ValidationContext ctx)
        {
            var r = new TestResult();
            var variants = new List<Variant>
            {
                new Variant { name = "S1 configuration" },
                new Variant { name = "without hard contact (D-055)", tweak = HardContact(false) },
                new Variant { name = "without spring-back suppression (D-056)", tweak = All(Relax(0f), GroupRate("structure", 5f)) },
                new Variant { name = "without self-collision of the detachables (D-058)", defTweak = d =>
                {
                    foreach (var n in d.nodes) n.flags &= ~NodeFlag.SelfCollision;
                } },
                new Variant { name = "configuration at 30 km/h", kmh = 30f },
                new Variant { name = "configuration at 64 km/h", kmh = 64f },
                new Variant { name = "configuration at 120 km/h", kmh = 120f },
            };
            foreach (var v in variants)
            {
                var o = Run(ctx, r, v);
                Report(r, o);
            }
            r.notes.Add($"Settled Hellcat launched rolling (Launch) {Gap} m before a rigid concrete wall, neutral, no brakes. Crush: cabin " +
                        "travel from the first wall force above 5 kN until the cabin stops. Energy created: largest rise of (kinetic + " +
                        "gravity + elastic + torsion + pressure + driveline + damping + plastic + breaking) above its value at the contact " +
                        "start; the wall and the ground are passive, so this sum may only fall. Energies in kJ by material.");
            return r;
        }

        static void Report(TestResult r, Outcome o)
        {
            string p = o.name + ": ";
            r.Info(p + "entry speed", o.entryKmh, "km/h");
            r.Info(p + "dynamic crush (cabin travel to the stop)", o.crush, "m");
            r.Info(p + "pulse duration", o.pulseMs, "ms");
            r.Info(p + "peak cabin deceleration, 1 ms / 10 ms mean", o.peakG1ms, "g", $"{o.peakG10ms:F1} g over 10 ms, mean {o.meanG:F1} g");
            r.Info(p + "peak wall force", o.wallPeakKN, "kN");
            r.Info(p + "rebound speed of the cabin", o.reboundMps, "m/s");
            r.Info(p + "kinetic energy after the stop (largest within 0.4 s)", o.reboundKeJ, "J", $"at contact {o.keAtContact:F0} J");
            r.Info(p + "pitch (nose down) / rear lift / cabin rise", o.maxPitchDeg, "deg", $"rear lift {o.maxRearLift:F3} m, cabin rise {o.maxCabinRise:F3} m");
            r.Info(p + "energy created (largest balance rise)", o.excessJ, "J");
            r.Info(p + "plastic / breaking / damping / -contact / elastic at the end", o.plasticJ, "J",
                $"breaking {o.breakingJ:F0}, damping {o.dampingJ:F0}, contact {-o.contactJ:F0}, elastic {o.elasticJ:F0}");
            r.Info(p + "broken / plastic beams", o.brokenBeams, "", $"plastic {o.plasticBeams}");
            r.notes.Add(p + "at the cabin stop: " + o.atStop);
            r.notes.Add(p + "at the end: " + o.atEnd);
            r.Info(p + "colliding nodes past the wall face / non-finite", o.tunnelled, "", $"non-finite {o.nonFinite}, max node speed {o.maxNodeSpeed:F1} m/s");
            r.Info(p + "solver time per substep (editor, energy tracking on)", o.stepUs, "us");
        }

        /// <summary>Passenger-cell nodes (body nodes between the A and C pillars below the belt line, as CrashMetrics).</summary>
        public static int[] CabinNodes(VehicleDef d)
        {
            var l = new List<int>();
            for (int i = 0; i < d.nodes.Length; i++)
            {
                var n = d.nodes[i];
                if (n.part == "body" && n.p[2] > -1.05f && n.p[2] < 0.85f && n.p[1] < 1.0f && math.abs(n.p[0]) < 0.95f)
                    l.Add(i);
            }
            return l.ToArray();
        }

        public static Outcome Run(ValidationContext ctx, TestResult r, Variant v, double after = 0.6, bool writeCsv = true)
        {
            var (def, prm) = LoadHellcat(ctx);
            v.tweak?.Invoke(prm);
            v.defTweak?.Invoke(def);
            float front = float.MinValue;
            foreach (var n in def.nodes) front = math.max(front, n.p[2]);
            float wallZ = front + Gap;
            var statics = Ground();
            statics.AddBox(new float3(0f, 1.5f, wallZ + 0.5f), quaternion.identity, new float3(6f, 1.5f, 0.5f), "concrete", "wall_O1");
            using var w = new SoftBodyWorld(prm) { trackEnergy = true };
            int bi = w.AddBody("hellcat", def, prm, float3.zero, quaternion.identity, float3.zero, true);
            w.bodies[bi].spawnClearance = 0.01f;
            w.Build(statics);
            var b = w.bodies[bi];
            // settled spawn as SimRunner (D-037): parked while settling (in drive the car would creep towards the wall)
            w.SetInput(b.vehicleIndex, new DriverInput { brake = 1f, handbrake = 1f, gear = 0 });
            w.Settle(bi);
            float speed = v.kmh / 3.6f;
            w.Launch(bi, new float3(0f, 0f, speed));
            w.SetInput(b.vehicleIndex, DriverInput.Neutral);

            int[] cabin = CabinNodes(def);
            var rearIdx = new List<int>();
            var frontCab = new List<int>();
            var rearCab = new List<int>();
            for (int i = 0; i < def.nodes.Length; i++)
            {
                var n = def.nodes[i];
                if (n.part == "body" && n.p[2] < -1.75f && n.p[1] < 0.8f) rearIdx.Add(i);
            }
            foreach (int i in cabin)
            {
                if (def.nodes[i].p[2] > 0.4f) frontCab.Add(i);
                if (def.nodes[i].p[2] < -0.6f) rearCab.Add(i);
            }
            double Avg(List<int> ids, int axis)
            {
                double s = 0, m = 0;
                foreach (int i in ids) { double mi = 1.0 / w.invMass[b.nodeStart + i]; s += mi * w.pos[b.nodeStart + i][axis]; m += mi; }
                return s / m;
            }
            void Cabin(out double3 c, out double3 vel)
            {
                double3 p = 0, q = 0;
                double m = 0;
                foreach (int i in cabin)
                {
                    int g = b.nodeStart + i;
                    double mi = 1.0 / w.invMass[g];
                    p += mi * (double3)w.pos[g];
                    q += mi * (double3)w.vel[g];
                    m += mi;
                }
                c = p / m;
                vel = q / m;
            }
            var closures = new ClosureWatch(w, bi, cabin);
            double Pitch() => math.degrees(math.atan2(Avg(frontCab, 1) - Avg(rearCab, 1), Avg(frontCab, 2) - Avg(rearCab, 2)));
            double rear0 = Avg(rearIdx, 1), pitch0 = Pitch();
            Cabin(out double3 cab0, out _);

            var s = new Series("t", "cabin_vz", "cabin_y", "cabin_z", "decel_g", "wall_kN", "pitch_deg", "rear_lift", "kinetic", "stored",
                "plastic", "breaking", "damping", "contact", "balance", "broken");
            double tContact = -1, tStop = -1, crush = 0, prevVz = double.NaN, prevT = 0, peak1 = 0, reb = 0, maxPitch = 0, maxLift = 0,
                maxRise = 0, bal0 = double.NaN, excess = 0, keAfter = 0, wallPeak = 0, keContact = 0;
            int tunnelled = 0;
            double deepest = 0;
            string deepestName = "";
            var decel = new List<double>();
            string atStop = "";
            const int chunk = 2;                   // 1 ms
            double tEnd = Gap / speed + 0.25 + after;
            SoftBodyWorld.BodyMetrics m = default;
            long step0 = w.StepsTaken;           // the settling stepped the world already
            var watch = new System.Diagnostics.Stopwatch();
            while ((w.StepsTaken - step0) * (double)w.dt < tEnd)
            {
                w.UpdateNearLists(chunk * w.dt + 0.05f);
                w.ClearContactImp();
                watch.Start();
                w.Step(chunk);
                watch.Stop();
                double t = (w.StepsTaken - step0) * (double)w.dt;
                double fWall = 0;
                int past = 0;
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                {
                    float3 p = w.pos[i];
                    if (p.z > wallZ - 0.05f && p.y > 0.03f)
                        fWall -= w.contactImp[i].z;
                    if ((w.nodeFlags[i] & NodeFlag.StaticCollision) != 0 && p.z > wallZ + 1e-3f && p.y < 3f && math.abs(p.x) < 6f)
                    {
                        past++;
                        if (p.z - wallZ > deepest)
                        {
                            deepest = p.z - wallZ;
                            deepestName = $"{def.nodes[i - b.nodeStart].name} {deepest * 1000:F1} mm at {t * 1000:F1} ms (latch {w.contactLatch[i]})";
                        }
                    }
                }
                fWall /= chunk * w.dt;
                tunnelled = math.max(tunnelled, past);
                wallPeak = math.max(wallPeak, fWall);
                Cabin(out double3 c, out double3 cv);
                double g = double.IsNaN(prevVz) ? 0 : -(cv.z - prevVz) / (t - prevT) / 9.81;
                m = w.Metrics(bi);
                double stored = m.Mechanical;
                double balance = stored + m.Dissipated;
                if (tContact < 0 && fWall > 5000)
                {
                    tContact = t;
                    bal0 = balance;
                    keContact = m.kinetic;
                }
                if (tContact >= 0)
                {
                    closures.Sample(t - tContact);
                    excess = math.max(excess, balance - bal0);
                    if (tStop < 0)
                    {
                        crush += 0.5 * (cv.z + prevVz) * (t - prevT);
                        decel.Add(g);
                        peak1 = math.max(peak1, g);
                        if (cv.z <= 0)
                        {
                            tStop = t;
                            atStop = $"kinetic {m.kinetic / 1000:F1}, elastic {m.elastic / 1000:F1}, torsion {m.torsion / 1000:F1}, pressure " +
                                     $"{m.pressure / 1000:F1}, gravity {m.gravity / 1000:F1}, driveline {m.driveline / 1000:F1}, plastic {m.plastic / 1000:F1}, " +
                                     $"damping {m.damping / 1000:F1} | {ByRegion(w, bi)} | elastic by material: {ByMaterial(w, bi, true)} | " +
                                     $"plastic: {ByMaterial(w, bi, false)}";
                        }
                    }
                    else if (t - tStop < 0.4)
                    {
                        keAfter = math.max(keAfter, m.kinetic);
                        reb = math.min(reb, cv.z);
                    }
                    maxPitch = math.min(maxPitch, Pitch() - pitch0);
                    maxLift = math.max(maxLift, Avg(rearIdx, 1) - rear0);
                    maxRise = math.max(maxRise, c.y - cab0.y);
                }
                if (tContact >= 0 || t > Gap / speed - 0.05)
                    s.Add(t, cv.z, c.y, c.z, g, fWall / 1000.0, Pitch() - pitch0, Avg(rearIdx, 1) - rear0, m.kinetic, stored,
                        m.plastic, m.breaking, m.damping, m.contactWork, double.IsNaN(bal0) ? 0 : balance - bal0, m.brokenBeams);
                prevVz = cv.z;
                prevT = t;
            }
            double peak10 = 0, mean = 0;
            for (int k = 0; k < decel.Count; k++)
            {
                mean += decel[k];
                if (k >= 9)
                {
                    double a = 0;
                    for (int j = k - 9; j <= k; j++) a += decel[j];
                    peak10 = math.max(peak10, a / 10);
                }
            }
            mean /= math.max(decel.Count, 1);
            string tag = v.name.Replace(' ', '_').Replace(',', '_').Replace('(', '_').Replace(')', '_').Replace('/', '_').Replace('+', 'p').Replace('.', 'p');
            string file = writeCsv ? ctx.FilePath(r, $"wall_{v.kmh:F0}kmh_{tag}.csv") : null;
            if (file != null) s.Write(file);
            return new Outcome
            {
                name = v.name, entryKmh = speed * 3.6, crush = crush, pulseMs = tStop > 0 ? (tStop - tContact) * 1000 : double.NaN,
                peakG1ms = peak1, peakG10ms = peak10, meanG = mean, reboundMps = -reb, maxPitchDeg = -maxPitch, maxRearLift = maxLift,
                maxCabinRise = maxRise, excessJ = excess, reboundKeJ = keAfter, brokenBeams = m.brokenBeams, plasticBeams = m.plasticBeams,
                maxNodeSpeed = m.maxNodeSpeed, wallPeakKN = wallPeak / 1000, tunnelled = tunnelled, nonFinite = m.nonFinite,
                plasticJ = m.plastic, breakingJ = m.breaking, dampingJ = m.damping, contactJ = m.contactWork, elasticJ = m.elastic,
                keAtContact = keContact, csv = file, atStop = atStop,
                stepUs = watch.Elapsed.TotalMilliseconds * 1000.0 / math.max(w.StepsTaken - step0, 1),
                atEnd = $"elastic by material: {ByMaterial(w, bi, true)} | plastic: {ByMaterial(w, bi, false, 14)} | {Damage(w, bi)} | " +
                        closures.Report() + $" | deepest colliding node in the wall: {deepestName}",
            };
        }
    }
}
