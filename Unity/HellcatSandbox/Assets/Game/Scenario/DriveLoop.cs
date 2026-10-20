using Hellcat.Sim.Validation;
using Unity.Mathematics;
using UnityEngine;

namespace Hellcat.Game.Scenario
{
    /// <summary>The drive-test loop: a stadium of two straights joined by two semicircles, run anticlockwise seen from
    /// above (left turns) from the start pose, and its speed profile (brake into each curve at a constant deceleration).</summary>
    public static class DriveLoop
    {
        /// <summary>Start (0, 0) heading +z in the start's position; left turns (towards -x) around (-R, L) and (-R, 0).</summary>
        public static PolyPath Path(Transform start, double straight = 300.0, double radius = 60.0)
        {
            var p = new PolyPath { closed = true };
            double2 o = new double2(start.position.x, start.position.z);
            for (double z = 0; z < straight; z += 0.5) p.Add(o + new double2(0, z));
            int n = (int)math.ceil(math.PI * radius / 0.5);
            for (int i = 0; i <= n; i++)
            {
                double a = math.PI * i / n;
                p.Add(o + new double2(-radius + radius * math.cos(a), straight + radius * math.sin(a)));
            }
            for (double z = straight; z > 0; z -= 0.5) p.Add(o + new double2(-2 * radius, z));
            for (int i = 0; i <= n; i++)
            {
                double a = math.PI + math.PI * i / n;
                p.Add(o + new double2(-radius + radius * math.cos(a), radius * math.sin(a)));
            }
            return p;
        }

        /// <summary>Straight speed on the straights, curve speed through the curves, braking at brakeDecel into each curve.</summary>
        public static double TargetSpeed(double arc, double straight = 300.0, double radius = 60.0, double straightKmh = 160.0,
            double curveKmh = 75.0, double brakeDecel = 5.5)
        {
            double curve = math.PI * radius, lap = 2 * straight + 2 * curve;
            double s = arc - lap * math.floor(arc / lap);
            double vS = straightKmh / 3.6, vC = curveKmh / 3.6;
            double toCurve;
            if (s < straight) toCurve = straight - s;
            else if (s < straight + curve) return vC;
            else if (s < 2 * straight + curve) toCurve = 2 * straight + curve - s;
            else return vC;
            return math.min(vS, math.sqrt(vC * vC + 2 * brakeDecel * math.max(toCurve - 15.0, 0.0)));
        }
    }
}
