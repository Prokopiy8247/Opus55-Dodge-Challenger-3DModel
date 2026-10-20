using System.IO;
using Hellcat.Game.Core;
using UnityEditor;
using UnityEngine;

namespace Hellcat.EditorTools.Car
{
    /// <summary>
    /// P4 probes for the car import: where the vertices of an exported FBX land in Unity against the skeleton frame.
    /// Batch: -executeMethod Hellcat.EditorTools.Car.CarImportProbe.ProbeAxes
    /// </summary>
    public static class CarImportProbe
    {
        public const string ExportFolder = "Assets/Game/Vehicles/Hellcat/Export";

        [System.Serializable] class Obj { public string name; public float[] bbox_unity_min, bbox_unity_max; }

        public static void ProbeAxes()
        {
            int code = 1;
            try
            {
                AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
                var json = File.ReadAllText(Path.Combine(ExportFolder, "parts.json"));
                foreach (var file in new[] { "mirror_L.fbx", "wheel_FR.fbx" })
                {
                    string path = $"{ExportFolder}/{file}";
                    var imp = AssetImporter.GetAtPath(path) as ModelImporter;
                    Debug.Log($"[Probe] {path}: importer {(imp != null)}, globalScale {imp?.globalScale}, useFileScale {imp?.useFileScale}, " +
                              $"fileScale {imp?.fileScale}, bakeAxisConversion {imp?.bakeAxisConversion}");
                    var go = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                    if (go == null) { Debug.LogError($"[Probe] cannot load {path}"); continue; }
                    Debug.Log($"[Probe] root {go.name}: pos {go.transform.position} rot {go.transform.rotation.eulerAngles} scale {go.transform.localScale}");
                    foreach (var mf in go.GetComponentsInChildren<MeshFilter>(true))
                    {
                        var m = mf.sharedMesh;
                        var t = mf.transform;
                        Vector3 lo = Vector3.positiveInfinity, hi = Vector3.negativeInfinity;
                        foreach (var v in m.vertices)
                        {
                            var w = go.transform.InverseTransformPoint(t.TransformPoint(v));
                            lo = Vector3.Min(lo, w);
                            hi = Vector3.Max(hi, w);
                        }
                        int i = json.IndexOf($"\"name\": \"{t.name}\"");
                        string bb = i >= 0 ? json.Substring(json.IndexOf("\"bbox_unity\"", i), 200).Replace("\n", "").Replace(" ", "") : "?";
                        Debug.Log($"[Probe]   {t.name}: {m.vertexCount} verts, local pos {t.localPosition} rot {t.localRotation.eulerAngles} scale {t.localScale}; " +
                                  $"bounds in the root frame min {lo.x:F4},{lo.y:F4},{lo.z:F4} max {hi.x:F4},{hi.y:F4},{hi.z:F4}; expected {bb}");
                    }
                }
                code = 0;
            }
            catch (System.Exception e)
            {
                Debug.LogException(e);
            }
            EditorApplication.Exit(code);
        }
    }
}
