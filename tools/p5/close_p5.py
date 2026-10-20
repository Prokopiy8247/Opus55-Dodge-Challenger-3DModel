"""One-off (P5 close): decisions D-081 ... D-083, docs/P5_report.md, the changelog row, the controls and STATUS updates,
from docs/gates/gate_p5.json, docs/p5/map_layout.json and docs/p5/mapcheck/mapcheck.json.

Usage: tools/.venv/Scripts/python.exe tools/p5/close_p5.py <P5 end timestamp UTC>
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
end = sys.argv[1] if len(sys.argv) > 1 else ""
g = json.loads((ROOT / "docs/gates/gate_p5.json").read_text(encoding="utf-8"))
lay = json.loads((ROOT / "docs/p5/map_layout.json").read_text(encoding="utf-8"))
m = json.loads((ROOT / "docs/p5/mapcheck/mapcheck.json").read_text(encoding="utf-8"))
runs = m["runs"]


def append_rows(path, rows, key):
    p = ROOT / path
    s = p.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")
    if key in s:
        print(f"{path}: already has {key}")
        return
    p.write_bytes((s + "\n" + "\n".join(rows) + "\n").encode("utf-8"))
    print(f"{path}: {len(rows)} rows appended")


# ---- decisions
append_rows("docs/decisions.md", [
    "| D-081 | 2026-10-15 | Debris (test map O8) is soft bodies in the car's solver: `PropFactory` builds node-beam barrels (18 nodes, 20 kg), boxes (8 nodes, 5 kg), traffic cones (9 nodes, 1.5 kg, weighted base) and wooden fence panels (16 nodes, 15 kg, posts held by two buried fixed nodes each, anchor beams breaking at 4 kN); `PropField` adds them to the world through `IDynamicBodySource` (after the car, fixed order) and draws each as a rigid mesh on the best-fit frame of its movable nodes. Spring and damping rates are sized per prop from its most connected node for about 0.6 (stiffness) + 0.3 (damping) + 0.7 (contact) of the explicit-step criterion S; props spawn 12 mm above the surface below; box stacks are aligned corner on corner; Ctrl+R puts the debris back. | Brief 8 asks for debris that interacts with the soft body in one physics world. The first rates (stiff, 120 N s/m dampers) took the world's exact S from 2.44 to 2.83 - S counts 2 dt C / m, and the barrel's end-cap centres carry 17 beams; props spawned on the ground sat inside the 10 mm contact zone and were kicked off; a single anchor point let the fence panels tip like inverted pendulums; rotated stacks overhung and fell. Now S stays at the car's 2.44, the debris rests within 4 cm and 0.06 m/s, and the solver costs 349 instead of 286 us per substep with 46 debris bodies. |",
    "| D-082 | 2026-10-15 | Test map (`TestMapBuilder`, scene TestMap, player `Builds/TestMap/HellcatTestMap.exe`): 300 x 200 m asphalt (x east, z north, 10 m marks in the ground texture, 8 m grass band); south row (lanes heading north) O1 wall, O2 the same wall with the 40 % offset line on the driver side, O3 pole, O4 six F-shape jersey barriers (two convex prisms each) at 20 deg, O5 guardrail met at 10 deg; north row (lanes heading south) O6 ramp with the landing pad 25 m beyond the lip, O7 circular-arc speed bump and a 45 deg curb, O8 debris field, O9 3 m ledge (30 m access ramp, plateau, lower pad) and a separate 30 deg grass bank; every lane 60.1-65.8 m of clean run-up from its spawn, painted with distance marks and a label; skidpad R 30 m in the open east. Surfaces: asphalt x1.0, concrete x0.9, grass x0.6 of the tyre friction (car about 0.94 / 0.85 / 0.57 g). `MapCheck` (-scenario mapcheck) and `tools/gate_p5.py` (G-Map) check the layout against the brief, the debris at rest, one run per lane and the screenshots. | The rows face each other across a free strip so every lane gets its run-up inside 200 m and the cars that carry on after an obstacle run past the other row; static obstacles are convex primitives the solver already has (boxes, cylinders, prisms). The friction scales were tuned in P3b on asphalt (skidpad 0.94 g); concrete and grass keep their ratios rather than the brief's absolute values, which they match within 10 %. |",
    "| D-083 | 2026-10-15 | The teleport speed hold (D-080) lets go 1 m before static solids taller than 0.3 m that lie ahead of the car only (not the grass slabs, curbs and bumps it drives over, not obstacles behind it), and lanes over drivable obstacles (O8 debris, O9 ledge and bank) hold the speed through them until the run-up time is over (`SpawnPoint.holdThrough`). | On the north row the hold let go at once: the grass band 0.4 m behind the spawn counted as an obstacle, so the car coasted and stopped 20 m short of the debris; on O9 it let go at the foot of the access ramp and the car stalled on the plateau short of the ledge. |",
], "| D-081 |")

# ---- report
by = {(r["lane"], r["target_kmh"]): r for r in runs}
rows = "\n".join(f"| {r['lane']} | {r['target_kmh']} | {r['release_kmh']} | {r['release']} | {r['end_speed_kmh']} | {r['broken_beams']} ({r.get('broken_by_material') or '-'}) | "
                 f"{r['bent_beams']} | {r['airborne_s']} | {r['props_moved']} | {r['deepest_in_obstacle_m'] * 1000:.0f} |" for r in runs)
lanes = "\n".join(f"| {ln['id']} | ({ln['spawn'][0]}, {ln['spawn'][1]}) | {ln['heading_deg']} | {ln['clean_run_m']} | {ln['default_kmh']} |" for ln in lay["lanes"])
checks = "\n".join(f"| {k} | {r['check']} | {r['status']} | {r['detail']} |" for k, r in enumerate(g["checks"], 1))
st = m["settle"]
report = f"""# P5 report: the test map

