using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using Hellcat.Game.Cameras;
using Hellcat.Game.Capture;
using Hellcat.Game.Core;
using Hellcat.Game.Views;
using Hellcat.Game.World;
using Hellcat.Sim;
using Hellcat.Sim.Props;
using Hellcat.Sim.Validation;
using Hellcat.Sim.Vehicle;
using Unity.Mathematics;
using UnityEngine;

namespace Hellcat.Game.Scenario
{
    /// <summary>
    /// The scripted scenarios of brief 9 (P6; S1 began in P4 on its own crash scene): the Hellcat is respawned settled on a
    /// test-map lane and driven up to the entry speed by a speed hold and lane keeping (programmatic inputs, so results
    /// compare between builds), then the event (S1 / S2 / S3 / S8 frontal into a wall or pole, S4 / S6 glancing along a
    /// barrier row or guardrail, S5 the ramp jump and landing, S7 pushing through the debris) and the time after it.
    /// Recorded per frame: the cabin centre of mass (deceleration over 4 ms, the 1 kHz velocity near the obstacle for the
    /// CFC 60 pulse), crush, the body's deformation and the intrusion into the passenger cell against the rigid rear cabin,
    /// broken and plastic beams, detached parts, the energy ledger (kinetic, elastic, pressure, plastic, breaking, damping,
    /// contact work), tunnelling into the obstacle and the skinning checks; frames from four cameras (tracking, side,
    /// front three-quarter, top). The run's driver inputs are recorded (<c>.hrec</c>, the world snapshot at the start); after
    /// the run the recording is replayed from its snapshot - with the event re-rendered at 250 fps from three cameras (the
    /// slow-motion variant) - and the replay's end state is compared bit for bit with the run's. Command line:
    ///   -scenario S1..S8 -out &lt;dir&gt; [-targetKmh v] [-capture 1] [-captureWidth 1280 -captureHeight 720] [-launch 1]
    ///   [-lateral m] [-lead s] [-postImpact s] [-slowmo 1] [-replayCheck 1] [-breakGlass s]
    /// (-launch 1: the settled car starts rolling at the target speed, for speeds the run-up does not reach: S8 at 120 km/h)
    /// </summary>
    public class CarCrashScenario : MonoBehaviour, IDriverInputSource
    {
        public enum Kind { Frontal, Glancing, Jump, Debris }

        /// <summary>One scripted scenario: the test map's lane (spawn label), the obstacle's objects, entry speed, the kind
        /// of event, the capture window and the camera layout in the lane frame (along the lane from the obstacle face,
        /// right of the lane, up).</summary>
        public sealed class Spec
        {
            public string id, lane, what;
            public string[] targets;                  // name prefixes of the obstacle's static objects (null: the debris)
            public float kmh;
            public Kind kind;
            public bool launch;                       // start rolling at the speed
            public bool wheelLine;                    // lane offset: the left front wheel in line with the obstacle (S3)
            public float lead = 3f, post = 4f;        // s captured before the first contact and after the event
            public float slowBefore = 0.3f, slowAfter = 1.0f;   // slow-motion window round the contact (S5: the landing)
            public float focus;                       // m along the lane from the face where the action is
            public float side = 1f;                   // side camera right (+1) or left (-1) of the lane
            public float sideDist = 13f, sideHeight = 1.4f, sideFov = 32f;
            public Vector3 quarter = new Vector3(-7.5f, 2.6f, -9f);   // three-quarter camera: (x side, up, along) from the focus
            public float quarterFov = 40f;
            public float topHeight = 16f, topFov = 30f;
            public bool topAcross;                    // top view with the lane across the image (long events)
        }

        public static readonly Spec[] Specs =
        {
            new Spec { id = "S1", lane = "O1", targets = new[] { "O1_Wall" }, kmh = 50f, kind = Kind.Frontal,
                what = "full frontal into the O1 rigid wall" },
            new Spec { id = "S2", lane = "O2", targets = new[] { "O2_Wall" }, kmh = 64f, kind = Kind.Frontal, side = -1f,
                what = "40 % offset frontal (driver side) into the O2 wall" },
            new Spec { id = "S3", lane = "O3", targets = new[] { "O3_Pole" }, kmh = 50f, kind = Kind.Frontal,
                what = "O3 pole, centred (aimed at the front axle)" },
            new Spec { id = "S4", lane = "O4", targets = new[] { "O4_Jersey" }, kmh = 40f, kind = Kind.Glancing, slowAfter = 1.2f,
                focus = 1f, sideDist = 15f, sideFov = 42f, quarter = new Vector3(9f, 3.5f, 17f), topHeight = 22f, topFov = 42f, topAcross = true,
                what = "into the O4 jersey-barrier row at 20 deg" },
            new Spec { id = "S5", lane = "O6", targets = new[] { "O6_Ramp" }, kmh = 80f, kind = Kind.Jump, lead = 2f, post = 3.5f,
                slowBefore = 0.6f, slowAfter = 0.9f, focus = 18f, side = -1f, sideDist = 27f, sideHeight = 2.5f, sideFov = 50f,
                quarter = new Vector3(-10f, 3f, 30f), topHeight = 42f, topFov = 50f, topAcross = true,
                what = "O6 ramp jump and landing" },
            new Spec { id = "S6", lane = "O5", targets = new[] { "O5_" }, kmh = 70f, kind = Kind.Glancing, slowAfter = 1.2f,
                focus = 4f, side = -1f, sideDist = 14f, sideHeight = 1.8f, sideFov = 45f, quarter = new Vector3(8f, 2.5f, 16f),
                topHeight = 22f, topFov = 45f, topAcross = true, what = "O5 guardrail scrape at 10 deg" },
            new Spec { id = "S7", lane = "O8", targets = null, kmh = 15f, kind = Kind.Debris, lead = 2.5f, post = 6f, slowAfter = 1.5f,
                focus = 24f, sideDist = 12f, sideHeight = 2f, sideFov = 50f, quarter = new Vector3(-8f, 3f, 16f),
                topHeight = 25f, topFov = 50f, topAcross = true, what = "low-speed push through the O8 debris" },
            new Spec { id = "S8", lane = "O1", targets = new[] { "O1_Wall" }, kmh = 120f, kind = Kind.Frontal, launch = true,
                what = "120 km/h full frontal into the O1 wall (rolling start)" },
        };

        public static Spec Find(string id) => Array.Find(Specs, s => string.Equals(s.id, id, StringComparison.OrdinalIgnoreCase));

        public SimRunner runner;
        public SoftBodyCarView carView;
        public SkinningProbe probe;
        [Tooltip("Fixed capture cameras (P4 crash scene); empty: tracking, side, front three-quarter and top in the lane frame")]
        public Camera[] cameras;
        [Tooltip("P4 crash scene: the wall (on the test map each scenario finds its obstacle's objects by name)")]
        public Transform obstacle;
        public PropField props;
        public string scenarioId = "S1";
        public float targetKmh = 50f;
        public float settleTime = 0.5f;
        public float postImpactTime = 3.0f;
        public bool runFromCommandLineOnly = true;
        public string outDir = "";
        public bool capture = true;
        public int captureWidth = 1280, captureHeight = 720;
        public float captureLeadTime = 3f;
        /// <summary>s after the first contact counted as the impact pulse (the skinning probe keeps the cabin's transient
        /// trim folds of that window apart, G-Crash).</summary>
        const double PulseWindow = 0.15;
        [Tooltip("Captured frames per simulated second")]
        public int fps = 60;
        [Tooltip("Slow-motion replay: frames per simulated second (8 substeps per frame at 250)")]
        public int slowFps = 250;
        public bool launchAtTarget;
        public bool slowMotion = true, replayCheck = true;
        [Tooltip("Test of the pre-fractured glass: break every glass beam this long after the impact (negative: never)")]
        public float breakGlassAfter = -1f;

        public int Priority => 10;
        public bool Active => running || replaying;

