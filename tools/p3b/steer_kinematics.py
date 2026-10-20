"""P3b: rigid-knuckle steering kinematics of the front corners (rotation about the ball-joint axis, the tie rod as a
hydro beam of length l0 (1 + hf u)): road-wheel angles vs input, Ackermann share at lock, on-centre ratio, for a
tie-rod-end offset dx (outboard, m) and a hydro factor. Usage: steer_kinematics.py [dx ...]"""
import sys
import numpy as np

sys.path.insert(0, "tools/skeleton")
from stability import load  # noqa: E402

g, p = load("hellcat")
N = g["nodes"]
I = {n["name"]: i for i, n in enumerate(N)}
P = {n["name"]: np.array(n["p"], float) for n in N}
turns = p["steering"]["steeringWheelTurnsLockToLock"]
WB = 2.951


def rot(v, k, a):
    return v * np.cos(a) + np.cross(k, v) * np.sin(a) + k * np.dot(k, v) * (1 - np.cos(a))


def wheel_angle(side, u, dx, hf):
    s = "R" if side > 0 else "L"
    lbj, ubj, tre, rack = P[f"F{s}_lbj"], P[f"F{s}_ubj"], P[f"F{s}_tre"].copy(), P[f"rack_{s}"]
    tre[0] += side * dx
    ai, ao = P[f"F{s}_axle_in"], P[f"F{s}_axle_out"]
    k = (ubj - lbj) / np.linalg.norm(ubj - lbj)
    l0 = np.linalg.norm(tre - rack)
    lt = l0 * np.clip(1 + side * hf * u, 0.7, 1.3)
    # solve |rot(tre - lbj) + lbj - rack| = lt for the rotation about k (bisection near 0)
    f = lambda a: np.linalg.norm(rot(tre - lbj, k, a) + lbj - rack) - lt
    lo, hi = -1.2, 1.2
    a = np.linspace(lo, hi, 2401)
    v = np.array([f(x) for x in a])
    # root closest to 0
    idx = np.where(np.sign(v[:-1]) != np.sign(v[1:]))[0]
    best = min(idx, key=lambda i: abs(a[i]))
    x0, x1 = a[best], a[best + 1]
    for _ in range(60):
        xm = 0.5 * (x0 + x1)
        if np.sign(f(xm)) == np.sign(f(x0)):
            x0 = xm
        else:
            x1 = xm
    ang = 0.5 * (x0 + x1)
    axle = rot((ao - ai) * side, k, ang)        # outward axle direction
    head = np.cross(axle * side, np.array([0, 1.0, 0]))   # forward for both sides
    head = head / np.linalg.norm(head)
    return np.degrees(np.arctan2(head[0], head[2]))     # right positive


def study(dx, hf=0.22):
    us = np.linspace(-1, 1, 41)
    fl = np.array([wheel_angle(-1, u, dx, hf) for u in us])
    fr = np.array([wheel_angle(+1, u, dx, hf) for u in us])
    fl -= wheel_angle(-1, 0, dx, hf)
    fr -= wheel_angle(+1, 0, dx, hf)
    # right lock: inner = FR
    inner, outer = fr[-1], fl[-1]
    # ideal Ackermann outer for this inner: cot(o) - cot(i) = t / L (t: kingpin track)
    t = P["FR_lbj"][0] * 2 + 2 * dx
    ideal = np.degrees(np.arctan(1 / (1 / np.tan(np.radians(inner)) + t / WB)))
    share = (inner - outer) / max(inner - ideal, 1e-9)
    sw = 0.5 * turns * 360
    c = 0.5 * (fl[21] + fr[21]) / (us[21])          # input 0.05
    print(f"dx {dx * 1000:+5.1f} mm hf {hf:.3f}: inner {inner:5.2f} outer {outer:5.2f} (ideal outer {ideal:5.2f}, "
          f"Ackermann {share * 100:5.1f} %), on-centre ratio {sw / c:5.2f}:1, at lock {sw / (0.5 * (inner + outer)):5.2f}:1, "
          f"mean at 0.5 input {0.5 * (fl[30] + fr[30]):5.2f}")


for a in (sys.argv[1:] or ["0", "0.01", "0.02", "0.03", "0.04"]):
    study(float(a))