Gate G-Map: **{g['verdict']}** ({g['fails']} FAIL, {g['warns']} WARN, {len(g['checks'])} checks, `docs/gates/gate_p5.md`).

**What the map is.** The test map of brief 8 is built in Unity by code (`TestMapBuilder`, scene `Assets/Scenes/TestMap.unity`, player `Builds/TestMap/HellcatTestMap.exe`).

- A 300 m x 200 m asphalt proving ground with 10 m marks and an 8 m grass band round the edge.
- The nine obstacles O1-O9, each with a painted lane and at least 60 m of clean run-up from its spawn point (60.1-65.8 m).
- A 30 m skidpad circle in the open east part.

**Debris.** The O8 debris (12 barrels, 20 boxes, 8 cones, 6 fence panels) consists of soft bodies in the same solver as the car (D-081). It collides with the car both ways and with the statics.

With 46 debris bodies in the world:

- the solver's exact stability criterion stays at the car's S = {m['world']['stability_S']:.3f} (limit 2.5);
- the debris rests within {st['prop_max_drift_m'] * 100:.1f} cm and {st['prop_max_node_speed']:.3f} m/s;
- physics costs {m['us_per_substep']} us per 0.5 ms substep, within the 500 us real-time budget.

**The map check** runs one drive per lane in the player, using the teleport speed hold (D-080, D-083).

- **Walls, pole and barriers.** The car meets them at the target speed.
- **Debris.** The car scatters {by.get(('O8', 20), {}).get('props_moved', '?')} debris bodies.
- **Ramp and ledge.** The car flies {by.get(('O6', 60), {}).get('airborne_s', '?')} s off the ramp and {by.get(('O9', 30), {}).get('airborne_s', '?')} s off the 3 m ledge, and lands upright.
- **Bump and curb.** At 30 and 50 km/h they leave no structural damage. Brief 9 says the car must not self-destruct over curbs and bumps at 30-50 km/h.
- **Solver health.** No node ends up inside an obstacle and no value is non-finite.

Decisions D-081 ... D-083 are in `docs/decisions.md`.

![top-down](p5/map_topdown_annotated.png)

## Layout

{len(lay['obstacles']) - 2} obstacle entries, extent {lay['extent_m'][0]} x {lay['extent_m'][1]} m (`docs/p5/map_layout.json`).

