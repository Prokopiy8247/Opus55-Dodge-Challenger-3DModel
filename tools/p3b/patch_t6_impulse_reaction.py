"""One-off (P3b): T6 measures the ground reaction from the contact impulses (penalty + hard projection), total and per
wheel, instead of the penalty forces alone (D-048 left part of a cambered tire's static load to the projection)."""
from pathlib import Path

P = Path("Unity/HellcatSandbox/Assets/Sim/Validation/VehicleTests.cs")
s = P.read_text(encoding="utf-8")


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:100]
    s = s.replace(old, new)


rep("""                double firstContact = -1.0;
                long steps0 = w.StepsTaken;
                double stepSeconds = Run(w, seconds, 20, t =>
                {
                    var m = w.Metrics(0);
                    BodyPose(w, out double sag, out double roll, out double pitch, out double fs, out double rs);
                    double cn = 0.0, minY = double.MaxValue;
                    for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                    {
                        cn += w.contactFn[i];
                        minY = math.min(minY, w.pos[i].y);
                    }""",
    """                double firstContact = -1.0;
                long steps0 = w.StepsTaken;
                // ground reaction from the contact impulses (penalty and hard projection, the force plate of T7 / T9):
                // the penalty forces alone miss what the projection carries
                var probe6 = new CarProbe(w, 0);
                w.ClearContactImp();
                double tLast = w.StepsTaken * (double)w.dt;
                var wheelFz = new double[b.wheelCount];
                double stepSeconds = Run(w, seconds, 20, t =>
                {
                    var m = w.Metrics(0);
                    BodyPose(w, out double sag, out double roll, out double pitch, out double fs, out double rs);
                    double cn = 0.0, minY = double.MaxValue, span = math.max(t - tLast, 1e-9);
                    for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                    {
                        cn += w.contactImp[i].y / span;
                        minY = math.min(minY, w.pos[i].y);
                    }
                    for (int k = 0; k < b.wheelCount; k++)
                        wheelFz[k] = probe6.TreadImpulse(k).y / span;
                    w.ClearContactImp();
                    tLast = t;""")
rep("""                    for (int k = 0; k < b.wheelCount; k++) row.Add(w.wheelState[b.wheelStart + k].load);""",
    """                    for (int k = 0; k < b.wheelCount; k++) row.Add(wheelFz[k]);""")
P.write_text(s, encoding="utf-8")
print("patched")
