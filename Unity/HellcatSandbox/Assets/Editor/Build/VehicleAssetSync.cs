using System.IO;
using UnityEditor;
using UnityEngine;

namespace Hellcat.EditorTools.Build
{
    /// <summary>Copies sim/vehicle/&lt;name&gt;/*.json (project root) into StreamingAssets/Vehicles/&lt;name&gt;/.</summary>
    public static class VehicleAssetSync
    {
        public static string ProjectRoot => Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", ".."));

        [MenuItem("Tools/Hellcat/Sync Vehicle Data")]
        public static void SyncAll()
        {
            string src = Path.Combine(ProjectRoot, "sim", "vehicle");
            string dst = Path.Combine(Application.dataPath, "StreamingAssets", "Vehicles");
            int files = 0;
            foreach (var dir in Directory.GetDirectories(src))
            {
                string name = Path.GetFileName(dir);
                string target = Path.Combine(dst, name);
                Directory.CreateDirectory(target);
                foreach (var f in Directory.GetFiles(dir))
                {
                    string ext = Path.GetExtension(f).ToLowerInvariant();
                    if (ext != ".json" && ext != ".bin")
                        continue;
                    File.Copy(f, Path.Combine(target, Path.GetFileName(f)), true);
                    files++;
                }
            }
            AssetDatabase.Refresh();
            Debug.Log($"[VehicleAssetSync] copied {files} files from {src}");
        }
    }
}
