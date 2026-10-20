using System;
using Hellcat.Game.Core;
using Hellcat.Sim;
using Hellcat.Sim.Validation;
using Hellcat.Sim.Vehicle;
using Unity.Mathematics;
using UnityEngine;

namespace Hellcat.Game.Input
{
    /// <summary>
    /// "Teleport to obstacle N at speed V" (brief 4.12, D-080): after the teleport the car is held at V on the spawn's lane
    /// by the driver robot (speed PI, pure pursuit on the straight line) and let go - pedals released, wheel straight - once
    /// its nearest node is within <see cref="releaseDistance"/> of an obstacle, the way a crash-test tow cable lets the car
    /// go just before the barrier, so it meets the obstacle at V. Obstacles are static solids taller than 0.3 m ahead of the
    /// car (not the grass slabs, curbs or bumps it drives over); a lane can hold through them (ramps, ledges). The hold also
    /// ends when the driver touches a pedal, the steering or the handbrake, or after the run-up time.
    /// </summary>
    [DefaultExecutionOrder(-250)]
    public class ApproachHoldSource : MonoBehaviour, IDriverInputSource
    {
        public SimRunner runner;
        public LiveDriverInput live;
        public int priority = 40;   // above the live driver, below the drive-test robot and the replay
        [Tooltip("Release the pedals this far (m) from the obstacle")]
        public float releaseDistance = 1.0f;

        public bool Holding { get; private set; }
        public float TargetSpeed { get; private set; }
        public string ReleaseReason { get; private set; } = "";
        public float ReleaseSpeed { get; private set; }

        public int Priority => priority;
        public bool Active => (Holding || coasting) && enabled;

        DriverRobot robot;
        CarProbe probe;
        bool releaseNear = true;
        const float ObstacleHeight = 0.3f;
        DriverInput current = DriverInput.Idle;
        double t0, lastT, deadline;
        bool coasting;   // released near the obstacle: idle input until the driver takes over

        void Start()
        {
            if (runner == null || runner.World == null)
                return;
            probe = new CarProbe(runner.World, runner.VehicleBody);
            runner.RegisterInput(this);
            runner.Rebuilt += OnRebuilt;
        }

        void OnRebuilt()
        {
            Stop("world rebuilt");
            probe = new CarProbe(runner.World, runner.VehicleBody);
        }

        void OnDestroy()
        {
            if (!runner) return;
            runner.UnregisterInput(this);
            runner.Rebuilt -= OnRebuilt;
        }

        /// <summary>Holds <paramref name="speed"/> (m/s) along the line through <paramref name="origin"/> in direction
        /// <paramref name="dir"/> (ground plane) for at most <paramref name="length"/> m.</summary>
        public void Begin(Vector3 origin, Vector3 dir, float speed, float length, bool releaseNearObstacles = true)
        {
            releaseNear = releaseNearObstacles;
            var d = new double2(dir.x, dir.z);
            d = math.normalizesafe(d, new double2(0, 1));
            robot = new DriverRobot(runner.VehicleParams)
            {
                path = PolyPath.Line(new double2(origin.x, origin.z), d, length + 40.0),
                targetSpeed = (t, arc) => speed,
                flags = DriverInput.FlagAbs | DriverInput.FlagTc,
            };
            TargetSpeed = speed;
            t0 = lastT = runner.SimTime;
            deadline = runner.SimTime + length / math.max(speed, 1f) + 3.0;
            Holding = true;
            coasting = false;
            ReleaseReason = "";
        }

        public void Stop(string why)
        {
            if (Holding || coasting)
                ReleaseReason = why;
            Holding = false;
            coasting = false;
            current = DriverInput.Idle;
        }

        void Update()
        {
            if (!Holding && !coasting)
                return;
            if (live != null && live.Touched)
            {
                Stop("driver took over");
                return;
            }
            if (coasting)
                return;
            var f = probe.Frame();
            if (runner.SimTime > deadline)
            {
                Release("run-up time over", f);
                return;
            }
            var w = runner.World;
            var b = w.bodies[runner.VehicleBody];
            if (releaseNear && ObstacleAhead(w, b, f) < releaseDistance)
            {
                Release($"released {releaseDistance:F1} m before the obstacle", f);
                return;
            }
            double t = runner.SimTime - t0;
            double dt = Math.Max(runner.SimTime - lastT, 1e-4);
            lastT = runner.SimTime;
            current = robot.Control(t, dt, f);
        }

        void Release(string why, in CarFrame f)
        {
            Holding = false;
            coasting = true;
            ReleaseReason = why;
            ReleaseSpeed = (float)f.speed;
            current = DriverInput.Idle;
        }

        /// <summary>Nearest distance of the car's front-half nodes to a static solid ahead of it that stands taller than
        /// 0.3 m (planes, ground slabs, curbs and bumps are driven over).</summary>
        static float ObstacleAhead(SoftBodyWorld w, SoftBodyWorld.Body b, in CarFrame f)
        {
            float best = float.MaxValue;
            float3 c = (float3)f.com, fwd = (float3)f.forward;
            for (int p = 0; p < w.prims.Length; p++)
            {
                var prim = w.prims[p];
                if (prim.type == PrimType.Plane || prim.aabbMax.y < ObstacleHeight)
                    continue;
                float3 nearest = math.clamp(c, prim.aabbMin, prim.aabbMax);
                if (math.dot(nearest - c, fwd) <= 0f || math.distance(nearest, c) > 15f)
                    continue;
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                    if (math.dot(w.pos[i] - c, fwd) > 0f)
                        best = math.min(best, StaticSdf.Distance(prim, w.planes, w.pos[i], out _));
            }
            return best;
        }

        public DriverInput Sample(long substepIndex, in VehicleState state) => current;
    }
}
