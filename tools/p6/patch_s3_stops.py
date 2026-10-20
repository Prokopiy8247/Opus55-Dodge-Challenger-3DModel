"""P6: S3 centred on the pole (aimed at the front axle, D-084); dynamic crush only while the cabin is stopping; closure
stop releases counted apart from broken beams."""
import io

p = r"W:/YouTube/3D Model Dodge Challenger/Unity/HellcatSandbox/Assets/Game/Scenario/CarCrashScenario.cs"
s = io.open(p, encoding="utf-8", newline="").read()
rep = [
    ('            new Spec { id = "S3", lane = "O3", targets = new[] { "O3_Pole" }, kmh = 50f, kind = Kind.Frontal, wheelLine = true,\n'
     '                what = "O3 pole in line with the left front wheel (front axle)" },\n',
     '            new Spec { id = "S3", lane = "O3", targets = new[] { "O3_Pole" }, kmh = 50f, kind = Kind.Frontal,\n'
     '                what = "O3 pole, centred (aimed at the front axle)" },\n'),
    # dynamic crush: integrate only while the cabin is stopping (a car that glances off is not crushing)
    ('                    if (stopSimTime < 0)\n                    {\n                        dynamicCrush += 0.5 * (vf + prevChunkVf) * n * w.dt;\n'
     '                        if (vf <= 0f) stopSimTime = tNow;\n                    }\n',
     '                    if (stopSimTime < 0 && !double.IsNaN(dynamicCrush))\n                    {\n'
     '                        dynamicCrush += 0.5 * (vf + prevChunkVf) * n * w.dt;\n                        if (vf <= 0f) stopSimTime = tNow;\n'
     '                        else if (tNow - contactSimTime > 0.5) dynamicCrush = double.NaN;   // not stopped by the obstacle\n'
     '                    }\n'),
    # stop releases apart from broken beams
    ('        bool[] isRim;\n', '        bool[] isRim;\n        int[] stopBeams = Array.Empty<int>();   // closure perimeter stops (D-034): they release, they do not break\n'),
    ('            intrusionDyn = new double[crash.intrusionGroups.Count];\n',
     '            intrusionDyn = new double[crash.intrusionGroups.Count];\n'
     '            var bodyDef = w.bodies[runner.VehicleBody];\n'
     '            stopBeams = Enumerable.Range(0, bodyDef.beamCount).Where(k => def.beams[k].mat == "stop_closure").Select(k => bodyDef.beamStart + k).ToArray();\n'),
    ('                length.ToString("F4", Ic), crushNow.ToString("F4", Ic), cabinFront.ToString("F4", Ic), m.brokenBeams.ToString(Ic),\n',
     '                length.ToString("F4", Ic), crushNow.ToString("F4", Ic), cabinFront.ToString("F4", Ic), (m.brokenBeams - StopsReleased()).ToString(Ic),\n'),
    ('            Put("broken_beams", m.brokenBeams.ToString(Ic));\n',
     '            int stops = StopsReleased();\n'
     '            Put("broken_beams", (m.brokenBeams - stops).ToString(Ic));\n'
     '            Put("broken_beams_all", m.brokenBeams.ToString(Ic));\n'
     '            Put("closure_stops_released", stops.ToString(Ic));\n'),
    ('        void GroundCheck()\n',
     '        int StopsReleased()\n        {\n            var w = runner.World;\n            int n = 0;\n'
     '            foreach (int j in stopBeams)\n                if (w.broken[j] != 0) n++;\n            return n;\n        }\n\n'
     '        void GroundCheck()\n'),
    ('            Debug.Log($"[CarCrash] done: {runId} entry {entrySpeed * 3.6f:F1} km/h, broken {m.brokenBeams}, ',
     '            Debug.Log($"[CarCrash] done: {runId} entry {entrySpeed * 3.6f:F1} km/h, broken {m.brokenBeams - stops} (+{stops} stops released), '),
]
for a, b in rep:
    if s.count(a) != 1:
        raise SystemExit(f"{s.count(a)} x {a[:80]!r}")
    s = s.replace(a, b)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