        Spec spec;
        bool running, replaying, viewReset;
        float time;                     // simulated s since the start of the scenario
        long startStep, steps;          // world substeps at the start, substeps since
        double simStart;                // world time at the start
        int frames;
        float maxTime = 40f;
        float impactTime = -1f;         // the event: first contact (frontal, glancing), the landing (jump), the first prop hit
        float speedAtImpact, prevSpeed;
        float peakCabinG, peakCabinGt, peakFrameG, peakVecG, peakLatG, peakVertG;
        float3 lastCabinVel;
        bool haveCabin;
        int frameIndex;
        float captureStart = -1f;
        string runId;
        float initialLength, cabinFront0, bodyFront0, bodyFrontL0, bodyFrontR0;
        float3 laneO, laneF, laneR;     // lane frame: origin on the lane line at the spawn (offset included), forward, right
        float3 face;                    // obstacle face on the lane
        float lateral;
        int[] targets = Array.Empty<int>();
        int maxTunnelled;
        string tunnelledNames = "";
        float maxVertexJump, maxVertexJumpT, maxInverted, maxStretch, maxSpike, maxSpikeT, maxExcess, maxExcessT, maxRot, maxRotT;
        string maxExcessMesh = "", maxVertexJumpMesh = "", maxSpikeMesh = "", jumpReport = "", endReport = "";
        // dynamic crush: cabin travel along the lane from the first contact until the cabin stops (1 ms steps)
        double contactSimTime = -1, stopSimTime = -1, dynamicCrush, rebound;
        float prevChunkVf;
        float entrySpeed = float.NaN;
        // passive energy check: kinetic + stored + dissipated must not rise after the contact (statics are passive)
        double balanceAtContact = double.NaN, energyCreated, driveAtContact;
        double stepMs;
        CrashMetrics crash;
        CrashDiagnostics.ClosureWatch closures;
        readonly List<string> rows = new List<string>();
        DriverInput current = DriverInput.Idle;
        float holdI;                    // speed hold: integral of the speed error
        readonly List<float> cabinG4ms = new List<float>();
        readonly List<string> skinLog = new List<string>();
        // captures are rendered at the end of the frame, after Unity has skinned the car for this frame (GPU skinning runs in
        // PostLateUpdate: a Camera.Render() in Update drew the skinned meshes of an older frame, partly stale)
        readonly List<(Camera cam, string path, int w, int h, bool jpg)> pending = new List<(Camera, string, int, int, bool)>();
        bool quitAfterCapture;
        readonly List<string> pulse = new List<string> { "t_s,cabin_vx_mps,cabin_vy_mps,cabin_vz_mps,cabin_vf_mps,gap_m" };
        bool near;
        // 4 ms window of the cabin velocity (peaks after the first contact)
        readonly List<(double t, float3 v)> window = new List<(double, float3)>();
        // glancing: time in contact, speed and heading when the car last left the obstacle
        double contactDuration;
        bool inContact;
        float exitSpeed = float.NaN, exitHeading = float.NaN;
        // jump: airborne interval (no tread node touching after the ramp), landing
        double airStart = -1, takeoffSim = -1, landSim = -1;
        float airSpeed, takeoffSpeed, landingVy, lastVy, jumpDistance;
        float3 airCom;
        int underbodyMax, rimMax;
        bool[] isRim;
        int[] stopBeams = Array.Empty<int>();   // closure perimeter stops (D-034): they release, they do not break
        // deformation and intrusion
        double maxDeformDyn;
        double[] intrusionDyn;
        // debris
        float3[] propStart;
        float debrisLastAlong = float.MinValue;
        bool passedDebris;
        int propsMoved;
        float propsMaxDisp;
        float lowestNode = float.MaxValue;
        int belowGroundMax, belowGroundTireMax, belowGroundCollMax;
        string lowestNodeInfo = "";
        // nodes that collide with the ground and the obstacles (the inner suspension and driveline nodes do not)
        float lowestColliding = float.MaxValue;
        string lowestCollidingInfo = "";
        // recording and replay
        InputRecording rec, replayRec;
        string recPath = "";
        ulong runHash, replayHash;
        long runSteps, replayStart;
        int slowFrames;
        bool replayIdentical;
        string replayNote = "";
        ChaseCamera chase;
        readonly List<(string key, string json)> result = new List<(string, string)>();

        static readonly CultureInfo Ic = CultureInfo.InvariantCulture;

        void Start()
        {
            var args = Environment.GetCommandLineArgs();
            string id = Arg(args, "-scenario", null);
            if (runFromCommandLineOnly && id == null)
            {
                enabled = false;
                return;
            }
            if (id != null) scenarioId = id;
            spec = Find(scenarioId);
            if (spec == null || Arg(args, "-driven", "0") == "1")
            {
                enabled = false;   // other scenarios of the player (mapcheck, drive, showcase) or the driven variant
                return;
            }
            // reports and logs with '.' decimals whatever the system locale (the summaries interpolate numbers)
            CultureInfo.CurrentCulture = CultureInfo.DefaultThreadCurrentCulture = Ic;
            targetKmh = float.Parse(Arg(args, "-targetKmh", spec.kmh.ToString(Ic)), Ic);
            outDir = Arg(args, "-out", string.IsNullOrEmpty(outDir) ? Path.Combine(Application.persistentDataPath, "scenario") : outDir);
            capture = Arg(args, "-capture", capture ? "1" : "0") == "1";
            captureWidth = int.Parse(Arg(args, "-captureWidth", captureWidth.ToString(Ic)), Ic);
            captureHeight = int.Parse(Arg(args, "-captureHeight", captureHeight.ToString(Ic)), Ic);
            launchAtTarget = Arg(args, "-launch", spec.launch ? "1" : "0") == "1";
            breakGlassAfter = float.Parse(Arg(args, "-breakGlass", breakGlassAfter.ToString(Ic)), Ic);
            fps = int.Parse(Arg(args, "-fps", fps.ToString(Ic)), Ic);
            postImpactTime = float.Parse(Arg(args, "-postImpact", spec.post.ToString(Ic)), Ic);
            captureLeadTime = float.Parse(Arg(args, "-lead", spec.lead.ToString(Ic)), Ic);
            slowMotion = Arg(args, "-slowmo", capture ? "1" : "0") == "1";
            replayCheck = Arg(args, "-replayCheck", "1") == "1" && breakGlassAfter < 0f;   // the glass test breaks beams by hand
            runId = $"{scenarioId}_{targetKmh:F0}kmh";
            Directory.CreateDirectory(outDir);
            Time.captureFramerate = fps;           // 1/fps s per frame: deterministic simulated time per frame
            runner.paused = true;                  // this script steps the solver (4 ms chunks, 1 ms near the obstacle)
            runner.RegisterInput(this);

            var w = runner.World;
            var sp = FindLane(spec.lane);
            float approach;
            if (sp != null)
            {
                var fw = sp.transform.forward;
                laneF = math.normalizesafe(new float3(fw.x, 0f, fw.z));
                laneR = new float3(laneF.z, 0f, -laneF.x);
                lateral = float.Parse(Arg(args, "-lateral", (spec.wheelLine ? WheelLine() : 0f).ToString(Ic)), Ic);
                laneO = (float3)sp.transform.position + laneR * lateral;
                approach = sp.approachDistance;
                runner.RespawnSettled(laneO, Quaternion.LookRotation(laneF, Vector3.up), launchAtTarget ? targetKmh / 3.6f : 0f);
            }
            else
            {
                // P4 crash scene: the car already settled at the scene's spawn, the lane along +z to the wall
                laneO = runner.spawnPoint ? (float3)runner.spawnPoint.position : float3.zero;
                laneF = new float3(0f, 0f, 1f);
                laneR = new float3(1f, 0f, 0f);
                approach = obstacle ? obstacle.position.z - 0.5f * obstacle.lossyScale.z - laneO.z : 70f;
                if (launchAtTarget)
                    w.Launch(runner.VehicleBody, laneF * (targetKmh / 3.6f));
            }
            face = laneO + laneF * approach;
            maxTime = 1f + (approach + 40f) / math.max(targetKmh / 3.6f, 1f) + postImpactTime + 5f;
            targets = TargetPrims();
            startStep = w.StepsTaken;
            simStart = runner.SimTime;

            crash = new CrashMetrics(w, runner.VehicleBody);
            closures = new CrashDiagnostics.ClosureWatch(w, runner.VehicleBody, CrashDiagnostics.CabinNodes(w.bodies[runner.VehicleBody].def));
            var def = w.bodies[runner.VehicleBody].def;
            isRim = new bool[def.nodes.Length];
            for (int i = 0; i < isRim.Length; i++)
                isRim[i] = def.nodes[i].name.Contains("_rim");
            intrusionDyn = new double[crash.intrusionGroups.Count];
            var bodyDef = w.bodies[runner.VehicleBody];
            stopBeams = Enumerable.Range(0, bodyDef.beamCount).Where(k => def.beams[k].mat == "stop_closure").Select(k => bodyDef.beamStart + k).ToArray();
            initialLength = VehicleLength();
            crash.Fronts(laneO, laneF, out cabinFront0, out _);
            crash.Cabin(out float3 c0, out _);
            float ca0 = math.dot(c0 - laneO, laneF);
            bodyFront0 = BodyFront(0) - ca0;
            bodyFrontL0 = BodyFront(-1) - ca0;
            bodyFrontR0 = BodyFront(1) - ca0;
            if (spec.kind == Kind.Debris && props != null)
            {
                propStart = new float3[props.Bodies.Count];
                for (int k = 0; k < propStart.Length; k++)
                {
                    propStart[k] = Centroid(w.bodies[props.Bodies[k]]);
                    float r = PropFactory.Radius(props.props[k].kind);
                    if (math.abs(math.dot(propStart[k] - laneO, laneR)) < 1.06f + r)
                        debrisLastAlong = math.max(debrisLastAlong, math.dot(propStart[k] - laneO, laneF) + r);
                }
            }
            if (capture && (cameras == null || cameras.Length == 0))
                cameras = MakeCameras();
            if (cameras != null)
                foreach (var c in cameras)
                    if (c && c.TryGetComponent(out ChaseCamera cc)) chase = cc;
            chase?.Snap();

            // the run's driver inputs from here, with the world's state as the start (the slow-motion replay restores it)
            rec = new InputRecording
            {
                vehicle = runner.vehicleName,
                note = $"{runId}: {spec.what}",
                createdUtc = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                dataHash = runner.DataHash,
                dt = w.dt,
                startStep = w.StepsTaken,
                start = InputRecording.StartKind.Snapshot,
                state = WorldState.Capture(w),
            };

            rows.Add("t,speed_kmh,cabin_x,cabin_y,cabin_z,cabin_decel_g,frame_decel_g,length_m,crush_m,cabin_front_m,broken,plastic_beams,detached," +
                     "kinetic_J,elastic_J,pressure_J,torsion_J,plastic_J,breaking_J,damping_J,contact_J,tunnelled,vertex_jump_mm,inverted_share," +
                     "throttle,brake,steer,gap_m,cabin_vf_mps,cabin_accel_g,max_deformation_m,props_moved,drive_work_J,aero_work_J");
            running = true;
            StartCoroutine(EndOfFrameCaptures());
            Debug.Log($"[CarCrash] {runId}: {spec.what}; target {targetKmh} km/h, lane {(sp ? sp.label : "scene spawn")}, lateral {lateral:F3} m, " +
                      $"{targets.Length} obstacle primitives, cabin {crash.CabinNodes} nodes ({crash.cabinMass:F0} kg), out {outDir}");
        }

