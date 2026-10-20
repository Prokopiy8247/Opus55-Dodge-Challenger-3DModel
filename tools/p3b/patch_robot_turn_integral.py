"""One-off (P3b): the driver robot's cross-track integral is an understeer correction, so it changes side with the turn: when
the path curvature ahead (at half the look-ahead, |kappa| > 1/150 m) changes sign, the integral flips sign. On a figure
eight the integral learned on one circle pushed the car outward at every crossover (1.3-1.5 m transients)."""
from pathlib import Path

P = Path("Unity/HellcatSandbox/Assets/Sim/Validation/DynamicsCommon.cs")
s = P.read_text(encoding="utf-8")


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:100]
    s = s.replace(old, new)


rep('''        double integ, cross;
        double hPrev = double.NaN, tPrev, deltaF;''',
    '''        double integ, cross;
        int turnSign;                          // side of the last curve (sign of the path curvature ahead), 0 before any
        double hPrev = double.NaN, tPrev, deltaF;''')
rep('''                double kc = kCross * math.min(1.0, math.pow(15.0 / math.max(v, 1.0), crossSpeedExp));
                cross = math.clamp(cross + lateral * dt, -50.0, 50.0);''',
    '''                double kc = kCross * math.min(1.0, math.pow(15.0 / math.max(v, 1.0), crossSpeedExp));
                // the integral is the understeer offset of the current curve: it changes side with the turn
                double kAhead = path.Curvature(arc + 0.5 * look);
                int sideNow = kAhead > 1.0 / 150.0 ? 1 : kAhead < -1.0 / 150.0 ? -1 : 0;
                if (sideNow != 0)
                {
                    if (turnSign != 0 && sideNow != turnSign)
                        cross = -cross;
                    turnSign = sideNow;
                }
                cross = math.clamp(cross + lateral * dt, -50.0, 50.0);''')
P.write_text(s, encoding="utf-8")
print("patched")
