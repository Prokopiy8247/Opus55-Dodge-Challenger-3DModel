"""One-off (P4): the crash scenario records a 1 kHz cabin pulse around the impact (CFC 60 filtering in tools/gate_p4.py)."""
from pathlib import Path

p = Path("Unity/HellcatSandbox/Assets/Game/Scenario/CarCrashScenario.cs")
s = p.read_text(encoding="utf-8")
pairs = [
    ('''        readonly List<float> cabinG4ms = new List<float>();''',
     '''        readonly List<float> cabinG4ms = new List<float>();
        readonly List<string> pulse = new List<string> { "t_s,cabin_vz_mps,car_front_m" };   // 1 kHz around the impact
        bool near;'''),
    ('''            // step the frame in 4 ms chunks, the cabin deceleration from its velocity change per chunk
            int total = (int)math.round(frameDt / w.dt);
            float3 v0 = float3.zero;
            if (haveCabin) v0 = lastCabinVel;
            for (int done = 0; done < total;)
            {
                int n = math.min(8, total - done);''',
     '''            // step the frame in 4 ms chunks (1 ms near the wall), the cabin deceleration from its velocity change per chunk;
            // the 1 kHz cabin velocity goes to <run>_pulse.csv (CFC 60 filtering in tools/gate_p4.py)
            int total = (int)math.round(frameDt / w.dt);
            float3 v0 = float3.zero;
            if (haveCabin) v0 = lastCabinVel;
            for (int done = 0; done < total;)
            {
                int n = math.min(near ? 2 : 8, total - done);'''),
    ('''                lastCabinVel = cv;
                haveCabin = true;
            }''',
     '''                lastCabinVel = cv;
                haveCabin = true;
                if (near && (impactTime < 0f || time - impactTime < 0.6f))
                {
                    crash.Fronts(out _, out float cf);
                    pulse.Add(string.Format(CultureInfo.InvariantCulture, "{0:F4},{1:F5},{2:F4}", runner.SimTime, cv.z, cf));
                }
            }'''),
    ('''            crash.Fronts(out float cabinFront, out float carFront);''',
     '''            crash.Fronts(out float cabinFront, out float carFront);
            near = near || wallFace - carFront < 1.0f;'''),
]
for o, n in pairs:
    assert s.count(o) == 1, o[:80]
    s = s.replace(o, n)
lines = s.split("\n")
out = []
for ln in lines:
    out.append(ln)
    if '_timeseries.csv"), string.Join(' in ln:
        out.append('            File.WriteAllText(Path.Combine(outDir, $"{runId}_pulse.csv"), string.Join(Environment.NewLine, pulse));')
p.write_text("\n".join(out), encoding="utf-8")
print("patched")
