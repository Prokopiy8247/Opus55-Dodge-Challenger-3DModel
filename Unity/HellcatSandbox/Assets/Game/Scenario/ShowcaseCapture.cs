using System;
using System.Collections;
using System.Globalization;
using System.IO;
using System.Linq;
using Hellcat.Game.Cameras;
using Hellcat.Game.Core;
using Hellcat.Game.Input;
using Hellcat.Game.UI;
using Hellcat.Game.Views;
using Hellcat.Game.World;
using Hellcat.Sim;
using Unity.Mathematics;
using UnityEngine;

namespace Hellcat.Game.Scenario
{
    /// <summary>
    /// The P4b short capture (<c>-scenario showcase</c>): a scripted tour of the game layer written frame by frame (the window
    /// with HUD and captions, JPG at 60 fps of video; the simulation advances exactly 1/60 s per frame, or a tenth of that
    /// in slow motion, so the frame rate of the machine does not matter). Chase camera on the drive loop, cockpit with the
    /// live gauges and mirrors, bumper camera, node-beam overlay with the stress map through a curve, a teleport to the O1
    /// wall at 64 km/h with the last second recorded (F5) and the impact in slow motion from the side, the deformation
    /// heat-map around the wreck, and the recording replayed (F6) twice: with the beam stresses over the paint, and from
    /// the driver's seat. Options: -captureOut dir (frames go to dir/frames).
    /// </summary>
    public class ShowcaseCapture : MonoBehaviour
    {
        public SimRunner runner;
        public RobotDriverSource robot;
        public CameraRig cameras;
        public DebugViews views;
        public ReplayController replay;
        public GameControls controls;
        public Hud hud;
        public Transform start;
        [Tooltip("The drive loop (DriveLoop): straights, curve radius and speeds; the P4b plane has room for 300 m / 60 m")]
        public double straight = 300.0, radius = 60.0, straightKmh = 160.0, curveKmh = 75.0;

        string outDir, frames;
        int frame, pattern;
        float rate = 1f;            // simulated seconds per video second
        string caption = "";
        GUIStyle captionStyle;
        Texture2D white;
        readonly CultureInfo ic = CultureInfo.InvariantCulture;

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
            if (Arg("-scenario", "") != "showcase")
            {
                enabled = false;
                return;
            }
            string root = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", ".."));
            outDir = Arg("-captureOut", Path.Combine(root, "docs", "p4b", "capture"));
            frames = Path.Combine(outDir, "frames");
            Directory.CreateDirectory(frames);
            foreach (var f in Directory.GetFiles(frames, "*.jpg"))
                File.Delete(f);
            StartCoroutine(Run());
        }

        /// <summary>Substeps of the next frame: 1/60 s of simulated time times the rate, the fractions carried over.</summary>
        double carry;
        int NextSubsteps()
        {
            double want = rate / 60.0 / runner.World.dt + carry;
            int n = (int)math.floor(want + 1e-9);
            carry = want - n;
            return n;
        }

        IEnumerator Frames(int count, Action<int> each = null)
        {
            var eof = new WaitForEndOfFrame();
            for (int i = 0; i < count; i++)
            {
                pattern = NextSubsteps();
                yield return null;          // this frame steps `pattern` substeps
                each?.Invoke(i);
                yield return eof;
                var tex = ScreenCapture.CaptureScreenshotAsTexture();
                File.WriteAllBytes(Path.Combine(frames, $"f_{frame++:D5}.jpg"), tex.EncodeToJPG(93));
                Destroy(tex);
            }
        }

