using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using Hellcat.Sim.Data;
using Unity.Mathematics;

namespace Hellcat.Sim.Validation
{
    /// <summary>One numeric check of a validation test.</summary>
    public sealed class Check
    {
        public string name;
        public double value;
        public string unit;
        public string limit;   // human-readable criterion
        public bool pass;
        public bool info;      // informational (not part of PASS/FAIL)
    }

    public sealed class TestResult
    {
        public string id, title;
        public readonly List<Check> checks = new List<Check>();
        public readonly List<string> notes = new List<string>();
        public readonly List<string> files = new List<string>();
        public double seconds;
        public string error;

        public bool Pass
        {
            get
            {
                if (error != null)
                    return false;
                foreach (var c in checks)
                    if (!c.info && !c.pass)
                        return false;
                return true;
            }
        }

        public void Max(string name, double value, double limit, string unit = "") =>
            checks.Add(new Check { name = name, value = value, unit = unit, limit = $"<= {Fmt(limit)}", pass = value <= limit });

        public void Min(string name, double value, double limit, string unit = "") =>
            checks.Add(new Check { name = name, value = value, unit = unit, limit = $">= {Fmt(limit)}", pass = value >= limit });

        public void Near(string name, double value, double target, double relTol, string unit = "") =>
            checks.Add(new Check
            {
                name = name, value = value, unit = unit, limit = $"{Fmt(target)} +- {relTol * 100:0.###} %",
                pass = math.abs(value - target) <= relTol * math.abs(target),
            });

        public void NearAbs(string name, double value, double target, double absTol, string unit = "") =>
            checks.Add(new Check
            {
                name = name, value = value, unit = unit, limit = $"{Fmt(target)} +- {Fmt(absTol)}",
                pass = math.abs(value - target) <= absTol,
            });

        public void Info(string name, double value, string unit = "", string note = "") =>
            checks.Add(new Check { name = name, value = value, unit = unit, limit = note, pass = true, info = true });

        public void Flag(string name, bool ok, string limit) =>
            checks.Add(new Check { name = name, value = ok ? 1 : 0, unit = "", limit = limit, pass = ok });

        public static string Fmt(double v) => v.ToString(math.abs(v) >= 1e5 || (math.abs(v) < 1e-3 && v != 0) ? "0.###e+0" : "0.#####", CultureInfo.InvariantCulture);
    }

    /// <summary>Time series written as CSV (one row per sample).</summary>
    public sealed class Series
    {
        readonly string[] columns;
        readonly List<double[]> rows = new List<double[]>();

        public Series(params string[] columns) => this.columns = columns;

        public int Count => rows.Count;
        public double[] this[int i] => rows[i];

        public void Add(params double[] values)
        {
            if (values.Length != columns.Length)
                throw new ArgumentException($"expected {columns.Length} values, got {values.Length}");
            rows.Add(values);
        }

        public void Write(string path)
        {
            var sb = new StringBuilder();
            sb.AppendLine(string.Join(",", columns));
            var ic = CultureInfo.InvariantCulture;
            foreach (var r in rows)
            {
                for (int k = 0; k < r.Length; k++)
                {
                    if (k > 0)
                        sb.Append(',');
                    sb.Append(r[k].ToString("R", ic));
                }
                sb.AppendLine();
            }
            File.WriteAllText(path, sb.ToString());
        }
    }

    public sealed class ValidationContext
    {
        public string outDir;
        public string vehicleFolder;   // folder with geometry.json and params.json of the Hellcat
        public Action<string> log = s => { };
        public bool quick;             // shorter runs (smoke test)
        public double referenceS = double.NaN; // exact S of the skeleton from tools/skeleton/stability.py (docs/p2_stability.json)
        public string currentId = "";  // set by the runner
        public string resultsFile = "validation_results.json";

        public string FilePath(TestResult r, string name)
        {
            string f = $"{currentId}_{name}";
            r.files.Add(f);
            return Path.Combine(outDir, f);
        }
    }

