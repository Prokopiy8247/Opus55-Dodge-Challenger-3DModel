using Hellcat.EditorTools.Car;
using Hellcat.Game.Cameras;
using Hellcat.Game.Core;
using Hellcat.Game.Input;
using Hellcat.Game.UI;
using Hellcat.Game.Views;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace Hellcat.EditorTools.Build
{
    /// <summary>
    /// The playable rig every game scene shares (P4b, P5): the solver runner with the car at the start spawn, the input
    /// sources (live driver, drive-test robot, teleport speed hold, replay), the skinned Hellcat with its live cockpit, the
    /// camera rig, the debug views, HUD, pause menu and controls. Scene builders add the world around it and their
    /// scenario components.
    /// </summary>
    public static class GameRigBuilder
    {
        public sealed class Rig
        {
            public GameObject sim;
            public SimRunner runner;
            public LiveDriverInput live;
            public RobotDriverSource robot;
            public ReplayController replay;
            public ApproachHoldSource approach;
            public SoftBodyCarView view;
            public Camera camera;
            public CameraRig cameras;
            public CockpitInstruments cockpit;
            public SkeletonDebugView skeleton;
            public DebugViews views;
            public Hud hud;
            public PauseMenu menu;
            public GameControls controls;
            public InteriorLod interiorLod;
            public StartScreen startScreen;
        }

        public static void Lighting(Vector3 probeCentre, Vector3 probeSize)
        {
            var light = new GameObject("Sun").AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.4f;
            light.shadows = LightShadows.Soft;
            light.shadowStrength = 0.85f;
            light.transform.rotation = Quaternion.Euler(42f, -40f, 0f);
            // P7: a procedural sky behind the scene and in the reflection probe, so glass and paint reflect a sky with a
            // horizon and the sun; the ambient light stays the trilight of the earlier phases
            var sky = EditorAssets.ShaderMaterial("SkyProcedural", "Skybox/Procedural");
            sky.SetFloat("_SunDisk", 2f);              // high quality sun disk (a keyword enum)
            sky.DisableKeyword("_SUNDISK_NONE");
            sky.DisableKeyword("_SUNDISK_SIMPLE");
            sky.EnableKeyword("_SUNDISK_HIGH_QUALITY");
            sky.SetFloat("_SunSize", 0.035f);
            sky.SetFloat("_SunSizeConvergence", 6f);
            sky.SetFloat("_AtmosphereThickness", 0.85f);
            sky.SetColor("_SkyTint", new Color(0.52f, 0.56f, 0.62f));
            sky.SetColor("_GroundColor", new Color(0.38f, 0.37f, 0.35f));
            sky.SetFloat("_Exposure", 1.15f);
            EditorUtility.SetDirty(sky);
            RenderSettings.skybox = sky;
            RenderSettings.sun = light;
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.66f, 0.72f, 0.82f);
            RenderSettings.ambientEquatorColor = new Color(0.48f, 0.48f, 0.48f);
            RenderSettings.ambientGroundColor = new Color(0.26f, 0.25f, 0.23f);
            var probe = new GameObject("Reflections").AddComponent<ReflectionProbe>();
            probe.mode = ReflectionProbeMode.Realtime;
            probe.refreshMode = ReflectionProbeRefreshMode.OnAwake;
            probe.size = probeSize;
            probe.transform.position = probeCentre;
        }

        public static Rig Create(Transform start)
        {
            var r = new Rig();
            r.sim = new GameObject("Sim");
            r.runner = r.sim.AddComponent<SimRunner>();
            r.runner.vehicleName = "hellcat";
            r.runner.spawnPoint = start;
            r.runner.spawnClearance = 0.01f;
            r.runner.settleOnSpawn = true;
            r.runner.trackEnergy = true;
            r.runner.maxSubstepsPerFrame = 66;
            r.live = r.sim.AddComponent<LiveDriverInput>();
            r.live.runner = r.runner;
            r.robot = r.sim.AddComponent<RobotDriverSource>();
            r.robot.runner = r.runner;
            r.replay = r.sim.AddComponent<ReplayController>();
            r.replay.runner = r.runner;
            r.approach = r.sim.AddComponent<ApproachHoldSource>();
            r.approach.runner = r.runner;
            r.approach.live = r.live;

            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(CarImporter.PrefabPath);
            if (prefab == null)
                throw new System.IO.FileNotFoundException("run Tools/Hellcat/Import Car first", CarImporter.PrefabPath);
            var car = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
            r.view = car.GetComponent<SoftBodyCarView>();
            r.view.runner = r.runner;

            var camGo = new GameObject("Main Camera") { tag = "MainCamera" };
            r.camera = camGo.AddComponent<Camera>();
            r.camera.fieldOfView = 55f;
            r.camera.nearClipPlane = 0.1f;
            r.camera.farClipPlane = 1500f;
            CameraSky.Apply(r.camera);
            camGo.AddComponent<AudioListener>();
            camGo.transform.position = start.position + start.rotation * new Vector3(0f, 2.4f, -7f);
            r.cameras = camGo.AddComponent<CameraRig>();
            r.cameras.runner = r.runner;

            r.cockpit = car.AddComponent<CockpitInstruments>();
            r.cockpit.runner = r.runner;
            r.cockpit.view = r.view;
            r.cockpit.eyeCamera = r.camera;
            r.cockpit.mirrorShader = Shader.Find("Hellcat/MirrorGlass");
            r.cameras.instruments = r.cockpit;

            var views = new GameObject("Views");
            var skel = new GameObject("Skeleton");
            skel.transform.SetParent(views.transform);
            skel.AddComponent<MeshFilter>();
            skel.AddComponent<MeshRenderer>().sharedMaterial = EditorAssets.ShaderMaterial("DebugLines", "Hellcat/VertexColorUnlit");
            r.skeleton = skel.AddComponent<SkeletonDebugView>();
            r.skeleton.runner = r.runner;
            r.views = views.AddComponent<DebugViews>();
            r.views.runner = r.runner;
            r.views.skeleton = r.skeleton;
            r.views.car = r.view;
            r.views.deformationMaterial = EditorAssets.ShaderMaterial("DeformationHeatmap", "Hellcat/DeformationHeatmap");

            var ui = new GameObject("UI");
            r.hud = ui.AddComponent<Hud>();
            r.hud.runner = r.runner;
            r.hud.cameras = r.cameras;
            r.hud.replay = r.replay;
            r.hud.views = r.views;
            r.hud.approach = r.approach;
            r.menu = ui.AddComponent<PauseMenu>();
            r.menu.runner = r.runner;
            r.menu.cameras = r.cameras;
            r.menu.views = r.views;
            r.menu.replay = r.replay;
            r.controls = ui.AddComponent<GameControls>();
            r.controls.runner = r.runner;
            r.controls.cameraRig = r.cameras;
            r.controls.debugViews = r.views;
            r.controls.replay = r.replay;
            r.controls.live = r.live;
            r.controls.approach = r.approach;
            r.controls.hud = r.hud;
            r.controls.menu = r.menu;
            r.hud.controls = r.controls;
            r.menu.controls = r.controls;
            // P7: the interior drawn in full only from the cockpit or inside the cabin (brief 4.12), the start screen
            var lod = car.AddComponent<InteriorLod>();
            lod.view = r.view;
            lod.cameras = r.cameras;
            lod.eye = r.camera;
            r.interiorLod = lod;
            var startScreen = ui.AddComponent<StartScreen>();
            startScreen.hud = r.hud;
            r.startScreen = startScreen;
            return r;
        }
    }
}
