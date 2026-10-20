"""Suspension design from first principles (brief 4.7): springs, dampers, preloads and anti-roll bars of a
skeleton, derived from ride-frequency, damping-ratio and roll-gradient targets on the actual geometry.

Kinematics: each knuckle is a rigid body held by five two-force links (front SLA: two lower-arm members,
two upper-arm members, tie rod; rear: the five links). Their first-order constraints leave one degree of
freedom, the wheel travel; its null-space motion gives every pick-up point's velocity per metre of wheel
travel - spring and damper motion ratios, camber gain, bump steer, the roll centre (the contact-patch path
in the front view) and the anti-roll-bar lever rotation through its drop link.

Design (per axle):  k_wheel = m_sprung (2 pi f)^2,  k_spring = k_wheel / MR^2,  preload = m_sprung g / MR,
                    c_wheel = 2 zeta sqrt(k_wheel m_sprung),  c_damper = c_wheel / MR^2,
                    roll stiffness K = k_wheel t^2 / 2 (springs) + K_t g^2 t^2 (bar, g = lever rad per m of
                    wheel travel), total from the roll-gradient target, split by the front share.

Usage: tools/.venv/Scripts/python.exe tools/skeleton/suspension_design.py [vehicle] [--apply]
Writes docs/p2_suspension.json; --apply writes the derived values into params.json (other lines untouched).
"""
import argparse
import json
import math
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
G = 9.81
UP = np.array([0.0, 1.0, 0.0])          # Unity frame: x right, y up, z forward

TARGETS = {
    "ride_hz": {"F": 1.40, "R": 1.55},   # brief: 1.2-1.5 front, 1.4-1.7 rear (wheel rate, no tire)
    "zeta_compression": 0.28,            # brief: 0.25-0.4 rebound, slightly less in compression; P3 (D-036): the
    "zeta_rebound": 0.38,                # tire in series and the blow-off leave ~0.6 of the mean in the heave mode
    "fast_ratio": 0.40,                  # damping above the velocity split / below it (blow-off)
    "roll_gradient_deg_per_g": 2.3,      # D-025
    "front_roll_share": 0.60,            # D-025: TLLTD a little above the 57 % front weight -> mild understeer
    "tire_rate_assumed": 292900.0,       # N/m, 305/35 ZR20 at 241 kPa: measured by tools/skeleton/tire_rate.py (P3)
    "rear_roll_centre_fallback": 0.12,   # m, used only if the rear kinematics give no roll centre
}


def strip_comments(text):
    out, in_str, i = [], False, 0
    while i < len(text):
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < len(text):
                out.append(text[i + 1])
                i += 1
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
            out.append(ch)
        elif text.startswith("//", i):
            while i < len(text) and text[i] != "\n":
                i += 1
            out.append("\n")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


class Car:
    def __init__(self, vehicle):
        d = ROOT / "sim/vehicle" / vehicle
        self.params_path = d / "params.json"
        self.g = json.loads((d / "geometry.json").read_text(encoding="utf-8"))
        self.p = json.loads(strip_comments(self.params_path.read_text(encoding="utf-8")))
        self.mats = {m["name"]: m for m in self.p["materials"]}
        self.nodes = self.g["nodes"]
        self.idx = {n["name"]: i for i, n in enumerate(self.nodes)}
        self.P = np.array([n["p"] for n in self.nodes], float)
        self.m = np.array([n["m"] for n in self.nodes], float)
        self.beams = self.g["beams"]

    def pos(self, name):
        return self.P[self.idx[name]]

    def partner(self, node, mat):
        i = self.idx[node]
        for b in self.beams:
            if b["mat"] == mat and i in (b["a"], b["b"]):
                return b["b"] if b["a"] == i else b["a"]
        raise KeyError(f"no {mat} beam at {node}")


def knuckle_motion(links, centre):
    """links: [(fixed point q, knuckle point p)]. Returns v(x) (velocity per unit upward wheel-centre travel)."""
    rows = []
    for q, p in links:
        u = (p - q) / np.linalg.norm(p - q)
        # v(p) = v0 + w x (p - c);  u . v0 + u . (w x r) = u . v0 + (r x u) . w
        rows.append(np.concatenate([u, np.cross(p - centre, u)]))
    A = np.array(rows)
    _, s, vt = np.linalg.svd(A)
    x = vt[-1]
    v0, w = x[:3], x[3:]
    scale = 1.0 / v0[1]               # wheel centre moves +1 m upward
    v0, w = v0 * scale, w * scale

    def vel(p):
        return v0 + np.cross(w, p - centre)

    return vel, w, float(s[-2] / s[0])  # conditioning of the 1-DOF solution


