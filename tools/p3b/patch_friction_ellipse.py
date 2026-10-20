"""One-off (P3b): anisotropic tread friction (D-048): a friction ellipse per tire tread node, lateral / longitudinal
friction = muLateral, the lateral axis from the node's lateral tread beams (works on the car and on the tire rig)."""
from pathlib import Path

ROOT = Path("Unity/HellcatSandbox/Assets/Sim")


def patch(path, pairs):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:120])
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")


patch("Data/SimParamsDef.cs", [(
    """        public float alphaTangent = 0.3f;
        public float zetaTangent = 0.15f;
    }""",
    """        public float alphaTangent = 0.3f;
        public float zetaTangent = 0.15f;
        // anisotropic friction (tire tread, D-048): lateral / longitudinal friction of a node whose lateral axis runs
        // along its beams of material lateralBeams (both ends: the axis through the two neighbours); 1: isotropic
        public float muLateral = 1f;
        public string lateralBeams = "";
    }""")])

patch("Core/SimTypes.cs", [(
    """        public float alphaTangent;          // friction anchor stiffness = alpha * m / dt^2
        public float zetaTangent;
    }""",
    """        public float alphaTangent;          // friction anchor stiffness = alpha * m / dt^2
        public float zetaTangent;
        public float latExtra;              // friction ellipse (D-048): 1 / muLateral^2 - 1 (0: isotropic)
    }""")])

patch("Core/Kernels.cs", [(
    """        public static float Apply(float3 p, float3 v, float m, float dt, float s, float3 n, int primIndex,
            in ContactMaterial cm, in SurfaceMaterial surf, ref float3 anchor, ref int anchorPrim, ref float3 force,
            out float slipSpeed)""",
    """        public static float Apply(float3 p, float3 v, float m, float dt, float s, float3 n, int primIndex,
            in ContactMaterial cm, in SurfaceMaterial surf, float3 lat, ref float3 anchor, ref int anchorPrim, ref float3 force,
            out float slipSpeed)"""), (
    """            float3 ft = -kt * dpt - ct * vt;
            float ftLen = math.length(ft);
            float limit = muStatic * fn;
            slipSpeed = math.length(vt);
            if (ftLen > limit)
            {
                float mu = surf.frictionScale * SlidingMu(cm, slipSpeed) * lf;
                float fslide = math.min(mu * fn, ftLen);
                float3 dir = ftLen > 1e-9f ? ft / ftLen : float3.zero;
                ft = dir * fslide;
                // Keep the anchor at the distance where the spring alone gives the sliding force.
                anchor = surfacePoint + dir * (fslide / kt);
            }""",
    """            float3 ft = -kt * dpt - ct * vt;
            // friction ellipse (D-048): the component along the lateral axis lat counts 1 / muLateral times (lat zero:
            // isotropic); the limit scales the trial force back onto the ellipse
            float ftLat = math.dot(ft, lat);
            float ftLen = math.sqrt(math.lengthsq(ft) + cm.latExtra * ftLat * ftLat);
            float limit = muStatic * fn;
            slipSpeed = math.length(vt);
            if (ftLen > limit)
            {
                float mu = surf.frictionScale * SlidingMu(cm, slipSpeed) * lf;
                ft *= math.min(mu * fn / ftLen, 1f);
                // Keep the anchor at the distance where the spring alone gives the sliding force.
                anchor = surfacePoint + ft / kt;
            }""")])

patch("Core/SimJobs.cs", [(
    """        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> contactImp;   // contact impulse accumulated since the last ClearContactImp

        public void Execute(int i)
        {
            float im = invMass[i];""",
    """        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> contactImp;   // contact impulse accumulated since the last ClearContactImp
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> nodeLat;  // lateral friction axis (D-048), zero: isotropic

        public void Execute(int i)
        {
            float im = invMass[i];"""), (
    """                    float fn = ContactKernel.Apply(p, v, m, prm.dt, s, nrm, pi, cm, surf, ref anc, ref ancPrim, ref f, out float sl);""",
    """                    float fn = ContactKernel.Apply(p, v, m, prm.dt, s, nrm, pi, cm, surf, nodeLat[i], ref anc, ref ancPrim, ref f, out float sl);""")])

