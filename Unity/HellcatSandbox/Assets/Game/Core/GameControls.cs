using System;
using System.IO;
using Hellcat.Game.Cameras;
using Hellcat.Game.Input;
using Hellcat.Game.Views;
using Hellcat.Game.World;
using Hellcat.Sim;
using Hellcat.Sim.Validation;
using Unity.Mathematics;
using UnityEngine;
using UnityEngine.InputSystem;

namespace Hellcat.Game.Core
{
    /// <summary>
    /// Sandbox keys (brief 4.12, docs/controls.md): R reset to the last safe position (fresh car), Shift+R repair in place,
    /// Ctrl+R reset the map's debris too,
    /// C camera, T slow motion, N / Shift+N node-beam view / overlay, H / Shift+H stress / deformation heat-map, P pause,
    /// Shift+P step one frame, F5 / F6 record / replay, F7 / F8 ABS / traction control, F9 reload params.json, F1 HUD,
    /// F12 screenshot, Esc menu.
    /// Gamepad: Y camera, X reset, Start menu, Back slow motion. Tracks the last safe pose: every 0.25 s of simulated time
    /// while the car is upright, has not broken a beam for a second and stays at least 0.6 m from every obstacle (the
    /// ground plane excepted).
    /// </summary>
    [DefaultExecutionOrder(-300)]   // before the inputs and the runner: a reset applies to this frame's steps
    public class GameControls : MonoBehaviour
    {
        public SimRunner runner;
        public CameraRig cameraRig;
        public DebugViews debugViews;
        public ReplayController replay;
        public LiveDriverInput live;
        public ApproachHoldSource approach;
        [Tooltip("Teleports hold the speed on the lane until just before the obstacle (D-080)")]
        public bool holdApproachSpeed = true;
        public UI.Hud hud;
        public PauseMenu menu;
        [Tooltip("Substeps per Shift+P step (1/60 s)")]
        public int stepSubsteps = 33;
        public float safeClearance = 0.6f;

        public string Message { get; private set; } = "";
        public float MessageTime { get; private set; } = -100f;
        public bool Abs => live == null || live.abs;
        public bool Tc => live == null || live.tc;
        public Vector3 SafePosition => safePos;
        public float SafeAge => (float)(runner.SimTime - safeTime);

        CarProbe probe;
        PropField props;
        Vector3 safePos;
        Quaternion safeRot = Quaternion.identity;
        double safeTime, nextSafeCheck, lastDamageTime;
        int lastBroken;
        GameSettings settings;

        void Start()
        {
            settings = GameSettings.Current;
            settings.Apply();
            if (live != null)
            {
                live.abs = settings.abs;
                live.tc = settings.tractionControl;
            }
            if (hud != null)
                hud.visible = settings.hud;
            if (runner != null && runner.World != null)
            {
                runner.maxSubstepsPerFrame = settings.maxSubstepsPerFrame;
                probe = new CarProbe(runner.World, runner.VehicleBody);
                safePos = runner.spawnPoint ? runner.spawnPoint.position : Vector3.zero;
                safeRot = runner.spawnPoint ? runner.spawnPoint.rotation : Quaternion.identity;
                runner.Respawned += OnRespawned;
                runner.Rebuilt += OnRebuilt;
            }
            props = FindFirstObjectByType<PropField>();
        }

        void OnDestroy()
        {
            if (!runner) return;
            runner.Respawned -= OnRespawned;
            runner.Rebuilt -= OnRebuilt;
        }

        void OnRebuilt() => probe = new CarProbe(runner.World, runner.VehicleBody);

        /// <summary>F9: params.json (and geometry.json) read again, the world rebuilt, a fresh car where this one is.</summary>
        public void ReloadParams()
        {
            replay?.Interrupt();
            var rot = probe.Pose(out double3 origin);
            var q = YawOf(rot);
            var p = ClearPose(new Vector3((float)origin.x, (float)origin.y, (float)origin.z), q);
            var sw = System.Diagnostics.Stopwatch.StartNew();
            runner.ReloadVehicleData(p, q);
            Say($"params.json reloaded, world rebuilt in {sw.Elapsed.TotalSeconds:F1} s");
        }

        public void Say(string msg)
        {
            Message = msg;
            MessageTime = Time.unscaledTime;
            Debug.Log("[Controls] " + msg);
        }

        static bool Down(Keyboard kb, Key k) => kb != null && kb[k].wasPressedThisFrame;

