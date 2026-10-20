"""Print a dynamics results file (P3b helper): one line per check, failures marked XX."""
import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "docs/p3b/validation/dynamics_results.json"
d = json.load(open(path))
for t in d["tests"]:
    if len(sys.argv) > 2 and t["id"] not in sys.argv[2].split(","):
        continue
    print(t["id"], "PASS" if t["pass"] else "FAIL", t["seconds"])
    for c in t["checks"]:
        flag = "    " if c.get("info") else (" ok " if c["pass"] else " XX ")
        v = c["value"]
        vs = "None" if v is None else "%.4g" % v
        print("  %s %s = %s %s | %s" % (flag, c["name"], vs, c["unit"], c["limit"]))
    for n in t.get("notes", []):
        print("   note:", n[:300])
