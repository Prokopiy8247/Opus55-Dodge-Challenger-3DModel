using Hellcat.Game.Cameras;
using Hellcat.Game.Core;
using Hellcat.Game.Scenario;
using Hellcat.Game.UI;
using Hellcat.Game.Views;
using Hellcat.Game.World;
using Hellcat.EditorTools.Car;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace Hellcat.EditorTools.Build
{
    /// <summary>
    /// Builds Assets/Scenes/P4_Crash.unity (brief 9, S1): flat asphalt, the O1 concrete wall (12 x 3 x 1 m) with its face
    /// 70 m ahead of the spawn, the skinned Hellcat (prefab from Tools/Hellcat/Import Car) on the solver with a settled
    /// spawn, chase / side / front-quarter / top cameras and the crash scenario. Batch:
    /// -executeMethod Hellcat.EditorTools.Build.CrashSceneBuilder.Build
    /// </summary>
    public static class CrashSceneBuilder
    {
        public const string ScenePath = "Assets/Scenes/P4_Crash.unity";
        const float WallFace = 70f;

        [MenuItem("Tools/Hellcat/Build P4 Crash Scene")]
        public static void Build()
        {
            VehicleAssetSync.SyncAll();
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            var light = new GameObject("Sun").AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.4f;
            light.shadows = LightShadows.Soft;
            light.shadowStrength = 0.85f;
            light.transform.rotation = Quaternion.Euler(42f, -40f, 0f);
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.66f, 0.72f, 0.82f);
            RenderSettings.ambientEquatorColor = new Color(0.48f, 0.48f, 0.48f);
            RenderSettings.ambientGroundColor = new Color(0.26f, 0.25f, 0.23f);
            var probe = new GameObject("Reflections").AddComponent<ReflectionProbe>();
            probe.mode = ReflectionProbeMode.Realtime;
            probe.refreshMode = ReflectionProbeRefreshMode.OnAwake;
            probe.size = new Vector3(200f, 40f, 200f);
            probe.transform.position = new Vector3(0f, 3f, 40f);

            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "Ground";
            Object.DestroyImmediate(ground.GetComponent<Collider>());
            ground.transform.localScale = new Vector3(40f, 1f, 40f);
            ground.transform.position = new Vector3(0f, 0f, 40f);
            ground.GetComponent<MeshRenderer>().sharedMaterial = EditorAssets.Lit("Asphalt", Color.white, 0.25f, 0f, EditorAssets.GroundGrid(), new Vector2(40f, 40f));
            ground.AddComponent<StaticPlaneSource>().surface = "asphalt";

            var wall = GameObject.CreatePrimitive(PrimitiveType.Cube);
            wall.name = "Wall_O1";
            Object.DestroyImmediate(wall.GetComponent<Collider>());
            wall.transform.localScale = new Vector3(12f, 3f, 1f);
            wall.transform.position = new Vector3(0f, 1.5f, WallFace + 0.5f);
            wall.GetComponent<MeshRenderer>().sharedMaterial = EditorAssets.Lit("Concrete", new Color(0.72f, 0.71f, 0.68f), 0.15f);
            wall.AddComponent<StaticBoxSource>().surface = "concrete";

            var spawn = new GameObject("Spawn").transform;
            spawn.position = Vector3.zero;

            var sim = new GameObject("Sim");
            var runner = sim.AddComponent<SimRunner>();
            runner.vehicleName = "hellcat";
            runner.spawnPoint = spawn;
            runner.spawnClearance = 0.01f;
            runner.settleOnSpawn = true;
            runner.trackEnergy = true;
            runner.maxSubstepsPerFrame = 66;

            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(CarImporter.PrefabPath);
            if (prefab == null)
                throw new System.IO.FileNotFoundException("run Tools/Hellcat/Import Car first", CarImporter.PrefabPath);
            var car = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
            var view = car.GetComponent<SoftBodyCarView>();
            view.runner = runner;
            var skinProbe = car.AddComponent<SkinningProbe>();
            skinProbe.view = view;

            var cams = new System.Collections.Generic.List<Camera>();
            Camera Cam(string name, Vector3 pos, Vector3 look, float fov, bool tag)
            {
                var go = new GameObject(name);
                if (tag) go.tag = "MainCamera";
                var c = go.AddComponent<Camera>();
                c.fieldOfView = fov;
                c.nearClipPlane = 0.1f;
                c.farClipPlane = 600f;
                c.clearFlags = CameraClearFlags.SolidColor;
                c.backgroundColor = new Color(0.62f, 0.68f, 0.76f);
                go.transform.position = pos;
                go.transform.LookAt(look);
                cams.Add(c);
                return c;
            }
            var chase = Cam("chase", new Vector3(0f, 2.4f, -7f), new Vector3(0f, 0.8f, 2f), 50f, true);
            var follow = chase.gameObject.AddComponent<ChaseCamera>();
            follow.runner = runner;
            Cam("side", new Vector3(13f, 1.4f, WallFace - 2.5f), new Vector3(0f, 0.8f, WallFace - 2.5f), 32f, false);
            Cam("front34", new Vector3(-7.5f, 2.6f, WallFace - 9f), new Vector3(0f, 0.7f, WallFace - 2.0f), 40f, false);
            Cam("top", new Vector3(0f, 16f, WallFace - 2.6f), new Vector3(0f, 0f, WallFace - 2.5f), 30f, false);

            var scenario = sim.AddComponent<CarCrashScenario>();
            scenario.runner = runner;
            scenario.carView = view;
            scenario.probe = skinProbe;
            scenario.cameras = cams.ToArray();
            scenario.obstacle = wall.transform;

            var hud = new GameObject("HUD").AddComponent<Hud>();
            hud.runner = runner;

            EditorSceneManager.SaveScene(scene, ScenePath);
            Debug.Log($"[CrashSceneBuilder] wrote {ScenePath}");
        }
    }
}
