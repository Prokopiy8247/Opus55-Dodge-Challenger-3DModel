"""One-off source patch (P3, D-030): out-of-plane supports of the single-layer panels in hskel.build_panels."""
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
rep = [
    ("""        weld_edges(B, ids, "weld", k=2, max_d=0.32)
        out[f"quarter_{s}"] = ids""",
     """        weld_edges(B, ids, "weld", k=2, max_d=0.32)
        B.support_surface(ids, "panel_support", k=2)
        out[f"quarter_{s}"] = ids"""),
    ("""            for t in B.nearest(B.P(q), list(ids.ravel()), k=2, max_d=0.20):
                B.beam(q, t, "weld")
    out["roof"] = ids""",
     """            for t in B.nearest(B.P(q), list(ids.ravel()), k=2, max_d=0.20):
                B.beam(q, t, "weld")
    B.support_surface(ids, "panel_support", k=2, max_d=0.55)
    out["roof"] = ids"""),
    ("""        weld_edges(B, ids, "bolt", edges=("top", "start"), k=2, max_d=0.25)
        out[f"fender_{side}"] = ids""",
     """        weld_edges(B, ids, "bolt", edges=("top", "start"), k=2, max_d=0.25)
        B.support_surface(ids, "panel_support_bolt", k=2)
        out[f"fender_{side}"] = ids"""),
    ("""            for t in B.nearest(B.P(q), list(out[f].ravel()), k=1, max_d=0.14, min_d=0.03):
                B.beam(q, t, "clip", bg="bumper_F")
    out["fascia"] = ids""",
     """            for t in B.nearest(B.P(q), list(out[f].ravel()), k=1, max_d=0.14, min_d=0.03):
                B.beam(q, t, "clip", bg="bumper_F")
    B.support_surface(ids, "plastic_support", k=2, bg="bumper_F", bgt=1)
    out["fascia"] = ids"""),
    ("""            for t in B.nearest(B.P(q), list(out[f].ravel()), k=1, max_d=0.14, min_d=0.03):
                B.beam(q, t, "clip", bg="bumper_R")
    out["rbumper"] = ids""",
     """            for t in B.nearest(B.P(q), list(out[f].ravel()), k=1, max_d=0.14, min_d=0.03):
                B.beam(q, t, "clip", bg="bumper_R")
    B.support_surface(ids, "plastic_support", k=2, bg="bumper_R", bgt=1)
    out["rbumper"] = ids"""),
]
for a, b in rep:
    if a not in s:
        sys.exit("not found: " + a[:90])
    s = s.replace(a, b)
p.write_text(s, encoding="utf-8", newline="\n")
print("patched", p)
