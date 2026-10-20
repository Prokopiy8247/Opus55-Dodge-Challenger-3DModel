"""One-off (P4): the crash time series records the driver inputs of every frame (throttle, brake, steer: the scripted
scenario's input recording, brief 9), and the result JSON the time the frame capture started."""
from pathlib import Path

p = Path("Unity/HellcatSandbox/Assets/Game/Scenario/CarCrashScenario.cs")
s = p.read_text(encoding="utf-8")
pairs = [
    ('''        int frameIndex;''',
     '''        int frameIndex;
        float captureStart = -1f;'''),
    ('''"kinetic_J,elastic_J,pressure_J,torsion_J,plastic_J,breaking_J,damping_J,contact_J,tunnelled,vertex_jump_mm,inverted_share");''',
     '''"kinetic_J,elastic_J,pressure_J,torsion_J,plastic_J,breaking_J,damping_J,contact_J,tunnelled,vertex_jump_mm,inverted_share," +
                     "throttle,brake,steer");'''),
    ('''                m.contactWork.ToString("F1", ic), tunnelled.ToString(), (jump * 1000f).ToString("F2", ic), inv.ToString("F5", ic),''',
     '''                m.contactWork.ToString("F1", ic), tunnelled.ToString(), (jump * 1000f).ToString("F2", ic), inv.ToString("F5", ic),
                current.throttle.ToString("F3", ic), current.brake.ToString("F3", ic), current.steer.ToString("F4", ic),'''),
    ('''                frameIndex++;''',
     '''                if (frameIndex == 0) captureStart = time;
                frameIndex++;'''),
]
for o, n in pairs:
    assert s.count(o) == 1, o[:90]
    s = s.replace(o, n)
o = '''            sb.Append($"  \\"frames_captured\\": {frameIndex},'''
assert s.count(o) == 1, "frames_captured"
s = s.replace(o, '''            sb.Append($"  \\"capture_start_s\\": {F(captureStart, "F4")},\\n  \\"capture_fps\\": {fps},\\n");
            sb.Append($"  \\"frames_captured\\": {frameIndex},''')
p.write_text(s, encoding="utf-8")
print("patched")