    /// <summary>Runs the validation tests of brief section 10 (1-8) plus the energy-drift and determinism checks of G-Solver.</summary>
    public static class ValidationSuite
    {
        public delegate TestResult TestFn(ValidationContext ctx);

        public static readonly List<(string id, string title, TestFn fn)> Tests = new List<(string, string, TestFn)>
        {
            ("T1", "Single beam: frequency, damping, static stretch and compression", StructuralTests.SingleBeam),
            ("T2", "Pendulum and hanging chain: period and energy", StructuralTests.PendulumChain),
            ("T3", "Cube with and without diagonal bracing", StructuralTests.Cube),
            ("T4", "Force-displacement: tensile cycle and falling-mass crush", StructuralTests.ForceDisplacement),
            ("T5", "Rigid box: drop on the ground, rest and slide on slopes", StructuralTests.BoxDropSlope),
            ("T6", "Hellcat: drop from 0.2 m, settle, rest", VehicleTests.CarDrop),
            ("T7", "Hellcat: locked-wheel stop from 50 km/h and lateral slide", VehicleTests.CarSlide),
            ("T8", "Tunnelling at 120 km/h: 20 cm static wall, node-beam wall", VehicleTests.Tunnelling),
            ("E1", "Hellcat free-floating 10 s: energy drift", VehicleTests.EnergyDrift),
            ("D1", "Determinism: re-run and single vs multi-thread", VehicleTests.Determinism),
        };

        /// <summary>Vehicle dynamics tests 9-14 of brief section 10 (P3b, gate G-Dynamics).</summary>
        public static readonly List<(string id, string title, TestFn fn)> DynamicsTests = new List<(string, string, TestFn)>
        {
            ("T9", "Tire: load-deflection, pressure vs volume, free rolling, slip-angle and slip-ratio sweeps, puncture", TireTests.Tire),
            ("T10", "Suspension: static corner loads, bounce, 50 mm step, curb strike, roll gradient, anti-roll bars", HandlingTests.Suspension),
            ("T11", "Steering: angle vs input on turntables, ratio, speed-sensitive reduction, return to centre", HandlingTests.Steering),
            ("T12", "Powertrain: idle, rev limit, gear ratios, 0-100 km/h, top speed, engine braking, wheelspin", PowertrainTests.Powertrain),
            // diagnostics (ids starting with X run only when requested with -valTests)
            ("X9", "Diagnostic: rolling losses of the tire rig by source", TireTests.RollingLosses),
            ("X10", "Diagnostic: tire tuning metrics of a list of variants", TireTests.TireTuning),
            ("X12", "Diagnostic: straight line at speed without the driver robot", SpeedDiagnostics.StraightLine),
            ("X13", "Diagnostic: traction control and ABS gains on the launch and the stop", AssistTuning.Run),
            ("X14", "Diagnostic: rig drive and braking slip sweeps at several speeds and loads", TireTests.SlipSpeedSweeps),
            ("X15", "Diagnostic: tire friction curve and contact anchor variants on the rig", TireTests.FrictionTuning),
            ("X16", "Diagnostic: driver robot steering at 250 km/h, variants", SpeedDiagnostics.RobotAtSpeed),
            ("X17", "Diagnostic: elastokinematics of the parked car (toe and camber under hub forces)", SpeedDiagnostics.Elastokinematics),
            ("X18", "Diagnostic: skidpad balance for anti-roll-bar, rear toe and traction-control variants", HandlingTests.Balance),
            ("X19", "Diagnostic: driver robot variants on the slalom", HandlingTests.SlalomRobot),
            ("X20", "Diagnostic: the 0.2 m drop for parameter variants (settling, residual ringing)", DropDiagnostics.DropVariants),
            ("X21", "Diagnostic: the settled car rolling at 50 km/h into a rigid wall, contact and structure variants", CrashDiagnostics.WallVariants),
            ("X22", "Diagnostic: where a wall impact raises the energy sum, step by step", EnergyJumpDiagnostics.Run),
            ("X23", "Diagnostic: the energy hunt of X22 at 120 km/h (nodes at the speed clamp)", EnergyJumpDiagnostics.Run120),
            ("X24", "Diagnostic: top-speed attitude drift with the P4 solver changes switched off one at a time", CrashDiagnostics.TopSpeedDrift),
            ("T13", "Brakes: 100-0 km/h with and without ABS, steering while braking, handbrake, repeated stops", PowertrainTests.Brakes),
            ("T14", "Drive tests: slalom, skidpad, figure eight, speed bump and curb, ramp jump", HandlingTests.DriveTests),
        };

