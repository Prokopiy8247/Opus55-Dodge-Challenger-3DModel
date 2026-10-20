"""P6: the speed hold gets an integral term (anti-windup within 1 m/s of the target), so the entry speed has no droop
(S8 met the wall at 118.3 km/h instead of 120 with the P law alone)."""
import io

p = r"W:/YouTube/3D Model Dodge Challenger/Unity/HellcatSandbox/Assets/Game/Scenario/CarCrashScenario.cs"
s = io.open(p, encoding="utf-8", newline="").read()
rep = [
    ('        DriverInput current = DriverInput.Idle;\n', '        DriverInput current = DriverInput.Idle;\n        float holdI;                    // speed hold: integral of the speed error\n'),
    ('            var hold = new DriverInput\n            {\n                throttle = math.saturate((target - st.speed) * 0.6f + 0.05f), steer = steer, gear = DriverInput.Drive, flags = DriverInput.FlagTc,\n            };\n',
     '            float err = target - st.speed;\n'
     '            if (math.abs(err) < 1f)\n'
     '                holdI = math.clamp(holdI + 0.4f * err / fps, 0f, 0.8f);\n'
     '            var hold = new DriverInput\n            {\n                throttle = math.saturate(err * 0.6f + 0.05f + holdI), steer = steer, gear = DriverInput.Drive, flags = DriverInput.FlagTc,\n            };\n'),
]
for a, b in rep:
    assert s.count(a) == 1, (s.count(a), a[:70])
    s = s.replace(a, b)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
