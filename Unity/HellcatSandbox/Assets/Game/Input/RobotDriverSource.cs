using System;
using Hellcat.Game.Core;
using Hellcat.Sim.Validation;
using Hellcat.Sim.Vehicle;
using UnityEngine;

namespace Hellcat.Game.Input
{
    /// <summary>
    /// The validation driver robot (<see cref="DriverRobot"/>: PI speed control, pure-pursuit path following) as an input
    /// source of the game, for the automated drive test (gate G-Drive) and scripted captures. Computes one input per frame
    /// from the cabin frame, before the runner steps (so a recording of it replays exactly).
    /// </summary>
    [DefaultExecutionOrder(-250)]
    public class RobotDriverSource : MonoBehaviour, IDriverInputSource
    {
        public SimRunner runner;
        public int priority = 50;

        public DriverRobot Robot { get; private set; }
        public CarProbe Probe { get; private set; }
        public CarFrame Frame { get; private set; }
        public bool Driving { get; private set; }

        public int Priority => priority;
        public bool Active => Driving && enabled;

        DriverInput current = DriverInput.Idle;
        double t0, lastT;

        void Start()
        {
            if (runner == null || runner.World == null)
                return;
            Probe = new CarProbe(runner.World, runner.VehicleBody);
            Frame = Probe.Frame();
            runner.RegisterInput(this);
            runner.Rebuilt += OnRebuilt;
        }

        void OnRebuilt()
        {
            End();
            Probe = new CarProbe(runner.World, runner.VehicleBody);
        }

        void OnDestroy()
        {
            if (!runner) return;
            runner.UnregisterInput(this);
            runner.Rebuilt -= OnRebuilt;
        }

        public void Begin(PolyPath path, Func<double, double, double> targetSpeed, int flags = DriverInput.FlagAbs | DriverInput.FlagTc)
        {
            Robot = new DriverRobot(runner.VehicleParams) { path = path, targetSpeed = targetSpeed, flags = flags };
            t0 = lastT = runner.SimTime;
            Driving = true;
        }

        public void End()
        {
            Driving = false;
            current = DriverInput.Idle;
        }

        void Update()
        {
            if (!Driving || Probe == null)
                return;
            Frame = Probe.Frame();
            double t = runner.SimTime - t0;
            double dt = Math.Max(runner.SimTime - lastT, 1e-4);
            lastT = runner.SimTime;
            current = Robot.Control(t, dt, Frame);
        }

        public DriverInput Sample(long substepIndex, in VehicleState state) => current;
    }
}
