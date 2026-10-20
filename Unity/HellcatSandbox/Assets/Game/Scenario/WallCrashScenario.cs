using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using Hellcat.Game.Capture;
using Hellcat.Game.Core;
using Hellcat.Sim;
using Hellcat.Sim.Vehicle;
using Unity.Mathematics;
using UnityEngine;

namespace Hellcat.Game.Scenario
{
    /// <summary>
    /// Scripted straight-line crash (vertical slice, later S1/S8): settle, accelerate to the target
    /// speed with a P controller while holding the lane, hit the wall, record metrics, capture frames
    /// from two cameras, then quit. Started from the command line:
    ///   -scenario wall -targetKmh 50 -out &lt;dir&gt; [-capture 1] [-captureWidth 1280 -captureHeight 720]
    /// </summary>
    public class WallCrashScenario : MonoBehaviour, IDriverInputSource
    {
        public SimRunner runner;
        public Camera chaseCamera, sideCamera;
        public Transform wall;
        public float targetKmh = 50f;
        public float settleTime = 1.0f;
        public float postImpactTime = 3.0f;
        public float maxTime = 40f;
        public bool runFromCommandLineOnly = true;
        public string outDir = "";
        public bool capture = true;
        public int captureWidth = 1280, captureHeight = 720;
        public float captureLeadTime = 1.2f; // seconds before impact to start the video frames

        public int Priority => 10;
        public bool Active => running;

        bool running;
        float time;
        float impactTime = -1f;
        float3 lastComVel;
        bool haveLast;
        float peakDecelG;
        float speedAtImpact;
        float prevSpeed;
        double stepMsTotal;
        float stepMsMax;
        long substepsTotal;
        float initialLength;
        int frameIndex;
        readonly List<string> rows = new List<string>();
        DriverInput current = DriverInput.Idle;
        float laneX;
        string runId;

        void Start()
        {
            var args = Environment.GetCommandLineArgs();
            string scenario = Arg(args, "-scenario", null);
            if (runFromCommandLineOnly && scenario != "wall")
            {
                enabled = false;
                return;
            }
            targetKmh = float.Parse(Arg(args, "-targetKmh", targetKmh.ToString(CultureInfo.InvariantCulture)), CultureInfo.InvariantCulture);
            outDir = Arg(args, "-out", string.IsNullOrEmpty(outDir) ? Path.Combine(Application.persistentDataPath, "scenario") : outDir);
            capture = Arg(args, "-capture", capture ? "1" : "0") == "1";
            captureWidth = int.Parse(Arg(args, "-captureWidth", captureWidth.ToString()));
            captureHeight = int.Parse(Arg(args, "-captureHeight", captureHeight.ToString()));
            runId = $"wall_{targetKmh:F0}kmh";
            Directory.CreateDirectory(outDir);
            Time.captureFramerate = 60; // fixed 1/60 s frames: deterministic sim time per frame
            runner.RegisterInput(this);
            laneX = runner.spawnPoint ? runner.spawnPoint.position.x : 0f;
            initialLength = VehicleLength();
            rows.Add("t,speed_kmh,com_x,com_y,com_z,decel_g,length_m,broken,plastic_beams,kinetic_J,elastic_J,plastic_J,breaking_J,throttle,brake,steer,wheel_speed_driven_kmh,load_driven_N");
            running = true;
            Debug.Log($"[WallCrash] start target={targetKmh} km/h out={outDir}");
        }

        static string Arg(string[] args, string name, string fallback)
        {
            for (int i = 0; i < args.Length - 1; i++)
                if (string.Equals(args[i], name, StringComparison.OrdinalIgnoreCase))
                    return args[i + 1];
            return fallback;
        }

        float VehicleLength()
        {
            var w = runner.World;
            var b = w.bodies[runner.VehicleBody];
            float3 fwd = w.vehicleState[runner.VehicleIndex].forward;
            float lo = float.MaxValue, hi = float.MinValue;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
            {
                if ((w.nodeFlags[i] & NodeFlag.Tire) != 0)
                    continue;
                float d = math.dot(w.pos[i], fwd);
                lo = math.min(lo, d);
                hi = math.max(hi, d);
            }
            return hi - lo;
        }

