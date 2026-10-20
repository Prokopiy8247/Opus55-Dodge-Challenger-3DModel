"""One-off (P3b): DamageWatch in the curb, bump, step and ramp runs of T10 / T14 (which beams break or yield, when, and
which intact beams come close to their limit)."""
from pathlib import Path

P = Path("Unity/HellcatSandbox/Assets/Sim/Validation/HandlingTests.cs")
s = P.read_text(encoding="utf-8")


def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (s.count(old), old[:120])
    s = s.replace(old, new)


# T10 (c) step
rep("""                var s = new Series("t", "travel_FR_mm", "travel_RR_mm", "pitch_deg", "com_y_mm", "fz_FR", "fz_RR");
                double y0 = f0.com.y;
                w.ClearContactImp();
                Dyn.Drive(w, 4.0, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
                {
                    double span = 10 * w.dt;""",
    """                var s = new Series("t", "travel_FR_mm", "travel_RR_mm", "pitch_deg", "com_y_mm", "fz_FR", "fz_RR");
                double y0 = f0.com.y;
                var dmg = new DamageWatch(w, b);
                w.ClearContactImp();
                Dyn.Drive(w, 4.0, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
                {
                    dmg.Sample(t);
                    double span = 10 * w.dt;""")
rep("""                r.Max("step 50 mm at 10 km/h: broken beams", m.brokenBeams, 0);""",
    """                r.Max("step 50 mm at 10 km/h: broken beams", m.brokenBeams, 0);
                dmg.Report(r, "step 50 mm");""")
# T10 (d) curb
rep("""                var s = new Series("t", "travel_FR_mm", "travel_RR_mm", "roll_deg", "heading_deg", "fz_FR");
                w.ClearContactImp();
                Dyn.Drive(w, 4.0, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
                {""",
    """                var s = new Series("t", "travel_FR_mm", "travel_RR_mm", "roll_deg", "heading_deg", "fz_FR");
                var dmg = new DamageWatch(w, b);
                w.ClearContactImp();
                Dyn.Drive(w, 4.0, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
                {
                    dmg.Sample(t);""")
rep("""                r.Max("curb strike at 20 km/h: plastically deformed beams", m.plasticBeams, 0);""",
    """                r.Max("curb strike at 20 km/h: plastically deformed beams", m.plasticBeams, 0);
                dmg.Report(r, "curb strike 20 km/h");""")
# T14 (d) bumps
rep("""                var s = new Series("t", "speed_kmh", "path_error", "pitch_deg", "roll_deg", "heading_deg", "acc_y_g");
                double tPrev = 0; double3 velPrev = f0.vel;
                Dyn.Drive(w, 30.0 / (kmh * Kmh) + 1.0, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
                {""",
    """                var s = new Series("t", "speed_kmh", "path_error", "pitch_deg", "roll_deg", "heading_deg", "acc_y_g");
                double tPrev = 0; double3 velPrev = f0.vel;
                var dmg = new DamageWatch(w, b);
                Dyn.Drive(w, 30.0 / (kmh * Kmh) + 1.0, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
                {
                    dmg.Sample(t);""")
rep("""                r.Info($"{what} at {kmh:F0} km/h: peak pitch / roll", MaxAbs(s, 3, 0.5), "deg", $"roll {MaxAbs(s, 4, 0.5):F2} deg, peak vertical acceleration of the body {MaxAbs(s, 6, 0.5):F2} g, {m.plasticBeams} plastic beams");""",
    """                r.Info($"{what} at {kmh:F0} km/h: peak pitch / roll", MaxAbs(s, 3, 0.5), "deg", $"roll {MaxAbs(s, 4, 0.5):F2} deg, peak vertical acceleration of the body {MaxAbs(s, 6, 0.5):F2} g, {m.plasticBeams} plastic beams");
                dmg.Report(r, $"{tag}");""")
# T14 (e) ramp
rep("""                double tAir = 0, tLand = double.NaN, maxH = 0;
                Dyn.Drive(w, 4.5, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
                {""",
    """                double tAir = 0, tLand = double.NaN, maxH = 0;
                var dmg = new DamageWatch(w, b);
                Dyn.Drive(w, 4.5, 10, (t, f) => robot.Control(t, 10 * w.dt, f), (t, f) =>
                {
                    dmg.Sample(t);""")
rep("""                r.Info("ramp jump: plastically deformed beams after the landing", m.plasticBeams, "");""",
    """                r.Info("ramp jump: plastically deformed beams after the landing", m.plasticBeams, "", $"take-off at {tAir:F2} s of flight, landing at {tLand:F2} s");
                dmg.Report(r, "ramp jump");""")
P.write_text(s, encoding="utf-8")
print("patched")
