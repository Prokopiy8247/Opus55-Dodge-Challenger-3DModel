using Hellcat.EditorTools.Car;
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
    /// Builds Assets/Scenes/P4b_Drive.unity, the drivable sandbox of P4b (brief 4.12): a 1 km asphalt square, the drive-test
    /// loop at the origin (spawn "Start"), four demo obstacles east of it with an approach spawn 60 m before each (O1 concrete
    /// wall, O2 steel pole, O3 offset block, O4 ramp; P5 replaces them with the test map), the skinned Hellcat with the live
    /// cockpit, the camera rig, HUD, pause menu, controls, record / replay, the debug views, the G-Drive test
    /// (-scenario drive) and the short capture (-scenario showcase). Batch:
    /// -executeMethod Hellcat.EditorTools.Build.DriveSceneBuilder.Build
    /// </summary>
    public static class DriveSceneBuilder
    {
        public const string ScenePath = "Assets/Scenes/P4b_Drive.unity";

        [MenuItem("Tools/Hellcat/Build P4b Drive Scene")]
        public static void Build()
        {
            VehicleAssetSync.SyncAll();
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            GameRigBuilder.Lighting(new Vector3(0f, 4f, 150f), new Vector3(400f, 60f, 600f));

            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "Ground";
            Object.DestroyImmediate(ground.GetComponent<Collider>());
            ground.transform.localScale = new Vector3(100f, 1f, 100f);   // 1 km x 1 km
            ground.transform.position = new Vector3(50f, 0f, 150f);
            ground.GetComponent<MeshRenderer>().sharedMaterial = EditorAssets.Lit("AsphaltDrive", Color.white, 0.25f, 0f, EditorAssets.GroundGrid(), new Vector2(100f, 100f));
            ground.AddComponent<StaticPlaneSource>().surface = "asphalt";

            var obstacles = new GameObject("Obstacles").transform;
            var concrete = EditorAssets.Lit("Concrete", new Color(0.72f, 0.71f, 0.68f), 0.15f);
            var steel = EditorAssets.Lit("SteelPole", new Color(0.55f, 0.57f, 0.6f), 0.55f, 0.8f);
            GameObject Box(string name, Vector3 pos, Vector3 size, Quaternion rot, Material mat, string surface)
            {
                var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
                go.name = name;
                Object.DestroyImmediate(go.GetComponent<Collider>());
                go.transform.SetParent(obstacles, false);
                go.transform.SetPositionAndRotation(pos, rot);
                go.transform.localScale = size;
                go.GetComponent<MeshRenderer>().sharedMaterial = mat;
                go.AddComponent<StaticBoxSource>().surface = surface;
                return go;
            }
            void Spawn(string label, int order, Vector3 pos, float approach, float kmh)
            {
                var go = new GameObject($"Spawn_{order}_{label}");
                go.transform.SetParent(obstacles, false);
                go.transform.position = pos;
                var sp = go.AddComponent<SpawnPoint>();
                sp.label = label;
                sp.order = order;
                sp.approachDistance = approach;
                sp.defaultKmh = kmh;
            }
            // O1: the S1 wall (12 x 3 x 1 m), face at z = 150
            Box("O1_Wall", new Vector3(100f, 1.5f, 150.5f), new Vector3(12f, 3f, 1f), Quaternion.identity, concrete, "concrete");
            Spawn("O1 concrete wall", 1, new Vector3(100f, 0f, 90f), 60f, 50f);
            // O2: steel pole, 0.3 m diameter, 4 m tall
            var pole = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            pole.name = "O2_Pole";
            Object.DestroyImmediate(pole.GetComponent<Collider>());
            pole.transform.SetParent(obstacles, false);
            pole.transform.position = new Vector3(140f, 2f, 150.15f);
            pole.transform.localScale = new Vector3(0.3f, 2f, 0.3f);
            pole.GetComponent<MeshRenderer>().sharedMaterial = steel;
            pole.AddComponent<StaticCylinderSource>().surface = "steel";
            Spawn("O2 steel pole", 2, new Vector3(140f, 0f, 90f), 60f, 50f);
            // O3: rigid block overlapping the driver's side by 40 % of the width (offset frontal)
            Box("O3_Block", new Vector3(179.2f, 1f, 151f), new Vector3(1.2f, 2f, 2f), Quaternion.identity, concrete, "concrete");
            Spawn("O3 offset block (40 %)", 3, new Vector3(180f, 0f, 90f), 60f, 64f);
            // O4: ramp, 12 deg, 8 m long, 4 m wide
            float ang = 12f, len = 8f, th = 0.3f;
            float rise = len * Mathf.Sin(ang * Mathf.Deg2Rad);
            Box("O4_Ramp", new Vector3(220f, 0.5f * rise - 0.5f * th * Mathf.Cos(ang * Mathf.Deg2Rad), 150f + 0.5f * len * Mathf.Cos(ang * Mathf.Deg2Rad)),
                new Vector3(4f, th, len), Quaternion.Euler(-ang, 0f, 0f), concrete, "concrete");
            Spawn("O4 ramp jump", 4, new Vector3(220f, 0f, 90f), 60f, 80f);

            var startGo = new GameObject("Spawn_0_Start");
            startGo.transform.SetParent(obstacles, false);
            var startSp = startGo.AddComponent<SpawnPoint>();
            startSp.label = "Start (drive loop)";
            startSp.order = 0;
            var start = startGo.transform;

            var rig = GameRigBuilder.Create(start);

            var test = rig.sim.AddComponent<DriveTest>();
            test.runner = rig.runner;
            test.robot = rig.robot;
            test.live = rig.live;
            test.cameras = rig.cameras;
            test.views = rig.views;
            test.replay = rig.replay;
            test.hud = rig.hud;
            test.cockpit = rig.cockpit;
            test.start = start;

            var show = rig.sim.AddComponent<ShowcaseCapture>();
            show.runner = rig.runner;
            show.robot = rig.robot;
            show.cameras = rig.cameras;
            show.views = rig.views;
            show.replay = rig.replay;
            show.controls = rig.controls;
            show.hud = rig.hud;
            show.start = start;

            System.IO.Directory.CreateDirectory("Assets/Scenes");
            EditorSceneManager.SaveScene(scene, ScenePath);
            AssetDatabase.SaveAssets();
            Debug.Log($"[DriveSceneBuilder] wrote {ScenePath}");
        }
    }
}
