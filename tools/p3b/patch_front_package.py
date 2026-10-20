"""One-off (P3b, D-051): front suspension package in hskel.py - tie-rod ends 40 mm outboard of the kingpin (Ackermann,
hydro factor 0.20), front knuckle beams on their own material, the front anti-roll-bar links on the lower ball joints
(the lever tips above them), a K-member (lower-arm pivots tied across the car) and rack-to-pivot ties, the lower ball
joint heavier inside its knuckle group (stability)."""
from pathlib import Path

P = Path("tools/blender/hcar/hskel.py")
s = P.read_text(encoding="utf-8")


def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (s.count(old), old[:120])
    s = s.replace(old, new)


rep('''    B.beam(ax_in, ax_out, "knuckle")
    for k in range(n):''', '''    B.beam(ax_in, ax_out, "knuckle_f" if front else "knuckle")
    for k in range(n):''')
rep('''        lbj = B.node(f"{name}_lbj", (sx * 0.745, cy, 0.165), kg, part, cmat="metal", flags=F_NOCOL)
        ubj = B.node(f"{name}_ubj", (sx * 0.715, cy - 0.02, 0.575), kg, part, cmat="metal", flags=F_NOCOL)
        tre = B.node(f"{name}_tre", (sx * 0.735, cy + 0.135, 0.255), kg, part, cmat="metal", flags=F_NOCOL)
        kn = [w["ax_in"], w["ax_out"], lbj, ubj, tre]
        for a in range(len(kn)):
            for b in range(a + 1, len(kn)):
                B.beam(kn[a], kn[b], "knuckle")''',
    '''        # the lower ball joint carries the spring, the damper and the anti-roll-bar link: heavier in the knuckle group
        # (exact stability, D-051)
        lbj = B.node(f"{name}_lbj", (sx * 0.745, cy, 0.165), kg, part, cmat="metal", flags=F_NOCOL, w=1.25)
        ubj = B.node(f"{name}_ubj", (sx * 0.715, cy - 0.02, 0.575), kg, part, cmat="metal", flags=F_NOCOL)
        # steering arm: tie-rod end 0.135 m ahead of the axle and 40 mm outboard of the kingpin, so the arms' extensions
        # meet behind the axle - about 50 % Ackermann for the front-mounted rack (D-051; inboard it was anti-Ackermann)
        tre = B.node(f"{name}_tre", (sx * 0.775, cy + 0.135, 0.255), kg, part, cmat="metal", flags=F_NOCOL)
        kn = [w["ax_in"], w["ax_out"], lbj, ubj, tre]
        for a in range(len(kn)):
            for b in range(a + 1, len(kn)):
                B.beam(kn[a], kn[b], "knuckle_f")''')
rep('''        # rack end (pinned to the housing and the rail), HYDRO tie rod to the steering arm: 33 deg
        # at the wheel needs ~74 mm of lateral arm travel on a 0.335 m tie rod -> hf 0.22
        rk = B.node(f"rack_{s}", (sx * 0.40, yrk, zrk), "rack", "body", cmat="metal", flags=F_NOCOL)
        B.pin(rk, [rack_c, fr[s][3][1], fr[s][3][2]], "subframe")
        B.beam(rk, fr[s][2][1], "subframe")
        B.mount(rk, "subframe_mount", k=3, max_d=0.45, bg=f"tierod_{name}", bgt=1)
        B.beam(rk, tre, "tierod", type="HYDRO", hydro="steering", hf=(0.22 if sx > 0 else -0.22), bg=f"tierod_{name}")
        rack[s] = rk
        wheels[name] = dict(w, arm=tre, lsh=lbj, arb_pick=lsh, part=part)''',
    '''        # rack end (pinned to the housing and the rail), HYDRO tie rod to the steering arm: +-20 % of the 0.375 m tie
        # rod turns the inner wheel 34 deg and the outer 30 deg at full lock (tools/p3b/steer_kinematics.py, D-051)
        rk = B.node(f"rack_{s}", (sx * 0.40, yrk, zrk), "rack", "body", cmat="metal", flags=F_NOCOL)
        B.pin(rk, [rack_c, fr[s][3][1], fr[s][3][2]], "subframe")
        B.beam(rk, fr[s][2][1], "subframe")
        B.mount(rk, "subframe_mount", k=3, max_d=0.45, bg=f"tierod_{name}", bgt=1)
        B.beam(rk, tre, "tierod", type="HYDRO", hydro="steering", hf=(0.20 if sx > 0 else -0.20), bg=f"tierod_{name}")
        rack[s] = rk
        # anti-roll-bar drop link on the lower ball joint: on the arm's shock node it bent the (nearly flat) arm and the
        # bar worked at half its rate (D-051)
        wheels[name] = dict(w, arm=tre, lsh=lbj, arb_pick=lbj, part=part, lca=(li_f, li_r))''')
rep('''    st["rack"] = rack
    st["wheels_front"] = wheels''',
    '''    st["rack"] = rack
    st["wheels_front"] = wheels
    # K-member: the lower-arm pivots tied across the car (and crosswise), the rack housing tied to them, so the pivots and
    # the rack move as one cradle - before, the pivots hung on the rails alone and the arms yawed under brake and side
    # forces (front compliance steer 1.1 deg/kN, D-051)
    (rf, rr), (lf, lr) = wheels["FR"]["lca"], wheels["FL"]["lca"]
    for a, b in ((rf, lf), (rr, lr), (rf, lr), (rr, lf), (rack["R"], rf), (rack["R"], rr), (rack["L"], lf), (rack["L"], lr),
                 (rack_c, rr), (rack_c, lr)):
        B.beam(a, b, "kmember")''')
rep('''    tips = anti_roll_levers(B, "arbF", axR, axL, {"R": (0.62, 1.52, 0.31), "L": (-0.62, 1.52, 0.31)}, "rack",''',
    '''    tips = anti_roll_levers(B, "arbF", axR, axL, {"R": (0.70, 1.52, 0.31), "L": (-0.70, 1.52, 0.31)}, "rack",''')
P.write_text(s, encoding="utf-8")
print("patched hskel")
