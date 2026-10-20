using System;
using UnityEngine;
using UnityEngine.InputSystem;

namespace Hellcat.Game.UI
{
    /// <summary>
    /// The minimal start screen of the standalone sandbox (brief: "a minimal start / pause screen", P7): the title, the
    /// main keys and "press any key", over the car waiting at the start. Any key, mouse button or gamepad button closes it.
    /// Not shown for command-line scenarios (-scenario, -replay) or with -noStartScreen.
    /// </summary>
    public class StartScreen : MonoBehaviour
    {
        public Hud hud;
        public bool Visible { get; private set; }

        GUIStyle title, sub, body, keyStyle, hint;
        Texture2D panel;
        bool hudWasVisible;

        static readonly (string key, string what)[] Keys =
        {
            ("W / S", "throttle / brake (hold S at rest: reverse)"),
            ("A / D", "steer"),
            ("Space", "handbrake"),
            ("Q / E", "gear down / up"),
            ("C", "camera: chase, bumper, cockpit, free"),
            ("R / Shift+R", "reset to the last safe spot / repair here"),
            ("T", "slow motion"),
            ("N / H", "node-beam view / stress heat-map"),
            ("Shift+H", "deformation heat-map"),
            ("P", "pause (Shift+P: step)"),
            ("F5 / F6", "record / replay"),
            ("Esc", "menu: teleport to an obstacle at a chosen speed"),
        };

        static bool HasArg(string name) =>
            Array.Exists(Environment.GetCommandLineArgs(), a => string.Equals(a, name, StringComparison.OrdinalIgnoreCase));

        void Start()
        {
            Visible = !HasArg("-scenario") && !HasArg("-replay") && !HasArg("-noStartScreen");
            if (Visible && hud != null)
            {
                hudWasVisible = hud.visible;
                hud.visible = false;
            }
        }

        void Update()
        {
            if (!Visible)
                return;
            bool any = (Keyboard.current != null && Keyboard.current.anyKey.wasPressedThisFrame) ||
                       (Mouse.current != null && (Mouse.current.leftButton.wasPressedThisFrame || Mouse.current.rightButton.wasPressedThisFrame));
            var pad = Gamepad.current;
            if (pad != null)
                any |= pad.buttonSouth.wasPressedThisFrame || pad.buttonEast.wasPressedThisFrame || pad.buttonWest.wasPressedThisFrame ||
                       pad.buttonNorth.wasPressedThisFrame || pad.startButton.wasPressedThisFrame || pad.rightTrigger.wasPressedThisFrame;
            if (!any)
                return;
            Visible = false;
            if (hud != null)
                hud.visible = hudWasVisible;
        }

        void Styles()
        {
            if (title != null)
                return;
            float s = Mathf.Max(1f, Screen.height / 1080f);
            title = new GUIStyle(GUI.skin.label) { fontSize = Mathf.RoundToInt(46 * s), fontStyle = FontStyle.Bold, alignment = TextAnchor.MiddleCenter };
            title.normal.textColor = Color.white;
            sub = new GUIStyle(GUI.skin.label) { fontSize = Mathf.RoundToInt(20 * s), alignment = TextAnchor.MiddleCenter, wordWrap = true };
            sub.normal.textColor = new Color(0.82f, 0.86f, 0.92f);
            keyStyle = new GUIStyle(GUI.skin.label) { fontSize = Mathf.RoundToInt(19 * s), fontStyle = FontStyle.Bold, alignment = TextAnchor.MiddleRight };
            keyStyle.normal.textColor = new Color(1f, 0.82f, 0.35f);
            body = new GUIStyle(GUI.skin.label) { fontSize = Mathf.RoundToInt(19 * s), alignment = TextAnchor.MiddleLeft };
            body.normal.textColor = Color.white;
            hint = new GUIStyle(GUI.skin.label) { fontSize = Mathf.RoundToInt(24 * s), fontStyle = FontStyle.Bold, alignment = TextAnchor.MiddleCenter };
            hint.normal.textColor = Color.white;
            panel = new Texture2D(1, 1);
            panel.SetPixel(0, 0, new Color(0.04f, 0.05f, 0.07f, 0.82f));
            panel.Apply();
        }

        void OnGUI()
        {
            if (!Visible)
                return;
            Styles();
            float s = Mathf.Max(1f, Screen.height / 1080f);
            float w = 900f * s, rowH = 30f * s, h = (250f + Keys.Length * 30f) * s;
            var r = new Rect((Screen.width - w) * 0.5f, (Screen.height - h) * 0.5f, w, h);
            GUI.DrawTexture(r, panel);
            float y = r.y + 24f * s;
            GUI.Label(new Rect(r.x, y, w, 56f * s), "HELLCAT SANDBOX", title);
            y += 60f * s;
            GUI.Label(new Rect(r.x + 40f * s, y, w - 80f * s, 50f * s),
                "Dodge Challenger SRT Hellcat Widebody on a 2 kHz node-beam soft-body solver - drive it into the test map's obstacles", sub);
            y += 62f * s;
            foreach (var (key, what) in Keys)
            {
                GUI.Label(new Rect(r.x, y, w * 0.36f, rowH), key, keyStyle);
                GUI.Label(new Rect(r.x + w * 0.39f, y, w * 0.6f, rowH), what, body);
                y += rowH;
            }
            y += 18f * s;
            float pulse = 0.65f + 0.35f * Mathf.Sin(Time.unscaledTime * 3f);
            GUI.color = new Color(1f, 1f, 1f, pulse);
            GUI.Label(new Rect(r.x, y, w, 40f * s), "Press any key or gamepad button to drive", hint);
            GUI.color = Color.white;
        }
    }
}
