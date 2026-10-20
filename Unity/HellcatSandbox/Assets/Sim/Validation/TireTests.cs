using System;
using System.Collections.Generic;
using Hellcat.Sim.Data;
using Hellcat.Sim.Vehicle;
using Unity.Mathematics;
using static Hellcat.Sim.Validation.ValidationSuite;

namespace Hellcat.Sim.Validation
{
    /// <summary>Validation test 9 of brief section 10: the pressurized tire on a single-wheel rig and on the car.</summary>
    public static class TireTests
    {
        public const double LoadRear = 4300.0, LoadFront = 5700.0;   // static corner loads (N, T6)

        /// <summary>Spindle height control for a target vertical load (flat-track tester in load control): the height
        /// moves with the filtered load error (bandwidth about 3 Hz on the measured vertical rate).</summary>
        sealed class LoadControl
        {
            public double target, filtered, rate = 290000.0, bandwidth = 3.0;
            public double Update(double fz, double dt)
            {
                filtered += (fz - filtered) * math.min(dt / 0.01, 1.0);
                return (filtered - target) / rate * 2.0 * math.PI * bandwidth;   // dy/dt (m/s): load too high -> up
            }
        }

        public static TestResult Tire(ValidationContext ctx)
        {
            var r = new TestResult();
            var prm = LoadHellcat(ctx).prm;

            // ---------------------------------------------------------------- (a) static load vs deflection
            double yContact;
            var loadX = new List<double>();
            var loadF = new List<double>();
            {
                using var rig = TireRig.Build(ctx, "RR", false);
                var w = rig.w;
                rig.Begin();
                for (int k = 0; k < 600; k++)
                    rig.Step();
                rig.Force(600 * w.dt, out _);
                yContact = rig.centre.y - (rig.LowestTread() - 0.0);
                var s = new Series("t", "deflection_mm", "fz_N", "volume_l", "gauge_kPa", "pv_over_gas", "loading");
                double gas0 = rig.Gas();
                const int chunk = 10;
                double chunkT = chunk * w.dt;
                void Sweep(double vy, double untilDefl, bool loading)
                {
                    rig.velocity = new double3(0, vy, 0);
                    while (loading ? (yContact - rig.centre.y) < untilDefl : (yContact - rig.centre.y) > untilDefl)
                    {
                        for (int k = 0; k < chunk; k++)
                            rig.Step();
                        double3 f = rig.Force(chunkT, out _);
                        double defl = yContact - rig.centre.y;
                        s.Add(rig.time, defl * 1000.0, f.y, rig.CavityVolume() * 1000.0, rig.GaugePressure() / 1000.0,
                            rig.AbsPressure() * rig.CavityVolume() / gas0, loading ? 1 : 0);
                        if (loading) { loadX.Add(defl); loadF.Add(f.y); }
                    }
                }
                Sweep(-0.02, 0.050, true);
                Sweep(0.02, -0.002, false);
                rig.velocity = double3.zero;
                s.Write(ctx.FilePath(r, "static_deflection.csv"));
                double kRear = LocalRate(loadX, loadF, LoadRear, out double dRear);
                double kFront = LocalRate(loadX, loadF, LoadFront, out double dFront);
                double secRear = LoadRear / dRear, secFront = LoadFront / dFront;
                r.Info("vertical tire rate at the rear corner load (4.3 kN): tangent", kRear / 1000.0, "kN/m",
                    $"deflection {dRear * 1000.0:F1} mm, secant {secRear / 1000.0:F0} kN/m");
                r.Info("vertical tire rate at the front corner load (5.7 kN): tangent", kFront / 1000.0, "kN/m",
                    $"deflection {dFront * 1000.0:F1} mm, secant {secFront / 1000.0:F0} kN/m (progressive: the patch widens)");
                // D-041 designed the suspension with the linear rate 292.9 kN/m (tools/skeleton/tire_rate.py, one contact
                // node): compare the secant of the real contact
                r.Near("vertical rate at the front load (secant) vs the linear rate of the suspension design (292.9 kN/m, D-041)", secFront, 292900.0, 0.2, "N/m");
                r.Min("vertical rate plausible for a 305/35 ZR20 at 241 kPa (tangent >= 220 kN/m)", kFront, 220000.0, "N/m");
                r.Max("vertical rate plausible (tangent <= 500 kN/m)", kFront, 500000.0, "N/m");
                double pvDev = 0;
                for (int i = 0; i < s.Count; i++)
                    pvDev = math.max(pvDev, math.abs(s[i][5] - 1.0));
                r.Max("sealed cavity: p V = const (isothermal ideal gas) over the load cycle", pvDev, 1e-4);
                double v0 = s[0][3], vMax = double.MaxValue, pMax = 0;
                for (int i = 0; i < s.Count; i++)
                    if (math.abs(s[i][2] - LoadFront) < 300.0) { vMax = math.min(vMax, s[i][3]); pMax = math.max(pMax, s[i][4]); }
                r.Info("cavity volume unloaded / at 5.7 kN", v0, "l", $"{vMax:F2} l, gauge pressure {s[0][4]:F1} -> {pMax:F1} kPa");
            }

            // ---------------------------------------------------------------- (b) inflation pressure vs volume and rate
            {
                var s = new Series("gauge_kPa", "volume_l", "tread_radius_mm", "rate_kN_per_m", "deflection_4300_mm");
                var ps = new[] { 0.0, 60.0, 150.0, 200.0, 241.0, 280.0 };
                double vPrev = 0, kPrev = 0, dFlat = double.NaN, dFull = double.NaN;
                bool volMono = true, rateMono = true;
                foreach (double pg in ps)
                {
                    using var rig = TireRig.Build(ctx, "RR", false);
                    var w = rig.w;
                    rig.Begin();
                    for (int k = 0; k < 200; k++)
                        rig.Step();
                    rig.SetGauge(pg * 1000.0);
                    for (int k = 0; k < 800; k++)
                        rig.Step();
                    double vol = rig.CavityVolume() * 1000.0, rad = rig.TreadRadius() * 1000.0;
                    double yc = rig.centre.y - rig.LowestTread();
                    var xs = new List<double>();
                    var fs = new List<double>();
                    rig.Force(1.0, out _);
                    rig.velocity = new double3(0, -0.025, 0);
                    double fLast = 0;
                    while (yc - rig.centre.y < 0.09 && fLast < LoadRear + 1500.0)
                    {
                        for (int k = 0; k < 10; k++)
                            rig.Step();
                        double3 f = rig.Force(10 * w.dt, out _);
                        xs.Add(yc - rig.centre.y);
                        fs.Add(f.y);
                        fLast = f.y;
                    }
                    double kk = LocalRate(xs, fs, LoadRear, out double dd);
                    s.Add(pg, vol, rad, kk / 1000.0, dd * 1000.0);
                    if (pg == 0.0) dFlat = dd;
                    if (pg == 241.0) dFull = dd;
                    // a 0.05 % tolerance: below the spawn inflation the cords keep the modelled shape (D-028)
                    if (vPrev > 0 && vol < vPrev * (1.0 - 5e-4)) volMono = false;
                    if (kPrev > 0 && kk < kPrev) rateMono = false;
                    vPrev = vol;
                    kPrev = kk;
                    r.Info($"inflated to {pg:F0} kPa: cavity volume / tread radius / rate at 4.3 kN", vol, "l",
                        $"radius {rad:F1} mm, rate {kk / 1000.0:F0} kN/m, deflection {dd * 1000.0:F1} mm");
                }
                s.Write(ctx.FilePath(r, "inflation.csv"));
                r.Flag("inflation: cavity volume does not shrink with pressure (0.05 % tolerance)", volMono, "monotonic");
                r.Flag("inflation: vertical rate rises with the inflation pressure", rateMono, "monotonic");
                r.Info("inflation 0 -> 280 kPa: volume change", (s[s.Count - 1][1] / s[0][1] - 1.0) * 100.0, "%",
                    "the cords are pre-tensioned for the modelled shape at every inflation (D-028): real tires grow 1-3 %");
                // a flat tire carries the load on its carcass alone (D-045): several times the inflated deflection, the
                // rim still clear of the ground (section height 107 mm)
                r.Min("flat tire (0 kPa): deflection at 4.3 kN over the inflated one", dFlat / dFull, 3.0);
                r.Max("flat tire: deflection at 4.3 kN below the section height (rim clear)", dFlat * 1000.0, 95.0, "mm");
            }

            // ---------------------------------------------------------------- (c) free rolling
            double reRef = 0.35;
            var reBySpeed = new List<(double v, double re)>();
            {
                var s = new Series("speed", "fz_N", "fx_N", "fy_N", "crr", "omega", "rolling_radius_mm", "tread_radius_mm", "fz_std_rel");
                foreach (double v in new[] { 5.0, 10.0, 20.0, 30.0, 45.0, 60.0, 75.0, 90.0 })
                {
                    if (ctx.quick && v > 30.0)
                        continue;
                    var res = RollFree(ctx, v, LoadRear, 0.0, 1.0, 0.5);
                    double re = v / res.omega;
                    reBySpeed.Add((v, re));
                    if (math.abs(v - 20.0) < 1e-6)
                        reRef = re;
                    s.Add(v, res.fz, res.fx, res.fy, -res.fx / res.fz, res.omega, re * 1000.0, res.treadR * 1000.0, res.fzStd / res.fz);
                    r.Info($"free rolling at {v * 3.6:F0} km/h: rolling resistance coefficient", -res.fx / res.fz, "",
                        $"rolling radius {re * 1000.0:F1} mm, tread radius {res.treadR * 1000.0:F1} mm, |Fy|/Fz {math.abs(res.fy) / res.fz:F4}, Fz ripple {res.fzStd / res.fz * 100.0:F1} %");
                }
                s.Write(ctx.FilePath(r, "free_rolling.csv"));
                double crr20 = 0, crrTop = 0, re20 = 0, reMax = 0, latMax = 0, rippleMax = 0;
                for (int i = 0; i < s.Count; i++)
                {
                    if (math.abs(s[i][0] - 20.0) < 1e-6) { crr20 = s[i][4]; re20 = s[i][6]; }
                    crrTop = s[i][4];
                    reMax = math.max(reMax, s[i][6]);
                    latMax = math.max(latMax, math.abs(s[i][3]) / s[i][1]);
                    rippleMax = math.max(rippleMax, s[i][8]);
                }
                // the mesh's own losses (carcass hysteresis, contact): the car adds the surface term in the wheel couple
                // minus the share the mesh covers (meshRollingResistance)
                double crrMax = 0;
                for (int i = 0; i < s.Count; i++)
                    crrMax = math.max(crrMax, s[i][4]);
                // the mesh's own losses are the tire's rolling resistance on asphalt (meshRollingResistance 0.012: the
                // wheel couple adds only the excess of softer surfaces); real UHP tires ~0.010-0.012, rising at speed
                r.Max("rolling resistance of the tire mesh at 72 km/h (C_rr; P Zero class ~0.010-0.012)", crr20, 0.02);
                r.Max("rolling resistance of the mesh at 324 km/h (C_rr; real tires rise to ~0.02-0.03)", crrTop, 0.04);
                r.Max("rolling resistance of the mesh: highest value 18-324 km/h (24-section resonances)", crrMax, 0.035);
                r.Near("effective rolling radius at 72 km/h vs 350.4 mm (731 rev/mile, Dodge S1-S5)", re20, 350.4, 0.02, "mm");
                r.Max("rolling radius growth up to 324 km/h (centrifugal; ring hoop tension D-044)", reMax - re20, 8.0, "mm");
                r.Max("free rolling straight: lateral force (|Fy| / Fz: conicity / ply steer of the mesh, mirrored left / right on the car)", latMax, 0.06);
                r.Max("free rolling: vertical load ripple up to 324 km/h (RMS / mean, 24 sections)", rippleMax, 0.15);
            }

            // ---------------------------------------------------------------- (d) slip-angle sweep
            {
                var s = new Series("fz_target", "alpha_deg", "fz_N", "fy_N", "fx_N", "mz_Nm", "mu_y");
                foreach (double load in new[] { LoadRear, LoadFront })
                {
                    var alphas = load == LoadRear
                        ? new[] { 0.0, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0, 20.0, -4.0, -8.0 }
                        : new[] { 0.0, 1.0, 2.0, 4.0, 6.0, 8.0, 12.0, 20.0 };
                    if (ctx.quick)
                        alphas = new[] { 0.0, 2.0, 6.0, 12.0 };
                    var res = SlipAngleSweep(ctx, 15.0, load, alphas);
                    foreach (var p in res)
                        s.Add(load, p.alpha, p.fz, p.fy, p.fx, p.mz, p.fy / p.fz);
                    // cornering stiffness from the small angles, peak and saturation
                    var xs = new List<double>();
                    var ys = new List<double>();
                    double peak = 0, peakA = 0, last = 0, lastA = 0, at1 = 0;
                    foreach (var p in res)
                    {
                        if (p.alpha >= 0.0 && p.alpha <= 2.0) { xs.Add(p.alpha); ys.Add(p.fy); }
                        if (p.alpha > 0 && p.fy / p.fz > peak) { peak = p.fy / p.fz; peakA = p.alpha; }
                        if (p.alpha > lastA) { lastA = p.alpha; last = p.fy / p.fz; }
                        if (math.abs(p.alpha - 1.0) < 1e-6) at1 = p.fy;
                    }
                    var fit = Dyn.Fit(xs, ys);
                    string tag = load == LoadRear ? "4.3 kN" : "5.7 kN";
                    // saturation: the angle where the force reaches 90 % of its maximum, and the slope at the largest angles
                    double a90 = double.NaN, slopeEnd = 0.0;
                    var pos = res.FindAll(p => p.alpha >= 0.0);
                    pos.Sort((x, y) => x.alpha.CompareTo(y.alpha));
                    for (int i = 1; i < pos.Count && double.IsNaN(a90); i++)
                        if (pos[i].fy >= 0.9 * peak * load)
                            a90 = pos[i - 1].alpha + (pos[i].alpha - pos[i - 1].alpha) * (0.9 * peak * load - pos[i - 1].fy) / math.max(pos[i].fy - pos[i - 1].fy, 1e-6);
                    if (pos.Count >= 2)
                        slopeEnd = (pos[pos.Count - 1].fy - pos[pos.Count - 2].fy) / math.max(pos[pos.Count - 1].alpha - pos[pos.Count - 2].alpha, 1e-6);
                    r.Info($"slip angle at {tag}: cornering stiffness (0-2 deg)", fit.slope, "N/deg", $"C_alpha / Fz {fit.slope / load:F3} 1/deg");
                    r.Info($"slip angle at {tag}: peak lateral force coefficient", peak, "", $"at {peakA:F0} deg; 90 % of it at {a90:F1} deg; at {lastA:F0} deg {last:F3}");
                    if (load == LoadRear)
                    {
                        r.Min("cornering force rises with slip angle: cornering stiffness / Fz (0-2 deg)", fit.slope / load, 0.05, "1/deg");
                        r.Max("cornering stiffness / Fz plausible (<= 0.6 per deg)", fit.slope / load, 0.6, "1/deg");
                        r.Min("cornering force saturates: peak lateral force coefficient", peak, 0.8);
                        r.Max("peak lateral force coefficient plausible (<= 1.4)", peak, 1.4);
                        r.Max("saturation: 90 % of the maximum lateral force reached by (deg)", a90, 12.0, "deg");
                        r.Max("saturation: slope at the largest angles / cornering stiffness", slopeEnd / math.max(fit.slope, 1e-6), 0.1);
                        r.Min("saturation: force at the largest angle still >= 75 % of the peak (no collapse)", last / math.max(peak, 1e-6), 0.75);
                        double sym = 0;
                        foreach (var p in res)
                            if (p.alpha < 0)
                                foreach (var q in res)
                                    if (math.abs(q.alpha + p.alpha) < 1e-6)
                                        sym = math.max(sym, math.abs(p.fy + q.fy) / math.max(math.abs(q.fy), 1.0));
                        r.Max("slip angle sweep symmetric (|Fy(-a) + Fy(a)| / |Fy(a)|)", sym, 0.15);
                    }
                }
                s.Write(ctx.FilePath(r, "slip_angle.csv"));
            }

            // ---------------------------------------------------------------- (e) longitudinal slip sweep
            {
                var s = new Series("kappa", "fz_N", "fx_N", "mu_x", "side");
                double peakD = 0, kD = 0, peakB = 0, kB = 0, locked = 0;
                var xs = new List<double>();
                var ys = new List<double>();
                foreach (int side in new[] { 1, -1 })
                {
                    var res = LongitudinalSweep(ctx, 15.0, LoadRear, reRef, side * 0.6, 3.0, side < 0);
                    foreach (var p in res)
                    {
                        s.Add(p.kappa, p.fz, p.fx, p.fx / p.fz, side);
                        double mu = p.fx / p.fz;
                        if (side > 0 && mu > peakD) { peakD = mu; kD = p.kappa; }
                        if (side < 0 && p.kappa > -0.99 && -mu > peakB) { peakB = -mu; kB = p.kappa; }
                        if (side < 0 && p.kappa <= -0.99) locked = -mu;
                        if (math.abs(p.kappa) <= 0.02) { xs.Add(p.kappa); ys.Add(p.fx); }
                    }
                }
                s.Write(ctx.FilePath(r, "longitudinal_slip.csv"));
                var fit = Dyn.Fit(xs, ys);
                r.Info("longitudinal slip stiffness (|slip ratio| <= 0.02)", fit.slope / 1000.0, "kN per unit slip", $"C_kappa / Fz {fit.slope / LoadRear:F1}");
                r.Info("drive: peak longitudinal force coefficient", peakD, "", $"at slip ratio {kD:F3}");
                r.Info("braking: peak longitudinal force coefficient", peakB, "", $"at slip ratio {kB:F3}; locked wheel {locked:F3}");
                r.Min("longitudinal force rises with slip: peak drive coefficient", peakD, 0.9);
                r.Max("peak drive coefficient plausible (<= 1.5)", peakD, 1.5);
                r.Min("braking: peak coefficient", peakB, 0.9);
                r.Max("peak slip ratio (braking) plausible (<= 0.3)", -kB, 0.3);
                r.Max("locked wheel slides below the peak (Stribeck): locked / peak", locked / math.max(peakB, 1e-6), 0.98);
                r.Min("locked wheel still grips (locked / peak)", locked / math.max(peakB, 1e-6), 0.65);
            }

            // ---------------------------------------------------------------- (f) puncture on the parked car
            Puncture(ctx, r);
            r.notes.Add("Rig: the rear wheel assembly (rim, tread, cavity, tire beams, damp group) extracted from the skeleton; spindle " +
                        "(axle and knuckle nodes) kinematic, held at the target vertical load by a height controller; forces from the " +
                        "contact impulses the solver applied (force plate). Slip-angle runs at 15 m/s with the rim free (free rolling); " +
                        "the longitudinal sweep drives the rim kinematically at omega = (1 + slip) v / R_e.");
            return r;
        }

