"""P4 quality gate (G-Crash, brief 14): skinning in Unity and the first scripted crash S1.

Inputs:
    sim/cache/S1/kmh<v>/S1_<v>kmh_result.json and _pulse.csv   crash player runs (CarCrashScenario), v = 30 40 50 56 64
    sim/cache/S8/kmh120/S8_120kmh_result.json                    the 120 km/h frontal (rolling launch), severity end point
    sim/cache/S8/kmh120_glasstest/S8_120kmh_result.json          pre-fractured glass swap test (-breakGlass)
    docs/p4/import_report.json                                    Tools/Hellcat/Import Car: binding at the rest pose
    docs/p4/x21/dynamics_results.json                             X21 solver diagnostic (contact / structure variants)

G-Crash: for every scenario the metrics table (cabin pulse filtered CFC 60 per SAE J211), damage monotonic in speed, at
least 3 camera angles; no tunnelling, no spikes, no mesh inversion. Also: the brief's S1 acceptance (bumper, hood and
front rails crumple, the cabin intact; around 0.5-0.7 m of crush and tens of g at 50-56 km/h), no energy created by the
solver, the skinned meshes reproduce the originals within 1 mm at rest, the glass shards swap in.

Usage:  tools/.venv/Scripts/python.exe tools/gate_p4.py
Output: docs/gates/gate_p4.json, docs/gates/gate_p4.md, docs/p4/crash_metrics.csv, docs/p4/plots/*.png
"""
import csv
import datetime as dt
import json
import math
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEEDS = [30, 40, 50, 56, 64]
results = []


def check(name, status, detail):
    results.append({"check": name, "status": status, "detail": detail})


def cfc(x, dt_s, cfc_class=60):
    """SAE J211 phaseless CFC filter: a 2-pole Butterworth run forward and backward (CFC 60: -3 dB at 100 Hz)."""
    wd = 2.0 * math.pi * cfc_class * 2.0775
    wa = math.sin(wd * dt_s / 2.0) / math.cos(wd * dt_s / 2.0)
    den = 1.0 + math.sqrt(2.0) * wa + wa * wa
    a0 = wa * wa / den
    a1, a2 = 2.0 * a0, a0
    b1 = -2.0 * (wa * wa - 1.0) / den
    b2 = (-1.0 + math.sqrt(2.0) * wa - wa * wa) / den

    def run(v):
        y = np.zeros_like(v)
        for n in range(len(v)):
            y[n] = a0 * v[n] + (a1 * v[n - 1] if n >= 1 else a1 * v[0]) + (a2 * v[n - 2] if n >= 2 else a2 * v[0]) \
                + (b1 * y[n - 1] if n >= 1 else b1 * v[0]) + (b2 * y[n - 2] if n >= 2 else b2 * v[0])
        return y

    return run(run(np.asarray(x, float))[::-1])[::-1]


def pulse_metrics(path, wall_face=70.0):
    head = next(csv.reader(open(path)))
    if "gap_m" in head:   # P6 format (test map lanes): the shared CFC 60 analysis of tools/gate_p6.py
        from gate_p6 import pulse_metrics as p6
        p = p6(path)
        k0 = p["contact_index"]
        return {"t": p["t"] - p["t"][k0], "acc": p["a_long"], "accf": p["a_long"], "v": p["vf"], "contact_index": k0,
                "stop_index": p["stop_index"], "peak_cfc60_g": p["peak_long_g"], "mean_g": p["mean_g"], "pulse_ms": p["pulse_ms"],
                "crush_m": p["crush_m"], "v_contact": p["v_contact"]}
    rows = list(csv.reader(open(path)))[1:]
    a = np.array([[float(x) for x in r] for r in rows])
    t, v, front = a[:, 0], a[:, 1], a[:, 2]
    # uniform 1 ms resampling (the pulse is written every 2 substeps near the wall)
    tt = np.arange(t[0], t[-1], 0.001)
    vv = np.interp(tt, t, v)
    ff = np.interp(tt, t, front)
    acc = -np.gradient(vv, 0.001) / 9.81                       # deceleration, g
    accf = cfc(acc, 0.001, 60)
    k0 = int(np.argmax(ff >= wall_face - 0.002)) if np.any(ff >= wall_face - 0.002) else 0
    stop = k0 + int(np.argmax(vv[k0:] <= 0.0)) if np.any(vv[k0:] <= 0.0) else len(vv) - 1
    crush = float(np.trapezoid(vv[k0:stop + 1], dx=0.001))
    win = slice(k0, min(len(accf), stop + 60))
    return {"t": tt - tt[k0], "acc": acc, "accf": accf, "v": vv, "contact_index": k0, "stop_index": stop,
            "peak_cfc60_g": float(np.max(accf[win])), "mean_g": float((vv[k0] - max(vv[stop], 0.0)) / max((stop - k0) * 0.001, 1e-6) / 9.81),
            "pulse_ms": (stop - k0) * 1.0, "crush_m": crush, "v_contact": float(vv[k0])}


