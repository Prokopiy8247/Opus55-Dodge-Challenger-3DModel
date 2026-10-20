"""One-off source patch (P3, D-030): coarser inner glass layer, heavier bumper-beam top rows."""
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
old_pane = s[s.index("def glass_pane(B, G, part, mat):"):s.index("def build_glass(B, V, st, panels):")]
new_pane = '''def glass_pane(B, G, part, mat):
    """A pane as two layers 2 cm apart, so it has bending stiffness across its plane like curved glass (a single
    layer has none, D-030): the outer layer (collision, skinning) and a coarser inner layer (every second node, no
    collision) linked to the outer nodes around each inner node. Returns (outer, inner) node grids."""
    outer = B.grid(part, G, part, part, "glass", w=1.0)
    Gi = offset_in(G, GLASS_GAP)[::2, ::2]
    inner = B.grid(f"{part}_in", Gi, part, part, "glass", flags=F_NOCOL, w=1.0)
    B.grid_beams(outer, mat, mat, skip=False, bg=part)
    B.grid_beams(inner, mat, mat, skip=False, bg=part)
    ni, nj = outer.shape
    for I in range(inner.shape[0]):
        for J in range(inner.shape[1]):
            for i in range(2 * I - 1, 2 * I + 2):
                for j in range(2 * J - 1, 2 * J + 2):
                    if 0 <= i < ni and 0 <= j < nj:
                        B.beam(outer[i, j], inner[I, J], mat, bg=part, bgt=1)
    B.grid_tris(outer, part, inside_point, bg=part)
    return outer, inner


'''
s = s.replace(old_pane, new_pane)
a = '''            for t in B.nearest(B.P(ids[i, 1]), top_i, k=1, max_d=0.40):
                B.beam(ids[i, 1], t, "glass_mount", bg=part)
            for t in B.nearest(B.P(gin[i, 0]), top_i + top_o, k=2, max_d=0.30, min_d=0.03):
                B.beam(gin[i, 0], t, "glass_mount", bg=part)'''
b = '''            for t in B.nearest(B.P(ids[i, 1]), top_i, k=1, max_d=0.40):
                B.beam(ids[i, 1], t, "glass_mount", bg=part)
        for i in range(gin.shape[0]):
            for t in B.nearest(B.P(gin[i, 0]), top_i + top_o, k=2, max_d=0.30, min_d=0.03):
                B.beam(gin[i, 0], t, "glass_mount", bg=part)'''
if a not in s:
    sys.exit("door glass mount block not found")
s = s.replace(a, b)
for x in ('B.node("bbF_t_C", (0.0, yb, bb["z"] + 0.08), "cell", "body", w=1.6, cage=True)',
          'B.pair(f"bbF_t{int(x * 100)}", (x, yb, bb["z"] + 0.08), "cell", "body", w=1.6, cage=True)',
          'B.node("bbR_t_C", (0.0, yb, bb["z"] + 0.08), "cell", "body", w=1.4, cage=True)',
          'B.pair(f"bbR_t{int(x * 100)}", (x, yb, bb["z"] + 0.08), "cell", "body", w=1.4, cage=True)'):
    if x not in s:
        sys.exit("bumper top not found: " + x)
    s = s.replace(x, x.replace("w=1.6", "w=2.6").replace("w=1.4", "w=2.6"))
p.write_text(s, encoding="utf-8", newline="\n")
print("patched", p)
