"""Wind-up bar design (P3, D-036): a torsion bar (dihedral spring-damper) per corner about the axle line, between a
knuckle node and a body anchor, resisting the knuckle's rotation about the spin axis relative to the body (brake and
drive torque reaction) that the stability-limited link stiffness cannot.

For every candidate body anchor near a corner this reports
  travel   d(phi)/d(wheel travel) from the P2 knuckle kinematics (rad/m): the bar adds K (dphi/dz)^2 to the wheel rate
  steer    d(phi)/d(steer angle) about the kingpin (front): the bar adds K (dphi/dsteer)^2 to the steering stiffness
  load     max over the 4 nodes of dt^2 K |g_i|^2 / m_i (the bar's own explicit-stability load at stiffness K)
  lever    distance of the anchor from the axle line (m)

Usage: tools/.venv/Scripts/python.exe tools/p3/windup_bar.py [--k 60000] [--top 8]
"""
import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from suspension_design import Car, knuckle_motion  # noqa: E402


def dihedral(x1, x2, x3, x4):
    """phi and its gradient (Blondel-Karplus, as TorsionKernel.Gradient)."""
    b1, b2, b3 = x2 - x1, x3 - x2, x4 - x3
    n1, n2 = np.cross(b1, b2), np.cross(b2, b3)
    lb2 = np.linalg.norm(b2)
    m1 = np.cross(n1, b2 / lb2)
    phi = np.arctan2(m1 @ n2, n1 @ n2)
    g1 = -lb2 / (n1 @ n1) * n1
    g4 = lb2 / (n2 @ n2) * n2
    c1, c3 = (b1 @ b2) / (lb2 * lb2), (b3 @ b2) / (lb2 * lb2)
    g2 = (c1 - 1.0) * g1 - c3 * g4
    g3 = (c3 - 1.0) * g4 - c1 * g1
    return phi, (g1, g2, g3, g4)


def rot(v, axis, ang):
    axis = axis / np.linalg.norm(axis)
    return v * np.cos(ang) + np.cross(axis, v) * np.sin(ang) + axis * (axis @ v) * (1 - np.cos(ang))


def corner_links(car, name):
    if name[0] == "F":
        kn = {k: car.pos(f"{name}_{k}") for k in ("lbj", "ubj", "tre")}
        links = [(car.pos(f"{name}_lca_f"), kn["lbj"]), (car.pos(f"{name}_lca_r"), kn["lbj"]),
                 (car.pos(f"{name}_uca_f"), kn["ubj"]), (car.pos(f"{name}_uca_r"), kn["ubj"]),
                 (car.pos(f"rack_{name[1]}"), kn["tre"])]
        wing = f"{name}_ubj"
    else:
        kp = {k: car.pos(f"{name}_{k}") for k in ("klf", "klr", "kup")}
        outer = [kp["klf"], kp["klr"], kp["kup"], kp["kup"], kp["klf"]]
        links = [(car.pos(f"{name}_link{n}"), o) for n, o in enumerate(outer)]
        wing = f"{name}_kup"
    return links, wing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=float, default=60000.0, help="bar stiffness N m/rad for the stability load column")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--maxd", type=float, default=1.6)
    ns = ap.parse_args()
    car = Car("hellcat")
    dt = car.p.get("dt", 0.0005)
    names = [n["name"] for n in car.nodes]
    for name in ("FL", "RL"):
        wh = next(w for w in car.g["wheels"] if w["name"] == name)
        ai, ao = wh["axleInner"], wh["axleOuter"]
        hub = (car.P[ai] + car.P[ao]) / 2
        links, wing = corner_links(car, name)
        vel, w, _ = knuckle_motion(links, hub)
        x1i = car.idx[wing]
        x1, x2, x3 = car.P[x1i], car.P[ai], car.P[ao]
        print(f"{name}: wing {wing}, axle nodes {names[ai]} {names[ai]} m {car.m[ai]:.2f}/{car.m[ao]:.2f} kg, "
              f"axle node spacing {np.linalg.norm(x3 - x2) * 1000:.0f} mm, knuckle w.e per m travel "
              f"{w @ ((x3 - x2) / np.linalg.norm(x3 - x2)):+.3f} rad/m")
        rows = []
        for j, nd in enumerate(car.nodes):
            if nd["part"] != "body" or nd["flags"] & 8:
                continue
            x4 = car.P[j]
            if np.linalg.norm(x4 - hub) > ns.maxd:
                continue
            e = (x3 - x2) / np.linalg.norm(x3 - x2)
            r4 = x4 - x2
            lever = np.linalg.norm(r4 - (r4 @ e) * e)
            if lever < 0.15:
                continue
            phi, g = dihedral(x1, x2, x3, x4)
            # travel: knuckle points move with vel(), the anchor is fixed
            dtr = sum(gi @ vel(xi) for gi, xi in zip(g[:3], (x1, x2, x3)))
            dst = 0.0
            if name[0] == "F":
                lbj, ubj = car.pos(f"{name}_lbj"), car.pos(f"{name}_ubj")
                kp = ubj - lbj
                h = 1e-4
                y = [lbj + rot(x - lbj, kp, h) for x in (x1, x2, x3)]
                p2, _ = dihedral(y[0], y[1], y[2], x4)
                dst = (p2 - phi) / h
            masses = (car.m[x1i], car.m[ai], car.m[ao], car.m[j])
            load = max(dt * dt * ns.k * (gi @ gi) / mi for gi, mi in zip(g, masses))
            rows.append((abs(dtr) + 0.3 * abs(dst), names[j], dtr, dst, load, lever, car.m[j]))
        rows.sort()
        print(f"  {'anchor':16s} {'travel':>8s} {'steer':>8s} {'load':>6s} {'lever':>6s} {'m':>5s}   "
              f"(+ wheel rate at K={ns.k / 1000:.0f} kN m/rad = K travel^2)")
        for _, nm, dtr, dst, load, lever, mj in rows[:ns.top]:
            print(f"  {nm:16s} {dtr:+8.3f} {dst:+8.3f} {load:6.3f} {lever:6.3f} {mj:5.1f}   "
                  f"+{ns.k * dtr * dtr / 1000:5.2f} kN/m")


if __name__ == "__main__":
    main()
