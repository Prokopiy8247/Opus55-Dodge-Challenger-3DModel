"""One-off (P3b): the driver robot keeps two cross-track integrals - one for curves (the understeer offset: it changes side
with the turn and fades on straights, time constant 1 s) and one for straights (a steady pull); each integrates only in its
own section. After the slalom the curve integral learned on the gates pushed the car off the straight run-out (0.69 m)."""
from pathlib import Path

P = Path("Unity/HellcatSandbox/Assets/Sim/Validation/DynamicsCommon.cs")
s = P.read_text(encoding="utf-8")


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:100]
    s = s.replace(old, new)


rep('''        double integ, cross;
        int turnSign;                          // side of the last curve (sign of the path curvature ahead), 0 before any''',
    '''        public double curveFade = 1.0;         // s: the curve integral fades on straights
        double integ, cross, crossCurve;       // speed integral; cross-track integrals on straights and in curves
        int turnSign;                          // side of the last curve (sign of the path curvature ahead), 0 before any''')
rep('''                // the integral is the understeer offset of the current curve: it changes side with the turn
                double kAhead = path.Curvature(arc + 0.5 * look);
                int sideNow = kAhead > 1.0 / 150.0 ? 1 : kAhead < -1.0 / 150.0 ? -1 : 0;
                if (sideNow != 0)
                {
                    if (turnSign != 0 && sideNow != turnSign)
                        cross = -cross;
                    turnSign = sideNow;
                }
                cross = math.clamp(cross + lateral * dt, -50.0, 50.0);
                delta -= kc * cross;''',
    '''                // in curves the integral is the understeer offset: it changes side with the turn and fades on straights;
                // on straights a separate integral takes a steady pull
                double kAhead = path.Curvature(arc + 0.5 * look);
                int sideNow = kAhead > 1.0 / 150.0 ? 1 : kAhead < -1.0 / 150.0 ? -1 : 0;
                if (sideNow != 0)
                {
                    if (turnSign != 0 && sideNow != turnSign)
                        crossCurve = -crossCurve;
                    turnSign = sideNow;
                    crossCurve = math.clamp(crossCurve + lateral * dt, -50.0, 50.0);
                }
                else
                {
                    crossCurve *= math.exp(-dt / math.max(curveFade, 1e-3));
                    cross = math.clamp(cross + lateral * dt, -50.0, 50.0);
                }
                delta -= kc * (cross + crossCurve);''')
P.write_text(s, encoding="utf-8")
print("patched")
