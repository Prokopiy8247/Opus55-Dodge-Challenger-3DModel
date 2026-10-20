"""P4: global body stiffness without the rigidifiers (D-040) that reach into the crush zones.

The rigidifier design (tools/skeleton/rigidifier_design.py) chose long beams from the bumper / core support / front rail
tips through the body to the rear floor: in a frontal crash they are struts that bypass the crush zone. This evaluates the
torsion, bending and tower-cantilever metrics of the body-in-white with the rigidifiers that have an end ahead of
z = zf (front) or behind z = zr (rear) removed, for a few limits.

Usage: tools/.venv/Scripts/python.exe tools/p4/rigidifier_zones.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load  # noqa: E402
from rigidifier_design import Body  # noqa: E402


def main():
    g, p = load("hellcat")
    P = [n["p"] for n in g["nodes"]]
    beams = g["beams"]
    rig = [b for b in beams if b["mat"] == "rigidifier"]
    print(f"{len(rig)} rigidifiers")
    for zf, zr in ((99, -99), (1.9, -99), (1.8, -99), (1.7, -99), (1.6, -99), (1.7, -2.0), (1.7, -1.9), (1.5, -99)):
        keep = [b for b in beams if b["mat"] != "rigidifier" or
                (max(P[b["a"]][2], P[b["b"]][2]) <= zf and min(P[b["a"]][2], P[b["b"]][2]) >= zr)]
        g2 = dict(g)
        g2["beams"] = keep
        B = Body(g2, p, 1.5e6)
        met = B.metrics(B.solve_all())
        nr = sum(1 for b in keep if b["mat"] == "rigidifier")
        print(f"front limit {zf:5.2f} rear {zr:6.2f}: {nr:3d} rigidifiers -> {met}")


if __name__ == "__main__":
    main()
