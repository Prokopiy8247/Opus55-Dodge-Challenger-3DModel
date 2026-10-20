using System;
using System.Collections.Generic;
using System.Text;
using Hellcat.Sim.Data;
using Hellcat.Sim.Vehicle;
using Unity.Mathematics;
using static Hellcat.Sim.Validation.ValidationSuite;

namespace Hellcat.Sim.Validation
{
    /// <summary>X22 (diagnostic, P4): finds where a crash creates energy. Runs the X21 wall impact for a variant one substep
    /// at a time and books every step's change of the energy sum (kinetic, gravity, beam elastic, hinges and bars, tire
    /// cavities, driveline; beam, group, hinge, bar and driveline damping; plastic work; breaking). For the steps with the
    /// largest rise it lists the terms, the nodes that gained the most kinetic energy and the beams whose elastic energy
    /// rose most, so a jump can be traced to a beam, a contact or a damper.</summary>
    public static class EnergyJumpDiagnostics
    {
        public static TestResult Run(ValidationContext ctx) => Hunt(ctx, CrashDiagnostics.Kmh, true);

        /// <summary>X23: the same hunt in the configuration at 120 km/h (T8 speed): which element drives nodes to the speed
        /// clamp.</summary>
        public static TestResult Run120(ValidationContext ctx) => Hunt(ctx, 120f, false);

