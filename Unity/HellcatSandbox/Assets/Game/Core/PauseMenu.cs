using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Hellcat.Game.Cameras;
using Hellcat.Game.Views;
using Hellcat.Game.World;
using Hellcat.Sim;
using UnityEngine;

namespace Hellcat.Game.Core
{
    /// <summary>
    /// Pause menu (Esc, brief 4.12 quality of life): resume, reset / repair, the spawn points with "teleport to obstacle N
    /// at speed V", camera, time scale, debug views, driver aids, recordings (record, replay, the latest files) and the
    /// settings file. The simulation is paused while the menu is open.
    /// </summary>
    public class PauseMenu : MonoBehaviour
    {
        public SimRunner runner;
        public GameControls controls;
        public CameraRig cameras;
        public DebugViews views;
        public ReplayController replay;

        public bool Open { get; private set; }

        bool wasPaused;
        float teleportKmh = 50f;
        Vector2 scroll;
        SpawnPoint[] spawns = Array.Empty<SpawnPoint>();
        string[] files = Array.Empty<string>();
        GUIStyle title, label, button;

        void Start()
        {
            spawns = FindObjectsByType<SpawnPoint>(FindObjectsInactive.Exclude).OrderBy(s => s.order).ThenBy(s => s.label).ToArray();
        }

        public void Toggle()
        {
            Open = !Open;
            if (Open)
            {
                wasPaused = runner.paused;
                runner.paused = true;
                RefreshFiles();
            }
            else
            {
                runner.paused = wasPaused;
            }
        }

        void Close()
        {
            if (Open) Toggle();
        }

        void RefreshFiles()
        {
            try
            {
                files = Directory.Exists(GameSettings.RecordingsPath)
                    ? new DirectoryInfo(GameSettings.RecordingsPath).GetFiles("*.hrec").OrderByDescending(f => f.LastWriteTimeUtc).Take(6).Select(f => f.FullName).ToArray()
                    : Array.Empty<string>();
            }
            catch (Exception)
            {
                files = Array.Empty<string>();
            }
        }

