"""P7: docs/README.md - the crash table to the final series (D-104) and the measured frame rates (docs/p7 drive tests)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
p = ROOT / "docs/README.md"
s = p.read_text(encoding="utf-8")
start = s.index("| Scenario | Result |")
end = s.index("\n\n", start)
table = """| Scenario | Result |
|---|---|
| S1 full frontal, 50 km/h | 0.51 m crush, 45 g peak (CFC 60) over 68 ms, hood folded, cabin intact |
| S1 at 56 km/h vs the 2013 Challenger NHTSA NCAP test | static crush 574 mm vs 573-642 mm (calibrated); 51 g peak |
| S2 40 % offset, 64 km/h | struck side 1.00 m, IIHS-style intrusion "good" (8 cm), latches hold |
| S3 centred pole, 50 km/h | the pole goes 1.0 m into the front (twice the wall), soft 22 g pulse, the hood latch tears |
| S4 barrier row at 20 deg, 40 km/h | slides 0.4 s along the barriers, tie rod and a subframe mount break |
| S5 ramp, 80 km/h | 1.17 s in the air over 24 m, lands at 6.1 m/s, no beam breaks |
| S6 guardrail scrape, 70 km/h | 0.8 s along the rail, 116 fascia supports and clips torn |
| S7 debris, 10-20 km/h | 35-36 of 46 props moved; at 20 km/h a fence panel tears the left mirror off |
| S8 full frontal, 120 km/h | 1.13 m crush, 607 kJ of plastic work, 144 g peak, mirrors torn off |"""
s = s[:start] + table + s[end:]
d = json.loads((ROOT / "docs/p7/drive/drive_test.json").read_text(encoding="utf-8"))
q = json.loads((ROOT / "docs/p7/drive1440/drive_test.json").read_text(encoding="utf-8"))
worst = min(x["fps_mean"] for x in d["segments"])
worstq = min(x["fps_mean"] for x in q["segments"])
perf = (f"physics at 2,000 Hz (x{d['realtime_factor']:.2f} real time, {d['step_us_per_substep']:.0f} us per substep with the debris "
        f"asleep), {d['fps_mean']:.0f} fps on average at 1600 x 900 ({worst:.0f} fps or more in every camera view) and "
        f"{q['fps_mean']:.0f} fps at 2560 x 1440 full screen ({worstq:.0f} or more); input latency {d['latency_ms_mean']:.0f} ms.")
assert "__PERF__" in s
s = s.replace("__PERF__", perf)
p.write_text(s, encoding="utf-8")
print(perf)
