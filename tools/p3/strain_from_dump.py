"""Where does the solver's resting car deform? Beam length changes from a T6 node dump (model vs final positions).

Usage: tools/.venv/Scripts/python.exe tools/p3/strain_from_dump.py docs/p3/validation/T6_spawn_nodes.csv [--top 40]
"""
import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "skeleton"))
from stability import load  # noqa: E402


def family(n):
    return re.split(r"\d", n, 1)[0].rstrip("_")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--top", type=int, default=40)
    ns = ap.parse_args()
    g, p = load("hellcat")
    mats = {m["name"]: m for m in p["materials"]}
    rows = {r["name"]: r for r in csv.DictReader(open(ns.dump, encoding="utf-8"))}
    names = [n["name"] for n in g["nodes"]]
    X0 = np.array([[float(rows[n]["mx"]), float(rows[n]["my"]), float(rows[n]["mz"])] for n in names])
    X1 = np.array([[float(rows[n]["x"]), float(rows[n]["y"]), float(rows[n]["z"])] for n in names])
    # remove the rigid motion (Kabsch fit on the body part) so only deformation remains
    body = np.array([n["part"] == "body" for n in g["nodes"]])
    c0, c1 = X0[body].mean(0), X1[body].mean(0)
    H = (X0[body] - c0).T @ (X1[body] - c1)
    U_, S_, Vt = np.linalg.svd(H)
    R = Vt.T @ U_.T
    if np.linalg.det(R) < 0:
        Vt[-1] *= -1
        R = Vt.T @ U_.T
    X1r = (X1 - c1) @ R + c0
    E, by = [], defaultdict(float)
    for j, b in enumerate(g["beams"]):
        m = mats[b["mat"]]
        k = m.get("spring", 0.0) or 0.0
        if k <= 0 or "spring" in b["mat"]:
            continue
        L0 = np.linalg.norm(X0[b["b"]] - X0[b["a"]])
        L1 = np.linalg.norm(X1[b["b"]] - X1[b["a"]])
        x = L1 - L0
        e = 0.5 * k * x * x
        E.append((e, j, k * x, x))
        by[tuple(sorted((family(names[b["a"]]), family(names[b["b"]]))))] += e
    E.sort(reverse=True)
    tot = sum(e for e, *_ in E)
    print(f"elastic energy in the structure (springs excluded): {tot:.1f} J; top beams:")
    for e, j, F, x in E[:ns.top]:
        b = g["beams"][j]
        print(f"  {e:7.2f} J  {names[b['a']]:>16s} - {names[b['b']]:<16s} {b['mat']:14s} dL {x * 1000:7.2f} mm  F {F:8.0f} N")
    print("by family pair:")
    for key, e in sorted(by.items(), key=lambda kv: -kv[1])[:25]:
        print(f"  {e:7.2f} J {100 * e / tot:5.1f} %  {key[0]} - {key[1]}")
    d = np.linalg.norm(X1r - X0, axis=1)
    print("largest deformation displacement after removing the rigid motion (mm):")
    for i in np.argsort(-d)[:15]:
        print(f"  {names[i]:18s} {d[i] * 1000:7.1f}  dy {(X1r[i, 1] - X0[i, 1]) * 1000:7.1f}")


if __name__ == "__main__":
    main()
