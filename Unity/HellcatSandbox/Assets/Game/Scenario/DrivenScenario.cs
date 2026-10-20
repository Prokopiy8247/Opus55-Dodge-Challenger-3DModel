using System;
using System.Collections;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using Hellcat.Game.Cameras;
using Hellcat.Game.Capture;
using Hellcat.Game.Core;
using Hellcat.Game.UI;
using Hellcat.Game.World;
using Hellcat.Sim;
using Unity.Mathematics;
using UnityEngine;

namespace Hellcat.Game.Scenario
{
    /// <summary>
    /// The driven variant of a scripted scenario (brief 9, P6): the scenario's lane through the game's own controls - the
    /// pause menu's "teleport to obstacle at V km/h" with the speed hold that lets go 1 m before the obstacle (D-080) -
    /// recorded as with F5 and replayed as with F6 (the recorded frame partition at time scale 1); the replay's end state
    /// must equal the run's bit for bit. Command line (test-map player):
    ///   -scenario S1..S8 -driven 1 -out &lt;dir&gt; [-targetKmh v] [-postImpact s]
    /// Writes &lt;run&gt;_driven.json, the recording (&lt;run&gt;_driven.hrec / .csv) and a still at the end of the run and
    /// of the replay.
    /// </summary>
    public class DrivenScenario : MonoBehaviour
    {
        public SimRunner runner;
        public GameControls controls;
        public ReplayController replay;
        public CameraRig cameras;
        public Hud hud;

        static readonly CultureInfo Ic = CultureInfo.InvariantCulture;

        static string Arg(string name, string fallback)
        {
            var a = Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++)
                if (string.Equals(a[i], name, StringComparison.OrdinalIgnoreCase))
                    return a[i + 1];
            return fallback;
        }

        void Start()
        {
            var spec = CarCrashScenario.Find(Arg("-scenario", ""));
            if (spec == null || Arg("-driven", "0") != "1")
            {
                enabled = false;
                return;
            }
            StartCoroutine(Run(spec));
        }

        static string F(double v, string f = "F3") => double.IsFinite(v) ? v.ToString(f, Ic) : "null";