        /// <summary>Diagnostic (not in the gate): rolling losses of the rig wheel by source at several speeds, and the
        /// contact state (nodes in contact, vertical speed of the nodes landing in the patch).</summary>
        /// <summary>Diagnostic X14: drive and braking slip sweeps of the rig tire at several speeds and loads (the peak
        /// coefficient and its slip ratio move with the slip speed through the Stribeck curve), for the assist targets.</summary>
        public static TestResult SlipSpeedSweeps(ValidationContext ctx)
        {
            var r = new TestResult();
            var s = new Series("speed", "load", "side", "kappa", "mu_x");
            foreach (double load in new[] { LoadRear, 5400.0 })
                foreach (double v in new[] { 5.0, 10.0, 20.0, 28.0 })
                    foreach (int side in new[] { 1, -1 })
                    {
                        var res = LongitudinalSweep(ctx, v, load, 0.351, side * 0.6, 3.0, false);
                        double peak = 0, kPeak = 0;
                        var at = new double[4];
                        var probes = new[] { 0.1, 0.15, 0.2, 0.3 };
                        foreach (var q in res)
                        {
                            double mu = side * q.fx / math.max(q.fz, 1.0);
                            s.Add(v, load, side, q.kappa, q.fx / math.max(q.fz, 1.0));
                            if (mu > peak) { peak = mu; kPeak = q.kappa; }
                            for (int k = 0; k < 4; k++)
                                if (math.abs(math.abs(q.kappa) - probes[k]) < 0.004)
                                    at[k] = mu;
                        }
                        r.Info($"{(side > 0 ? "drive" : "brake")} {v:F0} m/s, {load:F0} N: peak coefficient", peak, "",
                            $"at slip ratio {kPeak:F3} (slip speed {math.abs(kPeak) * v:F2} m/s); at 0.10 / 0.15 / 0.20 / 0.30: {at[0]:F2} / {at[1]:F2} / {at[2]:F2} / {at[3]:F2}");
                    }
            s.Write(ctx.FilePath(r, "slip_speed_sweeps.csv"));
            return r;
        }

