using Hellcat.Game.Cameras;
using Hellcat.Game.Core;
using Hellcat.Game.Views;
using Hellcat.Sim;
using Unity.Mathematics;
using UnityEngine;

namespace Hellcat.Game.UI
{
    /// <summary>
    /// Driving HUD (brief 4.12, 16): speed, rpm, gear, pedals and steering, G-force, broken beams, energy bars (kinetic,
    /// elastic, plastic work, lost to breaking and damping), physics Hz / fps, quality mode, and the sandbox state (camera,
    /// time scale, pause, recording / replay, debug views, ABS / TC) with short messages. F1 hides it.
    /// </summary>
    public class Hud : MonoBehaviour
    {
        public SimRunner runner;
        public CameraRig cameras;
        public ReplayController replay;
        public DebugViews views;
        public GameControls controls;
        public Input.ApproachHoldSource approach;
        public bool visible = true;

        float fps, fpsTimer;
        int fpsFrames;
        float3 lastVel;
        float gLong, gLat;
        GUIStyle style, small, big;
        Texture2D white;

        // energies at a few Hz (the elastic sum walks every beam); the text at 10 Hz (fewer allocations, steadier frames)
        float energyTimer, textTimer;
        double eKin, eElastic, ePlastic, eLost, eRef = 1.0;
        string tSpeed = "", tPedals = "", tSteer = "", tDamage = "", tPerf = "", tQuality = "", tStatus = "", tMessage = "";
        string[] tBar = { "", "", "", "" };
        Vector2 statusSize, messageSize;

        public float Fps => fps;

        void Update()
        {
            fpsTimer += Time.unscaledDeltaTime;
            fpsFrames++;
            if (fpsTimer >= 0.5f)
            {
                fps = fpsFrames / fpsTimer;
                fpsTimer = 0f;
                fpsFrames = 0;
            }
            if (runner == null || runner.World == null || Time.deltaTime <= 0f)
                return;
            var st = runner.World.vehicleState[runner.VehicleIndex];
            float simDt = runner.LastSubsteps * runner.World.dt;
            if (simDt > 0f)
            {
                float3 a = (st.velocity - lastVel) / simDt;
                lastVel = st.velocity;
                float3 fwd = math.normalizesafe(st.forward);
                float3 right = math.normalizesafe(math.cross(new float3(0f, 1f, 0f), fwd));
                gLong = math.lerp(gLong, math.dot(a, fwd) / 9.81f, 0.15f);
                gLat = math.lerp(gLat, math.dot(a, right) / 9.81f, 0.15f);
            }
            energyTimer -= Time.unscaledDeltaTime;
            if (visible && energyTimer <= 0f)
            {
                energyTimer = 0.2f;
                var m = runner.World.Metrics(runner.VehicleBody, true);
                eKin = m.kinetic;
                eElastic = m.elastic + m.torsion + m.pressure;
                ePlastic = m.plastic;
                eLost = m.breaking + m.damping;
                eRef = math.max(eRef, math.max(math.max(eKin, eElastic), math.max(ePlastic, eLost)));
            }
            textTimer -= Time.unscaledDeltaTime;
            if (visible && textTimer <= 0f)
            {
                textTimer = 0.1f;
                BuildText();
            }
        }

        void BuildText()
        {
            var w = runner.World;
            var st = w.vehicleState[runner.VehicleIndex];
            var m = w.Metrics(runner.VehicleBody, false);
            var inp = runner.LastInput;
            string gear = st.gear < 0 ? "R" : st.gear == 0 ? "N" : st.gear >= 99 ? "D" : st.gear.ToString();
            tSpeed = $"<b>{math.abs(st.speed) * 3.6f:F0}</b> km/h   gear <b>{gear}</b>   {st.engineRpm:F0} rpm";
            tPedals = $"throttle {inp.throttle * 100f:F0} %  brake {inp.brake * 100f:F0} %  handbrake {inp.handbrake * 100f:F0} %";
            tSteer = $"steer {st.steer:+0.00;-0.00}   G long {gLong:+0.00;-0.00}  lat {gLat:+0.00;-0.00}";
            tDamage = $"broken beams <b>{m.brokenBeams}</b>   bent beams {m.plasticBeams}" +
                      (controls != null ? $"   ABS {(controls.Abs ? "on" : "off")}  TC {(controls.Tc ? "on" : "off")}" : "");
            tBar[0] = Kj(eKin); tBar[1] = Kj(eElastic); tBar[2] = Kj(ePlastic); tBar[3] = Kj(eLost);
            tPerf = $"physics {runner.PhysicsHz:F0} Hz  x{runner.RealTimeFactor:F2}   fps {fps:F0}   step {runner.LastStepMs:F2} ms / {runner.LastSubsteps}";
            tQuality = $"quality: full ({w.NodeCount} nodes, {w.BeamCount} beams, dt {w.dt * 1000f:F2} ms, {(w.UsesSingleThread ? "1 thread" : "Burst parallel")}" +
                       (w.HasSleepTail ? (w.TailAsleep ? ", debris asleep" : ", debris awake") : "") + ")" +
                       (runner.SlowDown ? "  <color=#ff4040><b>SLOW-DOWN</b></color>" : "");
            var line = new System.Text.StringBuilder();
            if (cameras != null) line.Append($"camera {cameras.ModeName}");
            if (runner.paused) line.Append("   <color=#ffd040><b>PAUSED</b></color> (P resume, Shift+P step)");
            else if (!Mathf.Approximately(runner.timeScale, 1f)) line.Append($"   <color=#80d0ff><b>slow motion x{runner.timeScale:0.##}</b></color>");
            if (replay != null && replay.State == ReplayController.Mode.Recording)
                line.Append($"   <color=#ff3030><b>REC {replay.Elapsed:F1} s</b></color>");
            if (replay != null && replay.State == ReplayController.Mode.Replaying)
                line.Append($"   <color=#40ff60><b>REPLAY {replay.Elapsed:F1} / {replay.Duration:F1} s</b></color>{(replay.Exact ? "" : " (per substep)")}");
            if (approach != null && approach.Holding)
                line.Append($"   <color=#ffd040>speed hold {approach.TargetSpeed * 3.6f:F0} km/h to the obstacle</color>");
            string v = views != null ? views.Describe() : "";
            if (v.Length > 0) line.Append("   ").Append(v);
            tStatus = line.ToString();
            string msg = "";
            float age = 99f;
            if (replay != null && Time.unscaledTime - replay.MessageTime < 4f) { msg = replay.Message; age = Time.unscaledTime - replay.MessageTime; }
            if (controls != null && Time.unscaledTime - controls.MessageTime < 4f && Time.unscaledTime - controls.MessageTime < age) msg = controls.Message;
            tMessage = msg;
            statusSize = messageSize = Vector2.zero;
        }

