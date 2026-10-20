"""One-off source patch (P3, D-030): mechanism-free mounts in hskel (drive shaft, exhaust, radiator, rear seat, subframe)."""
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
rep = [
    ("""    B.chain(ds, "driveshaft")
    for q in (st["tunnel"][4], st["tunnel"][5]):
        B.beam(ds[1], q, "mount_trans")""",
     """    B.chain(ds, "driveshaft")
    for q in (st["tunnel"][4], st["tunnel"][5]):
        B.beam(ds[1], q, "mount_trans")
    # centre bearing and the rear shaft node held in 3D (a straight chain is a mechanism, D-030)
    pool = st["tunnel"] + st["floor"]["R"] + st["floor"]["L"]
    for q in ds[1:]:
        B.anchor(q, pool, "mount_trans", k=3, max_d=0.7)"""),
    ("""        for k in (2, 4, 6, 7):
            for t in B.nearest(B.P(ids[k]), B.cage, k=2, max_d=0.45):
                B.beam(ids[k], t, "exhaust_hanger", bg="exhaust")""",
     """        for k in range(1, len(ids)):                     # every node hung in 3D (the pipe is nearly straight)
            B.anchor(ids[k], B.cage, "exhaust_hanger", k=3, max_d=0.6, bg="exhaust")"""),
    ("""    for q in rad:
        for t in B.nearest(B.P(q), [core[k] for k in core], k=2, max_d=0.30):
            B.beam(q, t, "lamp_mount")""",
     """    pool = [core[k] for k in core] + [n for s_ in ("R", "L") for sec in st["frail"][s_][3:] for n in sec] + [st["xm2"]]
    for q in rad:
        B.anchor(q, pool, "lamp_mount", k=3, max_d=0.6)"""),
    ("""    for q in rs:
        for t in B.nearest(B.P(q), B.cage, k=2, max_d=0.40):
            B.beam(q, t, "seat_mount")""",
     """    for q in rs:
        B.anchor(q, B.cage, "seat_mount", k=3, max_d=0.6)"""),
    ("""    B.beam(sub["cf"], sub["ca"], "subframe")
    B.beam(sub[("R", "m")], sub[("L", "m")], "subframe")""",
     """    B.beam(sub["cf"], sub["ca"], "subframe")
    B.beam(sub[("R", "m")], sub[("L", "m")], "subframe")
    for s in ("R", "L"):                    # the subframe frame is nearly flat: cross it vertically
        B.beam(sub[(s, "f")], sub[("L" if s == "R" else "R", "m")], "subframe")"""),
    ("""    for q in diff:
        for t in (sub[("R", "m")], sub[("L", "m")], sub["cf"], sub["ca"]):
            B.beam(q, t, "subframe_mount", bg="differential")""",
     """    for q in diff:
        for t in (sub[("R", "m")], sub[("L", "m")], sub["cf"], sub["ca"]):
            B.beam(q, t, "subframe_mount", bg="differential")
    for c in (sub["cf"], sub["ca"]):
        B.anchor(c, diff + [sub[(s_, k_)] for s_ in ("R", "L") for k_ in ("f", "m", "a")], "subframe", k=3, max_d=0.7)"""),
]
for a, b in rep:
    if a not in s:
        sys.exit("not found: " + a[:90])
    s = s.replace(a, b)
p.write_text(s, encoding="utf-8", newline="\n")
print("patched", p)