        /// <summary>Diagnostic X15: friction-curve and contact-anchor variants of the tire compound: rig stability S,
        /// cornering at 20 m/s, drive and braking peaks at 3, 10 and 28 m/s, the locked wheel at 14 and 28 m/s.</summary>
        public static TestResult FrictionTuning(ValidationContext ctx)
        {
            var r = new TestResult();
            TireVariant F(string name, float muS, float muK, float vS, float ex, float alphaT = -1f, float zetaT = -1f, float ls = -1f,
                float muLat = -1f) => new TireVariant
            {
                name = name,
                prm = p =>
                {
                    foreach (var c in p.contactMaterials)
                        if (c.name == "tire")
                        {
                            c.muStatic = muS; c.muSliding = muK; c.stribeckVel = vS; c.stribeckExp = ex;
                            if (alphaT > 0f) c.alphaTangent = alphaT;
                            if (zetaT >= 0f) c.zetaTangent = zetaT;
                            if (ls >= 0f) c.loadSensitivity = ls;
                            if (muLat > 0f) { c.muLateral = muLat; c.lateralBeams = "tire_tread_lat"; }
                        }
                },
            };
            var variants = new List<TireVariant>
            {
                F("iso_mu1.40_0.85_v12_e1.2", 1.40f, 0.85f, 12f, 1.2f, 0.5f, 0.06f),
                F("lat0.90_mu1.55_0.75_v12_e1.4", 1.55f, 0.75f, 12f, 1.4f, 0.5f, 0.06f, -1f, 0.90f),
                F("lat0.90_mu1.55_0.85_v12_e1.2", 1.55f, 0.85f, 12f, 1.2f, 0.5f, 0.06f, -1f, 0.90f),
                F("lat0.88_mu1.60_0.75_v12_e1.4", 1.60f, 0.75f, 12f, 1.4f, 0.5f, 0.06f, -1f, 0.88f),
                F("lat0.92_mu1.50_0.75_v12_e1.4", 1.50f, 0.75f, 12f, 1.4f, 0.5f, 0.06f, -1f, 0.92f),
            };
            var s = new Series("variant", "S", "c_alpha", "mu_y", "alpha_peak", "drive3", "k_drive3", "brake3", "k_brake3", "drive10", "brake10",
                "drive28", "k_drive28", "brake28", "k_brake28", "locked14", "locked28", "c_kappa");
            for (int vi = 0; vi < variants.Count; vi++)
            {
                var v = variants[vi];
                double sv;
                using (var rig = TireRig.Build(ctx, "RR", false, v.prm, 0.002f, v.def))
                    sv = StabilityReport.Compute(rig.w).exactS;
                var al = SlipAngleSweepV(ctx, v, 20.0, LoadRear, new[] { 0.0, 1.0, 2.0, 4.0, 6.0, 8.0, 10.0, 14.0 });
                double ca = (al[2].fy - al[0].fy) / 2.0 / LoadRear, muY = 0, aPk = 0;
                foreach (var q in al)
                    if (q.fy / q.fz > muY) { muY = q.fy / q.fz; aPk = q.alpha; }
                double Peak(double speed, double kEnd, out double kPk, out double ck)
                {
                    var res = LongitudinalSweepV(ctx, v, speed, LoadRear, 0.351, kEnd, 1.5, false);
                    double pk = 0; kPk = 0;
                    var xs = new List<double>(); var ys = new List<double>();
                    foreach (var q in res)
                    {
                        double mu = math.sign(kEnd) * q.fx / math.max(q.fz, 1.0);
                        if (mu > pk) { pk = mu; kPk = q.kappa; }
                        if (math.abs(q.kappa) <= 0.02) { xs.Add(q.kappa); ys.Add(q.fx); }
                    }
                    ck = xs.Count > 3 ? Dyn.Fit(xs, ys).slope / LoadRear : double.NaN;
                    return pk;
                }
                double Locked(double speed)
                {
                    var res = LongitudinalSweepV(ctx, v, speed, LoadRear, 0.351, -1.0, 0.3, true);
                    double sum = 0; int n = 0;
                    for (int i = res.Count / 2; i < res.Count; i++)
                        if (res[i].kappa <= -0.999) { sum += -res[i].fx / math.max(res[i].fz, 1.0); n++; }
                    return n > 0 ? sum / n : double.NaN;
                }
                double d3 = Peak(3.0, 0.4, out double kd3, out double ck), b3 = Peak(3.0, -0.4, out double kb3, out _);
                double d10 = Peak(10.0, 0.4, out _, out _), b10 = Peak(10.0, -0.4, out _, out _);
                double d28 = Peak(28.0, 0.4, out double kd28, out _), b28 = Peak(28.0, -0.4, out double kb28, out _);
                double l14 = Locked(14.0), l28 = Locked(28.0);
                s.Add(vi, sv, ca, muY, aPk, d3, kd3, b3, kb3, d10, b10, d28, kd28, b28, kb28, l14, l28, ck);
                r.Info(v.name, sv, "S", $"C_a/Fz {ca:F3}/deg, mu_y {muY:F3} @ {aPk:F0} deg (20 m/s); drive / brake peaks 3 m/s {d3:F2} ({kd3:F2}) / {b3:F2} ({kb3:F2}), " +
                    $"10 m/s {d10:F2} / {b10:F2}, 28 m/s {d28:F2} ({kd28:F2}) / {b28:F2} ({kb28:F2}); locked 14 / 28 m/s {l14:F2} / {l28:F2}; C_k/Fz {ck:F1}");
            }
            s.Write(ctx.FilePath(r, "friction_tuning.csv"));
            return r;
        }

