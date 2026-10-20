"""One-off patch (P3, D-036): suspension wind-up bars and the drive torque reaction on the differential.

1. Torsion bars get a break group (the wheel's part): a wind-up bar must stop when its wheel is torn off.
2. Wind-up bars: one torsion bar per corner about the axle line, upper knuckle node -> axle nodes -> a body anchor
   straight above the hub (front apron2_*, rear shelf68_*): resists the knuckle's rotation about the spin axis relative to
   the body, which the stability-limited link stiffness cannot (7 / 5 kN m/rad measured; real corners 50-300).
3. Drive torque reaction: the drive couple on a driven wheel's rim is reacted on the differential nodes (body), through the
   half-shaft, instead of on the knuckle; only the brake and rolling-resistance torques react on the knuckle (caliper,
   bearing). With the reaction on the knuckle the rear knuckles wound up under drive torque like under braking.
"""
from pathlib import Path

SIM = Path("Unity/HellcatSandbox/Assets/Sim")


def patch(path, reps):
    s = path.read_text(encoding="utf-8")
    for old, new in reps:
        assert s.count(old) == 1, (path.name, old[:120])
        s = s.replace(old, new)
    path.write_text(s, encoding="utf-8")


# ---------------------------------------------------------------- data
patch(SIM / "Data" / "VehicleDef.cs", [
    ('''        public string pressureGroup; // "" for wheels without a pressurized tire
    }''',
     '''        public string pressureGroup; // "" for wheels without a pressurized tire
        public int[] driveReaction;  // body nodes taking the drive torque reaction (the differential); empty: none driven
    }'''),
])

# ---------------------------------------------------------------- types
patch(SIM / "Vehicle" / "VehicleTypes.cs", [
    ('''        public int slotStart;                // rimCount + knuckleCount + 2 slots: rim nodes, knuckle nodes, axle inner, axle outer''',
     '''        public int slotStart;                // rimCount + knuckleCount + 2 + driveCount slots: rim nodes, knuckle nodes, axle
                                             // inner, axle outer, drive reaction nodes
        public int driveStart, driveCount;   // into driveNodes: the differential (drive torque reaction, D-036)'''),
])
patch(SIM / "Core" / "SimTypes.cs", [
    ('''        public int beam12, beam23, beam34;  // the bar is gone once one of these beams breaks (-1: no such beam)
        public int slotStart;               // 4 slots: n1, n2, n3, n4
        public int body;
    }''',
     '''        public int beam12, beam23, beam34;  // the bar is gone once one of these beams breaks (-1: no such beam)
        public int breakGroup;              // ... or once this break group fires (-1: none), e.g. a wind-up bar's wheel
        public int slotStart;               // 4 slots: n1, n2, n3, n4
        public int body;
    }'''),
])

# ---------------------------------------------------------------- force elements: break group
patch(SIM / "Core" / "ForceElements.cs", [
    ('''        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<byte> broken;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> slotForce;''',
     '''        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<byte> broken;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<byte> groupDone;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> slotForce;'''),
    ('''                ((tb.beam12 >= 0 && broken[tb.beam12] != 0) || (tb.beam23 >= 0 && broken[tb.beam23] != 0) ||
                 (tb.beam34 >= 0 && broken[tb.beam34] != 0)))''',
     '''                ((tb.beam12 >= 0 && broken[tb.beam12] != 0) || (tb.beam23 >= 0 && broken[tb.beam23] != 0) ||
                 (tb.beam34 >= 0 && broken[tb.beam34] != 0) || (tb.breakGroup >= 0 && groupDone[tb.breakGroup] != 0)))'''),
])

