using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using Hellcat.EditorTools.Build;
using Hellcat.Game.Views;
using Hellcat.Sim.Data;
using Unity.Collections;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace Hellcat.EditorTools.Car
{
    /// <summary>
    /// Tools/Hellcat/Import Car (brief 7): imports the FBX files written by <c>tools/export_all.py</c>
    /// (Assets/Game/Vehicles/Hellcat/Export: one FBX per part group, parts.json, materials.json, textures), creates URP
    /// materials, binds every visual vertex to up to 4 nodes of its part(s) (the nearest, inverse-distance weights;
    /// each node is a bone whose frame is built from the node and two neighbours of its part by Gram-Schmidt), writes
    /// the bindings as <c>&lt;group&gt;.skin.bytes</c> next to each FBX (applied on import by <see cref="CarSkinPostprocessor"/>),
    /// and builds Assets/Game/Vehicles/Hellcat/Hellcat.prefab (node bones + skinned mesh renderers + SoftBodyCarView).
    /// Writes docs/p4/import_report.json: the axis check of every object against the export and the bind-pose
    /// reconstruction error. Batch: -executeMethod Hellcat.EditorTools.Car.CarImporter.ImportBatch
    /// </summary>
    public static class CarImporter
    {
        public const string Root = "Assets/Game/Vehicles/Hellcat";
        public const string Export = Root + "/Export";
        public const string Materials = Root + "/Materials";
        public const string PrefabPath = Root + "/Hellcat.prefab";
        public const int MaxBones = 4;

        // FBX import: Blender's front (+y) comes in along -z; the skeleton frame is (x, z, y) of Blender, a 180 deg
        // turn about y (checked per object against the export's bounding boxes)
        internal static readonly Matrix4x4 ToSkeleton = Matrix4x4.Rotate(Quaternion.Euler(0f, 180f, 0f));

        [Serializable] class PartsFile { public string frame; public FbxEntry[] fbx; }
        [Serializable] class FbxEntry { public string file, group; public ObjEntry[] objects; }
        [Serializable] class ObjEntry { public string name; public string[] bind; public string[] materials; public int vertices, triangles; public float[] bbox_min, bbox_max; }
        [Serializable] class MaterialsFile { public MatEntry[] materials; }
        [Serializable] class MatEntry { public string name; public float[] baseColor; public float metallic, roughness, alpha; public float[] emission; public float emissionStrength; public string textures_json; }

        /// <summary>Node filters of the running-gear visuals (regex over node names, {W} wheel, {S} side); the rest bind to all
        /// nodes of their parts.</summary>
        // interior trims on the cell (P4): weights 1 / (d + 8 cm) instead of 1 / (d + 1 cm), so a thin trim strip blends its
        // sparse cage nodes smoothly instead of switching between them within a few centimetres (it folded over in the pulse)
        static readonly Regex InteriorRx = new Regex(@"^CH_Int_(?!DoorCard|Seat)");
        const float InteriorSoft = 0.08f;

        static readonly (Regex obj, string nodes)[] Rules =
        {
            (new Regex(@"^CH_Wheel_(?<W>FL|FR|RL|RR)_(Rim|Disc)$"), @"^{W}_(rimI|rimO)\d+$"),
            (new Regex(@"^CH_Wheel_(?<W>FL|FR|RL|RR)_Tire$"), @"^{W}_(rimI|rimO|trI|trC|trO)\d+$"),
            (new Regex(@"^CH_Wheel_(?<W>FL|FR|RL|RR)_Caliper$"), @"^{W}_(axle_in|axle_out|lbj|ubj|tre|klf|klr|kup)$"),
            (new Regex(@"^CH_Knuckles_(?<S>L|R)$"), @"^[FR]{S}_(axle_in|axle_out|lbj|ubj|tre|klf|klr|kup)$"),
            (new Regex(@"^CH_Susp_Front_Arms_(?<S>L|R)$"), @"^F{S}_(lca_f|lca_r|lca_sh|lbj|uca_f|uca_r|ubj|tre)$|^rack_{S}$"),
            (new Regex(@"^CH_Susp_Front_(Spring|Damper)_(?<S>L|R)$"), @"^F{S}_lca_sh$|^aplo1_{S}$"),
            (new Regex(@"^CH_Susp_Rear_Links_(?<S>L|R)$"), @"^R{S}_link\d$|^R{S}_(klf|klr|kup)$"),
            (new Regex(@"^CH_Susp_Rear_(Spring|Damper)_(?<S>L|R)$"), @"^R{S}_klr$|^rtower_{S}$"),
            (new Regex(@"^CH_HalfShaft_(?<S>L|R)$"), @"^R{S}_(axle_in|axle_out)$|^diff\d$"),
            // interior on the body: the passenger cell's cage only (not the skin panels, crush zones or chassis nodes)
            (new Regex(@"^CH_Int_(?!DoorCard|Seat)"),
                @"^(sill|floor|tunnel|hinge|aplo|bp\d|cp\d|rail\d|dash|cowl\d|cowl_C|fw_|hdrF|bowB|hdrR|shelf|bulk|xm|whouse|column_)"),
        };

        [MenuItem("Tools/Hellcat/Import Car")]
        public static void ImportMenu() => Import();

        public static void ImportBatch()
        {
            int code = 1;
            try
            {
                Import();
                code = 0;
            }
            catch (Exception e)
            {
                Debug.LogException(e);
            }
            EditorApplication.Exit(code);
        }

        public static void Import()
        {
            // '.' decimals in the report and the log, whatever the OS locale
            CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;
            VehicleAssetSync.SyncAll();
            string projectRoot = VehicleAssetSync.ProjectRoot;
            string geoPath = Path.Combine(Application.streamingAssetsPath, "Vehicles", "hellcat", "geometry.json");
            var def = VehicleDef.Load(geoPath);
            string geoHash = Hash(File.ReadAllBytes(geoPath));
            var parts = JsonUtility.FromJson<PartsFile>(File.ReadAllText(Path.Combine(Export, "parts.json")));
            Debug.Log($"[CarImporter] {parts.fbx.Length} FBX files, {def.nodes.Length} nodes, geometry {geoHash}");

            var mats = BuildMaterials();
            foreach (var e in parts.fbx)
                ConfigureFbx($"{Export}/{e.file}", mats);
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);

            // node frames: best-fit rotation of the node's neighbourhood (D-062), the identity at the model pose
            var nbrs = FrameNeighbors(def, out int[] nbrStart);
            var bind = new Matrix4x4[def.nodes.Length];
            for (int i = 0; i < def.nodes.Length; i++)
                bind[i] = Matrix4x4.Translate(P(def, i));
            var partNodes = new Dictionary<string, int[]>();
            foreach (var pd in def.parts)
                partNodes[pd.name] = pd.nodes;

            var report = new StringBuilder();
            report.Append("{\n \"geometry\": \"").Append(geoHash).Append("\",\n \"objects\": [\n");
            int nObj = 0, nVert = 0;
            double worstAxis = 0, worstBind = 0, worstReach = 0;
            string worstAxisObj = "", worstBindObj = "", worstReachObj = "";
            foreach (var e in parts.fbx)
            {
                string fbxPath = $"{Export}/{e.file}";
                var go = AssetDatabase.LoadAssetAtPath<GameObject>(fbxPath);
                if (go == null)
                    throw new InvalidDataException($"cannot load {fbxPath}");
                var skin = new CarSkinData { geometryHash = geoHash };
                foreach (var mf in go.GetComponentsInChildren<MeshFilter>(true))
                {
                    // a single-object FBX carries its mesh on the root (named after the file)
                    string objName = mf.transform == go.transform && e.objects.Length == 1 ? e.objects[0].name : mf.name;
                    var obj = e.objects.FirstOrDefault(o => o.name == objName);
                    if (obj == null)
                        throw new InvalidDataException($"{fbxPath}: {objName} not in parts.json");
                    var mesh = mf.sharedMesh;
                    Matrix4x4 toWorld = ToSkeleton * mf.transform.localToWorldMatrix;   // the asset root holds a single object's transform
                    var verts = mesh.vertices;
                    // axis check against the export's bounding box (skeleton frame)
                    Vector3 lo = Vector3.positiveInfinity, hi = Vector3.negativeInfinity;
                    var world = new Vector3[verts.Length];
                    for (int v = 0; v < verts.Length; v++)
                    {
                        world[v] = toWorld.MultiplyPoint3x4(verts[v]);
                        lo = Vector3.Min(lo, world[v]);
                        hi = Vector3.Max(hi, world[v]);
                    }
                    double axisErr = Math.Max(MaxAbs(lo - V(obj.bbox_min)), MaxAbs(hi - V(obj.bbox_max)));
                    var candidates = Candidates(def, obj, partNodes);
                    double reach;
                    var ms = objName.EndsWith("_Shards")
                        ? BindShards(def, mesh, world, candidates, bind, toWorld, out reach)
                        : Bind(def, world, candidates, bind, toWorld, out reach, InteriorRx.IsMatch(obj.name) ? InteriorSoft : 0.01f);
                    ms.name = objName;
                    skin.meshes.Add(ms);
                    double bindErr = BindError(world, verts, ms, bind);
                    if (axisErr > worstAxis) { worstAxis = axisErr; worstAxisObj = objName; }
                    if (bindErr > worstBind) { worstBind = bindErr; worstBindObj = objName; }
                    if (reach > worstReach) { worstReach = reach; worstReachObj = objName; }
                    report.Append(nObj > 0 ? ",\n" : "").Append(($"  {{\"name\": \"{objName}\", \"fbx\": \"{e.file}\", \"vertices\": {verts.Length}, " +
                        $"\"candidates\": {candidates.Length}, \"bones\": {ms.boneNodes.Length}, \"axis_error_m\": {axisErr:G4}, " +
                        $"\"bind_error_m\": {bindErr:G4}, \"farthest_bound_node_m\": {reach:G4} }}"));
                    nObj++;
                    nVert += verts.Length;
                }
                skin.Write(Path.Combine(Export, Path.GetFileNameWithoutExtension(e.file) + ".skin.bytes"));
            }
            report.Append(($"\n ],\n \"objects_count\": {nObj},\n \"vertices\": {nVert},\n \"worst_axis_error_m\": {worstAxis:G4},\n \"worst_axis_object\": \"{worstAxisObj}\",\n" +
                $" \"worst_bind_error_m\": {worstBind:G4},\n \"worst_bind_object\": \"{worstBindObj}\",\n \"worst_farthest_bound_node_m\": {worstReach:G4},\n \"worst_reach_object\": \"{worstReachObj}\"\n}}\n"));
            Directory.CreateDirectory(Path.Combine(projectRoot, "docs", "p4"));
            File.WriteAllText(Path.Combine(projectRoot, "docs", "p4", "import_report.json"), report.ToString());
            Debug.Log(($"[CarImporter] bound {nObj} objects, {nVert} vertices; worst axis error {worstAxis * 1000:F3} mm ({worstAxisObj}), " +
                      $"worst bind-pose error {worstBind * 1000:F4} mm ({worstBindObj}), farthest bound node {worstReach:F3} m ({worstReachObj})"));
            if (worstAxis > 1e-3)
                throw new InvalidDataException($"imported vertices off the skeleton frame by {worstAxis * 1000:F1} mm ({worstAxisObj})");

            // apply the skins (postprocessor) and build the prefab
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            foreach (var e in parts.fbx)
                AssetDatabase.ImportAsset($"{Export}/{e.file}", ImportAssetOptions.ForceUpdate | ImportAssetOptions.ForceSynchronousImport);
            BuildPrefab(def, parts, nbrStart, nbrs, bind);
        }

        static Vector3 P(VehicleDef d, int i) => new Vector3(d.nodes[i].p[0], d.nodes[i].p[1], d.nodes[i].p[2]);
        static Vector3 V(float[] a) => new Vector3(a[0], a[1], a[2]);
        static double MaxAbs(Vector3 v) => Math.Max(Math.Abs(v.x), Math.Max(Math.Abs(v.y), Math.Abs(v.z)));

        static string Hash(byte[] b)
        {
            using var sha = SHA256.Create();
            return BitConverter.ToString(sha.ComputeHash(b), 0, 8).Replace("-", "");
        }

        /// <summary>Frame neighbours of every node (D-062): its beam neighbours in the same part, nearest first, at most 8; a
        /// node with fewer than 3 also takes the nearest nodes of its part within 0.8 m. The spinning rim and tread nodes:
        /// a knuckle or axle node's frame must not lean on them (the frame, and the caliper and knuckle meshes on it, would
        /// turn with the wheel); a spinning node's frame may use the axle nodes. Returns the CSR list (local indices).</summary>
        public static int[] FrameNeighbors(VehicleDef def, out int[] start)
        {
            int n = def.nodes.Length;
            var nb = new List<int>[n];
            for (int i = 0; i < n; i++) nb[i] = new List<int>();
            foreach (var b in def.beams)
            {
                if (def.nodes[b.a].part != def.nodes[b.b].part)
                    continue;
                nb[b.a].Add(b.b);
                nb[b.b].Add(b.a);
            }
            var byPart = new Dictionary<string, List<int>>();
            for (int i = 0; i < n; i++)
            {
                if (!byPart.TryGetValue(def.nodes[i].part, out var l)) byPart[def.nodes[i].part] = l = new List<int>();
                l.Add(i);
            }
            var spins = new bool[n];
            if (def.wheels != null)
                foreach (var wd in def.wheels)
                {
                    foreach (int r in wd.rim) spins[r] = true;
                    foreach (int r in wd.tread) spins[r] = true;
                }
            bool Usable(int i, int j) => spins[i] || !spins[j];
            var list = new List<int>();
            start = new int[n + 1];
            for (int i = 0; i < n; i++)
            {
                Vector3 p = P(def, i);
                var cand = nb[i].Distinct().Where(j => j != i && Usable(i, j) && (P(def, j) - p).sqrMagnitude > 1e-8f)
                    .OrderBy(j => (P(def, j) - p).sqrMagnitude).Take(8).ToList();
                if (cand.Count < 3)
                    cand.AddRange(byPart[def.nodes[i].part]
                        .Where(j => j != i && Usable(i, j) && !cand.Contains(j) && (P(def, j) - p).sqrMagnitude > 1e-8f &&
                                    (P(def, j) - p).sqrMagnitude < 0.64f)
                        .OrderBy(j => (P(def, j) - p).sqrMagnitude).Take(3 - cand.Count));
                if (cand.Count == 0)
                    throw new InvalidDataException($"node {def.nodes[i].name}: no frame neighbour in part {def.nodes[i].part}");
                list.AddRange(cand);
                start[i + 1] = list.Count;
            }
            return list.ToArray();
        }

        static int[] Candidates(VehicleDef def, ObjEntry obj, Dictionary<string, int[]> partNodes)
        {
            var all = new List<int>();
            foreach (var p in obj.bind)
                if (partNodes.TryGetValue(p, out var ids))
                    all.AddRange(ids);
            foreach (var (rx, nodes) in Rules)
            {
                var m = rx.Match(obj.name);
                if (!m.Success)
                    continue;
                string pat = nodes.Replace("{W}", m.Groups["W"].Success ? m.Groups["W"].Value : "")
                                  .Replace("{S}", m.Groups["S"].Success ? m.Groups["S"].Value : "");
                var nrx = new Regex(pat);
                // the filter may reach nodes of other parts (rack, spring towers, differential): all nodes are eligible
                var filtered = Enumerable.Range(0, def.nodes.Length).Where(i => nrx.IsMatch(def.nodes[i].name)).ToList();
                if (filtered.Count == 0)
                    throw new InvalidDataException($"{obj.name}: node filter {pat} matches nothing");
                return filtered.ToArray();
            }
            if (all.Count == 0)
                throw new InvalidDataException($"{obj.name}: no nodes in parts {string.Join(",", obj.bind)}");
            return all.Distinct().ToArray();
        }

        /// <summary>The k nearest candidate nodes of every vertex, weights 1 / (d + soft) normalized (soft 1 cm, the interior 8 cm);
        /// bones are the used nodes,
        /// bind poses B^-1 M (B the node frame at the model pose, M the mesh-to-skeleton transform).</summary>
        static CarSkinData.MeshSkin Bind(VehicleDef def, Vector3[] world, int[] cand, Matrix4x4[] bind, Matrix4x4 toWorld, out double reach,
            float soft = 0.01f)
        {
            var cp = cand.Select(i => P(def, i)).ToArray();
            var boneOf = new Dictionary<int, int>();
            var bones = new List<int>();
            var bpv = new byte[world.Length];
            var weights = new List<BoneWeight1>(world.Length * MaxBones);
            reach = 0;
            var bestD = new float[MaxBones];
            var bestI = new int[MaxBones];
            for (int v = 0; v < world.Length; v++)
            {
                int k = Math.Min(MaxBones, cand.Length);
                for (int q = 0; q < MaxBones; q++) { bestD[q] = float.MaxValue; bestI[q] = -1; }
                Vector3 x = world[v];
                for (int c = 0; c < cp.Length; c++)
                {
                    float d = (cp[c] - x).sqrMagnitude;
                    if (d >= bestD[k - 1]) continue;
                    int q = k - 1;
                    while (q > 0 && bestD[q - 1] > d) { bestD[q] = bestD[q - 1]; bestI[q] = bestI[q - 1]; q--; }
                    bestD[q] = d;
                    bestI[q] = c;
                }
                float sum = 0f;
                var w = new float[k];
                for (int q = 0; q < k; q++)
                {
                    w[q] = 1f / (Mathf.Sqrt(bestD[q]) + soft);
                    sum += w[q];
                }
                reach = Math.Max(reach, Mathf.Sqrt(bestD[0]));
                bpv[v] = (byte)k;
                for (int q = 0; q < k; q++)
                {
                    int node = cand[bestI[q]];
                    if (!boneOf.TryGetValue(node, out int bi)) { bi = bones.Count; boneOf[node] = bi; bones.Add(node); }
                    weights.Add(new BoneWeight1 { boneIndex = bi, weight = w[q] / sum });
                }
            }
            var bp = bones.Select(n => bind[n].inverse * toWorld).ToArray();
            return new CarSkinData.MeshSkin
            {
                vertexCount = world.Length, boneNodes = bones.ToArray(), bindposes = bp, bonesPerVertex = bpv, weights = weights.ToArray(),
            };
        }

        /// <summary>Pre-fractured glass (hcar.glass_shards): every vertex rigidly on the node its shard was cut around, whose
        /// index (vehicle definition) the second UV map carries; the shards keep their pane's shape while its nodes hold
        /// together and fly with them once the glass beams break.</summary>
        static CarSkinData.MeshSkin BindShards(VehicleDef def, Mesh mesh, Vector3[] world, int[] cand, Matrix4x4[] bind, Matrix4x4 toWorld,
            out double reach)
        {
            var uv = new List<Vector2>();
            mesh.GetUVs(1, uv);
            if (uv.Count != world.Length)
                throw new InvalidDataException($"{mesh.name}: no ShardNode UV map (second UV channel)");
            var allowed = new HashSet<int>(cand);
            var boneOf = new Dictionary<int, int>();
            var bones = new List<int>();
            var bpv = new byte[world.Length];
            var weights = new BoneWeight1[world.Length];
            reach = 0;
            for (int v = 0; v < world.Length; v++)
            {
                int node = Mathf.RoundToInt(uv[v].x);
                if (!allowed.Contains(node))
                    throw new InvalidDataException($"{mesh.name}: vertex {v} names node {node}, not a node of its pane");
                if (!boneOf.TryGetValue(node, out int bi)) { bi = bones.Count; boneOf[node] = bi; bones.Add(node); }
                bpv[v] = 1;
                weights[v] = new BoneWeight1 { boneIndex = bi, weight = 1f };
                reach = Math.Max(reach, (P(def, node) - world[v]).magnitude);
            }
            var bp = bones.Select(n => bind[n].inverse * toWorld).ToArray();
            return new CarSkinData.MeshSkin
            {
                vertexCount = world.Length, boneNodes = bones.ToArray(), bindposes = bp, bonesPerVertex = bpv, weights = weights,
            };
        }

        /// <summary>Linear blend skinning at the bind pose (bones at the model pose) against the vertices in the skeleton frame.</summary>
        static double BindError(Vector3[] world, Vector3[] local, CarSkinData.MeshSkin ms, Matrix4x4[] bind)
        {
            double err = 0;
            int o = 0;
            for (int v = 0; v < world.Length; v++)
            {
                Vector3 s = Vector3.zero;
                for (int q = 0; q < ms.bonesPerVertex[v]; q++, o++)
                {
                    var bw = ms.weights[o];
                    s += bw.weight * (bind[ms.boneNodes[bw.boneIndex]] * ms.bindposes[bw.boneIndex]).MultiplyPoint3x4(local[v]);
                }
                err = Math.Max(err, (s - world[v]).magnitude);
            }
            return err;
        }

        static Dictionary<string, Material> BuildMaterials()
        {
            if (!AssetDatabase.IsValidFolder(Materials))
                AssetDatabase.CreateFolder(Root, "Materials");
            string json = File.ReadAllText(Path.Combine(Export, "materials.json"));
            // JsonUtility cannot read the textures dictionary: pull it out per material with a regex
            var mf = JsonUtility.FromJson<MaterialsFile>(json);
            var texRx = new Regex("\"name\": \"(?<n>[^\"]+)\"[^{}]*\"textures\": \\{(?<t>[^}]*)\\}");
            var tex = new Dictionary<string, Dictionary<string, string>>();
            foreach (Match m in texRx.Matches(json))
            {
                var d = new Dictionary<string, string>();
                foreach (Match kv in new Regex("\"(?<k>[^\"]+)\": \"(?<v>[^\"]+)\"").Matches(m.Groups["t"].Value))
                    d[kv.Groups["k"].Value] = kv.Groups["v"].Value;
                tex[m.Groups["n"].Value] = d;
            }
            var lit = Shader.Find("Universal Render Pipeline/Lit");
            var outMats = new Dictionary<string, Material>();
            foreach (var e in mf.materials)
            {
                string path = $"{Materials}/{e.name}.mat";
                var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
                if (mat == null)
                {
                    mat = new Material(lit);
                    AssetDatabase.CreateAsset(mat, path);
                }
                mat.shader = lit;
                // Blender colours are linear; Unity material colours are sRGB
                var c = new Color(e.baseColor[0], e.baseColor[1], e.baseColor[2], 1f).gamma;
                c.a = e.alpha;
                mat.SetColor("_BaseColor", c);
                mat.SetFloat("_Metallic", e.metallic);
                mat.SetFloat("_Smoothness", Mathf.Clamp01(1f - e.roughness));
                bool transparent = e.alpha < 0.99f;
                mat.SetFloat("_Surface", transparent ? 1f : 0f);
                mat.SetFloat("_Blend", 0f);
                mat.SetFloat("_ZWrite", transparent ? 0f : 1f);
                mat.SetFloat("_SrcBlend", transparent ? (float)BlendMode.SrcAlpha : (float)BlendMode.One);
                mat.SetFloat("_DstBlend", transparent ? (float)BlendMode.OneMinusSrcAlpha : (float)BlendMode.Zero);
                mat.renderQueue = transparent ? (int)RenderQueue.Transparent : -1;
                mat.SetOverrideTag("RenderType", transparent ? "Transparent" : "Opaque");
                if (transparent) mat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT"); else mat.DisableKeyword("_SURFACE_TYPE_TRANSPARENT");
                tex.TryGetValue(e.name, out var tx);
                Texture2D T(string socket) => tx != null && tx.TryGetValue(socket, out var f) ? AssetDatabase.LoadAssetAtPath<Texture2D>($"{Export}/Textures/{f}") : null;
                var baseMap = T("Base Color");
                mat.SetTexture("_BaseMap", baseMap);
                if (baseMap != null) mat.SetColor("_BaseColor", new Color(1f, 1f, 1f, e.alpha));
                var em = new Color(e.emission[0], e.emission[1], e.emission[2]).gamma * e.emissionStrength;
                var emMap = T("Emission Color");
                bool emissive = e.emissionStrength > 0f && (em.maxColorComponent > 0.001f || emMap != null);
                if (emissive)
                {
                    mat.EnableKeyword("_EMISSION");
                    mat.SetColor("_EmissionColor", emMap != null ? Color.white * e.emissionStrength : em);
                    mat.SetTexture("_EmissionMap", emMap);
                    mat.globalIlluminationFlags = MaterialGlobalIlluminationFlags.RealtimeEmissive;
                }
                else
                {
                    mat.DisableKeyword("_EMISSION");
                }
                if (tx != null && tx.ContainsKey("Alpha"))
                {
                    mat.SetFloat("_AlphaClip", 1f);
                    mat.SetFloat("_Cutoff", 0.5f);
                    mat.EnableKeyword("_ALPHATEST_ON");
                }
                if (transparent)
                {
                    // P7 glass look: URP's own blend set-up with "preserve specular lighting", so the reflections on tinted
                    // glass and lamp lenses keep their strength instead of fading with the alpha (they read as holes)
                    PreserveSpecularBlend(mat);
                }
                EditorUtility.SetDirty(mat);
                outMats[e.name] = mat;
            }
            GlassVariants(outMats);
            AssetDatabase.SaveAssets();
            return outMats;
        }

        // P7 glass: the windshield and the front side windows lighter (the driver looks out through them) than the rear and
        // quarter windows (privacy tint); the Blender material's single alpha 0.3 read almost clear in the renders
        const string GlassMaterial = "CH_Glass_Tint", FrontGlassMaterial = "CH_Glass_Front";
        const float PrivacyGlassAlpha = 0.6f, FrontGlassAlpha = 0.25f;
        static readonly string[] FrontGlassFbx = { "glass_windshield.fbx", "glass_side_FL.fbx", "glass_side_FR.fbx" };
        static Material frontGlass;

        /// <summary>URP Lit, transparent, alpha blending with "preserve specular lighting" - the set-up URP's material inspector
        /// makes: the shader multiplies the diffuse by alpha (premultiplied), not the specular, so reflections keep their
        /// strength on a mostly clear surface.</summary>
        static void PreserveSpecularBlend(Material mat)
        {
            mat.SetFloat("_Surface", 1f);
            mat.SetFloat("_Blend", 0f);
            mat.SetFloat("_BlendModePreserveSpecular", 1f);
            mat.SetFloat("_SrcBlend", (float)BlendMode.One);
            mat.SetFloat("_DstBlend", (float)BlendMode.OneMinusSrcAlpha);
            mat.SetFloat("_SrcBlendAlpha", (float)BlendMode.One);
            mat.SetFloat("_DstBlendAlpha", (float)BlendMode.OneMinusSrcAlpha);
            mat.SetFloat("_ZWrite", 0f);
            mat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            mat.EnableKeyword("_ALPHAPREMULTIPLY_ON");
            mat.DisableKeyword("_ALPHAMODULATE_ON");
            mat.SetOverrideTag("RenderType", "Transparent");
            mat.renderQueue = (int)RenderQueue.Transparent;
            mat.SetShaderPassEnabled("DepthOnly", false);
        }

        static void GlassVariants(Dictionary<string, Material> mats)
        {
            frontGlass = null;
            if (!mats.TryGetValue(GlassMaterial, out var glass))
                return;
            var c = glass.GetColor("_BaseColor");
            glass.SetColor("_BaseColor", new Color(c.r, c.g, c.b, PrivacyGlassAlpha));
            PreserveSpecularBlend(glass);
            string path = $"{Materials}/{FrontGlassMaterial}.mat";
            var front = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (front == null)
            {
                front = new Material(glass);
                AssetDatabase.CreateAsset(front, path);
            }
            else
            {
                front.shader = glass.shader;
                front.CopyPropertiesFromMaterial(glass);
            }
            front.SetColor("_BaseColor", new Color(c.r, c.g, c.b, FrontGlassAlpha));
            PreserveSpecularBlend(front);
            EditorUtility.SetDirty(glass);
            EditorUtility.SetDirty(front);
            frontGlass = front;
        }

        static void ConfigureFbx(string path, Dictionary<string, Material> mats)
        {
            var imp = AssetImporter.GetAtPath(path) as ModelImporter;
            if (imp == null)
            {
                AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceSynchronousImport);
                imp = AssetImporter.GetAtPath(path) as ModelImporter;
            }
            if (imp == null)
                throw new InvalidDataException($"{path}: no model importer");
            imp.globalScale = 1f;
            imp.useFileScale = true;
            imp.bakeAxisConversion = false;
            imp.isReadable = true;
            imp.meshCompression = ModelImporterMeshCompression.Off;
            imp.importNormals = ModelImporterNormals.Import;
            imp.importTangents = ModelImporterTangents.CalculateMikk;
            imp.importBlendShapes = false;
            imp.importCameras = false;
            imp.importLights = false;
            imp.importVisibility = false;
            imp.importAnimation = false;
            imp.animationType = ModelImporterAnimationType.None;
            imp.weldVertices = true;
            imp.optimizeMeshPolygons = true;
            imp.optimizeMeshVertices = true;
            imp.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            imp.materialLocation = ModelImporterMaterialLocation.InPrefab;
            bool front = frontGlass != null && FrontGlassFbx.Contains(Path.GetFileName(path));
            foreach (var kv in mats)
                imp.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), kv.Key),
                    front && kv.Key == GlassMaterial ? frontGlass : kv.Value);
            imp.SaveAndReimport();
        }

        static void BuildPrefab(VehicleDef def, PartsFile parts, int[] nbrStart, int[] nbrs, Matrix4x4[] bind)
        {
            var root = new GameObject("Hellcat");
            var view = root.AddComponent<SoftBodyCarView>();
            var nodesRoot = new GameObject("Nodes").transform;
            nodesRoot.SetParent(root.transform, false);
            var bones = new Transform[def.nodes.Length];
            for (int i = 0; i < def.nodes.Length; i++)
            {
                var t = new GameObject($"{i:D4}_{def.nodes[i].name}").transform;
                t.SetParent(nodesRoot, false);
                t.SetPositionAndRotation(bind[i].GetColumn(3), bind[i].rotation);
                bones[i] = t;
            }
            view.nodeBones = bones;
            view.frameNbrStart = nbrStart;
            view.frameNbr = nbrs;
            var visual = new GameObject("Visual").transform;
            visual.SetParent(root.transform, false);
            int body = Array.FindIndex(def.nodes, n => n.part == "body");
            foreach (var e in parts.fbx)
            {
                string fbxPath = $"{Export}/{e.file}";
                var go = AssetDatabase.LoadAssetAtPath<GameObject>(fbxPath);
                var skinAsset = Path.Combine(Export, Path.GetFileNameWithoutExtension(e.file) + ".skin.bytes");
                var skin = CarSkinData.Read(File.ReadAllBytes(skinAsset));
                var group = new GameObject(e.group).transform;
                group.SetParent(visual, false);
                foreach (var mf in go.GetComponentsInChildren<MeshFilter>(true))
                {
                    string objName = mf.transform == go.transform && skin.meshes.Count == 1 ? skin.meshes[0].name : mf.name;
                    var ms = skin.meshes.First(m => m.name == objName);
                    var mesh = mf.sharedMesh;
                    if (mesh.bindposeCount != ms.boneNodes.Length)
                        throw new InvalidDataException($"{objName}: the imported mesh carries {mesh.bindposeCount} bind poses, the skin {ms.boneNodes.Length} (postprocessor not applied?)");
                    var smrGo = new GameObject(objName);
                    smrGo.transform.SetParent(group, false);
                    var smr = smrGo.AddComponent<SkinnedMeshRenderer>();
                    smr.sharedMesh = mesh;
                    smr.sharedMaterials = mf.GetComponent<MeshRenderer>().sharedMaterials;
                    smr.bones = ms.boneNodes.Select(n => bones[n]).ToArray();
                    smr.rootBone = bones[ms.boneNodes[0]];
                    smr.quality = SkinQuality.Bone4;
                    // skinned every frame even when the main camera culls it (capture cameras, mirrors; GPU skinning
                    // skips culled renderers and they would show an old pose)
                    smr.updateWhenOffscreen = true;
                    // generous bounds about the root bone (the car may deform and parts may fly)
                    smr.localBounds = new Bounds(Vector3.zero, new Vector3(8f, 8f, 8f));
                    smr.shadowCastingMode = ShadowCastingMode.On;
                }
            }
            if (File.Exists(PrefabPath))
                AssetDatabase.DeleteAsset(PrefabPath);
            PrefabUtility.SaveAsPrefabAsset(root, PrefabPath);
            UnityEngine.Object.DestroyImmediate(root);
            AssetDatabase.SaveAssets();
            Debug.Log($"[CarImporter] prefab {PrefabPath}: {bones.Length} node bones");
        }
    }

    /// <summary>Applies <c>&lt;fbx&gt;.skin.bytes</c> (bone weights and bind poses per mesh) to the car FBX files on import.</summary>
    public class CarSkinPostprocessor : AssetPostprocessor
    {
        // 2: UV3 carries the model-pose position (P4b deformation heat-map)
        public override uint GetVersion() => 2;

        void OnPostprocessModel(GameObject g)
        {
            if (!assetPath.StartsWith(CarImporter.Export + "/", StringComparison.Ordinal))
                return;
            string skinPath = assetPath.Substring(0, assetPath.LastIndexOf('/') + 1) + Path.GetFileNameWithoutExtension(assetPath) + ".skin.bytes";
            context.DependsOnSourceAsset(skinPath);
            if (!File.Exists(skinPath))
                return;
            var skin = CarSkinData.Read(File.ReadAllBytes(skinPath));
            foreach (var mf in g.GetComponentsInChildren<MeshFilter>(true))
            {
                string objName = mf.transform == g.transform && skin.meshes.Count == 1 ? skin.meshes[0].name : mf.name;
                var ms = skin.meshes.FirstOrDefault(m => m.name == objName);
                var mesh = mf.sharedMesh;
                if (ms == null || mesh == null)
                    continue;
                if (mesh.vertexCount != ms.vertexCount)
                {
                    Debug.LogWarning($"[CarSkinPostprocessor] {assetPath}/{mf.name}: {mesh.vertexCount} vertices, skin {ms.vertexCount}: re-run Tools/Hellcat/Import Car");
                    continue;
                }
                using var bpv = new NativeArray<byte>(ms.bonesPerVertex, Allocator.Temp);
                using var w = new NativeArray<BoneWeight1>(ms.weights, Allocator.Temp);
                mesh.SetBoneWeights(bpv, w);
                mesh.bindposes = ms.bindposes;
                // UV3 = the vertex at the model pose in the car frame (deformation heat-map, DebugViews)
                Matrix4x4 toModel = CarImporter.ToSkeleton * mf.transform.localToWorldMatrix;
                var verts = mesh.vertices;
                var rest = new List<Vector3>(verts.Length);
                foreach (var v in verts)
                    rest.Add(toModel.MultiplyPoint3x4(v));
                mesh.SetUVs(3, rest);
            }
        }
    }
}