        public static TestResult RollingLosses(ValidationContext ctx)
        {
            var r = new TestResult();
            var s = new Series("variant", "speed", "crr", "p_total_W", "p_beams_W", "p_group_W", "p_contact_W", "p_fric_W", "contacts_mean", "landing_vn", "fz_ripple");
            void TireMat(SimParamsDef p, Action<BeamMaterialDef> f)
            {
                foreach (var m in p.materials)
                    if (m.name.StartsWith("tire_"))
                        f(m);
            }
            void TireContact(SimParamsDef p, Action<ContactMaterialDef> f)
            {
                foreach (var c in p.contactMaterials)
                    if (c.name == "tire")
                        f(c);
            }
            void HalfMass(VehicleDef d)
            {
                foreach (var nd in d.nodes)
                    if (nd.cmat == "tire" && nd.part.StartsWith("wheel_")) nd.m *= 0.5f;
            }
            Action<SimParamsDef> Belt(float bend) => p =>
            {
                var list = new List<HingeMaterialDef>(p.hingeMaterials) { new HingeMaterialDef { name = "tire_belt", bend = bend, damp = bend * 2e-4f } };
                p.hingeMaterials = list.ToArray();
            };
            void Mass(VehicleDef d, float f)
            {
                foreach (var nd in d.nodes)
                    if (nd.cmat == "tire" && nd.part.StartsWith("wheel_")) nd.m *= f;
            }
            void TireGroup(SimParamsDef p, Action<DampGroupMaterialDef> f)
            {
                foreach (var g in p.dampGroupMaterials)
                    if (g.name == "tire")
                        f(g);
            }
            _ = (Action<VehicleDef>)HalfMass;
            _ = (Func<float, Action<SimParamsDef>>)Belt;
            _ = (Action<VehicleDef, float>)Mass;
            void RimMat(SimParamsDef p, Action<BeamMaterialDef> f)
            {
                foreach (var m in p.materials)
                    if (m.name == "rim" || m.name == "rim_spoke")
                        f(m);
            }
            Action<SimParamsDef> LowDamp = p =>
            {
                TireMat(p, m => { m.damp *= 0.5f; if (m.dampRebound > 0) m.dampRebound *= 0.5f; });
                TireGroup(p, g => g.rate = 4f);
                TireContact(p, c => c.zetaNormal = 0.05f);
            };
            var variants = new List<(string name, Action<SimParamsDef> tweak, Action<VehicleDef> defTweak)>
            {
                ("low_damping", LowDamp, null),
                ("low_damping_rim_saturating", p => { LowDamp(p); RimMat(p, m => { m.velSplit = 0.3f; m.dampFast = 0f; m.dampReboundFast = 0f; }); }, null),
                ("low_damping_rim_damp_5", p => { LowDamp(p); RimMat(p, m => m.damp = 5f); }, null),
                ("low_damping_contact_zeta_0.02", p => { LowDamp(p); TireContact(p, c => c.zetaNormal = 0.02f); }, null),
            };
            var unused = new List<(string name, Action<SimParamsDef> tweak, Action<VehicleDef> defTweak)>
            {
                ("current", null, null),
                ("beam_damp_0.5", p => TireMat(p, m => { m.damp *= 0.5f; if (m.dampRebound > 0) m.dampRebound *= 0.5f; }), null),
                ("group_rate_4", p => TireGroup(p, g => g.rate = 4f), null),
                ("contact_zeta_0.05", p => TireContact(p, c => c.zetaNormal = 0.05f), null),
                ("anchor_alpha_0.15", p => TireContact(p, c => c.alphaTangent = 0.15f), null),
                ("all_low_damping", p =>
                {
                    TireMat(p, m => { m.damp *= 0.5f; if (m.dampRebound > 0) m.dampRebound *= 0.5f; });
                    TireGroup(p, g => g.rate = 4f);
                    TireContact(p, c => c.zetaNormal = 0.05f);
                }, null),
            };
            int vi = -1;
            foreach (var (vname, tweak, defTweak) in variants)
            {
            vi++;
            {
                using var rs = TireRig.Build(ctx, "RR", false, tweak, 0.002f, defTweak);
                var sr = StabilityReport.Compute(rs.w);
                // static secant rate at the rear load
                rs.Begin();
                for (int k = 0; k < 400; k++)
                    rs.Step();
                double yc = rs.centre.y - rs.LowestTread();
                rs.Force(1.0, out _);
                rs.velocity = new double3(0, -0.02, 0);
                double fzq = 0;
                while (fzq < LoadRear)
                {
                    for (int k = 0; k < 10; k++)
                        rs.Step();
                    fzq = rs.Force(10 * rs.w.dt, out _).y;
                }
                double defl = yc - rs.centre.y;
                r.Info($"{vname}: exact stability S of the rig wheel", sr.exactS, "", $"{rs.w.HingeCount} hinges; static deflection at 4.3 kN {defl * 1000:F1} mm (secant {LoadRear / defl / 1000:F0} kN/m)");
            }
            foreach (double v in new[] { 5.0, 20.0, 45.0, 90.0 })
            {
                using var rig = TireRig.Build(ctx, "RR", false, tweak, 0.002f, defTweak);
                var w = rig.w;
                w.trackEnergy = true;
                rig.Begin();
                var lc = new LoadControl { target = LoadRear };
                rig.velocity = new double3(0, -0.03, 0);
                while (true)
                {
                    for (int k = 0; k < 10; k++)
                        rig.Step();
                    if (rig.Force(10 * w.dt, out _).y >= LoadRear)
                        break;
                }
                lc.filtered = LoadRear;
                rig.SetRolling(new double3(0, 0, v), v / 0.351);
                var b = w.bodies[0];
                double E() => Sum(w, b, out _, out _, out _);
                const int chunk = 10;
                double chunkT = chunk * w.dt;
                double t = 0, e0 = 0, b0 = 0, g0 = 0, c0 = 0, fx = 0, fzS = 0, fz2 = 0, fric = 0, cont = 0, vnLand = 0;
                int n = 0, nLand = 0;
                var inContact = new bool[b.nodeCount];
                for (; t < 1.2; t += chunkT)
                {
                    if (t >= 0.6 && n == 0)
                    {
                        e0 = Sum(w, b, out b0, out g0, out c0);
                        rig.Force(1.0, out _);
                    }
                    for (int k = 0; k < chunk; k++)
                    {
                        rig.Step();
                        if (t >= 0.6)
                        {
                            for (int i = 0; i < b.nodeCount; i++)
                            {
                                int gi = b.nodeStart + i;
                                bool c = w.contactFn[gi] > 0f;
                                if (c && !inContact[i])
                                {
                                    vnLand += math.abs(w.vel[gi].y);
                                    nLand++;
                                }
                                inContact[i] = c;
                                if (c) cont += 1;
                                fric += w.frictionPower[gi] * w.dt;
                            }
                        }
                    }
                    double3 f = rig.Force(chunkT, out _);
                    rig.velocity = new double3(0, lc.Update(f.y, chunkT), v);
                    if (t >= 0.6)
                    {
                        fx += f.z;
                        fzS += f.y;
                        fz2 += f.y * f.y;
                        n++;
                    }
                }
                double e1 = Sum(w, b, out double b1, out double g1, out double c1);
                double dur = n * chunkT;
                double fzm = fzS / n;
                s.Add(vi, v, -fx / n / fzm, (e1 - e0) / dur, (b1 - b0) / dur, (g1 - g0) / dur, (c1 - c0) / dur, fric / dur,
                    cont / (n * chunk), nLand > 0 ? vnLand / nLand : 0, math.sqrt(math.max(fz2 / n - fzm * fzm, 0)) / fzm);
                r.Info($"{vname} {v * 3.6:F0} km/h: C_rr", -fx / n / fzm, "",
                    $"P {(e1 - e0) / dur:F0} W = beams {(b1 - b0) / dur:F0} + group {(g1 - g0) / dur:F0} + contact {(c1 - c0) / dur:F0} (static friction {fric / dur:F0}); " +
                    $"F v = {-fx / n * v:F0} W; {cont / (n * chunk):F1} nodes in contact, landing |vy| {(nLand > 0 ? vnLand / nLand : 0):F2} m/s, Fz ripple {math.sqrt(math.max(fz2 / n - fzm * fzm, 0)) / fzm * 100:F1} %");
            }
            }
            s.Write(ctx.FilePath(r, "rolling_losses.csv"));
            return r;
        }