# ---------------------------------------------------------------- world
patch(SIM / "Core" / "SoftBodyWorld.cs", [
    # slot and node counts
    ('''                        nKnuckle += b.knuckles[w].Count;
                        nSlots += wd.rim.Length + b.knuckles[w].Count + 2;''',
     '''                        nKnuckle += b.knuckles[w].Count;
                        int nd = wd.driven != 0 ? (wd.driveReaction?.Length ?? 0) : 0;
                        nDrive += nd;
                        nSlots += wd.rim.Length + b.knuckles[w].Count + 2 + nd;'''),
    # torsion bar break group
    ('''                        strength = mat.strength > 0f ? mat.strength : float.MaxValue,
                        slotStart = slotCursor,
                        body = bi,
                    };
                    tb.beam12 = pairBeam.TryGetValue(PairKey(tb.n1, tb.n2), out int b12) ? b12 : -1;''',
     '''                        strength = mat.strength > 0f ? mat.strength : float.MaxValue,
                        slotStart = slotCursor,
                        body = bi,
                        breakGroup = -1,
                    };
                    if (!string.IsNullOrEmpty(td.bg))
                    {
                        int gi = b.groupNames.IndexOf(td.bg);
                        if (gi < 0)
                            throw new InvalidDataException($"{b.name}: torsion bar {t}: unknown break group '{td.bg}'");
                        tb.breakGroup = b.groupStart + gi;
                    }
                    tb.beam12 = pairBeam.TryGetValue(PairKey(tb.n1, tb.n2), out int b12) ? b12 : -1;'''),
    # wheel static: drive reaction range
    ('''                    knuckleStart = knCursor,
                    knuckleCount = b.knuckles[w].Count,
                    slotStart = slotCursor,''',
     '''                    knuckleStart = knCursor,
                    knuckleCount = b.knuckles[w].Count,
                    driveStart = drCursor,
                    driveCount = wd.driven != 0 ? (wd.driveReaction?.Length ?? 0) : 0,
                    slotStart = slotCursor,'''),
    ('''                slotOwner[slotCursor++] = ws.axleInner;
                slotOwner[slotCursor++] = ws.axleOuter;
                foreach (int tn in wd.tread)''',
     '''                slotOwner[slotCursor++] = ws.axleInner;
                slotOwner[slotCursor++] = ws.axleOuter;
                for (int k = 0; k < ws.driveCount; k++)
                {
                    driveNodes[drCursor++] = b.nodeStart + wd.driveReaction[k];
                    slotOwner[slotCursor++] = b.nodeStart + wd.driveReaction[k];
                }
                foreach (int tn in wd.tread)'''),
    ('''                broken = broken,
                slotForce = slotForce,
                torsionBars = torsionBars,''',
     '''                broken = broken,
                groupDone = groupDone,
                slotForce = slotForce,
                torsionBars = torsionBars,'''),
])

# the counters, allocation, cursor and job wiring need a look at the surrounding code: done below with anchors
w = SIM / "Core" / "SoftBodyWorld.cs"
s = w.read_text(encoding="utf-8")
# counter declaration next to nKnuckle
import re
m = re.search(r"int [^;]*\bnKnuckle = 0[^;]*;", s)
assert m, "nKnuckle declaration"
s = s[:m.end()] + " int nDrive = 0;" + s[m.end():]
# allocation next to knuckleNodes
m = re.search(r"\n(\s*)knuckleNodes = Alloc<int>\(([^;]*)\);", s)
assert m, "knuckleNodes alloc"
ind = m.group(1)
s = s[:m.end()] + f"\n{ind}driveNodes = Alloc<int>(math.max(nDrive, 1));" + s[m.end():]
# field declaration next to knuckleNodes
m = re.search(r"NativeArray<int>[^;]*\bknuckleNodes\b[^;]*;", s)
assert m, "knuckleNodes field"
s = s[:m.end()] + "\n        NativeArray<int> driveNodes;   // differential nodes of the driven wheels (drive torque reaction, D-036)" + s[m.end():]
# cursor: BuildVehicle signature and call
assert s.count("ref int knCursor)") == 1
s = s.replace("ref int knCursor)", "ref int knCursor, ref int drCursor)")
m = re.search(r"BuildVehicle\(b, slotOwner, ref rimCursor, ref treadCursor, ref slotCursor, ref refCursor, ref knCursor\)", s)
assert m, "BuildVehicle call"
s = s[:m.start()] + "BuildVehicle(b, slotOwner, ref rimCursor, ref treadCursor, ref slotCursor, ref refCursor, ref knCursor, ref drCursor)" + s[m.end():]
m = re.search(r"int [^;]*\bknCursor = 0[^;]*;", s)
assert m, "knCursor declaration"
s = s[:m.end()] + " int drCursor = 0;" + s[m.end():]
# control job wiring: next to knuckleNodes = knuckleNodes,
assert s.count("knuckleNodes = knuckleNodes,") == 1
s = s.replace("knuckleNodes = knuckleNodes,", "knuckleNodes = knuckleNodes,\n                    driveNodes = driveNodes,")
w.write_text(s, encoding="utf-8")