        static string Arg(string[] args, string name, string fallback)
        {
            for (int i = 0; i < args.Length - 1; i++)
                if (string.Equals(args[i], name, StringComparison.OrdinalIgnoreCase))
                    return args[i + 1];
            return fallback;
        }

        static SpawnPoint FindLane(string lane)
        {
            if (string.IsNullOrEmpty(lane)) return null;
            return FindObjectsByType<SpawnPoint>(FindObjectsInactive.Exclude, FindObjectsSortMode.None)
                .OrderBy(s => s.order).FirstOrDefault(s => s.label.StartsWith(lane + " ", StringComparison.Ordinal));
        }

        /// <summary>Lateral offset that puts the left front tyre's centre plane on the lane line (model x of its tread).</summary>
        float WheelLine()
        {
            var def = runner.World.bodies[runner.VehicleBody].def;
            double x = 0;
            int n = 0;
            foreach (var nd in def.nodes)
                if (nd.name.StartsWith("FL_trC")) { x += nd.p[0]; n++; }
            return n > 0 ? (float)(-x / n) : 0.87f;
        }

        /// <summary>The obstacle's static primitives: those whose box centre lies in the bounds of the obstacle's renderers.</summary>
        int[] TargetPrims()
        {
            var bounds = new List<Bounds>();
            if (obstacle)
            {
                foreach (var r in obstacle.GetComponentsInChildren<Renderer>())
                    bounds.Add(r.bounds);
            }
            else if (spec.targets != null)
            {
                foreach (var r in FindObjectsByType<Renderer>(FindObjectsSortMode.None))
                    foreach (var p in spec.targets)
                        if (r.gameObject.name.StartsWith(p, StringComparison.Ordinal))
                        {
                            bounds.Add(r.bounds);
                            break;
                        }
            }
            var w = runner.World;
            var list = new List<int>();
            for (int k = 0; k < w.prims.Length; k++)
            {
                var prim = w.prims[k];
                if (prim.type == PrimType.Plane) continue;
                var c = (Vector3)(0.5f * (prim.aabbMin + prim.aabbMax));
                foreach (var bd in bounds)
                {
                    var e = bd;
                    e.Expand(0.1f);
                    if (e.Contains(c))
                    {
                        list.Add(k);
                        break;
                    }
                }
            }
            return list.ToArray();
        }

        Camera[] MakeCameras()
        {
            var s = spec;
            var up = new float3(0f, 1f, 0f);
            float3 p = face + laneF * s.focus;
            Camera Make(string name, float3 pos, float3 look, float fov, float3 upHint)
            {
                var go = new GameObject(name);
                var c = go.AddComponent<Camera>();
                c.enabled = false;              // rendered on demand into the capture texture
                c.fieldOfView = fov;
                c.nearClipPlane = 0.1f;
                c.farClipPlane = 1500f;
                CameraSky.Apply(c);
                go.transform.SetPositionAndRotation(pos, Quaternion.LookRotation((Vector3)(look - pos), upHint));
                return c;
            }
            var chaseCam = Make("chase", laneO - laneF * 7f + up * 2.4f, laneO + up * 0.8f, 50f, up);
            var cc = chaseCam.gameObject.AddComponent<ChaseCamera>();
            cc.runner = runner;
            var side = Make("side", p - laneF * 2.5f + laneR * (s.side * s.sideDist) + up * s.sideHeight, p - laneF * 2.5f + up * 0.8f, s.sideFov, up);
            var q = s.quarter;
            var quarter = Make("front34", p + laneF * q.z + laneR * (s.side * q.x) + up * q.y, p - laneF * 2f + up * 0.7f, s.quarterFov, up);
            var top = Make("top", p - laneF * 2.6f + up * s.topHeight, p - laneF * 2.5f, s.topFov, s.topAcross ? laneR : laneF);
            return new[] { chaseCam, side, quarter, top };
        }

        /// <summary>Front of the structure along the lane: the largest coordinate of the body-part nodes below 1.2 m (rails,
        /// crash boxes, core support) still connected to the cabin (a torn-off core support left at the wall is not the
        /// car's front); <paramref name="side"/> -1 / +1: only the left / right half (model x), 0 both.</summary>
        float BodyFront(int side)
        {
            var w = runner.World;
            var b = w.bodies[runner.VehicleBody];
            var on = crash.Connected();
            float hi = float.MinValue;
            for (int i = 0; i < b.nodeCount; i++)
            {
                var nd = b.def.nodes[i];
                if (!on[i] || nd.part != "body" || nd.p[1] >= 1.2f) continue;
                if (side != 0 && nd.p[0] * side < 0f) continue;
                hi = math.max(hi, math.dot(w.pos[b.nodeStart + i] - laneO, laneF));
            }
            return hi;
        }

        /// <summary>Length of the car along the lane over the non-tire nodes still connected to the cabin.</summary>
        float VehicleLength()
        {
            var w = runner.World;
            var b = w.bodies[runner.VehicleBody];
            var on = crash.Connected();
            float lo = float.MaxValue, hi = float.MinValue;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
            {
                if ((w.nodeFlags[i] & NodeFlag.Tire) != 0 || !on[i - b.nodeStart]) continue;
                float a = math.dot(w.pos[i] - laneO, laneF);
                lo = math.min(lo, a);
                hi = math.max(hi, a);
            }
            return hi - lo;
        }

        float3 Centroid(SoftBodyWorld.Body b)
        {
            var w = runner.World;
            float3 c = float3.zero;
            int n = 0;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
            {
                if (w.invMass[i] <= 0f) continue;
                c += w.pos[i];
                n++;
            }
            return n > 0 ? c / n : float3.zero;
        }

