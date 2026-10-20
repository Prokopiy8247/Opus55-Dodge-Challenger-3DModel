using System;
using System.Collections.Generic;
using System.IO;
using Hellcat.Game.World;
using Hellcat.Sim;
using Hellcat.Sim.Data;
using Hellcat.Sim.Vehicle;
using Unity.Mathematics;
using UnityEngine;

namespace Hellcat.Game.Core
{
    /// <summary>Supplies the driver controls for the substeps of one frame (live input, scripts, replay).</summary>
    public interface IDriverInputSource
    {
        /// <summary>Higher priority wins when several sources are enabled.</summary>
        int Priority { get; }
        bool Active { get; }
        DriverInput Sample(long substepIndex, in VehicleState state);
    }

    /// <summary>
    /// Owns the soft-body world: loads the vehicle (StreamingAssets/Vehicles/name), collects the static
    /// geometry of the scene, and advances the simulation with a fixed step accumulated against the
    /// frame time (cap per frame; a slow-down flag is raised when the cap is hit).
    /// </summary>
    [DefaultExecutionOrder(-100)]
    public class SimRunner : MonoBehaviour
    {
        public string vehicleName = "boxcar";
        public Transform spawnPoint;
        public float spawnSpeed;
        [Tooltip("Max substeps per frame (2000 Hz x 1/60 s = 33)")]
        public int maxSubstepsPerFrame = 66;
        public float timeScale = 1f;
        public bool paused;
        public bool forceSingleThread;
        [Tooltip("Spawn the car this far above the statics and relax it to static equilibrium first (D-037); NaN: as placed")]
        public float spawnClearance = float.NaN;
        public bool settleOnSpawn;
        [Tooltip("Energy ledger of the contacts and dampers (crash metrics; a few % of the step time)")]
        public bool trackEnergy;

        public SoftBodyWorld World { get; private set; }
        public int VehicleBody { get; private set; }
        public int VehicleIndex => World.bodies[VehicleBody].vehicleIndex;
        public VehicleDef VehicleDefinition { get; private set; }
        public SimParamsDef VehicleParams { get; private set; }
        public StabilityReport Stability { get; private set; }
        public bool SlowDown { get; private set; }
        public int LastSubsteps { get; private set; }
        public float LastStepMs { get; private set; }
        public float PhysicsHz { get; private set; }      // substeps per real second (smoothed)
        public float RealTimeFactor { get; private set; } // simulated seconds per real second
        public double SimTime => World.StepsTaken * World.dt;
        /// <summary>FNV-1a of geometry.json + params.json: recordings name the vehicle data they were made with.</summary>
        public ulong DataHash { get; private set; }
        /// <summary>The active input source gave different inputs within the last frame (a replay of a recording made
        /// from such a source is not exact: recordings keep one input per frame).</summary>
        public bool InputVariedInFrame { get; private set; }
        public event Action<int> Stepped;                 // substeps done this frame
        /// <summary>Raised after the car was respawned (reset, repair, teleport, replay start): views reset their state.</summary>
        public event Action Respawned;
        /// <summary>When set, each frame steps exactly this many substeps (replay: the recorded frame partition, so the run
        /// is bit-identical); a negative value ends the override.</summary>
        public Func<int> SubstepOverride;
        /// <summary>Paused: substeps to advance on the next frames (P4b step key), then hold.</summary>
        public int PendingSteps;

        readonly List<IDriverInputSource> inputSources = new List<IDriverInputSource>();
        double accumulator;
        float hzWindowTime;
        int hzWindowSteps;
        double hzWindowSim;
        DriverInput lastInput = DriverInput.Idle;

        public static string VehicleFolder(string vehicle) =>
            Path.Combine(Application.streamingAssetsPath, "Vehicles", vehicle);

        void Awake()
        {
            // English logs and files: '.' decimals whatever the OS locale
            System.Globalization.CultureInfo.CurrentCulture = System.Globalization.CultureInfo.InvariantCulture;
            System.Globalization.CultureInfo.DefaultThreadCurrentCulture = System.Globalization.CultureInfo.InvariantCulture;
            Vector3 p = spawnPoint ? spawnPoint.position : Vector3.zero;
            Quaternion r = spawnPoint ? spawnPoint.rotation : Quaternion.identity;
            CreateWorld(p, r, spawnSpeed, settleOnSpawn);
        }

