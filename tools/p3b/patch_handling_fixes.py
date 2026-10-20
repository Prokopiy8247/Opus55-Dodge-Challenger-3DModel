"""One-off (P3b): HandlingTests geometry fixes (step 50 mm, 120 mm curb under the right wheels, ramp faces outward),
travel from positions for every wheel, PolyPath.Add public, T10 / T11 / T14 registered."""
from pathlib import Path

V = Path("Unity/HellcatSandbox/Assets/Sim/Validation")


def patch(path, pairs):
    p = V / path
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:100])
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")


patch("DynamicsCommon.cs", [("""        void Add(double2 p)""", """        public void Add(double2 p)""")])

patch("HandlingTests.cs", [
    ('''statics.AddBox(new float3(0f, 0.025f - 1.0f, 3.0f + 25.0f), quaternion.identity, new float3(5f, 1.0f, 25f), "asphalt", "step");''',
     '''statics.AddBox(new float3(0f, 0.05f - 1.0f, 3.0f + 25.0f), quaternion.identity, new float3(5f, 1.0f, 25f), "asphalt", "step");'''),
    ('''                statics.AddBox(new float3(1.0f, 0.06f - 0.5f, 8.0f), quaternion.RotateY(math.radians(45f)), new float3(0.15f, 0.5f, 3.0f), "concrete", "curb");''',
     '''                // 6 m long along (sin 45, 0, cos 45) from x 0.1 to 4.3 m: only the right wheels (x 0.83) meet it, at z ~6.6 m
                statics.AddBox(new float3(2.2f, 0.12f - 0.5f, 8.0f), quaternion.RotateY(math.radians(45f)), new float3(0.15f, 0.5f, 3.0f), "concrete", "curb");'''),
    ('''                    statics.AddBox(new float3(1.0f, 0.06f - 0.5f, 12.0f), quaternion.RotateY(math.radians(45f)), new float3(0.15f, 0.5f, 3.0f), "concrete", "curb");''',
     '''                    statics.AddBox(new float3(2.2f, 0.12f - 0.5f, 12.0f), quaternion.RotateY(math.radians(45f)), new float3(0.15f, 0.5f, 3.0f), "concrete", "curb");'''),
    ('''                var faces = new List<int[]> { new[] { 0, 2, 3, 1 }, new[] { 4, 5, 3, 2 }, new[] { 0, 1, 5, 4 }, new[] { 0, 4, 2 }, new[] { 1, 3, 5 } };
                statics.AddConvexMesh(verts, faces, "asphalt", "ramp");''',
     '''                var faces = new List<int[]> { new[] { 0, 1, 3, 2 }, new[] { 2, 3, 5, 4 }, new[] { 0, 4, 5, 1 }, new[] { 0, 2, 4 }, new[] { 1, 5, 3 } };
                statics.AddConvexMesh(verts, OrientOutward(verts, faces), "asphalt", "ramp");'''),
    ('''        static bool IsSprung(VehicleDef d, int local) => !d.nodes[local].part.StartsWith("wheel_");''',
     '''        static bool IsSprung(VehicleDef d, int local) => !d.nodes[local].part.StartsWith("wheel_");

        /// <summary>Faces of a convex mesh wound so their normals point away from the centroid (AddConvexMesh takes the
        /// normal from the first three vertices).</summary>
        static List<int[]> OrientOutward(IReadOnlyList<float3> v, List<int[]> faces)
        {
            float3 c = float3.zero;
            foreach (var p in v) c += p;
            c /= v.Count;
            var outF = new List<int[]>();
            foreach (var f in faces)
            {
                float3 n = math.cross(v[f[1]] - v[f[0]], v[f[2]] - v[f[0]]);
                if (math.dot(n, v[f[0]] - c) < 0f)
                {
                    var g = (int[])f.Clone();
                    Array.Reverse(g);
                    outF.Add(g);
                }
                else outF.Add(f);
            }
            return outF;
        }

        /// <summary>Bump travel of a wheel (m, wheel up against the body): its hub along the cabin's up axis over the centroid
        /// of the body nodes that carry its suspension, against the model.</summary>
        static double Travel(SoftBodyWorld w, SoftBodyWorld.Body b, int wheel, in CarFrame f)
        {
            var wd = b.def.wheels[wheel];
            double3 hub = 0.5 * ((double3)w.pos[b.nodeStart + wd.axleInner] + (double3)w.pos[b.nodeStart + wd.axleOuter]);
            double3 c = double3.zero;
            foreach (int n in wd.windupBody) c += (double3)w.pos[b.nodeStart + n];
            c /= wd.windupBody.Length;
            double hubM = 0.5 * (b.def.nodes[wd.axleInner].p[1] + b.def.nodes[wd.axleOuter].p[1]);
            double cM = 0;
            foreach (int n in wd.windupBody) cM += b.def.nodes[n].p[1];
            cM /= wd.windupBody.Length;
            return math.dot(hub - c, f.up) - (hubM - cM);
        }'''),
    ('''                    var ws = w.wheelState[b.wheelStart + k];
                    s.Add(k, fz[k], target, ws.travel * 1000.0, probe.CamberDeg(k, f), probe.RoadWheelDeg(k, f));
                    r.Info($"static {wd.name}: corner load (contact impulses) vs centre of mass", fz[k], "N",
                        $"target {target:F0} N; travel {ws.travel * 1000:F1} mm from the model ride height; camber {probe.CamberDeg(k, f):F2} deg, toe {probe.RoadWheelDeg(k, f):F2} deg (right positive)");''',
     '''                    double tr = Travel(w, b, k, f);
                    s.Add(k, fz[k], target, tr * 1000.0, probe.CamberDeg(k, f), probe.RoadWheelDeg(k, f));
                    r.Info($"static {wd.name}: corner load (contact impulses) vs centre of mass", fz[k], "N",
                        $"target {target:F0} N; travel {tr * 1000:F1} mm from the model ride height; camber {probe.CamberDeg(k, f):F2} deg, toe {probe.RoadWheelDeg(k, f):F2} deg (right positive)");'''),
    ('''                double tf = 0, tr = 0;
                for (int k = 0; k < b.wheelCount; k++)
                    if (b.def.wheels[k].steered != 0) tf = math.max(tf, math.abs(w.wheelState[b.wheelStart + k].travel));
                    else tr = math.max(tr, math.abs(w.wheelState[b.wheelStart + k].travel));
                r.Max("static: ride height within 15 mm of the model at every corner (rear, alignment element travel)", tr * 1000.0, 15.0, "mm");''',
     '''                double tMax = 0;
                for (int k = 0; k < b.wheelCount; k++)
                    tMax = math.max(tMax, math.abs(Travel(w, b, k, f)));
                r.Max("static: ride height within 15 mm of the model at every corner", tMax * 1000.0, 15.0, "mm");'''),
    ('''                    s.Add(t, w.wheelState[b.wheelStart + iFR].travel * 1000.0, w.wheelState[b.wheelStart + iRR].travel * 1000.0, f.pitchDeg,
                        (f.com.y - y0) * 1000.0, probe.TreadImpulse(iFR).y / span, probe.TreadImpulse(iRR).y / span);''',
     '''                    s.Add(t, Travel(w, b, iFR, f) * 1000.0, Travel(w, b, iRR, f) * 1000.0, f.pitchDeg,
                        (f.com.y - y0) * 1000.0, probe.TreadImpulse(iFR).y / span, probe.TreadImpulse(iRR).y / span);'''),
    ('''                    s.Add(t, w.wheelState[b.wheelStart + iFR].travel * 1000.0, w.wheelState[b.wheelStart + iRR].travel * 1000.0, f.rollDeg,
                        Dyn.WrapDeg(math.degrees(f.heading - f0.heading)), probe.TreadImpulse(iFR).y / (10 * w.dt));''',
     '''                    s.Add(t, Travel(w, b, iFR, f) * 1000.0, Travel(w, b, iRR, f) * 1000.0, f.rollDeg,
                        Dyn.WrapDeg(math.degrees(f.heading - f0.heading)), probe.TreadImpulse(iFR).y / (10 * w.dt));'''),
])

patch("ValidationSuite.cs", [
    ('''            ("T12", "Powertrain: idle, rev limit, gear ratios, 0-100 km/h, top speed, engine braking, wheelspin", PowertrainTests.Powertrain),''',
     '''            ("T10", "Suspension: static corner loads, bounce, 50 mm step, curb strike, roll gradient, anti-roll bars", HandlingTests.Suspension),
            ("T11", "Steering: angle vs input on turntables, ratio, speed-sensitive reduction, return to centre", HandlingTests.Steering),
            ("T12", "Powertrain: idle, rev limit, gear ratios, 0-100 km/h, top speed, engine braking, wheelspin", PowertrainTests.Powertrain),'''),
    ('''            ("T13", "Brakes: 100-0 km/h with and without ABS, steering while braking, handbrake, repeated stops", PowertrainTests.Brakes),''',
     '''            ("T13", "Brakes: 100-0 km/h with and without ABS, steering while braking, handbrake, repeated stops", PowertrainTests.Brakes),
            ("T14", "Drive tests: slalom, skidpad, figure eight, speed bump and curb, ramp jump", HandlingTests.DriveTests),'''),
])
print("patched")