        static TestResult Hunt(ValidationContext ctx, float kmh, bool noRelax)
        {
            var r = new TestResult();
            var variant = new CrashDiagnostics.Variant
            {
                name = "without spring-back suppression (D-056)",
                tweak = p =>
                {
                    foreach (var name in CrashDiagnostics.Structural)
                    {
                        var m = CrashDiagnostics.Mat(p, name);
                        if (m != null) m.unloadRelax = 0f;
                    }
                    foreach (var g in p.dampGroupMaterials)
                        if (g.name == "structure") g.rate = 5f;
                },
            };
            var (def, prm) = LoadHellcat(ctx);
            if (noRelax) variant.tweak(prm);
            float front = float.MinValue;
            foreach (var n in def.nodes) front = math.max(front, n.p[2]);
            float wallZ = front + 2.0f;
            var statics = Ground();
            statics.AddBox(new float3(0f, 1.5f, wallZ + 0.5f), quaternion.identity, new float3(6f, 1.5f, 0.5f), "concrete", "wall_O1");
            using var w = new SoftBodyWorld(prm) { trackEnergy = true };
            int bi = w.AddBody("hellcat", def, prm, float3.zero, quaternion.identity, float3.zero, true);
            w.bodies[bi].spawnClearance = 0.01f;
            w.Build(statics);
            var b = w.bodies[bi];
            w.SetInput(b.vehicleIndex, new DriverInput { brake = 1f, handbrake = 1f, gear = 0 });
            w.Settle(bi);
            w.Launch(bi, new float3(0f, 0f, kmh / 3.6f));
            w.SetInput(b.vehicleIndex, DriverInput.Neutral);

            int nb = b.beamCount, nn = b.nodeCount;
            var elPrev = new double[nb];
            var kePrev = new double[nn];
            double Total(out double[] parts)
            {
                var m = w.Metrics(bi);
                double beamDamp = 0, groupDamp = 0, other = 0;
                for (int j = b.beamStart; j < b.beamStart + nb; j++) beamDamp += w.dampEnergy[j];
                for (int t = b.dampGroupStart; t < b.dampGroupStart + b.dampGroupCount; t++) groupDamp += w.dampGroupEnergy[t];
                other = m.damping - beamDamp - groupDamp;
                parts = new[] { m.kinetic, m.gravity, m.elastic, m.torsion, m.pressure, m.driveline, beamDamp, groupDamp, other, m.plastic, m.breaking };
                return m.Mechanical + m.Dissipated;
            }
            string[] names = { "kinetic", "gravity", "elastic", "torsion+hinges", "pressure", "driveline", "beam damping", "group damping",
                "other damping", "plastic", "breaking" };
            void Snapshot()
            {
                for (int k = 0; k < nb; k++) elPrev[k] = w.BeamElasticEnergy(b.beamStart + k);
                for (int i = 0; i < nn; i++)
                {
                    float im = w.invMass[b.nodeStart + i];
                    kePrev[i] = im > 0f ? 0.5 / im * math.lengthsq((double3)w.vel[b.nodeStart + i]) : 0.0;
                }
            }

            double prevTotal = Total(out double[] prevParts);
            Snapshot();
            var jumps = new List<(double rise, double t, string text)>();
            long step0 = w.StepsTaken;
            var brokenPrev = new byte[nb];
            double tEnd = 0.40;
            while ((w.StepsTaken - step0) * (double)w.dt < tEnd)
            {
                w.UpdateNearLists(w.dt + 0.05f);
                w.Step(1);
                double t = (w.StepsTaken - step0) * (double)w.dt;
                double total = Total(out double[] parts);
                double rise = total - prevTotal;
                double vmaxNow = 0;
                for (int i = 0; i < nn; i++) vmaxNow = math.max(vmaxNow, math.length(w.vel[b.nodeStart + i]));
                if (rise > 50.0 || vmaxNow > 100.0)
                {
                    var sb = new StringBuilder();
                    sb.Append($"t {t * 1000:F1} ms: +{rise:F0} J (fastest node {vmaxNow:F0} m/s) =");
                    for (int k = 0; k < parts.Length; k++)
                    {
                        double d = parts[k] - prevParts[k];
                        if (math.abs(d) > 5) sb.Append($" {names[k]} {d:+0;-0}");
                    }
                    // nodes that gained the most kinetic energy
                    var gain = new List<(double d, int i)>();
                    for (int i = 0; i < nn; i++)
                    {
                        float im = w.invMass[b.nodeStart + i];
                        double ke = im > 0f ? 0.5 / im * math.lengthsq((double3)w.vel[b.nodeStart + i]) : 0.0;
                        gain.Add((ke - kePrev[i], i));
                    }
                    gain.Sort((x, y) => y.d.CompareTo(x.d));
                    sb.Append(" | nodes:");
                    for (int k = 0; k < 6; k++)
                    {
                        int i = gain[k].i;
                        float3 v = w.vel[b.nodeStart + i];
                        sb.Append($" {def.nodes[i].name} +{gain[k].d:F0} J (v {math.length(v):F1} m/s, latch {w.contactLatch[b.nodeStart + i]})");
                    }
                    var el = new List<(double d, int k)>();
                    for (int k = 0; k < nb; k++)
                    {
                        double e = w.BeamElasticEnergy(b.beamStart + k);
                        el.Add((e - elPrev[k], k));
                        if (w.broken[b.beamStart + k] != 0 && brokenPrev[k] == 0)
                            sb.Append($" | broke {def.beams[k].mat} {def.nodes[def.beams[k].a].name}-{def.nodes[def.beams[k].b].name}");
                    }
                    el.Sort((x, y) => y.d.CompareTo(x.d));
                    sb.Append(" | beams:");
                    for (int k = 0; k < 6; k++)
                    {
                        var bd = def.beams[el[k].k];
                        sb.Append($" {bd.mat} {def.nodes[bd.a].name}-{def.nodes[bd.b].name} +{el[k].d:F0} J");
                    }
                    jumps.Add((math.max(rise, vmaxNow * 10.0), t, sb.ToString()));
                }
                for (int k = 0; k < nb; k++) brokenPrev[k] = w.broken[b.beamStart + k];
                prevTotal = total;
                prevParts = parts;
                Snapshot();
            }
            jumps.Sort((x, y) => y.rise.CompareTo(x.rise));
            double sum = 0;
            foreach (var j in jumps) sum += j.rise;
            r.Info("steps that raised the energy sum by more than 50 J", jumps.Count, "", $"together {sum:F0} J");
            for (int k = 0; k < math.min(12, jumps.Count); k++)
                r.notes.Add(jumps[k].text);
            return r;
        }
    }
}