# ---------------------------------------------------------------- control job: split the reaction
patch(SIM / "Vehicle" / "VehicleControlJob.cs", [
    ('''        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> knuckleNodes;''',
     '''        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> knuckleNodes;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> driveNodes;'''),
    ('''                // Reaction couple on the knuckle nodes (f_i = -T (axis x r_i) / sum r^2: torque -T about the axis);
                // their net force is balanced on the two axle nodes, which lie on the axis.
                float kscale = denK > 1e-9f ? -total / denK : 0f;''',
     '''                // Reaction couples (D-036): the drive torque comes through the half-shaft from the differential, so the
                // differential nodes (body) take its reaction; the knuckle takes the brake (caliper) and rolling
                // resistance (bearing) torques. Without differential nodes the knuckle takes everything.
                float driveReact = ws.driveCount > 0 ? drive : 0f;
                // Reaction couple on the knuckle nodes (f_i = -T (axis x r_i) / sum r^2: torque -T about the axis);
                // their net force is balanced on the two axle nodes, which lie on the axis.
                float kscale = denK > 1e-9f ? -(total - driveReact) / denK : 0f;'''),
    ('''                slotForce[ws.slotStart + ws.rimCount + ws.knuckleCount] = -0.5f * fSum;
                slotForce[ws.slotStart + ws.rimCount + ws.knuckleCount + 1] = -0.5f * fSum;''',
     '''                slotForce[ws.slotStart + ws.rimCount + ws.knuckleCount] = -0.5f * fSum;
                slotForce[ws.slotStart + ws.rimCount + ws.knuckleCount + 1] = -0.5f * fSum;
                if (ws.driveCount > 0)
                {
                    // pure couple -drive about the axis on the differential: radii from the nodes' centroid (net force 0)
                    float3 dc = float3.zero;
                    for (int k = 0; k < ws.driveCount; k++)
                        dc += pos[driveNodes[ws.driveStart + k]];
                    dc /= ws.driveCount;
                    float denD = 0f;
                    for (int k = 0; k < ws.driveCount; k++)
                    {
                        float3 r = pos[driveNodes[ws.driveStart + k]] - dc;
                        r -= math.dot(r, axis) * axis;
                        denD += math.lengthsq(r);
                    }
                    float dscale = denD > 1e-9f ? -driveReact / denD : 0f;
                    int d0 = ws.slotStart + ws.rimCount + ws.knuckleCount + 2;
                    for (int k = 0; k < ws.driveCount; k++)
                    {
                        float3 r = pos[driveNodes[ws.driveStart + k]] - dc;
                        r -= math.dot(r, axis) * axis;
                        slotForce[d0 + k] = dscale * math.cross(axis, r);
                    }
                }'''),
])