        /// <summary>A tire variant for the tuning diagnostic: parameter and geometry tweaks.</summary>
        public sealed class TireVariant
        {
            public string name;
            public Action<SimParamsDef> prm;
            public Action<VehicleDef> def;
        }

        /// <summary>Moves a fraction of every tread node's mass to the rim nodes of the same wheel (the tire's bead and
        /// sidewall mass sits near the rim; the belt and tread of a 305/35 ZR20 weigh about 8-9 kg, the model's tread 18 kg).</summary>
        public static void ShiftTreadMass(VehicleDef d, float keep)
        {
            foreach (var w in d.wheels)
            {
                float moved = 0f;
                foreach (int t in w.tread)
                {
                    moved += d.nodes[t].m * (1f - keep);
                    d.nodes[t].m *= keep;
                }
                foreach (int r in w.rim)
                    d.nodes[r].m += moved / w.rim.Length;
            }
        }

        public static void ScaleMaterial(SimParamsDef p, string name, float spring)
        {
            foreach (var m in p.materials)
                if (m.name == name)
                {
                    m.spring *= spring;
                    if (m.springExp > 0f) m.springExp *= spring;
                }
        }

        public static void AddHingeMaterial(SimParamsDef p, string name, float bend)
        {
            var list = new List<HingeMaterialDef>(p.hingeMaterials);
            list.RemoveAll(h => h.name == name);
            list.Add(new HingeMaterialDef { name = name, bend = bend, damp = bend * 2e-4f });
            p.hingeMaterials = list.ToArray();
        }

        /// <summary>Diagnostic (not in the gate): the tuning metrics of a list of tire variants on the rig: stability S,
        /// static rate, cornering stiffness and peak, slip stiffness and peaks, rolling resistance at speed, contact
        /// quality and the lateral force at zero slip angle at high speed.</summary>
        public static TestResult TireTuning(ValidationContext ctx)
        {
            var r = new TestResult();
            var variants = TuningVariants();
            var s = new Series("variant", "S", "rate_secant_kNm", "c_alpha_per_deg", "mu_y_peak", "alpha_peak", "c_kappa", "mu_x_drive",
                "mu_x_brake", "crr_20", "crr_45", "crr_75", "crr_90", "contacts_90", "ripple_90", "fy0_90");
            for (int vi = 0; vi < variants.Count; vi++)
            {
                var v = variants[vi];
                using (var rig = TireRig.Build(ctx, "RR", false, v.prm, 0.002f, v.def))
                {
                    double sv = StabilityReport.Compute(rig.w).exactS;
                    rig.Begin();
                    for (int k = 0; k < 400; k++)
                        rig.Step();
                    double yc = rig.centre.y - rig.LowestTread();
                    rig.Force(1.0, out _);
                    rig.velocity = new double3(0, -0.02, 0);
                    double fzq = 0;
                    while (fzq < LoadRear)
                    {
                        for (int k = 0; k < 10; k++)
                            rig.Step();
                        fzq = rig.Force(10 * rig.w.dt, out _).y;
                    }
                    double rate = LoadRear / (yc - rig.centre.y) / 1000.0;
                    // static lateral stiffness: the loaded tire held by its patch, the spindle moved 4 mm sideways
                    rig.velocity = double3.zero;
                    for (int k = 0; k < 400; k++)
                        rig.Step();
                    rig.Force(1.0, out _);
                    rig.velocity = new double3(0.008, 0, 0);
                    for (int k = 0; k < 1000; k++)
                        rig.Step();
                    rig.velocity = double3.zero;
                    for (int k = 0; k < 200; k++)
                        rig.Step();
                    double fyLat = rig.Force(200 * rig.w.dt, out _).x;
                    double kLat = -fyLat / 0.004 / 1000.0;
                    // cornering
                    var al = SlipAngleSweepV(ctx, v, 15.0, LoadRear, new[] { 0.0, 1.0, 2.0, 4.0, 6.0, 8.0, 10.0, 14.0, 20.0 });
                    double ca = (al[2].fy - al[0].fy) / 2.0 / LoadRear;
                    double peak = 0, peakA = 0;
                    foreach (var p in al)
                        if (p.fy / p.fz > peak) { peak = p.fy / p.fz; peakA = p.alpha; }
                    // longitudinal
                    var ld = LongitudinalSweepV(ctx, v, 15.0, LoadRear, 0.351, 0.3, 1.5, false);
                    var lb = LongitudinalSweepV(ctx, v, 15.0, LoadRear, 0.351, -0.3, 1.5, false);
                    double muD = 0, muB = 0, ck = 0;
                    var xs = new List<double>();
                    var ys = new List<double>();
                    foreach (var p in ld) { muD = math.max(muD, p.fx / p.fz); if (p.kappa <= 0.02) { xs.Add(p.kappa); ys.Add(p.fx); } }
                    foreach (var p in lb) { muB = math.max(muB, -p.fx / p.fz); if (p.kappa >= -0.02) { xs.Add(p.kappa); ys.Add(p.fx); } }
                    ck = Dyn.Fit(xs, ys).slope / LoadRear;
                    var crr = new double[4];
                    var speeds = new[] { 20.0, 45.0, 75.0, 90.0 };
                    double c90 = 0, rip90 = 0, fy90 = 0, fy20 = 0;
                    for (int k = 0; k < speeds.Length; k++)
                    {
                        var res = RollFreeV(ctx, v, speeds[k], LoadRear, 0.8, 0.4, out double nc);
                        crr[k] = -res.fx / res.fz;
                        if (k == 0) fy20 = res.fy / res.fz;
                        if (k == 3) { c90 = nc; rip90 = res.fzStd / res.fz; fy90 = res.fy / res.fz; }
                    }
                    s.Add(vi, sv, rate, ca, peak, peakA, ck, muD, muB, crr[0], crr[1], crr[2], crr[3], c90, rip90, fy90);
                    r.Info($"{v.name}", sv, "S",
                        $"rate {rate:F0} kN/m, lateral {kLat:F0} kN/m; C_a/Fz {ca:F3}/deg, mu_y {peak:F3} @ {peakA:F0} deg; C_k/Fz {ck:F1}, mu_x drive {muD:F3} brake {muB:F3}; " +
                        $"C_rr 72/162/270/324 km/h {crr[0]:F4}/{crr[1]:F4}/{crr[2]:F4}/{crr[3]:F4}; Fy/Fz at 0 deg 72 km/h {fy20:F3}; at 324 km/h {c90:F1} nodes, ripple {rip90 * 100:F1} %, Fy/Fz {fy90:F3}");
                }
            }
            s.Write(ctx.FilePath(r, "tire_tuning.csv"));
            return r;
        }

