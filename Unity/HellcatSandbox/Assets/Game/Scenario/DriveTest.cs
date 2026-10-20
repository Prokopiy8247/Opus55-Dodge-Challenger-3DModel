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
using Hellcat.Game.Input;
using Hellcat.Game.UI;
using Hellcat.Game.Views;
using Hellcat.Sim;
using Hellcat.Sim.Validation;
using Unity.Mathematics;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;

namespace Hellcat.Game.Scenario
{
    /// <summary>
    /// Gate G-Drive (brief 14, P4b): the drive player started with <c>-scenario drive</c> measures, in the rendered game,
    /// (1) input latency: a key press (D, queued on a virtual keyboard through the Input System) until the first rendered
    /// frame whose front wheel has turned 0.25 deg, several probes at rest; (2) a continuous drive of the driver robot on a
    /// 977 m stadium loop (300 m straights at 160 km/h, R 60 m curves at 75 km/h, ABS and TC on), five minutes of simulated
    /// time in five camera / view segments (chase, cockpit with mirrors, bumper, node-beam overlay with the stress map,
    /// deformation map), logging physics Hz, frame times, path error and divergence signs (non-finite values, node speeds,
    /// broken or bent beams, cabin floor bending); (3) the first 60 s of the drive recorded (F5 path) and replayed (F6
    /// path) with the end states compared bit for bit. Results: drive_test.json, drive_timeseries.csv, screenshots.
    /// Options: -driveOut dir, -driveSeconds s, -driveRecord s.
    /// </summary>
    public class DriveTest : MonoBehaviour
    {
        public SimRunner runner;
        public RobotDriverSource robot;
        public LiveDriverInput live;
        public CameraRig cameras;
        public DebugViews views;
        public ReplayController replay;
        public Hud hud;
        public CockpitInstruments cockpit;
        public Transform start;

        public double straight = 300.0, radius = 60.0;
        public double straightKmh = 160.0, curveKmh = 75.0, brakeDecel = 5.5;

        string outDir;
        double driveSeconds = 300.0, recordSeconds = 60.0;
        readonly List<string> rows = new List<string>();
        readonly List<(int frames, double ms, bool ok)> probes = new List<(int, double, bool)>();
        readonly CultureInfo ic = CultureInfo.InvariantCulture;

        // per-frame and per-segment statistics
        sealed class Segment
        {
            public string name;
            public readonly List<float> frameMs = new List<float>();
            public long substeps;
            public double realSeconds, stepMs;
            public int slowFrames;
        }
        readonly List<Segment> segments = new List<Segment>();
        Segment seg;

        static string Arg(string name, string fallback)
        {
            var a = Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++)
                if (a[i] == name)
                    return a[i + 1];
            return fallback;
        }

        void Start()
        {
            if (Arg("-scenario", "") != "drive")
            {
                enabled = false;
                return;
            }
            // editor: <root>/Unity/HellcatSandbox/Assets; player: <root>/Builds/<name>/<exe>_Data
            string root = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", ".."));
            outDir = Arg("-driveOut", Path.Combine(root, "docs", "p4b", "drive"));
            driveSeconds = double.Parse(Arg("-driveSeconds", "300"), ic);
            recordSeconds = double.Parse(Arg("-driveRecord", "60"), ic);
            Directory.CreateDirectory(outDir);
            StartCoroutine(Run());
        }

        PolyPath Stadium() => DriveLoop.Path(start, straight, radius);

        double TargetSpeed(double arc) => DriveLoop.TargetSpeed(arc, straight, radius, straightKmh, curveKmh, brakeDecel);