        public DriverInput Sample(long substepIndex, in VehicleState state) =>
            replaying ? replayRec.InputAt(substepIndex - replayStart) : current;

        /// <summary>Speed hold and lane keeping up to the event, then per kind: brake (frontal, glancing; the P4 law), hands
        /// and feet off in the air and brake after the landing (jump), keep pushing until the debris is passed (debris).</summary>
        DriverInput Control(in VehicleState st, float3 com)
        {
            float3 fwd = math.normalizesafe(st.forward);
            float target = targetKmh / 3.6f;
            float lat = math.dot(com - laneO, laneR);
            float headingErr = math.atan2(math.dot(fwd, laneR), math.dot(fwd, laneF));
            float steer = math.clamp(-1.5f * lat - 3f * headingErr, -1f, 1f);
            if (time < settleTime && !launchAtTarget)
                return new DriverInput { brake = 1f, gear = DriverInput.Drive, flags = DriverInput.FlagTc };
            float err = target - st.speed;
            if (math.abs(err) < 1f)
                holdI = math.clamp(holdI + 0.4f * err / fps, 0f, 0.8f);
            var hold = new DriverInput
            {
                throttle = math.saturate(err * 0.6f + 0.05f + holdI), steer = steer, gear = DriverInput.Drive, flags = DriverInput.FlagTc,
            };
            switch (spec.kind)
            {
                case Kind.Jump:
                    if (landSim >= 0)
                        return new DriverInput { brake = 0.6f, steer = steer, gear = DriverInput.Drive, flags = DriverInput.FlagAbs };
                    return airStart >= 0 ? new DriverInput { gear = DriverInput.Drive } : hold;
                case Kind.Debris:
                    return passedDebris ? new DriverInput { brake = 0.5f, steer = steer, gear = DriverInput.Drive, flags = DriverInput.FlagAbs } : hold;
                default:
                    return impactTime < 0f ? hold : new DriverInput { brake = 0.3f, gear = DriverInput.Drive };
            }
        }

        void Update()
        {
            if (!running)
                return;
            if (!viewReset && carView)
            {
                // the view starts after this script: its frames get the lane heading now (the respawn's reset found it not ready)
                carView.ResetVisualState();
                viewReset = true;
            }
            var w = runner.World;
            float frameDt = 1f / fps;
            var st = w.vehicleState[runner.VehicleIndex];
            crash.Cabin(out float3 cabinCom, out _);
            current = Control(st, cabinCom);

            // step the frame (whole substeps; frames of 33 and 34 at 60 fps) in 4 ms chunks, 1 ms near the obstacle; the
            // 1 kHz cabin velocity goes to <run>_pulse.csv (CFC 60 filtering in tools/gate_p6.py)
            frames++;
            int total = (int)(math.round(frames / (double)fps / w.dt) - steps);
            float3 v0 = haveCabin ? lastCabinVel : float3.zero;
            for (int done = 0; done < total;)
            {
                int n = math.min(near ? 2 : 8, total - done);
                runner.StepNow(n);
                stepMs += runner.LastStepMs;
                steps += n;
                done += n;
                double tNow = runner.SimTime;
                crash.Cabin(out float3 ccom, out float3 cv);
                float vf = math.dot(cv, laneF);
                if (haveCabin && impactTime >= 0f)
                    cabinG4ms.Add(-(vf - math.dot(lastCabinVel, laneF)) / (n * w.dt) / 9.81f);
                Window(tNow, cv);
                lastCabinVel = cv;
                haveCabin = true;
                float gap = near ? ChunkGap() : float.MaxValue;
                if (near)
                    crash.TrackPlates(targets, laneO);   // tunnelling through a plate (wall, guardrail beam)
                if (near && (impactTime < 0f || time - impactTime < (spec.kind == Kind.Frontal ? 0.6f : postImpactTime)))
                    pulse.Add(string.Format(Ic, "{0:F4},{1:F5},{2:F5},{3:F5},{4:F5},{5:F4}", tNow, cv.x, cv.y, cv.z, vf, math.min(gap, 99f)));
                if (contactSimTime < 0 && near && (spec.kind == Kind.Debris ? PropSpeed() > 0.3f : gap <= 0.002f))
                {
                    contactSimTime = tNow;
                    entrySpeed = math.max(w.vehicleState[runner.VehicleIndex].speed, vf);
                }
                if (spec.kind == Kind.Glancing && contactSimTime >= 0)
                {
                    bool touching = gap < 0.02f;
                    if (touching) contactDuration += n * w.dt;
                    if (inContact && gap > 0.05f)
                    {
                        float3 hv = new float3(cv.x, 0f, cv.z);
                        exitSpeed = math.length(hv);
                        float3 hf = math.normalizesafe(w.vehicleState[runner.VehicleIndex].forward);
                        exitHeading = math.degrees(math.atan2(math.dot(hf, laneR), math.dot(hf, laneF)));
                    }
                    inContact = touching || (inContact && gap <= 0.05f);
                }
                if (spec.kind == Kind.Jump && contactSimTime >= 0)
                    JumpChunk(tNow, ccom, cv);
                if (contactSimTime >= 0 && spec.kind == Kind.Frontal)
                {
                    if (stopSimTime < 0 && !double.IsNaN(dynamicCrush))
                    {
                        dynamicCrush += 0.5 * (vf + prevChunkVf) * n * w.dt;
                        if (vf <= 0f) stopSimTime = tNow;
                        else if (tNow - contactSimTime > 0.5) dynamicCrush = double.NaN;   // not stopped by the obstacle
                    }
                    else if (tNow - stopSimTime < 0.5)
                        rebound = math.max(rebound, -vf);
                }
                prevChunkVf = vf;
            }
            time = (float)(steps * w.dt);
            rec.Add(total, current);

            st = w.vehicleState[runner.VehicleIndex];
            var m = w.Metrics(runner.VehicleBody, true);
            // kinetic + stored + dissipated, less what the engine and the air put in or took out (the debris' own ledgers
            // included: the car hands them energy): must not rise after the contact
            double balance = m.Mechanical + m.Dissipated - m.driveWork - m.aeroWork + PropsEnergy();
            if (contactSimTime >= 0 && double.IsNaN(balanceAtContact))
            {
                balanceAtContact = balance;
                driveAtContact = m.driveWork;
            }
            if (!double.IsNaN(balanceAtContact))
                energyCreated = math.max(energyCreated, balance - balanceAtContact);
            if (contactSimTime >= 0)
                closures.Sample(runner.SimTime - contactSimTime);
            crash.Cabin(out cabinCom, out float3 cabinVel);
            float frameG = -math.dot(cabinVel - v0, laneF) / frameDt / 9.81f;
            crash.Fronts(laneO, laneF, out float cabinFront, out float carFront);
            float gapNow = FrameGap(carFront);
            near = near || gapNow < 1.0f || (spec.kind == Kind.Jump && contactSimTime >= 0);
            if (spec.kind == Kind.Debris && !passedDebris && carFront - initialLength > debrisLastAlong + 0.5f)
                passedDebris = true;
            if (impactTime < 0f && time > settleTime)
            {
                bool hit = spec.kind switch
                {
                    Kind.Frontal => gapNow < 0.02f || frameG > 3f,
                    Kind.Glancing => gapNow < 0.02f,
                    Kind.Jump => landSim >= 0,
                    _ => contactSimTime >= 0,
                };
                if (hit)
                {
                    impactTime = time;
                    speedAtImpact = prevSpeed;
                    Debug.Log($"[CarCrash] {(spec.kind == Kind.Jump ? "landing" : "impact")} at t={time:F3}s, speed {prevSpeed * 3.6f:F1} km/h, " +
                              $"entry {entrySpeed * 3.6f:F1} km/h");
                }
            }
            prevSpeed = math.max(st.speed, math.dot(cabinVel, laneF));
            if (impactTime >= 0f)
                peakFrameG = math.max(peakFrameG, frameG);

            var tnames = new List<string>();
            int tunnelled = crash.Tunnelled(targets, laneO, 0.001f, tnames);
            if (tunnelled > maxTunnelled)
                tunnelledNames = $"t+{time - impactTime:F3} s: " + string.Join(", ", tnames.Take(12));
            maxTunnelled = math.max(maxTunnelled, tunnelled);
            GroundCheck();
            if (breakGlassAfter >= 0f && impactTime >= 0f && time - impactTime >= breakGlassAfter)
            {
                BreakGlass();
                breakGlassAfter = -1f;
            }

            // deformation of the structure and intrusion into the cell against the rigid rear cabin
            var connected = crash.Connected();
            double deform = crash.MaxDeformation(connected, out _);
            if (contactSimTime >= 0)
            {
                maxDeformDyn = math.max(maxDeformDyn, deform);
                var intr = crash.Intrusions();
                for (int g = 0; g < intr.Length; g++)
                    intrusionDyn[g] = math.max(intrusionDyn[g], intr[g]);
            }
            if (propStart != null)
                PropsMoved();

            // skinning checks (the bones follow the nodes; the probe skins every vertex on the CPU)
            if (carView) carView.UpdateBones();
            float jump = 0f, inv = 0f;
            if (probe)
            {
                probe.Connected = connected;
                probe.time = time;
                probe.inPulse = contactSimTime >= 0 && runner.SimTime - contactSimTime < PulseWindow;
                probe.Measure();
                jump = probe.MaxFrameDisplacement;
                inv = probe.InvertedShare;
                if (probe.MaxSpike > maxSpike)
                {
                    maxSpike = probe.MaxSpike; maxSpikeT = time; maxSpikeMesh = probe.MaxSpikeMesh;
                }
                if (probe.MaxFrameRotationDeg > maxRot)
                {
                    maxRot = probe.MaxFrameRotationDeg; maxRotT = time;
                }
                if (probe.SpikeExcess > maxExcess)
                {
                    maxExcess = probe.SpikeExcess; maxExcessT = time; maxExcessMesh = probe.SpikeExcessMesh;
                }
                if (jump > maxVertexJump)
                {
                    maxVertexJump = jump; maxVertexJumpT = time; maxVertexJumpMesh = probe.MaxFrameDisplacementMesh;
                    jumpReport = probe.MeshReport();
                }
                maxInverted = math.max(maxInverted, inv);
                if (contactSimTime >= 0 && runner.SimTime - contactSimTime < 0.25)
                {
                    probe.Stretch();
                    var cr = closures.CabinFrame(out double3 cc, out double3 cc0);
                    skinLog.Add($"t+{(runner.SimTime - contactSimTime) * 1000:F0} ms frame {frameIndex}: {probe.MeshReport(8)} | " +
                                probe.RigidOffsetReport(cr, cc, cc0, 400));
                }
                if (frames <= 3)
                    probe.ResetHistory();   // the car's bones settle on the lane pose over the first frames after the respawn
                if (impactTime >= 0f && Mathf.Abs(time - impactTime - postImpactTime + 0.5f) < frameDt * 0.5f)
                {
                    maxStretch = probe.Stretch();
                    endReport = probe.MeshReport();
                }
            }

            float length = VehicleLength();
            float crushNow = bodyFront0 - (BodyFront(0) - math.dot(cabinCom - laneO, laneF));
            int detached = (frameIndex % 15 == 0 || impactTime >= 0f) ? crash.Detached().Count : -1;
            float accelG = window.Count > 0 ? lastAccel : 0f;
            rows.Add(string.Join(",", new[]
            {
                time.ToString("F4", Ic), (st.speed * 3.6f).ToString("F3", Ic), cabinCom.x.ToString("F4", Ic), cabinCom.y.ToString("F4", Ic),
                cabinCom.z.ToString("F4", Ic), (cabinG4ms.Count > 0 ? cabinG4ms[cabinG4ms.Count - 1] : 0f).ToString("F3", Ic), frameG.ToString("F3", Ic),
                length.ToString("F4", Ic), crushNow.ToString("F4", Ic), cabinFront.ToString("F4", Ic), (m.brokenBeams - StopsReleased()).ToString(Ic),
                m.plasticBeams.ToString(Ic), detached.ToString(Ic), m.kinetic.ToString("F1", Ic), m.elastic.ToString("F1", Ic), m.pressure.ToString("F1", Ic),
                m.torsion.ToString("F1", Ic), m.plastic.ToString("F1", Ic), m.breaking.ToString("F1", Ic), m.damping.ToString("F1", Ic),
                m.contactWork.ToString("F1", Ic), tunnelled.ToString(Ic), (jump * 1000f).ToString("F2", Ic), inv.ToString("F5", Ic),
                current.throttle.ToString("F3", Ic), current.brake.ToString("F3", Ic), current.steer.ToString("F4", Ic),
                math.min(gapNow, 999f).ToString("F4", Ic), math.dot(cabinVel, laneF).ToString("F4", Ic), accelG.ToString("F3", Ic),
                deform.ToString("F4", Ic), propsMoved.ToString(Ic), m.driveWork.ToString("F1", Ic), m.aeroWork.ToString("F1", Ic),
            }));

            if (capture && (impactTime >= 0f || gapNow < math.max(st.speed, 1f) * captureLeadTime))
            {
                string dir = Path.Combine(outDir, "frames");
                foreach (var cam in cameras)
                    if (cam) pending.Add((cam, Path.Combine(dir, $"{cam.name}_{frameIndex:D4}.jpg"), captureWidth, captureHeight, true));
                if (frameIndex == 0) captureStart = time;
                frameIndex++;
            }
            if (capture && impactTime >= 0f && Mathf.Abs(time - impactTime) < frameDt * 0.5f)
                Stills("at_impact");
            if ((impactTime >= 0f && time > impactTime + postImpactTime) || time > maxTime)
                Finish(m, length);
        }