        void Update()
        {
            if (runner == null || runner.World == null)
                return;
            var kb = Keyboard.current;
            var pad = Gamepad.current;
            bool shift = kb != null && (kb.leftShiftKey.isPressed || kb.rightShiftKey.isPressed);

            if (Down(kb, Key.Escape) || (pad != null && pad.startButton.wasPressedThisFrame))
                menu?.Toggle();
            if (menu != null && menu.Open)
                return;   // the menu takes the keys (and pauses)

            bool ctrl = kb != null && (kb.leftCtrlKey.isPressed || kb.rightCtrlKey.isPressed);
            if (Down(kb, Key.R) || (pad != null && pad.buttonWest.wasPressedThisFrame))
            {
                if (ctrl) ResetMap();
                else if (shift) RepairInPlace();
                else ResetToSafe();
            }
            if (Down(kb, Key.C) || (pad != null && pad.buttonNorth.wasPressedThisFrame))
            {
                cameraRig?.Cycle();
                Say($"camera: {cameraRig?.ModeName}");
            }
            if (Down(kb, Key.T) || (pad != null && pad.selectButton.wasPressedThisFrame))
                ToggleSlowMotion();
            if (Down(kb, Key.N) && debugViews != null)
                debugViews.ToggleSkeleton(shift);
            if (Down(kb, Key.H) && debugViews != null)
            {
                if (shift) debugViews.ToggleDeformation();
                else debugViews.ToggleStress();
            }
            if (Down(kb, Key.P))
            {
                if (shift)
                {
                    if (!runner.paused) runner.paused = true;
                    runner.PendingSteps += stepSubsteps;
                }
                else
                {
                    runner.paused = !runner.paused;
                    runner.PendingSteps = 0;
                    Say(runner.paused ? "paused" : "running");
                }
            }
            if (Down(kb, Key.F5))
                replay?.ToggleRecording();
            if (Down(kb, Key.F6))
                replay?.ToggleReplay();
            if (Down(kb, Key.F7) && live != null)
            {
                live.abs = !live.abs;
                Say($"ABS {(live.abs ? "on" : "off")}");
            }
            if (Down(kb, Key.F8) && live != null)
            {
                live.tc = !live.tc;
                Say($"traction control {(live.tc ? "on" : "off")}");
            }
            if (Down(kb, Key.F9))
                ReloadParams();
            if (Down(kb, Key.F1) && hud != null)
                hud.visible = !hud.visible;
            if (Down(kb, Key.F12))
                Screenshot();

            TrackSafePose();
        }

        public void ToggleSlowMotion()
        {
            runner.timeScale = Mathf.Approximately(runner.timeScale, 1f) ? settings.slowMotionScale : 1f;
            Say(Mathf.Approximately(runner.timeScale, 1f) ? "real time" : $"slow motion x{runner.timeScale:0.##}");
        }

        void OnRespawned()
        {
            approach?.Stop("respawn");
            lastBroken = runner.World.Metrics(runner.VehicleBody, false).brokenBeams;
            lastDamageTime = runner.SimTime;
        }

        // ------------------------------------------------------------------ safe pose, reset, repair, teleport

        void TrackSafePose()
        {
            if (runner.SimTime < nextSafeCheck || (replay != null && replay.State == ReplayController.Mode.Replaying))
                return;
            nextSafeCheck = runner.SimTime + 0.25;
            var w = runner.World;
            var m = w.Metrics(runner.VehicleBody, false);
            if (m.brokenBeams != lastBroken)
            {
                lastBroken = m.brokenBeams;
                lastDamageTime = runner.SimTime;
                return;
            }
            if (runner.SimTime - lastDamageTime < 1.0 || m.nonFinite > 0)
                return;
            var f = probe.Frame();
            if (f.up.y < 0.95)
                return;
            var b = w.bodies[runner.VehicleBody];
            if (MinObstacleDistance(i => w.pos[i], b.nodeStart, b.nodeCount) < safeClearance)
                return;
            var rot = probe.Pose(out double3 origin);
            safePos = new Vector3((float)origin.x, (float)origin.y, (float)origin.z);
            safeRot = YawOf(rot);
            safeTime = runner.SimTime;
        }

        static Quaternion YawOf(double3x3 rot)
        {
            double3 fwd = math.mul(rot, new double3(0, 0, 1));
            return Quaternion.LookRotation(new Vector3((float)fwd.x, 0f, (float)fwd.z).normalized, Vector3.up);
        }

