"""Writes docs/P4_report.md (P4: skinning in Unity and the first scripted crash S1, gate G-Crash) from the gate result
docs/gates/gate_p4.json, the crash results in sim/cache, the X21 diagnostic docs/p4/x21/dynamics_results.json and the
import report docs/p4/import_report.json. Run tools/gate_p4.py first (it writes the table and the plots), then this, then
the gate again (it checks that the report exists).

Usage: tools/.venv/Scripts/python.exe tools/p4/make_p4_report.py
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def fmt(v, f="{:.2f}"):
    return f.format(v) if isinstance(v, (int, float)) else str(v)


def x21_table():
    p = ROOT / "docs/p4/x21/dynamics_results.json"
    if not p.exists():
        return "(X21 results missing)"
    d = load(p)
    t = next(t for t in d["tests"] if t["id"] == "X21")
    rows, detail = {}, {}
    for c in t["checks"]:
        name, _, metric = c["name"].partition(": ")
        rows.setdefault(name, {})[metric] = c["value"]
        detail.setdefault(name, {})[metric] = c.get("limit", "")
    out = ["| variant (50 km/h unless named) | crush m | pulse ms | peak g 1 ms / 10 ms, mean | rebound m/s | KE after the stop kJ | energy created J | broken beams |",
           "|---|---|---|---|---|---|---|---|"]
    for name, r in rows.items():
        g10 = re.findall(r"[\d.]+", detail[name].get("peak cabin deceleration, 1 ms / 10 ms mean", ""))
        g10 = f" / {float(g10[0]):.1f}, {float(g10[2]):.1f}" if len(g10) >= 3 else ""
        out.append(f"| {name} | {r.get('dynamic crush (cabin travel to the stop)', float('nan')):.3f} | "
                   f"{r.get('pulse duration', float('nan')):.0f} | {r.get('peak cabin deceleration, 1 ms / 10 ms mean', float('nan')):.1f}{g10} | "
                   f"{r.get('rebound speed of the cabin', float('nan')):.2f} | {r.get('kinetic energy after the stop (largest within 0.4 s)', float('nan')) / 1000:.1f} | "
                   f"{r.get('energy created (largest balance rise)', float('nan')):.0f} | {r.get('broken / plastic beams', float('nan')):.0f} |")
    notes = [n for n in t["notes"] if n.startswith("S1 configuration: at the cabin stop")]
    return "\n".join(out) + ("\n\nAt the cabin stop (S1 configuration, kJ): " + notes[0].split(": at the cabin stop: ")[1].split(" | elastic by material")[0]
                              if notes else "")


def series_table(table):
    out = ["| run | impact km/h | crush dynamic / residual m | pulse ms | peak g CFC 60 (raw 4 ms) | mean g | rebound m/s | broken / plastic beams | plastic kJ | detached | hood rise m | door offset m | energy created J | tunnelled |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(table, key=lambda r: r["target_kmh"]):
        out.append(f"| {r['scenario']} {r['target_kmh']} km/h | {r['impact_kmh']:.1f} | {r['dynamic_crush_m']:.3f} / {r['residual_crush_m']:.3f} | "
                   f"{r['pulse_ms']:.0f} | {r['peak_cfc60_g']:.1f} ({r['peak_raw_4ms_g']:.1f}) | {r['mean_g']:.1f} | {r['rebound_mps']:.2f} | "
                   f"{r['broken_beams']} / {r['plastic_beams']} | {r['plastic_kJ']:.1f} | {r['detached'].replace('+', ', ') or '-'} | "
                   f"{r['hood_rise_m']:.2f} | {r['door_offset_m']:.3f}{' (latch broke)' if r['door_latch_broken'] else ''} | "
                   f"{r['energy_created_J']:.0f} | {r['tunnelled']} |")
    return "\n".join(out)


def skin_table(table):
    out = ["| run | largest node-frame turn per frame (node) | largest vertex move per frame (mesh) | vertex ahead of the fastest node (mesh) | cabin: largest turned-over area of a mesh (outside the pulse) | cabin: transient fold in the pulse | crush zones: largest turned-over area of a mesh | physics us / substep |",
           "|---|---|---|---|---|---|---|---|"]
    for r in sorted(table, key=lambda r: r["target_kmh"]):
        out.append(f"| {r['scenario']} {r['target_kmh']} km/h | {r['frame_rotation_deg']:.1f} deg ({r['frame_rotation_node']}) | "
                   f"{r['max_vertex_jump_mm']:.0f} mm ({r['max_vertex_jump_mesh']}) | {r['spike_excess_mm']:.0f} mm ({r['spike_excess_mesh'] or '-'}) | "
                   f"{r['cabin_inverted_cm2']:.1f} cm2 ({r['cabin_inverted_mesh'] or '-'}) | "
                   f"{r['cabin_pulse_inverted_cm2']:.0f} cm2 ({r['cabin_pulse_inverted_mesh'] or '-'}) | "
                   f"{r['other_inverted_cm2']:.0f} cm2 ({r['other_inverted_mesh'] or '-'}) | {r['physics_us_per_substep']:.0f} |")
    return "\n".join(out)


def gate_list(g):
    out = ["| # | check | status | detail |", "|---|---|---|---|"]
    for k, c in enumerate(g["checks"], 1):
        out.append(f"| {k} | {c['check']} | {c['status']} | {c['detail']} |")
    return "\n".join(out)


def main():
    g = load(ROOT / "docs/gates/gate_p4.json")
    table = g["table"]
    s50 = load(ROOT / "sim/cache/S1/kmh50/S1_50kmh_result.json")
    ir = load(ROOT / "docs/p4/import_report.json")
    e = s50["energy_J"]
    r50 = next(r for r in table if r["scenario"] == "S1" and r["target_kmh"] == 50)
    glass = load(ROOT / "sim/cache/S8/kmh120_glasstest/S8_120kmh_result.json")
    vids = sorted(p.name for p in (ROOT / "docs/video_assets/P4").glob("*") if p.suffix in (".mp4", ".jpg", ".png"))
    damage = s50["damage"].split(" | ")
    md = f"""# P4 report: skinning in Unity and the first scripted crash (S1)