        public DriverInput Sample(long substepIndex, in VehicleState state) => current;

        void Update()
        {
            if (!running)
                return;
            var w = runner.World;
            var st = w.vehicleState[runner.VehicleIndex];
            var m = w.Metrics(runner.VehicleBody);
            float dtFrame = Time.deltaTime;
            time += dtFrame;
            stepMsTotal += runner.LastStepMs;
            stepMsMax = math.max(stepMsMax, runner.LastStepMs);
            substepsTotal += runner.LastSubsteps;

            // Controller: hold the lane (x = laneX) and the target speed until impact.
            float targetSpeed = targetKmh / 3.6f;
            float3 fwd = math.normalizesafe(st.forward);
            float headingErr = math.atan2(fwd.x, fwd.z);
            float lateral = m.centerOfMass.x - laneX;
            float steer = math.clamp(-2.5f * lateral - 4f * headingErr, -1f, 1f);
            if (time < settleTime)
                current = new DriverInput { brake = 1f, gear = DriverInput.Drive };
            else if (impactTime < 0f)
                current = new DriverInput { throttle = math.saturate((targetSpeed - st.speed) * 0.8f + 0.1f), steer = steer, gear = DriverInput.Drive };
            else
                current = new DriverInput { brake = 0.2f, gear = DriverInput.Drive };

            // Deceleration of the centre of mass (per frame, from the momentum-weighted velocity).
            float decelG = 0f;
            if (haveLast && dtFrame > 0f)
                decelG = -math.dot(m.velocity - lastComVel, fwd) / dtFrame / 9.81f;
            lastComVel = m.velocity;
            haveLast = true;

            float frontDist = WallDistance();
            if (impactTime < 0f && time > settleTime && (frontDist < 0.03f || decelG > 3f))
            {
                impactTime = time;
                speedAtImpact = prevSpeed; // speed in the last frame before contact
                Debug.Log($"[WallCrash] impact at t={time:F3}s entry speed={prevSpeed * 3.6f:F1} km/h");
            }
            prevSpeed = st.speed;
            if (impactTime >= 0f)
                peakDecelG = math.max(peakDecelG, decelG);

            float length = VehicleLength();
            var ic = CultureInfo.InvariantCulture;
            float wheelSpeed = 0f, drivenLoad = 0f;
            int driven = 0;
            var vs = w.vehicles[runner.VehicleIndex];
            for (int k = 0; k < vs.wheelCount; k++)
            {
                var ws = w.wheels[vs.wheelStart + k];
                if (ws.driven == 0)
                    continue;
                var wst = w.wheelState[vs.wheelStart + k];
                wheelSpeed += wst.omega * ws.radius;
                drivenLoad += wst.load;
                driven++;
            }
            if (driven > 0)
                wheelSpeed /= driven;
            rows.Add(string.Join(",", new[]
            {
                time.ToString("F4", ic), (st.speed * 3.6f).ToString("F3", ic),
                m.centerOfMass.x.ToString("F4", ic), m.centerOfMass.y.ToString("F4", ic), m.centerOfMass.z.ToString("F4", ic),
                decelG.ToString("F3", ic), length.ToString("F4", ic), m.brokenBeams.ToString(), m.plasticBeams.ToString(),
                m.kinetic.ToString("F1", ic), m.elastic.ToString("F1", ic), m.plastic.ToString("F1", ic), m.breaking.ToString("F1", ic),
                current.throttle.ToString("F3", ic), current.brake.ToString("F3", ic), current.steer.ToString("F3", ic),
                (wheelSpeed * 3.6f).ToString("F3", ic), drivenLoad.ToString("F1", ic),
            }));

            bool inWindow = capture && (impactTime >= 0f || frontDist < targetSpeed * captureLeadTime);
            if (inWindow)
            {
                string frames = Path.Combine(outDir, "frames");
                FrameCapture.Save(chaseCamera, Path.Combine(frames, $"chase_{frameIndex:D4}.jpg"), captureWidth, captureHeight, true);
                if (sideCamera)
                    FrameCapture.Save(sideCamera, Path.Combine(frames, $"side_{frameIndex:D4}.jpg"), captureWidth, captureHeight, true);
                frameIndex++;
            }
            if (capture && impactTime >= 0f && Mathf.Abs(time - impactTime - 0.0f) < dtFrame * 0.5f)
                SaveStill("at_impact");

            if ((impactTime >= 0f && time > impactTime + postImpactTime) || time > maxTime)
                Finish(m, length);
        }

