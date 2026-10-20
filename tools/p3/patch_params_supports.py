"""One-off params patch (P3, D-030): materials of the panel out-of-plane supports."""
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
anchor = """    { "name": "plastic_brace", "spring": 22000,   "damp": 8,   "deform": 350,   "hardening": 3000,   "deformCap": 2400 },"""
add = anchor + """
    // out-of-plane supports of single-layer panels to the cage (D-030): soft, plastic (dents stay), never inverted
    { "name": "panel_support",      "spring": 25000, "damp": 6, "deform": 400, "hardening": 3000, "deformCap": 2500, "deformLimitMin": 0.4 },
    { "name": "panel_support_bolt", "spring": 25000, "damp": 6, "deform": 400, "hardening": 3000, "deformCap": 2500, "deformLimitMin": 0.4, "strength": 3500 },
    { "name": "plastic_support",    "spring": 12000, "damp": 6, "deform": 250, "hardening": 2000, "deformCap": 1500, "deformLimitMin": 0.4, "strength": 1500 },"""
if anchor not in s:
    sys.exit("anchor not found")
if "panel_support" not in s:
    s = s.replace(anchor, add)
p.write_text(s, encoding="utf-8", newline="\n")
print("ok")