def corner(car, name, front):
    wh = next(w for w in car.g["wheels"] if w["name"] == name)
    hub = (car.P[wh["axleInner"]] + car.P[wh["axleOuter"]]) / 2
    if front:
        kn = {k: car.pos(f"{name}_{k}") for k in ("lbj", "ubj", "tre")}
        side = name[1]
        rack = car.pos(f"rack_{side}")
        links = [(car.pos(f"{name}_lca_f"), kn["lbj"]), (car.pos(f"{name}_lca_r"), kn["lbj"]),
                 (car.pos(f"{name}_uca_f"), kn["ubj"]), (car.pos(f"{name}_uca_r"), kn["ubj"]), (rack, kn["tre"])]
        spring_lo = f"{name}_lbj"
        smat, dmat = "spring_f", "damper_f"
    else:
        kp = {k: car.pos(f"{name}_{k}") for k in ("klf", "klr", "kup")}
        outer = [kp["klf"], kp["klr"], kp["kup"], kp["kup"], kp["klf"]]
        links = [(car.pos(f"{name}_link{n}"), o) for n, o in enumerate(outer)]
        spring_lo = f"{name}_klr"
        smat, dmat = "spring_r", "damper_r"
    vel, w, cond = knuckle_motion(links, hub)
    lo = car.pos(spring_lo)
    top = car.P[car.partner(spring_lo, smat)]
    s_hat = (top - lo) / np.linalg.norm(top - lo)
    mr = float(np.dot(vel(lo), s_hat))                       # spring compression per m of wheel travel
    # contact patch: on the ground under the wheel plane (mean x of the tread nodes; the axle nodes sit
    # 25 mm inboard of it); roll centre from its path in the front view
    sx = np.sign(hub[0])
    cp = np.array([car.P[wh["tread"], 0].mean(), 0.0, hub[2]])
    vcp = vel(cp)
    rc = float(cp[0] * vcp[0] / vcp[1]) if abs(vcp[1]) > 1e-9 else None
    camber_gain = float(np.degrees(w[2]) * -sx)              # deg per m of bump, negative = more negative camber
    bump_steer = float(np.degrees(w[1]) * sx)                # deg per m of bump, positive = toe-out
    # anti-roll bar lever: tip rotates about the bar axis; drop link to the pick node
    tb = next(t for t in car.g["torsionBars"] if t["mat"] == ("arb_front" if front else "arb_rear"))
    tip_i = tb["n"][0] if sx > 0 else tb["n"][3]
    ax_a, ax_b = car.P[tb["n"][1]], car.P[tb["n"][2]]
    b_hat = (ax_b - ax_a) / np.linalg.norm(ax_b - ax_a)
    tip = car.P[tip_i]
    pick_i = next(b["b"] if b["a"] == tip_i else b["a"] for b in car.beams
                  if b["mat"] == "arb_link" and tip_i in (b["a"], b["b"]))
    pick = car.P[pick_i]
    if front:
        # pick node on the lower arm: arm rotation about its pivot axis, rate from the ball joint velocity
        a0, a1 = car.pos(f"{name}_lca_f"), car.pos(f"{name}_lca_r")
        a_hat = (a1 - a0) / np.linalg.norm(a1 - a0)
        t_l = np.cross(a_hat, kn["lbj"] - a0)
        omega_arm = float(np.dot(vel(kn["lbj"]), t_l) / np.dot(t_l, t_l))
        v_pick = omega_arm * np.cross(a_hat, pick - a0)
    else:
        v_pick = vel(pick)
    l_hat = (pick - tip) / np.linalg.norm(pick - tip)
    t_tip = np.cross(b_hat, tip - ax_a)
    g_lever = float(np.dot(v_pick, l_hat) / np.dot(t_tip, l_hat))     # lever rad per m of wheel travel
    part_nodes = next(p["nodes"] for p in car.g["parts"] if p["name"] == f"wheel_{name}")
    return {"hub": hub, "cp": cp, "mr": mr, "spring_len": float(np.linalg.norm(top - lo)), "rc": rc, "camber_gain": camber_gain,
            "bump_steer": bump_steer, "g_lever": abs(g_lever), "cond": cond,
            "unsprung": float(car.m[part_nodes].sum()), "spring_incl_deg": float(np.degrees(np.arccos(abs(s_hat[1]))))}


