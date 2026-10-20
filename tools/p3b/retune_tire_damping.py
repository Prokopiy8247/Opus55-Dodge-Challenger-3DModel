"""One-off (P3b): tire damping retune from the rig loss study (D-043), rim saturating damping, tire contact damping,
mesh rolling-resistance share; flat-tire inflation share."""
from pathlib import Path

P = Path("sim/vehicle/hellcat/params.json")
s = P.read_text(encoding="utf-8")


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:100]
    s = s.replace(old, new)


rep('''    { "name": "rim",           "spring": 400000,  "damp": 20 },
    { "name": "rim_spoke",     "spring": 250000,  "damp": 20 },''',
    '''    // rim: damping saturates above 0.3 m/s like the carcass (D-043); the rim rings ring at the 24-section rolling
    // frequency at speed (40 kW of the rig wheel's losses at 324 km/h were the rim dampers)
    { "name": "rim",           "spring": 400000,  "damp": 20, "velSplit": 0.3, "dampFast": 0, "dampReboundFast": 0 },
    { "name": "rim_spoke",     "spring": 250000,  "damp": 20, "velSplit": 0.3, "dampFast": 0, "dampReboundFast": 0 },''')
rep('''    { "name": "tire_side",     "spring": 95000,   "damp": 40,  "strength": 60000, "velSplit": 0.3, "dampFast": 0, "dampReboundFast": 0, "inflationShare": 0.8 },
    { "name": "tire_side_diag","spring": 40000,   "damp": 25, "velSplit": 0.3, "dampFast": 0, "dampReboundFast": 0, "inflationShare": 0.8 },''',
    '''    { "name": "tire_side",     "spring": 95000,   "damp": 20,  "strength": 60000, "velSplit": 0.3, "dampFast": 0, "dampReboundFast": 0, "inflationShare": 0.95 },
    { "name": "tire_side_diag","spring": 40000,   "damp": 12.5, "velSplit": 0.3, "dampFast": 0, "dampReboundFast": 0, "inflationShare": 0.95 },''')
rep('''    { "name": "tire_tread",    "spring": 230000,  "damp": 15, "velSplit": 0.3, "dampFast": 0, "dampReboundFast": 0 },
    { "name": "tire_tread_lat","spring": 130000,  "damp": 15, "velSplit": 0.3, "dampFast": 0, "dampReboundFast": 0 },
    { "name": "tire_tread_diag","spring": 115000,  "damp": 12, "velSplit": 0.3, "dampFast": 0, "dampReboundFast": 0 }''',
    '''    { "name": "tire_tread",    "spring": 230000,  "damp": 7.5, "velSplit": 0.3, "dampFast": 0, "dampReboundFast": 0 },
    { "name": "tire_tread_lat","spring": 130000,  "damp": 7.5, "velSplit": 0.3, "dampFast": 0, "dampReboundFast": 0 },
    { "name": "tire_tread_diag","spring": 115000,  "damp": 6, "velSplit": 0.3, "dampFast": 0, "dampReboundFast": 0 }''')
rep('''    { "name": "tire", "rate": 12, "vCap": 0.3, "spin": true }''',
    '''    { "name": "tire", "rate": 4, "vCap": 0.3, "spin": true }''')
P.write_text(s, encoding="utf-8")
print("ok")
