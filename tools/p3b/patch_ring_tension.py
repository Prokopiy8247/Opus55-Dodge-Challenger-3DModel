"""One-off (P3b): ring hoop tension for spinning wheel groups (D-044) - patch the solver sources."""
from pathlib import Path

CORE = Path("Unity/HellcatSandbox/Assets/Sim/Core")


def patch(path, pairs):
    p = CORE / path
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:90])
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")


patch("SimTypes.cs", [(
    """        public short pressureGroup;           // -1: none; else the beam adds pretension * pressureScale[group] (D-028)
        public float pretension;              // N, tension at full inflation that balances the cavity pressure at spawn
    }""",
    """        public short pressureGroup;           // -1: none; else the beam adds pretension * pressureScale[group] (D-028)
        public float pretension;              // N, tension at full inflation that balances the cavity pressure at spawn
        public int spinGroup;                 // -1: none; else a ring beam of a spinning wheel group: tension spinCoef |w|^2
        public float spinCoef;                // N s^2: (m / L) R^2 of the ring, so the tension is the hoop tension mu v^2 (D-044)
    }""")])

patch("SimJobs.cs", [(
    """        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float> pressureScale;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float> rest;""",
    """        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float> pressureScale;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<DampGroupRigid> dampRigid; // wheel spin (D-044)
        [NativeDisableContainerSafetyRestriction] public NativeArray<float> rest;"""), (
    """            float pre = s.pressureGroup >= 0 ? s.pretension * pressureScale[s.pressureGroup] : 0f;""",
    """            float pre = s.pressureGroup >= 0 ? s.pretension * pressureScale[s.pressureGroup] : 0f;
            // D-044: a ring of a spinning wheel carries the hoop tension mu v^2 (rigid rotation of its group, previous
            // substep), under which the moving ring follows any shape without inertial forces (no centrifugal growth,
            // no impact where the tread turns from the round onto the flat contact patch)
            if (s.spinGroup >= 0)
            {
                DampGroupRigid rg = dampRigid[s.spinGroup];
                if (rg.valid != 0)
                    pre += s.spinCoef * (float)math.lengthsq(rg.w);
            }""")])

patch("GroupDampJob.cs", [(
    """                diss += math.dot(f, dv);   // sum f.v = -rate sum m |dv|^2 (the rigid part does no work)
                // D-044: centripetal force of the group's rigid rotation, m w x (w x r) (zero sum about the centre of mass):
                // a spinning wheel's rim and belt need ~3 kN per tread node at 250 km/h, far beyond the hoop stiffness
                // the 2 kHz stability bound allows the polygonal rings (the tire grew 86 mm at 288 km/h)
                if (g.spin != 0)
                    f += math.cross(w, math.cross(w, r)) / im;
                dampForce[i] = (float3)f;""",
    """                diss += math.dot(f, dv);   // sum f.v = -rate sum m |dv|^2 (the rigid part does no work)
                dampForce[i] = (float3)f;"""), (
    """        public int spin;                    // 1: centripetal compensation in the group's rotating frame (wheels, D-044)""",
    """        public int spin;                    // 1: a wheel: its ring beams carry the hoop tension of the rotation (D-044)""")])