        // ------------------------------------------------------------------ per-chunk measures

        float lastAccel;

        /// <summary>Cabin acceleration over the last 4 ms (peaks after the first contact): along the lane (deceleration
        /// positive), lateral, vertical and the vector's magnitude, in g (kinematic: an accelerometer adds 1 g up).</summary>
        void Window(double t, float3 v)
        {
            window.Add((t, v));
            while (window.Count > 2 && t - window[1].t >= 0.004 - 1e-7)
                window.RemoveAt(0);
            if (t - window[0].t < 0.004 - 1e-7)
                return;
            float3 a = (v - window[0].v) / (float)(t - window[0].t) / 9.81f;
            lastAccel = math.length(a);
            if (contactSimTime < 0)
                return;
            float dec = -math.dot(a, laneF);
            if (dec > peakCabinG)
            {
                peakCabinG = dec;
                peakCabinGt = (float)(t - contactSimTime);
            }
            peakVecG = math.max(peakVecG, math.length(a));
            peakLatG = math.max(peakLatG, math.abs(math.dot(a, laneR)));
            peakVertG = math.max(peakVertG, a.y);
        }

        /// <summary>Gap to the obstacle this chunk: the signed distance of the nearest node (statics), the distance along
        /// the lane to the nearest prop in the car's path (debris).</summary>
        float ChunkGap()
        {
            if (spec.kind == Kind.Debris)
            {
                crash.Fronts(laneO, laneF, out _, out float carFront);
                return DebrisGap(carFront);
            }
            float g = crash.Gap(targets, 1.5f, out _);
            return g;
        }

        /// <summary>Gap for the frame: as the chunk's, or along the lane to the obstacle face while the car is far.</summary>
        float FrameGap(float carFront)
        {
            if (spec.kind == Kind.Debris)
                return DebrisGap(carFront);
            float g = crash.Gap(targets, 1.5f, out _);
            return g < float.MaxValue ? g : math.dot(face - laneO, laneF) - carFront;
        }

        float DebrisGap(float carFront)
        {
            if (props == null) return float.MaxValue;
            var w = runner.World;
            float best = float.MaxValue;
            for (int k = 0; k < props.Bodies.Count; k++)
            {
                float3 c = Centroid(w.bodies[props.Bodies[k]]);
                float r = PropFactory.Radius(props.props[k].kind);
                if (math.abs(math.dot(c - laneO, laneR)) > 1.06f + r) continue;
                best = math.min(best, math.dot(c - laneO, laneF) - r - carFront);
            }
            return best;
        }

        float PropSpeed()
        {
            if (props == null) return 0f;
            var w = runner.World;
            float best = 0f;
            foreach (int bi in props.Bodies)
            {
                var b = w.bodies[bi];
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                    if (w.invMass[i] > 0f)
                        best = math.max(best, math.length(w.vel[i]));
            }
            return best;
        }

