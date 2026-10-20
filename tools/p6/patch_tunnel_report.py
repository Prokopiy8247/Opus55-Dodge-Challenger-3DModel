"""P6: the tunnelling report names the primitive and the test (inside it, or through a plate)."""
import io

p = r"W:/YouTube/3D Model Dodge Challenger/Unity/HellcatSandbox/Assets/Game/Scenario/CrashMetrics.cs"
s = io.open(p, encoding="utf-8", newline="").read()
rep = [
    ('                    float depth = -1f;\n', '                    float depth = -1f;\n                    bool through = false;\n'),
    ('                        if (within && q[ax] * sideSign[k] < -(h[ax] + tol))\n                            depth = math.abs(q[ax]) - h[ax];\n',
     '                        if (within && q[ax] * sideSign[k] < -(h[ax] + tol))\n                        {\n'
     '                            depth = math.abs(q[ax]) - h[ax];\n                            through = true;\n                        }\n'),
    ('                    names?.Add($"{def.nodes[i - b.nodeStart].name} (y {x.y:F2}, {depth:F3} m in)");\n',
     '                    names?.Add($"{def.nodes[i - b.nodeStart].name} (y {x.y:F2}, {depth:F3} m {(through ? "through" : "inside")} primitive {prims[k]})");\n'),
]
for a, b in rep:
    assert s.count(a) == 1, (s.count(a), a[:60])
    s = s.replace(a, b)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