        /// <summary>Smallest distance of the given nodes from any static primitive except planes (the ground).</summary>
        float MinObstacleDistance(Func<int, float3> position, int start, int count)
        {
            var w = runner.World;
            float best = float.MaxValue;
            float3 c = position(start);
            for (int p = 0; p < w.prims.Length; p++)
            {
                var prim = w.prims[p];
                if (prim.type == PrimType.Plane)
                    continue;
                // far primitives are skipped by their bounds
                float3 lo = prim.aabbMin - 8f, hi = prim.aabbMax + 8f;
                if (math.any(c < lo) || math.any(c > hi))
                    continue;
                for (int i = start; i < start + count; i++)
                    best = math.min(best, StaticSdf.Distance(prim, w.planes, position(i), out _));
            }
            return best;
        }

        /// <summary>R: a fresh car at rest at the last safe pose.</summary>
        public void ResetToSafe()
        {
            replay?.Interrupt();
            runner.RespawnSettled(safePos, safeRot, 0f);
            Say($"reset to the last safe position ({SafeAgeText()})");
        }

        /// <summary>Ctrl+R: the debris back where it started and the car to the last safe position.</summary>
        public void ResetMap()
        {
            props?.ResetAll();
            ResetToSafe();
            Say("map reset: debris back in place, car at the last safe position");
        }

        string SafeAgeText() => safeTime > 0 ? $"{runner.SimTime - safeTime:F1} s of driving ago" : "spawn";

        /// <summary>Shift+R: a fresh car where this one is, upright, at rest; moved back out of an obstacle if needed.</summary>
        public void RepairInPlace()
        {
            replay?.Interrupt();
            var rot = probe.Pose(out double3 origin);
            var q = YawOf(rot);
            var p = new Vector3((float)origin.x, (float)origin.y, (float)origin.z);
            var clear = ClearPose(p, q);
            runner.RespawnSettled(clear, q, 0f);
            Say(Vector3.Distance(clear, p) > 0.01f ? $"repaired, moved {Vector3.Distance(clear, p):F1} m clear of the obstacle" : "repaired");
        }

        /// <summary>The pose itself if the undeformed car fits there, else the nearest along its heading (back first).</summary>
        Vector3 ClearPose(Vector3 p, Quaternion q)
        {
            var def = runner.World.bodies[runner.VehicleBody].def;
            var fwd = q * Vector3.forward;
            for (int k = 0; k <= 40; k++)
            {
                float d = k <= 20 ? -0.25f * k : 0.25f * (k - 20);   // back out first, then forward
                var cand = p + fwd * d;
                if (MinObstacleDistance(i => (float3)(cand + q * new Vector3(def.nodes[i].p[0], def.nodes[i].p[1], def.nodes[i].p[2])), 0, def.nodes.Length) > 0.05f)
                    return cand;
            }
            return p;
        }

        /// <summary>Teleport to a spawn point, settled, launched at the given speed along its heading; with
        /// <see cref="holdApproachSpeed"/> the speed is held on the lane until just before the obstacle (D-080).</summary>
        public void Teleport(SpawnPoint sp, float kmh)
        {
            replay?.Interrupt();
            var fwd = Vector3.ProjectOnPlane(sp.transform.forward, Vector3.up).normalized;
            runner.RespawnSettled(sp.transform.position, Quaternion.LookRotation(fwd, Vector3.up), kmh / 3.6f);
            safePos = sp.transform.position;
            safeRot = sp.transform.rotation;
            safeTime = runner.SimTime;
            if (approach != null && holdApproachSpeed && kmh > 0f)
                approach.Begin(sp.transform.position, fwd, kmh / 3.6f, sp.approachDistance > 0f ? sp.approachDistance : 80f, !sp.holdThrough);
            Say($"{sp.label} at {kmh:F0} km/h" + (approach != null && approach.Holding ? " (speed held to the obstacle)" : ""));
        }

        public void Screenshot()
        {
            try
            {
                Directory.CreateDirectory(GameSettings.RecordingsPath);
                string path = Path.Combine(GameSettings.RecordingsPath, $"shot_{DateTime.Now:yyyyMMdd_HHmmss}.png");
                ScreenCapture.CaptureScreenshot(path, Math.Max(1, settings.screenshotSuperSize));
                Say("screenshot " + Path.GetFileName(path));
            }
            catch (Exception e)
            {
                Say("screenshot failed: " + e.Message);
            }
        }
    }
}
