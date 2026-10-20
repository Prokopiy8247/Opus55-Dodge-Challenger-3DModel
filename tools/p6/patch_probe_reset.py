"""P6: the skinning probe forgets its previous frame when the scenario starts (the car was respawned on a lane, up to
180 deg from where it was), and its wheel / suspension exclusion matches the bones' 'NNNN_' index prefix."""
import io

p = r"W:/YouTube/3D Model Dodge Challenger/Unity/HellcatSandbox/Assets/Game/Views/SkinningProbe.cs"
raw = io.open(p, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")
rep = [
    ("        /// <summary>Skins every vertex for the current bone transforms and updates the per-frame statistics.</summary>\n",
     "        /// <summary>Forget the previous measurement (after a respawn: the next frame is compared with nothing).</summary>\n"
     "        public void ResetHistory()\n        {\n            havePrev = false;\n            prevBone = null;\n        }\n\n"
     "        /// <summary>Skins every vertex for the current bone transforms and updates the per-frame statistics.</summary>\n"),
    ("                    string bn = view.nodeBones[i].name;\n",
     "                    string bn = view.nodeBones[i].name;\n"
     "                    if (bn.Length > 5 && bn[4] == '_' && char.IsDigit(bn[0]))\n"
     "                        bn = bn.Substring(5);            // bones are named '<node index>_<node name>'\n"),
]
for a, b in rep:
    assert s.count(a) == 1, (s.count(a), a[:60])
    s = s.replace(a, b)
io.open(p, "w", encoding="utf-8", newline="").write(s.replace("\n", nl))
print("probe ok")

p = r"W:/YouTube/3D Model Dodge Challenger/Unity/HellcatSandbox/Assets/Game/Scenario/CarCrashScenario.cs"
s = io.open(p, encoding="utf-8", newline="").read()
a = "                if (impactTime >= 0f && Mathf.Abs(time - impactTime - postImpactTime + 0.5f) < frameDt * 0.5f)\n"
b = ("                if (frames <= 3)\n"
     "                    probe.ResetHistory();   // the car's bones settle on the lane pose over the first frames after the respawn\n") + a
assert s.count(a) == 1
s = s.replace(a, b)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("scenario ok")