        float WallDistance()
        {
            if (wall == null)
                return float.MaxValue;
            var w = runner.World;
            var b = w.bodies[runner.VehicleBody];
            float wallFace = wall.position.z - 0.5f * wall.lossyScale.z;
            float maxZ = float.MinValue;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                maxZ = math.max(maxZ, w.pos[i].z);
            return wallFace - maxZ;
        }

        void SaveStill(string tag)
        {
            FrameCapture.Save(chaseCamera, Path.Combine(outDir, $"{runId}_{tag}_chase.png"), 1920, 1080);
            if (sideCamera)
                FrameCapture.Save(sideCamera, Path.Combine(outDir, $"{runId}_{tag}_side.png"), 1920, 1080);
        }

        void Finish(SoftBodyWorld.BodyMetrics m, float length)
        {
            running = false;
            if (capture)
                SaveStill("final");
            File.WriteAllText(Path.Combine(outDir, $"{runId}_timeseries.csv"), string.Join("\n", rows));
            var ic = CultureInfo.InvariantCulture;
            var sb = new StringBuilder();
            sb.Append("{\n");
            sb.Append($"  \"scenario\": \"wall\",\n  \"target_kmh\": {targetKmh.ToString(ic)},\n");
            sb.Append($"  \"impact_time_s\": {impactTime.ToString("F4", ic)},\n  \"speed_at_impact_kmh\": {(speedAtImpact * 3.6f).ToString("F2", ic)},\n");
            sb.Append($"  \"peak_decel_g_frame_avg\": {peakDecelG.ToString("F2", ic)},\n");
            sb.Append($"  \"crush_m\": {(initialLength - length).ToString("F4", ic)},\n  \"length_initial_m\": {initialLength.ToString("F4", ic)},\n");
            sb.Append($"  \"broken_beams\": {m.brokenBeams},\n  \"plastic_beams\": {m.plasticBeams},\n");
            sb.Append($"  \"energy_J\": {{\"kinetic\": {m.kinetic.ToString("F1", ic)}, \"elastic\": {m.elastic.ToString("F1", ic)}, \"plastic\": {m.plastic.ToString("F1", ic)}, \"breaking\": {m.breaking.ToString("F1", ic)}}},\n");
            sb.Append($"  \"nonfinite_nodes\": {m.nonFinite},\n  \"max_node_speed\": {m.maxNodeSpeed.ToString("F2", ic)},\n");
            sb.Append($"  \"frames_captured\": {frameIndex},\n  \"sim_steps\": {runner.World.StepsTaken},\n");
            double simSeconds = substepsTotal * runner.World.dt;
            sb.Append($"  \"physics_ms_per_sim_second\": {(stepMsTotal / math.max(simSeconds, 1e-6)).ToString("F3", ic)},\n");
            sb.Append($"  \"physics_us_per_substep\": {(stepMsTotal * 1000.0 / math.max(substepsTotal, 1)).ToString("F3", ic)},\n");
            sb.Append($"  \"physics_ms_per_frame_max\": {stepMsMax.ToString("F3", ic)},\n");
            sb.Append($"  \"solver\": \"{(runner.World.UsesSingleThread ? "single-thread" : "parallel")}\",\n");
            sb.Append($"  \"stability_maxS\": {runner.Stability.maxS.ToString("F3", ic)},\n  \"stability_errors\": {runner.Stability.errorCount}\n");
            sb.Append("}\n");
            File.WriteAllText(Path.Combine(outDir, $"{runId}_result.json"), sb.ToString());
            Debug.Log($"[WallCrash] done: {sb}");
            Application.Quit(0);
#if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
#endif
        }
    }
}
