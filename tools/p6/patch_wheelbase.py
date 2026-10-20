"""P6: wheelbase change at the end of a run (left / right axle centres), as NHTSA's NCAP data sheet reports it."""
import io

p = r"W:/YouTube/3D Model Dodge Challenger/Unity/HellcatSandbox/Assets/Game/Scenario/CarCrashScenario.cs"
s = io.open(p, encoding="utf-8", newline="").read()
a = '            Put("length_initial_m", F(initialLength, "F4"));\n'
b = ('            Put("wheelbase_change_left_mm", F(WheelbaseChange("L") * 1000.0, "F1"));\n'
     '            Put("wheelbase_change_right_mm", F(WheelbaseChange("R") * 1000.0, "F1"));\n') + a
assert s.count(a) == 1
s = s.replace(a, b)
a = '        int StopsReleased()\n'
b = ('        /// <summary>Shortening (m) of one side\'s wheelbase: the outer axle centres, model distance minus now.</summary>\n'
     '        double WheelbaseChange(string side)\n        {\n            var w = runner.World;\n'
     '            var b = w.bodies[runner.VehicleBody];\n            int f = -1, r = -1;\n'
     '            for (int i = 0; i < b.nodeCount; i++)\n            {\n'
     '                if (b.def.nodes[i].name == $"F{side}_axle_out") f = i;\n'
     '                if (b.def.nodes[i].name == $"R{side}_axle_out") r = i;\n            }\n'
     '            if (f < 0 || r < 0) return double.NaN;\n'
     '            var pf = b.def.nodes[f].p;\n            var pr = b.def.nodes[r].p;\n'
     '            double rest = math.distance(new double3(pf[0], pf[1], pf[2]), new double3(pr[0], pr[1], pr[2]));\n'
     '            return rest - math.distance((double3)w.pos[b.nodeStart + f], (double3)w.pos[b.nodeStart + r]);\n        }\n\n') + a
assert s.count(a) == 1
s = s.replace(a, b)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
