"""One-off source patch (P3, D-030): closure seals, frameless-glass seals, column / seat / bulkhead anchors in hskel."""
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
rep = [
    # helper after weld_edges
    ('''def build_panels(B, V, st):''',
     '''def seal_edges(B, ids, pool, mat, bg, edges=("start", "end", "bottom", "top"), max_d=0.16):
    """Weatherstrip of a closed closure: each perimeter node of the outer skin to the nearest body node. The
    seals belong to the latch group (passive), so they let go when the latch breaks (D-030)."""
    ni, nj = ids.shape
    border = set()
    if "bottom" in edges:
        border |= {ids[i, 0] for i in range(ni)}
    if "top" in edges:
        border |= {ids[i, nj - 1] for i in range(ni)}
    if "start" in edges:
        border |= {ids[0, j] for j in range(nj)}
    if "end" in edges:
        border |= {ids[ni - 1, j] for j in range(nj)}
    n = 0
    for a in sorted(border):
        for t in B.nearest(B.P(a), pool, k=1, max_d=max_d, min_d=0.02):
            B.beam(a, t, mat, bg=bg, bgt=1)
            n += 1
    return n


def build_panels(B, V, st):'''),
    # doors: seals on the rear, bottom and front edges
    ('''            B.beam(latch, t, "latch", bg=f"{part}_latch")
        out[part] = (outer, inner)''',
     '''            B.beam(latch, t, "latch", bg=f"{part}_latch")
        seal_edges(B, outer, B.cage, "seal", f"{part}_latch", edges=("start", "end", "bottom"))
        out[part] = (outer, inner)'''),
    # hood: seals all round (aprons, core, cowl)
    ('''                    B.beam(outer[i, j], t, "stop", type="SUPPORT")
    out["hood"] = (outer, inner)''',
     '''                    B.beam(outer[i, j], t, "stop", type="SUPPORT")
    seal_edges(B, outer, B.cage, "seal", "hood_latch", max_d=0.20)
    out["hood"] = (outer, inner)'''),
    # deck lid: seals to the cage and the quarter panels
    ('''        B.beam(lt, t, "latch", bg="trunk_latch")
    out["trunk"] = (outer, inner)''',
     '''        B.beam(lt, t, "latch", bg="trunk_latch")
    seal_edges(B, outer, B.cage + list(out["quarter_R"].ravel()) + list(out["quarter_L"].ravel()), "seal", "trunk_latch",
               max_d=0.20)
    out["trunk"] = (outer, inner)'''),
    # frameless door glass: top edge against the roof rail weatherstrip
    ('''            for t in B.nearest(B.P(gin[i, 0]), top_i + top_o, k=2, max_d=0.30, min_d=0.03):
                B.beam(gin[i, 0], t, "glass_mount", bg=part)
        st[part] = ids''',
     '''            for t in B.nearest(B.P(gin[i, 0]), top_i + top_o, k=2, max_d=0.30, min_d=0.03):
                B.beam(gin[i, 0], t, "glass_mount", bg=part)
        rails = [n for sec in st["rail"][s] for n in sec]
        for i in range(ids.shape[0]):           # frameless glass: top edge sealed against the roof rail
            for t in B.nearest(B.P(ids[i, ids.shape[1] - 1]), rails, k=1, max_d=0.16, min_d=0.02):
                B.beam(ids[i, ids.shape[1] - 1], t, "seal", bg=f"door_{side}_latch", bgt=1)
        st[part] = ids'''),
    # column anchors
    ('''    B.beam(c_top, st["fw"][("L", T.FIREWALL["z"][1])], "column")
    st["column"] = (c_top, c_mid)''',
     '''    B.beam(c_top, st["fw"][("L", T.FIREWALL["z"][1])], "column")
    pool = st["dash"] + list(st["cowl"]) + st["hinge"]["L"] + [st["fw"][k] for k in st["fw"]]
    B.anchor(c_mid, pool, "dash", k=3, max_d=0.7)
    B.anchor(c_top, pool, "column", k=3, max_d=0.8)
    st["column"] = (c_top, c_mid)'''),
    # front seat mounts in 3D
    ('''        for q in base:
            for t in B.nearest(B.P(q), st["floor"][s] + st["tunnel"] + [n_ for sec in st["sill"][s] for n_ in sec], k=2,
                               max_d=0.45):
                B.beam(q, t, "seat_mount", bg=f"seat_{side}")''',
     '''        for q in base:
            B.anchor(q, st["floor"][s] + st["tunnel"] + [n_ for sec in st["sill"][s] for n_ in sec], "seat_mount", k=3,
                     max_d=0.5, bg=f"seat_{side}")'''),
]
for a, b in rep:
    if a not in s:
        sys.exit("not found: " + a[:90])
    s = s.replace(a, b)
# bulkhead centre anchor at the end of build_cage
a = '''    st["shelf"], st["bulk"] = shelf, bulk
    return st'''
b = '''    B.anchor(bulk[0], B.cage, "cell_brace", k=3, max_d=0.6)
    st["shelf"], st["bulk"] = shelf, bulk
    return st'''
if a not in s:
    sys.exit("bulk anchor not found")
s = s.replace(a, b)
p.write_text(s, encoding="utf-8", newline="\n")
print("patched", p)