        void PropsMoved()
        {
            var w = runner.World;
            int n = 0;
            float best = 0f;
            for (int k = 0; k < propStart.Length; k++)
            {
                float d = math.distance(Centroid(w.bodies[props.Bodies[k]]), propStart[k]);
                if (d > 0.05f) n++;
                best = math.max(best, d);
            }
            propsMoved = n;
            propsMaxDisp = best;
        }

        /// <summary>Jump: the airborne interval after the ramp contact (no tread node touching); the landing ends the first
        /// interval longer than 0.2 s; body and rim nodes touching in the 0.5 s after it (underbody and rim strikes).</summary>
        void JumpChunk(double t, float3 com, float3 cv)
        {
            var w = runner.World;
            var b = w.bodies[runner.VehicleBody];
            bool tread = false;
            int body = 0, rim = 0;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
            {
                if (w.contactFn[i] <= 0f) continue;
                if ((w.nodeFlags[i] & NodeFlag.Tire) != 0) tread = true;
                else if (isRim[i - b.nodeStart]) rim++;
                else body++;
            }
            if (landSim >= 0 && t - landSim < 0.5)
            {
                underbodyMax = math.max(underbodyMax, body);
                rimMax = math.max(rimMax, rim);
            }
            if (!tread)
            {
                if (airStart < 0)
                {
                    airStart = t;
                    airSpeed = math.length(cv);
                    airCom = com;
                }
                lastVy = cv.y;
            }
            else if (airStart >= 0)
            {
                if (landSim < 0 && t - airStart > 0.2)
                {
                    takeoffSim = airStart;
                    landSim = t;
                    takeoffSpeed = airSpeed;
                    landingVy = lastVy;
                    jumpDistance = math.dot(com - airCom, laneF);
                    underbodyMax = math.max(underbodyMax, body);
                    rimMax = math.max(rimMax, rim);
                    Debug.Log($"[CarCrash] airborne {landSim - takeoffSim:F3} s over {jumpDistance:F1} m, take-off {takeoffSpeed * 3.6f:F1} km/h, " +
                              $"landing vertical speed {landingVy:F2} m/s");
                }
                airStart = -1;
            }
        }

        /// <summary>Shortening (m) of one side's wheelbase: the outer axle centres, model distance minus now.</summary>
        double WheelbaseChange(string side)
        {
            var w = runner.World;
            var b = w.bodies[runner.VehicleBody];
            int f = -1, r = -1;
            for (int i = 0; i < b.nodeCount; i++)
            {
                if (b.def.nodes[i].name == $"F{side}_axle_out") f = i;
                if (b.def.nodes[i].name == $"R{side}_axle_out") r = i;
            }
            if (f < 0 || r < 0) return double.NaN;
            var pf = b.def.nodes[f].p;
            var pr = b.def.nodes[r].p;
            double rest = math.distance(new double3(pf[0], pf[1], pf[2]), new double3(pr[0], pr[1], pr[2]));
            return rest - math.distance((double3)w.pos[b.nodeStart + f], (double3)w.pos[b.nodeStart + r]);
        }

        /// <summary>Debris run: the props' kinetic, stored and dissipated energy (zero otherwise).</summary>
        double PropsEnergy()
        {
            if (spec.kind != Kind.Debris || props == null) return 0.0;
            var w = runner.World;
            double e = 0.0;
            foreach (int bi in props.Bodies)
            {
                var pm = w.Metrics(bi, true);
                e += pm.Mechanical + pm.Dissipated;
            }
            return e;
        }

        int StopsReleased()
        {
            var w = runner.World;
            int n = 0;
            foreach (int j in stopBeams)
                if (w.broken[j] != 0) n++;
            return n;
        }

        void GroundCheck()
        {
            var w = runner.World;
            var b = w.bodies[runner.VehicleBody];
            int below = 0, belowTire = 0, belowColl = 0;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
            {
                float y = w.pos[i].y;
                bool tire = (w.nodeFlags[i] & NodeFlag.Tire) != 0;
                bool coll = (w.nodeFlags[i] & NodeFlag.StaticCollision) != 0;
                if (y < lowestNode)
                {
                    lowestNode = y;
                    lowestNodeInfo = NodeInfo(b, i, tire, coll);
                }
                if (coll && y < lowestColliding)
                {
                    lowestColliding = y;
                    lowestCollidingInfo = NodeInfo(b, i, tire, coll);
                }
                if (y < -0.02f)
                {
                    below++;
                    if (tire) belowTire++;
                    if (coll) belowColl++;
                }
            }
            belowGroundMax = math.max(belowGroundMax, below);
            belowGroundTireMax = math.max(belowGroundTireMax, belowTire);
            belowGroundCollMax = math.max(belowGroundCollMax, belowColl);
        }

        string NodeInfo(SoftBodyWorld.Body b, int i, bool tire, bool coll)
        {
            var w = runner.World;
            return $"{b.def.nodes[i - b.nodeStart].name} at t={time:F3} s, x {w.pos[i].x:F2} z {w.pos[i].z:F2}" +
                   (tire ? ", tread" : "") + (coll ? ", static-colliding" : ", not colliding with statics");
        }

        /// <summary>Glass test (-breakGlass): every beam of the panes' glass materials is broken, so the car view swaps in the
        /// pre-fractured shards and the panes' nodes are left on their mounts.</summary>
        void BreakGlass()
        {
            var w = runner.World;
            var b = w.bodies[runner.VehicleBody];
            int n = 0;
            for (int k = 0; k < b.beamCount; k++)
            {
                string mat = b.def.beams[k].mat;
                if ((mat == "glass" || mat == "glass_side") && w.broken[b.beamStart + k] == 0)
                {
                    w.broken[b.beamStart + k] = 1;
                    n++;
                }
            }
            Debug.Log($"[CarCrash] glass test: broke {n} glass beams");
        }

        void Stills(string tag)
        {
            foreach (var cam in cameras)
                if (cam) pending.Add((cam, Path.Combine(outDir, $"{runId}_{tag}_{cam.name}.png"), 1920, 1080, false));
        }

        IEnumerator EndOfFrameCaptures()
        {
            var eof = new WaitForEndOfFrame();
            while (true)
            {
                yield return eof;
                foreach (var (cam, path, w, h, jpg) in pending)
                    FrameCapture.Save(cam, path, w, h, jpg);
                pending.Clear();
                if (quitAfterCapture)
                {
                    Application.Quit(0);
#if UNITY_EDITOR
                    UnityEditor.EditorApplication.isPlaying = false;
#endif
                    yield break;
                }
            }
        }

        // ------------------------------------------------------------------ results

        void Put(string key, string json)
        {
            int i = result.FindIndex(r => r.key == key);
            if (i >= 0) result[i] = (key, json);
            else result.Add((key, json));
        }

        static string F(double v, string f = "F3") => double.IsFinite(v) ? v.ToString(f, Ic) : "null";
        static string Q(string s) =>
            "\"" + (s ?? "").Replace("\\", "/").Replace("\"", "'").Replace("\r", "").Replace("\n", " | ").Replace("\t", " ") + "\"";

        void WriteResult()
        {
            var sb = new StringBuilder("{\n");
            for (int i = 0; i < result.Count; i++)
                sb.Append($"  \"{result[i].key}\": {result[i].json}{(i + 1 < result.Count ? "," : "")}\n");
            sb.Append("}\n");
            File.WriteAllText(Path.Combine(outDir, $"{runId}_result.json"), sb.ToString());
        }

