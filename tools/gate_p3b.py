"""P3b quality gate (G-Dynamics): vehicle dynamics of the Hellcat - pressurized tires, suspension, steering, powertrain,
brakes; validation tests 9-14 (brief section 10) and the driving targets of brief section 4.13.

Inputs:
    docs/p3b/validation/dynamics_results.json   Unity dynamics suite (Hellcat.EditorTools.Validation.ValidationTasks
                                                .RunDynamics -valTests T9,T10,T11,T12,T13,T14); --run executes it first
    docs/p3/validation/validation_results.json  the P3 suite (T1-T8, E1, D1) re-run after the P3b solver changes
                                                (--run executes it too)
    sim/vehicle/<vehicle>/geometry.json, params.json and Unity/HellcatSandbox/Assets/Sim/**/*.cs
                                                both result files must be newer than all of them (no stale evidence)
    docs/p2_stability.json                      tools/skeleton/stability.py --json (exact S of the current skeleton)
    docs/dynamics_report.md, docs/p3b/plots/    the report (tools/p3b/make_dynamics_report.py) and its plots

G-Dynamics (brief 14): tests 9-14 pass; the target table of 4.13 is filled with measured values (each target within the
brief's +-15 % tolerance).

Usage:  tools/.venv/Scripts/python.exe tools/gate_p3b.py [vehicle] [--run]
Output: docs/gates/gate_p3b.json, docs/gates/gate_p3b.md and docs/p3b/targets_4_13.json (the filled table)
"""
import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ["T9", "T10", "T11", "T12", "T13", "T14"]
P3_REQUIRED = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "E1", "D1"]
results = []


def check(name, status, detail):
    results.append({"check": name, "status": status, "detail": detail})


def run(cmd_args, log):
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
           f"& tools\\unity\\run_unity_batch.ps1 -LogFile {log} -ProjectPath Unity\\HellcatSandbox -UnityArgs @({cmd_args})"]
    return subprocess.run(cmd, cwd=ROOT).returncode


def find(test, fragment):
    if test is None:
        return None
    for c in test["checks"]:
        if fragment in c["name"]:
            return c
    return None


