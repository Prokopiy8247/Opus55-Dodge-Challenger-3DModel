using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using Hellcat.Game.Cameras;
using Hellcat.Game.Core;
using Hellcat.Game.Input;
using Hellcat.Game.UI;
using Hellcat.Game.Views;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;

namespace Hellcat.Game.Scenario
{
    /// <summary>
    /// Gate G-Build (brief 14, P7): "controls work" in the standalone build. Started with <c>-scenario controls</c>, it
    /// adds a virtual keyboard and a virtual gamepad to the Input System (the game reads them like real devices) and
    /// presses every default control of brief 4.12 in turn on the open asphalt, checking the game's reaction: pedals,
    /// steering, handbrake and gears in the driver input and the car's speed; camera cycling, slow motion, the debug views,
    /// pause and single step, record / replay, reset and repair, the HUD, the driver aids and the pause menu; then the
    /// gamepad's triggers, stick and buttons. Writes controls_check.json (-controlsOut dir) and quits.
    /// </summary>
    public class ControlsCheck : MonoBehaviour
    {
        public SimRunner runner;
        public LiveDriverInput live;
        public GameControls controls;
        public CameraRig cameras;
        public DebugViews views;
        public ReplayController replay;
        public PauseMenu menu;
        public Hud hud;
        public Transform start;

        readonly CultureInfo ic = CultureInfo.InvariantCulture;
        readonly List<string> results = new List<string>();
        int passed, failed, respawns;
        Keyboard kb;
        Gamepad pad;
        string outDir;
        // largest driver input seen while a control is held
        float maxThrottle, maxBrake, maxHandbrake, minSteer, maxSteer;

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
            if (Arg("-scenario", "") != "controls")
            {
                enabled = false;
                return;
            }
            string root = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", ".."));
            outDir = Arg("-controlsOut", Path.Combine(root, "docs", "p7", "controls"));
            Directory.CreateDirectory(outDir);
            runner.Respawned += () => respawns++;
            StartCoroutine(Run());
        }

        float Speed() => runner.World.vehicleState[runner.VehicleIndex].speed;