def design(vehicle):
    car = Car(vehicle)
    M = float(car.m.sum())
    com = (car.m[:, None] * car.P).sum(0) / M
    C = {n: corner(car, n, n[0] == "F") for n in ("FL", "FR", "RL", "RR")}
    zf = np.mean([C[n]["hub"][2] for n in ("FL", "FR")])
    zr = np.mean([C[n]["hub"][2] for n in ("RL", "RR")])
    front = (com[2] - zr) / (zf - zr)
    out = {"mass": M, "com": com.round(4).tolist(), "front_share": front, "axles": {}}
    loads = {}
    for ax, share in (("F", front), ("R", 1 - front)):
        xl, xr = C[ax + "L"]["hub"][0], C[ax + "R"]["hub"][0]
        left = (xr - com[0]) / (xr - xl)
        loads[ax + "L"], loads[ax + "R"] = M * share * left, M * share * (1 - left)
    ms_tot, ms_y, axles = 0.0, 0.0, {}
    for ax in ("F", "R"):
        L, R = C[ax + "L"], C[ax + "R"]
        corner_load = (loads[ax + "L"] + loads[ax + "R"]) / 2
        unsprung = (L["unsprung"] + R["unsprung"]) / 2
        ms = corner_load - unsprung
        mr = (L["mr"] + R["mr"]) / 2
        track = R["cp"][0] - L["cp"][0]
        f = TARGETS["ride_hz"][ax]
        kw = ms * (2 * math.pi * f) ** 2
        k = kw / mr ** 2
        pre = ms * G / mr
        root = math.sqrt(kw * ms)
        cw_c, cw_r = 2 * TARGETS["zeta_compression"] * root, 2 * TARGETS["zeta_rebound"] * root
        kt = TARGETS["tire_rate_assumed"]
        f_tire = math.sqrt(kw * kt / (kw + kt) / ms) / (2 * math.pi)
        axles[ax] = {"corner_load_kg": corner_load, "unsprung_kg": unsprung, "sprung_kg": ms, "motion_ratio": mr,
                     "spring_inclination_deg": (L["spring_incl_deg"] + R["spring_incl_deg"]) / 2,
                     "spring_length_m": (L["spring_len"] + R["spring_len"]) / 2, "track_m": track,
                     "ride_hz": f, "wheel_rate": kw, "spring_rate": k, "preload_N": pre,
                     "static_compression_m": pre / k, "ride_hz_with_tire": f_tire,
                     "damper_compression": cw_c / mr ** 2, "damper_rebound": cw_r / mr ** 2,
                     "roll_centre_m": None if L["rc"] is None else (L["rc"] + R["rc"]) / 2,
                     "camber_gain_deg_per_m": (L["camber_gain"] + R["camber_gain"]) / 2,
                     "bump_steer_deg_per_m": (L["bump_steer"] + R["bump_steer"]) / 2,
                     "arb_lever_rad_per_m": (L["g_lever"] + R["g_lever"]) / 2,
                     "kinematics_conditioning": min(L["cond"], R["cond"]),
                     "roll_stiffness_springs": kw * track ** 2 / 2}
        ms_tot += 2 * ms
        ms_y += 2 * ms * com[1] - 0.0
    # sprung centre of mass height: total minus the unsprung masses at the hubs
    mu = {n: C[n]["unsprung"] for n in C}
    hs = (M * com[1] - sum(mu[n] * C[n]["hub"][1] for n in C)) / (M - sum(mu.values()))
    rcf = axles["F"]["roll_centre_m"]
    rcr = axles["R"]["roll_centre_m"] if axles["R"]["roll_centre_m"] is not None else TARGETS["rear_roll_centre_fallback"]
    zs = com[2]
    h_ra = rcr + (rcf - rcr) * (zs - zr) / (zf - zr)
    arm = hs - h_ra
    k_total = (M - sum(mu.values())) * G * arm / math.radians(TARGETS["roll_gradient_deg_per_g"])
    for ax, share in (("F", TARGETS["front_roll_share"]), ("R", 1 - TARGETS["front_roll_share"])):
        a = axles[ax]
        need = share * k_total - a["roll_stiffness_springs"]
        a["roll_stiffness_target"] = share * k_total
        a["arb_roll_stiffness"] = max(need, 0.0)
        a["arb_torsion_Nm_per_rad"] = max(need, 0.0) / (a["arb_lever_rad_per_m"] ** 2 * a["track_m"] ** 2)
    out.update({"axles": axles, "sprung_mass_kg": M - sum(mu.values()), "sprung_com_height_m": hs,
                "roll_axis_height_at_com_m": h_ra, "roll_moment_arm_m": arm, "roll_stiffness_total": k_total,
                "targets": TARGETS})
    # what the current params give
    cur = {}
    for ax, sm, dm, am in (("F", "spring_f", "damper_f", "arb_front"), ("R", "spring_r", "damper_r", "arb_rear")):
        a = axles[ax]
        kw = car.mats[sm]["spring"] * a["motion_ratio"] ** 2
        cur[ax] = {"ride_hz": math.sqrt(kw / a["sprung_kg"]) / (2 * math.pi),
                   "zeta_compression": car.mats[dm]["damp"] * a["motion_ratio"] ** 2 / (2 * math.sqrt(kw * a["sprung_kg"])),
                   "roll_stiffness": kw * a["track_m"] ** 2 / 2 + car.mats[am]["spring"] * a["arb_lever_rad_per_m"] ** 2 * a["track_m"] ** 2}
    k_cur = cur["F"]["roll_stiffness"] + cur["R"]["roll_stiffness"]
    out["current_params"] = {"axles": cur, "roll_gradient_deg_per_g": math.degrees(out["sprung_mass_kg"] * G * arm / k_cur),
                             "front_roll_share": cur["F"]["roll_stiffness"] / k_cur}
    return car, out