- **Rows.** South row, lanes heading north: O1-O5. North row, lanes heading south: O6-O9. The obstacles face each other across a free strip, so a car that carries on after an obstacle passes between the other row's obstacles.
- **Surfaces.** Asphalt x1.0, concrete x0.9, grass x0.6 of the tyre friction. With the car this gives about 0.94 / 0.85 / 0.57 g: the skidpad measures 0.94 g on asphalt and the tyre's peak coefficient is 1.20 (T9). The brief asks for about 0.9 / 0.8 / 0.6.

| obstacle | build | brief |
|---|---|---|
| O1 | concrete wall 12 x 3 x 1 m, face at z = -20 | 12 x 3 x 1 m |
| O2 | the same wall; yellow lines for the wall edge and the 40 % overlap of the car's width on the driver side | 40 % overlap line |
| O3 | steel pole 0.30 m x 6 m | 0.30 x 6 m |
| O4 | 6 F-shape jersey barriers 3.66 m x 0.81 m (base 0.61, break 0.25 m wide at 0.33 m, top 0.15 m) end to end at 20 deg to the lane | 6 units, ~3.66 x 0.81 m, at 20 deg |
| O5 | guardrail 15.2 m, 9 posts every 1.9 m, W-beam 0.31 m with its top at 0.70 m, turned-down end; the lane meets it at 10 deg | ~15 m, posts 1.9 m, ~0.7 m |
| O6 | concrete ramp 6 m x 1.2 m (11.3 deg), 4 m wide; landing pad 10 x 20 m centred 25 m beyond the lip | 6 m x 1.2 m, landing 25 m beyond |
| O7 | speed bump 0.10 m high, 3 m long (circular arc), 6 m wide; curb 0.15 m x 0.3 m x 10 m at 45 deg to the lane, 20 m after the bump | curb 0.15 m, bump 0.10 x 3 m |
| O8 | 8 cones in gates, 12 barrels (4 x 3), 20 boxes (12 on the ground, 8 stacked), 6 fence panels across the lane, as soft bodies | 12 / 20 / 8 / 6 with the brief's sizes and masses |
| O9 | 30 m access ramp to a 10 x 15 m plateau, 3 m ledge over a 16 x 30 m lower pad; a separate 30 deg grass bank 4 m high, 24 m long beside its own lane | 3 m ledge with lower pad, 30 deg bank |

| lane | spawn (x, z) | heading deg | clean run-up m | default km/h |
|---|---|---|---|---|
{lanes}

## Debris in the solver (D-081)

`PropFactory` (Sim) builds the bodies and `PropField` (Game) adds them to the world and draws them.

- **Barrel.** Two rings of 8 nodes and two end-cap centres, braced; 20 kg.
- **Box.** 8 corner nodes, every pair braced; 5 kg.
- **Cone.** Weighted base corners, a foot ring and the tip; 1.5 kg.
- **Fence panel.** A 4 x 2 x 2 node board. Each end post is held by two buried fixed nodes in front of and behind it; the anchor beams break at 4 kN, after which the panel flies free.

Problems found and fixed on the way:

- **Stability.** S counts damping too (2 dt C / m), so the first rates took the world's S to 2.83. They are now sized per prop for about 0.6 (stiffness) + 0.3 (damping) + 0.7 (contact).
- **Spawn kick.** Props spawned on the ground sat inside the 10 mm contact zone and were kicked off. They now spawn 12 mm up.
- **Fence panels.** One anchor point per post let them tip over like inverted pendulums.
- **Box stacks.** Rotated stacks overhung their supporting corners and fell; the stacks are now aligned corner on corner.

Debris at rest after 5 s:

- fastest node {st['prop_max_node_speed']:.3f} m/s;
- largest drift {st['prop_max_drift_m'] * 100:.1f} cm;
- the fence panels still shiver a little ({st['movers'].split(';')[0] if st['movers'] else '-'}).

## Map check (player, `-scenario mapcheck`)

