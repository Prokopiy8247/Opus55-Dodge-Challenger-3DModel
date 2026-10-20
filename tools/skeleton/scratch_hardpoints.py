"""Scratch: evaluate suspension hardpoint changes with the kinematics of suspension_design.py (no rebuild).
Positions in the Blender car frame (x right, y forward, z up); both sides are set (mirrored)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import suspension_design as sd  # noqa: E402


def setp(car, name, xb, yb, zb):
    car.P[car.idx[name]] = [xb, zb, yb]


def getb(car, name):
    u = car.P[car.idx[name]]
    return u[0], u[2], u[1]


def front(car, lca_z, uca_z, rack_z, uca_x=None):
    for nm, sx in (("FR", 1), ("FL", -1)):
        for k in ("lca_f", "lca_r"):
            x, y, _ = getb(car, f"{nm}_{k}")
            setp(car, f"{nm}_{k}", x, y, lca_z)
        for k in ("uca_f", "uca_r"):
            x, y, _ = getb(car, f"{nm}_{k}")
            setp(car, f"{nm}_{k}", sx * uca_x if uca_x else x, y, uca_z)
        s = nm[1]
        x, y, _ = getb(car, f"rack_{s}")
        setp(car, f"rack_{s}", x, y, rack_z)


def rear(car, low_z, up_x, up_z, toe_z):
    for nm, sx in (("RR", 1), ("RL", -1)):
        for n in (0, 1):
            x, y, _ = getb(car, f"{nm}_link{n}")
            setp(car, f"{nm}_link{n}", x, y, low_z)
        for n in (2, 3):
            x, y, _ = getb(car, f"{nm}_link{n}")
            setp(car, f"{nm}_link{n}", sx * up_x, y, up_z)
        x, y, _ = getb(car, f"{nm}_link4")
        setp(car, f"{nm}_link4", x, y, toe_z)


def report(car, tag):
    for n in ("FR", "RR"):
        c = sd.corner(car, n, n[0] == "F")
        print(f"{tag} {n}: MR {c['mr']:.3f} RC {c['rc']:.3f} camber {c['camber_gain']:.1f} deg/m bump steer "
              f"{c['bump_steer']:.2f} deg/m cond {c['cond']:.3f} lever {c['g_lever']:.2f}")


def zero(fn, lo, hi):
    flo = fn(lo)
    for _ in range(60):
        mid = (lo + hi) / 2
        fm = fn(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return (lo + hi) / 2


def main():
    car, _ = sd.design("hellcat")
    report(car, "now ")
    lca_z, uca_z = float(sys.argv[1]), float(sys.argv[2])
    low_z, up_x, up_z = float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])

    def bs_front(rz):
        front(car, lca_z, uca_z, rz)
        return sd.corner(car, "FR", True)["bump_steer"]

    def bs_rear(tz):
        rear(car, low_z, up_x, up_z, tz)
        return sd.corner(car, "RR", False)["bump_steer"]

    for rz in (0.20, 0.25, 0.30, 0.35):
        print(f"  rack z {rz}: front bump steer {bs_front(rz):.2f}")
    for tz in (0.20, 0.25, 0.30, 0.35, 0.40):
        print(f"  toe z {tz}: rear bump steer {bs_rear(tz):.2f}")
    rz = zero(bs_front, 0.18, 0.40)
    tz = zero(bs_rear, 0.15, 0.45)
    front(car, lca_z, uca_z, rz)
    rear(car, low_z, up_x, up_z, tz)
    print(f"rack z {rz:.4f}, toe z {tz:.4f}")
    report(car, "new ")


if __name__ == "__main__":
    main()