        void Finish(SoftBodyWorld.BodyMetrics m, float length)
        {
            running = false;
            if (capture) Stills("final");
            var w = runner.World;
            File.WriteAllText(Path.Combine(outDir, $"{runId}_timeseries.csv"), string.Join("\n", rows));
            File.WriteAllText(Path.Combine(outDir, $"{runId}_pulse.csv"), string.Join(Environment.NewLine, pulse));
            File.WriteAllText(Path.Combine(outDir, $"{runId}_skin_impact.txt"), string.Join(Environment.NewLine, skinLog));
            var detached = crash.Detached();
            crash.Fronts(laneO, laneF, out float cabinFront, out _);
            crash.Cabin(out float3 cEnd, out _);
            float ca = math.dot(cEnd - laneO, laneF);
            double t0 = simStart;
            var connected = crash.Connected();
            double deform = crash.MaxDeformation(connected, out int deformNode);
            var intr = crash.Intrusions();
            var b = w.bodies[runner.VehicleBody];
            var brokenBy = new SortedDictionary<string, int>(StringComparer.Ordinal);
            for (int k = 0; k < b.beamCount; k++)
                if (w.broken[b.beamStart + k] != 0)
                {
                    string mat = b.def.beams[k].mat;
                    brokenBy[mat] = brokenBy.TryGetValue(mat, out int c) ? c + 1 : 1;
                }

            Put("scenario", Q(scenarioId));
            Put("what", Q(spec.what));
            Put("kind", Q(spec.kind.ToString()));
            Put("lane", Q(spec.lane));
            Put("target_kmh", F(targetKmh, "F1"));
            Put("launch", launchAtTarget ? "true" : "false");
            Put("lateral_offset_m", F(lateral, "F3"));
            Put("lane_origin", $"[{F(laneO.x)}, {F(laneO.z)}]");
            Put("lane_heading_deg", F(math.degrees(math.atan2(laneF.x, laneF.z)), "F2"));
            Put("impact_time_s", F(impactTime, "F4"));
            Put("contact_time_s", F(contactSimTime >= 0 ? contactSimTime - t0 : double.NaN, "F4"));
            Put("sim_start_s", F(simStart, "F4"));
            Put("takeoff_time_s", F(landSim >= 0 ? takeoffSim - t0 : double.NaN, "F4"));
            Put("landing_time_s", F(landSim >= 0 ? landSim - t0 : double.NaN, "F4"));
            Put("entry_speed_kmh", F(entrySpeed * 3.6, "F2"));
            Put("speed_at_impact_kmh", F(speedAtImpact * 3.6, "F2"));
            Put("peak_cabin_decel_g_4ms", F(peakCabinG, "F2"));
            Put("peak_cabin_decel_time_s", F(peakCabinGt, "F4"));
            Put("peak_cabin_decel_g_frame", F(peakFrameG, "F2"));
            Put("peak_cabin_accel_g_4ms", F(peakVecG, "F2"));
            Put("peak_lateral_g_4ms", F(peakLatG, "F2"));
            Put("peak_vertical_g_4ms", F(peakVertG, "F2"));
            Put("dynamic_crush_m", F(spec.kind == Kind.Frontal ? dynamicCrush : double.NaN, "F4"));
            Put("pulse_duration_ms", F(stopSimTime > 0 ? (stopSimTime - contactSimTime) * 1000.0 : double.NaN, "F1"));
            Put("rebound_mps", F(rebound, "F3"));
            Put("residual_crush_m", F(bodyFront0 - (BodyFront(0) - ca), "F4"));
            Put("residual_crush_left_m", F(bodyFrontL0 - (BodyFront(-1) - ca), "F4"));
            Put("residual_crush_right_m", F(bodyFrontR0 - (BodyFront(1) - ca), "F4"));
            Put("wheelbase_change_left_mm", F(WheelbaseChange("L") * 1000.0, "F1"));
            Put("wheelbase_change_right_mm", F(WheelbaseChange("R") * 1000.0, "F1"));
            Put("length_initial_m", F(initialLength, "F4"));
            Put("length_final_m", F(length, "F4"));
            Put("cabin_front_m", F(cabinFront, "F4"));
            Put("cabin_front_initial_m", F(cabinFront0, "F4"));
            Put("max_deformation_m", F(deform, "F4"));
            Put("max_deformation_node", Q(crash.NodeName(deformNode)));
            Put("max_deformation_dynamic_m", F(maxDeformDyn, "F4"));
            Put("intrusion_cm", "{" + string.Join(", ", crash.intrusionGroups.Select((g, k) => $"\"{g.name}\": {F(intr[k] * 100.0, "F1")}")) + "}");
            Put("intrusion_dynamic_cm", "{" + string.Join(", ", crash.intrusionGroups.Select((g, k) => $"\"{g.name}\": {F(intrusionDyn[k] * 100.0, "F1")}")) + "}");
            int stops = StopsReleased();
            Put("broken_beams", (m.brokenBeams - stops).ToString(Ic));
            Put("broken_beams_all", m.brokenBeams.ToString(Ic));
            Put("closure_stops_released", stops.ToString(Ic));
            Put("plastic_beams", m.plasticBeams.ToString(Ic));
            Put("plastic_hinges", m.plasticHinges.ToString(Ic));
            Put("broken_by_material", "{" + string.Join(", ", brokenBy.Select(kv => $"\"{kv.Key}\": {kv.Value}")) + "}");
            Put("detached_parts", "[" + string.Join(", ", detached.ConvertAll(Q)) + "]");
            Put("energy_J", $"{{\"kinetic\": {F(m.kinetic, "F1")}, \"elastic\": {F(m.elastic, "F1")}, \"pressure\": {F(m.pressure, "F1")}, " +
                            $"\"torsion\": {F(m.torsion, "F1")}, \"plastic\": {F(m.plastic, "F1")}, \"breaking\": {F(m.breaking, "F1")}, " +
                            $"\"damping\": {F(m.damping, "F1")}, \"contact\": {F(m.contactWork, "F1")}}}");
            Put("energy_at_contact_J", F(balanceAtContact, "F1"));
            Put("energy_created_J", F(energyCreated, "F1"));
            Put("contact_and_friction_loss_J", F(balanceAtContact - (m.Mechanical + m.Dissipated - m.driveWork - m.aeroWork + PropsEnergy()), "F1"));
            Put("drive_work_after_contact_J", F(m.driveWork - driveAtContact, "F1"));
            Put("damage", Q(CrashDiagnostics.Damage(w, runner.VehicleBody)));
            Put("closures", Q(closures.Report()));
            Put("hood_rise_m", F(closures.maxRise.TryGetValue("hood", out double hr) ? hr : 0.0, "F3"));
            Put("roof_skin_rise_m", F(closures.maxRise.TryGetValue("roof skin", out double rr) ? rr : 0.0, "F3"));
            Put("door_latch_broken", closures.latchBreak.Count > 0 ? "true" : "false");
            Put("contact_duration_s", F(spec.kind == Kind.Glancing ? contactDuration : double.NaN, "F3"));
            Put("exit_speed_kmh", F(exitSpeed * 3.6, "F2"));
            Put("exit_heading_deg", F(exitHeading, "F2"));
            Put("airborne_s", F(landSim >= 0 ? landSim - takeoffSim : double.NaN, "F3"));
            Put("takeoff_kmh", F(landSim >= 0 ? takeoffSpeed * 3.6 : double.NaN, "F2"));
            Put("landing_vertical_speed_mps", F(landSim >= 0 ? landingVy : double.NaN, "F3"));
            Put("jump_distance_m", F(landSim >= 0 ? jumpDistance : double.NaN, "F2"));
            Put("underbody_contact_nodes_max", underbodyMax.ToString(Ic));
            Put("rim_contact_nodes_max", rimMax.ToString(Ic));
            Put("props_moved", propsMoved.ToString(Ic));
            Put("props_max_displacement_m", F(propsMaxDisp, "F3"));
            Put("lowest_node_m", F(lowestNode, "F4"));
            Put("below_ground_nodes_max", belowGroundMax.ToString(Ic));
            Put("below_ground_tread_nodes_max", belowGroundTireMax.ToString(Ic));
            Put("below_ground_colliding_nodes_max", belowGroundCollMax.ToString(Ic));
            Put("lowest_node", Q(lowestNodeInfo));
            Put("lowest_colliding_node_m", F(lowestColliding, "F4"));
            Put("lowest_colliding_node", Q(lowestCollidingInfo));
            Put("tunnelled_nodes_max", maxTunnelled.ToString(Ic));
            Put("tunnelled_nodes", Q(tunnelledNames));
            Put("obstacle_primitives", targets.Length.ToString(Ic));
            Put("glass_panes_shattered", (carView ? carView.BrokenPanes : 0).ToString(Ic));
            Put("nonfinite_nodes", m.nonFinite.ToString(Ic));
            Put("max_node_speed", F(m.maxNodeSpeed, "F2"));
            Put("skin_vertices", (probe ? probe.VertexCount : 0).ToString(Ic));
            Put("skin_max_vertex_jump_mm", F(maxVertexJump * 1000.0, "F2"));
            Put("skin_max_vertex_jump_time_s", F(maxVertexJumpT, "F3"));
            Put("skin_max_vertex_jump_mesh", Q(maxVertexJumpMesh));
            Put("skin_max_spike_mm", F(maxSpike * 1000.0, "F2"));
            Put("skin_max_spike_time_s", F(maxSpikeT, "F3"));
            Put("skin_max_spike_mesh", Q(maxSpikeMesh));
            Put("skin_max_inverted_share", F(maxInverted, "F5"));
            Put("skin_stretch_m", F(maxStretch, "F4"));
            if (probe)
            {
                probe.RegionSummary(out float cs, out float ci, out float os, out float oi, out string wc, out string wo);
                Put("skin_cabin_spike_mm", F(cs * 1000.0, "F2"));
                Put("skin_cabin_inverted_share", F(ci, "F5"));
                Put("skin_other_spike_mm", F(os * 1000.0, "F2"));
                Put("skin_other_inverted_share", F(oi, "F5"));
                Put("skin_cabin_worst", Q(wc));
                Put("skin_other_worst", Q(wo));
                string cabinInv = probe.InvertedAreaSummary(out float cia, out string cim, out float cit, out float oia, out string oim, out float oit);
                Put("skin_cabin_inverted_cm2", F(cia * 1e4, "F2"));
                Put("skin_cabin_inverted_cm2_mesh", Q(cim));
                Put("skin_cabin_inverted_cm2_time_s", F(cit, "F3"));
                Put("skin_cabin_inverted_list", Q(cabinInv));
                Put("skin_other_inverted_cm2", F(oia * 1e4, "F1"));
                Put("skin_other_inverted_cm2_mesh", Q(oim));
                Put("skin_other_inverted_cm2_time_s", F(oit, "F3"));
                probe.PulseInvertedArea(out float pia, out string pim, out float pit);
                Put("skin_cabin_pulse_inverted_cm2", F(pia * 1e4, "F2"));
                Put("skin_cabin_pulse_inverted_mesh", Q(pim));
                Put("skin_cabin_pulse_inverted_time_s", F(pit, "F3"));
                Put("skin_spike_excess_mm", F(maxExcess * 1000.0, "F2"));
                Put("skin_spike_excess_time_s", F(maxExcessT, "F3"));
                Put("skin_spike_excess_mesh", Q(maxExcessMesh));
                Put("skin_max_frame_rotation_deg", F(probe.MaxFrameRotationDeg, "F1"));
                Put("skin_max_frame_rotation_node", Q(probe.MaxFrameRotationNode));
                Put("skin_max_frame_rotation_time_s", F(maxRotT, "F3"));
            }
            Put("skin_at_max_jump", Q(jumpReport));
            Put("skin_at_end", Q(endReport));
            Put("capture_start_s", F(captureStart, "F4"));
            Put("capture_fps", fps.ToString(Ic));
            Put("frames_captured", frameIndex.ToString(Ic));
            Put("cameras", "[" + string.Join(", ", (cameras ?? Array.Empty<Camera>()).Where(c => c).Select(c => Q(c.name))) + "]");
            Put("sim_steps", w.StepsTaken.ToString(Ic));
            Put("scenario_substeps", steps.ToString(Ic));
            Put("physics_us_per_substep", F(stepMs * 1000.0 / math.max(steps, 1), "F2"));
            Put("solver", Q(w.UsesSingleThread ? "single-thread" : "parallel"));
            Put("stability_maxS", F(runner.Stability.maxS));
            Put("data_hash", Q(runner.DataHash.ToString("x16")));

            // the run's recording: the start snapshot and every frame's substeps and input
            recPath = Path.Combine(outDir, $"{runId}.hrec");
            rec.Write(recPath);
            rec.WriteCsv(Path.ChangeExtension(recPath, ".csv"));
            runHash = WorldState.Hash(w);
            runSteps = w.StepsTaken;
            Put("recording", Q(Path.GetFileName(recPath)));
            Put("recording_frames", rec.frames.Count.ToString(Ic));
            Put("recording_s", F(rec.Duration, "F3"));
            Put("recording_bytes", new FileInfo(recPath).Length.ToString(Ic));
            Put("run_state_hash", Q(runHash.ToString("x16")));
            WriteResult();
            Debug.Log($"[CarCrash] done: {runId} entry {entrySpeed * 3.6f:F1} km/h, broken {m.brokenBeams - stops} (+{stops} stops released), plastic {m.plastic / 1000:F1} kJ, " +
                      $"crush {dynamicCrush:F3}/{bodyFront0 - (BodyFront(0) - ca):F3} m, deformation {deform:F3} m, detached {string.Join("+", detached)}");
            StartCoroutine(AfterRun());
        }

