"""P3 quality gate (G-Solver): solver core on the Hellcat skeleton, validation tests 1-8 (brief section 10), energy
drift and determinism.

Inputs:
    docs/p3/validation/validation_results.json   Unity validation suite (Hellcat.EditorTools.Validation.ValidationTasks
                                                 .RunAll); --run executes it first through tools/unity/run_unity_batch.ps1
    sim/vehicle/<vehicle>/geometry.json, params.json and Unity/HellcatSandbox/Assets/Sim/**/*.cs
                                                 the results must be newer than all of them (no stale evidence)
    docs/p3/body_stiffness.json                  tools/p3/body_stiffness.py --json (D-040)
    docs/validation_report.md                    the human-readable report

G-Solver (brief 14): tests 1-8 pass numerically; energy drift without impact < 1 % over 10 s; a deterministic re-run
matches. Also checked: exact stability S < 2.5 and the C# / Python agreement, the real-time step budget, the exported
data in sync, the global body stiffness floor of D-040.

Usage:  tools/.venv/Scripts/python.exe tools/gate_p3.py [vehicle] [--run]
Output: docs/gates/gate_p3.json and docs/gates/gate_p3.md
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "E1", "D1"]
BODY_FLOOR = {"torsion_kNm_per_deg": 5.0, "bending_kN_per_mm": 1.5}    # D-040 minimum (real cars ~15-35 / ~10-20)
results = []


def check(name, status, detail):
    results.append({"check": name, "status": status, "detail": detail})


def run_suite():
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
           "& tools\\unity\\run_unity_batch.ps1 -LogFile docs\\p3\\logs\\gate_p3_suite.log -ProjectPath Unity\\HellcatSandbox "
           "-UnityArgs @('-executeMethod','Hellcat.EditorTools.Validation.ValidationTasks.RunAll')"]
    return subprocess.run(cmd, cwd=ROOT).returncode


def find(test, fragment):
    for c in test["checks"]:
        if fragment in c["name"]:
            return c
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vehicle", nargs="?", default="hellcat")
    ap.add_argument("--run", action="store_true", help="run the Unity validation suite first")
    ns = ap.parse_args()
    if ns.run:
        run_suite()
    path = ROOT / "docs/p3/validation/validation_results.json"
    if not path.exists():
        check("validation results present", "FAIL", f"{path.relative_to(ROOT)} missing (run with --run)")
        return finish(ns.vehicle)
    vr = json.loads(path.read_text(encoding="utf-8"))
    tests = {t["id"]: t for t in vr["tests"]}
    when = dt.datetime.strptime(vr["time_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    missing = [t for t in REQUIRED if t not in tests]
    check("full validation run with every required test", "PASS" if not missing and not vr.get("quick") else "FAIL",
          f"run {vr['time_utc']}, quick={vr.get('quick')}, tests {', '.join(tests)}; missing: {missing or 'none'}")

    # evidence is not stale: newer than the vehicle data and the solver sources
    vd = ROOT / "sim/vehicle" / ns.vehicle
    inputs = [vd / "geometry.json", vd / "params.json"] + list((ROOT / "Unity/HellcatSandbox/Assets/Sim").rglob("*.cs"))
    newest = max(inputs, key=lambda q: q.stat().st_mtime)
    nt = dt.datetime.fromtimestamp(newest.stat().st_mtime, dt.timezone.utc)
    check("results newer than the vehicle data and the solver sources", "PASS" if when >= nt.replace(microsecond=0) else "FAIL",
          f"results {when:%Y-%m-%d %H:%M:%S} UTC, newest input {newest.relative_to(ROOT)} {nt:%Y-%m-%d %H:%M:%S} UTC")

    # tests 1-8
    for tid in REQUIRED[:8]:
        t = tests.get(tid)
        if t is None:
            continue
        bad = [c["name"] for c in t["checks"] if not c["pass"] and not c["info"]]
        n = sum(not c["info"] for c in t["checks"])
        check(f"test {tid[1:]}: {t['title']}", "PASS" if t["pass"] else "FAIL",
              f"{n - len(bad)}/{n} numeric checks pass in {t['seconds']:.1f} s" + (f"; failing: {bad}" if bad else "")
              + (f"; error: {t.get('error')}" if t.get("error") else ""))

    # energy drift < 1 % / 10 s
    e1 = tests.get("E1")
    if e1:
        drift = [c for c in e1["checks"] if "drift" in c["name"]]
        mom = [c for c in e1["checks"] if "angular momentum" in c["name"]]
        ok = drift and all(c["pass"] and c["value"] is not None and c["value"] < 0.01 for c in drift)
        check("energy drift without impact < 1 % over 10 s (damping on: mechanical + dissipated; off: mechanical)",
              "PASS" if ok else "FAIL", "; ".join(f"{c['name']} = {c['value']:.3g}" for c in drift))
        check("angular momentum conserved in free flight (< 0.1 %)", "PASS" if mom and all(c["pass"] for c in mom) else "FAIL",
              "; ".join(f"{c['name']} = {c['value']:.3g}" for c in mom))
    # determinism
    d1 = tests.get("D1")
    if d1:
        hashes = [c for c in d1["checks"] if not c["info"]]
        check("deterministic re-run matches (bit-identical, parallel and single-thread)",
              "PASS" if d1["pass"] and hashes else "FAIL", "; ".join(f"{c['name']}: {c['value']:.0f}" for c in hashes))
    # stability and real time (T6)
    t6 = tests.get("T6")
    if t6:
        s = find(t6, "exact stability S")
        ref = find(t6, "S without torsion bars")
        check("exact stability S < 2.5 on the built world (D-024) and the C# / Python agreement",
              "PASS" if s and s["pass"] and ref and ref["pass"] else "FAIL",
              f"S = {s['value']:.4f} ({s['limit']}); beams-only S = {ref['value']:.4f} vs Python {ref['limit']}" if s and ref else "missing")
        rt = find(t6, "real-time budget")
        check("physics time per substep within the 2 kHz real-time budget", "PASS" if rt and rt["pass"] else "FAIL",
              f"{rt['value']:.1f} us ({rt['limit']})" if rt else "missing")
    # data in sync
    sa = ROOT / "Unity/HellcatSandbox/Assets/StreamingAssets/Vehicles" / ns.vehicle
    same = all((sa / f).exists() and (sa / f).read_bytes() == (vd / f).read_bytes() for f in ("geometry.json", "params.json"))
    check("vehicle data in sync with the Unity StreamingAssets copy", "PASS" if same else "FAIL",
          f"{vd.relative_to(ROOT)} -> {sa.relative_to(ROOT)}: {'identical' if same else 'different'}")
    # body stiffness floor (D-040)
    bs = ROOT / "docs/p3/body_stiffness.json"
    if bs.exists():
        b = json.loads(bs.read_text(encoding="utf-8"))
        low = [k for k, v in BODY_FLOOR.items() if b.get(k, 0.0) < v]
        fresh = bs.stat().st_mtime >= (vd / "geometry.json").stat().st_mtime
        check("global body stiffness at or above the D-040 floor (torsion >= 5 kN m/deg, bending >= 1.5 kN/mm)",
              "PASS" if not low and fresh else "FAIL",
              f"torsion {b.get('torsion_kNm_per_deg')} kN m/deg, bending {b.get('bending_kN_per_mm')} kN/mm "
              f"(real cars ~15-35 / ~10-20: the 2 kHz stability limit, D-040){'' if fresh else '; STALE (older than geometry.json)'}")
    else:
        check("global body stiffness at or above the D-040 floor", "FAIL", "docs/p3/body_stiffness.json missing")
    rep = ROOT / "docs/validation_report.md"
    check("validation report written", "PASS" if rep.exists() and rep.stat().st_size > 2000 else "FAIL",
          f"{rep.relative_to(ROOT)} {rep.stat().st_size if rep.exists() else 0:,} bytes")
    return finish(ns.vehicle)


def finish(vehicle):
    failed = sum(r["status"] == "FAIL" for r in results)
    warned = sum(r["status"] == "WARN" for r in results)
    out = ROOT / "docs/gates"
    out.mkdir(parents=True, exist_ok=True)
    (out / "gate_p3.json").write_text(json.dumps({"gate": "P3 (G-Solver)", "vehicle": vehicle, "pass": failed == 0,
                                                  "fail": failed, "warn": warned, "checks": results}, indent=2),
                                      encoding="utf-8")
    lines = ["# Gate P3 (G-Solver)", "", f"Vehicle `{vehicle}`. Result: **{'PASS' if failed == 0 else 'FAIL'}** "
             f"({failed} FAIL, {warned} WARN, {len(results)} checks)", "", "| # | Check | Status | Detail |",
             "|---|---|---|---|"]
    lines += [f"| {i} | {r['check']} | {r['status']} | {r['detail'].replace('|', '/')} |" for i, r in enumerate(results, 1)]
    (out / "gate_p3.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for r in results:
        print(f"{r['status']:4}  {r['check']}  --  {r['detail'][:300]}")
    print(f"P3 gate: {'PASS' if failed == 0 else 'FAIL'} ({failed} fail, {warned} warn)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
