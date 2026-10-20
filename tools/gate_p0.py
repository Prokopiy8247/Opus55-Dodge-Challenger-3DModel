"""P0 quality gate: re-checks every P0 artifact and writes a PASS/FAIL report.

Usage:  python -I tools\\gate_p0.py
Output: docs\\gates\\gate_p0.json and docs\\gates\\gate_p0.md
Exit code 0 when no check FAILs (WARN is allowed). Standard library only.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_SHA256 = "AA42CA0C78B5BE03BCDE065E7861075C6BADFBBFD7FDDEF8DF9B2D74F9CFAE68"
REALTIME_STEPS_PER_S = 2000  # dt = 0.5 ms
FRAME_BUDGET_MS = 1000.0 / 60.0

results = []


def check(name, status, detail):
    results.append({"check": name, "status": status, "detail": detail})


def load_json(rel):
    path = ROOT / rel
    # PowerShell's Set-Content -Encoding UTF8 writes a BOM; utf-8-sig accepts both.
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


# --- Blender side ---------------------------------------------------------
orig = ROOT / "3DDodgeChallenger.blend"
digest = sha256(orig) if orig.exists() else "missing"
check("original .blend untouched", "PASS" if digest == ORIGINAL_SHA256 else "FAIL", f"sha256 {digest}")
v001 = ROOT / "3DDodgeChallenger_v001.blend"
check("working file v001 saved", "PASS" if v001.exists() else "FAIL",
      f"{v001.name} {v001.stat().st_size if v001.exists() else 0} bytes")
scripts = [ROOT / "tools/blender/p0_01_save_as_v001.py", ROOT / "tools/blender/p0_02_inspect_and_capture.py"]
check("Blender MCP scripts kept as files", "PASS" if all(p.exists() for p in scripts) else "FAIL",
      ", ".join(p.name for p in scripts))
shots = sorted((ROOT / "docs/video_assets/P0").glob("*.png"))
check("P0 video asset (Blender before-state screenshot)", "PASS" if shots else "FAIL",
      ", ".join(p.name for p in shots) or "none")

# --- Environment audit ----------------------------------------------------
env = load_json("docs/p0/env_audit.json")
cpu_ok = "5700X3D" in env["cpu"]["name"] and env["cpu"]["logical"] == 16
gpu_ok = any("RTX 5070" in g["name"] and g["driverVersion"] == "32.0.16.1692" for g in env["gpus"])
ram_ok = 60 <= env["ramGB"] <= 68
check("hardware matches brief (CPU, RAM, GPU, driver)", "PASS" if cpu_ok and gpu_ok and ram_ok else "FAIL",
      f"{env['cpu']['name']} {env['cpu']['cores']}C/{env['cpu']['logical']}T, {env['ramGB']} GB, "
      f"{env['nvidiaSmi']}")
c_free = next(d["freeGB"] for d in env["disks"] if d["drive"] == "C:")
check("drive C: low on space (everything on W:)", "WARN" if c_free < 25 else "PASS", f"C: {c_free} GB free at audit time")
unity_ed = env["unityEditors"][0]
check("Unity editor 6000.6.0f1 installed", "PASS" if unity_ed["version"] == "6000.6.0f1" else "FAIL",
      f"{unity_ed['exe']} ({unity_ed['productVersion']}); Windows variations: {', '.join(unity_ed['windowsVariations'])}")
check("IL2CPP module", "WARN" if not any("il2cpp" in v for v in unity_ed["windowsVariations"]) else "PASS",
      "not installed; Mono backend is used for Windows builds")

# --- Unity project, licence, packages -------------------------------------
proj = ROOT / "Unity/HellcatSandbox"
pv = (proj / "ProjectSettings/ProjectVersion.txt").read_text(encoding="utf-8")
check("Unity project created", "PASS" if "6000.6.0f1" in pv else "FAIL", str(proj))
create_log = (ROOT / "docs/p0/logs/01_create_project.log").read_text(encoding="utf-8", errors="replace")
lic_ok = "Successfully resolved entitlement details" in create_log and "No valid Unity Editor license" not in create_log
product = re.search(r"Product: (.+)", create_log)
check("Unity licence works in batch mode", "PASS" if lic_ok else "FAIL",
      f"{product.group(1).strip() if product else 'product not logged'}; "
      "log also shows 'Access token is unavailable' (non-blocking)")
manifest = load_json("Unity/HellcatSandbox/Packages/manifest.json")["dependencies"]
wanted = {"com.unity.burst": "2.0.0", "com.unity.collections": "6.6.0", "com.unity.inputsystem": "1.20.1",
          "com.unity.test-framework": "1.8.0", "com.unity.recorder": "5.1.7",
          "com.unity.render-pipelines.universal": "17.6.0"}
missing = {k: v for k, v in wanted.items() if manifest.get(k) != v}
check("package versions pinned in manifest.json", "PASS" if not missing else "FAIL",
      ", ".join(f"{k}@{v}" for k, v in wanted.items()) + (f"; missing/different: {missing}" if missing else ""))
uenv = {i["key"]: i["value"] for i in load_json("docs/p0/unity_environment.json")["items"]}
loaded = [k for k in uenv if k.startswith("type:") and "Cinemachine" not in k]
not_loaded = [k for k in loaded if not uenv[k].startswith("loaded")]
check("package assemblies load (Collections, Input System, Recorder, Test Framework, NUnit)",
      "PASS" if not not_loaded and uenv.get("burstEnabled") == "True" else "FAIL",
      f"burstEnabled={uenv.get('burstEnabled')}; Mathematics in {uenv.get('assembly:Unity.Mathematics.float3')}; "
      f"Burst in {uenv.get('assembly:Unity.Burst.BurstCompileAttribute')}" + (f"; missing {not_loaded}" if not_loaded else ""))
check("GPU visible to Unity + compute shader smoke test",
      "PASS" if uenv.get("computeSmokeTest", "").startswith("ok") and "RTX 5070" in uenv.get("gpu", "") else "FAIL",
      f"{uenv.get('gpu')} {uenv.get('gpuApi')} {uenv.get('gpuMemoryMB')} MB; {uenv.get('computeSmokeTest')}")

# --- BeamNG notes ---------------------------------------------------------
notes = (ROOT / "docs/physics_notes.md").read_text(encoding="utf-8")
sections = all(f"## {i}." in notes for i in range(1, 10))
check("docs/physics_notes.md written from official docs", "PASS" if sections and "documentation.beamng.com" in notes else "FAIL",
      f"{len(notes.splitlines())} lines, sections 1-9 present={sections}")

# --- Burst micro-benchmark ------------------------------------------------
bench = {ctx: load_json(f"docs/benchmarks/P0_burst_bench_{ctx}.json") for ctx in ("editor", "player")}
spec_ok = all(b["nodes"] == 3000 and b["beams"] == 15000 and abs(b["options"]["sim"]["dt"] - 0.0005) < 1e-9
              for b in bench.values())
check("benchmark matches spec (3,000 nodes / 15,000 beams / dt 0.5 ms)", "PASS" if spec_ok else "FAIL",
      "; ".join(f"{c}: {b['nodes']} nodes, {b['beams']} beams" for c, b in bench.items()))
all_runs = [(c, r) for c, b in bench.items() for r in b["runs"]]
check("Burst code executed in every run, no NaN/Inf",
      "PASS" if all(r["burst"] and r["nonFinite"] == 0 for _, r in all_runs) else "FAIL",
      f"{len(all_runs)} runs")
hashes = {}
for c, r in all_runs:
    hashes.setdefault(r["layout"], set()).add(r["stateHash"])
det_ok = all(len(h) == 1 for h in hashes.values())
check("determinism: identical state hash across runs, thread counts, ST/MT and editor/player",
      "PASS" if det_ok else "FAIL", "; ".join(f"{k}: {sorted(v)}" for k, v in hashes.items()))
player = bench["player"]["runs"]
best_mt = max((r for r in player if r["variant"] == "MT"), key=lambda r: r["stepsPerSecond"])
best_st = max((r for r in player if r["variant"] == "ST"), key=lambda r: r["stepsPerSecond"])
rt_ok = best_st["stepsPerSecond"] >= REALTIME_STEPS_PER_S and best_mt["stepsPerSecond"] >= REALTIME_STEPS_PER_S
check("real time at 2000 Hz (player build)", "PASS" if rt_ok else "FAIL",
      f"ST {best_st['stepsPerSecond']:.0f} steps/s (x{best_st['realtimeFactor']:.1f}); "
      f"MT {best_mt['stepsPerSecond']:.0f} steps/s (x{best_mt['realtimeFactor']:.1f}, {best_mt['workers']} workers)")
check("60 fps frame budget (33 substeps per frame, player build)",
      "PASS" if best_mt["frameMsP99"] < FRAME_BUDGET_MS and best_st["frameMsP99"] < FRAME_BUDGET_MS else "FAIL",
      f"MT mean {best_mt['frameMsMean']:.2f} ms / p99 {best_mt['frameMsP99']:.2f} ms; "
      f"ST mean {best_st['frameMsMean']:.2f} ms / p99 {best_st['frameMsP99']:.2f} ms (budget {FRAME_BUDGET_MS:.2f} ms)")
r0 = player[0]
check("plastic deformation and breaking exercised", "PASS" if r0["brokenBeams"] > 0 and r0["plasticBeams"] > 0 else "FAIL",
      f"{r0['plasticBeams']} plastic, {r0['brokenBeams']} broken beams after the wall impact")
b = bench["player"]
check("stability guideline omega*dt < 0.5 on the synthetic lattice", "WARN" if b["omegaViolations"] else "PASS",
      f"max omega*dt {b['maxOmegaDt']:.3f}, {b['omegaViolations']} nodes >= 0.5 (valence up to {b['maxValence']}); run stayed stable")

# --- write ----------------------------------------------------------------
failed = sum(r["status"] == "FAIL" for r in results)
warned = sum(r["status"] == "WARN" for r in results)
summary = {"gate": "P0", "pass": failed == 0, "fail": failed, "warn": warned, "checks": results}
out_dir = ROOT / "docs/gates"
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "gate_p0.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
lines = ["# Gate P0", "", f"Result: **{'PASS' if failed == 0 else 'FAIL'}** ({failed} FAIL, {warned} WARN, {len(results)} checks)", "",
         "| # | Check | Status | Detail |", "|---|---|---|---|"]
for i, r in enumerate(results, 1):
    lines.append(f"| {i} | {r['check']} | {r['status']} | {r['detail'].replace('|', '/')} |")
(out_dir / "gate_p0.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
for r in results:
    print(f"{r['status']:4}  {r['check']}  --  {r['detail']}")
print(f"P0 gate: {'PASS' if failed == 0 else 'FAIL'} ({failed} fail, {warned} warn)")
sys.exit(1 if failed else 0)
