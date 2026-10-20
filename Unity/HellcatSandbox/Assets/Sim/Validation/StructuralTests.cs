using System;
using System.Collections.Generic;
using Hellcat.Sim.Data;
using Unity.Mathematics;
using static Hellcat.Sim.Validation.ValidationSuite;

namespace Hellcat.Sim.Validation
{
    /// <summary>Validation tests 1-5 of brief section 10 on small bodies built in code.</summary>
    public static class StructuralTests
    {
        // ------------------------------------------------------------------ helpers

        /// <summary>Times of upward zero crossings (linear interpolation).</summary>
        static List<double> UpCrossings(Series s, int tc, int xc)
        {
            var list = new List<double>();
            for (int i = 1; i < s.Count; i++)
            {
                double x0 = s[i - 1][xc], x1 = s[i][xc];
                if (x0 < 0.0 && x1 >= 0.0)
                    list.Add(s[i - 1][tc] + (0.0 - x0) / (x1 - x0) * (s[i][tc] - s[i - 1][tc]));
            }
            return list;
        }

        static double OmegaFromCrossings(List<double> c) =>
            c.Count >= 2 ? 2.0 * math.PI * (c.Count - 1) / (c[c.Count - 1] - c[0]) : double.NaN;

        /// <summary>Complete elliptic integral of the first kind K(k) by the arithmetic-geometric mean.</summary>
        static double EllipticK(double k)
        {
            double a = 1.0, b = math.sqrt(1.0 - k * k);
            for (int i = 0; i < 30; i++)
            {
                double an = 0.5 * (a + b);
                b = math.sqrt(a * b);
                a = an;
            }
            return math.PI / (2.0 * a);
        }

        static double NodeKinetic(SoftBodyWorld w, int i)
        {
            float im = w.invMass[i];
            return im > 0f ? 0.5 / im * math.lengthsq((double3)w.vel[i]) : 0.0;
        }

        // ------------------------------------------------------------------ T1

        public static TestResult SingleBeam(ValidationContext ctx)
        {
            var r = new TestResult();
            const float dt = 0.0005f;
            double seconds = ctx.quick ? 0.6 : 2.0;

            // (a) fixed-free oscillation, (b) free-free oscillation, (c) damped oscillation
            double Oscillate(string tag, float mA, bool fixedA, float k, float c, out double zeta, out double x0)
            {
                var tb = new TestBody();
                int a = tb.Node("A", float3.zero, mA, fixedA ? NodeFlag.Fixed : TestBody.Free);
                int b = tb.Node("B", new float3(0f, 0f, 1f), 1f, TestBody.Free);
                tb.Beam(a, b, "spring", pre: 1f / 1.01f);
                var prm = TestBody.Params(0f, TestBody.Mat("spring", k, c));
                using var w = Build(prm, null, ww => ww.AddBody("beam", tb.Def("beam"), prm, float3.zero, quaternion.identity, float3.zero, false));
                var s = new Series("t", "x");
                x0 = math.distance(w.pos[a], w.pos[b]) - w.rest[0];
                s.Add(0.0, x0);
                Run(w, seconds, 1, t =>
                {
                    s.Add(t, math.distance(w.pos[a], w.pos[b]) - w.rest[0]);
                    return true;
                });
                s.Write(ctx.FilePath(r, $"{tag}.csv"));
                // damping ratio from the logarithmic decrement of successive maxima
                var peaks = new List<double>();
                for (int i = 1; i + 1 < s.Count; i++)
                    if (s[i][1] > s[i - 1][1] && s[i][1] >= s[i + 1][1] && s[i][1] > 0.0)
                        peaks.Add(s[i][1]);
                zeta = double.NaN;
                if (peaks.Count >= 6)
                {
                    double delta = math.log(peaks[0] / peaks[5]) / 5.0;
                    zeta = delta / math.sqrt(4.0 * math.PI * math.PI + delta * delta);
                }
                return OmegaFromCrossings(UpCrossings(s, 0, 1));
            }

            double w1 = Oscillate("fixed_free", 1f, true, 1e4f, 0f, out _, out double x0a);
            double wa = math.sqrt(1e4);
            r.Near("fixed-free omega (k 1e4 N/m, m 1 kg)", w1, wa, 0.005, "rad/s");
            r.Info("symplectic Euler discrete omega (2/dt) asin(w dt / 2)", 2.0 / dt * math.asin(wa * dt / 2.0), "rad/s");
            r.Info("initial stretch", x0a, "m");

            double w2 = Oscillate("free_free", 2f, false, 1e4f, 0f, out _, out _);
            double mu = 2.0 / 3.0;
            r.Near("free-free omega (2 kg + 1 kg, reduced mass 2/3 kg)", w2, math.sqrt(1e4 / mu), 0.005, "rad/s");

            double w3 = Oscillate("damped", 1f, true, 1e4f, 10f, out double zeta, out _);
            r.Near("damped zeta (c 10 N s/m, analytic 0.05)", zeta, 0.05, 0.03);
            r.Near("damped omega_d", w3, wa * math.sqrt(1.0 - 0.05 * 0.05), 0.005, "rad/s");

            // (d) static stretch (hanging mass) and compression (mass on a column)
            double Static(string tag, float yB)
            {
                var tb = new TestBody();
                int a = tb.Node("A", float3.zero, 1f, NodeFlag.Fixed);
                int b = tb.Node("B", new float3(0f, yB, 0f), 10f, TestBody.Free);
                tb.Beam(a, b, "rod");
                var prm = TestBody.Params(9.81f, TestBody.Mat("rod", 1e5f, 1400f));
                using var w = Build(prm, null, ww => ww.AddBody(tag, tb.Def(tag), prm, float3.zero, quaternion.identity, float3.zero, false));
                Run(w, 1.0, 50);
                return math.distance(w.pos[a], w.pos[b]) - w.rest[0];
            }
            double analytic = 10.0 * 9.81 / 1e5;
            r.Near("static stretch, 10 kg hanging on k 1e5 N/m", Static("hanging", -1f), analytic, 0.002, "m");
            r.Near("static compression, 10 kg on a column", Static("column", 1f), -analytic, 0.002, "m");
            return r;
        }

