using System.Collections.Generic;
using System.IO;
using Hellcat.EditorTools.Build;
using Hellcat.Game.Capture;
using Hellcat.Game.Views;
using Hellcat.Sim;
using Hellcat.Sim.Data;
using Hellcat.Sim.Vehicle;
using Unity.Mathematics;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace Hellcat.EditorTools.Car
{
    /// <summary>
    /// P4 stills of the skinned car without entering play mode: the Hellcat prefab on the ground with its node bones at the
    /// settled rest pose of the solver (D-037), rendered from several cameras into docs/video_assets/P4. Also reports how
    /// far every visual vertex moved from the bind pose at rest (skinning against the original meshes).
    /// Batch: -executeMethod Hellcat.EditorTools.Car.CarPreview.RenderRest
    /// </summary>
    public static class CarPreview
    {
        static readonly DriverInput Parked = new DriverInput { brake = 1f, handbrake = 1f, gear = 0 };

        public static void RenderRest()
        {
            int code = 1;
            try
            {
                System.Globalization.CultureInfo.CurrentCulture = System.Globalization.CultureInfo.InvariantCulture;
                string root = VehicleAssetSync.ProjectRoot;
                string outDir = Path.Combine(root, "docs", "video_assets", "P4");
                var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                Stage();
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(CarImporter.PrefabPath);
                var car = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
                var view = car.GetComponent<SoftBodyCarView>();

                // the solver at rest
                string folder = Path.Combine(Application.streamingAssetsPath, "Vehicles", "hellcat");
                var def = VehicleDef.Load(Path.Combine(folder, "geometry.json"));
                var prm = SimParamsDef.Load(Path.Combine(folder, "params.json"));
                using var w = new SoftBodyWorld(prm);
                int bi = w.AddBody("hellcat", def, prm, float3.zero, quaternion.identity, float3.zero, true);
                w.bodies[bi].spawnClearance = 0.01f;
                var statics = new StaticWorldBuilder();
                statics.AddPlane(new float3(0f, 1f, 0f), 0f, "asphalt");
                w.Build(statics);
                w.SetInput(w.bodies[bi].vehicleIndex, Parked);
                w.Settle(bi);
                for (int k = 0; k < 400; k++) { w.UpdateNearLists(0.06f); w.Step(10); }
                var b = w.bodies[bi];

                // reconstruction check: every node bone at the rest pose; the visual vertices against the original mesh
                // carried by the best rigid motion of its nodes would need CPU skinning - report the bone motion instead
                double maxMove = 0;
                for (int i = 0; i < def.nodes.Length; i++)
                {
                    float3 p = w.pos[b.nodeStart + i];
                    float3 X0 = new float3(def.nodes[i].p[0], def.nodes[i].p[1], def.nodes[i].p[2]);
                    maxMove = math.max(maxMove, math.distance(p, X0));
                    // the best-fit rotation of the node's neighbourhood (D-062), as SoftBodyCarView
                    float3x3 s = float3x3.zero;
                    for (int k = view.frameNbrStart[i]; k < view.frameNbrStart[i + 1]; k++)
                    {
                        int j = view.frameNbr[k];
                        float3 x = w.pos[b.nodeStart + j] - p;
                        float3 X = new float3(def.nodes[j].p[0], def.nodes[j].p[1], def.nodes[j].p[2]) - X0;
                        s += new float3x3(X * x.x, X * x.y, X * x.z);
                    }
                    view.nodeBones[i].SetPositionAndRotation(p, SoftBodyCarView.BestRotation(s, quaternion.identity));
                }
                Debug.Log($"[CarPreview] settled; largest node offset from the model pose {maxMove * 1000:F1} mm");

                var cams = new (string name, Vector3 pos, Vector3 look, float fov)[]
                {
                    ("front34", new Vector3(4.6f, 1.6f, 6.0f), new Vector3(0f, 0.6f, 0.2f), 32f),
                    ("rear34", new Vector3(-4.8f, 1.7f, -5.8f), new Vector3(0f, 0.6f, -0.3f), 32f),
                    ("side", new Vector3(8.5f, 1.0f, 0f), new Vector3(0f, 0.65f, 0f), 30f),
                    ("wheel_FR", new Vector3(2.4f, 0.55f, 2.9f), new Vector3(0.8f, 0.35f, 1.45f), 30f),
                    ("top", new Vector3(0f, 11f, 0.01f), new Vector3(0f, 0f, 0f), 30f),
                };
                var camGo = new GameObject("PreviewCamera");
                var cam = camGo.AddComponent<Camera>();
                cam.clearFlags = CameraClearFlags.SolidColor;
                cam.backgroundColor = new Color(0.62f, 0.68f, 0.76f);
                cam.nearClipPlane = 0.05f;
                cam.farClipPlane = 500f;
                cam.allowMSAA = true;
                foreach (var c in cams)
                {
                    cam.transform.position = c.pos;
                    cam.transform.LookAt(c.look);
                    cam.fieldOfView = c.fov;
                    string path = Path.Combine(outDir, $"2026-10-13_P4_rest_{c.name}.png");
                    FrameCapture.Save(cam, path, 1920, 1080);
                    Debug.Log($"[CarPreview] wrote {path}");
                }
                code = 0;
            }
            catch (System.Exception e)
            {
                Debug.LogException(e);
            }
            EditorApplication.Exit(code);
        }

        static void Stage()
        {
            var light = new GameObject("Sun").AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.4f;
            light.shadows = LightShadows.Soft;
            light.transform.rotation = Quaternion.Euler(42f, -40f, 0f);
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.66f, 0.72f, 0.82f);
            RenderSettings.ambientEquatorColor = new Color(0.48f, 0.48f, 0.48f);
            RenderSettings.ambientGroundColor = new Color(0.26f, 0.25f, 0.23f);
            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "Ground";
            Object.DestroyImmediate(ground.GetComponent<Collider>());
            ground.transform.localScale = new Vector3(10f, 1f, 10f);
            ground.GetComponent<MeshRenderer>().sharedMaterial = EditorAssets.Lit("Asphalt", Color.white, 0.25f, 0f, EditorAssets.GroundGrid(), new Vector2(10f, 10f));
            var probe = new GameObject("Reflections").AddComponent<ReflectionProbe>();
            probe.mode = ReflectionProbeMode.Realtime;
            probe.refreshMode = ReflectionProbeRefreshMode.EveryFrame;
            probe.size = new Vector3(40f, 20f, 40f);
            probe.transform.position = new Vector3(0f, 2f, 0f);
        }
    }
}