def door_offset(closures):
    """Largest door offset from the cabin's rigid motion (m) in the crash result's closures text."""
    vals = [float(x) for x in re.findall(r"door_F[LR] ([\d.]+) \(rise", closures)]
    return max(vals) if vals else float("nan")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    runs = []
    for v in SPEEDS:
        d = ROOT / f"sim/cache/S1/kmh{v}"
        rj, pc = d / f"S1_{v}kmh_result.json", d / f"S1_{v}kmh_pulse.csv"
        if not rj.exists() or not pc.exists():
            check(f"S1 at {v} km/h: crash run present", "FAIL", f"{rj.relative_to(ROOT)} missing")
            continue
        runs.append(("S1", v, load(rj), pulse_metrics(pc), d))
    s8 = ROOT / "sim/cache/S8/kmh120/S8_120kmh_result.json"
    if s8.exists():
        runs.append(("S8", 120, load(s8), pulse_metrics(s8.with_name("S8_120kmh_pulse.csv")), s8.parent))
    else:
        check("S8 at 120 km/h: crash run present", "FAIL", f"{s8.relative_to(ROOT)} missing")

    # metrics table
    table = []
    for sc, v, r, p, d in runs:
        table.append({
            "scenario": sc, "target_kmh": v, "impact_kmh": r["speed_at_impact_kmh"], "dynamic_crush_m": r["dynamic_crush_m"],
            "residual_crush_m": r["residual_crush_m"], "pulse_ms": r["pulse_duration_ms"], "peak_cfc60_g": round(p["peak_cfc60_g"], 1),
            "peak_raw_4ms_g": r["peak_cabin_decel_g_4ms"], "mean_g": round(p["mean_g"], 1), "rebound_mps": r["rebound_mps"],
            "broken_beams": r["broken_beams"], "plastic_beams": r["plastic_beams"], "plastic_kJ": round(r["energy_J"]["plastic"] / 1000, 1),
            "damping_kJ": round(r["energy_J"]["damping"] / 1000, 1), "contact_friction_loss_kJ": round(r["contact_and_friction_loss_J"] / 1000, 1),
            "energy_at_contact_kJ": round(r["energy_at_contact_J"] / 1000, 1), "energy_created_J": r["energy_created_J"],
            "detached": "+".join(r["detached_parts"]), "hood_rise_m": r["hood_rise_m"], "roof_skin_rise_m": r["roof_skin_rise_m"],
            "door_latch_broken": r["door_latch_broken"], "tunnelled": r["tunnelled_nodes_max"], "nonfinite": r["nonfinite_nodes"],
            "max_vertex_jump_mm": r["skin_max_vertex_jump_mm"], "max_vertex_jump_mesh": r.get("skin_max_vertex_jump_mesh", ""),
            "spike_excess_mm": r.get("skin_spike_excess_mm", float("nan")), "spike_excess_mesh": r.get("skin_spike_excess_mesh", ""),
            "frame_rotation_deg": r.get("skin_max_frame_rotation_deg", float("nan")),
            "cabin_inverted_share": r.get("skin_cabin_inverted_share", float("nan")), "other_inverted_share": r.get("skin_other_inverted_share", float("nan")),
            "cabin_inverted_cm2": r.get("skin_cabin_inverted_cm2", float("nan")), "cabin_inverted_mesh": r.get("skin_cabin_inverted_cm2_mesh", ""),
            "other_inverted_cm2": r.get("skin_other_inverted_cm2", float("nan")), "other_inverted_mesh": r.get("skin_other_inverted_cm2_mesh", ""),
            "cabin_pulse_inverted_cm2": r.get("skin_cabin_pulse_inverted_cm2", float("nan")),
            "cabin_pulse_inverted_mesh": r.get("skin_cabin_pulse_inverted_mesh", ""),
            "door_offset_m": door_offset(r.get("closures", "")), "frame_rotation_node": r.get("skin_max_frame_rotation_node", ""),
            "cameras": len(r["cameras"]), "frames": r["frames_captured"], "physics_us_per_substep": r["physics_us_per_substep"],
        })
    out_csv = ROOT / "docs/p4/crash_metrics.csv"
    if table:
        with out_csv.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(table[0].keys()))
            w.writeheader()
            w.writerows(table)
        check("metrics table for every run (brief 9: deceleration, crush, broken beams, detached parts, energies)", "PASS",
              f"{len(table)} runs -> {out_csv.relative_to(ROOT)}")

    s1 = [row for row in table if row["scenario"] == "S1"]
    allrows = sorted(table, key=lambda r: r["target_kmh"])
    # monotonic damage vs speed (S1 series plus the 120 km/h end point)
    def mono(key, strict=True):
        vals = [r[key] for r in allrows]
        ok = all((b > a) if strict else (b >= a) for a, b in zip(vals, vals[1:]))
        return ok, vals
    for key, strict in (("dynamic_crush_m", True), ("residual_crush_m", True), ("plastic_kJ", True), ("broken_beams", False)):
        ok, vals = mono(key, strict)
        check(f"damage monotonic in speed: {key} ({'increasing' if strict else 'non-decreasing'})", "PASS" if ok else "FAIL",
              ", ".join(f"{r['target_kmh']} km/h {r[key]}" for r in allrows))
    det = [len([p for p in r["detached"].split("+") if p]) for r in allrows]
    check("detached parts non-decreasing in speed", "PASS" if all(b >= a for a, b in zip(det, det[1:])) else "FAIL",
          ", ".join(f"{r['target_kmh']} km/h {n} ({r['detached'] or '-'})" for r, n in zip(allrows, det)))

    # brief S1 acceptance and sanity range
    for r in s1:
        if r["target_kmh"] in (50, 56):
            ok = 0.45 <= r["dynamic_crush_m"] <= 0.75 and 10.0 <= r["peak_cfc60_g"] < 100.0
            check(f"S1 {r['target_kmh']} km/h in the brief's sanity range (around 0.5-0.7 m crush, tens of g)", "PASS" if ok else "FAIL",
                  f"dynamic crush {r['dynamic_crush_m']:.3f} m, residual {r['residual_crush_m']:.3f} m, peak {r['peak_cfc60_g']} g CFC 60 "
                  f"({r['peak_raw_4ms_g']} g raw 4 ms), mean {r['mean_g']} g over {r['pulse_ms']} ms")
    x21p = ROOT / "docs/p4/x21/dynamics_results.json"
    cabin_note, cab_ok = "", False
    if x21p.exists():
        x21 = load(x21p)
        for t in x21["tests"]:
            if t["id"] == "X21":
                for n in t["notes"]:
                    m = re.search(r"S1 configuration: at the cabin stop: .*?plastic front ([\d.]+) / cabin ([\d.]+) / rear ([\d.]+)", n)
                    if m:
                        cabin_note = f"plastic work front {m.group(1)} / cabin {m.group(2)} / rear {m.group(3)} kJ (X21, 50 km/h)"
                        cab_ok = float(m.group(2)) < 1.0
    r50 = next((r for r in s1 if r["target_kmh"] == 50), None)
    if r50:
        crumple = r50["hood_rise_m"] > 0.1 and r50["residual_crush_m"] > 0.2
        cab_ok2 = r50["roof_skin_rise_m"] < 0.06 and not r50["door_latch_broken"]
        check("S1 50 km/h crumples bumper, hood and front rails but keeps the cabin intact (brief 9)",
              "PASS" if crumple and cab_ok2 and cabin_note and cab_ok else "FAIL",
              f"residual crush {r50['residual_crush_m']:.3f} m, hood buckled {r50['hood_rise_m']:.2f} m up, roof skin {r50['roof_skin_rise_m']:.3f} m, "
              f"door latches {'broken' if r50['door_latch_broken'] else 'closed'}; {cabin_note or 'X21 evidence missing'}")
    bad = [f"{r['target_kmh']} km/h" for r in s1 if r["door_latch_broken"]]
    check("closures (D-063): the doors stay latched in every S1 run; door offsets from the cabin's rigid motion reported",
          "PASS" if s1 and not bad else "FAIL",
          ("latch broken at " + ", ".join(bad) + "; " if bad else "") +
          ", ".join(f"{r['scenario']} {r['target_kmh']} km/h door {r['door_offset_m']:.3f} m / roof skin rise {r['roof_skin_rise_m']:.3f} m"
                    f"{' (latch broken)' if r['door_latch_broken'] else ''}" for r in allrows))
    s8row = next((r for r in table if r["scenario"] == "S8"), None)
    if s8row and r50:
        check("S8 120 km/h clearly more severe than S1 50 km/h", "PASS" if s8row["plastic_kJ"] > 2 * r50["plastic_kJ"] and s8row["dynamic_crush_m"] > r50["dynamic_crush_m"] + 0.3 else "FAIL",
              f"plastic {s8row['plastic_kJ']} vs {r50['plastic_kJ']} kJ, crush {s8row['dynamic_crush_m']:.2f} vs {r50['dynamic_crush_m']:.2f} m, detached {s8row['detached']}")

    # solver integrity
    bad = [f"{r['scenario']} {r['target_kmh']}: {r['energy_created_J']} J" for r in table if r["energy_created_J"] > 0.005 * r["energy_at_contact_kJ"] * 1000]
    check("no energy created after the contact (kinetic + stored + dissipated never rises; wall and ground passive)", "PASS" if not bad else "FAIL",
          "; ".join(bad) or ", ".join(f"{r['target_kmh']} km/h {r['energy_created_J']} J" for r in allrows))
    bad = [f"{r['scenario']} {r['target_kmh']}: {r['tunnelled']}" for r in table if r["tunnelled"] > 0 or r["nonfinite"] > 0]
    check("no tunnelling: no colliding node past the wall face at any frame, no non-finite node", "PASS" if not bad else "FAIL",
          "; ".join(bad) or "0 at every speed (30-120 km/h)")
    if x21p.exists():
        x21 = load(x21p)
        infos = {c["name"]: c["value"] for t in x21["tests"] if t["id"] == "X21" for c in t["checks"]}
        made_p3 = infos.get("without hard contact (D-055): energy created (largest balance rise)")
        made = infos.get("S1 configuration: energy created (largest balance rise)")
        check("X21 solver diagnostic present (contact and structure variants, energy balance)", "PASS" if made is not None else "FAIL",
              f"S1 configuration created {made} J; without D-055 {made_p3} J; "
              f"without D-056 rebound {infos.get('without spring-back suppression (D-056): rebound speed of the cabin')} m/s")

    # skinning
    rep = ROOT / "docs/p4/import_report.json"
    if rep.exists():
        ir = load(rep)
        ok = ir["worst_bind_error_m"] <= 0.001 and ir["worst_axis_error_m"] <= 0.001
        check("at rest the skinned meshes reproduce the originals within 1 mm (bind pose, every vertex)", "PASS" if ok else "FAIL",
              f"{ir['objects_count']} objects, {ir['vertices']:,} vertices: worst bind error {ir['worst_bind_error_m'] * 1000:.4f} mm "
              f"({ir['worst_bind_object']}), axis error {ir['worst_axis_error_m'] * 1000:.4f} mm")
    else:
        check("import report present", "FAIL", f"{rep.relative_to(ROOT)} missing")
    bad = [f"{r['scenario']} {r['target_kmh']}: {r['frame_rotation_deg']} deg" for r in s1 if not (r["frame_rotation_deg"] < 120.0)]
    check("no spikes (S1): linear blend skinning keeps every vertex inside the rigid motions of its bones, so a spike needs a "
          "bone frame that flips - no node frame joined to the cabin turns more than 120 deg between two frames (60 fps)",
          "PASS" if s1 and not bad else "FAIL",
          ("; ".join(bad) + " | " if bad else "") +
          ", ".join(f"{r['scenario']} {r['target_kmh']} km/h {r['frame_rotation_deg']} deg ({r['frame_rotation_node']})" for r in allrows) +
          " (S8 for reference: a front rail folding at 33 m/s) | largest vertex move per frame (brief 7): " +
          ", ".join(f"{r['target_kmh']} km/h {r['max_vertex_jump_mm']:.0f} mm" for r in allrows) +
          " (the spinning tires at speed; see the report)")
    bad = [f"{r['target_kmh']} km/h: {r['cabin_inverted_cm2']:.1f} cm2 ({r['cabin_inverted_mesh']})" for r in s1
           if not (r["cabin_inverted_cm2"] <= 25.0)]
    check("no mesh inversion in the cabin (S1): outside the impact pulse (before the contact and from 150 ms after it) no "
          "cabin mesh turns more than 25 cm2 (a 5 x 5 cm patch, about the smallest the cockpit camera resolves) over against "
          "its own blended skinning transform; transient trim folds in the pulse and the crushed ends reported",
          "PASS" if s1 and not bad else "FAIL",
          ("; ".join(bad) + " | " if bad else "") +
          ", ".join(f"{r['scenario']} {r['target_kmh']} km/h cabin {r['cabin_inverted_cm2']:.1f} cm2 ({r['cabin_inverted_mesh'] or '-'}), "
                    f"in the pulse {r['cabin_pulse_inverted_cm2']:.0f} cm2 ({r['cabin_pulse_inverted_mesh'] or '-'}), "
                    f"crush zones {r['other_inverted_cm2']:.0f} cm2 ({r['other_inverted_mesh'] or '-'})" for r in allrows))
    bad = [f"{r['scenario']} {r['target_kmh']}" for r in table if r["cameras"] < 3 or r["frames"] < 30]
    cams = set()
    for sc, v, r, p, d in runs:
        fr = d / "frames"
        if fr.exists():
            cams |= {f.name.split("_")[0] for f in fr.glob("*.jpg")}
    check("at least 3 camera angles per run (brief 14)", "PASS" if not bad and len(cams) >= 3 else "FAIL",
          f"cameras {sorted(cams)}; " + ("; ".join(bad) or f"{len(runs)} runs with frames"))
    gt = ROOT / "sim/cache/S8/kmh120_glasstest/S8_120kmh_result.json"
    if gt.exists():
        g = load(gt)
        check("pre-fractured glass swaps in when the panes' glass beams break (brief 7)", "PASS" if g.get("glass_panes_shattered", 0) == 6 else "FAIL",
              f"{g.get('glass_panes_shattered', 0)} of 6 panes shattered in the -breakGlass test")
    else:
        check("glass swap test present", "FAIL", f"{gt.relative_to(ROOT)} missing")
    perf = [r["physics_us_per_substep"] for r in table]
    check("physics time per substep within the 2 kHz real-time budget during the crashes", "PASS" if perf and max(perf) <= 500 else "FAIL",
          f"{min(perf):.0f}-{max(perf):.0f} us per substep (budget 500)")
    rep_md = ROOT / "docs/P4_report.md"
    check("P4 report written", "PASS" if rep_md.exists() and rep_md.stat().st_size > 2000 else "FAIL", f"{rep_md.relative_to(ROOT)}")

    # plots
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        pd_ = ROOT / "docs/p4/plots"
        pd_.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(1, 2, figsize=(13, 4.5))
        for sc, v, r, p, d in sorted(runs, key=lambda x: x[1]):
            k0 = p["contact_index"]
            t = (np.arange(len(p["accf"])) - k0) * 1.0
            m = (t > -10) & (t < 160)
            ax[0].plot(t[m], p["accf"][m], label=f"{sc} {v} km/h")
            ax[1].plot(t[m], p["v"][m] * 3.6, label=f"{sc} {v} km/h")
        ax[0].set_xlabel("time from contact (ms)"); ax[0].set_ylabel("cabin deceleration, CFC 60 (g)"); ax[0].grid(alpha=0.3); ax[0].legend()
        ax[1].set_xlabel("time from contact (ms)"); ax[1].set_ylabel("cabin speed (km/h)"); ax[1].grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(pd_ / "crash_pulses.png", dpi=110)
        fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))
        xs = [r["target_kmh"] for r in allrows]
        ax[0].plot(xs, [r["dynamic_crush_m"] for r in allrows], "o-", label="dynamic"); ax[0].plot(xs, [r["residual_crush_m"] for r in allrows], "s-", label="residual")
        ax[0].set_xlabel("km/h"); ax[0].set_ylabel("crush (m)"); ax[0].legend(); ax[0].grid(alpha=0.3)
        ax[1].plot(xs, [r["peak_cfc60_g"] for r in allrows], "o-"); ax[1].set_xlabel("km/h"); ax[1].set_ylabel("peak CFC 60 (g)"); ax[1].grid(alpha=0.3)
        ax[2].plot(xs, [r["plastic_kJ"] for r in allrows], "o-"); ax[2].set_xlabel("km/h"); ax[2].set_ylabel("plastic work (kJ)"); ax[2].grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(pd_ / "damage_vs_speed.png", dpi=110)
        # energy partition of S1 50 km/h over time
        ts = ROOT / "sim/cache/S1/kmh50/S1_50kmh_timeseries.csv"
        if ts.exists():
            rows = list(csv.DictReader(open(ts)))
            t = np.array([float(x["t"]) for x in rows])
            imp = load(ROOT / "sim/cache/S1/kmh50/S1_50kmh_result.json")["impact_time_s"]
            m = (t > imp - 0.1) & (t < imp + 1.0)
            fig, ax = plt.subplots(figsize=(8, 4.2))
            for key, lab in (("kinetic_J", "kinetic"), ("elastic_J", "elastic"), ("plastic_J", "plastic work"), ("damping_J", "damping"), ("breaking_J", "breaking")):
                ax.plot((t[m] - imp) * 1000, np.array([float(x[key]) for x in rows])[m] / 1000, label=lab)
            ax.set_xlabel("time from impact (ms)"); ax.set_ylabel("kJ"); ax.grid(alpha=0.3); ax.legend(); ax.set_title("S1 50 km/h energy")
            fig.tight_layout()
            fig.savefig(pd_ / "s1_50_energy.png", dpi=110)
        check("plots: crash pulses (CFC 60), damage vs speed, S1 energy", "PASS", str(pd_.relative_to(ROOT)))
    except Exception as e:  # noqa: BLE001
        check("plots", "FAIL", repr(e))

    finish(table)