        // ------------------------------------------------------------------ T2

        public static TestResult PendulumChain(ValidationContext ctx)
        {
            var r = new TestResult();
            double seconds = ctx.quick ? 2.5 : 5.0;
            const float g = 9.81f;

            // (a) pendulum: 1 kg on a stiff 1 m rod, released at 60 degrees
            {
                float th0 = math.radians(60f);
                var tb = new TestBody();
                int pivot = tb.Node("pivot", new float3(0f, 2f, 0f), 1f, NodeFlag.Fixed);
                int bob = tb.Node("bob", new float3(math.sin(th0), 2f - math.cos(th0), 0f), 1f, TestBody.Free);
                tb.Beam(pivot, bob, "rod");
                var prm = TestBody.Params(g, TestBody.Mat("rod", 1e6f, 0f));
                using var w = Build(prm, null, ww => ww.AddBody("pendulum", tb.Def("pendulum"), prm, float3.zero, quaternion.identity, float3.zero, false));
                // Leapfrog energy: positions at step n with the mean of the half-step velocities around it.
                double U() => g * (w.pos[bob].y - 1.0) + 0.5 * 1e6 * math.square(math.distance(w.pos[bob], w.pos[pivot]) - w.rest[0]);
                var s = new Series("t", "x", "y", "energy");
                double e0 = U() + 0.5 * math.lengthsq(w.vel[bob]);
                s.Add(0.0, w.pos[bob].x, w.pos[bob].y, e0);
                float3 vPrev = w.vel[bob], xPrev = w.pos[bob];
                double uPrev = U();
                Run(w, seconds, 1, t =>
                {
                    float3 v = w.vel[bob];
                    double ke = 0.5 * math.lengthsq(0.5f * (v + vPrev));
                    s.Add(t - w.dt, xPrev.x, xPrev.y, uPrev + ke);
                    vPrev = v;
                    xPrev = w.pos[bob];
                    uPrev = U();
                    return true;
                });
                s.Write(ctx.FilePath(r, "pendulum.csv"));
                var cr = UpCrossings(s, 0, 1);
                double T = cr.Count >= 2 ? (cr[cr.Count - 1] - cr[0]) / (cr.Count - 1) : double.NaN;
                double Ta = 4.0 * math.sqrt(1.0 / g) * EllipticK(math.sin(th0 / 2f));
                r.Near("pendulum period at 60 deg amplitude (exact elliptic)", T, Ta, 0.005, "s");
                r.Info("small-angle period 2 pi sqrt(L/g)", 2.0 * math.PI * math.sqrt(1.0 / g), "s");
                double eSwing = g * (1.0 - math.cos(th0));
                double drift = 0.0;
                for (int i = 1; i < s.Count; i++)
                    drift = math.max(drift, math.abs(s[i][3] - e0) / eSwing);
                r.Max("pendulum energy error, 5 s, no damping", drift, 0.01);
            }

            // (b) hanging chain: 10 links of 0.1 m, 0.1 kg nodes, released from horizontal
            {
                var tb = new TestBody();
                int n = 10;
                var ids = new int[n + 1];
                ids[0] = tb.Node("c0", new float3(0f, 2f, 0f), 1f, NodeFlag.Fixed);
                for (int i = 1; i <= n; i++)
                {
                    ids[i] = tb.Node($"c{i}", new float3(0.1f * i, 2f, 0f), 0.1f, TestBody.Free);
                    tb.Beam(ids[i - 1], ids[i], "link");
                }
                var prm = TestBody.Params(g, TestBody.Mat("link", 2e4f, 0f));
                using var w = Build(prm, null, ww => ww.AddBody("chain", tb.Def("chain"), prm, float3.zero, quaternion.identity, float3.zero, false));
                double U()
                {
                    double e = 0.0;
                    for (int i = 1; i <= n; i++)
                        e += 0.1 * g * (w.pos[ids[i]].y - 2.0);
                    for (int j = 0; j < w.BeamCount; j++)
                        e += 0.5 * 2e4 * math.square(math.distance(w.pos[w.beams[j].a], w.pos[w.beams[j].b]) - w.rest[j]);
                    return e;
                }
                var vPrev = new float3[n + 1];
                for (int i = 1; i <= n; i++)
                    vPrev[i] = w.vel[ids[i]];
                double e0 = U();
                double uPrev = e0;
                float3 tipPrev = w.pos[ids[n]];
                var s = new Series("t", "energy", "tip_x", "tip_y", "tip_speed");
                s.Add(0.0, e0, tipPrev.x, tipPrev.y, 0.0);
                Run(w, seconds, 1, t =>
                {
                    double ke = 0.0;
                    for (int i = 1; i <= n; i++)
                        ke += 0.5 * 0.1 * math.lengthsq(0.5f * (w.vel[ids[i]] + vPrev[i]));
                    s.Add(t - w.dt, uPrev + ke, tipPrev.x, tipPrev.y, math.length(w.vel[ids[n]]));
                    for (int i = 1; i <= n; i++)
                        vPrev[i] = w.vel[ids[i]];
                    uPrev = U();
                    tipPrev = w.pos[ids[n]];
                    return true;
                });
                s.Write(ctx.FilePath(r, "chain.csv"));
                // reference: potential energy released when the chain hangs straight down (centre of mass drop 0.55 m)
                double eRef = 1.0 * g * 0.55;
                double drift = 0.0, maxTip = 0.0;
                for (int i = 1; i < s.Count; i++)
                {
                    drift = math.max(drift, math.abs(s[i][1] - e0) / eRef);
                    maxTip = math.max(maxTip, s[i][4]);
                }
                r.Max("chain energy error, 5 s, no damping (relative to the released 5.4 J)", drift, 0.03);
                r.Info("chain tip peak speed (whip)", maxTip, "m/s");
            }
            return r;
        }

