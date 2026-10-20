"""P6: the scenario resets the car view's frames on its first frame (its Start runs before the view's, so the view
missed the respawn's reset and its bone frames turned from the old heading over the first frames: 180 deg on the
north-row lanes)."""
import io

p = r"W:/YouTube/3D Model Dodge Challenger/Unity/HellcatSandbox/Assets/Game/Scenario/CarCrashScenario.cs"
s = io.open(p, encoding="utf-8", newline="").read()
rep = [
    ("        bool running, replaying;\n", "        bool running, replaying, viewReset;\n"),
    ("            if (!running)\n                return;\n            var w = runner.World;\n            float frameDt = 1f / fps;\n",
     "            if (!running)\n                return;\n"
     "            if (!viewReset && carView)\n            {\n"
     "                // the view starts after this script: its frames get the lane heading now (the respawn's reset found it not ready)\n"
     "                carView.ResetVisualState();\n                viewReset = true;\n            }\n"
     "            var w = runner.World;\n            float frameDt = 1f / fps;\n"),
]
for a, b in rep:
    assert s.count(a) == 1, (s.count(a), a[:60])
    s = s.replace(a, b)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
