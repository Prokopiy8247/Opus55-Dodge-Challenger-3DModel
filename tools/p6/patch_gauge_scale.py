"""P6: tire gauge pressure scale in params.json (pressure.gaugeScale) for the sensitivity sweep."""
import io
from pathlib import Path

A = Path(r"W:/YouTube/3D Model Dodge Challenger/Unity/HellcatSandbox/Assets")


def patch(rel, pairs):
    p = A / rel
    s = io.open(p, encoding="utf-8", newline="").read()
    for a, b in pairs:
        if s.count(a) != 1:
            raise SystemExit(f"{rel}: {s.count(a)} x {a[:60]!r}")
        s = s.replace(a, b)
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("patched", rel)


nl = "\r\n" if b"\r\n" in (A / "Sim/Data/SimParamsDef.cs").read_bytes() else "\n"
patch("Sim/Data/SimParamsDef.cs", [(
    "        public float atmosphere = 101325f;   // Pa" + nl,
    "        public float atmosphere = 101325f;   // Pa" + nl +
    "        public float gaugeScale = 1f;        // multiplies the geometry's gauge pressures (tuning, P6 sweep)" + nl)])
nl = "\r\n" if b"\r\n" in (A / "Sim/Core/SoftBodyWorld.cs").read_bytes() else "\n"
patch("Sim/Core/SoftBodyWorld.cs", [
    ("            var pp = b.prm.pressure;" + nl + "            int gg = b.pressureStart + g;" + nl,
     "            var pp = b.prm.pressure;" + nl + "            float gauge = pd.pressure * pp.gaugeScale;" + nl +
     "            int gg = b.pressureStart + g;" + nl),
    ("                double3 share = pd.pressure * area / 3.0;", "                double3 share = gauge * area / 3.0;"),
    ("            float pAbs0 = pd.pressure + pp.atmosphere;", "            float pAbs0 = gauge + pp.atmosphere;"),
])