        // ------------------------------------------------------------------ T3

        public static TestResult Cube(ValidationContext ctx)
        {
            var r = new TestResult();
            double Run3(string tag, bool braced)
            {
                var tb = new TestBody();
                var id = tb.Box("k", new float3(0f, 0.25f, 0f), new float3(0.25f), 16f, "edge", brace: false);
                if (braced)
                {
                    for (int a = 0; a < 8; a++)
                        for (int b = a + 1; b < 8; b++)
                            if (math.countbits(a ^ b) >= 2)
                                tb.Beam(id[a], id[b], "edge");
                }
                var prm = TestBody.Params(9.81f, TestBody.Mat("edge", 2e5f, 20f));
                using var w = Build(prm, Ground(), ww =>
                {
                    int bi = ww.AddBody(tag, tb.Def(tag), prm, float3.zero, quaternion.identity, float3.zero, false);
                    ww.bodies[bi].spawnClearance = 0.026f;
                });
                // perturbation: the top face moves sideways at 0.3 m/s
                for (int k = 0; k < 8; k++)
                    if ((k & 2) != 0)
                        w.vel[id[k]] = new float3(0.3f, 0f, 0f);
                double h0 = 0.0;
                for (int k = 0; k < 8; k++)
                    h0 += ((k & 2) != 0 ? 0.25 : -0.25) * w.pos[id[k]].y;
                var s = new Series("t", "top_height");
                double Height()
                {
                    double top = 0.0, bottom = 0.0;
                    for (int k = 0; k < 8; k++)
                        if ((k & 2) != 0) top += 0.25 * w.pos[id[k]].y; else bottom += 0.25 * w.pos[id[k]].y;
                    return top - bottom;
                }
                h0 = Height();
                s.Add(0.0, h0);
                Run(w, ctx.quick ? 1.5 : 3.0, 20, t =>
                {
                    s.Add(t, Height());
                    return true;
                });
                s.Write(ctx.FilePath(r, $"{tag}.csv"));
                return Height() / h0;
            }
            double unbraced = Run3("unbraced", false);
            double braced = Run3("braced", true);
            r.Max("cube without diagonals: final height / initial (collapses)", unbraced, 0.3);
            r.Min("cube with face and body diagonals: final height / initial (holds)", braced, 0.99);
            r.notes.Add("Edges alone are a mechanism (12 beams for 18 degrees of freedom less 6 rigid modes needs 12 + 6 = 18 beams); " +
                        "face diagonals (12) and body diagonals (4) make the cube rigid.");
            return r;
        }