        // ------------------------------------------------------------------ replay: determinism and the slow-motion variant

        /// <summary>Replays the run's recording from its snapshot (inputs looked up per substep): fast up to the slow-motion
        /// window, there 8 substeps per frame (250 fps) captured from the tracking, side and three-quarter cameras, then
        /// fast to the end; the end state must equal the run's bit for bit (<see cref="WorldState.Hash"/>).</summary>
        IEnumerator AfterRun()
        {
            yield return null;   // the final stills
            if (replayCheck)
            {
                var w = runner.World;
                replayRec = InputRecording.Read(recPath);   // the saved file, not the run's own copy
                runner.RestoreState(replayRec.state);
                replayStart = w.StepsTaken;
                replaying = true;
                long end = replayStart + replayRec.TotalSubsteps;
                double t0 = runner.SimTime;
                double ev = spec.kind == Kind.Jump && landSim >= 0 ? landSim : contactSimTime;
                bool slow = capture && slowMotion && ev >= 0;
                double from = ev - spec.slowBefore, to = ev + spec.slowAfter;
                int per = (int)math.round(1.0 / (slowFps * w.dt));
                var slowCams = (cameras ?? Array.Empty<Camera>()).Where(c => c && (c.name == "chase" || c.name == "side" || c.name == "front34")).ToArray();
                bool entered = false;
                string dir = Path.Combine(outDir, "frames_slowmo");
                if (slow && Directory.Exists(dir))
                    Directory.Delete(dir, true);
                while (w.StepsTaken < end)
                {
                    if (slow && runner.SimTime >= from - 1e-9 && runner.SimTime < to)
                    {
                        if (!entered)
                        {
                            entered = true;
                            Time.captureFramerate = slowFps;
                            chase?.Snap();
                        }
                        runner.StepNow((int)math.min(per, end - w.StepsTaken));
                        foreach (var cam in slowCams)
                            pending.Add((cam, Path.Combine(dir, $"{cam.name}_{slowFrames:D4}.jpg"), captureWidth, captureHeight, true));
                        slowFrames++;
                    }
                    else
                    {
                        long left = end - w.StepsTaken;
                        if (slow && runner.SimTime < from - 1e-9)
                            left = math.min(left, math.max(1L, (long)math.round((from - runner.SimTime) / w.dt)));
                        left = math.min(left, 2000L);
                        while (left > 0)
                        {
                            int k = (int)math.min(left, 66L);
                            runner.StepNow(k);
                            left -= k;
                        }
                    }
                    yield return null;
                }
                replaying = false;
                replayHash = WorldState.Hash(w);
                replayIdentical = replayHash == runHash && w.StepsTaken == runSteps;
                replayNote = replayIdentical
                    ? $"replay of {rec.frames.Count} frames ({rec.Duration:F2} s) from the snapshot: end state identical"
                    : $"replay differs: hash {replayHash:x16} vs {runHash:x16}, steps {w.StepsTaken} vs {runSteps}";
                Debug.Log("[CarCrash] " + replayNote + (slow ? $"; slow motion {slowFrames} frames at {slowFps} fps" : "") + $" (sim {runner.SimTime - t0:F2} s)");
                Put("replay_identical", replayIdentical ? "true" : "false");
                Put("replay_state_hash", Q(replayHash.ToString("x16")));
                Put("replay_note", Q(replayNote));
                Put("slowmo_fps", slow ? slowFps.ToString(Ic) : "null");
                Put("slowmo_frames", slowFrames.ToString(Ic));
                Put("slowmo_window_s", slow ? $"[{F(from - t0, "F3")}, {F(to - t0, "F3")}]" : "null");
                Put("slowmo_cameras", "[" + string.Join(", ", slowCams.Select(c => Q(c.name))) + "]");
                WriteResult();
            }
            quitAfterCapture = true;   // after the last captures (end of this frame)
        }
    }
}
