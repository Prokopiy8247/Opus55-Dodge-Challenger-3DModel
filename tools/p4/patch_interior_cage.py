"""One-off (P4): the interior (CH_Int_* bound to the body part) binds to the passenger cell's cage only - sills, floor,
tunnel, pillars, roof rails and bows, dash, cowl, firewall, shelf, bulkhead, wheel houses, steering column - not to the
outer skin panels (roof, quarters), the crush zones or the suspension and driveline nodes of the body part: the trim then
follows the cell, which stays intact in a frontal crash, instead of blending skin panels that flex in the pulse."""
from pathlib import Path

p = Path("Unity/HellcatSandbox/Assets/Editor/Car/CarImporter.cs")
s = p.read_text(encoding="utf-8")
o = '''            (new Regex(@"^CH_HalfShaft_(?<S>L|R)$"), @"^R{S}_(axle_in|axle_out)$|^diff\\d$"),
        };'''
n = '''            (new Regex(@"^CH_HalfShaft_(?<S>L|R)$"), @"^R{S}_(axle_in|axle_out)$|^diff\\d$"),
            // interior on the body: the passenger cell's cage only (not the skin panels, crush zones or chassis nodes)
            (new Regex(@"^CH_Int_(?!DoorCard|Seat)"),
                @"^(sill|floor|tunnel|hinge|aplo|bp\\d|cp\\d|rail\\d|dash|cowl\\d|cowl_C|fw_|hdrF|bowB|hdrR|shelf|bulk|xm|whouse|column_)"),
        };'''
assert s.count(o) == 1, "rules"
s = s.replace(o, n)
p.write_text(s, encoding="utf-8")
print("patched")