        /// <summary>The variant list of the tuning diagnostic (edited while calibrating).</summary>
        /// <summary>Cross-section braces of the tire (bead to the opposite shoulder, both ways): lateral shear stiffness of
        /// the carcass (the inflated carcass of a real tire is laterally much stiffer than the radial sidewall cords).</summary>
        public static void AddCrossBraces(VehicleDef d, string mat)
        {
            var index = new Dictionary<string, int>();
            for (int i = 0; i < d.nodes.Length; i++)
                index[d.nodes[i].name] = i;
            var list = new List<BeamDef>(d.beams);
            foreach (var w in new[] { "FR", "FL", "RR", "RL" })
                for (int k = 0; index.ContainsKey($"{w}_trC{k}"); k++)
                {
                    list.Add(new BeamDef { a = index[$"{w}_rimI{k}"], b = index[$"{w}_trO{k}"], type = "NORMAL", mat = mat, bg = "", pre = 1f, hydro = "" });
                    list.Add(new BeamDef { a = index[$"{w}_rimO{k}"], b = index[$"{w}_trI{k}"], type = "NORMAL", mat = mat, bg = "", pre = 1f, hydro = "" });
                }
            d.beams = list.ToArray();
        }

        static void AddCrossMaterial(SimParamsDef p, float k)
        {
            var list = new List<BeamMaterialDef>(p.materials);
            list.RemoveAll(m => m.name == "tire_side_x");
            list.Add(new BeamMaterialDef { name = "tire_side_x", spring = k, damp = 12.5f, velSplit = 0.3f, dampFast = 0f, dampReboundFast = 0f, inflationShare = 0.95f });
            p.materials = list.ToArray();
        }

        static void Mu(SimParamsDef p, float muS, float muK)
        {
            foreach (var c in p.contactMaterials)
                if (c.name == "tire") { c.muStatic = muS; c.muSliding = muK; }
        }

        static List<TireVariant> TuningVariants()
        {
            var list = new List<TireVariant>
            {
                new TireVariant { name = "mirrored" },
                new TireVariant { name = "tread_diag_x1.5", prm = p => ScaleMaterial(p, "tire_tread_diag", 1.5f) },
                new TireVariant { name = "tread_diag_x2", prm = p => ScaleMaterial(p, "tire_tread_diag", 2f) },
                new TireVariant { name = "tread_diag_x2_mu_1.5_0.9_v3", prm = p =>
                {
                    ScaleMaterial(p, "tire_tread_diag", 2f);
                    foreach (var c in p.contactMaterials)
                        if (c.name == "tire") { c.muStatic = 1.5f; c.muSliding = 0.9f; c.stribeckVel = 3f; }
                } },
                new TireVariant { name = "tread_diag_x2_mu_1.6_0.9_v3", prm = p =>
                {
                    ScaleMaterial(p, "tire_tread_diag", 2f);
                    foreach (var c in p.contactMaterials)
                        if (c.name == "tire") { c.muStatic = 1.6f; c.muSliding = 0.9f; c.stribeckVel = 3f; }
                } },
            };
            return list;
        }

        static List<TireVariant> TuningVariantsOld()
        {
            var list = new List<TireVariant>
            {
                new TireVariant { name = "current" },
                new TireVariant { name = "belt400", prm = p => AddHingeMaterial(p, "tire_belt", 400f), def = d => AddBeltHinges(d) },
                new TireVariant
                {
                    name = "mass0.8_belt400_tread0.85", prm = p =>
                    {
                        AddHingeMaterial(p, "tire_belt", 400f);
                        foreach (var n in new[] { "tire_tread", "tire_tread_lat", "tire_tread_diag" }) ScaleMaterial(p, n, 0.85f);
                    },
                    def = d => { ShiftTreadMass(d, 0.8f); AddBeltHinges(d); },
                },
                new TireVariant
                {
                    name = "mass0.8_belt400_side_diag1.5", prm = p =>
                    {
                        AddHingeMaterial(p, "tire_belt", 400f);
                        foreach (var n in new[] { "tire_tread", "tire_tread_lat", "tire_tread_diag" }) ScaleMaterial(p, n, 0.85f);
                        ScaleMaterial(p, "tire_side_diag", 1.5f);
                    },
                    def = d => { ShiftTreadMass(d, 0.8f); AddBeltHinges(d); },
                },
            };
            return list;
        }

        static RollResult RollFreeV(ValidationContext ctx, TireVariant v, double speed, double load, double seconds, double window, out double contacts)
        {
            using var rig = TireRig.Build(ctx, "RR", false, v.prm, 0.002f, v.def);
            var w = rig.w;
            rig.Begin();
            var lc = new LoadControl { target = load };
            rig.velocity = new double3(0, -0.03, 0);
            while (true)
            {
                for (int k = 0; k < 10; k++)
                    rig.Step();
                if (rig.Force(10 * w.dt, out _).y >= load)
                    break;
            }
            lc.filtered = load;
            rig.SetRolling(new double3(0, 0, speed), speed / 0.351);
            var b = w.bodies[0];
            int chunk = 10;
            double chunkT = chunk * w.dt;
            var fz = new List<double>();
            double sx = 0, sy = 0, sc = 0;
            int n = 0;
            for (double t = 0; t < seconds; t += chunkT)
            {
                double cnt = 0;
                for (int k = 0; k < chunk; k++)
                {
                    rig.Step();
                    if (t >= seconds - window)
                        for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                            if (w.contactFn[i] > 0f) cnt += 1;
                }
                double3 f = rig.Force(chunkT, out _);
                rig.velocity = new double3(0, lc.Update(f.y, chunkT), speed);
                if (t >= seconds - window)
                {
                    sx += f.z; sy += f.x; fz.Add(f.y); sc += cnt / chunk; n++;
                }
            }
            double mean = 0;
            foreach (double q in fz) mean += q;
            mean /= math.max(fz.Count, 1);
            double var = 0;
            foreach (double q in fz) var += (q - mean) * (q - mean);
            contacts = sc / math.max(n, 1);
            return new RollResult { fz = mean, fx = sx / n, fy = sy / n, fzStd = math.sqrt(var / math.max(fz.Count, 1)) };
        }

