using System;
using System.Collections.Generic;
using System.IO;
using Hellcat.Sim.Data;
using Hellcat.Sim.Vehicle;
using Unity.Collections;
using Unity.Jobs;
using Unity.Mathematics;

namespace Hellcat.Sim
{
    /// <summary>
    /// One physics world: every soft body (vehicles, debris, test structures) shares the same node/beam arrays
    /// so that they can collide with each other in one solver. Build once, then step with
    /// <see cref="ScheduleSubsteps"/>. All state lives in NativeArrays (no managed allocation per step).
    /// </summary>
    public sealed class SoftBodyWorld : IDisposable
    {
        public sealed class Body
        {
            public string name;
            public VehicleDef def;
            public SimParamsDef prm;
            public int nodeStart, nodeCount, beamStart, beamCount;
            public int groupStart, groupCount;
            public int vehicleIndex = -1;
            public int wheelStart, wheelCount;
            public int torsionStart, torsionCount;
            public int hingeStart, hingeCount;
            public int dampGroupStart, dampGroupCount;
            public int pressureStart, pressureCount;
            public int collTriStart, collTriCount;
            public bool sleepable;                   // part of the sleeping tail (D-098): debris added after the vehicles
            public float3 spawnPosition;
            public quaternion spawnRotation;
            public float3 spawnVelocity;
            public float3 spawnAngularVelocity;      // rad/s about the spawn centre of mass (tests)
            public float spawnClearance = float.NaN; // m: lowest static-collision node this far from the statics (NaN: as placed)
            public float spawnLift;                  // m applied by the clearance rule (telemetry)
            public readonly Dictionary<string, int> hydroIndex = new Dictionary<string, int>();
            public readonly List<string> groupNames = new List<string>();
            public float totalMass;
            public bool hasCollisionNodes, hasSelfCollisionNodes;
            public List<int>[] knuckles;             // per wheel: local indices of the knuckle reaction nodes
            public int pretensionedBeams;
            public float pretensionMax;              // N
            public float pretensionResidual;         // N, worst force imbalance at spawn after form finding
            public float couplingScale = 1f;         // brake hold / wind-up scale-down by the stability budget (1: none)
            public int curveStart, gearStart;        // engine mode: offsets into the world's curve / gear arrays
            public int ringBeams;                    // ring beams of spinning wheel groups (hoop tension, D-044)
        }

        const float RadPerRpm = 2f * math.PI / 60f;

        public readonly SimParamsDef worldParams;
        public readonly float dt;
        public readonly List<Body> bodies = new List<Body>();
        public int maxSubsteps = 132;
        public int parallelThreshold = 1200;   // beams; below this one thread is faster than scheduling
        public int beamBatch = 256, nodeBatch = 64;
        public bool forceSingleThread;
        public bool trackEnergy;               // per-beam damping energy, contact work (validation, metrics)

        public int NodeCount { get; private set; }
        public int BeamCount { get; private set; }
        public int GroupCount { get; private set; }
        public int VehicleCount { get; private set; }
        public int WheelCount { get; private set; }
        public int TorsionBarCount { get; private set; }
        public int HingeCount { get; private set; }
        public int DampGroupCount { get; private set; }
        public int PressureGroupCount { get; private set; }
        public int hingeBatch = 128;
        public int CollTriCount { get; private set; }
        public bool CollisionEnabled { get; private set; }
        public long StepsTaken => clock.IsCreated ? clock[0] : 0;
        public bool IsBuilt { get; private set; }
        public string[] PrimNames { get; private set; }

        // Nodes
        public NativeArray<float3> pos, vel;
        public NativeArray<float> invMass;
        public NativeArray<int> nodeFlags, nodeBody, nodeCmat, nodePart;
        public NativeArray<float3> anchor;
        public NativeArray<int> anchorPrim;
        public NativeArray<byte> contactLatch;   // 1: hard static contact since the last projection (D-055)
        public NativeArray<float> contactFn, contactSlip, frictionPower;
        public NativeArray<float3> contactImp; // contact impulse since ClearContactImp (validation)
        public NativeArray<int> contactSurface;
        public NativeArray<float3> extForce;
        public NativeArray<double> contactWork;  // J, work of static and dynamic contact forces (trackEnergy)
        NativeArray<float3> pos0, vel0;
        // Beams
        public NativeArray<BeamStatic> beams;
        public NativeArray<float> rest, yield, plasticWork, breakEnergy, stress;
        public NativeArray<byte> broken;
        public NativeArray<float3> beamForce;
        public NativeArray<double> dampEnergy;   // J dissipated per beam (trackEnergy)
        NativeArray<float> rest0, yield0;
        NativeArray<byte> relaxArmed;            // per beam: spring-back suppression armed by plastic flow (D-056)
        NativeArray<int> beamAdjStart, beamAdjCode;
        // Break groups
        public NativeArray<byte> groupDone;
        NativeArray<byte> groupTrigger;
        NativeArray<int> groupBeamStart, groupBeams;
        // Generic force slots (wheel couples, torsion bars, pressure)
        public NativeArray<float3> slotForce;
        NativeArray<int> slotAdjStart, slotAdjIndex;
        // Torsion bars
        public NativeArray<TorsionBarStatic> torsionBars;
        public NativeArray<byte> torsionBroken;
        public NativeArray<float> torsionAngle;
        public NativeArray<double> torsionDampEnergy;
        // Shell bending hinges (D-032)
        public NativeArray<HingeStatic> hinges;
        public NativeArray<float> hingeRest, hingeYield, hingeAngle, hingePlastic;
        public NativeArray<byte> hingeBroken;
        public NativeArray<double> hingeDampEnergy;
        // Deformation damping groups (D-033)
        public NativeArray<DampGroupStatic> dampGroups;
        public NativeArray<int> dampGroupNodes, dampGroupNodeBg;
        public NativeArray<float3> dampForce;
        public NativeArray<double> dampGroupEnergy;
        NativeArray<DampGroupRigid> dampRigid;          // per group rigid motion of the substep (D-038)
        NativeArray<double3> dampReactF, dampReactT;     // scratch of the relative damping pass
        // Pressure groups
        public NativeArray<PressureGroupStatic> pressureGroups;
        public NativeArray<PressureState> pressureState;
        public NativeArray<int3> pressureTris;
        public NativeArray<float> pressureScale;
        NativeArray<int> leakBeams;
        // Node-vs-triangle collision
        public NativeArray<CollTri> collTris;
        public NativeArray<NodeContact> contacts;
        public NativeArray<int> collCounters;
        public CollisionParams collisionParams;
        NativeArray<int> lastTri, lastBody, tested;
        NativeArray<float> lastSide;
        NativeArray<float3> lastNormal, dynForce;
        NativeArray<NodeImpulse> deferred;
        NativeArray<int2> bodyNodes, bodySelf;
        NativeArray<int> selfNodes;
        NativeArray<int> bodyColl;
        NativeArray<float3> bodyLo, bodyHi;
        NativeArray<byte> bodyInsert, bodyOthers;
        NativeArray<int> bucketStart, bucketFill, entryTri;
        NativeArray<ulong> entryKey;
        // Bodies
        NativeArray<float> bodyAge, spawnBlend;
        NativeArray<int> nearStart, nearCount, nearPrims;
        const int MaxNearPerBody = 64;
        // read-only view of the static near lists (validation: which obstacles a body can see)
        public NativeArray<int> NearStart => nearStart;
        public NativeArray<int> NearCount => nearCount;
        public NativeArray<int> NearPrims => nearPrims;
        // Static world and materials
        public NativeArray<StaticPrimitive> prims;
        public NativeArray<float4> planes;
        public NativeArray<ContactMaterial> cmats;
        public NativeArray<SurfaceMaterial> surfaces;
        public string[] SurfaceNames { get; private set; }
        public string[] ContactMaterialNames { get; private set; }
        // Vehicles
        public NativeArray<VehicleStatic> vehicles;
        public NativeArray<VehicleState> vehicleState;
        public NativeArray<WheelStatic> wheels;
        public NativeArray<WheelState> wheelState;
        NativeArray<int> rimNodes, treadNodes, refNodes, knuckleNodes;
        NativeArray<int> driveNodes;   // differential nodes of the driven wheels (drive torque reaction, D-036)
        NativeArray<int> windupNodes;  // body nodes of the wind-up couples (D-036)
        NativeArray<float2> engineCurve; // engine mode (D-042): full-throttle torque (rad/s, N*m) of every vehicle
        NativeArray<float> gearRatios;   // forward gear ratios of every vehicle
        public NativeArray<float3> bodyAccel; // per body: uniform acceleration of its nodes (aerodynamic drag)
        NativeArray<int3> frictionAxes;       // anisotropic contact nodes (D-048): (node, a, b)
        NativeArray<float3> nodeLat;          // lateral friction axis per node (zero: isotropic)
        int frictionAxisCount;
        public NativeArray<DriverInput> inputs;
        public NativeArray<float> hydroInput;
        // Misc
        NativeArray<long> clock;
        NativeArray<int> counters;

        readonly List<IDisposable> owned = new List<IDisposable>();

        public SoftBodyWorld(SimParamsDef worldParams)
        {
            worldParams.Normalize();
            this.worldParams = worldParams;
            dt = worldParams.dt;
        }

        // sleeping debris (D-098): the sleepable bodies at the end of the body list; see TailSleepPhase
        NativeArray<int> tailSleep;
        int tailNodeStart, tailBeamStart;
        public const int TailCheckEvery = 32;         // substeps (16 ms)
        public const int TailQuietChecks = 62;        // about 1 s at rest before it sleeps
        public const float TailWakeGap = 8f, TailSleepGap = 12f, TailSleepSpeed = 0.05f;

        /// <summary>Marks a body (added after every vehicle) as sleeping debris (D-098). Before Build.</summary>
        public void MarkSleepable(int body)
        {
            if (IsBuilt)
                throw new InvalidOperationException("world already built");
            bodies[body].sleepable = true;
        }

        /// <summary>The world has a sleeping tail of debris and it is asleep now.</summary>
        public bool TailAsleep => tailSleep.IsCreated && tailNodeStart < NodeCount && tailSleep[0] != 0;
        public bool HasSleepTail => tailSleep.IsCreated && tailNodeStart < NodeCount;

        /// <summary>Plastic change of a beam's rest length since the spawn (m; positive: longer).</summary>
        public float RestChange(int beam) => rest[beam] - rest0[beam];

        /// <summary>Wakes the sleeping tail (debris moved by the game, e.g. put back in place).</summary>
        public void WakeTail()
        {
            if (!tailSleep.IsCreated)
                return;
            tailSleep[0] = 0;
            tailSleep[1] = 0;
        }

        NativeArray<T> Alloc<T>(int length) where T : struct
        {
            var a = new NativeArray<T>(length, Allocator.Persistent, NativeArrayOptions.ClearMemory);
            owned.Add(a);
            return a;
        }

        // ------------------------------------------------------------------ building

        public int AddBody(string name, VehicleDef def, SimParamsDef prm, float3 position, quaternion rotation,
            float3 velocity, bool isVehicle)
        {
            if (IsBuilt)
                throw new InvalidOperationException("world already built");
            prm.Normalize();
            VehicleDef.Normalize(def);
            var b = new Body
            {
                name = name,
                def = def,
                prm = prm,
                spawnPosition = position,
                spawnRotation = rotation,
                spawnVelocity = velocity,
                vehicleIndex = isVehicle && def.wheels.Length > 0 ? VehicleCount : -1,
            };
            if (b.vehicleIndex >= 0)
                VehicleCount++;
            bodies.Add(b);
            return bodies.Count - 1;
        }

