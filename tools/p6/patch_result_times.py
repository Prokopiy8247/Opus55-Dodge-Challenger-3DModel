"""P6: the result JSON names the scenario's world start time and the jump's take-off / landing times (pulse alignment)."""
import io
p = r"W:/YouTube/3D Model Dodge Challenger/Unity/HellcatSandbox/Assets/Game/Scenario/CarCrashScenario.cs"
s = io.open(p, encoding="utf-8", newline="").read()
a = '            Put("contact_time_s", F(contactSimTime >= 0 ? contactSimTime - t0 : double.NaN, "F4"));\n'
b = a + ('            Put("sim_start_s", F(simStart, "F4"));\n'
         '            Put("takeoff_time_s", F(landSim >= 0 ? takeoffSim - t0 : double.NaN, "F4"));\n'
         '            Put("landing_time_s", F(landSim >= 0 ? landSim - t0 : double.NaN, "F4"));\n')
assert s.count(a) == 1
s = s.replace(a, b)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
