"""One-off source patch (P3): knuckle reaction nodes and the brake holding-spring bound in SoftBodyWorld.cs."""
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
rep = [
    ("""            public int pretensionedBeams;""",
     """            public List<int>[] knuckles;             // per wheel: local indices of the knuckle reaction nodes
            public int pretensionedBeams;"""),
    ("""        NativeArray<int> rimNodes, treadNodes, refNodes;""",
     """        NativeArray<int> rimNodes, treadNodes, refNodes, knuckleNodes;"""),
    ("""        int nNodes = 0, nBeams = 0, nGroups = 0, nWheels = 0, nRim = 0, nTread = 0, nSlots = 0, nHydro = 0, nRef = 0;""",
     """        int nNodes = 0, nBeams = 0, nGroups = 0, nWheels = 0, nRim = 0, nTread = 0, nSlots = 0, nHydro = 0, nRef = 0, nKnuckle = 0;"""),
    ("""                    b.wheelCount = b.def.wheels.Length;
                    nWheels += b.wheelCount;
                    foreach (var w in b.def.wheels)
                    {
                        nRim += w.rim.Length;
                        nTread += w.tread.Length;
                        nSlots += w.rim.Length + 3;
                        nRef += 1;
                    }""",
     """                    b.wheelCount = b.def.wheels.Length;
                    nWheels += b.wheelCount;
                    b.knuckles = new List<int>[b.wheelCount];
                    for (int w = 0; w < b.wheelCount; w++)
                    {
                        var wd = b.def.wheels[w];
                        b.knuckles[w] = KnuckleNodes(b.def, wd);
                        nRim += wd.rim.Length;
                        nTread += wd.tread.Length;
                        nKnuckle += b.knuckles[w].Count;
                        nSlots += wd.rim.Length + b.knuckles[w].Count + 2;
                        nRef += 1;
                    }"""),
    ("""            treadNodes = Alloc<int>(math.max(nTread, 1));""",
     """            treadNodes = Alloc<int>(math.max(nTread, 1));
            knuckleNodes = Alloc<int>(math.max(nKnuckle, 1));"""),
    ("""            int rimCursor = 0, treadCursor = 0, slotCursor = 0, refCursor = 0, ptCursor = 0, ctCursor = 0, partCursor = 0;""",
     """            int rimCursor = 0, treadCursor = 0, slotCursor = 0, refCursor = 0, ptCursor = 0, ctCursor = 0, partCursor = 0, knCursor = 0;"""),
    ("""                    BuildVehicle(b, slotOwner, ref rimCursor, ref treadCursor, ref slotCursor, ref refCursor);""",
     """                    BuildVehicle(b, slotOwner, ref rimCursor, ref treadCursor, ref slotCursor, ref refCursor, ref knCursor);"""),
    ("""        void BuildVehicle(Body b, int[] slotOwner, ref int rimCursor, ref int treadCursor, ref int slotCursor, ref int refCursor)
        {""",
     """        /// <summary>
        /// Knuckle reaction nodes of a wheel: nodes braced to both axle nodes (the rigid knuckle), off the axis, not rim or
        /// tread. The drive / brake reaction couple is spread over them (a single light node on a short lever made the
        /// brake holding spring numerically stiff). Falls back to the wheel's arm node.
        /// </summary>
        static List<int> KnuckleNodes(VehicleDef def, WheelDef wd)
        {
            var nIn = new HashSet<int>();
            var nOut = new HashSet<int>();
            foreach (var bd in def.beams)
            {
                if (bd.a == wd.axleInner) nIn.Add(bd.b);
                if (bd.b == wd.axleInner) nIn.Add(bd.a);
                if (bd.a == wd.axleOuter) nOut.Add(bd.b);
                if (bd.b == wd.axleOuter) nOut.Add(bd.a);
            }
            var skip = new HashSet<int>(wd.rim);
            skip.UnionWith(wd.tread);
            skip.Add(wd.axleInner);
            skip.Add(wd.axleOuter);
            float3 ai = P(def, wd.axleInner), ao = P(def, wd.axleOuter);
            float3 axis = math.normalize(ao - ai);
            var list = new List<int>();
            foreach (int n in nIn)
            {
                if (!nOut.Contains(n) || skip.Contains(n))
                    continue;
                float3 r = P(def, n) - ai;
                r -= math.dot(r, axis) * axis;
                if (math.length(r) > 0.02f)
                    list.Add(n);
            }
            list.Sort();
            if (list.Count == 0)
                list.Add(wd.arm);
            return list;
        }

        static float3 P(VehicleDef def, int i) => new float3(def.nodes[i].p[0], def.nodes[i].p[1], def.nodes[i].p[2]);

        /// <summary>max_i r_i^2 / ((sum_j r_j^2)^2 m_i) of a set of nodes around the axis (couple compliance per node).</summary>
        float CoupleCompliance(Body b, int[] local, float3 axisPoint, float3 axis)
        {
            float sum = 0f;
            var r2 = new float[local.Length];
            for (int k = 0; k < local.Length; k++)
            {
                float3 r = pos0[b.nodeStart + local[k]] - axisPoint;
                r -= math.dot(r, axis) * axis;
                r2[k] = math.lengthsq(r);
                sum += r2[k];
            }
            float q = 0f;
            for (int k = 0; k < local.Length; k++)
                if (sum > 0f)
                    q = math.max(q, r2[k] * invMass[b.nodeStart + local[k]] / (sum * sum));
            return q;
        }

        void BuildVehicle(Body b, int[] slotOwner, ref int rimCursor, ref int treadCursor, ref int slotCursor, ref int refCursor,
            ref int knCursor)
        {"""),
    ("""                    treadStart = treadCursor,
                    treadCount = wd.tread.Length,
                    slotStart = slotCursor,""",
     """                    treadStart = treadCursor,
                    treadCount = wd.tread.Length,
                    knuckleStart = knCursor,
                    knuckleCount = b.knuckles[w].Count,
                    slotStart = slotCursor,"""),
    ("""                ws.rimInertia = math.max(inertia, 1e-3f);
                ws.stickK = brake.stickStiffness > 0f ? brake.stickStiffness : 0.15f * ws.rimInertia / (dt * dt);
                ws.stickC = brake.stickDamping > 0f ? brake.stickDamping : 2f * 0.3f * math.sqrt(ws.stickK * ws.rimInertia);""",
     """                ws.rimInertia = math.max(inertia, 1e-3f);
                ws.stickK = brake.stickStiffness > 0f ? brake.stickStiffness : 0.15f * ws.rimInertia / (dt * dt);
                ws.stickC = brake.stickDamping > 0f ? brake.stickDamping : 2f * 0.3f * math.sqrt(ws.stickK * ws.rimInertia);
                // The holding spring acts on every rim and knuckle node with k_i = K r_i^2 / (sum r^2)^2 (c_i likewise):
                // keep dt^2 k_i / m_i + 2 dt c_i / m_i <= 1 on every node (a factor 4 below the explicit limit).
                float q = math.max(CoupleCompliance(b, wd.rim, ai, axis), CoupleCompliance(b, b.knuckles[w].ToArray(), ai, axis));
                float load = q * (dt * dt * ws.stickK + 2f * dt * ws.stickC);
                if (load > 1f)
                {
                    ws.stickK /= load;
                    ws.stickC /= load;
                }"""),
    ("""                for (int k = 0; k < wd.rim.Length; k++)
                {
                    rimNodes[rimCursor++] = b.nodeStart + wd.rim[k];
                    slotOwner[slotCursor++] = b.nodeStart + wd.rim[k];
                }
                slotOwner[slotCursor++] = ws.arm;
                slotOwner[slotCursor++] = ws.axleInner;
                slotOwner[slotCursor++] = ws.axleOuter;""",
     """                for (int k = 0; k < wd.rim.Length; k++)
                {
                    rimNodes[rimCursor++] = b.nodeStart + wd.rim[k];
                    slotOwner[slotCursor++] = b.nodeStart + wd.rim[k];
                }
                foreach (int kn in b.knuckles[w])
                {
                    knuckleNodes[knCursor++] = b.nodeStart + kn;
                    slotOwner[slotCursor++] = b.nodeStart + kn;
                }
                slotOwner[slotCursor++] = ws.axleInner;
                slotOwner[slotCursor++] = ws.axleOuter;"""),
    ("""                rimNodes = rimNodes,
                treadNodes = treadNodes,""",
     """                rimNodes = rimNodes,
                knuckleNodes = knuckleNodes,
                treadNodes = treadNodes,"""),
]
for a, b in rep:
    if a not in s:
        sys.exit("not found: " + a[:80])
    s = s.replace(a, b)
p.write_text(s, encoding="utf-8", newline="\n")
print("patched", p)
