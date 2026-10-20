"""Writes docs/metrics.csv (brief deliverable D9): one row per scripted scenario run S1-S8 (P6 series on the test map) with the
metrics of brief 9 - cabin deceleration (CFC 60), crush, broken beams, detached parts, energies - from the gate's summary
docs/p6/scenario_summary.csv (tools/gate_p6.py).

Usage: tools/.venv/Scripts/python.exe tools/p7/write_metrics.py
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLUMNS = [
    ("scenario", "scenario"), ("what", "description"), ("target_kmh", "target_kmh"), ("entry_kmh", "entry_kmh"),
    ("impact_kmh", "impact_kmh"), ("peak_long_cfc60_g", "peak_decel_cfc60_g"), ("peak_res_cfc60_g", "peak_resultant_cfc60_g"),
    ("mean_g", "mean_decel_g"), ("pulse_ms", "pulse_ms"), ("rebound_mps", "rebound_mps"), ("dynamic_crush_m", "crush_dynamic_m"),
    ("residual_crush_m", "crush_residual_m"), ("max_deformation_m", "max_structure_deformation_m"), ("intrusion_max_cm", "cabin_intrusion_max_cm"),
    ("broken_beams", "broken_beams"), ("plastic_beams", "plastic_beams"), ("detached", "detached_parts"), ("plastic_kJ", "plastic_work_kJ"),
    ("damping_kJ", "damping_kJ"), ("contact_friction_loss_kJ", "contact_and_friction_loss_kJ"), ("energy_created_J", "energy_created_J"),
    ("hood_rise_m", "hood_rise_m"), ("airborne_s", "airborne_s"), ("landing_vert_cfc60_g", "landing_vertical_cfc60_g"),
    ("contact_s", "sliding_contact_s"), ("exit_kmh", "exit_kmh"), ("props_moved", "props_moved"), ("tunnelled", "tunnelled_nodes"),
    ("replay_identical", "replay_bit_identical"),
]


def main():
    src = ROOT / "docs/p6/scenario_summary.csv"
    rows = list(csv.DictReader(open(src, encoding="utf-8")))
    out = ROOT / "docs/metrics.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow([c for _, c in COLUMNS])
        for r in sorted(rows, key=lambda r: (r["scenario"], float(r["target_kmh"]))):
            w.writerow([r.get(k, "") for k, _ in COLUMNS])
    print(f"{len(rows)} runs -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