        /// <summary>Loads geometry.json and params.json, collects the scene's static geometry and builds the world with the
        /// car at the pose (settled and launched when asked).</summary>
        void CreateWorld(Vector3 p, Quaternion r, float speed, bool settle)
        {
            string folder = VehicleFolder(vehicleName);
            // -vehicleParams <file>: another parameter set for the same geometry (P6 sensitivity sweep)
            string paramsPath = CommandLine("-vehicleParams") ?? Path.Combine(folder, "params.json");
            VehicleDefinition = VehicleDef.Load(Path.Combine(folder, "geometry.json"));
            VehicleParams = SimParamsDef.Load(paramsPath);
            DataHash = InputRecording.HashFiles(Path.Combine(folder, "geometry.json"), paramsPath);

            World = new SoftBodyWorld(VehicleParams) { forceSingleThread = forceSingleThread, trackEnergy = trackEnergy };
            var statics = new StaticWorldBuilder();
            var sources = new List<(string key, IStaticGeometrySource src)>();
            foreach (var mb in FindObjectsByType<MonoBehaviour>(FindObjectsInactive.Exclude))
                // isActiveAndEnabled is still false before OnEnable has run (this Awake runs first).
                if (mb is IStaticGeometrySource src && mb.enabled && mb.gameObject.activeInHierarchy)
                    sources.Add((HierarchyPath(mb.transform) + "|" + mb.GetType().Name, src));
            // Deterministic primitive order (contact forces are summed in this order).
            sources.Sort((a, b) => string.CompareOrdinal(a.key, b.key));
            foreach (var (_, src) in sources)
                src.AddTo(statics);
            if (statics.prims.Count == 0)
                statics.AddPlane(new float3(0f, 1f, 0f), 0f, VehicleParams.surfaces.Length > 0 ? VehicleParams.surfaces[0].name : "default");

            float3 v = (float3)(r * Vector3.forward) * speed;
            VehicleBody = World.AddBody(vehicleName, VehicleDefinition, VehicleParams, p, r, v, true);
            World.bodies[VehicleBody].spawnClearance = spawnClearance;
            // debris and props after the car, in a fixed order (D-081)
            var dynamic = new List<(string key, IDynamicBodySource src)>();
            foreach (var mb in FindObjectsByType<MonoBehaviour>(FindObjectsInactive.Exclude))
                if (mb is IDynamicBodySource d && mb.enabled && mb.gameObject.activeInHierarchy)
                    dynamic.Add((HierarchyPath(mb.transform) + "|" + mb.GetType().Name, d));
            dynamic.Sort((a, b) => string.CompareOrdinal(a.key, b.key));
            foreach (var (_, d) in dynamic)
                d.AddBodies(World);
            World.Build(statics);
            if (settle)
            {
                // settled spawn (D-037): tires squashed, springs at their static length, brakes holding
                World.SetInput(World.bodies[VehicleBody].vehicleIndex, new DriverInput { brake = 1f, handbrake = 1f, gear = 0 });
                World.Settle(VehicleBody);
                if (speed != 0f)
                    World.Launch(VehicleBody, v);
                World.SetInput(World.bodies[VehicleBody].vehicleIndex, DriverInput.Idle);
            }
            Stability = StabilityReport.Compute(World);
            Debug.Log($"[SimRunner] {vehicleName}: {World.NodeCount} nodes, {World.BeamCount} beams, " +
                      $"{statics.prims.Count} static primitives, {(World.UsesSingleThread ? "single-thread" : "parallel")} solver, dt={World.dt * 1000f:F2} ms\n" +
                      Stability.Summary(i => i < VehicleDefinition.nodes.Length ? VehicleDefinition.nodes[i].name : i.ToString()));
        }

        /// <summary>Raised after <see cref="ReloadVehicleData"/> replaced the world: holders of world references renew them.</summary>
        public event Action Rebuilt;

        /// <summary>F9 (brief 4.12 bonus): re-reads geometry.json and params.json from StreamingAssets/Vehicles/name and
        /// rebuilds the world without restarting; the car is respawned fresh and settled at the given pose. The node and
        /// beam layout must stay the same (the views keep their buffers): parameters only.</summary>
        public void ReloadVehicleData(Vector3 position, Quaternion rotation)
        {
            int nodes = World.NodeCount, beams = World.BeamCount;
            World.Dispose();
            if (float.IsNaN(spawnClearance))
                spawnClearance = 0.01f;
            CreateWorld(position, rotation, 0f, true);
            if (World.NodeCount != nodes || World.BeamCount != beams)
                Debug.LogError($"[SimRunner] reloaded vehicle has {World.NodeCount} nodes / {World.BeamCount} beams, was {nodes} / {beams}: restart the game");
            lastInput = DriverInput.Idle;
            accumulator = 0.0;
            Rebuilt?.Invoke();
            Respawned?.Invoke();
        }

        /// <summary>The value after <paramref name="name"/> on the command line, or null.</summary>
        public static string CommandLine(string name)
        {
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
                if (string.Equals(args[i], name, StringComparison.OrdinalIgnoreCase))
                    return args[i + 1];
            return null;
        }

        static string HierarchyPath(Transform t)
        {
            string path = t.name;
            for (var p = t.parent; p != null; p = p.parent)
                path = p.name + "/" + path;
            return path + "#" + t.GetSiblingIndex();
        }

        public void RegisterInput(IDriverInputSource source)
        {
            if (!inputSources.Contains(source))
                inputSources.Add(source);
        }

        public void UnregisterInput(IDriverInputSource source) => inputSources.Remove(source);