        static List<AlphaPoint> SlipAngleSweepV(ValidationContext ctx, TireVariant v, double speed, double load, double[] alphas)
        {
            var list = new List<AlphaPoint>();
            using var rig = TireRig.Build(ctx, "RR", false, v.prm, 0.002f, v.def);
            var w = rig.w;
            rig.Begin();
            var lc = new LoadControl { target = load };
            rig.velocity = new double3(0, -0.03, 0);
            while (true)
            {
                for (int k = 0; k < 10; k++)
                    rig.Step();
                if (rig.Force(10 * w.dt, out _).y >= load)
                    break;
            }
            lc.filtered = load;
            rig.SetRolling(new double3(0, 0, speed), speed / 0.351);
            const int chunk = 10;
            double chunkT = chunk * w.dt;
            double prev = 0;
            for (double t = 0; t < 0.3; t += chunkT)
            {
                for (int k = 0; k < chunk; k++)
                    rig.Step();
                double3 f = rig.Force(chunkT, out _);
                rig.velocity = new double3(0, lc.Update(f.y, chunkT), speed);
            }
            foreach (double a in alphas)
            {
                double fy = 0, fz = 0;
                int n = 0;
                for (double t = 0; t < 0.4; t += chunkT)
                {
                    rig.yaw = math.radians(math.lerp(prev, a, math.saturate(t / 0.05)));
                    for (int k = 0; k < chunk; k++)
                        rig.Step();
                    double3 f = rig.Force(chunkT, out _);
                    rig.velocity = new double3(0, lc.Update(f.y, chunkT), speed);
                    if (t >= 0.25)
                    {
                        double3 ax = new double3(math.cos(rig.yaw), 0, -math.sin(rig.yaw));
                        fy += math.dot(f, ax); fz += f.y; n++;
                    }
                }
                list.Add(new AlphaPoint { alpha = a, fy = fy / n, fz = fz / n });
                prev = a;
            }
            return list;
        }

        static List<KappaPoint> LongitudinalSweepV(ValidationContext ctx, TireVariant v, double speed, double load, double re, double kappaEnd,
            double seconds, bool holdLocked)
        {
            var list = new List<KappaPoint>();
            using var rig = TireRig.Build(ctx, "RR", true, v.prm, 0.002f, v.def);
            var w = rig.w;
            rig.Begin();
            var lc = new LoadControl { target = load };
            rig.velocity = new double3(0, -0.03, 0);
            while (true)
            {
                for (int k = 0; k < 10; k++)
                    rig.Step();
                if (rig.Force(10 * w.dt, out _).y >= load)
                    break;
            }
            lc.filtered = load;
            rig.SetRolling(new double3(0, 0, speed), speed / re);
            const int chunk = 10;
            double chunkT = chunk * w.dt;
            for (double t = 0; t < 0.3 + seconds + (holdLocked ? 0.6 : 0.0); t += chunkT)
            {
                double kappa = t < 0.3 ? 0 : t < 0.3 + seconds ? kappaEnd * (t - 0.3) / seconds : -1.0;
                rig.spinRate = (1.0 + kappa) * speed / re;
                for (int k = 0; k < chunk; k++)
                    rig.Step();
                double3 f = rig.Force(chunkT, out _);
                rig.velocity = new double3(0, lc.Update(f.y, chunkT), speed);
                if (t >= 0.2)
                    list.Add(new KappaPoint { kappa = kappa, fz = f.y, fx = f.z });
            }
            var sm = new List<KappaPoint>();
            for (int i = 0; i < list.Count; i++)
            {
                int a = math.max(0, i - 5), b = math.min(list.Count - 1, i + 5);
                double fz = 0, fx = 0;
                for (int k = a; k <= b; k++) { fz += list[k].fz; fx += list[k].fx; }
                int n = b - a + 1;
                sm.Add(new KappaPoint { kappa = list[i].kappa, fz = fz / n, fx = fx / n });
            }
            return sm;
        }

        /// <summary>Circumferential bending of the tread band (belt): a dihedral hinge across every lateral edge of the two
        /// tread strips (trI-trC, trC-trO) of every wheel, material "tire_belt" (D-032 hinge kernel).</summary>
        public static void AddBeltHinges(VehicleDef d)
        {
            var index = new Dictionary<string, int>();
            for (int i = 0; i < d.nodes.Length; i++)
                index[d.nodes[i].name] = i;
            var list = new List<HingeDef>(d.hinges ?? Array.Empty<HingeDef>());
            foreach (var w in new[] { "FR", "FL", "RR", "RL" })
            {
                if (!index.ContainsKey($"{w}_trC0"))
                    continue;
                int n = 0;
                while (index.ContainsKey($"{w}_trC{n}"))
                    n++;
                foreach (var (ra, rb) in new[] { ("trI", "trC"), ("trC", "trO") })
                    for (int k = 0; k < n; k++)
                    {
                        int km = (k + n - 1) % n, kp = (k + 1) % n;
                        list.Add(new HingeDef
                        {
                            n = new[] { index[$"{w}_{ra}{km}"], index[$"{w}_{ra}{k}"], index[$"{w}_{rb}{k}"], index[$"{w}_{rb}{kp}"] },
                            mat = "tire_belt",
                        });
                    }
            }
            d.hinges = list.ToArray();
        }

        /// <summary>Energy dissipated so far in a body: beam dampers, damp groups and contact (static contact is passive:
        /// minus its work is dissipation).</summary>
        static double Sum(SoftBodyWorld w, SoftBodyWorld.Body b, out double beams, out double groups, out double contact)
        {
            beams = 0;
            for (int j = b.beamStart; j < b.beamStart + b.beamCount; j++)
                beams += w.dampEnergy[j];
            groups = 0;
            for (int g = b.dampGroupStart; g < b.dampGroupStart + b.dampGroupCount; g++)
                groups += w.dampGroupEnergy[g];
            contact = 0;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                contact -= w.contactWork[i];
            for (int h = b.hingeStart; h < b.hingeStart + b.hingeCount; h++)
                beams += w.hingeDampEnergy[h];   // belt hinges counted with the beams
            return beams + groups + contact;
        }

        /// <summary>Local slope dF/dx of a loading curve around a force, and the deflection there.</summary>
        static double LocalRate(List<double> x, List<double> f, double at, out double defl)
        {
            var xs = new List<double>();
            var fs = new List<double>();
            defl = double.NaN;
            for (int i = 0; i < x.Count; i++)
            {
                if (math.abs(f[i] - at) < 600.0) { xs.Add(x[i]); fs.Add(f[i]); }
                if (double.IsNaN(defl) && f[i] >= at && i > 0)
                    defl = x[i - 1] + (x[i] - x[i - 1]) * (at - f[i - 1]) / math.max(f[i] - f[i - 1], 1e-9);
            }
            var fit = Dyn.Fit(xs, fs);
            return fit.slope;
        }

        struct RollResult { public double fz, fx, fy, omega, treadR, fzStd; }

        /// <summary>Free-rolling rig run at a speed and load (slip angle in degrees), averaged over the last window.</summary>
        static RollResult RollFree(ValidationContext ctx, double v, double load, double alphaDeg, double seconds, double window)
        {
            using var rig = TireRig.Build(ctx, "RR", false);
            var w = rig.w;
            rig.yaw = math.radians(alphaDeg);
            rig.Begin();
            // press to the load at rest, then roll
            var lc = new LoadControl { target = load };
            rig.velocity = new double3(0, -0.03, 0);
            while (true)
            {
                for (int k = 0; k < 10; k++)
                    rig.Step();
                double3 f = rig.Force(10 * w.dt, out _);
                if (f.y >= load)
                    break;
            }
            lc.filtered = load;
            rig.SetRolling(new double3(0, 0, v), v / 0.35);
            int chunk = 10;
            double chunkT = chunk * w.dt;
            var fz = new List<double>();
            double sx = 0, sy = 0, sw = 0, sr = 0;
            int n = 0;
            for (double t = 0; t < seconds; t += chunkT)
            {
                for (int k = 0; k < chunk; k++)
                    rig.Step();
                double3 f = rig.Force(chunkT, out _);
                double vy = lc.Update(f.y, chunkT);
                rig.velocity = new double3(0, vy, v);
                if (t >= seconds - window)
                {
                    double3 hd = new double3(math.sin(rig.yaw), 0, math.cos(rig.yaw));
                    double3 ax = new double3(math.cos(rig.yaw), 0, -math.sin(rig.yaw));
                    sx += math.dot(f, hd);
                    sy += math.dot(f, ax);
                    fz.Add(f.y);
                    sw += rig.Omega();
                    sr += rig.TreadRadius();
                    n++;
                }
            }
            double mean = 0;
            foreach (double q in fz) mean += q;
            mean /= math.max(fz.Count, 1);
            double var = 0;
            foreach (double q in fz) var += (q - mean) * (q - mean);
            return new RollResult { fz = mean, fx = sx / n, fy = sy / n, omega = sw / n, treadR = sr / n, fzStd = math.sqrt(var / math.max(fz.Count, 1)) };
        }

