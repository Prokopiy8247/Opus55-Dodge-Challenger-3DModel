"""One-off (P3b): saturating hinge damping (D-043 for the belt hinges)."""
from pathlib import Path

ROOT = Path("Unity/HellcatSandbox/Assets/Sim")


def patch(path, pairs):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:100])
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")


patch("Core/HingeJob.cs", [(
    """            float tauD = -h.c * sc * rate;""",
    """            // damping saturates above dampCap rad/s (D-043: a belt hinge bends once a revolution, in ~1.4 ms at 250 km/h;
            // viscous damping of that pass cost 8 kW per wheel, while its small vibrations still need the full damping)
            float rateD = h.dampCap > 0f ? math.clamp(rate, -h.dampCap, h.dampCap) : rate;
            float tauD = -h.c * sc * rateD;""")])

patch("Core/SimTypes.cs", [(
    """    public struct HingeStatic
    {""",
    """    public struct HingeStatic
    {
        public float dampCap;               // rad/s: the damping torque saturates above this bending rate (0: viscous)""")])

patch("Data/SimParamsDef.cs", [(
    """        public float yieldCap = -1;     // N*m/m, max yield moment (-1: unlimited)
    }""",
    """        public float yieldCap = -1;     // N*m/m, max yield moment (-1: unlimited)
        public float dampCap = 0;       // rad/s: damping saturates above this bending rate (D-043), 0: viscous
    }""")])

patch("Core/SoftBodyWorld.cs", [(
    """            h.c = math.max(mat.damp, 0f) * geo;""",
    """            h.c = math.max(mat.damp, 0f) * geo;
            h.dampCap = math.max(mat.dampCap, 0f);""")])
print("patched")
