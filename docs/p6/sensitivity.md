# P6 sensitivity sweep (brief 15.5)

Each parameter at x0.8 and x1.2 of the tuned value, everything else unchanged; S1 at 56 km/h (NHTSA full-width frontal), S5 at 80 km/h (ramp landing). Values from the run results and the pulses (CFC 60, tools/gate_p6.py).

## S1 at 56 km/h

| parameter | scale | dynamic_crush_m | residual_crush_m | pulse_ms | peak_cfc60_g | plastic_kJ | broken_beams | max_deformation_m | intrusion_max_cm |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 1 | 0.551 | 0.359 | 65 | 55.5 | 141 | 0 | 0.424 | 1.2 |
| rail_deform | 0.8 | 0.559 | 0.406 | 64 | 54.1 | 145 | 0 | 0.505 | 0.7 |
| rail_deform | 1.2 | 0.546 | 0.385 | 65 | 56.5 | 136 | 0 | 0.516 | 0.2 |
| rail_strength | 0.8 | 0.551 | 0.359 | 65 | 55.5 | 141 | 0 | 0.424 | 1.2 |
| rail_strength | 1.2 | 0.551 | 0.359 | 65 | 55.5 | 141 | 0 | 0.424 | 1.2 |
| clip_strength | 0.8 | 0.551 | 0.359 | 65 | 55.5 | 141 | 0 | 0.424 | 1.2 |
| clip_strength | 1.2 | 0.551 | 0.359 | 65 | 55.5 | 141 | 0 | 0.424 | 1.2 |
| tire_pressure | 0.8 | 0.545 | 0.393 | 65 | 47.5 | 143 | 0 | 0.492 | 0.7 |
| tire_pressure | 1.2 | 0.555 | 0.461 | 65.5 | 53.6 | 147 | 0 | 0.596 | 0.2 |
| damper_rate | 0.8 | 0.55 | 0.399 | 64 | 51.4 | 139 | 0 | 0.531 | 0.1 |
| damper_rate | 1.2 | 0.564 | 0.457 | 66.5 | 56.7 | 146 | 0 | 0.602 | 0.1 |

## S5 at 80 km/h

| parameter | scale | airborne_s | landing_vy | peak_vertical_cfc60_g | underbody_contact | rim_contact | plastic_kJ | broken_beams | max_deformation_m |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 1 | 1.17 | -6.11 | 15.3 | 32 | 0 | 10 | 0 | 0.194 |
| tire_pressure | 0.8 | 1.16 | -6.03 | 16.5 | 32 | 0 | 10.5 | 0 | 0.195 |
| tire_pressure | 1.2 | 1.17 | -6.14 | 14.7 | 29 | 0 | 8.28 | 0 | 0.193 |
| damper_rate | 0.8 | 1.18 | -6.13 | 16.7 | 30 | 0 | 9.25 | 0 | 0.193 |
| damper_rate | 1.2 | 1.14 | -5.92 | 15.6 | 30 | 0 | 9.91 | 0 | 0.195 |