        IDriverInputSource ActiveSource()
        {
            IDriverInputSource best = null;
            foreach (var s in inputSources)
                if (s.Active && (best == null || s.Priority > best.Priority))
                    best = s;
            return best;
        }

        float quitAfter = -1f;

        void Start()
        {
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
                if (args[i] == "-quitAfter")
                    quitAfter = float.Parse(args[i + 1], System.Globalization.CultureInfo.InvariantCulture);
        }

        void Update()
        {
            if (World == null || !World.IsBuilt)
                return;
            if (quitAfter > 0f && Time.realtimeSinceStartup > quitAfter)
            {
                Debug.Log($"[SimRunner] quitAfter reached: physics {PhysicsHz:F0} Hz x{RealTimeFactor:F2}, last step {LastStepMs:F3} ms / {LastSubsteps} substeps");
                Application.Quit(0);
            }
            int n;
            int forced = SubstepOverride != null && !paused ? SubstepOverride() : -1;
            SlowDown = false;
            if (forced >= 0)
            {
                n = forced;
                accumulator = 0.0;
            }
            else if (paused)
            {
                n = math.min(PendingSteps, World.maxSubsteps);
                PendingSteps -= n;
                accumulator = 0.0;
            }
            else
            {
                float frameDt = Time.deltaTime * timeScale;
                accumulator += frameDt;
                n = (int)math.floor(accumulator / World.dt);
                if (n > maxSubstepsPerFrame)
                {
                    n = maxSubstepsPerFrame;
                    accumulator = 0.0;
                    SlowDown = true;
                }
                else
                {
                    accumulator -= n * World.dt;
                }
            }
            n = math.min(n, World.maxSubsteps);
            LastSubsteps = n;
            if (n > 0)
                StepNow(n);

            hzWindowTime += Time.unscaledDeltaTime;
            hzWindowSteps += n;
            hzWindowSim += n * World.dt;
            if (hzWindowTime >= 0.5f)
            {
                PhysicsHz = hzWindowSteps / hzWindowTime;
                RealTimeFactor = (float)(hzWindowSim / hzWindowTime);
                hzWindowTime = 0f;
                hzWindowSteps = 0;
                hzWindowSim = 0.0;
            }
        }

        /// <summary>Advances exactly <paramref name="n"/> substeps with inputs from the active source.</summary>
        public void StepNow(int n)
        {
            var src = ActiveSource();
            int vi = VehicleIndex;
            long first = World.StepsTaken;
            var state = World.vehicleState[vi];
            InputVariedInFrame = false;
            for (int s = 0; s < n; s++)
            {
                var inp = src != null ? src.Sample(first + s, state) : lastInput;
                World.SetInput(vi, s, inp);
                if (s > 0 && !Same(inp, lastInput))
                    InputVariedInFrame = true;
                lastInput = inp;
            }
            World.UpdateNearLists(n * World.dt + 0.05f);
            var sw = System.Diagnostics.Stopwatch.StartNew();
            World.Step(n);
            LastStepMs = (float)sw.Elapsed.TotalMilliseconds;
            Stepped?.Invoke(n);
        }

        public DriverInput LastInput => lastInput;

        static bool Same(in DriverInput a, in DriverInput b) =>
            a.throttle == b.throttle && a.brake == b.brake && a.handbrake == b.handbrake && a.steer == b.steer && a.gear == b.gear && a.flags == b.flags;

        /// <summary>Puts the world back into a captured state (replay start); views reset as after a respawn.</summary>
        public void RestoreState(WorldState state)
        {
            state.Restore(World);
            lastInput = World.inputs[VehicleIndex * World.maxSubsteps];
            accumulator = 0.0;
            Respawned?.Invoke();
        }

        public void ResetVehicle() => World.ResetBody(VehicleBody);

        public void Respawn(Vector3 position, Quaternion rotation, float speed)
        {
            World.Respawn(VehicleBody, position, rotation, (float3)(rotation * Vector3.forward) * speed);
        }

        /// <summary>Puts a fresh (undamaged) car at the pose: placed just above the statics, relaxed to static equilibrium
        /// with the brakes on (D-037), then launched at <paramref name="speed"/> along its heading. Deterministic: the same
        /// pose and speed give the same state (record / replay start from here).</summary>
        public void RespawnSettled(Vector3 position, Quaternion rotation, float speed)
        {
            var b = World.bodies[VehicleBody];
            if (float.IsNaN(b.spawnClearance))
                b.spawnClearance = 0.01f;
            World.Respawn(VehicleBody, position, rotation, float3.zero);
            World.SetInput(VehicleIndex, new DriverInput { brake = 1f, handbrake = 1f, gear = 0 });
            World.Settle(VehicleBody);
            if (speed != 0f)
                World.Launch(VehicleBody, (float3)(rotation * Vector3.forward) * speed);
            World.SetInput(VehicleIndex, DriverInput.Idle);
            lastInput = DriverInput.Idle;
            accumulator = 0.0;
            Respawned?.Invoke();
        }

        void OnDestroy()
        {
            World?.Dispose();
            World = null;
        }
    }
}