        /// <summary>Game-layer tests (P4b, gate G-Drive): test 15, record / replay determinism.</summary>
        public static readonly List<(string id, string title, TestFn fn)> GameTests = new List<(string, string, TestFn)>
        {
            ("T15", "Record / replay: the same input recording reproduces the same path", ReplayTests.RecordReplay),
        };

        public static List<TestResult> Run(ValidationContext ctx, ICollection<string> ids) => Run(ctx, ids, Tests);

        public static List<TestResult> Run(ValidationContext ctx, ICollection<string> ids, List<(string id, string title, TestFn fn)> tests)
        {
            Directory.CreateDirectory(ctx.outDir);
            var results = new List<TestResult>();
            foreach (var (id, title, fn) in tests)
            {
                if (ids != null && ids.Count > 0 && !ids.Contains(id))
                    continue;
                if ((ids == null || ids.Count == 0) && id.StartsWith("X"))
                    continue;
                ctx.log($"[Validation] {id} {title} ...");
                var sw = System.Diagnostics.Stopwatch.StartNew();
                ctx.currentId = id;
                TestResult r;
                try
                {
                    r = fn(ctx);
                }
                catch (Exception e)
                {
                    r = new TestResult { error = e.ToString() };
                }
                r.id = id;
                r.title = title;
                r.seconds = sw.Elapsed.TotalSeconds;
                results.Add(r);
                ctx.log($"[Validation] {id}: {(r.Pass ? "PASS" : "FAIL")} in {r.seconds:F1} s" + (r.error != null ? "\n" + r.error : ""));
                foreach (var c in r.checks)
                    ctx.log($"    {(c.info ? "info" : c.pass ? "PASS" : "FAIL")}  {c.name} = {TestResult.Fmt(c.value)} {c.unit}  ({c.limit})");
                foreach (var n in r.notes)
                    ctx.log($"    note  {n}");
                WriteJson(ctx, results);
            }
            return results;
        }

        public static void WriteJson(ValidationContext ctx, List<TestResult> results)
        {
            var ic = CultureInfo.InvariantCulture;
            var sb = new StringBuilder();
            sb.Append("{\n  \"suite\": \"hellcat-validation\",\n");
            sb.Append($"  \"time_utc\": \"{DateTime.UtcNow:yyyy-MM-ddTHH:mm:ssZ}\",\n");
            sb.Append($"  \"quick\": {(ctx.quick ? "true" : "false")},\n  \"tests\": [\n");
            for (int t = 0; t < results.Count; t++)
            {
                var r = results[t];
                sb.Append($"    {{\"id\": \"{r.id}\", \"title\": {Q(r.title)}, \"pass\": {(r.Pass ? "true" : "false")}, \"seconds\": {r.seconds.ToString("F2", ic)},\n");
                sb.Append("     \"checks\": [");
                for (int k = 0; k < r.checks.Count; k++)
                {
                    var c = r.checks[k];
                    sb.Append(k == 0 ? "\n" : ",\n");
                    string v = double.IsFinite(c.value) ? c.value.ToString("R", ic) : "null";
                    sb.Append($"       {{\"name\": {Q(c.name)}, \"value\": {v}, \"unit\": {Q(c.unit)}, \"limit\": {Q(c.limit)}, \"pass\": {(c.pass ? "true" : "false")}, \"info\": {(c.info ? "true" : "false")}}}");
                }
                sb.Append("],\n     \"notes\": [");
                for (int k = 0; k < r.notes.Count; k++)
                    sb.Append((k == 0 ? "" : ", ") + Q(r.notes[k]));
                sb.Append("],\n     \"files\": [");
                for (int k = 0; k < r.files.Count; k++)
                    sb.Append((k == 0 ? "" : ", ") + Q(r.files[k]));
                sb.Append("]");
                if (r.error != null)
                    sb.Append($",\n     \"error\": {Q(r.error)}");
                sb.Append(t == results.Count - 1 ? "}\n" : "},\n");
            }
            sb.Append("  ]\n}\n");
            File.WriteAllText(Path.Combine(ctx.outDir, ctx.resultsFile), sb.ToString());
        }

