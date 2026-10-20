"""P6: tunnelling through a plate is a node path crossing the plate's far face inside its outline (tracked every chunk),
not merely a node behind the plate: a crumpled fender folding over a guardrail's top edge and hanging behind the
beam went round it (S6 at 70 km/h)."""
import io

p = r"W:/YouTube/3D Model Dodge Challenger/Unity/HellcatSandbox/Assets/Game/Scenario/CrashMetrics.cs"
raw = io.open(p, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")
start = s.index("        /// <summary>Colliding nodes inside one of the obstacle's primitives deeper than <paramref name=\"tol\"/>, or through a\n")
end = s.index("        /// <summary>Front of the cabin (the cabin nodes' largest coordinate along")
new = '''        // plate crossings (TrackPlates): each colliding node's position at the previous check and the plate it came through
        float3[] prevPos;
        int[] throughPrim;

        /// <summary>The obstacle's plates (boxes with one thin axis: a wall, a guardrail beam, a slab): thin axis and the
        /// sign of the side <paramref name="from"/> lies on (-1 at the box's negative face), or axis -1.</summary>
        void Plates(int[] prims, float3 from, out int[] axis, out float[] side)
        {
            axis = new int[prims.Length];
            side = new float[prims.Length];
            for (int k = 0; k < prims.Length; k++)
            {
                var prim = w.prims[prims[k]];
                axis[k] = -1;
                if (prim.type != PrimType.Box) continue;
                float3 h = prim.halfExtents;
                int ax = h.x <= h.y && h.x <= h.z ? 0 : (h.y <= h.z ? 1 : 2);
                float mid = ax == 0 ? math.min(h.y, h.z) : ax == 1 ? math.min(h.x, h.z) : math.min(h.x, h.y);
                if (h[ax] >= 0.6f * mid) continue;
                axis[k] = ax;
                float3 qf = math.rotate(math.conjugate(prim.rotation), from - prim.center);
                side[k] = qf[ax] < 0f ? -1f : 1f;
            }
        }

        /// <summary>Call every chunk near the obstacle: a colliding node whose path since the last call crosses a plate's
        /// far face inside its outline came through the plate; it counts as tunnelled while it stays behind. A node that
        /// went round an edge (over a guardrail's top, past its end) crosses the far face's plane outside the outline.</summary>
        public void TrackPlates(int[] prims, float3 from)
        {
            if (prims == null || prims.Length == 0)
                return;
            if (prevPos == null)
            {
                prevPos = new float3[b.nodeCount];
                throughPrim = new int[b.nodeCount];
                for (int i = 0; i < b.nodeCount; i++)
                {
                    prevPos[i] = w.pos[b.nodeStart + i];
                    throughPrim[i] = -1;
                }
                return;
            }
            Plates(prims, from, out var axis, out var side);
            for (int i = 0; i < b.nodeCount; i++)
            {
                int g = b.nodeStart + i;
                float3 x1 = w.pos[g], x0 = prevPos[i];
                prevPos[i] = x1;
                if ((w.nodeFlags[g] & NodeFlag.StaticCollision) == 0) continue;
                for (int k = 0; k < prims.Length; k++)
                {
                    int ax = axis[k];
                    if (ax < 0) continue;
                    var prim = w.prims[prims[k]];
                    var inv = math.conjugate(prim.rotation);
                    float3 q0 = math.rotate(inv, x0 - prim.center), q1 = math.rotate(inv, x1 - prim.center);
                    float3 h = prim.halfExtents;
                    float a0 = q0[ax] * side[k], a1 = q1[ax] * side[k];   // > -h: in front of the far face
                    if (throughPrim[i] == prims[k] && a1 > -h[ax])
                        throughPrim[i] = -1;                              // back in front: no longer through
                    if (!(a0 > -h[ax] && a1 < -h[ax]))
                        continue;
                    float t = (-h[ax] - a0) / (a1 - a0);
                    float3 qc = q0 + t * (q1 - q0);
                    bool inside = true;
                    for (int a = 0; a < 3; a++)
                        if (a != ax && math.abs(qc[a]) >= h[a]) inside = false;
                    if (inside)
                        throughPrim[i] = prims[k];
                }
            }
        }

        /// <summary>Colliding nodes inside one of the obstacle's primitives deeper than <paramref name="tol"/>, or behind a
        /// plate they came through (<see cref="TrackPlates"/>).</summary>
        public int Tunnelled(int[] prims, float3 from, float tol, List<string> names = null)
        {
            if (prims == null || prims.Length == 0)
                return 0;
            int n = 0;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
            {
                if ((w.nodeFlags[i] & NodeFlag.StaticCollision) == 0) continue;
                float3 x = w.pos[i];
                int via = throughPrim != null ? throughPrim[i - b.nodeStart] : -1;
                float depth = -1f;
                int hit = via;
                if (via < 0)
                    foreach (int p in prims)
                    {
                        var prim = w.prims[p];
                        if (!(math.all(x > prim.aabbMin - 0.01f) && math.all(x < prim.aabbMax + 0.01f))) continue;
                        float s = StaticSdf.Distance(prim, w.planes, x, out _);
                        if (s < -tol)
                        {
                            depth = -s;
                            hit = p;
                            break;
                        }
                    }
                if (via < 0 && depth < 0f) continue;
                n++;
                names?.Add(via >= 0 ? $"{def.nodes[i - b.nodeStart].name} (y {x.y:F2}, through primitive {via})"
                                    : $"{def.nodes[i - b.nodeStart].name} (y {x.y:F2}, {depth:F3} m inside primitive {hit})");
            }
            return n;
        }

'''
s = s[:start] + new + s[end:]
io.open(p, "w", encoding="utf-8", newline="").write(s.replace("\n", nl))
print("ok")
