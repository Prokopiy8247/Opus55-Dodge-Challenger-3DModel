"""One-off patch (P3): softer seat mounts, a centre-bearing material, heavier bumper-beam crush-can stations."""
import re
import sys
from pathlib import Path

hs = Path(sys.argv[1])
s = hs.read_text(encoding="utf-8")
a = '''    for q in ds[1:]:
        B.anchor(q, pool, "mount_trans", k=3, max_d=0.7)'''
if a not in s:
    sys.exit("dshaft anchor not found")
s = s.replace(a, a.replace('"mount_trans"', '"center_bearing"'))
for old, new in (
    ('back_row.append(list(B.pair(f"bbR_b{int(x * 100)}", (x, yb, bb["z"]), "cell", "body", w=2.0, cage=True)))',
     'back_row.append(list(B.pair(f"bbR_b{int(x * 100)}", (x, yb, bb["z"]), "cell", "body", w=3.2 if x == 0.45 else 2.0, cage=True)))'),
    ('front_row.append(list(B.pair(f"bbR_f{int(x * 100)}", (x, yb + bb["depth"], bb["z"]), "cell", "body", w=2.0,',
     'front_row.append(list(B.pair(f"bbR_f{int(x * 100)}", (x, yb + bb["depth"], bb["z"]), "cell", "body", w=3.2 if x == 0.45 else 2.0,')):
    if old not in s:
        sys.exit("bumper row not found: " + old[:60])
    s = s.replace(old, new)
hs.write_text(s, encoding="utf-8", newline="\n")
pp = Path(sys.argv[2])
t = pp.read_text(encoding="utf-8")
t2 = re.sub(r'\{ "name": "seat_mount",\s+"spring": 500000,', '{ "name": "seat_mount",    "spring": 300000,', t)
if t2 == t:
    sys.exit("seat_mount not found")
anchor = '    { "name": "driveshaft",'
if '"center_bearing"' not in t2:
    t2 = t2.replace(anchor, '    { "name": "center_bearing", "spring": 300000, "damp": 30, "strength": 20000 },\n' + anchor, 1)
pp.write_text(t2, encoding="utf-8", newline="\n")
print("patched")
