import io
p = r"W:/YouTube/3D Model Dodge Challenger/Unity/HellcatSandbox/Assets/Game/Scenario/CarCrashScenario.cs"
s = io.open(p, encoding="utf-8", newline="").read()
a = "                float gap = near ? ChunkGap() : float.MaxValue;\n"
b = a + "                if (near)\n                    crash.TrackPlates(targets, laneO);   // tunnelling through a plate (wall, guardrail beam)\n"
assert s.count(a) == 1
s = s.replace(a, b)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