        struct AlphaPoint { public double alpha, fz, fy, fx, mz; }

        /// <summary>Slip-angle steps at a speed with the spindle in load control, rim free (rolling).</summary>
        static List<AlphaPoint> SlipAngleSweep(ValidationContext ctx, double v, double load, double[] alphas)
        {
            var list = new List<AlphaPoint>();
            using var rig = TireRig.Build(ctx, "RR", false);
            var w = rig.w;
            rig.Begin();
            var lc = new LoadControl { target = load };
            rig.velocity = new double3(0, -0.03, 0);
            while (true)
            {
                for (int k = 0; k < 10; k++)
                    rig.Step();
                if (rig.Force(10 * w.dt, out _).y >= load)
                    break;
            }
            lc.filtered = load;
            rig.SetRolling(new double3(0, 0, v), v / 0.35);
            const int chunk = 10;
            double chunkT = chunk * w.dt;
            void Run(double seconds, double yawFrom, double yawTo, double ramp, Action<double3, double> sample)
            {
                for (double t = 0; t < seconds; t += chunkT)
                {
                    rig.yaw = math.radians(math.lerp(yawFrom, yawTo, math.saturate(t / ramp)));
                    for (int k = 0; k < chunk; k++)
                        rig.Step();
                    double3 f = rig.Force(chunkT, out double mz);
                    rig.velocity = new double3(0, lc.Update(f.y, chunkT), v);
                    sample?.Invoke(f, mz);
                }
            }
            Run(0.4, 0, 0, 0.01, null);
            double prev = 0;
            foreach (double a in alphas)
            {
                double fy = 0, fx = 0, fz = 0, mz = 0;
                int n = 0;
                double hold = 0.5, t0 = 0;
                Run(hold, prev, a, 0.06, (f, m) =>
                {
                    t0 += chunkT;
                    if (t0 < hold - 0.2)
                        return;
                    double3 hd = new double3(math.sin(rig.yaw), 0, math.cos(rig.yaw));
                    double3 ax = new double3(math.cos(rig.yaw), 0, -math.sin(rig.yaw));
                    fy += math.dot(f, ax); fx += math.dot(f, hd); fz += f.y; mz += m; n++;
                });
                list.Add(new AlphaPoint { alpha = a, fy = fy / n, fx = fx / n, fz = fz / n, mz = mz / n });
                prev = a;
            }
            return list;
        }

        struct KappaPoint { public double kappa, fz, fx; }

        /// <summary>Longitudinal slip ramp with the rim driven kinematically (omega = (1 + kappa) v / R_e); with
        /// holdLocked a final half second with the rim stopped (kappa = -1).</summary>
        static List<KappaPoint> LongitudinalSweep(ValidationContext ctx, double v, double load, double re, double kappaEnd, double seconds, bool holdLocked)
        {
            var list = new List<KappaPoint>();
            using var rig = TireRig.Build(ctx, "RR", true);
            var w = rig.w;
            rig.Begin();
            var lc = new LoadControl { target = load };
            rig.velocity = new double3(0, -0.03, 0);
            while (true)
            {
                for (int k = 0; k < 10; k++)
                    rig.Step();
                if (rig.Force(10 * w.dt, out _).y >= load)
                    break;
            }
            lc.filtered = load;
            rig.SetRolling(new double3(0, 0, v), v / re);
            const int chunk = 10;
            double chunkT = chunk * w.dt;
            double kappa = 0;
            for (double t = 0; t < 0.4 + seconds + (holdLocked ? 0.6 : 0.0); t += chunkT)
            {
                if (t < 0.4)
                    kappa = 0;
                else if (t < 0.4 + seconds)
                    kappa = kappaEnd * (t - 0.4) / seconds;
                else
                    kappa = -1.0;
                rig.spinRate = (1.0 + kappa) * v / re;
                for (int k = 0; k < chunk; k++)
                    rig.Step();
                double3 f = rig.Force(chunkT, out _);
                rig.velocity = new double3(0, lc.Update(f.y, chunkT), v);
                if (t >= 0.3 && (t < 0.4 + seconds || t > 0.4 + seconds + 0.3))
                    list.Add(new KappaPoint { kappa = kappa, fz = f.y, fx = f.z });
            }
            // smooth over 10 samples (50 ms) for the sweep curve
            var sm = new List<KappaPoint>();
            for (int i = 0; i < list.Count; i++)
            {
                int a = math.max(0, i - 5), b = math.min(list.Count - 1, i + 5);
                double fz = 0, fx = 0;
                for (int k = a; k <= b; k++) { fz += list[k].fz; fx += list[k].fx; }
                int n = b - a + 1;
                sm.Add(new KappaPoint { kappa = list[i].kappa, fz = fz / n, fx = fx / n });
            }
            return sm;
        }

        /// <summary>Puncture of the right rear tire on the parked car: pressure bleed, corner drop, stability.</summary>
        static void Puncture(ValidationContext ctx, TestResult r)
        {
            using var w = Dyn.Car(ctx, Ground(), float3.zero, 0f);
            var b = w.bodies[0];
            var probe = new CarProbe(w, 0);
            int wr = probe.WheelIndex("RR");
            int pg = -1;
            for (int g = 0; g < b.pressureCount; g++)
                if (b.def.pressureGroups[g].wheel == "RR")
                    pg = b.pressureStart + g;
            const float rate = 2.0f;
            var f0 = probe.Frame();
            double hub0 = probe.HubY(wr);
            var s = new Series("t", "gauge_kPa", "hub_drop_mm", "roll_deg", "max_node_speed", "rim_lowest_mm");
            double tPunct = 0.5, t63 = double.NaN, p0 = double.NaN, vmax = 0;
            var pk = w.pressureGroups[pg];
            Dyn.Drive(w, 5.0, 10, (t, f) =>
            {
                if (t >= tPunct && w.pressureState[pg].puncture == 0f)
                    w.Puncture(pg, rate);
                return new DriverInput { brake = 1f, handbrake = 1f, gear = 0 };
            }, (t, f) =>
            {
                double gauge = (w.pressureState[pg].pAbs - pk.pAtm) / 1000.0;
                if (double.IsNaN(p0) && t >= tPunct) p0 = gauge;
                if (!double.IsNaN(p0) && double.IsNaN(t63) && gauge <= p0 * math.exp(-1.0)) t63 = t - tPunct;
                double vm = 0;
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                    vm = math.max(vm, math.length(w.vel[i]));
                if (t > 4.0) vmax = math.max(vmax, vm);
                double rimLow = double.MaxValue;
                foreach (int n in b.def.wheels[wr].rim)
                    rimLow = math.min(rimLow, w.pos[b.nodeStart + n].y);
                s.Add(t, gauge, (hub0 - probe.HubY(wr)) * 1000.0, f.rollDeg - f0.rollDeg, vm, rimLow * 1000.0);
                return true;
            }, probe);
            s.Write(ctx.FilePath(r, "puncture_parked.csv"));
            var last = s[s.Count - 1];
            r.NearAbs("puncture (leak 2 /s): pressure decay time constant vs 1 / rate", t63, 1.0 / rate, 0.1, "s");
            r.Max("puncture: gauge pressure after 4.5 s", last[1], 10.0, "kPa");
            r.Info("puncture: right rear hub drop / rim lowest point / body roll", last[2], "mm", $"rim {last[5]:F1} mm above the ground, roll {last[3]:F2} deg");
            r.Min("puncture: the flat corner drops (deflated tire changes ride height)", last[2], 25.0, "mm");
            r.Max("puncture: the corner drop stays in a flat tire's range (sidewall 107 mm)", last[2], 110.0, "mm");
            r.Max("puncture: car at rest after deflating (max node speed after 4 s)", vmax, 0.05, "m/s");
        }
    }
}
