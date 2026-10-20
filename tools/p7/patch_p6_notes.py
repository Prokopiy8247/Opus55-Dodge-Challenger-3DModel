"""P7: the P6 report notes updated to the final series (hood crease 0.3, D-104; the series run again on the final build)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
p = ROOT / "docs/p6/report_notes.md"
s = p.read_text(encoding="utf-8")
reps = [
    ("""crash cans) was scaled x0.7 to match its static crush (D-096; tuning rows P6-006a-c in `docs/tuning_log.csv`).""",
     """crash cans) was scaled x0.7 to match its static crush (D-096; tuning rows P6-006a-c in `docs/tuning_log.csv`). The numbers
below are the final car (P7: hood crease strip at 0.3, D-104; the whole series run again on the final build)."""),
    ("""| static crush at bumper level (C1..C6) | 573-642 mm, mean 608 mm | 615 mm (bumper beam set-back 466 mm + 149 mm fascia stand-off) |
| largest static crush (centre line) | 740 mm | 701 mm (bumper beam centre 552 mm + 149 mm) |
| cabin pulse | - (not in the report's data sheets) | 52 g peak (CFC 60), cabin at rest after 63 ms, mean 25 g |
| rebound | 2.67 m/s | 4.0 m/s |
| wheelbase | 155 / 149 mm shorter | not shortened (reading -17 / -34 mm, within its +-20 mm pose noise) |
| door openings | 1-6 mm narrower after the test | up to 8 / 9 mm during the crash |
| doors | closed during the impact, operable | latches hold (latch force up to 1.5 kN) |""",
     """| static crush at bumper level (C1..C6) | 573-642 mm, mean 608 mm | 574 mm (bumper beam set-back 425 mm + 149 mm fascia stand-off) |
| largest static crush (centre line) | 740 mm | 671 mm (bumper beam centre 522 mm + 149 mm) |
| cabin pulse | - (not in the report's data sheets) | 51 g peak (CFC 60), cabin at rest after 64 ms, mean 25 g |
| rebound | 2.67 m/s | 4.0 m/s |
| wheelbase | 155 / 149 mm shorter | not shortened (reading -22 / -19 mm, within its +-20 mm pose noise) |
| door openings | 1-6 mm narrower after the test | up to 6 / 7 mm during the crash |
| doors | closed during the impact, operable | latches hold (latch force up to 1.3 kN) |"""),
    ("""The crush matches; the rebound and the wheelbase do not:""",
     """The crush is inside the NCAP band (at its low end: with the stiffer hood strip of D-104 the residual set-back came out
41 mm shorter than the 615 mm of the calibration run; the sweep shows the residual measure moving by a few cm with small
changes, the dynamic crush - 0.563 m - by less than 1 cm); the rebound and the wheelbase do not match:"""),
    ("""deformable honeycomb barrier, so this run is the harsher one): the struck side crushes 1.02 m against 0.35 m on the other,
the struck wheel is driven back (left wheelbase 124 mm shorter), the car yaws off the wall. IIHS structure measures (static,
against the rear cabin): firewall 8.0 cm, upper hinge pillar 0.9 cm, rocker, toe pan, dash and steering column 0.1 cm or less:
the 'good' band (up to 15 cm). The latches hold; the struck door's aperture distorts by up to 19 mm during the crash.""",
     """deformable honeycomb barrier, so this run is the harsher one): the struck side crushes 1.00 m against 0.31 m on the other,
the struck wheel is driven back (left wheelbase 128 mm shorter), the car yaws off the wall. IIHS structure measures (static,
against the rear cabin): firewall 8.0 cm, upper hinge pillar 1.0 cm, steering column 0.3 cm, rocker, toe pan and dash 0.1 cm
or less: the 'good' band (up to 15 cm). The latches hold; the struck door's aperture distorts by up to 23 mm during the crash."""),
    ("""- **S1 full frontal, 30-64 km/h**: bumper beam, crash cans and front rails crumple (dynamic crush 0.28 / 0.41 / 0.50 / 0.57 /
  0.62 m, residual 0.21 / 0.32 / 0.37 / 0.47 / 0.50 m, plastic work 37 / 74 / 117 / 146 / 177 kJ), the hood folds at its
  crease strip and rises 0.34 m at 50 km/h, the headlamps stay on their ductile brackets, no structural beam breaks, the cabin
  stays intact (intrusion 0.2 cm or less, latches closed, roof 3 cm). Peaks 33 / 39 / 48 / 52 / 83 g (CFC 60) in 55-70 ms
  pulses: at 64 km/h the tyres and the engine bay are crushed solid and the pulse stiffens.""",
     """- **S1 full frontal, 30-64 km/h**: bumper beam, crash cans and front rails crumple (dynamic crush 0.28 / 0.40 / 0.51 / 0.56 /
  0.63 m, residual 0.23 / 0.32 / 0.41 / 0.43 / 0.51 m, plastic work 37 / 73 / 121 / 149 / 178 kJ), the hood folds at its
  crease strip and rises 0.32-0.39 m, the headlamps stay on their ductile brackets, no structural beam breaks, the cabin
  stays intact (intrusion 0.3 cm or less, latches closed, roof 3 cm). Peaks 33 / 39 / 45 / 51 / 84 g (CFC 60) in 56-69 ms
  pulses: at 64 km/h the tyres and the engine bay are crushed solid and the pulse stiffens."""),
    ("""- **S3 centred pole, 30-50 km/h**: the pole drives the bumper beam's middle back 0.59 / 0.77 / 1.00 m - twice the wall's
  0.52 m at 50 km/h - and the cabin travels 1.03 m before it stops; the pulse is long and soft, as pole impacts
  are (27 g CFC 60 over 127 ms); the passenger cell is not reached (intrusion 0.3 cm).""",
     """- **S3 centred pole, 30-50 km/h**: the pole drives the bumper beam's middle back 0.59 / 0.79 / 0.98 m - twice the wall's
  0.50 m at 50 km/h - and the cabin travels 1.02 m before it stops; the pulse is long and soft, as pole impacts
  are (22 g CFC 60 over 124 ms); at 50 km/h the pole reaches the hood latch, which tears, and the hood springs open (0.71 m);
  the passenger cell is not reached (intrusion 0.3 cm)."""),
    ("""- **S8 full frontal at 120 km/h**: 1.13 m dynamic and 0.80 m residual crush, 608 kJ of plastic work (5.2 times S1 50), the
  front wheels driven back 34-40 cm, both mirrors torn off, the roof skin buckles 11 cm, the door apertures distort by up to
  25 mm, the hood folds up against the wall; 144 g peak (CFC 60) in a 55 ms pulse. The passenger cell keeps its shape (static intrusion
  3.3 cm at the firewall, 10 cm during the pulse) - see open point 1.""",
     """- **S8 full frontal at 120 km/h**: 1.13 m dynamic and 0.80 m residual crush, 607 kJ of plastic work (5.0 times S1 50), the
  front wheels driven back 30-32 cm, both mirrors torn off, the hood latch torn, the roof skin buckles 11 cm, the door
  apertures distort by up to 25 mm; 144 g peak (CFC 60) in a 56 ms pulse. The passenger cell keeps its shape (static intrusion
  2.9 cm at the firewall, 9.7 cm during the pulse) - see open point 1."""),
    ("""  0.4-0.5 s and glances off; the struck wheel breaks its tie rod and a subframe mount at every speed (it is knocked back 23 cm
  at 50 km/h), plastic work 0.8 / 2.4 / 10.7 kJ.""",
     """  0.4-0.5 s and glances off; the struck wheel breaks its tie rod and a subframe mount at every speed, plastic work 0.8 / 2.4 /
  10.9 kJ."""),
    ("""  take-off speed within 10 %), landing at 5.1-6.1 m/s vertical (14-17 g CFC 60) with 21-30 underbody nodes on the pad; no beam breaks (the closure stops hold, D-095), 2-9 kJ of plastic work
  in the suspension and the underbody.""",
     """  take-off speed within 10 %), landing at 5.1-6.1 m/s vertical (14-17 g CFC 60) with 21-30 underbody nodes on the pad; no beam
  breaks (the closure stops hold, D-095), 2-9 kJ of plastic work in the suspension and the underbody."""),
    ("""- **S7 debris, 10-20 km/h** (run again in P7 with the sleeping debris of D-098): 34-37 of the 46 props move (thrown up to
  16 / 19 / 17 m); light damage (1.6-2.6 kJ), most of it from the fence panels at the far end of the field - at 15 km/h a
  panel tears the left mirror off, at 10 and 20 km/h the car meets them differently, so the series is not monotonic (a gate
  warning).""",
     """- **S7 debris, 10-20 km/h**: 35-36 of the 46 props move (thrown up to 15 / 20 / 20 m); light damage (1.7-2.0 kJ), most of it
  from the fence panels at the far end of the field - at 20 km/h a panel tears the left mirror off, at 10 and 15 km/h the car
  meets them differently, so the series is not monotonic (a gate warning)."""),
    ("""   the front wheels driven back 34-40 cm do not load the hinge pillars,""",
     """   the front wheels driven back 30-32 cm do not load the hinge pillars,"""),
]
for a, b in reps:
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)
p.write_text(s, encoding="utf-8")
print("ok")