patch("Core/SerialPhaseJob.cs", [(
    """        public Vehicle.VehicleControlJob control;
        public ForceElementPhase forces;
        public CollisionGridPhase grid;

        public void Execute()
        {""",
    """        public Vehicle.VehicleControlJob control;
        public ForceElementPhase forces;
        public CollisionGridPhase grid;
        // lateral friction axes of the anisotropic contact nodes (D-048): (node, a, b), axis along pos[b] - pos[a]
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int3> frictionAxes;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> axisPos;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> nodeLat;
        public int frictionAxisCount;

        public void Execute()
        {
            for (int k = 0; k < frictionAxisCount; k++)
            {
                int3 e = frictionAxes[k];
                nodeLat[e.x] = math.normalizesafe(axisPos[e.z] - axisPos[e.y]);
            }""")])

patch("Core/SoftBodyWorld.cs", [(
    """            alphaTangent = d.alphaTangent,
            zetaTangent = d.zetaTangent,
        };""",
    """            alphaTangent = d.alphaTangent,
            zetaTangent = d.zetaTangent,
            latExtra = 1f / math.pow(math.clamp(d.muLateral, 0.2f, 5f), 2f) - 1f,
        };"""), (
    """            BuildBeamAdjacency();
            BuildSlotAdjacency(slotOwner);
            BuildCollision();

            IsBuilt = true;""",
    """            BuildBeamAdjacency();
            BuildSlotAdjacency(slotOwner);
            BuildCollision();
            BuildFrictionAxes();

            IsBuilt = true;"""), (
    """        /// <summary>
        /// Ring beams of a spinning wheel group (D-044):""",
    """        /// <summary>Anisotropic contact nodes (D-048): a node whose contact material names lateralBeams gets its lateral
        /// friction axis from those beams: through its two neighbours along them, or from itself to its only one.</summary>
        void BuildFrictionAxes()
        {
            var axes = new List<int3>();
            foreach (var b in bodies)
            {
                var latMat = new Dictionary<string, string>();
                foreach (var cm in b.prm.contactMaterials)
                    if (!string.IsNullOrEmpty(cm.lateralBeams) && cm.muLateral != 1f)
                        latMat[cm.name] = cm.lateralBeams;
                if (latMat.Count == 0)
                    continue;
                var nbr = new Dictionary<int, List<int>>();
                foreach (var bd in b.def.beams)
                {
                    string ca = b.def.nodes[bd.a].cmat ?? "", cb = b.def.nodes[bd.b].cmat ?? "";
                    if (latMat.TryGetValue(ca, out string ma) && ma == bd.mat)
                    {
                        if (!nbr.TryGetValue(bd.a, out var la)) nbr[bd.a] = la = new List<int>();
                        la.Add(bd.b);
                    }
                    if (latMat.TryGetValue(cb, out string mb) && mb == bd.mat)
                    {
                        if (!nbr.TryGetValue(bd.b, out var lb)) nbr[bd.b] = lb = new List<int>();
                        lb.Add(bd.a);
                    }
                }
                foreach (var kv in nbr)
                {
                    int n = b.nodeStart + kv.Key;
                    var l = kv.Value;
                    if (l.Count >= 2)
                        axes.Add(new int3(n, b.nodeStart + l[0], b.nodeStart + l[1]));
                    else
                        axes.Add(new int3(n, n, b.nodeStart + l[0]));
                }
            }
            frictionAxes = Alloc<int3>(math.max(axes.Count, 1));
            for (int k = 0; k < axes.Count; k++)
                frictionAxes[k] = axes[k];
            frictionAxisCount = axes.Count;
            nodeLat = Alloc<float3>(math.max(NodeCount, 1));
        }

        /// <summary>
        /// Ring beams of a spinning wheel group (D-044):"""), (
    """        public NativeArray<float3> bodyAccel; // per body: uniform acceleration of its nodes (aerodynamic drag)""",
    """        public NativeArray<float3> bodyAccel; // per body: uniform acceleration of its nodes (aerodynamic drag)
        NativeArray<int3> frictionAxes;       // anisotropic contact nodes (D-048): (node, a, b)
        NativeArray<float3> nodeLat;          // lateral friction axis per node (zero: isotropic)
        int frictionAxisCount;"""), (
    """            contactImp = contactImp,
        };

        NodeContactJob MakeContactJob() => new NodeContactJob""",
    """            contactImp = contactImp,
            nodeLat = nodeLat,
        };

        NodeContactJob MakeContactJob() => new NodeContactJob"""), (
    """            clock = clock,
            counters = counters,
            control = new VehicleControlJob""",
    """            clock = clock,
            counters = counters,
            frictionAxes = frictionAxes,
            axisPos = pos,
            nodeLat = nodeLat,
            frictionAxisCount = frictionAxisCount,
            control = new VehicleControlJob""")])
print("patched")
