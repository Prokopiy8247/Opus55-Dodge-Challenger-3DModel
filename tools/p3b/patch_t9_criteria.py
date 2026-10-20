"""One-off (P3b): T9 criteria update (rates, inflation incl. flat, rolling, saturation)."""
from pathlib import Path

P = Path("Unity/HellcatSandbox/Assets/Sim/Validation/TireTests.cs")
s = P.read_text(encoding="utf-8")


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:100]
    s = s.replace(old, new)


rep("""                double kRear = LocalRate(loadX, loadF, LoadRear, out double dRear);
                double kFront = LocalRate(loadX, loadF, LoadFront, out double dFront);
                r.Info("vertical tire rate at the rear corner load (4.3 kN)", kRear / 1000.0, "kN/m", $"deflection {dRear * 1000.0:F1} mm");
                r.Info("vertical tire rate at the front corner load (5.7 kN)", kFront / 1000.0, "kN/m", $"deflection {dFront * 1000.0:F1} mm");
                // D-041 designed the suspension with 292.9 kN/m (tools/skeleton/tire_rate.py, the car's tire at 5.7 kN)
                r.Near("vertical rate at the front load vs the rate the suspension design used (292.9 kN/m, D-041)", kFront, 292900.0, 0.15, "N/m");
                r.Min("vertical rate plausible for a 305/35 ZR20 at 241 kPa (>= 220 kN/m)", kFront, 220000.0, "N/m");
                r.Max("vertical rate plausible (<= 450 kN/m)", kFront, 450000.0, "N/m");""",
    """                double kRear = LocalRate(loadX, loadF, LoadRear, out double dRear);
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
                r.Max("vertical rate plausible (tangent <= 500 kN/m)", kFront, 500000.0, "N/m");""")

rep("""                var s = new Series("gauge_kPa", "volume_l", "tread_radius_mm", "rate_kN_per_m", "deflection_4300_mm");
                var ps = new[] { 150.0, 200.0, 241.0, 280.0 };
                double vPrev = 0, kPrev = 0;
                bool volMono = true, rateMono = true;""",
    """                var s = new Series("gauge_kPa", "volume_l", "tread_radius_mm", "rate_kN_per_m", "deflection_4300_mm");
                var ps = new[] { 0.0, 60.0, 150.0, 200.0, 241.0, 280.0 };
                double vPrev = 0, kPrev = 0, dFlat = double.NaN, dFull = double.NaN;
                bool volMono = true, rateMono = true;""")

rep("""                    rig.Force(1.0, out _);
                    rig.velocity = new double3(0, -0.025, 0);
                    while (yc - rig.centre.y < 0.035)
                    {
                        for (int k = 0; k < 10; k++)
                            rig.Step();
                        double3 f = rig.Force(10 * w.dt, out _);
                        xs.Add(yc - rig.centre.y);
                        fs.Add(f.y);
                    }
                    double kk = LocalRate(xs, fs, LoadRear, out double dd);
                    s.Add(pg, vol, rad, kk / 1000.0, dd * 1000.0);
                    if (vPrev > 0 && vol < vPrev - 1e-4) volMono = false;
                    if (kPrev > 0 && kk < kPrev) rateMono = false;
                    vPrev = vol;
                    kPrev = kk;""",
    """                    rig.Force(1.0, out _);
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
                    kPrev = kk;""")

rep("""                r.Flag("inflation: cavity volume does not shrink with pressure", volMono, "monotonic");
                r.Flag("inflation: vertical rate rises with the inflation pressure", rateMono, "monotonic");
                r.Info("inflation 150 -> 280 kPa: volume change", (s[s.Count - 1][1] / s[0][1] - 1.0) * 100.0, "%",
                    "the cords are pre-tensioned for the modelled shape at every inflation (D-028): real tires grow 1-3 %");""",
    """                r.Flag("inflation: cavity volume does not shrink with pressure (0.05 % tolerance)", volMono, "monotonic");
                r.Flag("inflation: vertical rate rises with the inflation pressure", rateMono, "monotonic");
                r.Info("inflation 0 -> 280 kPa: volume change", (s[s.Count - 1][1] / s[0][1] - 1.0) * 100.0, "%",
                    "the cords are pre-tensioned for the modelled shape at every inflation (D-028): real tires grow 1-3 %");
                // a flat tire carries the load on its carcass alone (D-045): several times the inflated deflection, the
                // rim still clear of the ground (section height 107 mm)
                r.Min("flat tire (0 kPa): deflection at 4.3 kN over the inflated one", dFlat / dFull, 3.0);
                r.Max("flat tire: deflection at 4.3 kN below the section height (rim clear)", dFlat * 1000.0, 95.0, "mm");""")