        static string Kj(double joules) => joules >= 1e4 ? $"{joules / 1000.0:F0} kJ" : $"{joules / 1000.0:F1} kJ";

        void OnGUI()
        {
            if (!visible || runner == null || runner.World == null)
                return;
            style ??= new GUIStyle(GUI.skin.label) { fontSize = 16, richText = true };
            small ??= new GUIStyle(GUI.skin.label) { fontSize = 13, richText = true };
            big ??= new GUIStyle(GUI.skin.label) { fontSize = 30, richText = true, fontStyle = FontStyle.Bold };
            if (white == null)
            {
                white = new Texture2D(1, 1);
                white.SetPixel(0, 0, Color.white);
                white.Apply();
            }
            if (tSpeed.Length == 0)
                BuildText();

            GUI.color = new Color(0f, 0f, 0f, 0.55f);
            GUI.DrawTexture(new Rect(10, 10, 400, 330), white);
            GUI.color = Color.white;
            GUILayout.BeginArea(new Rect(20, 14, 385, 325));
            GUILayout.Label(tSpeed, big);
            GUILayout.Label(tPedals, style);
            GUILayout.Label(tSteer, style);
            GUILayout.Label(tDamage, style);
            GUILayout.Space(4);
            Bar("kinetic", eKin, tBar[0], new Color(0.3f, 0.75f, 1f));
            Bar("elastic", eElastic, tBar[1], new Color(0.35f, 0.9f, 0.4f));
            Bar("plastic work", ePlastic, tBar[2], new Color(1f, 0.6f, 0.15f));
            Bar("broken + damped", eLost, tBar[3], new Color(1f, 0.3f, 0.3f));
            GUILayout.Space(4);
            GUILayout.Label(tPerf, small);
            GUILayout.Label(tQuality, small);
            GUILayout.EndArea();

            // sandbox state, top centre
            if (statusSize == Vector2.zero) statusSize = style.CalcSize(new GUIContent(tStatus));
            float x = Screen.width * 0.5f - statusSize.x * 0.5f;
            GUI.color = new Color(0f, 0f, 0f, 0.5f);
            GUI.DrawTexture(new Rect(x - 8, 8, statusSize.x + 16, statusSize.y + 6), white);
            GUI.color = Color.white;
            GUI.Label(new Rect(x, 10, statusSize.x + 4, statusSize.y + 4), tStatus, style);

            if (tMessage.Length > 0)
            {
                if (messageSize == Vector2.zero) messageSize = style.CalcSize(new GUIContent(tMessage));
                float mx = Screen.width * 0.5f - messageSize.x * 0.5f;
                GUI.color = new Color(0f, 0f, 0f, 0.6f);
                GUI.DrawTexture(new Rect(mx - 10, 44, messageSize.x + 20, messageSize.y + 8), white);
                GUI.color = Color.white;
                GUI.Label(new Rect(mx, 47, messageSize.x + 4, messageSize.y + 4), tMessage, style);
            }
            GUI.Label(new Rect(Screen.width - 260, Screen.height - 26, 255, 22), "F1 HUD  Esc menu  C camera  R reset", small);
        }

        void Bar(string label, double joules, string text, Color color)
        {
            var r = GUILayoutUtility.GetRect(320, 16);
            GUI.Label(new Rect(r.x, r.y - 2, 110, 18), label, small);
            float frac = (float)math.saturate(math.log10(1.0 + joules) / math.log10(1.0 + math.max(eRef, 1e5)));
            GUI.color = new Color(1f, 1f, 1f, 0.15f);
            GUI.DrawTexture(new Rect(r.x + 112, r.y + 3, 150, 10), white);
            GUI.color = color;
            GUI.DrawTexture(new Rect(r.x + 112, r.y + 3, 150 * frac, 10), white);
            GUI.color = Color.white;
            GUI.Label(new Rect(r.x + 268, r.y - 2, 90, 18), text, small);
        }
    }
}
