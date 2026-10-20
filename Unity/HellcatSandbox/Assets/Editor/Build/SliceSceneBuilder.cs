using Hellcat.Game.Cameras;
using Hellcat.Game.Core;
using Hellcat.Game.Input;
using Hellcat.Game.Scenario;
using Hellcat.Game.UI;
using Hellcat.Game.Views;
using Hellcat.Game.World;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace Hellcat.EditorTools.Build
{
    /// <summary>
    /// Builds Assets/Scenes/P05_Slice.unity: flat asphalt, a 12 x 3 x 1 m concrete wall 90 m ahead,
    /// the box car (StreamingAssets/Vehicles/boxcar), chase + side cameras, HUD and the wall scenario.
    /// Batch: -executeMethod Hellcat.EditorTools.Build.SliceSceneBuilder.Build
    /// </summary>
    public static class SliceSceneBuilder
    {
        public const string ScenePath = "Assets/Scenes/P05_Slice.unity";

        [MenuItem("Tools/Hellcat/Build P0.5 Slice Scene")]
        public static void Build()
        {
            VehicleAssetSync.SyncAll();
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            var light = new GameObject("Sun").AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.3f;
            light.shadows = LightShadows.Soft;
            light.transform.rotation = Quaternion.Euler(48f, -35f, 0f);
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.62f, 0.68f, 0.78f);
            RenderSettings.ambientEquatorColor = new Color(0.45f, 0.45f, 0.45f);
            RenderSettings.ambientGroundColor = new Color(0.25f, 0.24f, 0.22f);

            var groundTex = EditorAssets.GroundGrid();
            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "Ground";
            Object.DestroyImmediate(ground.GetComponent<Collider>());
            ground.transform.localScale = new Vector3(40f, 1f, 40f); // 400 m x 400 m
            ground.transform.position = new Vector3(0f, 0f, 80f);
            ground.GetComponent<MeshRenderer>().sharedMaterial = EditorAssets.Lit("Asphalt", Color.white, 0.25f, 0f, groundTex, new Vector2(40f, 40f));
            ground.AddComponent<StaticPlaneSource>().surface = "asphalt";

            var wall = GameObject.CreatePrimitive(PrimitiveType.Cube);
            wall.name = "Wall_O1";
            Object.DestroyImmediate(wall.GetComponent<Collider>());
            wall.transform.localScale = new Vector3(12f, 3f, 1f);
            wall.transform.position = new Vector3(0f, 1.5f, 90.5f); // front face at z = 90 m
            wall.GetComponent<MeshRenderer>().sharedMaterial = EditorAssets.Lit("Concrete", new Color(0.72f, 0.71f, 0.68f), 0.15f);
            wall.AddComponent<StaticBoxSource>().surface = "concrete";

            var spawn = new GameObject("Spawn").transform;
            spawn.position = Vector3.zero;

            var sim = new GameObject("Sim");
            var runner = sim.AddComponent<SimRunner>();
            runner.vehicleName = "boxcar";
            runner.spawnPoint = spawn;
            var live = sim.AddComponent<LiveDriverInput>();
            live.runner = runner;

            var camGo = new GameObject("Main Camera") { tag = "MainCamera" };
            var cam = camGo.AddComponent<Camera>();
            cam.fieldOfView = 55f;
            cam.nearClipPlane = 0.1f;
            cam.farClipPlane = 1500f;
            camGo.AddComponent<AudioListener>();
            var chase = camGo.AddComponent<ChaseCamera>();
            chase.runner = runner;
            camGo.transform.position = new Vector3(0f, 2.4f, -7.5f);

            var sideGo = new GameObject("Side Camera");
            var side = sideGo.AddComponent<Camera>();
            side.fieldOfView = 40f;
            side.enabled = false; // rendered on demand by the capture code
            sideGo.transform.position = new Vector3(13f, 2.2f, 86f);
            sideGo.transform.LookAt(new Vector3(0f, 0.8f, 87.5f));

            var scen = sim.AddComponent<WallCrashScenario>();
            scen.runner = runner;
            scen.chaseCamera = cam;
            scen.sideCamera = side;
            scen.wall = wall.transform;

            var views = new GameObject("Views");
            var skel = new GameObject("Skeleton");
            skel.transform.SetParent(views.transform);
            skel.AddComponent<MeshFilter>();
            skel.AddComponent<MeshRenderer>().sharedMaterial = EditorAssets.ShaderMaterial("DebugLines", "Hellcat/VertexColorUnlit");
            skel.AddComponent<SkeletonDebugView>().runner = runner;
            var box = new GameObject("BoxCar").AddComponent<BoxCarView>();
            box.transform.SetParent(views.transform);
            box.runner = runner;
            box.bodyMaterial = EditorAssets.Lit("SliceBody", new Color(0.92f, 0.92f, 0.93f, 1f), 0.55f);
            box.wheelMaterial = EditorAssets.Lit("SliceWheel", new Color(0.08f, 0.08f, 0.09f, 1f), 0.3f);

            var hud = new GameObject("HUD").AddComponent<Hud>();
            hud.runner = runner;

            System.IO.Directory.CreateDirectory("Assets/Scenes");
            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            AssetDatabase.SaveAssets();
            Debug.Log($"[SliceSceneBuilder] saved {ScenePath}");
        }
    }
}
