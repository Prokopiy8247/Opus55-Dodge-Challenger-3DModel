using System.IO;
using UnityEditor;
using UnityEngine;

namespace Hellcat.EditorTools.Build
{
    /// <summary>Creates (or reuses) generated material and texture assets under Assets/Game/Generated.</summary>
    public static class EditorAssets
    {
        public const string Folder = "Assets/Game/Generated";

        static void EnsureFolder()
        {
            if (!AssetDatabase.IsValidFolder("Assets/Game"))
                AssetDatabase.CreateFolder("Assets", "Game");
            if (!AssetDatabase.IsValidFolder(Folder))
                AssetDatabase.CreateFolder("Assets/Game", "Generated");
        }

        public static Material Lit(string name, Color color, float smoothness = 0.5f, float metallic = 0f, Texture2D albedo = null, Vector2? tiling = null)
        {
            EnsureFolder();
            string path = $"{Folder}/{name}.mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                mat = new Material(UnityEngine.Shader.Find("Universal Render Pipeline/Lit"));
                AssetDatabase.CreateAsset(mat, path);
            }
            mat.SetColor("_BaseColor", color);
            mat.SetFloat("_Smoothness", smoothness);
            mat.SetFloat("_Metallic", metallic);
            if (albedo != null)
            {
                mat.SetTexture("_BaseMap", albedo);
                mat.SetTextureScale("_BaseMap", tiling ?? Vector2.one);
            }
            EditorUtility.SetDirty(mat);
            return mat;
        }

        public static Material ShaderMaterial(string name, string shaderName)
        {
            EnsureFolder();
            string path = $"{Folder}/{name}.mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                mat = new Material(UnityEngine.Shader.Find(shaderName));
                AssetDatabase.CreateAsset(mat, path);
            }
            return mat;
        }

        /// <summary>Asphalt texture for a 10 m x 10 m tile: thin lines every metre, thick border (10 m marks).</summary>
        public static Texture2D GroundGrid(string name = "Ground10m")
        {
            EnsureFolder();
            string path = $"{Folder}/{name}.png";
            var existing = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
            if (existing != null)
                return existing;
            const int size = 1024;
            var tex = new Texture2D(size, size, TextureFormat.RGB24, true);
            var rng = new System.Random(7);
            var px = new Color32[size * size];
            float perMetre = size / 10f;
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    float n = (float)rng.NextDouble();
                    byte g = (byte)(78 + n * 18);
                    var c = new Color32(g, g, (byte)(g + 2), 255);
                    float fx = x % perMetre, fy = y % perMetre;
                    bool thin = fx < 1.5f || fy < 1.5f;
                    bool thick = x < 6 || y < 6 || x >= size - 6 || y >= size - 6;
                    if (thick)
                        c = new Color32(220, 220, 210, 255);
                    else if (thin)
                        c = new Color32(118, 118, 116, 255);
                    px[y * size + x] = c;
                }
            tex.SetPixels32(px);
            tex.Apply();
            File.WriteAllBytes(Path.Combine(Path.GetDirectoryName(Application.dataPath), path), tex.EncodeToPNG());
            Object.DestroyImmediate(tex);
            AssetDatabase.ImportAsset(path);
            var importer = (TextureImporter)AssetImporter.GetAtPath(path);
            importer.wrapMode = TextureWrapMode.Repeat;
            importer.anisoLevel = 8;
            importer.SaveAndReimport();
            return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }
    }
}
