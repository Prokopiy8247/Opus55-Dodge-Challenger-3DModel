"""One-off patch (P3, D-031): stiffness-proportional weighting of the cell node masses in hskel.distribute_mass."""
import sys
from pathlib import Path

hs = Path(sys.argv[1])
s = hs.read_text(encoding="utf-8")
a = '''    # cell mass: weights, then a linear tilt along y so the centre of mass hits the 57 / 43 split
    w = np.array([B.weight[i] for i in cell])'''
b = '''    # cell mass: weights scaled by the attached stiffness (D-031: a node carrying stiffer beams gets more mass, so the
    # local frequencies sqrt(sum k / m) even out and the stability measure S drops), then a linear tilt along y so
    # the centre of mass hits the 57 / 43 split
    ks = cell_stiffness(B, cell)
    med = float(np.median(ks))
    w = np.array([B.weight[i] for i in cell]) * (np.maximum(ks, 0.3 * med) / med) ** T.CELL_STIFFNESS_EXP'''
if a not in s:
    sys.exit("distribute_mass anchor not found")
s = s.replace(a, b)
a = '''def distribute_mass(B):'''
b = '''def cell_stiffness(B, cell):
    """Sum of the spring constants (params.json) of the beams at each cell node."""
    import json
    import re
    path = os.path.join(PROJECT_ROOT, "sim", "vehicle", "hellcat", "params.json")
    text = re.sub(r"//[^\n]*", "", open(path, encoding="utf-8").read())
    k = {m["name"]: max(m.get("spring", 0.0), 0.0) for m in json.loads(text)["materials"]}
    tot = {}
    for bm in B.sk.beams:
        kb = k.get(bm["mat"], 0.0)
        tot[bm["a"]] = tot.get(bm["a"], 0.0) + kb
        tot[bm["b"]] = tot.get(bm["b"], 0.0) + kb
    return np.array([tot.get(i, 0.0) for i in cell])


def distribute_mass(B):'''
s = s.replace(a, b, 1)
hs.write_text(s, encoding="utf-8", newline="\n")
tb = Path(sys.argv[2])
t = tb.read_text(encoding="utf-8")
if "CELL_STIFFNESS_EXP" not in t:
    t = t.rstrip("\n") + "\n\n# cell node mass weights x (attached stiffness / median) ** CELL_STIFFNESS_EXP (D-031)\nCELL_STIFFNESS_EXP = 0.5\n"
tb.write_text(t, encoding="utf-8", newline="\n")
print("patched")
