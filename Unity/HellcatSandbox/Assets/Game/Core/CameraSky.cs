using UnityEngine;

namespace Hellcat.Game.Core
{
    /// <summary>
    /// How every game camera clears (P7): to the scene's sky when it has one (the procedural sky of the game scenes, which
    /// the reflection probe and the glass reflect), else to the flat sky colour of the earlier phases.
    /// </summary>
    public static class CameraSky
    {
        public static readonly Color Fallback = new Color(0.62f, 0.68f, 0.76f);

        public static void Apply(Camera c)
        {
            if (c == null)
                return;
            if (RenderSettings.skybox != null)
            {
                c.clearFlags = CameraClearFlags.Skybox;
            }
            else
            {
                c.clearFlags = CameraClearFlags.SolidColor;
                c.backgroundColor = Fallback;
            }
        }
    }
}
