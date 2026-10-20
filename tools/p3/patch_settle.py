"""One-off patch (P3, D-037): settled spawn, T6 on a settled car, wind-up measured against the cabin floor."""
from pathlib import Path

SIM = Path("Unity/HellcatSandbox/Assets/Sim")


def patch(path, reps):
    s = path.read_text(encoding="utf-8")
    for old, new in reps:
        assert s.count(old) == 1, (path.name, old[:160])
        s = s.replace(old, new)
    path.write_text(s, encoding="utf-8")


patch(SIM / "Core" / "SoftBodyWorld.cs", [
    ('''        /// <summary>Per frame: static primitives near each body (AABB of the nodes + motion margin).</summary>''',
     '''        /// <summary>
        /// Settled spawn (D-037): relaxes one body to its static equilibrium on the statics by kinetic damping (all of the
        /// body's velocities are zeroed whenever its kinetic energy passes a peak), so a parked car starts at rest with
        /// its tires squashed, the springs at their static length and the brake, wind-up and friction preloads in place,
        /// instead of dropping from the unloaded model pose and bouncing. Rest lengths, angles and volumes keep their
        /// model values (the shape is not re-referenced); the clock keeps running (the spawn ramp completes). Inputs
        /// must be set before. Converged when the kinetic energy peak between two resets is below the tolerance.
        /// Returns the number of velocity resets (-1: not converged within maxSeconds).
        /// </summary>
        public int Settle(int bi, double maxSeconds = 4.0, double keTolerance = 1e-3)
        {
            var b = bodies[bi];
            const int chunk = 10;
            long steps = (long)math.round(maxSeconds / dt);
            double kePrev = 0.0, peak = 0.0;
            int resets = 0;
            bool converged = false;
            for (long s = 0; s < steps && !converged; s += chunk)
            {
                UpdateNearLists(chunk * dt + 0.05f);
                Step(chunk);
                double ke = 0.0;
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                    if (invMass[i] > 0f)
                        ke += 0.5 * math.lengthsq(vel[i]) / invMass[i];
                peak = math.max(peak, ke);
                if (ke < kePrev)
                {
                    converged = peak < keTolerance && resets > 0;
                    for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                        vel[i] = float3.zero;
                    resets++;
                    kePrev = 0.0;
                    peak = 0.0;
                }
                else
                {
                    kePrev = ke;
                }
            }
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                vel[i] = float3.zero;
            return converged ? resets : -1;
        }

        /// <summary>Per frame: static primitives near each body (AABB of the nodes + motion margin).</summary>'''),
])

vt = SIM / "Validation" / "VehicleTests.cs"
patch(vt, [
    # T6: the on-the-ground scenario starts from the settled spawn
    ('''                w.SetInput(b.vehicleIndex, Parked);
                var wheelNames = new string[b.wheelCount];''',
     '''                w.SetInput(b.vehicleIndex, Parked);
                if (tag == "spawn")
                {
                    // the car at rest on the ground (brief 10.6 acceptance): settled spawn (D-037), not a drop from the
                    // unloaded model pose
                    var swS = System.Diagnostics.Stopwatch.StartNew();
                    int resets = w.Settle(0);
                    r.Min("settled spawn (D-037) converged (kinetic energy peak < 1 mJ)", resets, 1, "resets");
                    r.Info("settled spawn: simulated / wall time", w.StepsTaken * (double)w.dt, "s", $"{swS.Elapsed.TotalSeconds:F2} s wall");
                }
                var wheelNames = new string[b.wheelCount];'''),
    # BodyPose with an optional cabin-floor filter
    ('''        static void BodyPose(SoftBodyWorld w, out double sag, out double rollDeg, out double pitchDeg, out double frontSag, out double rearSag)
        {
            var b = w.bodies[0];
            double sx = 0, sz = 0, sxx = 0, szz = 0, sxz = 0, sy = 0, sxy = 0, szy = 0;
            int n = 0;
            for (int i = 0; i < b.nodeCount; i++)
            {
                var nd = b.def.nodes[i];
                if (nd.part != "body")
                    continue;''',
     '''        static void BodyPose(SoftBodyWorld w, out double sag, out double rollDeg, out double pitchDeg, out double frontSag, out double rearSag,
            bool cabinFloor = false)
        {
            var b = w.bodies[0];
            double sx = 0, sz = 0, sxx = 0, szz = 0, sxz = 0, sy = 0, sxy = 0, szy = 0;
            int n = 0;
            for (int i = 0; i < b.nodeCount; i++)
            {
                var nd = b.def.nodes[i];
                if (nd.part != "body")
                    continue;
                if (cabinFloor && !(nd.name.StartsWith("sill") || nd.name.StartsWith("floor") || nd.name.StartsWith("tunnel")))
                    continue;'''),
    # the wind-up measure: relative to the cabin floor (the body pose fit over all body nodes includes the deforming ends)
    ('''            BodyPose(w, out _, out _, out double pitchDeg, out _, out _);
            double alpha = -math.tan(math.radians(pitchDeg));    // body rotation about +x (dy = c z -> alpha = -c)''',
     '''            BodyPose(w, out _, out _, out double pitchDeg, out _, out _, true);
            double alpha = -math.tan(math.radians(pitchDeg));    // cabin floor rotation about +x (dy = c z -> alpha = -c)'''),
])
print("patched")