Gate G-Crash: **{g['verdict']}** ({g['fails']} FAIL, {g['warns']} WARN, {len(g['checks'])} checks, `docs/gates/gate_p4.md`).
The Blender model is exported per part group and skinned in Unity to the 2,107 skeleton nodes ({ir['vertices']:,} vertices,
{ir['objects_count']} objects, worst bind error {ir['worst_bind_error_m'] * 1000:.4f} mm). The scripted frontal crash S1 into the rigid wall O1
at 50 km/h crumples the bumper, the hood and the front rails and leaves the cabin intact: dynamic crush
{r50['dynamic_crush_m']:.2f} m (residual {r50['residual_crush_m']:.2f} m), cabin pulse {r50['pulse_ms']:.0f} ms with a {r50['peak_cfc60_g']:.0f} g CFC 60 peak
({r50['mean_g']:.0f} g mean), rebound {r50['rebound_mps']:.1f} m/s, {r50['broken_beams']} broken beams, {r50['plastic_kJ']:.0f} kJ of plastic work, the headlamps torn off,
no energy created, no node through the wall. Damage grows with speed over 30 / 40 / 50 / 56 / 64 km/h and the 120 km/h
end point (S8). Videos and stills: `docs/video_assets/P4/`; decisions D-055 ... D-068 in `docs/decisions.md`. Found on the
way and open for P4b: a slow straight-line instability over minutes of driving (D-067), which keeps gate P3b at one
failing check (T12's top-speed path offset).

## What was built

- **Export (brief 7):** `tools/export_all.py` runs Blender in the background (`--factory-startup`) on the latest working
  file and writes one FBX per skeleton part group (32 files: body, doors, hood, deck lid, bumpers, fenders, glass,
  wheels, running gear, interior, seats, radiator, detachable lamps and mirrors), `parts.json`, `materials.json` and the
  textures to `Unity/HellcatSandbox/Assets/Game/Vehicles/Hellcat/Export`.
- **Binding:** `Tools/Hellcat/Import Car` (`CarImporter`, batch `ImportBatch`) binds every vertex to up to 4 nodes of its
  own part (inverse-distance weights; the interior trim to the passenger cell's cage with smoother weights, D-068), writes
  the compact `*.skin.bytes` next to every FBX and the prefab
  `Hellcat.prefab` (one bone per node, GPU skinning, `updateWhenOffscreen`). At the model pose the skinned meshes
  reproduce the originals within {ir['worst_bind_error_m'] * 1000:.4f} mm ({ir['worst_bind_object']}); farthest bound node
  {ir['worst_farthest_bound_node_m']:.2f} m ({ir['worst_reach_object']}). Report: `docs/p4/import_report.json`.
- **Node frames (D-062):** every node bone takes the best-fit rotation of its neighbourhood (Horn's quaternion method,
  warm-started), not a Gram-Schmidt frame from two neighbours: those flipped by up to 175 deg in a crush. The bind pose
  is a pure translation, so the frames are the identity at rest.
- **Detached parts:** the lamps, mirrors, radiator, fuel tank and seats are parts of their own (D-058) and fly with their
  nodes once their mounts break; lamps, mirrors and radiator collide with the car's own triangles.
- **Glass (D-064):** a pre-fractured shard mesh per pane (Voronoi cells seeded at the pane's nodes, `hcar/glass_shards.py`,
  `3DDodgeChallenger_v011.blend`), each shard rigid on one node; the pane swaps to its shards when its glass beams break.
  Test (`-breakGlass 0.4` at 120 km/h): {glass.get('glass_panes_shattered', 0)} of 6 panes shattered.
- **Crash player** (`Builds/P4_Crash/HellcatCrash.exe`, scene `P4_Crash`, `CarCrashScenario`, `CrashMetrics`,
  `SkinningProbe`): the settled car is driven along the lane at the target speed (speed and lane controllers, inputs
  recorded per frame) into the 12 x 3 x 1 m concrete wall, or launched rolling (S8); 4 cameras (chase, side, three-quarter from the left rear,
  top) captured at the end of every frame (after the GPU skinning); per run `sim/cache/<S>/<run>/`: result JSON, time
  series (energies, damage, inputs), 1 kHz cabin pulse, skinning log of the first 250 ms, stills, frames.
  `tools/p4/crash_series.ps1` runs the series, `tools/p4/pipeline.ps1` the whole chain after a change.
- **Solver and skeleton changes for crashes** (decisions D-055 ... D-063): hard contact with energy-correct projection,
  spring-back suppression, crush zones without rigidifiers, detachable assemblies with self-collision, hood latch,
  torsion-bar failure, pair impulse for node-triangle contact, and closure hinges / latches held in 3D.

## S1 at 50 km/h (baseline)

| quantity | value |
|---|---|
| speed at impact | {s50['speed_at_impact_kmh']:.1f} km/h |
| dynamic crush (cabin travel from the contact to the stop) / residual crush (car shortened, end of the run) | {s50['dynamic_crush_m']:.3f} m / {s50['residual_crush_m']:.3f} m |
| pulse duration, cabin deceleration peak CFC 60 / raw 4 ms / mean | {r50['pulse_ms']:.0f} ms, {r50['peak_cfc60_g']:.1f} g / {r50['peak_raw_4ms_g']:.1f} g / {r50['mean_g']:.1f} g |
| rebound speed of the cabin | {s50['rebound_mps']:.2f} m/s |
| energy at the contact / created after it | {s50['energy_at_contact_J'] / 1000:.1f} kJ / {s50['energy_created_J']:.0f} J |
| at the end: plastic / damping / breaking / contact and friction | {e['plastic'] / 1000:.1f} / {e['damping'] / 1000:.1f} / {e['breaking'] / 1000:.2f} / {s50['contact_and_friction_loss_J'] / 1000:.1f} kJ |
| broken / plastic beams, plastic shell hinges | {s50['broken_beams']} / {s50['plastic_beams']}, {s50['plastic_hinges']} |
| detached parts | {', '.join(s50['detached_parts']) or '-'} |
| damage | {damage[0]} |
| closures | {s50['closures']} |
| hood rise / roof skin rise | {s50['hood_rise_m']:.2f} m / {s50['roof_skin_rise_m']:.3f} m |
| colliding nodes past the wall face, non-finite nodes | {s50['tunnelled_nodes_max']}, {s50['nonfinite_nodes']} |
| physics cost | {s50['physics_us_per_substep']:.0f} us per 0.5 ms substep ({s50['solver']} solver), exact S {s50['stability_maxS']} |

The front structure takes the energy: in the X21 diagnostic (same car, editor) the plastic work at the cabin stop is
almost entirely in the front (rails, crush braces, cans, aprons, core support); the cabin's share stays below 1 kJ. The
hood folds up into a tent while its latch holds; the doors stay latched and move with the body's elastic flex (a few
centimetres relative to the cabin's rigid motion during the pulse, back afterwards).

![crash pulses](p4/plots/crash_pulses.png)

![S1 50 km/h energy](p4/plots/s1_50_energy.png)

## Speed series: damage grows with the speed

{series_table(table)}

Pulse: the cabin mass centre's speed at 1 kHz, deceleration filtered CFC 60 (SAE J211) in `tools/gate_p4.py`; the raw
4 ms value carries the structure's ringing. Door offset: the largest offset of a door node from the cabin's rigid motion.

![damage vs speed](p4/plots/damage_vs_speed.png)

## Why the solver changed (X21 crash diagnostic)

`X21` (`Assets/Sim/Validation/CrashDiagnostics.cs`, `-executeMethod ...ValidationTasks.RunDynamics -valTests X21`)
launches the settled car rolling into the wall in the editor with the production solver and full energy tracking, in
the final configuration and with single changes switched off; results `docs/p4/x21/`. The energy balance is kinetic +
gravity + elastic + torsion + pressure + driveline + damping + plastic + breaking: the wall and the ground are passive,
so it may only fall after the contact.

{x21_table()}

History of the S1 configuration at 50 km/h (X21 runs of the same day, `docs/p4/x21/*.csv`): the P3 contact (penalty +
projection) stopped the car in 0.46 m with a 92 g peak while the energy balance rose by 156 kJ (D-055); with the hard
contact 0.45 m / 76 g / 47 ms and nothing created; without the rigidifiers in the crush zones 0.67 m / 38 g / 79 ms
(D-057), rebound 5.6 m/s; spring-back suppression and the structure damping brought the rebound to 2.8 m/s (D-056).

## Skinning validation

{skin_table(table)}

- **At rest:** the bound meshes reproduce the originals within {ir['worst_bind_error_m'] * 1000:.4f} mm (brief: 1 mm).
- **Spikes:** linear blend skinning keeps every vertex inside the rigid motions of its own bones, so a spike needs a bone
  whose frame jumps. The probe (`SkinningProbe`, the GPU skinning recomputed on the CPU for all {s50['skin_vertices']:,} vertices every
  frame) reports the largest node-frame turn between two frames: below 120 deg for every node joined to the cabin in the
  S1 runs. At 120 km/h a front rail segment folds at 33 m/s closing speed and its frame turns {next((r['frame_rotation_deg'] for r in table if r['scenario'] == 'S8'), float('nan')):.0f} deg in one frame: a real fold
  (reported, not gated). The largest vertex move per frame (brief 7) is the tread of a spinning tire at speed (twice the
  car's speed at the top of the wheel); the excess of the fastest vertex over the fastest node of the same frame is
  largest on parts spinning free after they tore off (a lamp housing far from its three nodes), as rigid rotation
  gives.
- **Inversion:** a triangle is turned over when its normal opposes that of its rest shape carried by the blended
  skinning transform at its first vertex (what an undistorted triangle there would show); the probe sums the turned-over
  area per mesh, in the cabin (between the A-pillar base and the C pillar) and in the crush zones. Outside the impact
  pulse (before the contact and from 150 ms after it) no cabin mesh turns more than 25 cm2 (a 5 x 5 cm patch) over in the
  S1 runs. Within the pulse the sill trim folds briefly where the sill meets the hinge pillar (the structure there flexes
  elastically under the 40-50 g load; the trim is back in shape at the end and hidden behind the closed door); the
  interior binds to the cell's cage only, with smooth weights (1 / (d + 8 cm)); the crushed ends (core support, front subframe, fenders, wheel liners) fold
  over as real sheet metal does. (Shares of a mesh's area mislead on tiny meshes: one sliver of the tachometer needle
  is 10 % of it.)

## Evidence

{chr(10).join('- `docs/video_assets/P4/' + v + '`' for v in vids)}

## Gate G-Crash

{gate_list(g)}

## Deviations and open items

- **Frames (brief 7: Gram-Schmidt frames from 3 nearest nodes):** replaced by best-fit frames of up to 8 neighbours
  (D-062); the Gram-Schmidt frames flipped in the crush.
- **Shards (brief 7: Cell Fracture):** a scripted Voronoi split seeded at the pane nodes (D-064) so every shard sits on
  one node and the build stays reproducible in background Blender.
- **Hood:** folds into a single tent 0.4-0.6 m high at 30-64 km/h (a single fold of a 1.4 m hood shortened by the
  crush); real hoods fold lower thanks to crease initiators. Candidate for P6 tuning (hood crease lines).
- **Body flex:** the closures move a few centimetres relative to the cabin's rigid motion during the pulse at 50-64
  km/h; the body stiffness is capped by the 2 kHz stability limit (D-040).
- **S8 at 120 km/h** is clearly more severe (crush 1.1 m, all front structure, lamps and mirrors off, cabin plastic
  work), but the glass does not break by itself (only in the swap test); the glass strength and the A-pillar load path
  are P6 items (scenario S8 acceptance).
- **Physics cost:** {min(r['physics_us_per_substep'] for r in table):.0f}-{max(r['physics_us_per_substep'] for r in table):.0f} us per substep in the crash runs, with the self-collision of the
  detachables (budget 500 us at 2 kHz); interactive performance is measured in P4b.
- **Long-run straight-line stability (open defect, D-067, first task of P4b):** the P3b tests drive straight for 15-45 s.
  Diagnostic X24 (`-valTests X24`, `-valQuick 1` for the 120 s runs) found a slow directional instability: with the
  steering held at zero the car turns +4 deg in 60 s at a 150 km/h cruise and spins at about 90 s; at full throttle the
  robot loses the line after about 75 s (with the P3b skeleton and parameters too, so not a P4 regression). The
  road-wheel angles wander by tenths of a degree over 20-30 s (under drive the rear toe goes from 0.13 deg toe-in to 0.6
  deg toe-out); no plastic flow or rest-length change is involved. Its onset makes T12's top-speed path offset 0.505 m
  against the 0.5 m limit, so gate P3b fails on that one check until the fix. The crash scenarios (5 s runs with a lane
  controller) are not affected.
"""
    (ROOT / "docs/P4_report.md").write_text(md, encoding="utf-8")
    print("docs/P4_report.md", len(md), "chars")


if __name__ == "__main__":
    main()