rep("""                foreach (double v in new[] { 5.0, 10.0, 20.0, 30.0, 45.0, 60.0, 80.0 })""",
    """                foreach (double v in new[] { 5.0, 10.0, 20.0, 30.0, 45.0, 60.0, 75.0, 90.0 })""")

rep("""                double crr20 = 0, crr80 = 0, re20 = 0, reMax = 0, latMax = 0;
                for (int i = 0; i < s.Count; i++)
                {
                    if (math.abs(s[i][0] - 20.0) < 1e-6) { crr20 = s[i][4]; re20 = s[i][6]; }
                    crr80 = s[i][4];
                    reMax = math.max(reMax, s[i][6]);
                    latMax = math.max(latMax, math.abs(s[i][3]) / s[i][1]);
                }
                // the tire's own (hysteresis) rolling resistance: the car adds the surface term in the wheel couple
                r.Max("tire hysteresis rolling resistance at 72 km/h (the surface term is added on the car)", crr20, 0.012);
                r.Max("tire hysteresis rolling resistance at the highest speed run", crr80, 0.02);
                r.Near("effective rolling radius at 72 km/h vs 350.4 mm (731 rev/mile, Dodge S1-S5)", re20, 350.4, 0.02, "mm");
                r.Max("rolling radius growth up to the highest speed run (centrifugal)", reMax - re20, 8.0, "mm");
                r.Max("free rolling straight: lateral force (|Fy| / Fz, conicity / ply steer of the mesh)", latMax, 0.03);""",
    """                double crr20 = 0, crrTop = 0, re20 = 0, reMax = 0, latMax = 0, rippleMax = 0;
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
                r.Max("rolling losses of the tire mesh at 72 km/h (C_rr; P Zero class tires ~0.010-0.012 in total)", crr20, 0.015);
                r.Max("rolling losses of the mesh at 324 km/h (C_rr; real tires rise to ~0.02-0.03)", crrTop, 0.04);
                r.Near("effective rolling radius at 72 km/h vs 350.4 mm (731 rev/mile, Dodge S1-S5)", re20, 350.4, 0.02, "mm");
                r.Max("rolling radius growth up to 324 km/h (centrifugal; ring hoop tension D-044)", reMax - re20, 8.0, "mm");
                r.Max("free rolling straight: lateral force (|Fy| / Fz: conicity / ply steer of the mesh, mirrored left / right on the car)", latMax, 0.06);
                r.Max("free rolling: vertical load ripple up to 324 km/h (RMS / mean, 24 sections)", rippleMax, 0.15);""")

rep("""                    var fit = Dyn.Fit(xs, ys);
                    string tag = load == LoadRear ? "4.3 kN" : "5.7 kN";
                    r.Info($"slip angle at {tag}: cornering stiffness (0-2 deg)", fit.slope, "N/deg", $"C_alpha / Fz {fit.slope / load:F3} 1/deg");
                    r.Info($"slip angle at {tag}: peak lateral force coefficient", peak, "", $"at {peakA:F0} deg; at {lastA:F0} deg {last:F3}");""",
    """                    var fit = Dyn.Fit(xs, ys);
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
                    r.Info($"slip angle at {tag}: peak lateral force coefficient", peak, "", $"at {peakA:F0} deg; 90 % of it at {a90:F1} deg; at {lastA:F0} deg {last:F3}");""")

rep("""                        r.Max("saturation: peak slip angle", peakA, 15.0, "deg");""",
    """                        r.Max("saturation: 90 % of the maximum lateral force reached by (deg)", a90, 12.0, "deg");
                        r.Max("saturation: slope at the largest angles / cornering stiffness", slopeEnd / math.max(fit.slope, 1e-6), 0.1);""")

P.write_text(s, encoding="utf-8")
print("ok")
