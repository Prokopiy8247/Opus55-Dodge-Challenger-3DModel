"""P3b: material-stiffness sensitivity of the front compliance steer with the K-member, rack ties and a kingpin camber
element (80k): tie rod, knuckle, arm, subframe."""
import copy
import sys

sys.path.insert(0, "tools/skeleton")
sys.path.insert(0, "tools/p3b")
import front_struct_study as fs  # noqa: E402

base = copy.deepcopy(fs.p)


def with_mats(**kw):
    p2 = copy.deepcopy(base)
    for m in p2["materials"]:
        if m["name"] in kw:
            m["spring"] = kw[m["name"]]
    fs.p = p2


print("---- sensitivity (K-member + rack ties + camber 80k)")
for label, kw in [("as is", {}), ("tierod 8M", {"tierod": 8e6}), ("knuckle 10M", {"knuckle": 10e6}),
                  ("arm 5M", {"arm": 5e6}), ("subframe 3M", {"subframe": 3e6}),
                  ("tierod 8M knuckle 10M arm 5M", {"tierod": 8e6, "knuckle": 10e6, "arm": 5e6}),
                  ("all four", {"tierod": 8e6, "knuckle": 10e6, "arm": 5e6, "subframe": 3e6})]:
    with_mats(**kw)
    fs.run(label, ["kmember", "racktie"], kc=80000.0)
