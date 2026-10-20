"""One-off (P4, D-058): a body inserted into the collision grid only for its own self-colliding nodes inserts only the
triangles near those nodes (the Hellcat's 16 headlamp / mirror / radiator nodes made every substep hash all 1,924 body
triangles: physics 170 -> 296 us per substep)."""
from pathlib import Path

ROOT = Path("Unity/HellcatSandbox/Assets/Sim/Core")


def edit(name, pairs):
    p = ROOT / name
    s = p.read_text(encoding="utf-8")
    for o, n in pairs:
        assert s.count(o) == 1, (name, o[:80])
        s = s.replace(o, n)
    p.write_text(s, encoding="utf-8")


edit("DynamicCollision.cs", [
    ('''        [NativeDisableContainerSafetyRestriction] public NativeArray<byte> bodyOthers;   // another body's triangles are near''',
     '''        [NativeDisableContainerSafetyRestriction] public NativeArray<byte> bodyOthers;   // another body's triangles are near
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int2> bodySelf;     // start, count in selfNodes
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> selfNodes;     // self-colliding nodes by body'''),
    ('''            for (int b = 0; b < nb; b++)
            {
                byte ins = (byte)((bodyColl[b] & 2) != 0 ? 1 : 0);
                if (ins == 0)
                    for (int c = 0; c < nb; c++)
                    {
                        if (c == b || (bodyColl[c] & 1) == 0)
                            continue;
                        if (math.all(bodyLo[b] - margin <= bodyHi[c] + margin) && math.all(bodyLo[c] - margin <= bodyHi[b] + margin))
                        {
                            ins = 1;
                            break;
                        }
                    }
                bodyInsert[b] = ins;
                any |= ins;
            }''',
     '''            // 1: all of the body's triangles (another colliding body is near); 2: only those near its own self-colliding
            // nodes (D-058: a car's few self-colliding parts must not make every substep hash all its triangles)
            for (int b = 0; b < nb; b++)
            {
                byte ins = 0;
                for (int c = 0; c < nb; c++)
                {
                    if (c == b || (bodyColl[c] & 1) == 0)
                        continue;
                    if (math.all(bodyLo[b] - margin <= bodyHi[c] + margin) && math.all(bodyLo[c] - margin <= bodyHi[b] + margin))
                    {
                        ins = 1;
                        break;
                    }
                }
                if (ins == 0 && (bodyColl[b] & 2) != 0)
                    ins = 2;
                bodyInsert[b] = ins;
                any |= ins;
            }'''),
    ('''            int inserted = 0;
            for (int t = 0; t < tris.Length; t++)
            {
                CollTri tr = tris[t];
                if (bodyInsert[tr.body] == 0 || (tr.breakGroup >= 0 && groupDone[tr.breakGroup] != 0))
                    continue;''',
     '''            int inserted = 0;
            for (int t = 0; t < tris.Length; t++)
            {
                CollTri tr = tris[t];
                if (!Wanted(tr, margin))
                    continue;'''),
    ('''            for (int t = 0; t < tris.Length; t++)
            {
                CollTri tr = tris[t];
                if (bodyInsert[tr.body] == 0 || (tr.breakGroup >= 0 && groupDone[tr.breakGroup] != 0))
                    continue;
                CellRange(tr, margin, inv, out int3 c0, out int3 c1);
                int cells = 0;
                for (int x = c0.x; x <= c1.x; x++)
                for (int y = c0.y; y <= c1.y; y++)
                for (int z = c0.z; z <= c1.z; z++)
                {
                    if (++cells > MaxCellsPerTri)''',
     '''            for (int t = 0; t < tris.Length; t++)
            {
                CollTri tr = tris[t];
                if (!Wanted(tr, margin))
                    continue;
                CellRange(tr, margin, inv, out int3 c0, out int3 c1);
                int cells = 0;
                for (int x = c0.x; x <= c1.x; x++)
                for (int y = c0.y; y <= c1.y; y++)
                for (int z = c0.z; z <= c1.z; z++)
                {
                    if (++cells > MaxCellsPerTri)'''),
    ('''        void CellRange(in CollTri tr, float margin, float inv, out int3 c0, out int3 c1)''',
     '''        /// <summary>Insert this triangle? Its body must be inserted, the triangle not broken off, and for a body inserted
        /// only for its own self-colliding nodes one of them must lie within the margin of the triangle's box.</summary>
        bool Wanted(in CollTri tr, float margin)
        {
            byte ins = bodyInsert[tr.body];
            if (ins == 0 || (tr.breakGroup >= 0 && groupDone[tr.breakGroup] != 0))
                return false;
            if (ins == 1)
                return true;
            float3 a = pos[tr.a], b = pos[tr.b], c = pos[tr.c];
            float3 lo = math.min(a, math.min(b, c)) - margin, hi = math.max(a, math.max(b, c)) + margin;
            int2 r = bodySelf[tr.body];
            for (int k = r.x; k < r.x + r.y; k++)
            {
                float3 p = pos[selfNodes[k]];
                if (math.all(p >= lo) && math.all(p <= hi))
                    return true;
            }
            return false;
        }

        void CellRange(in CollTri tr, float margin, float inv, out int3 c0, out int3 c1)'''),
])

edit("SoftBodyWorld.cs", [
    ('''        NativeArray<int2> bodyNodes;''', '''        NativeArray<int2> bodyNodes, bodySelf;
        NativeArray<int> selfNodes;'''),
    ('''            bodyOthers = Alloc<byte>(bodies.Count);''', '''            bodyOthers = Alloc<byte>(bodies.Count);
            // self-colliding nodes by body: the grid inserts a body's triangles near them only (D-058)
            bodySelf = Alloc<int2>(bodies.Count);
            var selfList = new List<int>();
            for (int bi = 0; bi < bodies.Count; bi++)
            {
                var bb = bodies[bi];
                int s0 = selfList.Count;
                for (int i = 0; i < bb.nodeCount; i++)
                    if ((bb.def.nodes[i].flags & NodeFlag.SelfCollision) != 0)
                        selfList.Add(bb.nodeStart + i);
                bodySelf[bi] = new int2(s0, selfList.Count - s0);
            }
            selfNodes = Alloc<int>(math.max(selfList.Count, 1));
            for (int k = 0; k < selfList.Count; k++)
                selfNodes[k] = selfList[k];'''),
    ('''                bodyOthers = bodyOthers,
                bucketStart = bucketStart,''',
     '''                bodyOthers = bodyOthers,
                bodySelf = bodySelf,
                selfNodes = selfNodes,
                bucketStart = bucketStart,'''),
])
print("patched")
