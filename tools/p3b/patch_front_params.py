"""One-off (P3b, D-051): params for the front package - front knuckle and K-member materials, anti-roll-bar link / lever
rates, the front alignment element (camber about the kingpin), the steering lock."""
from pathlib import Path

P = Path("sim/vehicle/hellcat/params.json")
s = P.read_text(encoding="utf-8")


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:100]
    s = s.replace(old, new)


rep('''    { "name": "knuckle",       "spring": 4000000, "damp": 100 },''',
    '''    { "name": "knuckle",       "spring": 4000000, "damp": 100 },
    // front knuckle (D-051): the five-node knuckle carried 40-50 % of the front compliance steer; 6 MN/m keeps S at the body
    // limit with the lower ball joint 1.25x heavier in its group. K-member: lower-arm pivots and the rack tied into one cradle
    { "name": "knuckle_f",     "spring": 6000000, "damp": 100 },
    { "name": "kmember",       "spring": 1500000, "damp": 50,  "deform": 70000, "hardening": 300000, "strength": 220000 },''')
rep('''    { "name": "arb_link",      "spring": 800000,  "damp": 250 },
    { "name": "arb_lever",     "spring": 1200000, "damp": 250 },''',
    '''    // D-051: 0.8 / 1.2 MN/m left the bars at about half their rate (links, levers and the lower arm's shock node in series)
    { "name": "arb_link",      "spring": 2500000, "damp": 250 },
    { "name": "arb_lever",     "spring": 2500000, "damp": 250 },''')
rep('''  "steering": { "rate": 3.0, "returnRate": 4.0, "speedReductionStart": 15, "speedReductionAt60": 0.35, "wheelLockDeg": 33, "steeringWheelTurnsLockToLock": 2.6 },''',
    '''  "steering": { "rate": 3.0, "returnRate": 4.0, "speedReductionStart": 15, "speedReductionAt60": 0.35, "wheelLockDeg": 32, "steeringWheelTurnsLockToLock": 2.6 },''')
rep('''    { "name": "front", "stiffness": 200000, "damping": 150, "strength": 15000 },''',
    '''    // front alignment element (D-051): camber only, measured against the kingpin axis (the angle between the axle line and
    // the steering axis, which steering leaves unchanged); the toe is the rack's
    { "name": "front", "stiffness": 200000, "damping": 150, "strength": 15000,
      "camberStiffness": 80000, "camberDamping": 30, "camberStatic": -0.5, "camberGain": -22.9 },''')
P.write_text(s, encoding="utf-8")
print("patched params")