        IEnumerator Run()
        {
            var eof = new WaitForEndOfFrame();
            Debug.Log($"[DriveTest] start: {driveSeconds:F0} s drive, out {outDir}");
            if (hud) hud.visible = true;
            runner.RespawnSettled(start.position, start.rotation, 0f);
            for (int i = 0; i < 90; i++) yield return null;   // warm-up (shader compilation, first frames)

            // ---- 1. input latency
            var kb = InputSystem.AddDevice<Keyboard>("DriveTestKeyboard");
            var probe = robot.Probe ?? new CarProbe(runner.World, runner.VehicleBody);
            int fl = probe.WheelIndex("FL");
            for (int k = 0; k < 10; k++)
            {
                for (int i = 0; i < 45; i++) yield return null;
                yield return eof;
                double a0 = probe.RoadWheelDeg(fl, probe.Frame());
                InputSystem.QueueStateEvent(kb, new KeyboardState(Key.D));
                double t0 = Time.realtimeSinceStartupAsDouble;
                int f0 = Time.frameCount;
                bool ok = false;
                int frames = 0;
                double ms = 0;
                for (int i = 0; i < 30 && !ok; i++)
                {
                    yield return eof;
                    double a = probe.RoadWheelDeg(fl, probe.Frame());
                    if (math.abs(a - a0) >= 0.25)
                    {
                        ok = true;
                        frames = Time.frameCount - f0;
                        ms = (Time.realtimeSinceStartupAsDouble - t0) * 1000.0;
                    }
                }
                InputSystem.QueueStateEvent(kb, new KeyboardState());
                probes.Add((frames, ms, ok));
                Debug.Log($"[DriveTest] latency probe {k}: {(ok ? $"{frames} frames, {ms:F1} ms" : "no reaction")}");
            }
            for (int i = 0; i < 90; i++) yield return null;
            InputSystem.RemoveDevice(kb);

            // ---- 2. the drive
            runner.RespawnSettled(start.position, start.rotation, 0f);
            yield return null;
            var path = Stadium();
            robot.Begin(path, (t, arc) => TargetSpeed(arc));
            replay.StartRecording("G-Drive drive test");
            double t0Drive = runner.SimTime;
            double nextSample = 0.0, nextShot = 30.0;
            string[] names = { "chase", "cockpit", "bumper", "overlay_stress", "deformation" };
            int segIndex = -1;
            ulong recordedHash = 0;
            InputRecording rec = null;
            double maxLat = 0, sumLat2 = 0, maxResidual = 0, minUp = 1, maxSpeed = 0, maxNodeRatio = 0, distance = 0;
            int nLat = 0, nonFinite = 0, broken = 0, plastic = 0;
            float3 lastCom = (float3)robot.Probe.Frame().com;
            double lap = path.Length;
            while (runner.SimTime - t0Drive < driveSeconds)
            {
                double t = runner.SimTime - t0Drive;
                int want = math.min((int)(t / math.max(driveSeconds / names.Length, 1.0)), names.Length - 1);
                if (want != segIndex)
                {
                    segIndex = want;
                    SetView(names[segIndex]);
                    seg = new Segment { name = names[segIndex] };
                    segments.Add(seg);
                    nextShot = t + 0.5 * driveSeconds / names.Length;
                }
                yield return null;
                seg.frameMs.Add(Time.unscaledDeltaTime * 1000f);
                seg.realSeconds += Time.unscaledDeltaTime;
                seg.substeps += runner.LastSubsteps;
                seg.stepMs += runner.LastStepMs;
                if (runner.SlowDown) seg.slowFrames++;

                if (rec == null && runner.SimTime - t0Drive >= recordSeconds)
                {
                    rec = replay.StopRecording(true, Path.Combine(outDir, "drive_record.hrec"));
                    recordedHash = WorldState.Hash(runner.World);
                }
                if (runner.SimTime - t0Drive >= nextShot)
                {
                    nextShot = double.MaxValue;
                    yield return eof;
                    ScreenCapture.CaptureScreenshot(Path.Combine(outDir, $"drive_{segIndex + 1}_{names[segIndex]}.png"));
                    if (names[segIndex] == "cockpit" && cockpit != null)
                        cockpit.SaveMirrors(outDir);
                }
                if (runner.SimTime - t0Drive >= nextSample)
                {
                    nextSample += 0.25;
                    var f = robot.Frame;
                    var m = runner.World.Metrics(runner.VehicleBody, false);
                    double residual = robot.Probe.FloorResidual();
                    double lat = robot.Robot.lateral;
                    if (t > 20.0)   // after the start from rest
                    {
                        maxLat = math.max(maxLat, math.abs(lat));
                        sumLat2 += lat * lat;
                        nLat++;
                    }
                    maxResidual = math.max(maxResidual, residual);
                    minUp = math.min(minUp, f.up.y);
                    maxSpeed = math.max(maxSpeed, f.speed);
                    double ratio = m.maxNodeSpeed / math.max(math.abs(f.speed), 10.0);
                    maxNodeRatio = math.max(maxNodeRatio, ratio);
                    nonFinite = math.max(nonFinite, m.nonFinite);
                    broken = m.brokenBeams;
                    plastic = m.plasticBeams;
                    distance += math.distance(lastCom.xz, ((float3)f.com).xz);
                    lastCom = (float3)f.com;
                    rows.Add(string.Join(",", new[]
                    {
                        t.ToString("F3", ic), (f.speed * 3.6).ToString("F2", ic), lat.ToString("F3", ic), robot.Robot.arc.ToString("F1", ic),
                        f.up.y.ToString("F5", ic), (residual * 1000).ToString("F2", ic), m.brokenBeams.ToString(), m.plasticBeams.ToString(),
                        m.maxNodeSpeed.ToString("F2", ic), runner.PhysicsHz.ToString("F0", ic), runner.RealTimeFactor.ToString("F3", ic),
                        (hud ? hud.Fps : 0f).ToString("F1", ic), seg.name, runner.LastInput.throttle.ToString("F2", ic),
                        runner.LastInput.brake.ToString("F2", ic), runner.LastInput.steer.ToString("F3", ic), m.nonFinite.ToString(),
                    }));
                    if (m.nonFinite > 0 || f.up.y < 0.5)
                    {
                        Debug.LogError($"[DriveTest] diverged at {t:F1} s: non-finite {m.nonFinite}, up {f.up.y:F2}");
                        break;
                    }
                }
            }
            double driven = runner.SimTime - t0Drive;
            robot.End();
            SetView("chase");
            if (rec == null)
                rec = replay.StopRecording(true, Path.Combine(outDir, "drive_record.hrec"));

            // ---- 3. replay of the recorded minute
            bool replayOk = false;
            ulong replayHash = 0;
            double replayReal = 0;
            if (rec != null && recordedHash != 0)
            {
                double rt0 = Time.realtimeSinceStartupAsDouble;
                replay.StartReplay(rec);
                while (replay.State == ReplayController.Mode.Replaying)
                    yield return null;
                replayHash = WorldState.Hash(runner.World);
                replayOk = replayHash == recordedHash;
                replayReal = Time.realtimeSinceStartupAsDouble - rt0;
                Debug.Log($"[DriveTest] replay of {rec.Duration:F1} s: {(replayOk ? "bit-identical" : "DIFFERENT")} ({replayReal:F1} s real)");
            }

            Write(driven, lap, distance, maxLat, nLat > 0 ? math.sqrt(sumLat2 / nLat) : double.NaN, maxResidual, minUp, maxSpeed, maxNodeRatio,
                nonFinite, broken, plastic, rec, recordedHash, replayHash, replayOk, replayReal);
            Debug.Log("[DriveTest] done");
            yield return null;
            Application.Quit(0);
#if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
#endif
        }

