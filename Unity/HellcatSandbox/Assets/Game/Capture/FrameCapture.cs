using System.IO;
using UnityEngine;

namespace Hellcat.Game.Capture
{
    /// <summary>
    /// Renders a camera into an offscreen render texture and writes PNG/JPG files. Works in the
    /// editor, in standalone builds and in batch-mode players (no window needed). Used for
    /// screenshots, gates and video frame sequences (encoded with ffmpeg afterwards).
    /// </summary>
    public static class FrameCapture
    {
        static RenderTexture rt;
        static Texture2D readback;

        public static void Save(Camera cam, string path, int width, int height, bool jpg = false, int jpgQuality = 92)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            if (rt == null || rt.width != width || rt.height != height)
            {
                if (rt != null)
                    rt.Release();
                rt = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32) { antiAliasing = 4, name = "FrameCaptureRT" };
                rt.Create();
                readback = new Texture2D(width, height, TextureFormat.RGB24, false);
            }
            var prevTarget = cam.targetTexture;
            var prevActive = RenderTexture.active;
            cam.targetTexture = rt;
            cam.Render();
            RenderTexture.active = rt;
            readback.ReadPixels(new Rect(0, 0, width, height), 0, 0, false);
            readback.Apply(false);
            cam.targetTexture = prevTarget;
            RenderTexture.active = prevActive;
            File.WriteAllBytes(path, jpg ? readback.EncodeToJPG(jpgQuality) : readback.EncodeToPNG());
        }
    }
}