        void OnGUI()
        {
            if (!Open || runner == null || runner.World == null)
                return;
            title ??= new GUIStyle(GUI.skin.label) { fontSize = 22, fontStyle = FontStyle.Bold };
            label ??= new GUIStyle(GUI.skin.label) { fontSize = 14, richText = true };
            button ??= new GUIStyle(GUI.skin.button) { fontSize = 14 };
            float w = Mathf.Min(560f, Screen.width - 40f), h = Mathf.Min(700f, Screen.height - 40f);
            var area = new Rect((Screen.width - w) * 0.5f, (Screen.height - h) * 0.5f, w, h);
            GUI.Box(area, GUIContent.none);
            GUI.Box(area, GUIContent.none);
            GUILayout.BeginArea(new Rect(area.x + 14, area.y + 10, area.width - 28, area.height - 20));
            GUILayout.Label("Hellcat Sandbox - paused", title);
            scroll = GUILayout.BeginScrollView(scroll);

            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Resume (Esc)", button)) Close();
            if (GUILayout.Button("Reset to safe position (R)", button)) { controls.ResetToSafe(); Close(); }
            if (GUILayout.Button("Repair here (Shift+R)", button)) { controls.RepairInPlace(); Close(); }
            if (GUILayout.Button("Reset debris (Ctrl+R)", button)) { controls.ResetMap(); Close(); }
            GUILayout.EndHorizontal();

            GUILayout.Space(8);
            GUILayout.Label("<b>Spawn points and obstacles</b>", label);
            GUILayout.BeginHorizontal();
            GUILayout.Label($"teleport speed {teleportKmh:F0} km/h", label, GUILayout.Width(170));
            teleportKmh = Mathf.Round(GUILayout.HorizontalSlider(teleportKmh, 0f, 200f) / 5f) * 5f;
            GUILayout.EndHorizontal();
            controls.holdApproachSpeed = GUILayout.Toggle(controls.holdApproachSpeed,
                "hold the speed on the lane until 1 m before the obstacle (any pedal or steering takes over)", button);
            foreach (var sp in spawns)
            {
                GUILayout.BeginHorizontal();
                string dist = sp.approachDistance > 0f ? $" ({sp.approachDistance:F0} m to the face)" : "";
                GUILayout.Label($"{sp.order}. {sp.label}{dist}", label, GUILayout.Width(300));
                if (GUILayout.Button("at rest", button)) { controls.Teleport(sp, 0f); Close(); }
                if (GUILayout.Button($"at {teleportKmh:F0} km/h", button)) { controls.Teleport(sp, teleportKmh); Close(); }
                GUILayout.EndHorizontal();
            }

            GUILayout.Space(8);
            GUILayout.Label("<b>Camera and time</b>", label);
            GUILayout.BeginHorizontal();
            foreach (CameraMode m in Enum.GetValues(typeof(CameraMode)))
                if (cameras != null && GUILayout.Toggle(cameras.mode == m, m.ToString(), button))
                    cameras.mode = m;
            GUILayout.EndHorizontal();
            GUILayout.BeginHorizontal();
            foreach (float s in new[] { 1f, 0.5f, 0.25f, 0.1f, 0.05f })
                if (GUILayout.Toggle(Mathf.Approximately(runner.timeScale, s), $"x{s:0.##}", button))
                    runner.timeScale = s;
            GUILayout.EndHorizontal();

            if (views != null)
            {
                GUILayout.Space(8);
                GUILayout.Label("<b>Views</b>", label);
                GUILayout.BeginHorizontal();
                if (GUILayout.Toggle(views.Skeleton == DebugViews.SkeletonMode.Alone, "node-beam (N)", button) != (views.Skeleton == DebugViews.SkeletonMode.Alone))
                    views.ToggleSkeleton(false);
                if (GUILayout.Toggle(views.Skeleton == DebugViews.SkeletonMode.Overlay, "overlay (Shift+N)", button) != (views.Skeleton == DebugViews.SkeletonMode.Overlay))
                    views.ToggleSkeleton(true);
                if (GUILayout.Toggle(views.Stress, "stress (H)", button) != views.Stress)
                    views.ToggleStress();
                if (GUILayout.Toggle(views.Deformation, "deformation (Shift+H)", button) != views.Deformation)
                    views.ToggleDeformation();
                GUILayout.EndHorizontal();
            }

            if (controls.live != null)
            {
                GUILayout.Space(8);
                GUILayout.Label("<b>Driver aids</b>", label);
                GUILayout.BeginHorizontal();
                controls.live.abs = GUILayout.Toggle(controls.live.abs, "ABS (F7)", button);
                controls.live.tc = GUILayout.Toggle(controls.live.tc, "traction control (F8)", button);
                GUILayout.EndHorizontal();
            }

            if (replay != null)
            {
                GUILayout.Space(8);
                GUILayout.Label("<b>Recording</b>  (" + GameSettings.RecordingsPath + ")", label);
                GUILayout.BeginHorizontal();
                if (GUILayout.Button(replay.State == ReplayController.Mode.Recording ? "Stop recording (F5)" : "Record (F5)", button)) { replay.ToggleRecording(); Close(); }
                if (GUILayout.Button(replay.State == ReplayController.Mode.Replaying ? "Stop replay (F6)" : "Replay last (F6)", button)) { replay.ToggleReplay(); Close(); }
                GUILayout.EndHorizontal();
                foreach (var f in files)
                {
                    GUILayout.BeginHorizontal();
                    GUILayout.Label(Path.GetFileName(f), label, GUILayout.Width(300));
                    if (GUILayout.Button("replay", button))
                    {
                        try
                        {
                            replay.StartReplay(InputRecording.Read(f));
                        }
                        catch (Exception e)
                        {
                            controls.Say("cannot read " + Path.GetFileName(f) + ": " + e.Message);
                        }
                        Close();
                    }
                    GUILayout.EndHorizontal();
                }
            }

            GUILayout.Space(8);
            GUILayout.Label("<b>Settings</b>  " + GameSettings.FilePath, label);
            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Save current settings", button))
            {
                var s = GameSettings.Current;
                if (controls.live != null)
                {
                    s.abs = controls.live.abs;
                    s.tractionControl = controls.live.tc;
                }
                if (controls.hud != null)
                    s.hud = controls.hud.visible;
                s.Save();
                controls.Say("settings saved");
            }
            if (GUILayout.Button("Reload params.json (F9)", button)) { controls.ReloadParams(); Close(); }
            if (GUILayout.Button("Quit", button))
                Application.Quit();
            GUILayout.EndHorizontal();
            GUILayout.Label("Keys: W/S throttle, brake (reverse at a stop), A/D steer, Space handbrake, Q/E gears, C camera, T slow motion, " +
                            "N / H views, P pause, Shift+P step, F5 / F6 record / replay, F9 reload params, F12 screenshot. Details: docs/controls.md.", label);
            GUILayout.EndScrollView();
            GUILayout.EndArea();
        }
    }
}