        // ------------------------------------------------------------------ T4

        public static TestResult ForceDisplacement(ValidationContext ctx)
        {
            var r = new TestResult();
            // (a) displacement-controlled tensile cycle of one deformable, breakable beam: load to 6 cm, unload to
            //     zero force, reload to failure. Crosshead node of 1e8 kg moved at +-0.1 m/s.
            {
                const float k = 1e6f, yieldF = 2e4f, H = 2e5f, strength = 4e4f;
                var tb = new TestBody();
                int a = tb.Node("A", float3.zero, 1f, NodeFlag.Fixed);
                int b = tb.Node("B", new float3(0f, 0f, 1f), 1e8f, TestBody.Free);
                tb.Beam(a, b, "steel");
                var prm = TestBody.Params(0f, TestBody.Mat("steel", k, 0f, yieldF, strength, H));
                using var w = Build(prm, null, ww => ww.AddBody("tensile", tb.Def("tensile"), prm, float3.zero, quaternion.identity, float3.zero, false));
                float z0 = w.pos[b].z;
                var s = new Series("t", "displacement", "force", "rest_change", "phase");
                int phase = 0; // 0 load, 1 unload, 2 reload
                double unloadSet = double.NaN, breakForce = 0.0, breakDisp = double.NaN, peakForce = 0.0;
                w.vel[b] = new float3(0f, 0f, 0.1f);
                Run(w, 3.0, 2, t =>
                {
                    double d = w.pos[b].z - z0;
                    double f = w.broken[0] != 0 ? 0.0 : k * (math.distance(w.pos[a], w.pos[b]) - w.rest[0]);
                    s.Add(t, d, f, w.rest[0] - 1.0, phase);
                    peakForce = math.max(peakForce, f);
                    if (phase == 0 && d >= 0.06)
                    {
                        phase = 1;
                        w.vel[b] = new float3(0f, 0f, -0.1f);
                    }
                    else if (phase == 1 && f <= 0.0)
                    {
                        phase = 2;
                        unloadSet = d;
                        w.vel[b] = new float3(0f, 0f, 0.1f);
                    }
                    else if (phase == 2 && w.broken[0] != 0 && double.IsNaN(breakDisp))
                    {
                        breakDisp = d;
                        breakForce = peakForce;
                        return false;
                    }
                    return true;
                });
                s.Write(ctx.FilePath(r, "tensile.csv"));
                // analytic: yield at 2 cm (20 kN), hardening slope k H / (k + H); at 6 cm F = 26.67 kN and the rest
                // length has grown by 6 - 2.667 = 3.333 cm (permanent set); failure at F = 40 kN, d = 14 cm.
                double fAt6 = yieldF + k * H / (k + H) * (0.06 - yieldF / k);
                double set = 0.06 - fAt6 / k;
                double slopeY = double.NaN;
                for (int i = 1; i < s.Count; i++)
                    if (s[i][4] == 0 && s[i][1] > 0.03 && s[i][1] < 0.05)
                    {
                        int jx = i;
                        while (jx < s.Count && s[jx][1] < 0.05 && s[jx][4] == 0) jx++;
                        if (jx < s.Count)
                            slopeY = (s[jx][2] - s[i][2]) / (s[jx][1] - s[i][1]);
                        break;
                    }
                r.Near("elastic-plastic hardening slope k H / (k + H)", slopeY, k * H / (k + H), 0.01, "N/m");
                r.Near("permanent set after unloading from 6 cm", unloadSet, set, 0.01, "m");
                r.Near("failure force", breakForce, strength, 0.01, "N");
                r.Near("failure displacement", breakDisp, 0.14, 0.01, "m");
            }

            // (b) falling-mass crush of a braced square tube: 4 x 50 kg plate on a 0.2 x 0.2 x 0.4 m tube of
            //     deformable, breakable beams (hardening, no cap), fixed at the base; two impact speeds; energy ledger.
            void Crush(string tag, float v0, out double plastic, out int brokenBeams, out double ledger, out double crushFinal)
            {
                var tb = new TestBody();
                var ring = new int[3, 4];
                float[] ys = { 0f, 0.2f, 0.4f };
                for (int lv = 0; lv < 3; lv++)
                    for (int c = 0; c < 4; c++)
                    {
                        float x = (c == 0 || c == 3) ? -0.1f : 0.1f, z = c < 2 ? -0.1f : 0.1f;
                        float m = lv == 2 ? 50f : 5f;
                        ring[lv, c] = tb.Node($"r{lv}{c}", new float3(x, ys[lv], z), m, lv == 0 ? NodeFlag.Fixed : TestBody.Free);
                    }
                for (int lv = 0; lv < 3; lv++)
                {
                    for (int c = 0; c < 4; c++)
                        tb.Beam(ring[lv, c], ring[lv, (c + 1) % 4], "tube");
                    tb.Beam(ring[lv, 0], ring[lv, 2], "tube");
                    tb.Beam(ring[lv, 1], ring[lv, 3], "tube");
                }
                for (int lv = 0; lv < 2; lv++)
                    for (int c = 0; c < 4; c++)
                    {
                        int c1 = (c + 1) % 4;
                        tb.Beam(ring[lv, c], ring[lv + 1, c], "tube");
                        tb.Beam(ring[lv, c], ring[lv + 1, c1], "tube");
                        tb.Beam(ring[lv, c1], ring[lv + 1, c], "tube");
                    }
                var prm = TestBody.Params(9.81f, TestBody.Mat("tube", 2e6f, 60f, 1.2e4f, 4.5e4f, 1e6f));
                using var w = Build(prm, null, ww => ww.AddBody(tag, tb.Def(tag), prm, float3.zero, quaternion.identity, float3.zero, false));
                for (int c = 0; c < 4; c++)
                    w.vel[ring[2, c]] = new float3(0f, -v0, 0f);
                double ke0 = 0.0;
                for (int i = 0; i < w.NodeCount; i++)
                    ke0 += NodeKinetic(w, i);
                double topY0 = 0.4;
                double Top()
                {
                    double y = 0.0;
                    for (int c = 0; c < 4; c++)
                        y += 0.25 * w.pos[ring[2, c]].y;
                    return y;
                }
                var s = new Series("t", "crush", "force", "kinetic", "elastic", "plastic", "damping", "breaking", "gravity_work");
                double worst = 0.0;
                var vPrev = new float3[w.NodeCount];
                for (int i = 0; i < w.NodeCount; i++)
                    vPrev[i] = w.vel[i];
                var mPrev = w.Metrics(0);
                double crushPrev = topY0 - Top(), forcePrev = 0.0;
                Run(w, 0.25, 1, t =>
                {
                    // leapfrog: the previous positions' energies with the mean of the two half-step velocities
                    double ke = 0.0;
                    for (int i = 0; i < w.NodeCount; i++)
                    {
                        float im = w.invMass[i];
                        if (im > 0f)
                            ke += 0.5 / im * math.lengthsq((double3)(0.5f * (vPrev[i] + w.vel[i])));
                        vPrev[i] = w.vel[i];
                    }
                    double gravWork = -mPrev.gravity; // potential lost = work done by gravity
                    double balance = (ke + mPrev.elastic + mPrev.Dissipated) - (ke0 + gravWork);
                    worst = math.max(worst, math.abs(balance) / (ke0 + math.max(gravWork, 0.0)));
                    s.Add(t - w.dt, crushPrev, forcePrev, ke, mPrev.elastic, mPrev.plastic, mPrev.damping, mPrev.breaking, gravWork);
                    double f = 0.0;
                    for (int j = 0; j < w.BeamCount; j++)
                    {
                        var bs = w.beams[j];
                        if (w.broken[j] != 0)
                            continue;
                        if (w.invMass[bs.a] == 0f) f -= w.beamForce[j].y;  // force on the fixed node a
                        if (w.invMass[bs.b] == 0f) f += w.beamForce[j].y;  // node b gets -beamForce
                    }
                    forcePrev = f;
                    crushPrev = topY0 - Top();
                    mPrev = w.Metrics(0);
                    return true;
                });
                s.Write(ctx.FilePath(r, $"{tag}.csv"));
                var mm = w.Metrics(0);
                plastic = mm.plastic / ke0;
                brokenBeams = mm.brokenBeams;
                ledger = worst;
                crushFinal = topY0 - Top();
            }
            Crush("crush_5ms", 5f, out double plasticA, out int brokenA, out double ledgerA, out double crushA);
            r.Min("crush at 5 m/s: plastic work / impact energy", plasticA, 0.3);
            r.Max("crush at 5 m/s: broken beams", brokenA, 0);
            r.Min("crush at 5 m/s: permanent crush", crushA, 0.002, "m");
            r.Max("crush at 5 m/s: energy ledger error (kinetic + elastic + dissipated vs input)", ledgerA, 0.02);
            Crush("crush_15ms", 15f, out double plasticB, out int brokenB, out double ledgerB, out _);
            r.Min("crush at 15 m/s: broken beams", brokenB, 1);
            r.Info("crush at 15 m/s: plastic work / impact energy", plasticB);
            r.Max("crush at 15 m/s: energy ledger error", ledgerB, 0.03);
            r.notes.Add("Group-break energy is not counted in the ledger (no break groups here).");
            return r;
        }

