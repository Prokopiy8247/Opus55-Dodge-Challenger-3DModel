"""One-off (P3b): decision D-054 (front anti-roll-bar lever tips back at x 0.62, steering damper, T6 drop criterion kept)."""
from pathlib import Path

P = Path("docs/decisions.md")
s = P.read_text(encoding="utf-8")
row = ("| D-054 | 2026-10-13 | Front anti-roll-bar lever tips back at x 0.62 (D-051 had moved them to 0.70 to make the drop link "
       "vertical), the front bar 2950 N m/rad for the same 110 kN m/rad at the wheels (`tools/p3b/arb_tune2.py`), and a steering "
       "damper: the front alignment element damps the toe rate of the steered knuckles relative to the body frame, "
       "`steerDamping` 20 N m s/rad (the toe has no spring there; the rack holds it). The T6 drop criterion stays at 4 s / "
       "1 cm/s (D-039). | After D-051 the 0.2 m drop took 5.9 s to settle (limit 4 s; 2.9 s before): X20 bisected the package - "
       "the K-member alone took it to 6.4 s - and showed two lightly damped modes: the 1.7 kg lever tips swinging fore-aft at "
       "30 Hz (at x 0.70 both levers lay almost along the bar) and both front wheels yawing at 12 Hz on the stuck tire "
       "patches (the steering system against the tires' twist; the tie-rod dampers give 1.4 N m s/rad about the kingpin, "
       "and the stiffer K-member cradle no longer dissipated it). Tips at 0.62 and 15-30 N m s/rad of steering damping "
       "(zeta ~0.1 of that mode, like a power-steering gear) settle the drop in 3.45 s with 7 mm/s left; bushing damping "
       "(arms 300) and a higher tire damp-group rate added nothing. |")
P.write_text(s.rstrip("\n") + "\n" + row + "\n", encoding="utf-8")
print("appended D-054")