| lane | target km/h | at the obstacle km/h | hold | end km/h | broken beams (by material) | bent beams | airborne s | debris moved | deepest in obstacle mm |
|---|---|---|---|---|---|---|---|---|---|
{rows}

- **`stop_closure` beams.** These are the hood and deck-lid rubber stops. They release by design when a lid lifts off by half their length (D-034), so the jump and the 3 m drop shed some.
- **`lamp_mount` beams.** The headlamps detach in the frontal hits (D-058).
- **Bump and curb.** At 30 and 50 km/h they cost at most one released stop and no bent beam.

## Gate checks

| # | check | status | detail |
|---|---|---|---|
{checks}

## Files

- **Images:**
  - `docs/p5/map_topdown_annotated.png`: top-down with the dimensions legend and the run-up lengths;
  - `docs/p5/mapcheck/map_topdown.png`: raw top-down at 10 px/m;
  - `docs/p5/mapcheck/map_overview.png`: perspective overview;
  - `docs/p5/map_lanes_sheet.jpg`: every lane in perspective with its dimensions;
  - `docs/p5/mapcheck/lane_*.png` and `run_*.png`.
- **Data:** `docs/p5/map_layout.json` (builder) and `docs/p5/mapcheck/mapcheck.json` (player).
- **Tools:** `tools/p5/annotate_map.py` and `tools/gate_p5.py`.

## Open points

- **Closure stops.** The hood and deck-lid stops release on hard landings (the jump, the drop); after that the lids can flutter. To review in P6 tuning: keep them, or raise their release length.
- **Frontal hits.** At 30 km/h into the wall both headlamps detach and the closure stops release (as at 50 km/h in P4). The crash series is re-run and tuned in P6.
- **Debris look.** Debris is drawn rigid: a barrel's dents and a broken fence's pieces do not show.
- **O9 bank.** The bank is for free driving; the scripted scenarios S1-S8 do not use O9.
"""
(ROOT / "docs/P5_report.md").write_text(report, encoding="utf-8")
print("wrote docs/P5_report.md")

# ---- changelog
append_rows("docs/changelog.md", [
    f"| P5 | 2026-10-15 | P5 | Test map (brief 8): `TestMapBuilder` -> scene TestMap, player `Builds/TestMap/HellcatTestMap.exe`, 300 x 200 m with O1-O9 (walls, 40 % offset line, pole, jersey row at 20 deg, guardrail met at 10 deg, ramp + landing pad, speed bump + 45 deg curb, debris field, 3 m ledge + 30 deg bank), lanes of 60.1-65.8 m clean run-up with distance marks, skidpad, grass band, surfaces asphalt / concrete / grass x1.0 / 0.9 / 0.6 (D-082). Debris as soft bodies in the car's solver (`PropFactory`, `PropField`, `IDynamicBodySource`; S stays 2.44, debris at rest, D-081). Speed hold releases only before tall obstacles ahead, lanes can hold through (D-083). Map check in the player (`MapCheck`): one run per lane, no tunnelling, curb and bump at 30 / 50 km/h without structural damage; gate G-Map {g['verdict']} ({g['fails']} fail, {g['warns']} warn). `docs/P5_report.md`. |",
], "| P5 | 2026-10-15 |")

# ---- controls
cp = ROOT / "docs/controls.md"
c = cp.read_text(encoding="utf-8")
if "Ctrl+R" not in c:
    c = c.replace("| Shift+R | **Full repair** in place:", "| Ctrl+R | Reset the map: the debris back where it started and the car to the last safe position |\n| Shift+R | **Full repair** in place:")
    c = c.replace("The drivable sandbox is `Builds/P4b_Drive/HellcatDrive.exe` (scene `Assets/Scenes/P4b_Drive.unity`).",
                  "The test map (P5) is `Builds/TestMap/HellcatTestMap.exe` (scene `Assets/Scenes/TestMap.unity`, obstacles O1-O9 with their spawn points\n"
                  "in the pause menu); the P4b drive scene `Builds/P4b_Drive/HellcatDrive.exe` keeps the 977 m loop of the drive test.")
    c = c.replace("- `-scenario drive` runs the gate G-Drive test.", "- `-scenario mapcheck` (test map) runs the P5 map check (`-mapOut dir`).\n- `-scenario drive` runs the gate G-Drive test.")
    cp.write_text(c, encoding="utf-8")
    print("controls.md updated")

# ---- STATUS
sp = ROOT / "docs/STATUS.md"
s = sp.read_text(encoding="utf-8")
head = f"""# STATUS (resume here after a context compaction or restart)

