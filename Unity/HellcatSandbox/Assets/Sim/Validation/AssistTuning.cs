using System;
using System.Collections.Generic;
using Hellcat.Sim.Data;
using static Hellcat.Sim.Validation.ValidationSuite;

namespace Hellcat.Sim.Validation
{
    /// <summary>Diagnostic (not in the gate): traction control and ABS gains (D-047) on the T12 launch and the T13 stop.</summary>
    public static class AssistTuning
    {
        struct Variant
        {
            public string name;
            public Action<AssistDef> set;
            public Action<SimParamsDef> prm;
        }

        static Action<SimParamsDef> Tire(float alphaN) => p =>
        {
            foreach (var c in p.contactMaterials)
                if (c.name == "tire")
                    c.alphaNormal = alphaN;
        };

        public static TestResult Run(ValidationContext ctx)
        {
            var r = new TestResult();
            var launches = new List<Variant>
            {
                // P4 (after D-056 / D-057 the 95th percentile of the slip above 36 km/h sat at 0.350, limit 0.35)
                new Variant { name = "base" },
                new Variant { name = "tcKi4", set = a => a.tcKi = 4f },
                new Variant { name = "tcKp0.4", set = a => a.tcKp = 0.4f },
                new Variant { name = "tcKp0.4_tcKi4", set = a => { a.tcKp = 0.4f; a.tcKi = 4f; } },
                new Variant { name = "tcSlip0.19", set = a => a.tcSlip = 0.19f },
                new Variant { name = "tcSlipLow0.28", set = a => a.tcSlipLow = 0.28f },
            };
            var stops = new List<Variant>();
            var s = new Series("index", "t100", "t100_roll", "t60mph_roll", "slip_peak", "slip_after", "a1_g", "distance", "decel_g", "locked_s");
            int index = 0;
            foreach (var v in launches)
            {
                var L = PowertrainTests.Launch(ctx, r, $"launch_{v.name}", true, p => { v.set?.Invoke(p.assists); v.prm?.Invoke(p); }, 7.0);
                s.Add(index++, L.t100, L.t100Roll, L.t60Roll, L.slipPeak, L.slipAfter, L.a1 / Dyn.G, double.NaN, double.NaN, double.NaN);
                r.Info($"{v.name}: 0-100 km/h (1-ft rollout)", L.t100Roll, "s",
                    $"from the throttle {L.t100:F2} s, 0-60 mph (rollout) {L.t60Roll:F2} s; slip peak {L.slipPeak:F2}, above 36 km/h 95th pct {L.slipAfter:F3}, peak {L.slipAfterPeak:F2}; first second {L.a1 / Dyn.G:F2} g");
            }
            foreach (var v in stops)
            {
                var S = PowertrainTests.Stop(ctx, r, $"stop_{v.name}", true, 0.0, p => { v.set?.Invoke(p.assists); v.prm?.Invoke(p); });
                s.Add(index++, double.NaN, double.NaN, double.NaN, double.NaN, double.NaN, double.NaN, S.distance, S.meanDecel / Dyn.G, S.lockedTime);
                r.Info($"{v.name}: 100-0 km/h", S.distance, "m", $"mean deceleration {S.meanDecel / Dyn.G:F3} g, {S.lockedTime:F2} s with a wheel locked, dive {S.peakDive:F2} deg");
            }
            s.Write(ctx.FilePath(r, "assist_tuning.csv"));
            var names = new List<string>();
            foreach (var v in launches) names.Add(v.name);
            foreach (var v in stops) names.Add(v.name);
            r.notes.Add("rows of assist_tuning.csv: " + string.Join(", ", names));
            return r;
        }
    }
}