        void Check(string control, string expect, bool ok, string observed)
        {
            if (ok) passed++; else failed++;
            results.Add($"    {{\"control\": \"{control}\", \"expected\": \"{expect}\", \"observed\": \"{observed.Replace("\"", "'")}\", " +
                        $"\"pass\": {(ok ? "true" : "false")}}}");
            Debug.Log($"[ControlsCheck] {(ok ? "PASS" : "FAIL")} {control}: {observed}");
        }

        IEnumerator Frames(int n)
        {
            for (int i = 0; i < n; i++)
            {
                var d = runner.LastInput;
                maxThrottle = Mathf.Max(maxThrottle, d.throttle);
                maxBrake = Mathf.Max(maxBrake, d.brake);
                maxHandbrake = Mathf.Max(maxHandbrake, d.handbrake);
                minSteer = Mathf.Min(minSteer, d.steer);
                maxSteer = Mathf.Max(maxSteer, d.steer);
                yield return null;
            }
        }

        void ResetPeaks()
        {
            maxThrottle = maxBrake = maxHandbrake = 0f;
            minSteer = maxSteer = 0f;
        }

        /// <summary>Holds the keys for the given real time, then releases them.</summary>
        IEnumerator Hold(float seconds, params Key[] keys)
        {
            ResetPeaks();
            InputSystem.QueueStateEvent(kb, new KeyboardState(keys));
            float t0 = Time.unscaledTime;
            while (Time.unscaledTime - t0 < seconds)
                yield return Frames(1);
            InputSystem.QueueStateEvent(kb, new KeyboardState());
            yield return Frames(3);
        }

        /// <summary>One press: down for two frames, up, two frames for the game to react.</summary>
        IEnumerator Tap(params Key[] keys)
        {
            InputSystem.QueueStateEvent(kb, new KeyboardState(keys));
            yield return Frames(2);
            InputSystem.QueueStateEvent(kb, new KeyboardState());
            yield return Frames(3);
        }

        IEnumerator Pad(GamepadState state, float seconds)
        {
            ResetPeaks();
            InputSystem.QueueStateEvent(pad, state);
            float t0 = Time.unscaledTime;
            while (Time.unscaledTime - t0 < seconds)
                yield return Frames(1);
            InputSystem.QueueStateEvent(pad, new GamepadState());
            yield return Frames(3);
        }

        IEnumerator Run()
        {
            if (hud) hud.visible = true;
            runner.RespawnSettled(start.position, start.rotation, 0f);
            yield return Frames(60);
            kb = InputSystem.AddDevice<Keyboard>("ControlsCheckKeyboard");
            pad = InputSystem.AddDevice<Gamepad>("ControlsCheckGamepad");
            yield return Frames(5);
            double t0 = Time.realtimeSinceStartupAsDouble;

            // ---- keyboard: driving
            float v0 = Speed();
            yield return Hold(2.5f, Key.W);
            float v1 = Speed();
            Check("W", "throttle 1, the car accelerates", maxThrottle > 0.9f && v1 - v0 > 3f,
                  $"throttle {maxThrottle:F2}, speed {v0 * 3.6f:F1} -> {v1 * 3.6f:F1} km/h");
            yield return Hold(0.6f, Key.A);
            Check("A", "steer left (-1)", minSteer < -0.9f, $"steer {minSteer:F2}");
            yield return Hold(0.6f, Key.D);
            Check("D", "steer right (+1)", maxSteer > 0.9f, $"steer {maxSteer:F2}");
            float vb = Speed();
            yield return Hold(1.2f, Key.S);
            float va = Speed();
            Check("S", "brake 1, the car slows", maxBrake > 0.9f && va < vb - 2f, $"brake {maxBrake:F2}, speed {vb * 3.6f:F1} -> {va * 3.6f:F1} km/h");
            yield return Hold(0.5f, Key.Space);
            Check("Space", "handbrake 1", maxHandbrake > 0.9f, $"handbrake {maxHandbrake:F2}");
            int g0 = live.ManualGearRequest;
            yield return Tap(Key.E);
            int g1 = live.ManualGearRequest;
            yield return Tap(Key.Q);
            int g2 = live.ManualGearRequest;
            Check("E / Q", "gear up, gear down (manual request)", g1 == Mathf.Max(g0, 0) + 1 && g2 == Mathf.Max(g1 - 1, 0),
                  $"manual gear {g0} -> E {g1} -> Q {g2}, driven gear {runner.World.vehicleState[runner.VehicleIndex].gear}");
            live.ManualGearRequest = 0;

            // ---- keyboard: cameras, time, views
            var seen = new List<string> { cameras.ModeName };
            for (int i = 0; i < 4; i++)
            {
                yield return Tap(Key.C);
                seen.Add(cameras.ModeName);
            }
            Check("C", "cycles chase, bumper, cockpit, free and back", new HashSet<string>(seen).Count == 4 && seen[0] == seen[4],
                  string.Join(" > ", seen));
            yield return Tap(Key.T);
            float slow = runner.timeScale;
            yield return Tap(Key.T);
            Check("T", "slow motion on and off", slow < 0.5f && Mathf.Approximately(runner.timeScale, 1f), $"time scale {slow:0.##} -> {runner.timeScale:0.##}");
            yield return Tap(Key.N);
            var sk1 = views.Skeleton;
            yield return Tap(Key.N);
            yield return Tap(Key.LeftShift, Key.N);
            var sk2 = views.Skeleton;
            yield return Tap(Key.LeftShift, Key.N);
            Check("N / Shift+N", "node-beam view, then overlay on the paint", sk1 == DebugViews.SkeletonMode.Alone &&
                  sk2 == DebugViews.SkeletonMode.Overlay && views.Skeleton == DebugViews.SkeletonMode.Off, $"{sk1}, {sk2}, then {views.Skeleton}");
            yield return Tap(Key.H);
            bool st = views.Stress;
            yield return Tap(Key.H);
            yield return Tap(Key.LeftShift, Key.H);
            bool de = views.Deformation;
            yield return Tap(Key.LeftShift, Key.H);
            Check("H / Shift+H", "stress heat-map, deformation heat-map", st && de && !views.Stress && !views.Deformation,
                  $"stress {st}, deformation {de}, then {views.Stress} / {views.Deformation}");
            yield return Tap(Key.P);
            bool paused = runner.paused;
            long s0 = runner.World.StepsTaken;
            yield return Frames(10);
            long s1 = runner.World.StepsTaken;
            yield return Tap(Key.LeftShift, Key.P);
            yield return Frames(3);
            long s2 = runner.World.StepsTaken;
            yield return Tap(Key.P);
            Check("P / Shift+P", "pause (no steps), single step (33 substeps), resume", paused && s1 == s0 && s2 - s1 == controls.stepSubsteps && !runner.paused,
                  $"paused {paused}, {s1 - s0} steps while paused, step {s2 - s1}, running again {!runner.paused}");

            // ---- keyboard: record / replay, reset / repair
            yield return Tap(Key.F5);
            var recState = replay.State;
            yield return Hold(1.0f, Key.W);
            yield return Tap(Key.F5);
            var afterStop = replay.State;
            bool haveRec = replay.Last != null && replay.Last.frames.Count > 0;
            yield return Tap(Key.F6);
            var playState = replay.State;
            yield return Frames(20);
            yield return Tap(Key.F6);
            Check("F5 / F6", "record, stop, replay, stop", recState == ReplayController.Mode.Recording && afterStop == ReplayController.Mode.Idle &&
                  haveRec && playState == ReplayController.Mode.Replaying && replay.State == ReplayController.Mode.Idle,
                  $"{recState}, {afterStop} ({(haveRec ? replay.Last.frames.Count : 0)} frames), {playState}, {replay.State}");
            yield return Hold(1.5f, Key.W);
            int r0 = respawns;
            yield return Tap(Key.R);
            yield return Frames(10);
            Check("R", "reset: a fresh car at rest at the last safe spot", respawns == r0 + 1 && Mathf.Abs(Speed()) < 0.5f,
                  $"respawns +{respawns - r0}, speed {Speed() * 3.6f:F1} km/h; '{controls.Message}'");
            r0 = respawns;
            yield return Tap(Key.LeftShift, Key.R);
            yield return Frames(10);
            Check("Shift+R", "repair in place", respawns == r0 + 1 && controls.Message.StartsWith("repaired", StringComparison.Ordinal),
                  $"respawns +{respawns - r0}; '{controls.Message}'");

            // ---- keyboard: HUD, aids, menu
            bool h0 = hud.visible;
            yield return Tap(Key.F1);
            bool h1 = hud.visible;
            yield return Tap(Key.F1);
            Check("F1", "HUD off and on", h0 && !h1 && hud.visible, $"{h0} -> {h1} -> {hud.visible}");
            bool a0 = live.abs, c0 = live.tc;
            yield return Tap(Key.F7);
            yield return Tap(Key.F8);
            bool a1 = live.abs, c1 = live.tc;
            yield return Tap(Key.F7);
            yield return Tap(Key.F8);
            Check("F7 / F8", "ABS and traction control toggle", a1 != a0 && c1 != c0 && live.abs == a0 && live.tc == c0,
                  $"ABS {a0} -> {a1}, TC {c0} -> {c1}");
            yield return Tap(Key.Escape);
            bool open = menu.Open;
            yield return Tap(Key.Escape);
            Check("Esc", "pause menu opens and closes", open && !menu.Open, $"open {open}, then {menu.Open}");

            // ---- gamepad
            yield return Pad(new GamepadState { rightTrigger = 0.8f }, 1.0f);
            Check("gamepad right trigger", "analog throttle 0.8", maxThrottle > 0.75f && maxThrottle < 0.85f, $"throttle {maxThrottle:F2}");
            yield return Pad(new GamepadState { leftTrigger = 0.6f }, 0.6f);
            Check("gamepad left trigger", "analog brake 0.6", maxBrake > 0.55f && maxBrake < 0.65f, $"brake {maxBrake:F2}");
            yield return Pad(new GamepadState { leftStick = new Vector2(-0.5f, 0f) }, 0.5f);
            Check("gamepad left stick", "analog steering -0.5", minSteer < -0.4f && minSteer > -0.6f, $"steer {minSteer:F2}");
            yield return Pad(new GamepadState().WithButton(GamepadButton.East), 0.4f);
            Check("gamepad B (east)", "handbrake", maxHandbrake > 0.9f, $"handbrake {maxHandbrake:F2}");
            string cam0 = cameras.ModeName;
            yield return Pad(new GamepadState().WithButton(GamepadButton.North), 0.1f);
            Check("gamepad Y (north)", "next camera", cameras.ModeName != cam0, $"{cam0} -> {cameras.ModeName}");
            int gp = live.ManualGearRequest;
            yield return Pad(new GamepadState().WithButton(GamepadButton.RightShoulder), 0.1f);
            Check("gamepad RB", "gear up", live.ManualGearRequest == Mathf.Max(gp, 0) + 1, $"manual gear {gp} -> {live.ManualGearRequest}");
            live.ManualGearRequest = 0;

            InputSystem.RemoveDevice(kb);
            InputSystem.RemoveDevice(pad);
            var sb = new StringBuilder("{\n");
            sb.Append($"  \"time_utc\": \"{DateTime.UtcNow:yyyy-MM-ddTHH:mm:ssZ}\",\n");
            sb.Append($"  \"executable\": \"{Path.GetFileName(Environment.GetCommandLineArgs()[0]).Replace("\\", "/")}\",\n");
            sb.Append($"  \"screen\": \"{Screen.width}x{Screen.height}\",\n");
            sb.Append($"  \"devices\": \"virtual keyboard and gamepad through the Input System\",\n");
            sb.Append($"  \"seconds\": {(Time.realtimeSinceStartupAsDouble - t0).ToString("F1", ic)},\n");
            sb.Append($"  \"passed\": {passed},\n  \"failed\": {failed},\n  \"checks\": [\n{string.Join(",\n", results)}\n  ]\n}}\n");
            File.WriteAllText(Path.Combine(outDir, "controls_check.json"), sb.ToString());
            Debug.Log($"[ControlsCheck] {passed} passed, {failed} failed -> {outDir}");
            yield return null;
            Application.Quit(failed == 0 ? 0 : 2);
#if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
#endif
        }
    }
}