RING = '''        /// <summary>
        /// Ring beams of a spinning wheel group (D-044): beams between two of the group's nodes at the same radius about
        /// the wheel's polar axis (largest principal moment of the group) and in the same plane, i.e. the chords of the
        /// rim rings and tread rows. Each gets the hoop tension coefficient (m / L) R^2 (m the mean node mass, L the
        /// chord, R the ring radius), so that at a spin rate w it carries mu (w R)^2, the centrifugal hoop tension.
        /// </summary>
        void MarkRingBeams(Body b, int group)
        {
            var dg = dampGroups[group];
            var set = new HashSet<int>();
            double mt = 0.0;
            double3 c = double3.zero;
            for (int k = dg.nodeStart; k < dg.nodeStart + dg.nodeCount; k++)
            {
                int n = dampGroupNodes[k];
                set.Add(n);
                double m = invMass[n] > 0f ? 1.0 / invMass[n] : 0.0;
                mt += m;
                c += m * (double3)pos0[n];
            }
            if (mt <= 0.0)
                return;
            c /= mt;
            double xx = 0, yy = 0, zz = 0, xy = 0, xz = 0, yz = 0;
            foreach (int n in set)
            {
                double m = invMass[n] > 0f ? 1.0 / invMass[n] : 0.0;
                double3 r = (double3)pos0[n] - c;
                xx += m * (r.y * r.y + r.z * r.z);
                yy += m * (r.x * r.x + r.z * r.z);
                zz += m * (r.x * r.x + r.y * r.y);
                xy -= m * r.x * r.y;
                xz -= m * r.x * r.z;
                yz -= m * r.y * r.z;
            }
            // polar axis: power iteration on the inertia tensor (largest moment)
            var inertia = new double3x3(xx, xy, xz, xy, yy, yz, xz, yz, zz);
            double3 axis = math.normalize(new double3(1.0, 0.3, 0.2));
            for (int it = 0; it < 200; it++)
                axis = math.normalize(math.mul(inertia, axis));
            int marked = 0;
            for (int j = b.beamStart; j < b.beamStart + b.beamCount; j++)
            {
                var s = beams[j];
                if (!set.Contains(s.a) || !set.Contains(s.b))
                    continue;
                double3 pa = (double3)pos0[s.a] - c, pb = (double3)pos0[s.b] - c;
                double ha = math.dot(pa, axis), hb = math.dot(pb, axis);
                double3 ra = pa - ha * axis, rb = pb - hb * axis;
                double la = math.length(ra), lb = math.length(rb);
                if (math.abs(ha - hb) > 0.004 || math.abs(la - lb) > 0.004 || la < 0.05)
                    continue;
                double len = math.distance(pa, pb);
                double radius = 0.5 * (la + lb);
                if (len < 1e-4 || len > 0.6 * radius)
                    continue;
                double ma = invMass[s.a] > 0f ? 1.0 / invMass[s.a] : 0.0, mb = invMass[s.b] > 0f ? 1.0 / invMass[s.b] : 0.0;
                s.spinGroup = group;
                s.spinCoef = (float)(0.5 * (ma + mb) / len * radius * radius);
                beams[j] = s;
                marked++;
            }
            b.ringBeams += marked;
        }

        /// <summary>
        /// One panel hinge: the plate values of its material scaled by the geometry of the two triangles,'''

patch("SoftBodyWorld.cs", [(
    """            hydroInput = hydroInput,
            spawnBlend = spawnBlend,
            pressureScale = pressureScale,
            rest = rest,""",
    """            hydroInput = hydroInput,
            spawnBlend = spawnBlend,
            pressureScale = pressureScale,
            dampRigid = dampRigid,
            rest = rest,"""), (
    """            s.pressureGroup = -1;
            return s;
        }""",
    """            s.pressureGroup = -1;
            s.spinGroup = -1;
            return s;
        }"""), (
    """                    dampGroups[b.dampGroupStart + t] = dgs;
                }
""",
    """                    dampGroups[b.dampGroupStart + t] = dgs;
                }
                for (int t = 0; t < b.dampGroupCount; t++)
                    if (dampGroups[b.dampGroupStart + t].spin != 0)
                        MarkRingBeams(b, b.dampGroupStart + t);
"""), (
    """        /// <summary>
        /// One panel hinge: the plate values of its material scaled by the geometry of the two triangles,""",
    RING), (
    """            public int curveStart, gearStart;        // engine mode: offsets into the world's curve / gear arrays""",
    """            public int curveStart, gearStart;        // engine mode: offsets into the world's curve / gear arrays
            public int ringBeams;                    // ring beams of spinning wheel groups (hoop tension, D-044)""")])
print("patched")
