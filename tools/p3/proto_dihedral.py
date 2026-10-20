"""Finite-difference check of the dihedral-angle gradient used by the torsion bars (Sim/Core/Kernels.cs TorsionKernel).

phi = atan2(|b2| b1 . n2, n1 . n2), b1 = x2 - x1, b2 = x3 - x2, b3 = x4 - x3, n1 = b1 x b2, n2 = b2 x b3.
Gradient (Blondel & Karplus 1996, rewritten in these vectors):
  dphi/dx1 = -|b2| / |n1|^2 n1
  dphi/dx4 = +|b2| / |n2|^2 n2
  dphi/dx2 = -(1 + b1.b2 / |b2|^2) dphi/dx1 + (b3.b2 / |b2|^2) dphi/dx4
  dphi/dx3 = -(dphi/dx1 + dphi/dx2 + dphi/dx4)        (translation invariance)
Usage: tools/.venv/Scripts/python.exe tools/p3/proto_dihedral.py
"""
import numpy as np


def phi(x):
    x1, x2, x3, x4 = x
    b1, b2, b3 = x2 - x1, x3 - x2, x4 - x3
    n1, n2 = np.cross(b1, b2), np.cross(b2, b3)
    return np.arctan2(np.linalg.norm(b2) * np.dot(b1, n2), np.dot(n1, n2))


def grad(x):
    x1, x2, x3, x4 = x
    b1, b2, b3 = x2 - x1, x3 - x2, x4 - x3
    n1, n2 = np.cross(b1, b2), np.cross(b2, b3)
    lb2 = np.linalg.norm(b2)
    g1 = -lb2 / np.dot(n1, n1) * n1
    g4 = lb2 / np.dot(n2, n2) * n2
    s1 = np.dot(b1, b2) / (lb2 * lb2)
    s3 = np.dot(b3, b2) / (lb2 * lb2)
    g2 = -(1 + s1) * g1 + s3 * g4
    g3 = -(g1 + g2 + g4)
    return np.array([g1, g2, g3, g4])


def main():
    rng = np.random.default_rng(1)
    worst = 0.0
    for _ in range(500):
        x = rng.normal(size=(4, 3))
        g = grad(x)
        num = np.zeros_like(g)
        h = 1e-6
        for i in range(4):
            for k in range(3):
                xp, xm = x.copy(), x.copy()
                xp[i, k] += h
                xm[i, k] -= h
                d = phi(xp) - phi(xm)
                d = (d + np.pi) % (2 * np.pi) - np.pi
                num[i, k] = d / (2 * h)
        worst = max(worst, np.abs(num - g).max() / max(np.abs(g).max(), 1e-9))
        assert abs(g.sum(0)).max() < 1e-9                       # forces sum to zero
        torque = sum(np.cross(x[i], g[i]) for i in range(4))     # rotation invariance -> no net torque
        assert abs(torque).max() < 1e-9
    print("max relative gradient error", worst)


if __name__ == "__main__":
    main()
