"""Compare the parametric body (tools/blender/hcar/shape.py) with the reference drawing.

Writes docs/p1/overlay_shape/{side,plan,front,rear,sections}.png (not versioned: they contain the
private drawing). Usage: tools/.venv/Scripts/python.exe tools/ref/check_shape.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))

from hcar import body_tables as bt  # noqa: E402
from hcar.shape import KNOTS, Outline, Strip  # noqa: E402

OUT = ROOT / "docs" / "p1" / "overlay_shape"


def ref():
    feats = json.loads((ROOT / "docs/p1/ref_features.json").read_text(encoding="utf-8"))
    prof = json.loads((ROOT / "docs/p1/ref_profiles.json").read_text(encoding="utf-8"))
    return feats, prof


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    OUT.mkdir(parents=True, exist_ok=True)
    feats, prof = ref()
    O = Outline(bt.OUTLINE, R=bt.GUIDE_R)
    st = Strip(O, bt.FEATURE_CURVES, bt.STRIP_ANCHORS)
    ns = 400
    s = np.linspace(0, O.S, ns)
    tt = np.linspace(0, 1, 161)
    P = st.point(np.repeat(s, len(tt)).reshape(ns, -1), np.tile(tt, ns).reshape(ns, -1))  # (ns, nt, 3)
    knot_idx = [int(round(k * 160)) for k in KNOTS]
    colors = ["k", "b", "g", "r", "m", "c"]

    def draw_ref(ax, view, a_idx, b_idx, sign_a=1.0):
        for ln in feats[view]:
            p = np.array(ln["pts"])
            ax.plot(sign_a * p[:, 0], p[:, 1], "-", color="0.65", lw=0.6)

    # side view (y, z)
    fig, ax = plt.subplots(figsize=(26, 8))
    draw_ref(ax, "side", 0, 1)
    for k, j in enumerate(knot_idx):
        ax.plot(P[:, j, 1], P[:, j, 2], "-", color=colors[k], lw=1.0, label=f"K{k}")
    for i in range(0, ns, 8):
        ax.plot(P[i, :, 1], P[i, :, 2], "-", color="orange", lw=0.3)
    ax.set_aspect("equal"); ax.grid(True, lw=0.3); ax.legend(); ax.set_title("side: strip key lines (colour) vs drawing (grey)")
    fig.tight_layout(); fig.savefig(OUT / "side.png", dpi=80); plt.close(fig)

    # plan (y, x)
    fig, ax = plt.subplots(figsize=(26, 7))
    for ln in feats["plan"]:
        p = np.array(ln["pts"])
        if p[:, 1].mean() > -0.05:
            ax.plot(p[:, 0], p[:, 1], "-", color="0.65", lw=0.6)
    for k, j in enumerate(knot_idx):
        ax.plot(P[:, j, 1], P[:, j, 0], "-", color=colors[k], lw=1.0, label=f"K{k}")
    hmax = P[:, :, 0].max(axis=1)
    ax.plot(P[np.arange(ns), P[:, :, 0].argmax(axis=1), 1], hmax, "y--", lw=0.8, label="max x")
    ax.plot(O._pts[:, 1], O._pts[:, 0], "k:", lw=0.8, label="guide")
    ax.plot(O.waist[:, 1], O.waist[:, 0], "y-", lw=0.5, label="waist")
    for sa in st.anchor_s:
        g = O.point(sa)
        nn = O.normal(sa)
        ax.plot([g[1], g[1] - 0.25 * nn[1]], [g[0], g[0] - 0.25 * nn[0]], "-", color="purple", lw=0.6)
    ax.set_aspect("equal"); ax.grid(True, lw=0.3); ax.legend(); ax.set_title("plan: strip key lines vs drawing")
    fig.tight_layout(); fig.savefig(OUT / "plan.png", dpi=80)
    for nm, (y0, y1) in (("rear", (-2.65, -1.75)), ("front", (1.6, 2.5))):
        ax.set_xlim(y0, y1); ax.set_ylim(0.0, 1.0)
        for i in range(0, ns, 2):
            ax.plot(P[i, ::4, 1], P[i, ::4, 0], "-", color="orange", lw=0.25)
        fig.set_size_inches(12, 12)
        fig.savefig(OUT / f"plan_{nm}_corner.png", dpi=80)
    plt.close(fig)

    # front / rear views (x, z): only stations in front of / behind the middle
    for view, mask in (("front", P[:, 0, 1] > 0.3), ("rear", P[:, 0, 1] < -0.3)):
        fig, ax = plt.subplots(figsize=(10, 9))
        for ln in feats[view]:
            p = np.array(ln["pts"])
            if p[:, 0].mean() > -0.05:
                ax.plot(p[:, 0], p[:, 1], "-", color="0.65", lw=0.6)
        Q = P[mask]
        for k, j in enumerate(knot_idx):
            ax.plot(Q[:, j, 0], Q[:, j, 2], "-", color=colors[k], lw=1.0)
        for i in range(0, len(Q), 6):
            ax.plot(Q[i, :, 0], Q[i, :, 2], "-", color="orange", lw=0.3)
        ax.set_aspect("equal"); ax.grid(True, lw=0.3); ax.set_title(f"{view} view")
        fig.tight_layout(); fig.savefig(OUT / f"{view}.png", dpi=80); plt.close(fig)

    # sections at the anchors (h, z)
    fig, axes = plt.subplots(3, 8, figsize=(30, 13))
    for ax, sa, nm in zip(axes.ravel(), st.anchor_s, st.anchor_names):
        sec = st.section(sa)
        ax.plot(sec["p"][:, 0], sec["p"][:, 1], "b-", lw=1)
        K = sec["K"]
        ax.plot(K[:, 0], K[:, 1], "ro", ms=3)
        ax.set_aspect("equal"); ax.grid(True, lw=0.3); ax.set_title(nm, fontsize=9)
    fig.tight_layout(); fig.savefig(OUT / "sections.png", dpi=70); plt.close(fig)
    print("S =", round(O.S, 4), "anchors:", [round(v, 3) for v in st.anchor_s])


if __name__ == "__main__":
    main()