        public void Build(StaticWorldBuilder statics)
        {
            // Contact materials (union by name) and surfaces (world params).
            var cmatNames = new List<string>();
            var cmatList = new List<ContactMaterial>();
            foreach (var b in bodies)
                foreach (var cm in b.prm.contactMaterials)
                    if (!cmatNames.Contains(cm.name))
                    {
                        cmatNames.Add(cm.name);
                        cmatList.Add(ToRuntime(cm));
                    }
            if (!cmatNames.Contains("default"))
            {
                cmatNames.Add("default");
                cmatList.Add(ToRuntime(new ContactMaterialDef { name = "default" }));
            }
            ContactMaterialNames = cmatNames.ToArray();
            var surfNames = new List<string>();
            var surfList = new List<SurfaceMaterial>();
            foreach (var s in worldParams.surfaces)
            {
                surfNames.Add(s.name);
                surfList.Add(new SurfaceMaterial { frictionScale = s.frictionScale, rollingResistance = s.rollingResistance });
            }
            if (surfList.Count == 0)
            {
                surfNames.Add("default");
                surfList.Add(new SurfaceMaterial { frictionScale = 1f, rollingResistance = 0.012f });
            }
            SurfaceNames = surfNames.ToArray();
            statics.ResolveSurfaces(n =>
            {
                int i = surfNames.IndexOf(n);
                if (i < 0)
                    throw new InvalidDataException($"unknown surface '{n}'");
                return i;
            });
            prims = Alloc<StaticPrimitive>(statics.prims.Count);
            for (int i = 0; i < statics.prims.Count; i++)
                prims[i] = statics.prims[i];
            planes = Alloc<float4>(math.max(statics.planes.Count, 1));
            for (int i = 0; i < statics.planes.Count; i++)
                planes[i] = statics.planes[i];
            PrimNames = statics.primNames.ToArray();
            cmats = Alloc<ContactMaterial>(cmatList.Count);
            for (int i = 0; i < cmatList.Count; i++)
                cmats[i] = cmatList[i];
            surfaces = Alloc<SurfaceMaterial>(surfList.Count);
            for (int i = 0; i < surfList.Count; i++)
                surfaces[i] = surfList[i];

            // Sizes.
            int nNodes = 0, nBeams = 0, nGroups = 0, nWheels = 0, nRim = 0, nTread = 0, nSlots = 0, nHydro = 0, nRef = 0, nKnuckle = 0; int nDrive = 0, nWindup = 0;
            int nTorsion = 0, nHinge = 0, nDampGroup = 0, nDampNodes = 0, nPressure = 0, nPressureTris = 0, nCollTris = 0;
            foreach (var b in bodies)
            {
                b.nodeStart = nNodes;
                b.nodeCount = b.def.nodes.Length;
                b.beamStart = nBeams;
                b.beamCount = b.def.beams.Length;
                nNodes += b.nodeCount;
                nBeams += b.beamCount;
                b.groupStart = nGroups;
                foreach (var bd in b.def.beams)
                    if (!string.IsNullOrEmpty(bd.bg) && !b.groupNames.Contains(bd.bg))
                        b.groupNames.Add(bd.bg);
                foreach (var td in b.def.triangles)
                    if (!string.IsNullOrEmpty(td.bg) && !b.groupNames.Contains(td.bg))
                        b.groupNames.Add(td.bg);
                b.groupCount = b.groupNames.Count;
                nGroups += b.groupCount;
                foreach (var h in b.def.hydros)
                    b.hydroIndex[h] = nHydro++;
                if (b.vehicleIndex >= 0)
                {
                    b.wheelStart = nWheels;
                    b.wheelCount = b.def.wheels.Length;
                    nWheels += b.wheelCount;
                    b.knuckles = new List<int>[b.wheelCount];
                    for (int w = 0; w < b.wheelCount; w++)
                    {
                        var wd = b.def.wheels[w];
                        b.knuckles[w] = KnuckleNodes(b.def, wd);
                        nRim += wd.rim.Length;
                        nTread += wd.tread.Length;
                        nKnuckle += b.knuckles[w].Count;
                        int nd = wd.driven != 0 ? (wd.driveReaction?.Length ?? 0) : 0;
                        int nw = string.IsNullOrEmpty(wd.windup) ? 0 : (wd.windupBody?.Length ?? 0);
                        nDrive += nd;
                        nWindup += nw;
                        nSlots += wd.rim.Length + b.knuckles[w].Count + 2 + nd + nw;
                        nRef += 1;
                    }
                }
                b.torsionStart = nTorsion;
                b.torsionCount = b.def.torsionBars.Length;
                nTorsion += b.torsionCount;
                nSlots += 4 * b.torsionCount;
                b.hingeStart = nHinge;
                b.hingeCount = b.def.hinges?.Length ?? 0;
                nHinge += b.hingeCount;
                nSlots += 4 * b.hingeCount;
                b.dampGroupStart = nDampGroup;
                b.dampGroupCount = b.def.dampGroups?.Length ?? 0;
                nDampGroup += b.dampGroupCount;
                foreach (var dg in b.def.dampGroups ?? System.Array.Empty<DampGroupDef>())
                    nDampNodes += dg.nodes?.Length ?? 0;
                b.pressureStart = nPressure;
                b.pressureCount = b.def.pressureGroups.Length;
                nPressure += b.pressureCount;
                foreach (var pg in b.def.pressureGroups)
                {
                    nPressureTris += pg.tris.Length;
                    nSlots += 3 * pg.tris.Length;
                }
                b.collTriStart = nCollTris;
                foreach (var td in b.def.triangles)
                    if (IsCollisionTri(td))
                        nCollTris++;
                b.collTriCount = nCollTris - b.collTriStart;
            }
            NodeCount = nNodes;
            BeamCount = nBeams;
            // the sleeping tail (D-098): the sleepable bodies at the end of the list, after at least one other body
            int tailBody = bodies.Count;
            while (tailBody > 0 && bodies[tailBody - 1].sleepable)
                tailBody--;
            bool tail = tailBody > 0 && tailBody < bodies.Count;
            tailNodeStart = tail ? bodies[tailBody].nodeStart : nNodes;
            tailBeamStart = tail ? bodies[tailBody].beamStart : nBeams;
            tailSleep = Alloc<int>(2);
            GroupCount = nGroups;
            WheelCount = nWheels;
            TorsionBarCount = nTorsion;
            HingeCount = nHinge;
            DampGroupCount = nDampGroup;
            PressureGroupCount = nPressure;
            CollTriCount = nCollTris;

            pos = Alloc<float3>(nNodes);
            vel = Alloc<float3>(nNodes);
            pos0 = Alloc<float3>(nNodes);
            vel0 = Alloc<float3>(nNodes);
            invMass = Alloc<float>(nNodes);
            nodeFlags = Alloc<int>(nNodes);
            nodeBody = Alloc<int>(nNodes);
            nodeCmat = Alloc<int>(nNodes);
            nodePart = Alloc<int>(nNodes);
            anchor = Alloc<float3>(nNodes);
            anchorPrim = Alloc<int>(nNodes);
            contactLatch = Alloc<byte>(nNodes);
            contactFn = Alloc<float>(nNodes);
            contactSlip = Alloc<float>(nNodes);
            frictionPower = Alloc<float>(nNodes);
            contactImp = Alloc<float3>(nNodes);
            contactSurface = Alloc<int>(nNodes);
            extForce = Alloc<float3>(nNodes);
            contactWork = Alloc<double>(nNodes);

            beams = Alloc<BeamStatic>(nBeams);
            rest = Alloc<float>(nBeams);
            yield = Alloc<float>(nBeams);
            rest0 = Alloc<float>(nBeams);
            yield0 = Alloc<float>(nBeams);
            relaxArmed = Alloc<byte>(nBeams);
            plasticWork = Alloc<float>(nBeams);
            breakEnergy = Alloc<float>(nBeams);
            stress = Alloc<float>(nBeams);
            broken = Alloc<byte>(nBeams);
            beamForce = Alloc<float3>(nBeams);
            dampEnergy = Alloc<double>(nBeams);

            groupTrigger = Alloc<byte>(math.max(nGroups, 1));
            groupDone = Alloc<byte>(math.max(nGroups, 1));
            hydroInput = Alloc<float>(math.max(nHydro, 1));
            slotForce = Alloc<float3>(math.max(nSlots, 1));
            var slotOwner = new int[nSlots];

            vehicles = Alloc<VehicleStatic>(math.max(VehicleCount, 1));
            vehicleState = Alloc<VehicleState>(math.max(VehicleCount, 1));
            wheels = Alloc<WheelStatic>(math.max(nWheels, 1));
            wheelState = Alloc<WheelState>(math.max(nWheels, 1));
            rimNodes = Alloc<int>(math.max(nRim, 1));
            treadNodes = Alloc<int>(math.max(nTread, 1));
            knuckleNodes = Alloc<int>(math.max(nKnuckle, 1));
            driveNodes = Alloc<int>(math.max(nDrive, 1));
            windupNodes = Alloc<int>(math.max(nWindup, 1));
            refNodes = Alloc<int>(math.max(nRef, 1));
            inputs = Alloc<DriverInput>(math.max(VehicleCount, 1) * maxSubsteps);
            // engine curves and gear ratios of the engine-mode vehicles (D-042)
            var curveList = new List<float2>();
            var gearList = new List<float>();
            foreach (var b in bodies)
            {
                if (b.vehicleIndex < 0)
                    continue;
                var pt = b.prm.powertrain;
                b.curveStart = curveList.Count;
                b.gearStart = gearList.Count;
                int nc = math.min(pt.torqueRpm?.Length ?? 0, pt.torqueNm?.Length ?? 0);
                for (int k = 0; k < nc; k++)
                    curveList.Add(new float2(pt.torqueRpm[k] * RadPerRpm, pt.torqueNm[k]));
                if (pt.gearRatios != null)
                    gearList.AddRange(pt.gearRatios);
                if (pt.mode == "engine" && (nc < 2 || gearList.Count == b.gearStart))
                    throw new InvalidDataException($"{b.name}: engine powertrain needs a torque curve and gear ratios");
            }
            engineCurve = Alloc<float2>(math.max(curveList.Count, 1));
            for (int k = 0; k < curveList.Count; k++)
                engineCurve[k] = curveList[k];
            gearRatios = Alloc<float>(math.max(gearList.Count, 1));
            for (int k = 0; k < gearList.Count; k++)
                gearRatios[k] = gearList[k];
            bodyAccel = Alloc<float3>(math.max(bodies.Count, 1));

            torsionBars = Alloc<TorsionBarStatic>(nTorsion);
            torsionBroken = Alloc<byte>(nTorsion);
            torsionAngle = Alloc<float>(nTorsion);
            torsionDampEnergy = Alloc<double>(nTorsion);
            hinges = Alloc<HingeStatic>(math.max(nHinge, 1));
            hingeRest = Alloc<float>(math.max(nHinge, 1));
            hingeYield = Alloc<float>(math.max(nHinge, 1));
            hingeAngle = Alloc<float>(math.max(nHinge, 1));
            hingePlastic = Alloc<float>(math.max(nHinge, 1));
            hingeBroken = Alloc<byte>(math.max(nHinge, 1));
            hingeDampEnergy = Alloc<double>(math.max(nHinge, 1));
            dampGroups = Alloc<DampGroupStatic>(math.max(nDampGroup, 1));
            dampGroupNodes = Alloc<int>(math.max(nDampNodes, 1));
            dampGroupNodeBg = Alloc<int>(math.max(nDampNodes, 1));
            dampForce = Alloc<float3>(math.max(nNodes, 1));
            dampGroupEnergy = Alloc<double>(math.max(nDampGroup, 1));
            dampRigid = Alloc<DampGroupRigid>(math.max(nDampGroup, 1));
            dampReactF = Alloc<double3>(math.max(nDampGroup, 1));
            dampReactT = Alloc<double3>(math.max(nDampGroup, 1));
            int dgCursor = 0;
            var inDampGroup = new bool[nNodes];
            pressureGroups = Alloc<PressureGroupStatic>(nPressure);
            pressureState = Alloc<PressureState>(nPressure);
            pressureScale = Alloc<float>(math.max(nPressure, 1));
            pressureTris = Alloc<int3>(nPressureTris);
            var leakList = new List<int>();
            collTris = Alloc<CollTri>(nCollTris);

            bodyAge = Alloc<float>(bodies.Count);
            spawnBlend = Alloc<float>(bodies.Count);
            nearStart = Alloc<int>(bodies.Count);
            nearCount = Alloc<int>(bodies.Count);
            nearPrims = Alloc<int>(bodies.Count * MaxNearPerBody);
            bodyNodes = Alloc<int2>(bodies.Count);
            bodyColl = Alloc<int>(bodies.Count);
            bodyLo = Alloc<float3>(bodies.Count);
            bodyHi = Alloc<float3>(bodies.Count);
            bodyInsert = Alloc<byte>(bodies.Count);
            bodyOthers = Alloc<byte>(bodies.Count);
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
                selfNodes[k] = selfList[k];
            clock = Alloc<long>(2);   // [0] steps since build, [1] the step the collision grid schedule counts from
            counters = Alloc<int>(4);
            collCounters = Alloc<int>(CollisionCounter.Count);

            var groupLists = new List<int>[math.max(nGroups, 1)];
            for (int g = 0; g < groupLists.Length; g++)
                groupLists[g] = new List<int>();

            int rimCursor = 0, treadCursor = 0, slotCursor = 0, refCursor = 0, ptCursor = 0, ctCursor = 0, partCursor = 0, knCursor = 0; int drCursor = 0, wuCursor = 0;
            for (int bi = 0; bi < bodies.Count; bi++)
            {
                var b = bodies[bi];
                var def = b.def;
                nearStart[bi] = bi * MaxNearPerBody;
                spawnBlend[bi] = b.prm.spawnRamp > 0f ? 0f : 1f;
                bodyNodes[bi] = new int2(b.nodeStart, b.nodeCount);

                // Nodes.
                var partIds = new Dictionary<string, int>();
                int PartId(string name)
                {
                    name ??= "";
                    if (!partIds.TryGetValue(name, out int id))
                    {
                        id = partCursor++;
                        partIds[name] = id;
                    }
                    return id;
                }
                for (int i = 0; i < b.nodeCount; i++)
                {
                    var nd = def.nodes[i];
                    int gi = b.nodeStart + i;
                    bool isFixed = (nd.flags & NodeFlag.Fixed) != 0;
                    invMass[gi] = isFixed || nd.m <= 0f ? 0f : 1f / nd.m;
                    nodeFlags[gi] = nd.flags;
                    nodeBody[gi] = bi;
                    nodePart[gi] = PartId(nd.part);
                    int ci = cmatNames.IndexOf(string.IsNullOrEmpty(nd.cmat) ? "default" : nd.cmat);
                    if (ci < 0)
                        throw new InvalidDataException($"{b.name}: node {nd.name}: unknown contact material '{nd.cmat}'");
                    nodeCmat[gi] = ci;
                    b.totalMass += isFixed ? 0f : nd.m;
                    if ((nd.flags & NodeFlag.Collision) != 0)
                        b.hasCollisionNodes = true;
                    if ((nd.flags & NodeFlag.SelfCollision) != 0)
                        b.hasSelfCollisionNodes = true;
                }
                bodyColl[bi] = (b.hasCollisionNodes ? 1 : 0) | (b.hasSelfCollisionNodes ? 2 : 0);
                PlaceSpawn(bi);

                // Beams.
                var pairBeam = new Dictionary<long, int>();
                for (int j = 0; j < b.beamCount; j++)
                {
                    var bd = def.beams[j];
                    int gj = b.beamStart + j;
                    var mat = b.prm.materials[b.prm.MaterialIndex(bd.mat)];
                    float3 pa = pos0[b.nodeStart + bd.a], pb = pos0[b.nodeStart + bd.b];
                    var s = Resolve(bd, mat, math.distance(pa, pb));
                    ApplyZones(b.prm, def, bd, ref s);
                    s.a = b.nodeStart + bd.a;
                    s.b = b.nodeStart + bd.b;
                    s.body = bi;
                    s.breakGroup = -1;
                    s.pressureGroup = -1;
                    if (!string.IsNullOrEmpty(bd.bg))
                    {
                        int g = b.groupStart + b.groupNames.IndexOf(bd.bg);
                        s.breakGroup = (short)g;
                        groupLists[g].Add(gj);
                    }
                    if (bd.bgt == 1)
                        s.flags |= BeamFlag.GroupPassive;
                    s.hydro = -1;
                    if (s.type == BeamType.Hydro)
                    {
                        if (!b.hydroIndex.TryGetValue(bd.hydro ?? "", out int hi))
                            throw new InvalidDataException($"{b.name}: beam {j}: unknown hydro input '{bd.hydro}'");
                        s.hydro = hi;
                    }
                    beams[gj] = s;
                    rest0[gj] = s.spawnRest;
                    yield0[gj] = s.yield0;
                    pairBeam[PairKey(s.a, s.b)] = gj;
                }

                if (b.vehicleIndex >= 0)
                    BuildVehicle(b, slotOwner, ref rimCursor, ref treadCursor, ref slotCursor, ref refCursor, ref knCursor, ref drCursor, ref wuCursor);

                // Torsion bars (anti-roll bars): dihedral spring about the axis nodes.
                for (int t = 0; t < b.torsionCount; t++)
                {
                    var td = def.torsionBars[t];
                    if (td.n == null || td.n.Length != 4)
                        throw new InvalidDataException($"{b.name}: torsion bar {t} needs 4 nodes");
                    var mat = b.prm.Material(td.mat);
                    var tb = new TorsionBarStatic
                    {
                        n1 = b.nodeStart + td.n[0], n2 = b.nodeStart + td.n[1], n3 = b.nodeStart + td.n[2], n4 = b.nodeStart + td.n[3],
                        k = mat.spring,
                        c = math.max(mat.damp, 0f),
                        strength = mat.strength > 0f ? mat.strength : float.MaxValue,
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
                    tb.beam12 = pairBeam.TryGetValue(PairKey(tb.n1, tb.n2), out int b12) ? b12 : -1;
                    tb.beam23 = pairBeam.TryGetValue(PairKey(tb.n2, tb.n3), out int b23) ? b23 : -1;
                    tb.beam34 = pairBeam.TryGetValue(PairKey(tb.n3, tb.n4), out int b34) ? b34 : -1;
                    if (!TorsionKernel.Gradient(pos0[tb.n1], pos0[tb.n2], pos0[tb.n3], pos0[tb.n4], out tb.phi0,
                            out _, out _, out _, out _))
                        throw new InvalidDataException($"{b.name}: torsion bar {t} is degenerate (lever parallel to the axis)");
                    TorsionKernel.Levers(pos0[tb.n1], pos0[tb.n2], pos0[tb.n3], pos0[tb.n4], out tb.lever1, out tb.lever2, out tb.axis);
                    torsionBars[b.torsionStart + t] = tb;
                    slotOwner[slotCursor++] = tb.n1;
                    slotOwner[slotCursor++] = tb.n2;
                    slotOwner[slotCursor++] = tb.n3;
                    slotOwner[slotCursor++] = tb.n4;
                }

                // Shell bending hinges of the panel skins (D-032).
                for (int t = 0; t < b.hingeCount; t++)
                    hinges[b.hingeStart + t] = BuildHinge(b, bi, t, pairBeam, slotOwner, ref slotCursor);

                // Deformation damping groups (D-033).
                for (int t = 0; t < b.dampGroupCount; t++)
                {
                    var dg = def.dampGroups[t];
                    var dgs = new DampGroupStatic
                    {
                        nodeStart = dgCursor,
                        nodeCount = dg.nodes?.Length ?? 0,
                        rate = math.max(b.prm.DampGroupMaterial(dg.mat).rate, 0f),
                        vCap = math.max(b.prm.DampGroupMaterial(dg.mat).vCap, 0f),
                        spin = b.prm.DampGroupMaterial(dg.mat).spin ? 1 : 0,
                        breakGroup = string.IsNullOrEmpty(dg.bg) || !b.groupNames.Contains(dg.bg) ? -1
                            : b.groupStart + b.groupNames.IndexOf(dg.bg),
                        body = bi,
                        refGroup = -1,
                        relRate = 0f,
                        refBg0 = -1,
                        refBg1 = -1,
                    };
                    if (!string.IsNullOrEmpty(dg.reference))
                    {
                        int rg = Array.FindIndex(def.dampGroups, x => x.name == dg.reference);
                        if (rg < 0 || rg == t)
                            throw new InvalidDataException($"{b.name}: damp group {dg.name}: unknown reference '{dg.reference}'");
                        dgs.refGroup = b.dampGroupStart + rg;
                        dgs.relRate = math.max(b.prm.DampGroupMaterial(dg.mat).relRate, 0f);
                        var rb = dg.refBg ?? Array.Empty<string>();
                        if (rb.Length > 2)
                            throw new InvalidDataException($"{b.name}: damp group {dg.name}: at most 2 reference break groups");
                        dgs.refBg0 = rb.Length > 0 ? GroupIndex(b, rb[0]) : -1;
                        dgs.refBg1 = rb.Length > 1 ? GroupIndex(b, rb[1]) : -1;
                    }
                    for (int k = 0; k < dgs.nodeCount; k++)
                    {
                        int gn = b.nodeStart + dg.nodes[k];
                        if (inDampGroup[gn])
                            throw new InvalidDataException($"{b.name}: node {def.nodes[dg.nodes[k]].name} is in two damp groups");
                        inDampGroup[gn] = true;
                        string nbg = dg.nodeBg != null && k < dg.nodeBg.Length ? dg.nodeBg[k] : "";
                        dampGroupNodeBg[dgCursor] = string.IsNullOrEmpty(nbg) || !b.groupNames.Contains(nbg) ? -1
                            : b.groupStart + b.groupNames.IndexOf(nbg);
                        dampGroupNodes[dgCursor++] = gn;
                    }
                    dampGroups[b.dampGroupStart + t] = dgs;
                }
                for (int t = 0; t < b.dampGroupCount; t++)
                    if (dampGroups[b.dampGroupStart + t].spin != 0)
                        MarkRingBeams(b, b.dampGroupStart + t);

                // Pressure groups (tire cavities), with cord pre-tension so the spawn shape is in equilibrium.
                for (int g = 0; g < b.pressureCount; g++)
                    BuildPressureGroup(b, bi, g, pairBeam, leakList, slotOwner, ref ptCursor, ref slotCursor);

                // Collision triangles.
                foreach (var td in def.triangles)
                {
                    if (!IsCollisionTri(td))
                        continue;
                    collTris[ctCursor++] = new CollTri
                    {
                        a = b.nodeStart + td.a, b = b.nodeStart + td.b, c = b.nodeStart + td.c,
                        body = bi,
                        part = PartId(string.IsNullOrEmpty(td.group) ? def.nodes[td.a].part : td.group),
                        breakGroup = string.IsNullOrEmpty(td.bg) ? -1 : b.groupStart + b.groupNames.IndexOf(td.bg),
                    };
                }
            }

            leakBeams = Alloc<int>(math.max(leakList.Count, 1));
            for (int i = 0; i < leakList.Count; i++)
                leakBeams[i] = leakList[i];

            // Break group CSR.
            groupBeamStart = Alloc<int>(groupLists.Length + 1);
            int total = 0;
            for (int g = 0; g < groupLists.Length; g++)
            {
                groupBeamStart[g] = total;
                total += groupLists[g].Count;
            }
            groupBeamStart[groupLists.Length] = total;
            groupBeams = Alloc<int>(math.max(total, 1));
            int c = 0;
            foreach (var list in groupLists)
                foreach (int bj in list)
                    groupBeams[c++] = bj;

            BuildBeamAdjacency();
            BuildSlotAdjacency(slotOwner);
            BuildCollision();
            BuildFrictionAxes();

            IsBuilt = true;
            ResetAll();
        }

        /// <summary>Anisotropic contact nodes (D-048): a node whose contact material names lateralBeams gets its lateral
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
        /// One panel hinge: the plate values of its material scaled by the geometry of the two triangles,
        /// k = D |e|^2 / (A1 + A2) * HingeConst.Geometry (the same for the damping), yield = m_y |e|.
        /// </summary>
        HingeStatic BuildHinge(Body b, int bi, int t, Dictionary<long, int> pairBeam, int[] slotOwner, ref int slotCursor)
        {
            var hd = b.def.hinges[t];
            if (hd.n == null || hd.n.Length != 4)
                throw new InvalidDataException($"{b.name}: hinge {t} needs 4 nodes");
            var mat = b.prm.HingeMaterial(hd.mat);
            var h = new HingeStatic
            {
                n1 = b.nodeStart + hd.n[0], n2 = b.nodeStart + hd.n[1], n3 = b.nodeStart + hd.n[2], n4 = b.nodeStart + hd.n[3],
                slotStart = slotCursor,
                body = bi,
            };
            float3 x1 = pos0[h.n1], x2 = pos0[h.n2], x3 = pos0[h.n3], x4 = pos0[h.n4];
            float e2 = math.distancesq(x2, x3);
            float area = 0.5f * (math.length(math.cross(x2 - x1, x3 - x1)) + math.length(math.cross(x3 - x4, x2 - x4)));
            if (area < 1e-8f || !TorsionKernel.Gradient(x1, x2, x3, x4, out h.phi0, out float3 g1, out float3 g2, out float3 g3,
                    out float3 g4))
                throw new InvalidDataException($"{b.name}: hinge {t} is degenerate");
            h.g0sq = math.max(math.max(math.lengthsq(g1), math.lengthsq(g2)), math.max(math.lengthsq(g3), math.lengthsq(g4)));
            float geo = HingeConst.Geometry * e2 / area;
            h.k = mat.bend * geo;
            h.c = math.max(mat.damp, 0f) * geo;
            h.dampCap = math.max(mat.dampCap, 0f);
            float len = math.sqrt(e2);
            h.yield0 = mat.yieldMoment > 0f ? mat.yieldMoment * len : float.MaxValue;
            h.hardening = math.max(mat.hardening, 0f) * len;
            h.yieldCap = mat.yieldCap > 0f ? math.max(mat.yieldCap * len, h.yield0) : float.MaxValue;
            h.beam12 = pairBeam.TryGetValue(PairKey(h.n1, h.n2), out int b12) ? b12 : -1;
            h.beam23 = pairBeam.TryGetValue(PairKey(h.n2, h.n3), out int b23) ? b23 : -1;
            h.beam34 = pairBeam.TryGetValue(PairKey(h.n3, h.n4), out int b34) ? b34 : -1;
            slotOwner[slotCursor++] = h.n1;
            slotOwner[slotCursor++] = h.n2;
            slotOwner[slotCursor++] = h.n3;
            slotOwner[slotCursor++] = h.n4;
            return h;
        }

        static bool IsCollisionTri(TriDef td)
        {
            string t = (td.type ?? "COLLIDE").ToUpperInvariant();
            return t == "COLLIDE" || t == "";
        }

        static long PairKey(int a, int b) => a < b ? ((long)a << 32) | (uint)b : ((long)b << 32) | (uint)a;

        /// <summary>
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

        /// <summary>max_i r_i^2 / ((sum_j r_j^2)^2 m_i) of a set of nodes around an axis through <paramref name="centre"/>
        /// (couple compliance per node: a pure couple T puts k_i = K r_i^2 / (sum r^2)^2 on node i), and the set's
        /// moment of inertia about that axis.</summary>
        float CoupleCompliance(Body b, int[] local, float3 centre, float3 axis, out float inertia)
        {
            float sum = 0f;
            inertia = 0f;
            var r2 = new float[local.Length];
            for (int k = 0; k < local.Length; k++)
            {
                float3 r = pos0[b.nodeStart + local[k]] - centre;
                r -= math.dot(r, axis) * axis;
                r2[k] = math.lengthsq(r);
                sum += r2[k];
                float im = invMass[b.nodeStart + local[k]];
                inertia += im > 0f ? r2[k] / im : 0f;
            }
            float q = 0f;
            for (int k = 0; k < local.Length; k++)
                if (sum > 0f)
                    q = math.max(q, r2[k] * invMass[b.nodeStart + local[k]] / (sum * sum));
            return q;
        }

        static int GroupIndex(Body b, string name)
        {
            int g = string.IsNullOrEmpty(name) ? -1 : b.groupNames.IndexOf(name);
            return g >= 0 ? b.groupStart + g : -1;
        }

        float3 ModelPos(VehicleDef def, int n) => new float3(def.nodes[n].p[0], def.nodes[n].p[1], def.nodes[n].p[2]);

        float3 Centroid(Body b, int[] local)
        {
            float3 c = float3.zero;
            foreach (int n in local)
                c += pos0[b.nodeStart + n];
            return local.Length > 0 ? c / local.Length : c;
        }

        void BuildVehicle(Body b, int[] slotOwner, ref int rimCursor, ref int treadCursor, ref int slotCursor, ref int refCursor,
            ref int knCursor, ref int drCursor, ref int wuCursor)
        {
            var def = b.def;
            var pt = b.prm.powertrain;
            var asst = b.prm.assists;
            var aero = b.prm.aero;
            var vsd = new VehicleStatic
            {
                wheelStart = b.wheelStart,
                wheelCount = b.wheelCount,
                steerHydro = b.hydroIndex.TryGetValue("steering", out int sh) ? sh : -1,
                refStart = refCursor,
                refCount = b.wheelCount,
                mode = pt.mode == "engine" ? PowertrainMode.Engine : PowertrainMode.Simple,
                maxWheelTorque = pt.maxWheelTorque,
                maxPower = pt.maxPower,
                reverseTorque = pt.reverseTorque,
                steerRate = b.prm.steering.rate,
                steerReturnRate = b.prm.steering.returnRate,
                steerReductionStart = b.prm.steering.speedReductionStart,
                steerReductionAt60 = b.prm.steering.speedReductionAt60,
                body = bodies.IndexOf(b),
                mass = b.totalMass,
                // engine mode (D-042)
                curveStart = b.curveStart,
                curveCount = math.min(pt.torqueRpm?.Length ?? 0, pt.torqueNm?.Length ?? 0),
                gearStart = b.gearStart,
                gearCount = pt.gearRatios?.Length ?? 0,
                reverseRatio = math.abs(pt.reverseRatio),
                finalDrive = pt.finalDrive,
                efficiency = math.clamp(pt.efficiency, 0.5f, 1f),
                idleOmega = pt.idleRpm * RadPerRpm,
                revLimitOmega = pt.revLimitRpm * RadPerRpm,
                engineInertia = math.max(pt.engineInertia, 0.01f),
                fric0 = math.max(pt.frictionTorque0, 0f),
                fricPerOmega = math.max(pt.frictionTorquePerRpm, 0f) / RadPerRpm,
                idleKp = pt.idleKp,
                idleKi = pt.idleKi,
                shiftUpOmega = pt.shiftUpRpm * RadPerRpm,
                shiftUpLightOmega = pt.shiftUpLightRpm * RadPerRpm,
                shiftDownOmega = pt.shiftDownRpm * RadPerRpm,
                shiftDownLightOmega = pt.shiftDownLightRpm * RadPerRpm,
                shiftTime = math.max(pt.shiftTime, 0f),
                shiftHold = math.max(pt.shiftHold, 0f),
                shiftTorqueFactor = math.saturate(pt.shiftTorqueFactor),
                converterTR0 = math.max(pt.converterTorqueRatio, 1f),
                converterSRc = math.clamp(pt.converterCouplingSR, 0.05f, 0.99f),
                converterOverrun = math.max(pt.converterOverrun, 0f),
                lockupSpeed = pt.converterLockupSpeed,
                lockupTime = math.max(pt.lockupTime, 0f),
                lockupMinGear = math.max(pt.lockupMinGear, 1),
                clutchCap = math.max(pt.clutchMaxTorque, 0f),
                turbineInertia = math.max(pt.turbineInertia, 1e-3f),
                outputInertia = math.max(pt.outputInertia, 0.01f),
                shaftK = math.max(pt.driveshaftStiffness, 0f),
                shaftC = math.max(pt.driveshaftDamping, 0f),
                diffPreload = math.max(pt.diffPreload, 0f),
                diffBiasDrive = BiasFactor(pt.diffBias),
                diffBiasCoast = BiasFactor(pt.diffBiasCoast),
                diffK = math.max(pt.diffStiffness, 0f),
                diffC = math.max(pt.diffDamping, 0f),
                diffLeft = -1,
                diffRight = -1,
                engineGroup = GroupIndex(b, pt.engineGroup),
                rollingRadius = math.max(pt.rollingRadius, 0.05f),
                absSlip = math.max(asst.absSlip, 0.01f),
                absSlipLow = math.max(asst.absSlipLow, 0.01f),
                absKp = math.max(asst.absKp, 0f),
                absKi = math.max(asst.absKi, 0f),
                absFilter = math.max(asst.absFilter, 1e-4f),
                absMinSpeed = asst.absMinSpeed,
                tcSlip = math.max(asst.tcSlip, 0.01f),
                tcSlipLow = math.max(asst.tcSlipLow, 0.01f),
                slipBlendLow = asst.slipBlendLow,
                slipBlendHigh = math.max(asst.slipBlendHigh, asst.slipBlendLow + 0.1f),
                tcFloorSpeed = math.max(asst.tcFloorSpeed, 0.5f),
                tcKp = math.max(asst.tcKp, 0f),
                tcKi = math.max(asst.tcKi, 0f),
                tcFilter = math.max(asst.tcFilter, 1e-4f),
                tcMinFactor = math.saturate(asst.tcMinFactor),
                dragK = 0.5f * math.max(aero.airDensity, 0f) * math.max(aero.dragArea, 0f),
                liftKFront = 0.5f * math.max(aero.airDensity, 0f) * aero.liftFront,
                liftKRear = 0.5f * math.max(aero.airDensity, 0f) * aero.liftRear,
                liftOnMounts = 1,
            };
            if (!string.IsNullOrEmpty(pt.engineGroup) && vsd.engineGroup < 0)
                throw new InvalidDataException($"{b.name}: unknown engine break group '{pt.engineGroup}'");
            if (vsd.mode == PowertrainMode.Engine)
            {
                // converter capacity from the full-throttle stall speed: K omega_stall^2 = T_wot(omega_stall)
                float ws0 = math.max(pt.converterStallRpm, 100f) * RadPerRpm;
                vsd.converterK = CurveAt(pt, ws0) / (ws0 * ws0);
                // idle feed-forward: the throttle that balances the friction at idle
                float fi = vsd.fric0 + vsd.fricPerOmega * vsd.idleOmega;
                vsd.idleFeedForward = fi / math.max(CurveAt(pt, vsd.idleOmega) + fi, 1f);
            }
            float zMean = 0f;
            foreach (var wd0 in def.wheels)
                zMean += 0.5f * (def.nodes[wd0.axleInner].p[2] + def.nodes[wd0.axleOuter].p[2]) / def.wheels.Length;
            // the body frame of the alignment element at the model pose (front - rear and right - left centroids of the
            // wind-up body sets): its up is the reference of the geometric wind-up angle (D-069)
            float3 upM = float3.zero;
            {
                float3 sf = float3.zero, sr = float3.zero, sR = float3.zero, sL = float3.zero;
                int cf = 0, cr = 0, cR = 0, cL = 0;
                foreach (var wd0 in def.wheels)
                {
                    if (string.IsNullOrEmpty(wd0.windup) || wd0.windupBody == null || wd0.windupBody.Length == 0)
                        continue;
                    float3 cw = float3.zero;
                    foreach (int n in wd0.windupBody)
                        cw += ModelPos(def, n) / wd0.windupBody.Length;
                    bool isFront = 0.5f * (def.nodes[wd0.axleInner].p[2] + def.nodes[wd0.axleOuter].p[2]) > zMean;
                    if (isFront) { sf += cw; cf++; } else { sr += cw; cr++; }
                    if (def.nodes[wd0.axleInner].p[0] + def.nodes[wd0.axleOuter].p[0] >= 0f) { sR += cw; cR++; } else { sL += cw; cL++; }
                }
                if (cf > 0 && cr > 0 && cR > 0 && cL > 0)
                    upM = math.normalizesafe(math.cross(math.normalizesafe(sf / cf - sr / cr), math.normalizesafe(sR / cR - sL / cL)));
            }
            for (int w = 0; w < b.wheelCount; w++)
            {
                var wd = def.wheels[w];
                int gw = b.wheelStart + w;
                var brake = b.prm.Brake(wd.brake);
                var ws = new WheelStatic
                {
                    vehicle = b.vehicleIndex,
                    axleInner = b.nodeStart + wd.axleInner,
                    axleOuter = b.nodeStart + wd.axleOuter,
                    arm = b.nodeStart + wd.arm,
                    rimStart = rimCursor,
                    rimCount = wd.rim.Length,
                    treadStart = treadCursor,
                    treadCount = wd.tread.Length,
                    knuckleStart = knCursor,
                    knuckleCount = b.knuckles[w].Count,
                    driveStart = drCursor,
                    driveCount = wd.driven != 0 ? (wd.driveReaction?.Length ?? 0) : 0,
                    windupStart = wuCursor,
                    windupCount = string.IsNullOrEmpty(wd.windup) ? 0 : (wd.windupBody?.Length ?? 0),
                    wheelGroup = GroupIndex(b, def.nodes[wd.axleInner].part),
                    slotStart = slotCursor,
                    driven = wd.driven,
                    steered = wd.steered,
                    front = 0.5f * (def.nodes[wd.axleInner].p[2] + def.nodes[wd.axleOuter].p[2]) > zMean ? 1 : 0,
                    brakeTorque = brake.maxTorque,
                    handbrakeTorque = brake.handbrakeTorque,
                    radius = wd.radius,
                    meshRollingResistance = math.max(b.prm.tire.meshRollingResistance, 0f),
                    // Vehicle-local x is the car's right: orient every spin axis that way.
                    axisSign = def.nodes[wd.axleOuter].p[0] - def.nodes[wd.axleInner].p[0] >= 0f ? 1f : -1f,
                };
                // Rim inertia about the axle axis (spawn pose) for the brake holding spring.
                float3 ai = pos0[ws.axleInner], ao = pos0[ws.axleOuter];
                float3 axis = math.normalize(ao - ai);
                float inertia = 0f;
                foreach (int rn in wd.rim)
                {
                    int g = b.nodeStart + rn;
                    float3 r = pos0[g] - ai;
                    r -= math.dot(r, axis) * axis;
                    float m = invMass[g] > 0f ? 1f / invMass[g] : 0f;
                    inertia += m * math.lengthsq(r);
                }
                ws.rimInertia = math.max(inertia, 1e-3f);
                ws.stickK = brake.stickStiffness > 0f ? brake.stickStiffness : 0.15f * ws.rimInertia / (dt * dt);
                ws.stickC = brake.stickDamping > 0f ? brake.stickDamping : 2f * 0.3f * math.sqrt(ws.stickK * ws.rimInertia);
                // Wind-up element (D-036): knuckle rotation about the spin axis vs the body nodes that carry the suspension.
                if (ws.windupCount > 0)
                {
                    var wu = b.prm.Windup(wd.windup);
                    if (wu == null)
                        throw new InvalidDataException($"{b.name}: wheel {wd.name}: unknown wind-up set '{wd.windup}'");
                    ws.windupK = math.max(wu.stiffness, 0f);
                    ws.windupC = math.max(wu.damping, 0f);
                    ws.windupStrength = wu.strength > 0f ? wu.strength : float.MaxValue;
                    // alignment element (D-049)
                    ws.camberK = math.max(wu.camberStiffness, 0f);
                    ws.camberC = math.max(wu.camberDamping, 0f);
                    ws.toeK = wd.steered != 0 ? 0f : math.max(wu.toeStiffness, 0f);
                    ws.toeC = math.max(wd.steered != 0 ? wu.steerDamping : wu.toeDamping, 0f);
                    ws.camberStatic = math.radians(wu.camberStatic);
                    ws.toeStatic = math.radians(wu.toeStatic);
                    ws.camberGain = math.radians(wu.camberGain);
                    ws.bumpSteer = math.radians(wu.bumpSteer);
                    float3 hubM = 0.5f * (ModelPos(def, wd.axleInner) + ModelPos(def, wd.axleOuter));
                    float3 bcM = float3.zero;
                    foreach (int n in wd.windupBody)
                        bcM += ModelPos(def, n) / wd.windupBody.Length;
                    ws.travel0 = hubM.y - bcM.y;
                    ws.side = hubM.x >= 0f ? 1f : -1f;
                    // camber reference axis (D-051): steered knuckles measure the camber as the angle between the axle line
                    // and the steering axis, which steering does not change; phi0 makes it the plain camber at the model pose
                    float3 aM = math.normalizesafe(ModelPos(def, wd.axleOuter) - ModelPos(def, wd.axleInner), new float3(ws.side, 0f, 0f));
                    ws.kingpin = new float3(0f, 1f, 0f);
                    if (wd.steered != 0 && wd.kingpin != null && wd.kingpin.Length == 2)
                        ws.kingpin = math.normalizesafe(ModelPos(def, wd.kingpin[1]) - ModelPos(def, wd.kingpin[0]), ws.kingpin);
                    ws.kingpinPhi0 = math.acos(math.clamp(math.dot(aM, ws.kingpin), -1f, 1f)) + math.asin(math.clamp(aM.y, -1f, 1f));
                    // geometric wind-up angle (D-069): the knuckle node farthest from the axle line, its angle about the axle
                    // from the body frame's up; integrating the knuckle's and the body set's angular velocities drifted
                    // (their noise and bias random-walked into a spurious wind-up torque that steered the knuckles)
                    ws.windupRef = -1;
                    if (math.lengthsq(upM) > 0.5f && wu.geometricAngle)
                    {
                        float3 inM = ModelPos(def, wd.axleInner), outM = ModelPos(def, wd.axleOuter);
                        float3 axM = ws.axisSign * math.normalizesafe(outM - inM, new float3(1f, 0f, 0f));
                        float3 hubM2 = 0.5f * (inM + outM);
                        float best = 0f;
                        foreach (int kn in b.knuckles[w])
                        {
                            float3 u = ModelPos(def, kn) - hubM2;
                            u -= math.dot(u, axM) * axM;
                            if (math.lengthsq(u) > best) { best = math.lengthsq(u); ws.windupRef = b.nodeStart + kn; }
                        }
                        if (ws.windupRef >= 0)
                        {
                            float3 u = ModelPos(def, ws.windupRef - b.nodeStart) - hubM2;
                            u -= math.dot(u, axM) * axM;
                            float3 up = upM - math.dot(upM, axM) * axM;
                            ws.windupPhi0 = math.atan2(math.dot(axM, math.cross(up, u)), math.dot(up, u));
                        }
                    }
                }
                // Both couples act on the knuckle nodes as pure couples (radii from the knuckle centroid). Budget: per node
                // dt^2 k_i / m_i + 2 dt c_i / m_i <= 1 with k_i = K r_i^2 / (sum r^2)^2 (a factor 4 below the explicit
                // limit), and the knuckle's rotation mode (dt^2 (K_b + K_w) + 2 dt (C_b + C_w)) / I_knuckle <= 2.
                var knSet = b.knuckles[w].ToArray();
                float qk = CoupleCompliance(b, knSet, Centroid(b, knSet), axis, out float iK);
                float qr = CoupleCompliance(b, wd.rim, Centroid(b, wd.rim), axis, out _);
                ws.knuckleInertia = iK;
                float kTot = ws.stickK + ws.windupK, cTot = ws.stickC + ws.windupC;
                // driven rims also carry the half-shaft spring (one half of the axle-side spring) and the LSD clutch pack
                float kRim = ws.stickK, cRim = ws.stickC;
                if (vsd.mode == PowertrainMode.Engine && wd.driven != 0)
                {
                    kRim += 0.5f * vsd.shaftK + vsd.diffK;
                    cRim += 0.5f * vsd.shaftC + vsd.diffC;
                }
                float load = math.max(qr * (dt * dt * kRim + 2f * dt * cRim), qk * (dt * dt * kTot + 2f * dt * cTot));
                load = math.max(load, (dt * dt * kTot + 2f * dt * cTot) / math.max(iK, 1e-6f) / 2f);
                // the alignment element acts on the two axle nodes (a force pair across the axle, D-049): per node an
                // effective spring K / L^2 and damper C / L^2; keep dt^2 k / m + 2 dt c / m <= 0.5 (the knuckle beams use the rest)
                if (ws.camberK + ws.camberC + ws.toeK + ws.toeC > 0f)
                {
                    float l2 = math.max(math.lengthsq(ModelPos(def, wd.axleOuter) - ModelPos(def, wd.axleInner)), 1e-6f);
                    float mAx = math.min(def.nodes[wd.axleInner].m, def.nodes[wd.axleOuter].m);
                    float kMax = math.max(ws.camberK, ws.toeK) / l2, cMax = math.max(ws.camberC, ws.toeC) / l2;
                    float alignLoad = (dt * dt * kMax + 2f * dt * cMax) / math.max(mAx, 1e-3f) / 0.5f;
                    if (alignLoad > 1f)
                    {
                        ws.camberK /= alignLoad;
                        ws.camberC /= alignLoad;
                        ws.toeK /= alignLoad;
                        ws.toeC /= alignLoad;
                        b.couplingScale = math.min(b.couplingScale, 1f / alignLoad);
                    }
                }
                if (load > 1f)
                {
                    ws.stickK /= load;
                    ws.stickC /= load;
                    ws.windupK /= load;
                    ws.windupC /= load;
                    b.couplingScale = math.min(b.couplingScale, 1f / load);
                }
                wheels[gw] = ws;
                if (wd.driven != 0)
                    vsd.drivenCount++;

                for (int k = 0; k < wd.rim.Length; k++)
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
                slotOwner[slotCursor++] = ws.axleOuter;
                for (int k = 0; k < ws.driveCount; k++)
                {
                    driveNodes[drCursor++] = b.nodeStart + wd.driveReaction[k];
                    slotOwner[slotCursor++] = b.nodeStart + wd.driveReaction[k];
                }
                for (int k = 0; k < ws.windupCount; k++)
                {
                    windupNodes[wuCursor++] = b.nodeStart + wd.windupBody[k];
                    slotOwner[slotCursor++] = b.nodeStart + wd.windupBody[k];
                }
                foreach (int tn in wd.tread)
                    treadNodes[treadCursor++] = b.nodeStart + tn;
                refNodes[refCursor++] = ws.axleInner;
                if (ws.windupCount == 0)
                    vsd.liftOnMounts = 0;
            }
            // limited-slip differential pair: exactly two driven wheels, left (x < 0) and right
            int dl = -1, dr = -1, nDriven = 0;
            for (int w = 0; w < b.wheelCount; w++)
            {
                var wd = def.wheels[w];
                if (wd.driven == 0)
                    continue;
                nDriven++;
                if (def.nodes[wd.axleInner].p[0] + def.nodes[wd.axleOuter].p[0] < 0f) dl = b.wheelStart + w; else dr = b.wheelStart + w;
            }
            if (nDriven == 2 && dl >= 0 && dr >= 0)
            {
                vsd.diffLeft = dl;
                vsd.diffRight = dr;
            }
            vehicles[b.vehicleIndex] = vsd;
            for (int s = 0; s < maxSubsteps; s++)
                inputs[b.vehicleIndex * maxSubsteps + s] = DriverInput.Idle;
        }

        /// <summary>Torque bias ratio B -> the share of the axle torque the LSD can move across: (B - 1) / (B + 1).</summary>
        static float BiasFactor(float bias) => bias > 1f ? (bias - 1f) / (bias + 1f) : 0f;

        /// <summary>Full-throttle torque of a powertrain definition at an engine speed (rad/s), as the control job.</summary>
        static float CurveAt(PowertrainDef pt, float omega)
        {
            int n = math.min(pt.torqueRpm?.Length ?? 0, pt.torqueNm?.Length ?? 0);
            if (n == 0)
                return 0f;
            float rpm = omega / RadPerRpm;
            if (rpm <= pt.torqueRpm[0])
                return pt.torqueNm[0] * math.saturate(rpm / math.max(pt.torqueRpm[0], 1f));
            for (int k = 1; k < n; k++)
                if (rpm <= pt.torqueRpm[k])
                    return math.lerp(pt.torqueNm[k - 1], pt.torqueNm[k], (rpm - pt.torqueRpm[k - 1]) / math.max(pt.torqueRpm[k] - pt.torqueRpm[k - 1], 1e-3f));
            return pt.torqueNm[n - 1];
        }

        void BuildPressureGroup(Body b, int bi, int g, Dictionary<long, int> pairBeam, List<int> leakList, int[] slotOwner,
            ref int ptCursor, ref int slotCursor)
        {
            var pd = b.def.pressureGroups[g];
            var pp = b.prm.pressure;
            float gauge = pd.pressure * pp.gaugeScale;
            int gg = b.pressureStart + g;
            var cavity = new SortedSet<int>();
            int triStart = ptCursor;
            foreach (int ti in pd.tris)
            {
                var td = b.def.triangles[ti];
                var t = new int3(b.nodeStart + td.a, b.nodeStart + td.b, b.nodeStart + td.c);
                pressureTris[ptCursor++] = t;
                cavity.Add(t.x);
                cavity.Add(t.y);
                cavity.Add(t.z);
            }
            // Spawn volume and nodal pressure forces.
            float3 o = pos0[pressureTris[triStart].x];
            double vol = 0.0;
            var nodalForce = new Dictionary<int, double3>();
            foreach (int n in cavity)
                nodalForce[n] = double3.zero;
            for (int t = triStart; t < ptCursor; t++)
            {
                int3 tri = pressureTris[t];
                double3 a = pos0[tri.x] - o, bb = pos0[tri.y] - o, cc = pos0[tri.z] - o;
                vol += math.dot(a, math.cross(bb, cc)) / 6.0;
                double3 area = 0.5 * math.cross(bb - a, cc - a);
                double3 share = gauge * area / 3.0;
                nodalForce[tri.x] += share;
                nodalForce[tri.y] += share;
                nodalForce[tri.z] += share;
                for (int k = 0; k < 3; k++)
                    slotOwner[slotCursor + k] = tri[k];
                slotCursor += 3;
            }
            if (vol <= 0.0)
                throw new InvalidDataException($"{b.name}: pressure group {pd.name}: non-positive volume {vol} (winding?)");
            float pAbs0 = gauge + pp.atmosphere;
            var pgs = new PressureGroupStatic
            {
                triStart = triStart,
                triCount = ptCursor - triStart,
                slotStart = slotCursor - 3 * (ptCursor - triStart),
                leakBeamStart = leakList.Count,
                volume0 = (float)vol,
                gas0 = (float)(pAbs0 * vol),
                pAtm = pp.atmosphere,
                maxAbs = pAbs0 * math.max(pp.maxAbsRatio, 1f),
                minVolume = (float)vol * math.saturate(pp.minVolumeRatio),
                leakPerBeam = pp.leakPerBeam,
                leakMax = pp.leakMax,
                body = bi,
            };
            // Beams between cavity nodes: cords (pre-tension) and, if breakable, leak paths.
            var cords = new List<int>();
            for (int j = b.beamStart; j < b.beamStart + b.beamCount; j++)
            {
                var s = beams[j];
                if (!cavity.Contains(s.a) || !cavity.Contains(s.b))
                    continue;
                if ((s.flags & BeamFlag.Breakable) != 0)
                    leakList.Add(j);
                if (s.type != BeamType.Hydro && s.type != BeamType.Support && s.k > 0f)
                {
                    cords.Add(j);
                    s.pressureGroup = (short)gg;
                    beams[j] = s;
                }
            }
            pgs.leakBeamCount = leakList.Count - pgs.leakBeamStart;
            pressureGroups[gg] = pgs;
            if (pp.pretension && cords.Count > 0)
                SolvePretension(b, gg, cavity, nodalForce, cords);
        }

        /// <summary>
        /// Cord pre-tension (D-028): beam forces of the linear elastic cavity structure under the spawn pressure
        /// load (K u = f, t = k n.du; the minimum complementary energy distribution), so pressure and cord
        /// tension are in equilibrium at the modelled tire shape.
        /// </summary>
        void SolvePretension(Body b, int group, SortedSet<int> cavity, Dictionary<int, double3> nodalForce, List<int> cords)
        {
            var local = new Dictionary<int, int>();
            foreach (int n in cavity)
                local[n] = local.Count;
            int dim = 3 * local.Count;
            var K = new double[dim * dim];
            var dirs = new double3[cords.Count];
            for (int q = 0; q < cords.Count; q++)
            {
                var s = beams[cords[q]];
                double3 d = pos0[s.b] - pos0[s.a];
                double3 e = d / math.length(d);
                dirs[q] = e;
                int ia = 3 * local[s.a], ib = 3 * local[s.b];
                for (int r = 0; r < 3; r++)
                for (int cc = 0; cc < 3; cc++)
                {
                    double v = s.k * e[r] * e[cc];
                    K[(ia + r) * dim + ia + cc] += v;
                    K[(ib + r) * dim + ib + cc] += v;
                    K[(ia + r) * dim + ib + cc] -= v;
                    K[(ib + r) * dim + ia + cc] -= v;
                }
            }
            double trace = 0.0;
            for (int i = 0; i < dim; i++)
                trace += K[i * dim + i];
            var rhs = new double[dim];
            foreach (var kv in nodalForce)
            {
                int i = 3 * local[kv.Key];
                rhs[i] = kv.Value.x;
                rhs[i + 1] = kv.Value.y;
                rhs[i + 2] = kv.Value.z;
            }
            bool ok = false;
            for (double eps = 1e-9; eps < 1e-2 && !ok; eps *= 100.0)
            {
                var A = (double[])K.Clone();
                double add = eps * trace / dim;
                for (int i = 0; i < dim; i++)
                    A[i * dim + i] += add;
                if (!LinearAlgebra.Cholesky(A, dim))
                    continue;
                LinearAlgebra.CholeskySolve(A, dim, rhs);
                ok = true;
            }
            if (!ok)
                throw new InvalidDataException($"{b.name}: tire pre-tension: cavity stiffness is singular");
            var residual = new Dictionary<int, double3>(nodalForce);
            float tmax = 0f;
            for (int q = 0; q < cords.Count; q++)
            {
                int j = cords[q];
                var s = beams[j];
                int ia = 3 * local[s.a], ib = 3 * local[s.b];
                double3 du = new double3(rhs[ib] - rhs[ia], rhs[ib + 1] - rhs[ia + 1], rhs[ib + 2] - rhs[ia + 2]);
                double t = s.k * math.dot(dirs[q], du);
                s.pressureGroup = (short)group;
                s.pretension = (float)t;
                beams[j] = s;
                residual[s.a] += t * dirs[q];
                residual[s.b] -= t * dirs[q];
                tmax = math.max(tmax, math.abs((float)t));
            }
            double worst = 0.0;
            foreach (var r in residual.Values)
                worst = math.max(worst, math.cmax(math.abs(r)));
            b.pretensionedBeams += cords.Count;
            b.pretensionMax = math.max(b.pretensionMax, tmax);
            b.pretensionResidual = math.max(b.pretensionResidual, (float)worst);
        }

        /// <summary>Spawn positions and velocities of one body, lifted to its clearance above the statics.</summary>
        void PlaceSpawn(int bi)
        {
            var b = bodies[bi];
            float3 com = float3.zero;
            float mass = 0f;
            for (int i = 0; i < b.nodeCount; i++)
            {
                var nd = b.def.nodes[i];
                float3 p = b.spawnPosition + math.rotate(b.spawnRotation, new float3(nd.p[0], nd.p[1], nd.p[2]));
                pos0[b.nodeStart + i] = p;
                float m = invMass[b.nodeStart + i] > 0f ? 1f / invMass[b.nodeStart + i] : 0f;
                com += m * p;
                mass += m;
            }
            com = mass > 0f ? com / mass : b.spawnPosition;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                vel0[i] = invMass[i] > 0f ? b.spawnVelocity + math.cross(b.spawnAngularVelocity, pos0[i] - com) : float3.zero;
            b.spawnLift = 0f;
            if (float.IsNaN(b.spawnClearance) || prims.Length == 0)
                return;
            for (int iter = 0; iter < 3; iter++)
            {
                float minD = float.MaxValue;
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                {
                    if ((nodeFlags[i] & NodeFlag.StaticCollision) == 0)
                        continue;
                    for (int p = 0; p < prims.Length; p++)
                        minD = math.min(minD, StaticSdf.Distance(prims[p], planes, pos0[i], out _));
                }
                if (minD == float.MaxValue)
                    return;
                float lift = b.spawnClearance - minD;
                if (math.abs(lift) < 1e-5f)
                    break;
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                    pos0[i] += new float3(0f, lift, 0f);
                b.spawnLift += lift;
            }
        }

        void BuildCollision()
        {
            var cp = worldParams.collision;
            // Needed when a body with colliding nodes can meet another body's triangles, or with self-collision.
            bool needed = false;
            for (int i = 0; i < bodies.Count && !needed; i++)
            {
                needed |= bodies[i].hasSelfCollisionNodes && bodies[i].collTriCount > 0;
                if (!bodies[i].hasCollisionNodes)
                    continue;
                for (int j = 0; j < bodies.Count && !needed; j++)
                    needed |= j != i && bodies[j].collTriCount > 0;
            }
            CollisionEnabled = needed;
            float frontBias = 0f;
            for (int i = 0; i < cmats.Length; i++)
                frontBias = math.max(frontBias, cmats[i].bias);
            int cap = CollisionEnabled ? math.max(16384, 16 * CollTriCount) : 1;
            int buckets = 1;
            while (buckets < cap)
                buckets <<= 1;
            collisionParams = new CollisionParams
            {
                cellSize = math.max(cp.cellSize, 0.05f),
                rebuildEvery = math.max(cp.rebuildEvery, 1),
                frontBias = frontBias,
                backBias = math.max(cp.backBias, 0f),
                alpha = cp.alpha,
                zeta = cp.zeta,
                frictionScale = cp.frictionScale,
                footprintTolerance = cp.footprintTolerance,
                bucketMask = (ulong)(buckets - 1),
                entryCapacity = cap,
            };
            contacts = Alloc<NodeContact>(NodeCount);
            lastTri = Alloc<int>(NodeCount);
            lastBody = Alloc<int>(NodeCount);
            tested = Alloc<int>(NodeCount);
            lastSide = Alloc<float>(NodeCount);
            lastNormal = Alloc<float3>(NodeCount);
            dynForce = Alloc<float3>(NodeCount);
            deferred = Alloc<NodeImpulse>(NodeCount);
            bucketStart = Alloc<int>(buckets + 1);
            bucketFill = Alloc<int>(buckets);
            entryKey = Alloc<ulong>(cap);
            entryTri = Alloc<int>(cap);
        }

        static ContactMaterial ToRuntime(ContactMaterialDef d) => new ContactMaterial
        {
            muStatic = d.muStatic,
            muSliding = d.muSliding,
            stribeckVel = d.stribeckVel,
            stribeckExp = d.stribeckExp,
            loadRef = math.max(d.loadRef, 1f),
            loadSensitivity = d.loadSensitivity,
            minLoadFactor = d.minLoadFactor,
            bias = d.bias,
            alphaNormal = d.alphaNormal,
            zetaNormal = d.zetaNormal,
            alphaTangent = d.alphaTangent,
            zetaTangent = d.zetaTangent,
            latExtra = 1f / math.pow(math.clamp(d.muLateral, 0.2f, 5f), 2f) - 1f,
            hardContact = d.hardContact ? 1 : 0,
        };

        static byte ParseType(string t)
        {
            switch ((t ?? "NORMAL").ToUpperInvariant())
            {
                case "NORMAL": return BeamType.Normal;
                case "ANISOTROPIC": return BeamType.Anisotropic;
                case "BOUNDED": return BeamType.Bounded;
                case "SUPPORT": return BeamType.Support;
                case "HYDRO": return BeamType.Hydro;
                default: throw new InvalidDataException($"unknown beam type '{t}'");
            }
        }

        /// <summary>Material zones (params.materialZones): the thresholds of a part's beams inside a model-space box, scaled.</summary>
        static void ApplyZones(SimParamsDef prm, VehicleDef def, BeamDef bd, ref BeamStatic s)
        {
            if (prm.materialZones == null || prm.materialZones.Length == 0)
                return;
            var na = def.nodes[bd.a];
            var nb = def.nodes[bd.b];
            foreach (var z in prm.materialZones)
            {
                if (na.part != z.part || nb.part != z.part) continue;
                if (z.materials != null && z.materials.Length > 0 && Array.IndexOf(z.materials, bd.mat) < 0) continue;
                bool inside = z.min != null && z.max != null && z.min.Length == 3 && z.max.Length == 3;
                for (int k = 0; k < 3 && inside; k++)
                {
                    float mid = 0.5f * (na.p[k] + nb.p[k]);
                    inside = mid >= z.min[k] && mid <= z.max[k];
                }
                if (!inside) continue;
                if (s.yield0 < float.MaxValue) s.yield0 *= z.deformScale;
                s.hardening *= z.hardeningScale;
                if (s.yieldCap < float.MaxValue) s.yieldCap *= z.capScale;
                if (s.strength < float.MaxValue) s.strength *= z.strengthScale;
            }
        }

        /// <summary>Material + beam definition -> runtime parameters (lengths resolved from the spawn length).</summary>
        public static BeamStatic Resolve(BeamDef bd, BeamMaterialDef m, float spawnLength)
        {
            var s = new BeamStatic { type = ParseType(bd.type) };
            float pre = bd.pre > 0f ? bd.pre : 1f;
            float preloadLength = m.preload > 0f && m.spring > 0f ? m.preload / m.spring : 0f;
            s.spawnLength = spawnLength;
            s.spawnRest = spawnLength * pre + preloadLength;
            s.rampBase = spawnLength + preloadLength;
            s.k = m.spring;
            s.c = m.damp;
            s.cReb = m.dampRebound >= 0f ? m.dampRebound : m.damp;
            s.cFast = m.dampFast >= 0f ? m.dampFast : s.c;
            s.cRebFast = m.dampReboundFast >= 0f ? m.dampReboundFast : s.cReb;
            s.vSplit = m.velSplit > 0f ? m.velSplit : float.MaxValue;
            s.vSplitReb = m.velSplitRebound > 0f ? m.velSplitRebound : s.vSplit;
            s.kExp = m.springExp >= 0f ? m.springExp : m.spring;
            s.cExp = m.dampExp >= 0f ? m.dampExp : m.damp;
            if (m.deform > 0f)
            {
                s.flags |= BeamFlag.Deformable;
                s.yield0 = m.deform;
            }
            else
            {
                s.yield0 = float.MaxValue;
            }
            s.hardening = math.max(m.hardening, 0f);
            s.yieldCap = m.deformCap > 0f ? m.deformCap : float.MaxValue;
            if (m.strength > 0f)
            {
                s.flags |= BeamFlag.Breakable;
                s.strength = m.strength;
            }
            else
            {
                s.strength = float.MaxValue;
            }
            s.minRest = m.deformLimitMin > 0f ? s.spawnRest * m.deformLimitMin : 0f;
            s.maxRest = m.deformLimitMax > 0f ? s.spawnRest * m.deformLimitMax : float.MaxValue;
            if (s.type == BeamType.Support)
            {
                s.shortLen = 0f;
                s.longLen = m.longBound > 0f ? s.spawnRest * (1f + m.longBound) : 0f;
            }
            else
            {
                s.shortLen = m.shortBound > 0f ? s.spawnRest * (1f - m.shortBound) : 0f;
                s.longLen = m.longBound > 0f ? s.spawnRest * (1f + m.longBound) : float.MaxValue;
            }
            s.boundZone = math.max(m.boundZone, 1e-4f);
            s.kLimit = m.limitSpring;
            s.cLimit = m.limitDamp;
            s.cLimitReb = m.limitDampRebound >= 0f ? m.limitDampRebound : m.limitDamp;
            s.hydroFactor = bd.hf;
            s.hydroMinRatio = m.hydroMinRatio;
            s.hydroMaxRatio = m.hydroMaxRatio;
            s.pressureGroup = -1;
            s.inflationShare = math.saturate(m.inflationShare);
            s.relax = math.max(m.unloadRelax, 0f);
            s.spinGroup = -1;
            return s;
        }

        void BuildBeamAdjacency()
        {
            var counts = new int[NodeCount];
            for (int j = 0; j < BeamCount; j++)
            {
                counts[beams[j].a]++;
                counts[beams[j].b]++;
            }
            beamAdjStart = Alloc<int>(NodeCount + 1);
            for (int i = 0; i < NodeCount; i++)
                beamAdjStart[i + 1] = beamAdjStart[i] + counts[i];
            beamAdjCode = Alloc<int>(math.max(2 * BeamCount, 1));
            var fill = new int[NodeCount];
            for (int j = 0; j < BeamCount; j++)
            {
                int a = beams[j].a, b = beams[j].b;
                beamAdjCode[beamAdjStart[a] + fill[a]++] = j << 1;
                beamAdjCode[beamAdjStart[b] + fill[b]++] = (j << 1) | 1;
            }
        }

        void BuildSlotAdjacency(int[] slotOwner)
        {
            var counts = new int[NodeCount];
            foreach (int n in slotOwner)
                counts[n]++;
            slotAdjStart = Alloc<int>(NodeCount + 1);
            for (int i = 0; i < NodeCount; i++)
                slotAdjStart[i + 1] = slotAdjStart[i] + counts[i];
            slotAdjIndex = Alloc<int>(math.max(slotOwner.Length, 1));
            var fill = new int[NodeCount];
            for (int s = 0; s < slotOwner.Length; s++)
            {
                int n = slotOwner[s];
                slotAdjIndex[slotAdjStart[n] + fill[n]++] = s;
            }
        }

        // ------------------------------------------------------------------ state

        public void ResetAll()
        {
            for (int bi = 0; bi < bodies.Count; bi++)
                ResetBody(bi);
            clock[0] = 0;
            clock[1] = 0;
            for (int i = 0; i < collCounters.Length; i++)
                collCounters[i] = 0;
        }

        /// <summary>Restores the spawn state of one body (positions, velocities, damage, tire air).</summary>
        public void ResetBody(int bi)
        {
            var b = bodies[bi];
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
            {
                pos[i] = pos0[i];
                vel[i] = vel0[i];
                anchorPrim[i] = -1;
                contactLatch[i] = 0;
                contactFn[i] = 0f;
                contactSlip[i] = 0f;
                contactSurface[i] = -1;
                frictionPower[i] = 0f;
                contactImp[i] = float3.zero;
                extForce[i] = float3.zero;
                contactWork[i] = 0.0;
                contacts[i] = new NodeContact { tri = -1 };
                lastTri[i] = -1;
                lastBody[i] = -1;
                deferred[i] = new NodeImpulse { tri = -1 };
                dynForce[i] = float3.zero;
            }
            for (int j = b.beamStart; j < b.beamStart + b.beamCount; j++)
            {
                rest[j] = rest0[j];
                yield[j] = yield0[j];
                relaxArmed[j] = 0;
                broken[j] = 0;
                plasticWork[j] = 0f;
                breakEnergy[j] = 0f;
                stress[j] = 0f;
                beamForce[j] = float3.zero;
                dampEnergy[j] = 0.0;
            }
            for (int g = b.groupStart; g < b.groupStart + b.groupCount; g++)
            {
                groupTrigger[g] = 0;
                groupDone[g] = 0;
            }
            for (int t = b.torsionStart; t < b.torsionStart + b.torsionCount; t++)
            {
                torsionBroken[t] = 0;
                torsionAngle[t] = 0f;
                torsionDampEnergy[t] = 0.0;
            }
            for (int t = b.dampGroupStart; t < b.dampGroupStart + b.dampGroupCount; t++)
            {
                dampGroupEnergy[t] = 0.0;
                dampRigid[t] = default;
                var dg = dampGroups[t];
                for (int k = dg.nodeStart; k < dg.nodeStart + dg.nodeCount; k++)
                    dampForce[dampGroupNodes[k]] = float3.zero;
            }
            for (int t = b.hingeStart; t < b.hingeStart + b.hingeCount; t++)
            {
                hingeRest[t] = hinges[t].phi0;
                hingeYield[t] = hinges[t].yield0;
                hingeBroken[t] = 0;
                hingeAngle[t] = 0f;
                hingePlastic[t] = 0f;
                hingeDampEnergy[t] = 0.0;
            }
            for (int g = b.pressureStart; g < b.pressureStart + b.pressureCount; g++)
            {
                var pg = pressureGroups[g];
                pressureState[g] = new PressureState { volume = pg.volume0, gas = pg.gas0, pAbs = pg.gas0 / pg.volume0 };
                pressureScale[g] = 1f;
            }
            for (int w = b.wheelStart; w < b.wheelStart + b.wheelCount; w++)
                wheelState[w] = new WheelState { absFactor = 1f, absI = 1f };
            if (b.vehicleIndex >= 0)
            {
                var st = new VehicleState();
                st.velocity = b.spawnVelocity;
                st.forward = math.rotate(b.spawnRotation, new float3(0f, 0f, 1f));
                st.speed = math.dot(b.spawnVelocity, st.forward);
                st.tcFactor = 1f;
                st.tcI = 1f;
                st.engineOn = 1;
                InitDriveline(b, ref st);
                vehicleState[b.vehicleIndex] = st;
                bodyAccel[bi] = float3.zero;
                foreach (var kv in b.hydroIndex)
                    hydroInput[kv.Value] = 0f;
            }
            bodyAge[bi] = 0f;
            spawnBlend[bi] = b.prm.spawnRamp > 0f ? 0f : 1f;
        }

        /// <summary>Powertrain state for driving at st.speed in automatic drive: the gear for the speed, the axle side turning
        /// with the wheels, the lock-up clutch closed when the speed allows it (spawn, teleport at speed, launch).</summary>
        void InitDriveline(Body b, ref VehicleState st)
        {
            var vs = vehicles[b.vehicleIndex];
            st.gear = 1;
            st.shiftTimer = 0f;
            st.shiftDir = 0;
            st.locked = 0;
            st.lockRamp = 0f;
            st.shaftAngle = 0f;
            st.lsdStuck = 0;
            st.lsdAngle = 0f;
            if (vs.mode != PowertrainMode.Engine)
                return;
            float wheel = math.max(st.speed, 0f) / vs.rollingRadius;
            var pt = b.prm.powertrain;
            int g = 1;
            while (g < vs.gearCount && wheel * pt.gearRatios[g - 1] * vs.finalDrive > vs.shiftUpLightOmega)
                g++;
            st.gear = g;
            st.ratio = pt.gearRatios[g - 1] * vs.finalDrive;
            st.carrierOmega = wheel;
            st.engineOmega = vs.idleOmega;
            if (g >= vs.lockupMinGear && st.speed > vs.lockupSpeed)
            {
                st.locked = 1;
                st.lockRamp = 1f;
                st.engineOmega = math.max(st.ratio * wheel, vs.idleOmega);
            }
            st.engineRpm = st.engineOmega / RadPerRpm;
        }

        /// <summary>
        /// Sets a body moving at a velocity: every node translates with it; for a vehicle the wheels (rim and tread nodes)
        /// also spin at the rolling speed about their axles and the powertrain is put in the gear for the speed (automatic
        /// drive), the axle side turning with the wheels. Use after <see cref="Settle"/>: a settled car launched at speed
        /// starts with its static tire squash and spring preloads (tests, "teleport to an obstacle at speed V").
        /// </summary>
        public void Launch(int bi, float3 velocity)
        {
            var b = bodies[bi];
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                if (invMass[i] > 0f)
                    vel[i] = velocity;
            if (b.vehicleIndex < 0)
                return;
            var vs = vehicles[b.vehicleIndex];
            var st = vehicleState[b.vehicleIndex];
            float3 front = float3.zero, rear = float3.zero;
            int nf = 0, nr = 0;
            for (int w = b.wheelStart; w < b.wheelStart + b.wheelCount; w++)
            {
                var ws = wheels[w];
                float3 c = 0.5f * (pos[ws.axleInner] + pos[ws.axleOuter]);
                if (ws.steered != 0) { front += c; nf++; } else { rear += c; nr++; }
            }
            if (nf > 0 && nr > 0)
                st.forward = math.normalize(front / nf - rear / nr);
            st.velocity = velocity;
            st.speed = math.dot(velocity, st.forward);
            float rr = vs.rollingRadius > 0f ? vs.rollingRadius : 0.35f;
            for (int w = b.wheelStart; w < b.wheelStart + b.wheelCount; w++)
            {
                var ws = wheels[w];
                float3 hub = 0.5f * (pos[ws.axleInner] + pos[ws.axleOuter]);
                float3 axis = ws.axisSign * math.normalizesafe(pos[ws.axleOuter] - pos[ws.axleInner], new float3(1f, 0f, 0f));
                float3 heading = math.normalizesafe(math.cross(axis, new float3(0f, 1f, 0f)), st.forward);
                float3 spin = axis * (math.dot(velocity, heading) / rr);
                var wd = b.def.wheels[w - b.wheelStart];
                foreach (int n in wd.rim)
                    vel[b.nodeStart + n] = velocity + math.cross(spin, pos[b.nodeStart + n] - hub);
                foreach (int n in wd.tread)
                    vel[b.nodeStart + n] = velocity + math.cross(spin, pos[b.nodeStart + n] - hub);
            }
            InitDriveline(b, ref st);
            vehicleState[b.vehicleIndex] = st;
        }

        /// <summary>Punctures a pressure group (a nail in the tread, a cut sidewall): an extra leak of <paramref name="rate"/>
        /// 1/s on top of the leaks of broken tire beams (d(p V)/dt = -rate (p - p_atm) V). 0 seals it again.</summary>
        public void Puncture(int pressureGroup, float rate)
        {
            var st = pressureState[pressureGroup];
            st.puncture = math.max(rate, 0f);
            pressureState[pressureGroup] = st;
        }

        /// <summary>Moves a body's spawn pose (and resets it there). Use for "reset to last safe position" and teleports.</summary>
        public void Respawn(int bi, float3 position, quaternion rotation, float3 velocity)
        {
            var b = bodies[bi];
            b.spawnPosition = position;
            b.spawnRotation = rotation;
            b.spawnVelocity = velocity;
            PlaceSpawn(bi);
            ResetBody(bi);
            // the collision grid's rebuild schedule restarts here: what follows a respawn does not depend on the
            // substeps taken before it (replays that start from a respawn are bit-identical, D-070)
            clock[1] = clock[0];
        }

        public void SetInput(int vehicleIndex, DriverInput input)
        {
            for (int s = 0; s < maxSubsteps; s++)
                inputs[vehicleIndex * maxSubsteps + s] = input;
        }

        public void SetInput(int vehicleIndex, int substep, DriverInput input)
        {
            inputs[vehicleIndex * maxSubsteps + substep] = input;
        }

        /// <summary>
        /// Settled spawn (D-037): relaxes one body to its static equilibrium on the statics by kinetic damping (all of the
        /// body's velocities are zeroed whenever its kinetic energy passes a peak), so a parked car starts at rest with
        /// its tires squashed, the springs at their static length and the brake, wind-up and friction preloads in place,
        /// instead of dropping from the unloaded model pose and bouncing. Rest lengths, angles and volumes keep their
        /// model values (the shape is not re-referenced); the clock keeps running (the spawn ramp completes). Inputs
        /// must be set before. Converged when the kinetic energy peak between two resets is below the tolerance.
        /// Returns the number of velocity resets (-1: not converged within maxSeconds).
        /// </summary>
        public int Settle(int bi, double maxSeconds = 4.0, double keTolerance = 1e-3)
        {
            var b = bodies[bi];
            const int chunk = 10;
            long steps = (long)math.round(maxSeconds / dt);
            double kePrev = 0.0, peak = 0.0;
            int resets = 0;
            bool converged = false;
            for (long s = 0; s < steps && !converged; s += chunk)
            {
                UpdateNearLists(chunk * dt + 0.05f);
                Step(chunk);
                double ke = 0.0;
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                    if (invMass[i] > 0f)
                        ke += 0.5 * math.lengthsq(vel[i]) / invMass[i];
                peak = math.max(peak, ke);
                if (ke < kePrev)
                {
                    converged = peak < keTolerance && resets > 0;
                    for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                        vel[i] = float3.zero;
                    StopDriveline(b);
                    resets++;
                    kePrev = 0.0;
                    peak = 0.0;
                }
                else
                {
                    kePrev = ke;
                }
            }
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                vel[i] = float3.zero;
            StopDriveline(b);
            return converged ? resets : -1;
        }

        /// <summary>Kinetic damping of the driveline with the nodes (settled spawn): the axle side stops with the wheels.</summary>
        void StopDriveline(Body b)
        {
            if (b.vehicleIndex < 0)
                return;
            var st = vehicleState[b.vehicleIndex];
            st.carrierOmega = 0f;
            if (st.locked != 0)
                st.engineOmega = math.max(st.ratio * st.carrierOmega, vehicles[b.vehicleIndex].idleOmega);
            vehicleState[b.vehicleIndex] = st;
        }

        /// <summary>Per frame: static primitives near each body (AABB of the nodes + motion margin).</summary>
        /// <summary>Zero the contact-impulse accumulator (validation: the mean contact force over a frame is the
        /// accumulated impulse divided by the frame time, which is the force the node actually felt).</summary>
        public void ClearContactImp()
        {
            for (int i = 0; i < NodeCount; i++)
                contactImp[i] = float3.zero;
        }

        public void UpdateNearLists(float lookahead)
        {
            for (int bi = 0; bi < bodies.Count; bi++)
            {
                var b = bodies[bi];
                float3 lo = new float3(float.MaxValue), hi = new float3(float.MinValue);
                float vmax = 0f;
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                {
                    lo = math.min(lo, pos[i]);
                    hi = math.max(hi, pos[i]);
                    vmax = math.max(vmax, math.lengthsq(vel[i]));
                }
                float margin = 0.25f + math.sqrt(vmax) * lookahead;
                lo -= margin;
                hi += margin;
                int start = nearStart[bi], count = 0;
                for (int p = 0; p < prims.Length && count < MaxNearPerBody; p++)
                {
                    var pr = prims[p];
                    if (pr.type != PrimType.Plane &&
                        (math.any(pr.aabbMax < lo) || math.any(pr.aabbMin > hi)))
                        continue;
                    nearPrims[start + count++] = p;
                }
                nearCount[bi] = count;
            }
        }

        // ------------------------------------------------------------------ stepping

        public bool UsesSingleThread => forceSingleThread || BeamCount < parallelThreshold;

        /// <summary>Schedules <paramref name="substeps"/> fixed steps. Inputs must be set before.</summary>
        public JobHandle ScheduleSubsteps(int substeps, JobHandle dependency = default)
        {
            if (substeps <= 0)
                return dependency;
            if (substeps > maxSubsteps)
                throw new ArgumentOutOfRangeException(nameof(substeps), $"at most {maxSubsteps} per call");
            var stepParams = new StepParams
            {
                dt = dt,
                gravity = new float3(0f, -worldParams.gravity, 0f),
                maxNodeSpeed = worldParams.maxNodeSpeed,
            };
            var serial = MakeSerialJob();
            var beamJob = MakeBeamJob();
            var hingeJob = MakeHingeJob();
            var dampJob = MakeDampJob();
            var relDampJob = MakeRelDampJob();
            var nodeJob = MakeNodeJob(stepParams);
            var contactJob = MakeContactJob();
            var scatterJob = MakeScatterJob();
            var postJob = MakePostJob();
            int coll = CollisionEnabled ? 1 : 0;

            if (UsesSingleThread)
            {
                var st = new SingleThreadStepJob
                {
                    substeps = substeps,
                    beamCount = BeamCount,
                    hingeCount = HingeCount,
                    dampGroupCount = DampGroupCount,
                    nodeCount = NodeCount,
                    collisionEnabled = coll,
                    serial = serial,
                    beams = beamJob,
                    hingeJob = hingeJob,
                    dampJob = dampJob,
                    relDampJob = relDampJob,
                    contact = contactJob,
                    scatter = scatterJob,
                    nodes = nodeJob,
                    post = postJob,
                };
                return st.Schedule(dependency);
            }

            JobHandle h = dependency;
            for (int s = 0; s < substeps; s++)
            {
                serial.substepIndex = s;
                h = serial.Schedule(h);
                h = beamJob.Schedule(BeamCount, beamBatch, h);
                if (HingeCount > 0)
                    h = hingeJob.Schedule(HingeCount, hingeBatch, h);
                if (DampGroupCount > 0)
                {
                    h = dampJob.Schedule(DampGroupCount, 1, h);
                    h = relDampJob.Schedule(h);
                }
                if (coll != 0)
                {
                    h = contactJob.Schedule(NodeCount, nodeBatch, h);
                    h = scatterJob.Schedule(h);
                }
                h = nodeJob.Schedule(NodeCount, nodeBatch, h);
                if (coll != 0)
                    h = postJob.Schedule(h);
            }
            return h;
        }

        public void Step(int substeps) => ScheduleSubsteps(substeps).Complete();

        SerialPhaseJob MakeSerialJob() => new SerialPhaseJob
        {
            hasVehicles = VehicleCount > 0 ? 1 : 0,
            hasForceElements = TorsionBarCount + PressureGroupCount > 0 ? 1 : 0,
            collisionEnabled = CollisionEnabled ? 1 : 0,
            rebuildEvery = collisionParams.rebuildEvery,
            dt = dt,
            spawnRamp = bodies.Count > 0 ? bodies[0].prm.spawnRamp : 0f,
            groupTrigger = groupTrigger,
            groupDone = groupDone,
            groupBeamStart = groupBeamStart,
            groupBeams = groupBeams,
            broken = broken,
            bodyAge = bodyAge,
            spawnBlend = spawnBlend,
            clock = clock,
            counters = counters,
            frictionAxes = frictionAxes,
            axisPos = pos,
            nodeLat = nodeLat,
            frictionAxisCount = frictionAxisCount,
            control = new VehicleControlJob
            {
                dt = dt,
                maxSubsteps = maxSubsteps,
                pos = pos,
                vel = vel,
                contactFn = contactFn,
                contactSlip = contactSlip,
                contactSurface = contactSurface,
                surfaces = surfaces,
                vehicles = vehicles,
                wheels = wheels,
                rimNodes = rimNodes,
                knuckleNodes = knuckleNodes,
                driveNodes = driveNodes,
                windupNodes = windupNodes,
                groupDone = groupDone,
                treadNodes = treadNodes,
                refNodes = refNodes,
                engineCurve = engineCurve,
                gearRatios = gearRatios,
                inputs = inputs,
                vehicleState = vehicleState,
                wheelState = wheelState,
                hydroInput = hydroInput,
                slotForce = slotForce,
                bodyAccel = bodyAccel,
            },
            forces = new ForceElementPhase
            {
                dt = dt,
                trackEnergy = trackEnergy ? 1 : 0,
                pos = pos,
                vel = vel,
                broken = broken,
                groupDone = groupDone,
                slotForce = slotForce,
                torsionBars = torsionBars,
                torsionBroken = torsionBroken,
                torsionAngle = torsionAngle,
                torsionDampEnergy = torsionDampEnergy,
                pressureGroups = pressureGroups,
                pressureState = pressureState,
                pressureTris = pressureTris,
                leakBeams = leakBeams,
                pressureScale = pressureScale,
            },
            grid = new CollisionGridPhase
            {
                dt = dt,
                prm = collisionParams,
                pos = pos,
                vel = vel,
                bodyNodes = bodyNodes,
                bodyColl = bodyColl,
                tris = collTris,
                groupDone = groupDone,
                bodyLo = bodyLo,
                bodyHi = bodyHi,
                bodyInsert = bodyInsert,
                bodyOthers = bodyOthers,
                bodySelf = bodySelf,
                selfNodes = selfNodes,
                bucketStart = bucketStart,
                bucketFill = bucketFill,
                entryKey = entryKey,
                entryTri = entryTri,
                counters = collCounters,
            },
            sleep = new TailSleepPhase
            {
                tailNodeStart = tailNodeStart,
                nodeCount = NodeCount,
                checkEvery = TailCheckEvery,
                quietChecks = TailQuietChecks,
                wakeGap = TailWakeGap,
                sleepGap = TailSleepGap,
                sleepSpeed = TailSleepSpeed,
                pos = pos,
                vel = vel,
                invMass = invMass,
                state = tailSleep,
            },
        };

        GroupDampJob MakeDampJob() => new GroupDampJob
        {
            dt = dt,
            trackEnergy = trackEnergy ? 1 : 0,
            pos = pos,
            vel = vel,
            invMass = invMass,
            groupDone = groupDone,
            groups = dampGroups,
            groupNodes = dampGroupNodes,
            groupNodeBg = dampGroupNodeBg,
            dampForce = dampForce,
            groupDampEnergy = dampGroupEnergy,
            rigid = dampRigid,
        };

        GroupRelDampJob MakeRelDampJob() => new GroupRelDampJob
        {
            dt = dt,
            trackEnergy = trackEnergy ? 1 : 0,
            pos = pos,
            vel = vel,
            invMass = invMass,
            groupDone = groupDone,
            groups = dampGroups,
            groupNodes = dampGroupNodes,
            groupNodeBg = dampGroupNodeBg,
            rigid = dampRigid,
            dampForce = dampForce,
            groupDampEnergy = dampGroupEnergy,
            reactF = dampReactF,
            reactT = dampReactT,
        };

        HingeForceJob MakeHingeJob() => new HingeForceJob
        {
            dt = dt,
            trackEnergy = trackEnergy ? 1 : 0,
            pos = pos,
            vel = vel,
            broken = broken,
            hinges = hinges,
            hingeRest = hingeRest,
            hingeYield = hingeYield,
            hingeBroken = hingeBroken,
            hingeAngle = hingeAngle,
            hingePlastic = hingePlastic,
            hingeDampEnergy = hingeDampEnergy,
            slotForce = slotForce,
        };

        BeamForceJob MakeBeamJob() => new BeamForceJob
        {
            dt = dt,
            trackEnergy = trackEnergy ? 1 : 0,
            pos = pos,
            vel = vel,
            beams = beams,
            hydroInput = hydroInput,
            spawnBlend = spawnBlend,
            pressureScale = pressureScale,
            dampRigid = dampRigid,
            rest = rest,
            yield = yield,
            relaxArmed = relaxArmed,
            broken = broken,
            plasticWork = plasticWork,
            breakEnergy = breakEnergy,
            stress = stress,
            dampEnergy = dampEnergy,
            beamForce = beamForce,
            groupTrigger = groupTrigger,
            tailBeamStart = tailBeamStart,
            tailSleep = tailSleep,
        };

        NodeIntegrateJob MakeNodeJob(StepParams stepParams) => new NodeIntegrateJob
        {
            prm = stepParams,
            trackEnergy = trackEnergy ? 1 : 0,
            useDynamic = CollisionEnabled ? 1 : 0,
            dynForce = dynForce,
            dampForce = dampForce,
            contactWork = contactWork,
            pos = pos,
            vel = vel,
            invMass = invMass,
            flags = nodeFlags,
            nodeBody = nodeBody,
            nodeCmat = nodeCmat,
            beamAdjStart = beamAdjStart,
            beamAdjCode = beamAdjCode,
            beamForce = beamForce,
            slotAdjStart = slotAdjStart,
            slotAdjIndex = slotAdjIndex,
            slotForce = slotForce,
            extForce = extForce,
            bodyAccel = bodyAccel,
            prims = prims,
            planes = planes,
            nearStart = nearStart,
            nearCount = nearCount,
            nearPrims = nearPrims,
            cmats = cmats,
            surfaces = surfaces,
            anchor = anchor,
            anchorPrim = anchorPrim,
            contactLatch = contactLatch,
            contactFn = contactFn,
            contactSlip = contactSlip,
            contactSurface = contactSurface,
            frictionPower = frictionPower,
            contactImp = contactImp,
            nodeLat = nodeLat,
            tailNodeStart = tailNodeStart,
            tailSleep = tailSleep,
        };

        NodeContactJob MakeContactJob() => new NodeContactJob
        {
            dt = dt,
            prm = collisionParams,
            pos = pos,
            vel = vel,
            invMass = invMass,
            flags = nodeFlags,
            nodeBody = nodeBody,
            nodePart = nodePart,
            nodeCmat = nodeCmat,
            cmats = cmats,
            tris = collTris,
            groupDone = groupDone,
            bucketStart = bucketStart,
            entryKey = entryKey,
            entryTri = entryTri,
            counters = collCounters,
            bodyOthers = bodyOthers,
            contacts = contacts,
            lastTri = lastTri,
            lastSide = lastSide,
            lastNormal = lastNormal,
            lastBody = lastBody,
            tested = tested,
            tailNodeStart = tailNodeStart,
            tailSleep = tailSleep,
        };

        ContactScatterJob MakeScatterJob() => new ContactScatterJob
        {
            dt = dt,
            tris = collTris,
            contacts = contacts,
            tested = tested,
            deferred = deferred,
            dynForce = dynForce,
            counters = collCounters,
        };

        PostContactJob MakePostJob() => new PostContactJob
        {
            prm = collisionParams,
            pos = pos,
            vel = vel,
            invMass = invMass,
            tris = collTris,
            contacts = contacts,
            deferred = deferred,
            counters = collCounters,
        };

        /// <summary>Rank-one couplings of the vehicles for the exact stability S (D-024, D-036, D-042): per wheel the brake
        /// holding spring (rim vs knuckle) and the wind-up element (knuckle vs body) about the spin axis; per driven wheel
        /// of an engine-mode vehicle the half-shaft spring (rim vs the axle-side inertia, taken as fixed: the bound for the
        /// rim) and the LSD clutch pack (left rim vs right rim). Node lists with the gradient of the relative angle
        /// ((J^-1 e) x r_i per set, centroid radii, as the couples) and the weight dt^2 K + 2 dt C.</summary>
        public List<(int[] nodes, double3[] grads, double weight)> VehicleCouplings()
        {
            var list = new List<(int[], double3[], double)>();
            if (!IsBuilt)
                return list;
            int[] Set(NativeArray<int> src, int start, int count)
            {
                var a = new int[count];
                for (int k = 0; k < count; k++)
                    a[k] = src[start + k];
                return a;
            }
            float3 Axis(in WheelStatic ws) => ws.axisSign * math.normalizesafe(pos[ws.axleOuter] - pos[ws.axleInner], new float3(1f, 0f, 0f));
            double3[] Grad(int[] set, float3 axis, double sign)
            {
                // d(e.w)/dx_i of the least-squares rotation w = J^-1 sum r x v: (J^-1 e) x r_i (as the couples)
                double3 c = double3.zero;
                foreach (int n in set)
                    c += (double3)pos[n];
                c /= math.max(set.Length, 1);
                double xx = 0, yy = 0, zz = 0, xy = 0, xz = 0, yz = 0;
                var r = new double3[set.Length];
                for (int k = 0; k < set.Length; k++)
                {
                    double3 d = (double3)pos[set[k]] - c;
                    r[k] = d;
                    xx += d.y * d.y + d.z * d.z;
                    yy += d.x * d.x + d.z * d.z;
                    zz += d.x * d.x + d.y * d.y;
                    xy -= d.x * d.y;
                    xz -= d.x * d.z;
                    yz -= d.y * d.z;
                }
                double reg = 1e-6 * (xx + yy + zz) + 1e-12;
                var jm = new double3x3(xx + reg, xy, xz, xy, yy + reg, yz, xz, yz, zz + reg);
                double3 a = math.mul(math.inverse(jm), (double3)axis);
                var g = new double3[set.Length];
                for (int k = 0; k < set.Length; k++)
                    g[k] = sign * math.cross(a, r[k]);
                return g;
            }
            (int[], double3[], double) Pair(int[] a, float3 axisA, int[] bset, float3 axisB, double weight)
            {
                var n = new int[a.Length + bset.Length];
                var g = new double3[n.Length];
                var ga = Grad(a, axisA, 1.0);
                var gb = Grad(bset, axisB, -1.0);
                for (int k = 0; k < a.Length; k++) { n[k] = a[k]; g[k] = ga[k]; }
                for (int k = 0; k < bset.Length; k++) { n[a.Length + k] = bset[k]; g[a.Length + k] = gb[k]; }
                return (n, g, weight);
            }
            for (int wi = 0; wi < wheels.Length; wi++)
            {
                var ws = wheels[wi];
                if (ws.rimCount == 0)
                    continue;
                float3 axis = Axis(ws);
                var rim = Set(rimNodes, ws.rimStart, ws.rimCount);
                var kn = Set(knuckleNodes, ws.knuckleStart, ws.knuckleCount);
                if (kn.Length > 0)
                    list.Add(Pair(rim, axis, kn, axis, dt * dt * ws.stickK + 2.0 * dt * ws.stickC));
                if (ws.windupCount > 0 && wheelState[wi].windupBroken == 0 && kn.Length > 0)
                    list.Add(Pair(kn, axis, Set(windupNodes, ws.windupStart, ws.windupCount), axis, dt * dt * ws.windupK + 2.0 * dt * ws.windupC));
                var vs = vehicles[ws.vehicle];
                if (vs.mode == PowertrainMode.Engine && ws.driven != 0)
                    list.Add((rim, Grad(rim, axis, 1.0), dt * dt * 0.5 * vs.shaftK + 2.0 * dt * 0.5 * vs.shaftC));
            }
            for (int v = 0; v < VehicleCount; v++)
            {
                var vs = vehicles[v];
                if (vs.mode != PowertrainMode.Engine || vs.diffLeft < 0)
                    continue;
                var wl = wheels[vs.diffLeft];
                var wr = wheels[vs.diffRight];
                list.Add(Pair(Set(rimNodes, wr.rimStart, wr.rimCount), Axis(wr), Set(rimNodes, wl.rimStart, wl.rimCount), Axis(wl),
                    dt * dt * vs.diffK + 2.0 * dt * vs.diffC));
            }
            return list;
        }

        // ------------------------------------------------------------------ metrics

        public struct BodyMetrics
        {
            public float mass;
            public float3 centerOfMass, velocity, angularMomentum;
            public double kinetic, gravity, elastic, torsion, pressure;   // J, stored / potential (relative to spawn);
                                                                          // torsion includes the panel hinges
            public double damping, plastic, breaking, contactWork;        // J, cumulative since spawn
            public double driveline;   // J stored on the axle side of the driveline: carrier (and, locked, engine) kinetic
                                       // energy, half-shaft and LSD spring energy (D-042)
            public double aeroWork;    // J, work of the aerodynamic forces since spawn (negative: drag)
            public double driveWork;   // J, work of the gearbox output on the driveline's axle side since spawn
            public int brokenBeams, plasticBeams, plasticHinges;
            public float maxNodeSpeed;
            public int nonFinite;
            public double Mechanical => kinetic + gravity + elastic + torsion + pressure + driveline;
            public double Dissipated => damping + plastic + breaking;
        }

        /// <param name="energies">false: skip the elastic / torsion / pressure energies (per-frame HUD and cameras)</param>
        public BodyMetrics Metrics(int bi, bool energies = true)
        {
            var b = bodies[bi];
            var r = new BodyMetrics();
            float g = worldParams.gravity;
            double3 mp = double3.zero, mv = double3.zero;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
            {
                float im = invMass[i];
                if (im <= 0f)
                    continue;
                double m = 1.0 / im;
                float3 p = pos[i], v = vel[i];
                if (!math.all(math.isfinite(p)) || !math.all(math.isfinite(v)))
                {
                    r.nonFinite++;
                    continue;
                }
                r.mass += (float)m;
                mp += m * (double3)p;
                mv += m * (double3)v;
                r.kinetic += 0.5 * m * math.lengthsq((double3)v);
                r.gravity += m * g * (p.y - pos0[i].y);
                r.maxNodeSpeed = math.max(r.maxNodeSpeed, math.length(v));
                r.contactWork += contactWork[i];
            }
            if (r.mass > 0f)
            {
                r.centerOfMass = (float3)(mp / r.mass);
                r.velocity = (float3)(mv / r.mass);
                double3 l = double3.zero;
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                {
                    float im = invMass[i];
                    if (im <= 0f)
                        continue;
                    l += (1.0 / im) * math.cross((double3)(pos[i] - r.centerOfMass), (double3)(vel[i] - r.velocity));
                }
                r.angularMomentum = (float3)l;
            }
            for (int j = b.beamStart; j < b.beamStart + b.beamCount; j++)
            {
                var s = beams[j];
                r.damping += dampEnergy[j];
                if (broken[j] != 0)
                {
                    r.brokenBeams++;
                    r.breaking += breakEnergy[j];
                    r.plastic += plasticWork[j];
                    continue;
                }
                if (energies)
                    r.elastic += BeamEnergy(j, s);
                r.plastic += plasticWork[j];
                if (math.abs(rest[j] - rest0[j]) > 1e-5f)
                    r.plasticBeams++;
            }
            for (int t = b.torsionStart; t < b.torsionStart + b.torsionCount; t++)
            {
                r.damping += torsionDampEnergy[t];
                if (torsionBroken[t] != 0 || !energies)
                    continue;
                var tb = torsionBars[t];
                if (TorsionKernel.Gradient(pos[tb.n1], pos[tb.n2], pos[tb.n3], pos[tb.n4], out float phi, out _, out _, out _, out _))
                {
                    float d = TorsionKernel.Wrap(phi - tb.phi0);
                    r.torsion += 0.5 * tb.k * d * d;
                }
            }
            for (int t = b.dampGroupStart; t < b.dampGroupStart + b.dampGroupCount; t++)
                r.damping += dampGroupEnergy[t];
            // wind-up elements (D-036): spring energy 1/2 K theta^2, damper dissipation; alignment springs (D-049)
            for (int k = b.wheelStart; k < b.wheelStart + b.wheelCount && b.vehicleIndex >= 0; k++)
            {
                var wst = wheelState[k];
                r.damping += wst.windupDamped;
                if (energies && wst.windupBroken == 0)
                    r.torsion += 0.5 * wheels[k].windupK * wst.windupAngle * wst.windupAngle;
            }
            if (energies && b.vehicleIndex >= 0)
                r.torsion += AlignmentEnergy(b);
            for (int t = b.hingeStart; t < b.hingeStart + b.hingeCount; t++)
            {
                r.damping += hingeDampEnergy[t];
                r.plastic += hingePlastic[t];
                if (math.abs(TorsionKernel.Wrap(hingeRest[t] - hinges[t].phi0)) > 1e-4f)
                    r.plasticHinges++;
                if (hingeBroken[t] != 0 || !energies)
                    continue;
                var h = hinges[t];
                if (TorsionKernel.Gradient(pos[h.n1], pos[h.n2], pos[h.n3], pos[h.n4], out float phi, out _, out _, out _, out _))
                {
                    float d = TorsionKernel.Wrap(phi - hingeRest[t]);
                    r.torsion += 0.5 * h.k * d * d;
                }
            }
            if (b.vehicleIndex >= 0)
            {
                var vs = vehicles[b.vehicleIndex];
                var st = vehicleState[b.vehicleIndex];
                r.damping += st.drivelineDamped;
                r.aeroWork = st.aeroWork;
                r.driveWork = st.driveWork;
                if (vs.mode == PowertrainMode.Engine && energies)
                {
                    double gr = st.ratio;
                    double ic = vs.outputInertia + vs.turbineInertia * gr * gr + (st.locked != 0 ? vs.engineInertia * gr * gr : 0.0);
                    r.driveline = 0.5 * ic * st.carrierOmega * st.carrierOmega + 0.5 * vs.shaftK * st.shaftAngle * st.shaftAngle
                                  + (st.lsdStuck != 0 ? 0.5 * vs.diffK * st.lsdAngle * st.lsdAngle : 0.0);
                }
            }
            for (int pg = b.pressureStart; pg < b.pressureStart + b.pressureCount && energies; pg++)
            {
                var gs = pressureGroups[pg];
                var st = pressureState[pg];
                double v = math.max(CavityVolume(gs), gs.minVolume);
                // isothermal gas below a sealed cavity: U = -gas ln(V / V0) + p_atm (V - V0)
                r.pressure += -st.gas * math.log(v / gs.volume0) + gs.pAtm * (v - gs.volume0);
            }
            return r;
        }

        /// <summary>Elastic energy of the alignment springs (D-049) at the current positions, as the control job measures them:
        /// body frame from the wind-up body sets, camber / toe of every axle line against static + gain x travel.</summary>
        double AlignmentEnergy(Body b)
        {
            float3 sf = float3.zero, sr = float3.zero, sR = float3.zero, sL = float3.zero;
            int cf = 0, cr = 0, cR = 0, cL = 0;
            for (int k = b.wheelStart; k < b.wheelStart + b.wheelCount; k++)
            {
                var ws = wheels[k];
                if (ws.windupCount == 0)
                    continue;
                float3 cw = float3.zero;
                for (int q = 0; q < ws.windupCount; q++)
                    cw += pos[windupNodes[ws.windupStart + q]];
                cw /= ws.windupCount;
                if (ws.front != 0) { sf += cw; cf++; } else { sr += cw; cr++; }
                if (ws.side > 0f) { sR += cw; cR++; } else { sL += cw; cL++; }
            }
            if (cf == 0 || cr == 0 || cR == 0 || cL == 0)
                return 0.0;
            float3 bF = math.normalizesafe(sf / cf - sr / cr), bR = math.normalizesafe(sR / cR - sL / cL);
            float3 bU = math.normalizesafe(math.cross(bF, bR));
            if (math.lengthsq(bU) < 0.5f)
                return 0.0;
            bR = math.cross(bU, bF);
            double e = 0.0;
            for (int k = b.wheelStart; k < b.wheelStart + b.wheelCount; k++)
            {
                var ws = wheels[k];
                if (ws.windupCount == 0 || wheelState[k].windupBroken != 0 || ws.camberK + ws.toeK <= 0f)
                    continue;
                float3 bc = float3.zero;
                for (int q = 0; q < ws.windupCount; q++)
                    bc += pos[windupNodes[ws.windupStart + q]];
                bc /= ws.windupCount;
                float3 aOut = math.normalizesafe(pos[ws.axleOuter] - pos[ws.axleInner]);
                float3 hub = 0.5f * (pos[ws.axleInner] + pos[ws.axleOuter]);
                float travel = math.dot(hub - bc, bU) - ws.travel0;
                float toe = math.asin(math.clamp(math.dot(aOut, bF), -1f, 1f));
                float3 kp = ws.kingpin.x * bR + ws.kingpin.y * bU + ws.kingpin.z * bF;
                float camber = math.acos(math.clamp(math.dot(aOut, kp), -1f, 1f)) - ws.kingpinPhi0;
                double eC = camber - (ws.camberStatic + ws.camberGain * travel);
                double eT = toe - (ws.toeStatic + ws.bumpSteer * travel);
                e += 0.5 * ws.camberK * eC * eC + 0.5 * ws.toeK * eT * eT;
            }
            return e;
        }

        /// <summary>Elastic energy of one intact beam, consistent with the force law of BeamKernel.</summary>
        /// <summary>Elastic energy of one beam now (0 when broken): spring, limit spring, cavity pretension.</summary>
        public double BeamElasticEnergy(int j) => broken[j] != 0 ? 0.0 : BeamEnergy(j, beams[j]);

        /// <summary>Beam j's spring-back suppression is armed (it has flowed plastically and not unloaded since, D-056).</summary>
        public bool RelaxArmed(int j) => relaxArmed[j] != 0;

        double BeamEnergy(int j, in BeamStatic s)
        {
            float len = math.distance(pos[s.a], pos[s.b]);
            float l0;
            if (s.type == BeamType.Hydro)
            {
                float h = s.hydro >= 0 ? hydroInput[s.hydro] : 0f;
                l0 = s.spawnRest * math.clamp(1f + s.hydroFactor * h, s.hydroMinRatio, s.hydroMaxRatio);
            }
            else
            {
                float blend = spawnBlend[s.body];
                l0 = s.rampBase + (rest[j] - s.rampBase) * blend;
            }
            double x = len - l0;
            double e = 0.0;
            if (s.type == BeamType.Support && x > 0.0)
                return 0.0;
            double k = s.type == BeamType.Anisotropic && x > 0.0 ? s.kExp : s.k;
            if (s.pressureGroup >= 0)
                k *= 1.0 - s.inflationShare * (1.0 - pressureScale[s.pressureGroup]);
            e += 0.5 * k * x * x;
            if (s.pressureGroup >= 0)
                e += s.pretension * pressureScale[s.pressureGroup] * (len - s.spawnLength);
            if (s.type == BeamType.Bounded && s.kLimit > 0f)
            {
                double ex = len < s.shortLen ? s.shortLen - len : len > s.longLen ? len - s.longLen : 0.0;
                if (ex > 0.0)
                {
                    double z = s.boundZone;
                    e += ex <= z ? s.kLimit * ex * ex * ex / (3.0 * z) : s.kLimit * (z * z / 3.0 + 0.5 * (ex * ex - z * z));
                }
            }
            return e;
        }

        double CavityVolume(in PressureGroupStatic pg)
        {
            float3 o = pos[pressureTris[pg.triStart].x];
            double v = 0.0;
            for (int t = pg.triStart; t < pg.triStart + pg.triCount; t++)
            {
                int3 tri = pressureTris[t];
                v += math.dot((double3)(pos[tri.x] - o), math.cross((double3)(pos[tri.y] - o), (double3)(pos[tri.z] - o)));
            }
            return v / 6.0;
        }

        /// <summary>Hoop tension (N) a ring beam of a spinning wheel carries now (D-044): spinCoef |w|^2 of its group's
        /// rigid rotation in the last substep; 0 for other beams.</summary>
        public float SpinTension(int beam)
        {
            var s = beams[beam];
            if (s.spinGroup < 0)
                return 0f;
            var rg = dampRigid[s.spinGroup];
            return rg.valid != 0 ? s.spinCoef * (float)math.lengthsq(rg.w) : 0f;
        }

        /// <summary>Rest length of a beam at spawn (for deformation displays).</summary>
        public float SpawnRest(int beam) => rest0[beam];

        /// <summary>Spawn position of a node (after the clearance lift).</summary>
        public float3 SpawnPosition(int node) => pos0[node];

        public void Dispose()
        {
            if (!IsBuilt && owned.Count == 0)
                return;
            foreach (var d in owned)
                d.Dispose();
            owned.Clear();
            IsBuilt = false;
        }
    }
}
