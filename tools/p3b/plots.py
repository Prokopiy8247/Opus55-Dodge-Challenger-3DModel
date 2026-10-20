"""Plots for docs/dynamics_report.md (P3b) from the CSV series of the dynamics validation run
(docs/p3b/validation/T9_*.csv ... T14_*.csv). Writes PNGs into docs/p3b/plots/.

Usage: tools/.venv/Scripts/python.exe tools/p3b/plots.py
"""
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
VAL = ROOT / "docs/p3b/validation"
OUT = ROOT / "docs/p3b/plots"


def load(name):
    p = VAL / f"{name}.csv"
    if not p.exists():
        return None
    with p.open(encoding="utf-8") as f:
        rows = list(csv.reader(f))
    head = rows[0]
    data = {}
    for k, h in enumerate(head):
        col = []
        for r in rows[1:]:
            try:
                col.append(float(r[k]))
            except (ValueError, IndexError):
                col.append(np.nan)
        data[h] = np.array(col)
    return data


def fig(name, w=7.0, h=4.2):
    f, ax = plt.subplots(figsize=(w, h), dpi=110)
    ax.grid(True, alpha=0.3)
    return f, ax


def save(f, name):
    OUT.mkdir(parents=True, exist_ok=True)
    f.tight_layout()
    f.savefig(OUT / f"{name}.png")
    plt.close(f)
    return name


def t9():
    out = []
    d = load("T9_slip_angle")
    if d is not None:
        f, ax = fig("t9_lateral")
        for fz in sorted(set(d["fz_target"])):
            m = d["fz_target"] == fz
            ax.plot(d["alpha_deg"][m], -d["fy_N"][m] / 1000.0, "o-", ms=3, label=f"Fz {fz / 1000:.1f} kN")
        ax.set_xlabel("slip angle (deg)")
        ax.set_ylabel("lateral force (kN)")
        ax.set_title("T9 tire rig: lateral force vs slip angle")
        ax.legend()
        out.append(save(f, "t9_lateral_force"))
    d = load("T9_longitudinal_slip")
    if d is not None:
        f, ax = fig("t9_long")
        for side in sorted(set(d["side"])):
            m = d["side"] == side
            o = np.argsort(d["kappa"][m])
            ax.plot(d["kappa"][m][o], d["mu_x"][m][o], ".", ms=2, label="drive" if side > 0 else "brake")
        ax.set_xlabel("slip ratio")
        ax.set_ylabel("mu_x = Fx / Fz")
        ax.set_title("T9 tire rig: longitudinal slip sweep")
        ax.legend()
        out.append(save(f, "t9_longitudinal_slip"))
    return out


def t10():
    out = []
    f, ax = fig("t10_bounce")
    for tag, col in (("front", "front_y_mm"), ("rear", "rear_y_mm")):
        d = load(f"T10_bounce_{tag}")
        if d is not None:
            ax.plot(d["t"], d[col], label=f"{tag} bounce: {tag} body height")
    ax.set_xlabel("time after release (s)")
    ax.set_ylabel("body height at the axle (mm)")
    ax.set_title("T10 bounce tests")
    ax.legend()
    out.append(save(f, "t10_bounce"))
    f, ax = fig("t10_roll")
    for name, lab in (("T10_roll_circle", "with anti-roll bars"), ("T10_roll_circle_no_bars", "without")):
        d = load(name)
        if d is not None:
            m = d["t"] > 3.0
            ax.plot(d["ay_g"][m], d["roll_deg"][m], ".", ms=2, label=lab)
    ax.plot([0.0, 0.62], [0.0, 0.62 * 3.0], "k--", lw=1, label="design 3.0 deg/g (incl. tires)")
    ax.set_xlabel("lateral acceleration (g)")
    ax.set_ylabel("body roll (deg)")
    ax.set_title("T10 roll in steady cornering, R 45.7 m")
    ax.legend()
    out.append(save(f, "t10_roll_gradient"))
    d = load("T10_curb_20kmh")
    if d is not None:
        f, ax = fig("t10_curb")
        ax.plot(d["t"], d["travel_FR_mm"], label="FR travel (mm)")
        ax.plot(d["t"], d["travel_RR_mm"], label="RR travel (mm)")
        ax2 = ax.twinx()
        ax2.plot(d["t"], d["fz_FR"] / 1000.0, "r", lw=0.8, alpha=0.6, label="FR tire load (kN)")
        ax2.set_ylabel("tire load (kN)")
        ax.set_xlabel("time (s)")
        ax.set_ylabel("bump travel (mm)")
        ax.set_title("T10 120 mm curb strike at 20 km/h (right wheels)")
        ax.legend(loc="upper left")
        out.append(save(f, "t10_curb_strike"))
    return out