# ---------------------------------------------------------------- skeleton builder
patch(Path("tools/blender/hcar/sk.py"), [
    ('''    def wheel(self, name, axle_inner, axle_outer, rim, tread, arm, driven, steered, brake, radius, pressure_group=""):
        self.wheels.append({"name": name, "axleInner": self.idx(axle_inner), "axleOuter": self.idx(axle_outer),
                            "rim": [self.idx(n) for n in rim], "tread": [self.idx(n) for n in tread],
                            "arm": self.idx(arm), "driven": int(driven), "steered": int(steered),
                            "brake": brake, "radius": float(radius), "pressureGroup": pressure_group})''',
     '''    def wheel(self, name, axle_inner, axle_outer, rim, tread, arm, driven, steered, brake, radius, pressure_group="",
              drive_reaction=()):
        """drive_reaction: body nodes taking the drive torque reaction (the differential, D-036)."""
        self.wheels.append({"name": name, "axleInner": self.idx(axle_inner), "axleOuter": self.idx(axle_outer),
                            "rim": [self.idx(n) for n in rim], "tread": [self.idx(n) for n in tread],
                            "arm": self.idx(arm), "driven": int(driven), "steered": int(steered),
                            "brake": brake, "radius": float(radius), "pressureGroup": pressure_group,
                            "driveReaction": [self.idx(n) for n in drive_reaction]})'''),
])
patch(Path("tools/blender/hcar/hskel.py"), [
    ('''        B.sk.wheel(name, w["ax_in"], w["ax_out"], w["rim_i"] + w["rim_o"], w["tread"], w["arm"], driven=not front,
                   steered=front, brake="front" if front else "rear", radius=0.352, pressure_group=f"tire_{name}")''',
     '''        B.sk.wheel(name, w["ax_in"], w["ax_out"], w["rim_i"] + w["rim_o"], w["tread"], w["arm"], driven=not front,
                   steered=front, brake="front" if front else "rear", radius=0.352, pressure_group=f"tire_{name}",
                   drive_reaction=() if front else st["diff"])'''),
    # front wind-up bar after the coil-over
    ('''        top = lo[1]
        B.beam(lbj, top, "spring_f", pre=1.0)''',
     '''        top = lo[1]
        windup_bar(B, ubj, w, f"apron2_{s}", "windup_f", part)
        B.beam(lbj, top, "spring_f", pre=1.0)'''),
    # rear wind-up bar after the coil-over
    ('''        B.beam(k_lo_r, st[f"rtower_{s}"], "bumpstop_r", type="BOUNDED", allow_duplicate=True)
        wheels[name] = dict(w, arm=k_up, lsh=k_lo_r, part=part)''',
     '''        B.beam(k_lo_r, st[f"rtower_{s}"], "bumpstop_r", type="BOUNDED", allow_duplicate=True)
        windup_bar(B, k_up, w, f"shelf68_{s}", "windup_r", part)
        wheels[name] = dict(w, arm=k_up, lsh=k_lo_r, part=part)'''),
    ('''def anti_roll_levers(B, prefix, axR, axL, tip_pos, group, pick):''',
     '''def windup_bar(B, wing, w, anchor, mat, part):
    """Wind-up bar (D-036): torsion bar about the axle line from the upper knuckle node to a body anchor straight above the
    hub. It resists the knuckle's rotation about the spin axis relative to the body (brake torque reaction), which the
    links cannot carry stiffly enough within the explicit stability limit (7 / 5 kN m/rad measured, real corners
    50-300). With the anchor on the hub's vertical the bar is blind to wheel travel (the knuckle keeps its orientation to
    the body over the travel, tools/p3/windup_bar.py): no extra wheel rate; front steer adds ~0.2 kN m/rad. It breaks
    with its wheel (break group = the wheel's part) and above the material strength."""
    a = B.sk.node_index[anchor]
    B.sk.torsion_bars.append({"n": [B.sk.idx(wing), B.sk.idx(w["ax_in"]), B.sk.idx(w["ax_out"]), a], "mat": mat,
                              "bg": part})


def anti_roll_levers(B, prefix, axR, axL, tip_pos, group, pick):'''),
])

# ---------------------------------------------------------------- params
patch(Path("sim/vehicle/hellcat/params.json"), [
    ('''    { "name": "arb_front",     "spring": 1990, "damp": 0 },''',
     '''    { "name": "arb_front",     "spring": 1990, "damp": 0 },
    // wind-up bars (D-036): knuckle rotation about the spin axis vs the body, N m/rad; strength = bushing tear-out torque
    { "name": "windup_f",      "spring": 100000, "damp": 15, "strength": 15000 },
    { "name": "windup_r",      "spring": 80000,  "damp": 10, "strength": 12000 },'''),
])
print("patched")