        IEnumerator Run(CarCrashScenario.Spec spec)
        {
            CultureInfo.CurrentCulture = CultureInfo.DefaultThreadCurrentCulture = Ic;
            Time.captureFramerate = 60;            // 1/60 s per frame: 33 or 34 substeps, as a 60 fps game frame
            if (hud) hud.visible = false;
            float kmh = float.Parse(Arg("-targetKmh", spec.kmh.ToString(Ic)), Ic);
            string outDir = Arg("-out", Path.Combine(Application.persistentDataPath, "driven"));
            Directory.CreateDirectory(outDir);
            string runId = $"{spec.id}_{kmh:F0}kmh";
            for (int i = 0; i < 30; i++) yield return null;
            var sp = FindObjectsByType<SpawnPoint>(FindObjectsInactive.Exclude, FindObjectsSortMode.None)
                .OrderBy(s => s.order).FirstOrDefault(s => s.label.StartsWith(spec.lane + " ", StringComparison.Ordinal));
            if (sp == null)
            {
                Debug.LogError($"[Driven] no lane {spec.lane}");
                Application.Quit(1);
                yield break;
            }
            var w = runner.World;
            float post = float.Parse(Arg("-postImpact", spec.post.ToString(Ic)), Ic);
            // the run-up at the speed, the event and the time after it (the debris field is passed at the speed)
            double seconds = sp.approachDistance / (kmh / 3.6) + post + (spec.kind == CarCrashScenario.Kind.Debris ? 6.0 : 1.5);

            // the player's path: teleport at V with the speed hold, record (F5)
            controls.holdApproachSpeed = true;
            controls.Teleport(sp, kmh);
            cameras.mode = CameraMode.Chase;
            replay.StartRecording($"{runId} driven: {spec.what}");
            var crash = new CrashMetrics(w, runner.VehicleBody);
            double t0 = runner.SimTime;
            float releaseKmh = float.NaN, maxDecel = 0f;
            string releaseWhy = "";   // read at the release: the replay's respawn ends the coasting and rewrites the reason
            float3 lastV = float3.zero;
            bool have = false;
            while (runner.SimTime - t0 < seconds)
            {
                yield return null;
                crash.Cabin(out _, out float3 v);
                if (have && runner.LastSubsteps > 0)
                    maxDecel = math.max(maxDecel, math.length(v - lastV) / (runner.LastSubsteps * w.dt) / 9.81f);
                lastV = v;
                have = true;
                if (float.IsNaN(releaseKmh) && controls.approach != null && !controls.approach.Holding && runner.SimTime - t0 > 0.1)
                {
                    releaseKmh = controls.approach.ReleaseSpeed * 3.6f;
                    releaseWhy = controls.approach.ReleaseReason;
                }
            }
            string recPath = Path.Combine(outDir, $"{runId}_driven.hrec");
            var rec = replay.StopRecording(true, recPath);
            ulong runHash = WorldState.Hash(w);
            long runSteps = w.StepsTaken;
            var m = w.Metrics(runner.VehicleBody, false);
            var detached = crash.Detached();
            double deform = crash.MaxDeformation(crash.Connected(), out int deformNode);
            yield return new WaitForEndOfFrame();
            var cam = cameras.GetComponent<Camera>();
            FrameCapture.Save(cam, Path.Combine(outDir, $"{runId}_driven_end_run.png"), 1600, 900);

            // replay (F6): the recorded frame partition at time scale 1
            var fromFile = InputRecording.Read(recPath);
            bool started = replay.StartReplay(fromFile);
            int guard = fromFile.frames.Count + 10;
            while (started && replay.State == ReplayController.Mode.Replaying && guard-- > 0)
                yield return null;
            runner.paused = true;
            ulong replayHash = WorldState.Hash(w);
            bool identical = replayHash == runHash && w.StepsTaken == runSteps;
            yield return new WaitForEndOfFrame();
            FrameCapture.Save(cam, Path.Combine(outDir, $"{runId}_driven_end_replay.png"), 1600, 900);

            var sb = new StringBuilder("{\n");
            sb.Append($"  \"scenario\": \"{spec.id}\",\n  \"variant\": \"driven (teleport at V with the speed hold, recorded F5, replayed F6)\",\n");
            sb.Append($"  \"lane\": \"{sp.label}\",\n  \"target_kmh\": {F(kmh, "F1")},\n");
            sb.Append($"  \"release\": \"{releaseWhy}\",\n  \"release_kmh\": {F(releaseKmh, "F2")},\n");
            sb.Append($"  \"peak_cabin_accel_g_frame\": {F(maxDecel, "F2")},\n");
            sb.Append($"  \"broken_beams\": {m.brokenBeams},\n  \"plastic_beams\": {m.plasticBeams},\n");
            sb.Append($"  \"max_deformation_m\": {F(deform, "F4")},\n  \"max_deformation_node\": \"{crash.NodeName(deformNode)}\",\n");
            sb.Append($"  \"detached_parts\": [{string.Join(", ", detached.Select(d => $"\"{d}\""))}],\n");
            sb.Append($"  \"nonfinite_nodes\": {m.nonFinite},\n");
            sb.Append($"  \"recording\": \"{Path.GetFileName(recPath)}\",\n  \"recording_frames\": {(rec != null ? rec.frames.Count : 0)},\n");
            sb.Append($"  \"recording_s\": {F(rec != null ? rec.Duration : double.NaN, "F3")},\n");
            sb.Append($"  \"recording_bytes\": {(File.Exists(recPath) ? new FileInfo(recPath).Length : 0)},\n");
            sb.Append($"  \"replay_exact_partition\": {(replay.Exact ? "true" : "false")},\n");
            sb.Append($"  \"run_state_hash\": \"{runHash:x16}\",\n  \"replay_state_hash\": \"{replayHash:x16}\",\n");
            sb.Append($"  \"replay_identical\": {(identical ? "true" : "false")}\n}}\n");
            File.WriteAllText(Path.Combine(outDir, $"{runId}_driven.json"), sb.ToString());
            Debug.Log($"[Driven] {runId}: released at {releaseKmh:F1} km/h ({releaseWhy}), broken {m.brokenBeams}, " +
                      $"deformation {deform:F3} m, replay {(identical ? "identical" : "DIFFERS")}");
            yield return null;
            Application.Quit(0);
#if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
#endif
        }
    }
}
