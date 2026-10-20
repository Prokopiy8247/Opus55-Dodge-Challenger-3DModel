"""P7: sleeping debris in the solver (D-098) - the serial phase's sleep check, the jobs' early-outs, the world's tail."""
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / "Unity/HellcatSandbox/Assets/Sim/Core"


def patch(path, reps):
    raw = io.open(path, encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in raw else "\n"
    s = raw.replace("\r\n", "\n")
    for a, b in reps:
        assert s.count(a) == 1, (path.name, a[:80], s.count(a))
        s = s.replace(a, b)
    io.open(path, "w", encoding="utf-8", newline="").write(s.replace("\n", nl))
    print("ok", path.name)


patch(SIM / "SerialPhaseJob.cs", [
    ("""        public Vehicle.VehicleControlJob control;
        public ForceElementPhase forces;
        public CollisionGridPhase grid;""",
     """        public Vehicle.VehicleControlJob control;
        public ForceElementPhase forces;
        public CollisionGridPhase grid;
        public TailSleepPhase sleep;   // sleeping debris (D-098)"""),
    ("""            long step = clock[0];
            clock[0] = step + 1;
""",
     """            long step = clock[0];
            clock[0] = step + 1;
            sleep.Execute(step);
"""),
])

patch(SIM / "SimJobs.cs", [
    ("""        [NativeDisableContainerSafetyRestriction] [NativeDisableParallelForRestriction] public NativeArray<byte> groupTrigger;

        public void Execute(int i)
        {
            BeamStatic s = beams[i];""",
     """        [NativeDisableContainerSafetyRestriction] [NativeDisableParallelForRestriction] public NativeArray<byte> groupTrigger;
        public int tailBeamStart;                                                     // sleeping debris (D-098)
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> tailSleep;

        public void Execute(int i)
        {
            if (i >= tailBeamStart && tailSleep[0] != 0)
                return;
            BeamStatic s = beams[i];"""),
    ("""        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> nodeLat;  // lateral friction axis (D-048), zero: isotropic

        public void Execute(int i)
        {
            float im = invMass[i];""",
     """        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> nodeLat;  // lateral friction axis (D-048), zero: isotropic
        public int tailNodeStart;                                                     // sleeping debris (D-098)
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> tailSleep;

        public void Execute(int i)
        {
            if (i >= tailNodeStart && tailSleep[0] != 0)
                return;
            float im = invMass[i];"""),
])

patch(SIM / "DynamicCollision.cs", [
    ("""        [NativeDisableContainerSafetyRestriction] public NativeArray<int> tested;       // candidates per node (stats)

        public void Execute(int i)
        {
            var rec = new NodeContact { tri = -1 };
            int fl = flags[i];
            if (counters[CollisionCounter.Entries] == 0 || (fl & (NodeFlag.Collision | NodeFlag.SelfCollision)) == 0 || invMass[i] <= 0f ||
                ((fl & NodeFlag.SelfCollision) == 0 && bodyOthers[nodeBody[i]] == 0))""",
     """        [NativeDisableContainerSafetyRestriction] public NativeArray<int> tested;       // candidates per node (stats)
        public int tailNodeStart;                                                     // sleeping debris (D-098)
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> tailSleep;

        public void Execute(int i)
        {
            var rec = new NodeContact { tri = -1 };
            int fl = flags[i];
            if (counters[CollisionCounter.Entries] == 0 || (fl & (NodeFlag.Collision | NodeFlag.SelfCollision)) == 0 || invMass[i] <= 0f ||
                ((fl & NodeFlag.SelfCollision) == 0 && bodyOthers[nodeBody[i]] == 0) || (i >= tailNodeStart && tailSleep[0] != 0))"""),
])

patch(SIM / "SoftBodyWorld.cs", [
    ("""            public int collTriStart, collTriCount;
            public float3 spawnPosition;""",
     """            public int collTriStart, collTriCount;
            public bool sleepable;                   // part of the sleeping tail (D-098): debris added after the vehicles
            public float3 spawnPosition;"""),
    ("""        NativeArray<T> Alloc<T>(int length) where T : struct
        {""",
     """        // sleeping debris (D-098): the sleepable bodies at the end of the body list; see TailSleepPhase
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

        /// <summary>Wakes the sleeping tail (debris moved by the game, e.g. put back in place).</summary>
        public void WakeTail()
        {
            if (!tailSleep.IsCreated)
                return;
            tailSleep[0] = 0;
            tailSleep[1] = 0;
        }

        NativeArray<T> Alloc<T>(int length) where T : struct
        {"""),
    ("""            NodeCount = nNodes;
            BeamCount = nBeams;""",
     """            NodeCount = nNodes;
            BeamCount = nBeams;
            // the sleeping tail (D-098): the sleepable bodies at the end of the list, after at least one other body
            int tb = bodies.Count;
            while (tb > 0 && bodies[tb - 1].sleepable)
                tb--;
            bool tail = tb > 0 && tb < bodies.Count;
            tailNodeStart = tail ? bodies[tb].nodeStart : nNodes;
            tailBeamStart = tail ? bodies[tb].beamStart : nBeams;
            tailSleep = Alloc<int>(2);"""),
    ("""            groupTrigger = groupTrigger,
        };

        NodeIntegrateJob MakeNodeJob(StepParams stepParams) => new NodeIntegrateJob""",
     """            groupTrigger = groupTrigger,
            tailBeamStart = tailBeamStart,
            tailSleep = tailSleep,
        };

        NodeIntegrateJob MakeNodeJob(StepParams stepParams) => new NodeIntegrateJob"""),
    ("""            contactImp = contactImp,
            nodeLat = nodeLat,
        };""",
     """            contactImp = contactImp,
            nodeLat = nodeLat,
            tailNodeStart = tailNodeStart,
            tailSleep = tailSleep,
        };"""),
    ("""            lastBody = lastBody,
            tested = tested,
        };""",
     """            lastBody = lastBody,
            tested = tested,
            tailNodeStart = tailNodeStart,
            tailSleep = tailSleep,
        };"""),
    ("""                counters = collCounters,
            },
        };

        GroupDampJob MakeDampJob() => new GroupDampJob""",
     """                counters = collCounters,
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

        GroupDampJob MakeDampJob() => new GroupDampJob"""),
])