def stamp(vr):
    return dt.datetime.strptime(vr["time_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def newest_input(vehicle):
    vd = ROOT / "sim/vehicle" / vehicle
    inputs = [vd / "geometry.json", vd / "params.json"] + list((ROOT / "Unity/HellcatSandbox/Assets/Sim").rglob("*.cs"))
    newest = max(inputs, key=lambda q: q.stat().st_mtime)
    return newest, dt.datetime.fromtimestamp(newest.stat().st_mtime, dt.timezone.utc).replace(microsecond=0)


def targets(tests):
    """The table of brief 4.13: target, tolerance band, measured value, pass."""
    t9, t10, t12, t13, t14 = (tests.get(k) for k in ("T9", "T10", "T12", "T13", "T14"))
    rows = []

    def row(name, target, lo, hi, c, unit, note=""):
        v = c["value"] if c else None
        ok = v is not None and lo <= v <= hi
        rows.append({"target": name, "brief": target, "band": [lo, hi], "measured": v, "unit": unit, "pass": ok, "note": note})

    roll = find(t12, "0-100 km/h best, timed from the throttle")
    row("0-100 km/h", "3.5-4.0 s", 3.5 * 0.85, 4.0 * 1.15, find(t12, "0-100 km/h best, 1-ft rollout"), "s",
        f"1-ft rollout like the published figures; {roll['value']:.2f} s from the throttle application" if roll else "")
    row("top speed", "290-320 km/h (stock ~314)", 290 * 0.85, 320 * 1.15, find(t12, "top speed (drag and gearing limited"), "km/h",
        "asymptote of the acceleration vs speed of a full-throttle run from 270 km/h")
    row("100-0 km/h braking", "33-38 m", 33 * 0.85, 38 * 1.15, find(t13, "100-0 km/h with ABS: stopping distance (brief"), "m", "ABS on, asphalt")
    row("skidpad", "0.85-1.0 g", 0.85 * 0.85, 1.0 * 1.15, find(t14, "skidpad: brief 0.85-1.0 g, -15"), "g",
        "R 45.7 m (300 ft), highest 2 s mean a_y on the circle without sliding")
    dive = find(t13, "braking dive at 100-0")
    squat = find(t12, "launch, traction control on: peak squat")
    rollg = find(t10, "roll gradient in steady cornering")
    wt_ok = all(c is not None and c["value"] is not None for c in (dive, squat, rollg)) and dive["value"] > 0.5 and squat["value"] > 0.5 \
        and 1.0 < rollg["value"] < 8.0
    rows.append({"target": "weight transfer", "brief": "visible dive, squat, roll", "band": None,
                 "measured": None, "unit": "", "pass": bool(wt_ok),
                 "note": (f"dive {dive['value']:.1f} deg (100-0 km/h), squat {squat['value']:.1f} deg (launch), roll gradient "
                          f"{rollg['value']:.2f} deg/g" if wt_ok else "missing")})
    ctrl = []
    for tid, frag in (("T12", "straight-line stability at top speed (robot steering): yaw-rate RMS"),
                      ("T12", "open-loop straight line: largest heading change"),
                      ("T13", "ABS keeps the car steerable"),
                      ("T14", "slalom: largest body slip angle"), ("T14", "slalom: path error over the last 1.5 s"),
                      ("T14", "figure eight: largest body slip angle"), ("T14", "ramp jump: largest roll"),
                      ("T14", "ramp jump: heading change 1 s after the landing"), ("T12", "wheelspin on launch (traction control off)")):
        c = find(tests.get(tid), frag)
        ctrl.append((tid, frag, c))
    ok = all(c is not None and c["pass"] for _, _, c in ctrl)
    rows.append({"target": "controllable", "brief": "no self-oscillation, no flipping, recoverable slides, balance; easy wheelspin",
                 "band": None, "measured": None, "unit": "", "pass": bool(ok),
                 "note": "; ".join(f"{tid} {c['name'].split(':')[0]}: {c['value']:.3g} {c['unit']}" if c else f"{tid} {frag}: missing"
                                   for tid, frag, c in ctrl)})
    us = find(t10, "understeer gradient on the circle")
    if us:
        rows[-1]["note"] += f"; understeer gradient {us['value']:.1f} deg/g (understeer)"
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vehicle", nargs="?", default="hellcat")
    ap.add_argument("--run", action="store_true", help="run the Unity dynamics suite and the P3 suite first")
    ns = ap.parse_args()
    if ns.run:
        run("'-executeMethod','Hellcat.EditorTools.Validation.ValidationTasks.RunDynamics','-valTests','" + ",".join(REQUIRED) + "'",
            "docs\\p3b\\logs\\gate_p3b_dynamics.log")
        run("'-executeMethod','Hellcat.EditorTools.Validation.ValidationTasks.RunAll'", "docs\\p3b\\logs\\gate_p3b_p3suite.log")
    newest, nt = newest_input(ns.vehicle)
    path = ROOT / "docs/p3b/validation/dynamics_results.json"
    if not path.exists():
        check("dynamics results present", "FAIL", f"{path.relative_to(ROOT)} missing (run with --run)")
        return finish(ns.vehicle, [])
    vr = json.loads(path.read_text(encoding="utf-8"))
    tests = {t["id"]: t for t in vr["tests"]}
    when = stamp(vr)
    missing = [t for t in REQUIRED if t not in tests]
    check("dynamics run with every required test (9-14)", "PASS" if not missing else "FAIL",
          f"run {vr['time_utc']}, tests {', '.join(tests)}; missing: {missing or 'none'}")
    check("dynamics results newer than the vehicle data and the solver sources", "PASS" if when >= nt else "FAIL",
          f"results {when:%Y-%m-%d %H:%M:%S} UTC, newest input {newest.relative_to(ROOT)} {nt:%Y-%m-%d %H:%M:%S} UTC")
    for tid in REQUIRED:
        t = tests.get(tid)
        if t is None:
            continue
        bad = [c["name"] for c in t["checks"] if not c["pass"] and not c["info"]]
        n = sum(not c["info"] for c in t["checks"])
        check(f"test {tid[1:]}: {t['title']}", "PASS" if t["pass"] and not bad else "FAIL",
              f"{n - len(bad)}/{n} numeric checks pass in {t['seconds']:.1f} s" + (f"; failing: {bad}" if bad else "")
              + (f"; error: {t.get('error')}" if t.get("error") else ""))
    rows = targets(tests)
    for r in rows:
        band = f" (band {r['band'][0]:.4g}-{r['band'][1]:.4g} {r['unit']})" if r["band"] else ""
        meas = f"{r['measured']:.4g} {r['unit']}" if r["measured"] is not None else ""
        check(f"4.13 {r['target']}: {r['brief']}", "PASS" if r["pass"] else "FAIL", f"{meas}{band}; {r['note']}".strip("; "))
    # the P3 suite after the P3b changes (G-Solver evidence current)
    p3 = ROOT / "docs/p3/validation/validation_results.json"
    if p3.exists():
        v3 = json.loads(p3.read_text(encoding="utf-8"))
        t3 = {t["id"]: t for t in v3["tests"]}
        bad = [k for k in P3_REQUIRED if k not in t3 or not t3[k]["pass"]]
        fresh = stamp(v3) >= nt
        check("P3 suite (tests 1-8, energy drift, determinism) re-run after the P3b changes", "PASS" if not bad and fresh and not v3.get("quick") else "FAIL",
              f"run {v3['time_utc']}{'' if fresh else ' (STALE)'}, failing: {bad or 'none'}")
    else:
        check("P3 suite re-run after the P3b changes", "FAIL", "docs/p3/validation/validation_results.json missing")
    # stability of the current skeleton
    st = ROOT / "docs/p2_stability.json"
    vd = ROOT / "sim/vehicle" / ns.vehicle
    if st.exists():
        s = json.loads(st.read_text(encoding="utf-8"))
        fresh = st.stat().st_mtime >= (vd / "geometry.json").stat().st_mtime
        check("exact stability S < 2.5 on the current skeleton (D-024)", "PASS" if s["pass"] and fresh else "FAIL",
              f"S = {s['S_exact_max']} ({s['nodes']} nodes, {s['beams']} beams){'' if fresh else '; STALE'}")
    sa = ROOT / "Unity/HellcatSandbox/Assets/StreamingAssets/Vehicles" / ns.vehicle
    same = all((sa / f).exists() and (sa / f).read_bytes() == (vd / f).read_bytes() for f in ("geometry.json", "params.json"))
    check("vehicle data in sync with the Unity StreamingAssets copy", "PASS" if same else "FAIL",
          f"{vd.relative_to(ROOT)} -> {sa.relative_to(ROOT)}: {'identical' if same else 'different'}")
    rep = ROOT / "docs/dynamics_report.md"
    plots = sorted((ROOT / "docs/p3b/plots").glob("*.png"))
    ok = rep.exists() and rep.stat().st_size > 4000 and len(plots) >= 10
    check("dynamics report with plots", "PASS" if ok else "FAIL",
          f"{rep.relative_to(ROOT)} {rep.stat().st_size if rep.exists() else 0:,} bytes, {len(plots)} plots in docs/p3b/plots")
    return finish(ns.vehicle, rows)


def finish(vehicle, rows):
    failed = sum(r["status"] == "FAIL" for r in results)
    warned = sum(r["status"] == "WARN" for r in results)
    out = ROOT / "docs/gates"
    out.mkdir(parents=True, exist_ok=True)
    (ROOT / "docs/p3b").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs/p3b/targets_4_13.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    (out / "gate_p3b.json").write_text(json.dumps({"gate": "P3b (G-Dynamics)", "vehicle": vehicle, "pass": failed == 0,
                                                   "fail": failed, "warn": warned, "checks": results}, indent=2), encoding="utf-8")
    lines = ["# Gate P3b (G-Dynamics)", "", f"Vehicle `{vehicle}`. Result: **{'PASS' if failed == 0 else 'FAIL'}** "
             f"({failed} FAIL, {warned} WARN, {len(results)} checks)", "", "| # | Check | Status | Detail |", "|---|---|---|---|"]
    lines += [f"| {i} | {r['check']} | {r['status']} | {r['detail'].replace('|', '/')} |" for i, r in enumerate(results, 1)]
    (out / "gate_p3b.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for r in results:
        print(f"{r['status']:4s}  {r['check']}  --  {r['detail'][:220]}")
    print(f"P3b gate: {'PASS' if failed == 0 else 'FAIL'} ({failed} fail, {warned} warn)")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
