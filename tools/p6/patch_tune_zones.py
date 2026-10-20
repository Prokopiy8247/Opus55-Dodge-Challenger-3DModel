import io
p = r"W:/YouTube/3D Model Dodge Challenger/tools/p6/tune.py"
s = io.open(p, encoding="utf-8").read()
a = '''    "stops_lamps2": {"stop_closure": {"longBound": 2.0},
                     "lamp_mount": {"deform": 2000, "hardening": 8000, "deformCap": 6000, "strength": 4500}},
}
'''
b = '''    "stops_lamps2": {"stop_closure": {"longBound": 2.0},
                     "lamp_mount": {"deform": 2000, "hardening": 8000, "deformCap": 6000, "strength": 4500}},
    # + hood crease initiators: the front strip (rows 5-7 of the skin, the inner frame's front bay) yields early, so the
    # hood folds at its leading edge instead of arching as one panel
    "crease30": {"stop_closure": {"longBound": 2.0},
                 "lamp_mount": {"deform": 1500, "hardening": 6000, "deformCap": 4000, "strength": 3000},
                 "@zones": HOOD.format(s=0.3)},
    "crease20": {"stop_closure": {"longBound": 2.0},
                 "lamp_mount": {"deform": 1500, "hardening": 6000, "deformCap": 4000, "strength": 3000},
                 "@zones": HOOD.format(s=0.2)},
}
'''
assert s.count(a) == 1
s = s.replace(a, b)
a = "# candidate -> {material: {field: value}} (absolute values; None removes the field)\n"
b = ('HOOD = (\'{{ "part": "hood", "materials": ["panel", "panel_brace", "panel_inner", "panel_link"], "min": [-1.0, 0.0, 1.93], \'\n'
     '        \'"max": [1.0, 2.0, 2.40], "deformScale": {s}, "hardeningScale": {s}, "capScale": {s} }}\')\n\n' + a)
assert s.count(a) == 1
s = s.replace(a, b)
a = "    for mat, fields in CANDIDATES[cand].items():\n"
b = ("    zones = CANDIDATES[cand].get(\"@zones\")\n"
     "    if zones:\n"
     "        text = text.replace('  \"surfaces\": [', '  \"materialZones\": [\n    ' + zones + '\n  ],\n  \"surfaces\": [', 1)\n"
     "    for mat, fields in CANDIDATES[cand].items():\n"
     "        if mat.startswith(\"@\"):\n            continue\n")
assert s.count(a) == 1
s = s.replace(a, b)
io.open(p, "w", encoding="utf-8").write(s)
print("ok")