        static string Q(string s)
        {
            if (s == null)
                return "null";
            var sb = new StringBuilder("\"");
            foreach (char ch in s)
            {
                switch (ch)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (ch < 32)
                            sb.Append($"\\u{(int)ch:x4}");
                        else
                            sb.Append(ch);
                        break;
                }
            }
            return sb.Append('"').ToString();
        }

        // ------------------------------------------------------------------ helpers shared by the tests

        public static SoftBodyWorld Build(SimParamsDef prm, StaticWorldBuilder statics, Action<SoftBodyWorld> addBodies, bool trackEnergy = true)
        {
            var w = new SoftBodyWorld(prm) { trackEnergy = trackEnergy };
            addBodies(w);
            w.Build(statics ?? new StaticWorldBuilder());
            return w;
        }

        /// <summary>Steps in chunks of <paramref name="chunk"/> substeps until <paramref name="seconds"/>; sample after each chunk.</summary>
        public static double Run(SoftBodyWorld w, double seconds, int chunk, Func<double, bool> sample = null)
        {
            long steps = (long)math.round(seconds / w.dt);
            long done = 0;
            var sw = System.Diagnostics.Stopwatch.StartNew();
            double stepSeconds = 0.0;
            while (done < steps)
            {
                int n = (int)math.min(chunk, steps - done);
                w.UpdateNearLists(n * w.dt + 0.05f);
                var t0 = sw.Elapsed.TotalSeconds;
                w.Step(n);
                stepSeconds += sw.Elapsed.TotalSeconds - t0;
                done += n;
                if (sample != null && !sample(w.StepsTaken * (double)w.dt))
                    break;
            }
            return stepSeconds;
        }

        /// <summary>Hellcat geometry and parameters (StreamingAssets copies, synced from sim/vehicle/hellcat).</summary>
        public static (VehicleDef def, SimParamsDef prm) LoadHellcat(ValidationContext ctx)
        {
            var def = VehicleDef.Load(Path.Combine(ctx.vehicleFolder, "geometry.json"));
            var prm = SimParamsDef.Load(Path.Combine(ctx.vehicleFolder, "params.json"));
            return (def, prm);
        }

        public static StaticWorldBuilder Ground(string surface = "asphalt")
        {
            var s = new StaticWorldBuilder();
            s.AddPlane(new float3(0f, 1f, 0f), 0f, surface);
            return s;
        }

        /// <summary>Order-independent bit pattern hash of positions and velocities (determinism check).</summary>
        public static ulong StateHash(SoftBodyWorld w)
        {
            ulong h = 1469598103934665603UL;
            for (int i = 0; i < w.NodeCount; i++)
            {
                float3 p = w.pos[i], v = w.vel[i];
                foreach (float f in new[] { p.x, p.y, p.z, v.x, v.y, v.z })
                {
                    h ^= math.asuint(f);
                    h *= 1099511628211UL;
                }
            }
            return h;
        }
    }
}