        // ------------------------------------------------------------------ T5

        public static TestResult BoxDropSlope(ValidationContext ctx)
        {
            var r = new TestResult();
            var prm = TestBody.Params(9.81f, TestBody.Mat("rigid", 5e5f, 20f));
            var cm = prm.contactMaterials[0];
            TestBody MakeBox(out int[] id)
            {
                var tb = new TestBody();
                id = tb.Box("b", float3.zero, new float3(0.25f), 10f, "rigid");
                return tb;
            }

            // (a) drop from 1 m on flat ground
            {
                var tb = MakeBox(out var id);
                using var w = Build(prm, Ground(), ww =>
                {
                    int bi = ww.AddBody("box", tb.Def("box"), prm, new float3(0f, 2f, 0f), quaternion.identity, float3.zero, false);
                    ww.bodies[bi].spawnClearance = 1.0f;
                });
                double minY = double.MaxValue, impactKe = 0.0;
                var s = new Series("t", "bottom_y", "min_y", "kinetic");
                Run(w, ctx.quick ? 2.5 : 5.0, 4, t =>
                {
                    double bottom = 0.0, mn = double.MaxValue, ke = 0.0;
                    for (int k = 0; k < 8; k++)
                    {
                        if ((k & 2) == 0) bottom += 0.25 * w.pos[id[k]].y;
                        mn = math.min(mn, w.pos[id[k]].y);
                        ke += NodeKinetic(w, id[k]);
                    }
                    impactKe = math.max(impactKe, ke);
                    minY = math.min(minY, mn);
                    s.Add(t, bottom, mn, ke);
                    return true;
                });
                s.Write(ctx.FilePath(r, "drop.csv"));
                double restY = s[s.Count - 1][1];
                r.Min("drop: lowest node height over the run (no penetration of the ground)", minY, -1e-4, "m");
                r.NearAbs("drop: bottom nodes at rest in the contact zone (bias 0.025 m)", restY, cm.bias, 0.003, "m");
                r.Max("drop: kinetic energy at the end", s[s.Count - 1][3], 0.01, "J");
                r.Near("drop: peak kinetic energy (at contact) vs m g (1 m - bias)", impactKe, 10.0 * 9.81 * (1.0 - cm.bias), 0.02, "J");
            }

            // (b, c) slopes: 20 deg (static friction 0.6 > tan 20 = 0.36: holds), 40 deg (slides)
            void Slope(float deg, out double travel, out double accel, out double accelPred)
            {
                float th = math.radians(deg);
                float3 n = new float3(0f, math.cos(th), math.sin(th));
                float3 down = new float3(0f, -math.sin(th), math.cos(th));
                var statics = new StaticWorldBuilder();
                statics.AddPlane(n, 0f, "asphalt", "slope");
                var tb = MakeBox(out var id);
                using var w = Build(prm, statics, ww =>
                    ww.AddBody("box", tb.Def("box"), prm, n * (0.25f + cm.bias + 0.0005f), quaternion.RotateX(th), float3.zero, false));
                double Along()
                {
                    double d = 0.0;
                    for (int k = 0; k < 8; k++)
                        d += 0.125 * math.dot(w.pos[id[k]], down);
                    return d;
                }
                double SlipSpeed()
                {
                    double v = 0.0;
                    for (int k = 0; k < 8; k++)
                        v += 0.125 * math.dot(w.vel[id[k]], down);
                    return v;
                }
                double d0 = Along();
                var s = new Series("t", "travel", "speed");
                Run(w, ctx.quick ? 1.5 : 3.0, 4, t =>
                {
                    s.Add(t, Along() - d0, SlipSpeed());
                    return true;
                });
                s.Write(ctx.FilePath(r, $"slope_{deg:F0}.csv"));
                travel = s[s.Count - 1][1];
                // acceleration over the second half of the run (sliding at > 1 m/s: Stribeck term negligible)
                int i0 = s.Count / 2, i1 = s.Count - 1;
                accel = (s[i1][2] - s[i0][2]) / (s[i1][0] - s[i0][0]);
                double vMid = 0.5 * (s[i1][2] + s[i0][2]);
                double muV = cm.muSliding + (cm.muStatic - cm.muSliding) * math.exp(-math.pow(vMid / cm.stribeckVel, cm.stribeckExp));
                accelPred = 9.81 * (math.sin(th) - muV * math.cos(th));
            }
            Slope(20f, out double travel20, out _, out _);
            r.Max("slope 20 deg: travel in 3 s (static friction holds)", math.abs(travel20), 0.005, "m");
            Slope(40f, out double travel40, out double a40, out double a40p);
            r.Near("slope 40 deg: sliding acceleration vs g (sin - mu cos)", a40, a40p, 0.03, "m/s^2");
            r.Info("slope 40 deg: travel in 3 s", travel40, "m");
            return r;
        }
    }
}