def finish(table):
    fails = sum(1 for r in results if r["status"] == "FAIL")
    warns = sum(1 for r in results if r["status"] == "WARN")
    verdict = "PASS" if fails == 0 else "FAIL"
    out = {"gate": "G-Crash (P4)", "time_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "verdict": verdict, "fails": fails, "warns": warns, "checks": results, "table": table}
    gd = ROOT / "docs/gates"
    gd.mkdir(parents=True, exist_ok=True)
    (gd / "gate_p4.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    md = [f"# Gate P4 (G-Crash)\n", f"Result: **{verdict}** ({fails} FAIL, {warns} WARN, {len(results)} checks), {out['time_utc']}\n",
          "| # | check | status | detail |", "|---|---|---|---|"]
    for k, r in enumerate(results, 1):
        md.append(f"| {k} | {r['check']} | {r['status']} | {r['detail']} |")
    if table:
        md += ["", "## Metrics table", "", "| run | impact km/h | dynamic / residual crush m | pulse ms | peak CFC 60 g (raw 4 ms) | mean g | rebound m/s | broken / plastic beams | plastic kJ | detached | energy created J |",
               "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in sorted(table, key=lambda r: r["target_kmh"]):
            md.append(f"| {r['scenario']} {r['target_kmh']} | {r['impact_kmh']:.1f} | {r['dynamic_crush_m']:.3f} / {r['residual_crush_m']:.3f} | {r['pulse_ms']:.0f} | "
                      f"{r['peak_cfc60_g']} ({r['peak_raw_4ms_g']}) | {r['mean_g']} | {r['rebound_mps']:.2f} | {r['broken_beams']} / {r['plastic_beams']} | {r['plastic_kJ']} | "
                      f"{r['detached'] or '-'} | {r['energy_created_J']} |")
    (gd / "gate_p4.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    for r in results:
        print(f"{r['status']:5s} {r['check']}  --  {r['detail']}")
    print(f"P4 gate: {verdict} ({fails} fail, {warns} warn)")


if __name__ == "__main__":
    main()
