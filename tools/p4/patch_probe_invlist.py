"""One-off (P4): the skin summary also lists the cabin meshes by inverted share, and the frame-rotation record counts only
nodes still joined to the cabin (a torn-off headlamp may tumble)."""
from pathlib import Path

p = Path("Unity/HellcatSandbox/Assets/Game/Views/SkinningProbe.cs")
s = p.read_text(encoding="utf-8")
o = '''            worstCabin = Top(cab);
            worstOther = Top(oth);'''
n = '''            worstCabin = Top(cab);
            worstOther = Top(oth);
            cab.Sort((a, b) => b.Item3.CompareTo(a.Item3));
            var sbi = new System.Text.StringBuilder(" | by inverted share:");
            for (int k = 0; k < math.min(6, cab.Count); k++)
                sbi.Append($" {cab[k].Item1} {cab[k].Item3 * 100:F2} %");
            worstCabin += sbi.ToString();'''
assert s.count(o) == 1
s = s.replace(o, n)
o = '''                    string bn = view.nodeBones[i].name;
                    if (bn.StartsWith("FR_") || bn.StartsWith("FL_") || bn.StartsWith("RR_") || bn.StartsWith("RL_")) continue;'''
n = '''                    string bn = view.nodeBones[i].name;
                    if (bn.StartsWith("FR_") || bn.StartsWith("FL_") || bn.StartsWith("RR_") || bn.StartsWith("RL_")) continue;
                    if (Connected != null && !Connected[i]) continue;'''
assert s.count(o) == 1
s = s.replace(o, n)
o = '''        public float MaxFrameRotationDeg { get; private set; }'''
n = '''        public float MaxFrameRotationDeg { get; private set; }
        /// <summary>Optional, per node: still joined to the cabin (set by the crash scenario before each measurement).</summary>
        public bool[] Connected;'''
assert s.count(o) == 1
s = s.replace(o, n)
p.write_text(s, encoding="utf-8")

p = Path("Unity/HellcatSandbox/Assets/Game/Scenario/CarCrashScenario.cs")
s = p.read_text(encoding="utf-8")
o = '''                probe.Measure();
                jump = probe.MaxFrameDisplacement;'''
n = '''                probe.Connected = crash.Connected();
                probe.Measure();
                jump = probe.MaxFrameDisplacement;'''
assert s.count(o) == 1
s = s.replace(o, n)
p.write_text(s, encoding="utf-8")
print("patched")