        IEnumerator Run()
        {
            if (hud) hud.visible = true;
            runner.SubstepOverride = () => pattern;
            pattern = 0;
            runner.RespawnSettled(start.position, start.rotation, 0f);
            for (int i = 0; i < 30; i++) yield return null;

            // A: chase on the loop
            robot.Begin(DriveLoop.Path(start, straight, radius), (t, arc) => DriveLoop.TargetSpeed(arc, straight, radius, straightKmh, curveKmh));
            cameras.mode = CameraMode.Chase;
            caption = $"Chase camera - Hellcat Widebody on the 2 kHz soft-body solver ({runner.World.bodies[runner.VehicleBody].nodeCount} nodes, {runner.World.bodies[runner.VehicleBody].beamCount} beams)";
            yield return Frames(360);
            // B: cockpit
            cameras.mode = CameraMode.Cockpit;
            caption = "Cockpit camera - tach, speedometer, steering wheel and pedals driven by the simulation; live mirrors";
            yield return Frames(360);
            // C: bumper
            cameras.mode = CameraMode.Bumper;
            caption = "Bumper camera";
            yield return Frames(180);
            // D: overlay + stress through the curve
            cameras.mode = CameraMode.Chase;
            views.ToggleSkeleton(true);
            views.ToggleStress();
            caption = "Node-beam overlay (Shift+N) with the beam stress heat-map (H) - cornering";
            yield return Frames(300);
            views.ToggleStress();
            views.ToggleSkeleton(true);
            robot.End();

            // E: teleport to the wall at 64 km/h; the last second before the wall recorded; the impact in slow motion
            var wallSpawn = FindObjectsByType<SpawnPoint>(FindObjectsInactive.Exclude).First(s => s.label.StartsWith("O1"));
            controls.Teleport(wallSpawn, 64f);
            runner.SubstepOverride = () => pattern;
            cameras.mode = CameraMode.Chase;
            caption = "Teleport to obstacle O1 at 64 km/h (pause menu)";
            float wallZ = wallSpawn.transform.position.z + wallSpawn.approachDistance;
            var b = runner.World.bodies[runner.VehicleBody];
            Func<float> front = () =>
            {
                float z = float.MinValue;
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++) z = math.max(z, runner.World.pos[i].z);
                return z;
            };
            int guard = 0;
            while (front() < wallZ - 18f && guard++ < 600)
                yield return Frames(1);
            replay.StartRecording("P4b showcase: O1 wall at 64 km/h");
            caption = "Recording (F5)";
            guard = 0;
            while (front() < wallZ - 2.2f && guard++ < 600)
                yield return Frames(1);
            var wallX = wallSpawn.transform.position.x;
            var side = new Vector3(wallX + 8.5f, 1.3f, wallZ - 2.6f);
            var sideLook = new Vector3(wallX, 0.7f, wallZ - 2.4f);
            cameras.SetFreePose(side, sideLook);
            rate = 0.1f;
            caption = "Impact at 64 km/h, slow motion x0.1 (T)";
            yield return Frames(260);
            rate = 1f;
            caption = "Real time";
            yield return Frames(60);
            var rec = replay.StopRecording(true, Path.Combine(outDir, "showcase_crash.hrec"));

            // G: deformation heat-map, orbit from the right side round to the rear quarter (the wall is ahead of the car)
            views.ToggleDeformation();
            caption = "Deformation heat-map (Shift+H): distance from the undeformed shape, red = 30 cm";
            var com = runner.World.Metrics(runner.VehicleBody, false).centerOfMass;
            yield return Frames(300, i =>
            {
                float a = math.radians(88f - 68f * i / 299f);
                var c = new Vector3(com.x, 0.6f, com.z);
                cameras.SetFreePose(c + new Vector3(math.sin(a) * 6.5f, 2.2f, -math.cos(a) * 6.5f), c + new Vector3(0f, 0f, 1.0f));
            });
            views.ToggleDeformation();

            if (rec != null)
            {
                // H: replay with the beam stresses over the paint, from the side
                replay.StartReplay(rec);
                runner.SubstepOverride = () => pattern;
                cameras.SetFreePose(side, sideLook);
                views.ToggleSkeleton(true);
                views.ToggleStress();
                caption = "Replay (F6), bit-identical - beam stress over the paint (Shift+N, H)";
                guard = 0;
                while (front() < wallZ - 2.2f && guard++ < 600)
                    yield return Frames(1);
                rate = 0.1f;
                caption = "Replay x0.1 - beam stress: force / deform threshold, blue 0, yellow 0.5, red 1";
                yield return Frames(240);
                rate = 1f;
                replay.StopReplay("capture: next replay");
                views.ToggleStress();
                views.ToggleSkeleton(true);

                // I: replay from the driver's seat
                replay.StartReplay(rec);
                runner.SubstepOverride = () => pattern;
                cameras.mode = CameraMode.Cockpit;
                caption = "Replay (F6) from the driver's seat";
                guard = 0;
                while (front() < wallZ - 3.0f && guard++ < 600)
                    yield return Frames(1);
                rate = 0.12f;
                caption = "Replay from the driver's seat, slow motion";
                yield return Frames(280);
                rate = 1f;
                yield return Frames(45);
                replay.StopReplay("capture done");
            }
            runner.SubstepOverride = null;
            File.WriteAllText(Path.Combine(outDir, "showcase.txt"),
                $"frames {frame}\nfps 60\nwindow {Screen.width}x{Screen.height}\ntime_utc {DateTime.UtcNow:yyyy-MM-ddTHH:mm:ssZ}\n");
            Debug.Log($"[Showcase] {frame} frames in {frames}");
            yield return null;
            Application.Quit(0);
#if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
#endif
        }

        void OnGUI()
        {
            if (string.IsNullOrEmpty(caption))
                return;
            captionStyle ??= new GUIStyle(GUI.skin.label) { fontSize = 24, alignment = TextAnchor.MiddleCenter, richText = true };
            if (white == null)
            {
                white = new Texture2D(1, 1);
                white.SetPixel(0, 0, Color.white);
                white.Apply();
            }
            var size = captionStyle.CalcSize(new GUIContent(caption));
            var r = new Rect(Screen.width * 0.5f - size.x * 0.5f - 16, Screen.height - 90, size.x + 32, size.y + 16);
            GUI.color = new Color(0f, 0f, 0f, 0.6f);
            GUI.DrawTexture(r, white);
            GUI.color = Color.white;
            GUI.Label(r, caption, captionStyle);
        }
    }
}