Last update: 2026-10-15. Phase **P5 done** (test map, gate G-Map {g['verdict']} {g['fails']} fail / {g['warns']} warn); next **P6** (scenarios S1-S8,
crash series re-run with D-069, tuning, sensitivity sweep). Test map `Builds/TestMap/HellcatTestMap.exe`: 300 x 200 m, O1-O9 with
60+ m lanes, debris as soft bodies in the solver (S 2.44 unchanged, 349 us per substep), map check per lane without tunnelling
(`docs/P5_report.md`). P4b before: the game layer, G-Drive PASS (`docs/P4b_report.md`, `docs/controls.md`).
AUTONOMY MODE: work continuously P3 -> P7, no stops, no questions (brief top block).
"""
s = re.sub(r"\A# STATUS.*?AUTONOMY MODE:[^\n]*\n", head, s, count=1, flags=re.S)
if end and "P5 end" not in s:
    s = s.replace("P4 end 2026-10-14T18:58:24Z, P4b end 2026-10-14T21:27:23Z.", f"P4 end 2026-10-14T18:58:24Z, P4b end 2026-10-14T21:27:23Z, P5 end {end}.")
p5 = """## P5 test map (decisions D-081 ... D-083)
- Scene `Assets/Scenes/TestMap.unity` (`Tools/Hellcat/Build Test Map`, `TestMapBuilder`, which also writes
  `docs/p5/map_layout.json`); player `-executeMethod Hellcat.EditorTools.Build.BuildTasks.BuildTestMap` ->
  `Builds/TestMap/HellcatTestMap.exe`. Shared rig of every game scene: `Editor/Build/GameRigBuilder.cs`.
- Debris: `Sim/Props/PropFactory.cs` (barrel, box, cone, fence panel), `Game/World/PropField.cs` (`IDynamicBodySource`,
  rigid views, Ctrl+R reset); obstacles: `StaticBoxSource`, `StaticCylinderSource`, `StaticPrismSource` (convex prisms);
  spawns: `SpawnPoint` (`holdThrough` for drivable lanes).
- Check: `HellcatTestMap.exe -scenario mapcheck [-mapOut dir] [-mapSettleOnly 1]` -> `docs/p5/mapcheck/`; then
  `tools\\p5\\annotate_map.py` and `tools\\gate_p5.py`.
- Open for P6: closure rubber stops release on hard landings (D-034), headlamps detach at 30 km/h frontal; debris drawn rigid.
"""
if "## P5 test map" not in s:
    s = s.replace("## Architecture (short)", p5 + "\n## Architecture (short)")
s = re.sub(r"## Next \(plan\).*?(?=\n## Phase log)", """## Next (plan)
- **P6** scenarios S1-S8 on the test map (recorded inputs or programmatic speed hold / waypoints, each with a driven
  variant), metrics per scenario (pulse CFC 60, crush, broken beams, detached parts, energy vs time), captures (side +
  tracking camera, slow-motion replay >= 240 fps), crash series re-run with D-069, tuning (hood creases, closure stops,
  glass strength, S8 cabin), sensitivity sweep; gate G-Crash for every scenario.
- P7 build + README + cost report; interior LOD (brief 4.12).
""", s, count=1, flags=re.S)
if "| P5 |" not in s.split("## Phase log")[1]:
    s = s.rstrip("\n") + f"\n| P5 | done | {g['verdict']} ({g['fails']} fail, {g['warns']} warn) | docs/gates/gate_p5.md, docs/P5_report.md |\n"
sp.write_text(s, encoding="utf-8")
print("STATUS updated")
