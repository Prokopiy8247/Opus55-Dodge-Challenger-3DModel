"""P6: gate_p4 reads the P6 pulse format (t, cabin velocity vector, along the lane, gap) through gate_p6.pulse_metrics."""
import io

p = r"W:/YouTube/3D Model Dodge Challenger/tools/gate_p4.py"
raw = io.open(p, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")
a = 'def pulse_metrics(path, wall_face=70.0):\n    rows = list(csv.reader(open(path)))[1:]\n'
b = ('def pulse_metrics(path, wall_face=70.0):\n'
     '    head = next(csv.reader(open(path)))\n'
     '    if "gap_m" in head:   # P6 format (test map lanes): the shared CFC 60 analysis of tools/gate_p6.py\n'
     '        from gate_p6 import pulse_metrics as p6\n'
     '        p = p6(path)\n'
     '        k0 = p["contact_index"]\n'
     '        return {"t": p["t"] - p["t"][k0], "acc": p["a_long"], "accf": p["a_long"], "v": p["vf"], "contact_index": k0,\n'
     '                "stop_index": p["stop_index"], "peak_cfc60_g": p["peak_long_g"], "mean_g": p["mean_g"], "pulse_ms": p["pulse_ms"],\n'
     '                "crush_m": p["crush_m"], "v_contact": p["v_contact"]}\n'
     '    rows = list(csv.reader(open(path)))[1:]\n')
assert s.count(a) == 1, s.count(a)
s = s.replace(a, b)
io.open(p, "w", encoding="utf-8", newline="").write(s.replace("\n", nl))
print("ok")