def t11():
    out = []
    d = load("T11_angle_vs_input")
    if d is not None:
        f, ax = fig("t11")
        ax.plot(d["input"], d["fl_deg"], "o-", ms=3, label="FL")
        ax.plot(d["input"], d["fr_deg"], "s-", ms=3, label="FR")
        ax.set_xlabel("steering input (-1 left ... +1 right)")
        ax.set_ylabel("road-wheel angle (deg, right positive)")
        ax.set_title("T11 road-wheel angle vs input (turntables)")
        ax.legend()
        out.append(save(f, "t11_angle_vs_input"))
    d = load("T11_speed_reduction")
    if d is not None:
        f, ax = fig("t11b")
        ax.plot(d["speed"] * 3.6, d["expected_scale"], "k--", label="design")
        ax.plot(d["speed"] * 3.6, d["command_scale"] if "command_scale" in d else d["measured_scale"], "o", label="command")
        if "rwa_scale" in d:
            ax.plot(d["speed"] * 3.6, d["rwa_scale"], "s", label="road-wheel angle")
        ax.set_xlabel("speed (km/h)")
        ax.set_ylabel("scale of the 5 m/s response")
        ax.set_title("T11 speed-sensitive steering reduction")
        ax.legend()
        out.append(save(f, "t11_speed_reduction"))
    return out


def t12():
    out = []
    f, ax = fig("t12")
    for name, lab in (("T12_launch_tc", "traction control on"), ("T12_launch_no_tc", "off")):
        d = load(name)
        if d is not None:
            ax.plot(d["t"], d["speed_kmh"], label=lab)
    ax.axhline(100, color="k", lw=0.8, ls=":")
    ax.set_xlabel("time from the throttle (s)")
    ax.set_ylabel("speed (km/h)")
    ax.set_title("T12 launch, full throttle")
    ax.legend()
    out.append(save(f, "t12_launch"))
    d = load("T12_top_speed")
    if d is not None:
        f, ax = fig("t12b")
        ax.plot(d["t"], d["speed_kmh"])
        ax.set_xlabel("time (s)")
        ax.set_ylabel("speed (km/h)")
        ax.set_title("T12 top-speed run from 270 km/h")
        out.append(save(f, "t12_top_speed"))
    return out


def t13():
    out = []
    f, ax = fig("t13")
    for name, lab in (("T13_abs_100_0", "ABS on"), ("T13_noabs_100_0", "ABS off (locked)")):
        d = load(name)
        if d is not None:
            ax.plot(d["distance"], d["speed_kmh"], label=lab)
    ax.axvspan(33, 38, color="g", alpha=0.1, label="brief 33-38 m")
    ax.set_xlabel("distance (m)")
    ax.set_ylabel("speed (km/h)")
    ax.set_title("T13 100-0 km/h stop")
    ax.legend()
    out.append(save(f, "t13_stop"))
    return out


def t14():
    out = []
    d = load("T14_skidpad")
    if d is not None:
        f, ax = fig("t14")
        ax.plot(d["t"], d["ay_g"], label="a_y (g)")
        ax.plot(d["t"], d["beta_deg"] / 10.0, label="body slip / 10 (deg)")
        ax.plot(d["t"], d["path_error"], label="path error (m)")
        ax.axhspan(0.85 * 0.85, 1.15, color="g", alpha=0.08, label="brief 0.85-1.0 g +-15 %")
        ax.set_ylim(-0.5, 2.0)
        ax.set_xlabel("time (s)")
        ax.set_title("T14 skidpad R 45.7 m, a_y target rising 0.6 -> 1.15 g")
        ax.legend(loc="upper left")
        out.append(save(f, "t14_skidpad"))
    for name, title in (("T14_slalom_50", "T14 slalom 18 m, +-1 m at 50 km/h"), ("T14_figure8_40", "T14 figure eight 2 x 20 m at 40 km/h")):
        d = load(name)
        if d is None:
            continue
        f, ax = fig(name)
        ax.plot(d["t"], d["path_error"], label="path error (m)")
        ax.plot(d["t"], d["beta_deg"], label="body slip (deg)")
        ax.plot(d["t"], d["roll_deg"], label="roll (deg)")
        ax.set_xlabel("time (s)")
        ax.set_title(title)
        ax.legend()
        out.append(save(f, name.lower()))
    d = load("T14_ramp_jump_60")
    if d is not None:
        f, ax = fig("t14r")
        ax.plot(d["t"], d["com_y"] * 1000.0, label="centre of mass height (mm)")
        ax2 = ax.twinx()
        ax2.plot(d["t"], d["pitch_deg"], "r", label="pitch (deg)")
        ax2.set_ylabel("pitch (deg, nose up +)")
        ax.fill_between(d["t"], 0, d["airborne"] * 800, color="k", alpha=0.08, label="all wheels off the ground")
        ax.set_xlabel("time (s)")
        ax.set_ylabel("height (mm)")
        ax.set_title("T14 ramp jump at 60 km/h (0.45 m, 4 m ramp)")
        ax.legend(loc="upper left")
        out.append(save(f, "t14_ramp_jump"))
    return out


def main():
    made = []
    for fn in (t9, t10, t11, t12, t13, t14):
        made += fn()
    print("\n".join(f"docs/p3b/plots/{m}.png" for m in made))


if __name__ == "__main__":
    main()
