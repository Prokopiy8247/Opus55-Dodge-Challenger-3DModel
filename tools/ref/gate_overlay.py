"""G-Model silhouette comparison: model measurements (docs/gates/p1_model_measure.json, from
hcar.gate_model.measure) against the dimensions.com profiles (docs/p1/ref_profiles.json) and the
spec sheet dimensions.

Writes docs/gates/gate_p1_silhouette.json (stats, versioned) and overlay plots in
docs/p1/overlay_gate/ (not versioned: they show the private drawing).
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SPEC = {"length": 5.017, "width_no_mirrors": 1.990, "width_with_mirrors": 2.169, "height": 1.460,
        "width_body_no_flares": 1.923}


def arr(v):
    return np.array([np.nan if x is None else x for x in v], float)


def compare(x_m, v_m, x_r, v_r, mask=None):
    vr = np.interp(x_m, x_r, v_r, left=np.nan, right=np.nan)
    d = v_m - vr
    ok = ~np.isnan(d)
    if mask is not None:
        ok &= mask
    if not ok.any():
        return None, d
    return {"rms_mm": round(float(np.sqrt(np.nanmean(d[ok] ** 2)) * 1000), 1),
            "max_abs_mm": round(float(np.nanmax(np.abs(d[ok])) * 1000), 1),
            "p95_abs_mm": round(float(np.nanpercentile(np.abs(d[ok]), 95) * 1000), 1),
            "n": int(ok.sum())}, d


def main():
    mm = json.loads((ROOT / "docs/gates/p1_model_measure.json").read_text(encoding="utf-8"))
    rp = json.loads((ROOT / "docs/p1/ref_profiles.json").read_text(encoding="utf-8"))
    out = {"dims": {}, "silhouettes": {}}
    for k, ref in SPEC.items():
        v = mm["dims"][k]
        out["dims"][k] = {"model": round(v, 4), "spec": ref, "dev_pct": round(100 * (v - ref) / ref, 2)}
    y_m = np.array(mm["side"]["y"])
    y_r = np.array(rp["side"]["y"])
    # side silhouette: top (no antenna/mirrors) and bottom between the wheels and at the overhangs
    zt_m, zb_m = arr(mm["side"]["z_top"]), arr(mm["side"]["z_bottom"])
    zt_r, zb_r = arr(rp["side"]["z_top"]), arr(rp["side"]["z_bottom"])
    not_antenna = np.abs(y_m + 0.96) > 0.10
    no_scoop = ~((y_m > 1.14) & (y_m < 1.32))        # the hood scoop is not in the drawing (D-018)
    wheels = (np.abs(np.abs(y_m) - 1.4755) < 0.48)
    out["silhouettes"]["side_top"], d_top = compare(y_m, zt_m, y_r, zt_r, not_antenna)
    out["silhouettes"]["side_top_no_scoop"], _ = compare(y_m, zt_m, y_r, zt_r, not_antenna & no_scoop)
    out["silhouettes"]["side_bottom_body"], d_bot = compare(y_m, zb_m, y_r, zb_r, ~wheels)
    hw_m = arr(mm["plan"]["half_width_no_flares"])
    hw_r = arr(rp["plan"]["half_width"])
    out["silhouettes"]["plan_half_width_no_flares"], d_plan = compare(y_m, hw_m, y_r, hw_r)
    z_m = np.array(mm["front_view"]["z"])
    for view in ("front", "rear"):
        # the drawing shows the standard body: compare the body without the widebody flares
        hv_m = arr(mm[f"{view}_view"].get("half_width_no_flares", mm[f"{view}_view"]["half_width"]))
        hv_r = arr(rp[f"{view}_view"]["half_width"])
        z_r = np.array(rp[f"{view}_view"]["z"])
        # above the tires, below the roof top, outside the mirror band (the drawing envelope
        # includes the mirrors, the model profile excludes them)
        body_band = (z_m > 0.55) & (z_m < 1.42) & ~((z_m > 0.94) & (z_m < 1.13))
        out["silhouettes"][f"{view}_half_width"], _ = compare(z_m, hv_m, z_r, hv_r, body_band)
    (ROOT / "docs/gates/gate_p1_silhouette.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    od = ROOT / "docs/p1/overlay_gate"
    od.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(3, 1, figsize=(18, 13))
    ax[0].plot(y_r, zt_r, "k-", lw=1, label="drawing top")
    ax[0].plot(y_r, zb_r, "k-", lw=1, label="drawing bottom")
    ax[0].plot(y_m, zt_m, "r-", lw=0.8, label="model top")
    ax[0].plot(y_m, zb_m, "b-", lw=0.8, label="model bottom")
    ax[0].set_aspect("equal"); ax[0].grid(True, lw=0.3); ax[0].legend(); ax[0].set_title("side silhouette")
    ax[1].plot(y_m, d_top * 1000, "r-", lw=0.8, label="top deviation (mm)")
    ax[1].plot(y_m, d_bot * 1000, "b-", lw=0.8, label="bottom deviation (mm)")
    ax[1].plot(y_m, d_plan * 1000, "g-", lw=0.8, label="plan half-width deviation (mm)")
    ax[1].axhline(0, color="k", lw=0.5); ax[1].set_ylim(-80, 80); ax[1].grid(True, lw=0.3); ax[1].legend()
    ax[2].plot(arr(rp["front_view"]["half_width"]), rp["front_view"]["z"], "k-", label="drawing front")
    ax[2].plot(arr(mm["front_view"]["half_width"]), z_m, "r-", label="model front")
    ax[2].plot(arr(mm["front_view"].get("half_width_no_flares", [])), z_m[:len(mm["front_view"].get("half_width_no_flares", []))], "m:", label="model front, no flares")
    ax[2].plot(arr(rp["rear_view"]["half_width"]), rp["rear_view"]["z"], "k--", label="drawing rear")
    ax[2].plot(arr(mm["rear_view"]["half_width"]), z_m, "b--", label="model rear")
    ax[2].set_aspect("equal"); ax[2].grid(True, lw=0.3); ax[2].legend()
    fig.tight_layout(); fig.savefig(od / "silhouettes.png", dpi=70)


if __name__ == "__main__":
    sys.exit(main())