def material_line(name, fields):
    body = ", ".join(f'"{k}": {v}' for k, v in fields.items())
    return f'{{ "name": "{name}",'.ljust(27) + f"{body} }}"


def apply(car, out):
    text = car.params_path.read_text(encoding="utf-8")
    t = TARGETS
    new = {}
    for ax, sm, dm, am in (("F", "spring_f", "damper_f", "arb_front"), ("R", "spring_r", "damper_r", "arb_rear")):
        a = out["axles"][ax]
        new[sm] = {"spring": round(a["spring_rate"], -1), "damp": 0, "preload": round(a["preload_N"])}
        old = car.mats[dm]
        new[dm] = {"spring": 0, "damp": round(a["damper_compression"], -1), "dampRebound": round(a["damper_rebound"], -1),
                   "velSplit": old.get("velSplit", 0.2), "dampFast": round(a["damper_compression"] * t["fast_ratio"], -1),
                   "velSplitRebound": old.get("velSplitRebound", 0.25),
                   "dampReboundFast": round(a["damper_rebound"] * t["fast_ratio"], -1)}
        new[am] = {"spring": round(a["arb_torsion_Nm_per_rad"], -1), "damp": 0}
    for name, fields in new.items():
        fields = {k: (int(v) if isinstance(v, float) and v == int(v) else v) for k, v in fields.items()}
        pat = re.compile(r'\{\s*"name":\s*"' + re.escape(name) + r'"[^}]*\}')
        if not pat.search(text):
            raise KeyError(name)
        text = pat.sub(material_line(name, fields), text, count=1)
    car.params_path.write_text(text, encoding="utf-8")
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vehicle", nargs="?", default="hellcat")
    ap.add_argument("--apply", action="store_true")
    ns = ap.parse_args()
    car, out = design(ns.vehicle)
    (ROOT / "docs/p2_suspension.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    for ax, a in out["axles"].items():
        print(f"[{ax}] corner {a['corner_load_kg']:.0f} kg, unsprung {a['unsprung_kg']:.1f}, sprung {a['sprung_kg']:.0f}; "
              f"MR {a['motion_ratio']:.3f} (spring {a['spring_inclination_deg']:.1f} deg from vertical); track "
              f"{a['track_m']:.3f}")
        print(f"     ride {a['ride_hz']} Hz -> wheel rate {a['wheel_rate']:.0f} N/m, spring {a['spring_rate']:.0f} N/m, "
              f"preload {a['preload_N']:.0f} N (static compression {a['static_compression_m'] * 1000:.0f} mm); with "
              f"tire {a['ride_hz_with_tire']:.2f} Hz")
        print(f"     damper {a['damper_compression']:.0f} / {a['damper_rebound']:.0f} N s/m; roll centre "
              f"{a['roll_centre_m']:.3f} m; camber gain {a['camber_gain_deg_per_m']:.1f} deg/m; bump steer "
              f"{a['bump_steer_deg_per_m']:.2f} deg/m; kinematics conditioning {a['kinematics_conditioning']:.3f}")
        print(f"     ARB lever {a['arb_lever_rad_per_m']:.2f} rad/m; springs {a['roll_stiffness_springs']:.0f} N m/rad, "
              f"target {a['roll_stiffness_target']:.0f}, bar {a['arb_roll_stiffness']:.0f} -> torsion "
              f"{a['arb_torsion_Nm_per_rad']:.0f} N m/rad")
    print(f"sprung mass {out['sprung_mass_kg']:.0f} kg, sprung CoM {out['sprung_com_height_m']:.3f} m, roll axis at CoM "
          f"{out['roll_axis_height_at_com_m']:.3f} m, arm {out['roll_moment_arm_m']:.3f} m, total roll stiffness "
          f"{out['roll_stiffness_total']:.0f} N m/rad")
    c = out["current_params"]
    print("current params: " + ", ".join(f"{ax} {v['ride_hz']:.2f} Hz zeta_c {v['zeta_compression']:.2f}"
                                          for ax, v in c["axles"].items())
          + f"; roll gradient {c['roll_gradient_deg_per_g']:.2f} deg/g, front roll share {c['front_roll_share']:.2f}")
    if ns.apply:
        new = apply(car, out)
        print("applied: " + json.dumps(new))


if __name__ == "__main__":
    main()