        void SetView(string name)
        {
            if (views != null)
            {
                if (views.Skeleton != DebugViews.SkeletonMode.Off) views.ToggleSkeleton(views.Skeleton == DebugViews.SkeletonMode.Overlay);
                if (views.Stress) views.ToggleStress();
                if (views.Deformation) views.ToggleDeformation();
            }
            switch (name)
            {
                case "chase": cameras.mode = CameraMode.Chase; break;
                case "cockpit": cameras.mode = CameraMode.Cockpit; break;
                case "bumper": cameras.mode = CameraMode.Bumper; break;
                case "overlay_stress":
                    cameras.mode = CameraMode.Chase;
                    views?.ToggleSkeleton(true);
                    views?.ToggleStress();
                    break;
                case "deformation":
                    cameras.mode = CameraMode.Chase;
                    views?.ToggleDeformation();
                    break;
            }
        }

        static float Percentile(List<float> v, double p)
        {
            if (v.Count == 0) return float.NaN;
            var s = v.OrderBy(x => x).ToList();
            return s[(int)math.clamp(math.round(p * (s.Count - 1)), 0, s.Count - 1)];
        }

        void Write(double driven, double lap, double distance, double maxLat, double rmsLat, double maxResidual, double minUp,
            double maxSpeed, double maxNodeRatio, int nonFinite, int broken, int plastic, InputRecording rec, ulong recHash,
            ulong repHash, bool replayOk, double replayReal)
        {
            string F(double v, string f = "F3") => double.IsFinite(v) ? v.ToString(f, ic) : "null";
            var all = segments.SelectMany(s => s.frameMs).ToList();
            double real = segments.Sum(s => s.realSeconds);
            long substeps = segments.Sum(s => s.substeps);
            double stepMs = segments.Sum(s => s.stepMs);
            int slow = segments.Sum(s => s.slowFrames);
            var okProbes = probes.Where(p => p.ok).ToList();
            var sb = new StringBuilder("{\n");
            sb.Append($"  \"scenario\": \"drive\",\n  \"time_utc\": \"{DateTime.UtcNow:yyyy-MM-ddTHH:mm:ssZ}\",\n");
            sb.Append($"  \"system\": {{\"cpu\": \"{SystemInfo.processorType}\", \"threads\": {SystemInfo.processorCount}, \"gpu\": \"{SystemInfo.graphicsDeviceName}\", " +
                      $"\"screen\": \"{Screen.width}x{Screen.height}\", \"refresh_hz\": {F(Screen.currentResolution.refreshRateRatio.value, "F1")}, " +
                      $"\"vsync\": {QualitySettings.vSyncCount}, \"editor\": {(Application.isEditor ? "true" : "false")}}},\n");
            sb.Append($"  \"sim\": {{\"nodes\": {runner.World.NodeCount}, \"beams\": {runner.World.BeamCount}, \"dt_ms\": {F(runner.World.dt * 1000.0, "F2")}, " +
                      $"\"threads\": \"{(runner.World.UsesSingleThread ? "single" : "Burst parallel")}\", \"max_substeps_per_frame\": {runner.maxSubstepsPerFrame}}},\n");
            sb.Append($"  \"drive_seconds\": {F(driven, "F2")},\n  \"distance_km\": {F(distance / 1000.0, "F3")},\n  \"laps\": {F(distance / lap, "F2")},\n");
            sb.Append($"  \"frames\": {all.Count},\n  \"real_seconds\": {F(real, "F2")},\n");
            sb.Append($"  \"physics_hz_mean\": {F(substeps / math.max(real, 1e-6), "F1")},\n  \"realtime_factor\": {F(substeps * runner.World.dt / math.max(real, 1e-6), "F4")},\n");
            sb.Append($"  \"slowdown_frames\": {slow},\n  \"step_us_per_substep\": {F(stepMs * 1000.0 / math.max(substeps, 1), "F1")},\n");
            sb.Append($"  \"fps_mean\": {F(all.Count / math.max(real, 1e-6), "F1")},\n  \"frame_ms_p50\": {F(Percentile(all, 0.5), "F2")},\n");
            sb.Append($"  \"frame_ms_p99\": {F(Percentile(all, 0.99), "F2")},\n  \"frame_ms_max\": {F(all.Count > 0 ? all.Max() : double.NaN, "F2")},\n");
            sb.Append($"  \"fps_1pct_low\": {F(1000.0 / Percentile(all, 0.99), "F1")},\n");
            sb.Append("  \"segments\": [\n");
            for (int i = 0; i < segments.Count; i++)
            {
                var s = segments[i];
                sb.Append($"    {{\"view\": \"{s.name}\", \"frames\": {s.frameMs.Count}, \"fps_mean\": {F(s.frameMs.Count / math.max(s.realSeconds, 1e-6), "F1")}, " +
                          $"\"frame_ms_p99\": {F(Percentile(s.frameMs, 0.99), "F2")}, \"physics_hz\": {F(s.substeps / math.max(s.realSeconds, 1e-6), "F0")}, " +
                          $"\"step_us_per_substep\": {F(s.stepMs * 1000.0 / math.max(s.substeps, 1), "F1")}, \"slowdown_frames\": {s.slowFrames}}}{(i < segments.Count - 1 ? "," : "")}\n");
            }
            sb.Append("  ],\n");
            sb.Append($"  \"latency_probes\": {probes.Count},\n  \"latency_reacted\": {okProbes.Count},\n");
            sb.Append($"  \"latency_frames_mean\": {F(okProbes.Count > 0 ? okProbes.Average(p => p.frames) : double.NaN, "F2")},\n");
            sb.Append($"  \"latency_frames_max\": {(okProbes.Count > 0 ? okProbes.Max(p => p.frames) : -1)},\n");
            sb.Append($"  \"latency_ms_mean\": {F(okProbes.Count > 0 ? okProbes.Average(p => p.ms) : double.NaN, "F1")},\n");
            sb.Append($"  \"latency_ms_max\": {F(okProbes.Count > 0 ? okProbes.Max(p => p.ms) : double.NaN, "F1")},\n");
            sb.Append($"  \"latency_list_ms\": [{string.Join(", ", probes.Select(p => p.ok ? p.ms.ToString("F1", ic) : "null"))}],\n");
            sb.Append($"  \"path_error_max_m\": {F(maxLat)},\n  \"path_error_rms_m\": {F(rmsLat)},\n  \"speed_max_kmh\": {F(maxSpeed * 3.6, "F1")},\n");
            sb.Append($"  \"up_min\": {F(minUp, "F4")},\n  \"floor_residual_max_mm\": {F(maxResidual * 1000.0, "F2")},\n");
            sb.Append($"  \"node_speed_ratio_max\": {F(maxNodeRatio)},\n  \"non_finite\": {nonFinite},\n");
            sb.Append($"  \"broken_beams\": {broken},\n  \"plastic_beams\": {plastic},\n");
            sb.Append($"  \"replay_seconds\": {F(rec != null ? rec.Duration : double.NaN, "F2")},\n  \"replay_frames\": {(rec != null ? rec.frames.Count : 0)},\n");
            sb.Append($"  \"replay_hash_recorded\": \"{recHash:X16}\",\n  \"replay_hash_replayed\": \"{repHash:X16}\",\n");
            sb.Append($"  \"replay_bit_identical\": {(replayOk ? "true" : "false")},\n  \"replay_real_seconds\": {F(replayReal, "F1")}\n}}\n");
            File.WriteAllText(Path.Combine(outDir, "drive_test.json"), sb.ToString());
            File.WriteAllText(Path.Combine(outDir, "drive_timeseries.csv"),
                "t_s,speed_kmh,path_error_m,arc_m,up_y,floor_residual_mm,broken,plastic,max_node_speed,physics_hz,realtime_factor,fps,view,throttle,brake,steer,non_finite\n" +
                string.Join("\n", rows) + "\n");
        }
    }
}
