using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using Hellcat.Game.Scenario;
using Hellcat.Game.Views;
using Hellcat.Game.World;
using Hellcat.Sim.Props;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Hellcat.EditorTools.Build
{
    /// <summary>
    /// Builds Assets/Scenes/TestMap.unity (brief 8, P5, D-081/D-082): a 300 m x 200 m asphalt proving ground (x east, z north,
    /// centred on the origin; 10 m measuring marks in the ground texture, an 8 m grass band round the edge) with the nine
    /// obstacles of the brief, each with a lane of at least 60 m clean run-up from its spawn point (painted lane, distance
    /// marks every 10 m, a label). South row, lanes heading north: O1 wall, O2 wall with the 40 % offset line, O3 pole,
    /// O4 jersey-barrier row at 20 deg, O5 guardrail met at 10 deg. North row, lanes heading south: O6 ramp and landing pad,
    /// O7 speed bump and curb, O8 debris field (barrels, boxes, cones, fence: soft bodies in the solver), O9 3 m ledge with
    /// its lower pad and a 30 deg bank. East: open asphalt with a 30 m skidpad circle and the start spawn. Writes
    /// docs/p5/map_layout.json (every obstacle's dimensions, lanes, surfaces) for the gate. Batch:
    /// -executeMethod Hellcat.EditorTools.Build.TestMapBuilder.Build
    /// </summary>
    public static class TestMapBuilder
    {
        public const string ScenePath = "Assets/Scenes/TestMap.unity";
        public const float HalfX = 150f, HalfZ = 100f, GrassBand = 8f;
        const float CarFront = 2.41f;    // model origin to the front-most node (geometry.json)

        static readonly CultureInfo Ic = CultureInfo.InvariantCulture;
        static readonly List<string> layout = new List<string>();
        static readonly List<string> lanes = new List<string>();
        static Transform root, marks;
        static Material concrete, steel, paintWhite, paintYellow, grass, rubber, wood;

        [MenuItem("Tools/Hellcat/Build Test Map")]
        public static void Build()
        {
            VehicleAssetSync.SyncAll();
            layout.Clear();
            lanes.Clear();
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            GameRigBuilder.Lighting(new Vector3(0f, 5f, 0f), new Vector3(320f, 60f, 220f));

            concrete = EditorAssets.Lit("Concrete", new Color(0.72f, 0.71f, 0.68f), 0.15f);
            steel = EditorAssets.Lit("SteelPole", new Color(0.55f, 0.57f, 0.6f), 0.55f, 0.8f);
            paintWhite = EditorAssets.Lit("PaintWhite", new Color(0.93f, 0.93f, 0.9f), 0.3f);
            paintYellow = EditorAssets.Lit("PaintYellow", new Color(0.98f, 0.8f, 0.1f), 0.3f);
            grass = EditorAssets.Lit("Grass", new Color(0.33f, 0.48f, 0.2f), 0.05f);
            rubber = EditorAssets.Lit("ConeOrange", new Color(1f, 0.38f, 0.05f), 0.35f);
            wood = EditorAssets.Lit("Wood", new Color(0.55f, 0.41f, 0.26f), 0.2f);

            root = new GameObject("TestMap").transform;
            marks = new GameObject("Markings").transform;
            marks.SetParent(root, false);

            // ground: asphalt (infinite plane for the solver), the visual 300 x 200 m, grass beyond and round the edge
            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "Ground";
            Object.DestroyImmediate(ground.GetComponent<Collider>());
            ground.transform.SetParent(root, false);
            ground.transform.localScale = new Vector3(2f * HalfX / 10f, 1f, 2f * HalfZ / 10f);
            ground.GetComponent<MeshRenderer>().sharedMaterial = EditorAssets.Lit("AsphaltMap", Color.white, 0.25f, 0f, EditorAssets.GroundGrid(),
                new Vector2(2f * HalfX / 10f, 2f * HalfZ / 10f));
            ground.AddComponent<StaticPlaneSource>().surface = "asphalt";
            var outside = GameObject.CreatePrimitive(PrimitiveType.Plane);
            outside.name = "Surroundings";
            Object.DestroyImmediate(outside.GetComponent<Collider>());
            outside.transform.SetParent(root, false);
            outside.transform.position = new Vector3(0f, -0.02f, 0f);
            outside.transform.localScale = new Vector3(100f, 1f, 100f);
            outside.GetComponent<MeshRenderer>().sharedMaterial = grass;
            GrassBandAround();
            Record("ground", "asphalt proving ground", new Vector3(0f, 0f, 0f), new Vector3(2f * HalfX, 0f, 2f * HalfZ), "asphalt",
                $"\"grass_band_m\": {F(GrassBand)}");

            SouthRow();
            NorthRow();
            East();

            var start = SpawnAt("Start (open area, skidpad)", 0, new Vector3(60f, 0f, -60f), 0f, 0f, 0f);
            var rig = GameRigBuilder.Create(start);
            var check = rig.sim.AddComponent<MapCheck>();
            check.runner = rig.runner;
            check.cameras = rig.cameras;
            check.controls = rig.controls;
            check.hud = rig.hud;
            check.props = Object.FindFirstObjectByType<PropField>();
            if (check.props != null)
                check.props.runner = rig.runner;
            // P6: the scripted scenarios S1-S8 (-scenario Sx) and their driven variants (-scenario Sx -driven 1)
            var skinProbe = rig.view.gameObject.AddComponent<SkinningProbe>();
            skinProbe.view = rig.view;
            var crash = rig.sim.AddComponent<CarCrashScenario>();
            crash.runner = rig.runner;
            crash.carView = rig.view;
            crash.probe = skinProbe;
            crash.props = check.props;
            crash.cameras = new Camera[0];
            var driven = rig.sim.AddComponent<DrivenScenario>();
            driven.runner = rig.runner;
            driven.controls = rig.controls;
            driven.replay = rig.replay;
            driven.cameras = rig.cameras;
            driven.hud = rig.hud;
            // P7, the standalone sandbox's own checks: the drive test (G-Drive / G-Build) and the showcase capture on a
            // stadium loop in the open east (90 m straights, R 38 m curves: x 42-118 m, z -83-83 m), the controls check
            var loop = SpawnAt("Drive loop (east)", 20, new Vector3(118f, 0f, -45f), 0f, 0f, 0f);
            var test = rig.sim.AddComponent<DriveTest>();
            test.runner = rig.runner;
            test.robot = rig.robot;
            test.live = rig.live;
            test.cameras = rig.cameras;
            test.views = rig.views;
            test.replay = rig.replay;
            test.hud = rig.hud;
            test.cockpit = rig.cockpit;
            test.start = loop;
            test.straight = 90.0;
            test.radius = 38.0;
            test.straightKmh = 110.0;
            test.curveKmh = 55.0;
            var show = rig.sim.AddComponent<ShowcaseCapture>();
            show.runner = rig.runner;
            show.robot = rig.robot;
            show.cameras = rig.cameras;
            show.views = rig.views;
            show.replay = rig.replay;
            show.controls = rig.controls;
            show.hud = rig.hud;
            show.start = loop;
            show.straight = 90.0;
            show.radius = 38.0;
            show.straightKmh = 110.0;
            show.curveKmh = 55.0;
            var controlsCheck = rig.sim.AddComponent<ControlsCheck>();
            controlsCheck.runner = rig.runner;
            controlsCheck.live = rig.live;
            controlsCheck.controls = rig.controls;
            controlsCheck.cameras = rig.cameras;
            controlsCheck.views = rig.views;
            controlsCheck.replay = rig.replay;
            controlsCheck.menu = rig.menu;
            controlsCheck.hud = rig.hud;
            controlsCheck.start = start;

            Directory.CreateDirectory("Assets/Scenes");
            EditorSceneManager.SaveScene(scene, ScenePath);
            AssetDatabase.SaveAssets();
            WriteLayout();
            Debug.Log($"[TestMapBuilder] wrote {ScenePath}");
        }

        // ------------------------------------------------------------------ rows

        /// <summary>Lanes heading north (+z) from z = -88; obstacle faces near z = -20 (60+ m clean run-up).</summary>
        static void SouthRow()
        {
            float spawnZ = -88f;
            // O1: concrete wall 12 x 3 x 1 m, face at z = -20
            Box("O1_Wall", new Vector3(-120f, 1.5f, -19.5f), new Vector3(12f, 3f, 1f), Quaternion.identity, concrete, "concrete");
            Record("O1", "concrete wall, full frontal", new Vector3(-120f, 1.5f, -19.5f), new Vector3(12f, 3f, 1f), "concrete");
            Lane("O1", 1, new Vector3(-120f, 0f, spawnZ), 0f, -20f, 50f, "O1 WALL 12 x 3 x 1 m");

            // O2: the same wall; the car's lane puts 40 % of its width (driver side) over the wall's east end
            Box("O2_Wall", new Vector3(-90f, 1.5f, -19.5f), new Vector3(12f, 3f, 1f), Quaternion.identity, concrete, "concrete");
            float carW = 1.99f, edge = -84f, laneX = edge - 0.4f * carW + 0.5f * carW;
            Record("O2", "concrete wall with 40 % offset line", new Vector3(-90f, 1.5f, -19.5f), new Vector3(12f, 3f, 1f), "concrete",
                $"\"overlap\": 0.40, \"car_width_m\": {F(carW)}, \"lane_x\": {F(laneX)}, \"wall_edge_x\": {F(edge)}");
            Lane("O2", 2, new Vector3(laneX, 0f, spawnZ), 0f, -20f, 64f, "O2 OFFSET 40 %");
            Paint(new Vector3(edge, 0f, -20.5f), new Vector3(edge, 0f, -70f), 0.12f, paintYellow);                      // wall edge line
            Paint(new Vector3(edge - 0.4f * carW, 0f, -20.5f), new Vector3(edge - 0.4f * carW, 0f, -70f), 0.12f, paintYellow); // overlap line

            // O3: steel pole 0.30 m x 6 m, set in the ground
            var pole = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            pole.name = "O3_Pole";
            Object.DestroyImmediate(pole.GetComponent<Collider>());
            pole.transform.SetParent(root, false);
            pole.transform.position = new Vector3(-60f, 3f, -19.85f);
            pole.transform.localScale = new Vector3(0.3f, 3f, 0.3f);
            pole.GetComponent<MeshRenderer>().sharedMaterial = steel;
            pole.AddComponent<StaticCylinderSource>().surface = "steel";
            Record("O3", "steel pole", new Vector3(-60f, 3f, -19.85f), new Vector3(0.3f, 6f, 0.3f), "steel", "\"diameter_m\": 0.30, \"height_m\": 6.0");
            Lane("O3", 3, new Vector3(-60f, 0f, spawnZ), 0f, -20f, 50f, "O3 POLE 0.30 x 6 m");

            // O4: six jersey barriers 3.66 m x 0.81 m in a row at 20 deg to the lane
            float a4 = 20f;
            var d4 = new Vector3(Mathf.Sin(a4 * Mathf.Deg2Rad), 0f, Mathf.Cos(a4 * Mathf.Deg2Rad));
            var s4 = new Vector3(-33f, 0f, -28f);
            for (int k = 0; k < 6; k++)
            {
                var c = s4 + d4 * (3.66f * k + 1.83f + 0.02f * k);
                Jersey($"O4_Jersey_{k + 1}", c, Quaternion.LookRotation(d4, Vector3.up));
            }
            Record("O4", "jersey barrier row", s4 + d4 * 11f, new Vector3(0.61f, 0.81f, 6 * 3.66f), "concrete",
                $"\"units\": 6, \"unit_length_m\": 3.66, \"height_m\": 0.81, \"base_width_m\": 0.61, \"top_width_m\": 0.15, \"angle_to_lane_deg\": {F(a4)}");
            float t4 = (-30f - s4.x) / d4.x;
            Lane("O4", 4, new Vector3(-30f, 0f, spawnZ), 0f, s4.z + d4.z * t4, 40f, "O4 JERSEY ROW 20 deg");

            // O5: guardrail 15.2 m (posts every 1.9 m, W-beam top 0.70 m) along +z; the lane meets it at 10 deg
            float railX = 5f, railZ0 = -30f, railLen = 15.2f;
            for (int k = 0; k <= 8; k++)
                Box($"O5_Post_{k}", new Vector3(railX + 0.2f, 0.375f, railZ0 + 1.9f * k), new Vector3(0.15f, 0.75f, 0.15f), Quaternion.identity, steel, "steel");
            Box("O5_WBeam", new Vector3(railX, 0.55f, railZ0 + 0.5f * railLen), new Vector3(0.08f, 0.31f, railLen), Quaternion.identity, steel, "steel");
            Box("O5_EndTerminal", new Vector3(railX, 0.3f, railZ0 - 2.0f), new Vector3(0.08f, 0.31f, 4.1f),
                Quaternion.Euler(-7.5f, 0f, 0f), steel, "steel");
            Record("O5", "guardrail", new Vector3(railX, 0.55f, railZ0 + 0.5f * railLen), new Vector3(0.08f, 0.70f, railLen), "steel",
                "\"posts\": 9, \"post_spacing_m\": 1.9, \"wbeam_top_m\": 0.705, \"wbeam_height_m\": 0.31, \"lane_angle_deg\": 10");
            float a5 = 10f * Mathf.Deg2Rad;
            var hit = new Vector3(railX - 1.2f, 0f, railZ0 + 3.0f);                  // car centre when its right front corner meets the beam
            var dir5 = new Vector3(Mathf.Sin(a5), 0f, Mathf.Cos(a5));
            var sp5 = hit - dir5 * 63f;
            Lane("O5", 5, sp5, 10f, hit.z, 70f, "O5 GUARDRAIL 10 deg");
        }

        /// <summary>Lanes heading south (-z) from z = +89; obstacles near z = +25 (60+ m clean run-up).</summary>
        static void NorthRow()
        {
            float spawnZ = 89f;
            // O6: ramp 6 m long, 1.2 m high, 4 m wide; landing pad 25 m beyond the lip
            float lipZ = 20f;
            Prism("O6_Ramp", new[] { new Vector2(-2f, 0f), new Vector2(2f, 0f), new Vector2(2f, 1.2f), new Vector2(-2f, 1.2f) }, 0f,
                new Vector3(-135f, 0f, lipZ + 3f), Quaternion.identity, concrete, "concrete", ramp: true);
            Box("O6_LandingPad", new Vector3(-135f, -0.04f, lipZ - 25f), new Vector3(10f, 0.1f, 20f), Quaternion.identity, concrete, "concrete");
            Paint(new Vector3(-140f, 0f, lipZ - 25f), new Vector3(-130f, 0f, lipZ - 25f), 0.2f, paintYellow);
            Record("O6", "ramp and landing pad", new Vector3(-135f, 0.6f, lipZ + 3f), new Vector3(4f, 1.2f, 6f), "concrete",
                $"\"ramp_length_m\": 6.0, \"ramp_height_m\": 1.2, \"ramp_angle_deg\": {F(Mathf.Atan2(1.2f, 6f) * Mathf.Rad2Deg)}, \"landing_beyond_lip_m\": 25.0, \"landing_pad_m\": [10, 20]");
            Lane("O6", 6, new Vector3(-135f, 0f, spawnZ), 180f, lipZ + 6f, 80f, "O6 RAMP 6 x 1.2 m");

            // O7: speed bump 0.10 m x 3 m (circular arc), then a 0.15 m curb across the lane at 45 deg
            var arc = new List<Vector2>();
            const int seg = 10;
            float chord = 3f, hgt = 0.10f, rad = (chord * chord / 4f + hgt * hgt) / (2f * hgt);
            for (int k = 0; k <= seg; k++)
            {
                float x = -0.5f * chord + chord * k / seg;
                arc.Add(new Vector2(x, Mathf.Max(0f, Mathf.Sqrt(rad * rad - x * x) - (rad - hgt))));
            }
            Prism("O7_SpeedBump", arc.ToArray(), 6f, new Vector3(-105f, 0f, 25f), Quaternion.Euler(0f, 90f, 0f), concrete, "asphalt");
            Box("O7_Curb", new Vector3(-105f, 0.075f, 5f), new Vector3(0.3f, 0.15f, 10f), Quaternion.Euler(0f, 45f, 0f), concrete, "concrete");
            Record("O7", "speed bump and curb", new Vector3(-105f, 0.05f, 25f), new Vector3(6f, 0.10f, 3f), "asphalt",
                "\"bump_height_m\": 0.10, \"bump_length_m\": 3.0, \"curb_height_m\": 0.15, \"curb_angle_deg\": 45, \"curb_z\": 5.0");
            Lane("O7", 7, new Vector3(-105f, 0f, spawnZ), 180f, 26.5f, 30f, "O7 BUMP 0.10 m + CURB 0.15 m");

            // O8: debris field (soft bodies): 8 cones, 12 barrels, 20 boxes, a fence of 6 panels across the lane
            var fieldGo = new GameObject("O8_DebrisField");
            fieldGo.transform.SetParent(root, false);
            var field = fieldGo.AddComponent<PropField>();
            field.barrelMaterial = EditorAssets.Lit("Barrel", new Color(0.12f, 0.27f, 0.6f), 0.45f, 0.3f);
            field.boxMaterial = EditorAssets.Lit("Cardboard", new Color(0.62f, 0.47f, 0.3f), 0.1f);
            field.coneMaterial = rubber;
            field.fenceMaterial = wood;
            float fx = -70f;
            for (int k = 0; k < 8; k++)
                field.props.Add(new PropField.Spot { kind = PropFactory.Kind.Cone, position = new Vector3(fx + (k % 2 == 0 ? -1.4f : 1.4f), 0f, 25f - 2.5f * k) });
            for (int r = 0; r < 3; r++)
                for (int c = 0; c < 4; c++)
                    field.props.Add(new PropField.Spot { kind = PropFactory.Kind.Barrel, position = new Vector3(fx - 1.02f + 0.68f * c, 0f, 3.5f - 0.68f * r) });
            int boxes = 0;
            for (int c = 0; c < 6 && boxes < 20; c++)
                for (int r = 0; r < 2 && boxes < 20; r++, boxes++)
                    field.props.Add(new PropField.Spot { kind = PropFactory.Kind.Box, position = new Vector3(fx - 1.55f + 0.62f * c, 0f, -3.5f - 0.62f * r) });
            for (int c = 0; c < 4 && boxes < 20; c++)
                for (int r = 0; r < 2 && boxes < 20; r++, boxes++)
                    field.props.Add(new PropField.Spot { kind = PropFactory.Kind.Box, position = new Vector3(fx - 0.93f + 0.62f * c, PropFactory.BoxSize + PropField.SpawnGap, -3.5f - 0.62f * r) });
            for (int k = 0; k < 6; k++)
                field.props.Add(new PropField.Spot { kind = PropFactory.Kind.FencePanel, position = new Vector3(fx - 7.25f + 2.42f * k + 1.2f, 0f, -9f) });
            Record("O8", "debris field", new Vector3(fx, 0f, 8f), new Vector3(15f, 1.2f, 36f), "asphalt",
                $"\"barrels\": 12, \"barrel_m\": [{F(2f * PropFactory.BarrelRadius)}, {F(PropFactory.BarrelHeight)}], \"barrel_kg\": {F(PropFactory.BarrelMass)}, " +
                $"\"boxes\": 20, \"box_m\": {F(PropFactory.BoxSize)}, \"box_kg\": {F(PropFactory.BoxMass)}, \"cones\": 8, \"cone_m\": {F(PropFactory.ConeHeight)}, " +
                $"\"cone_kg\": {F(PropFactory.ConeMass)}, \"fence_panels\": 6, \"fence_panel_m\": [{F(PropFactory.FenceWidth)}, {F(PropFactory.FenceHeight)}], \"fence_panel_kg\": {F(PropFactory.FenceMass)}");
            Lane("O8", 8, new Vector3(fx, 0f, spawnZ), 180f, 25.3f, 15f, "O8 DEBRIS FIELD", holdThrough: true);

            // O9: access ramp (30 m, 3 m rise) to a plateau whose south edge is a 3 m ledge over a lower pad; a 30 deg bank beside it
            Prism("O9_AccessRamp", new[] { new Vector2(-5f, 0f), new Vector2(5f, 0f), new Vector2(5f, 3f), new Vector2(-5f, 3f) }, 0f,
                new Vector3(-40f, 0f, 55f), Quaternion.identity, concrete, "concrete", ramp: true, rampLength: 30f);
            Box("O9_Plateau", new Vector3(-40f, 1.5f, 32.5f), new Vector3(10f, 3f, 15f), Quaternion.identity, concrete, "concrete");
            Box("O9_LowerPad", new Vector3(-40f, -0.04f, 10f), new Vector3(16f, 0.1f, 30f), Quaternion.identity, concrete, "concrete");
            Record("O9", "3 m ledge with lower pad", new Vector3(-40f, 1.5f, 32.5f), new Vector3(10f, 3f, 15f), "concrete",
                "\"ledge_height_m\": 3.0, \"ledge_z\": 25.0, \"access_ramp_m\": 30.0, \"lower_pad_m\": [16, 30]");
            Lane("O9", 9, new Vector3(-40f, 0f, spawnZ), 180f, 25f, 40f, "O9 LEDGE 3 m", holdThrough: true);
            float bankH = 4f, bankW = bankH / Mathf.Tan(30f * Mathf.Deg2Rad);
            Prism("O9_Bank30", new[] { new Vector2(0f, 0f), new Vector2(bankW, bankH), new Vector2(bankW + 1f, 0f) }, 24f,
                new Vector3(-17f, 0f, 14f), Quaternion.Euler(0f, 180f, 0f), grass, "grass");
            Record("O9b", "30 deg bank", new Vector3(-17f - 0.5f * bankW, 0.5f * bankH, 14f), new Vector3(bankW, bankH, 24f), "grass",
                $"\"angle_deg\": 30, \"height_m\": {F(bankH)}, \"foot_x\": -17.0, \"z_range\": [2, 26]");
            Lane("O9b", 10, new Vector3(-14f, 0f, spawnZ), 180f, 26f, 40f, "O9 BANK 30 deg (steer right)", holdThrough: true);
        }

        static void East()
        {
            // skidpad circle R 30 m and the open area
            const int n = 72;
            var c = new Vector3(100f, 0f, 40f);
            for (int k = 0; k < n; k++)
            {
                float a0 = 2f * Mathf.PI * k / n, a1 = 2f * Mathf.PI * (k + 1) / n;
                Paint(c + 30f * new Vector3(Mathf.Cos(a0), 0f, Mathf.Sin(a0)), c + 30f * new Vector3(Mathf.Cos(a1), 0f, Mathf.Sin(a1)), 0.15f, paintWhite);
            }
            Text("SKIDPAD R 30 m", c + new Vector3(0f, 0f, -33f), 0f, 0.6f);
            Record("skidpad", "skidpad circle", c, new Vector3(60f, 0f, 60f), "asphalt", "\"radius_m\": 30");
        }

        // ------------------------------------------------------------------ pieces

        static GameObject Box(string name, Vector3 c, Vector3 size, Quaternion rot, Material mat, string surface)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            Object.DestroyImmediate(go.GetComponent<Collider>());
            go.transform.SetParent(root, false);
            go.transform.SetPositionAndRotation(c, rot);
            go.transform.localScale = size;
            go.GetComponent<MeshRenderer>().sharedMaterial = mat;
            go.AddComponent<StaticBoxSource>().surface = surface;
            return go;
        }

        /// <summary>A convex prism; with <paramref name="ramp"/> the profile is replaced by a wedge of length
        /// <paramref name="rampLength"/> whose height (the profile's height) rises towards the object's -z (low edge at
        /// +rampLength/2, vertical high edge at -rampLength/2) and whose width is the profile's width.</summary>
        static GameObject Prism(string name, Vector2[] profile, float length, Vector3 pos, Quaternion rot, Material mat, string surface,
            bool ramp = false, float rampLength = 6f)
        {
            var go = new GameObject(name);
            go.transform.SetParent(root, false);
            go.transform.SetPositionAndRotation(pos, rot);
            go.AddComponent<MeshFilter>();
            go.AddComponent<MeshRenderer>().sharedMaterial = mat;
            var p = go.AddComponent<StaticPrismSource>();
            p.surface = surface;
            if (ramp)
            {
                // the wedge's side profile in the prism's x-y plane, extruded along its z (the width); turned by -90 deg
                // about y the prism's +x becomes the object's +z, so the high edge (x = -L/2) lies towards -z
                float w = profile[1].x - profile[0].x, h = profile[2].y;
                p.profile = new[] { new Vector2(-0.5f * rampLength, 0f), new Vector2(0.5f * rampLength, 0f), new Vector2(-0.5f * rampLength, h) };
                p.length = w;
                go.transform.rotation = rot * Quaternion.Euler(0f, -90f, 0f);
            }
            else
            {
                p.profile = profile;
                p.length = length;
            }
            p.BuildMesh();
            return go;
        }

        /// <summary>Jersey (F-shape) barrier: two convex prisms (base 0.61 m, 0.33 m break at 0.25 m wide, top 0.15 m at 0.81 m).</summary>
        static void Jersey(string name, Vector3 c, Quaternion rot)
        {
            var lower = new[] { new Vector2(-0.305f, 0f), new Vector2(0.305f, 0f), new Vector2(0.305f, 0.075f), new Vector2(0.127f, 0.33f),
                new Vector2(-0.127f, 0.33f), new Vector2(-0.305f, 0.075f) };
            var upper = new[] { new Vector2(-0.127f, 0.33f), new Vector2(0.127f, 0.33f), new Vector2(0.075f, 0.81f), new Vector2(-0.075f, 0.81f) };
            Prism(name + "_Lower", lower, 3.66f, c, rot, concrete, "concrete");
            Prism(name + "_Upper", upper, 3.66f, c, rot, concrete, "concrete");
        }

        static void GrassBandAround()
        {
            float t = 0.01f;
            void Band(string n, Vector3 c, Vector3 s) => Box(n, c, s, Quaternion.identity, grass, "grass").transform.position += new Vector3(0f, -0.5f * s.y + 0.5f * t, 0f);
            Band("Grass_S", new Vector3(0f, 0f, -HalfZ + 0.5f * GrassBand), new Vector3(2f * HalfX, 0.2f, GrassBand));
            Band("Grass_N", new Vector3(0f, 0f, HalfZ - 0.5f * GrassBand), new Vector3(2f * HalfX, 0.2f, GrassBand));
            Band("Grass_W", new Vector3(-HalfX + 0.5f * GrassBand, 0f, 0f), new Vector3(GrassBand, 0.2f, 2f * HalfZ - 2f * GrassBand));
            Band("Grass_E", new Vector3(HalfX - 0.5f * GrassBand, 0f, 0f), new Vector3(GrassBand, 0.2f, 2f * HalfZ - 2f * GrassBand));
        }

        /// <summary>A lane: spawn point, painted centre line and edges, distance marks every 10 m before the obstacle, label.</summary>
        static void Lane(string id, int order, Vector3 spawn, float headingDeg, float faceZ, float kmh, string label, bool holdThrough = false)
        {
            var rot = Quaternion.Euler(0f, headingDeg, 0f);
            var fwd = rot * Vector3.forward;
            float run = Mathf.Abs(faceZ - spawn.z) / Mathf.Max(Mathf.Abs(fwd.z), 1e-3f);
            float clean = run - CarFront;
            var face = spawn + fwd * run;
            var right = rot * Vector3.right;
            Paint(spawn + fwd * 3f, face - fwd * 1f, 0.12f, paintWhite, dashed: true);
            Paint(spawn - right * 2.2f, face - right * 2.2f - fwd * 0.5f, 0.1f, paintWhite);
            Paint(spawn + right * 2.2f, face + right * 2.2f - fwd * 0.5f, 0.1f, paintWhite);
            for (int m = 10; m <= 60 && m < run; m += 10)
            {
                var at = face - fwd * m;
                Paint(at - right * 2.2f, at - right * 1.4f, 0.15f, paintWhite);
                Text($"{m}", at - right * 3.2f, headingDeg, 0.35f);
            }
            Text(label, spawn - fwd * 4f, headingDeg, 0.45f);
            SpawnAt(label, order, spawn, headingDeg, run, kmh).GetComponent<SpawnPoint>().holdThrough = holdThrough;
            lanes.Add($"{{\"id\": \"{id}\", \"spawn\": [{F(spawn.x)}, {F(spawn.z)}], \"heading_deg\": {F(headingDeg)}, \"face\": [{F(face.x)}, {F(face.z)}], " +
                      $"\"run_m\": {F(run)}, \"clean_run_m\": {F(clean)}, \"default_kmh\": {F(kmh)}}}");
        }

        static Transform SpawnAt(string label, int order, Vector3 pos, float headingDeg, float approach, float kmh)
        {
            var go = new GameObject($"Spawn_{order}_{label}");
            go.transform.SetParent(root, false);
            go.transform.SetPositionAndRotation(pos, Quaternion.Euler(0f, headingDeg, 0f));
            var sp = go.AddComponent<SpawnPoint>();
            sp.label = label;
            sp.order = order;
            sp.approachDistance = approach;
            sp.defaultKmh = kmh;
            return go.transform;
        }

        static void Paint(Vector3 a, Vector3 b, float width, Material mat, bool dashed = false)
        {
            var d = b - a;
            float len = d.magnitude;
            if (len < 1e-3f) return;
            var dir = d / len;
            if (dashed)
            {
                for (float s = 0f; s < len; s += 6f)
                    Paint(a + dir * s, a + dir * Mathf.Min(s + 3f, len), width, mat);
                return;
            }
            var go = GameObject.CreatePrimitive(PrimitiveType.Quad);
            go.name = "Paint";
            Object.DestroyImmediate(go.GetComponent<Collider>());
            go.transform.SetParent(marks, false);
            go.transform.position = 0.5f * (a + b) + new Vector3(0f, 0.004f, 0f);
            go.transform.rotation = Quaternion.LookRotation(Vector3.down, dir);   // quad faces up, its y along the line
            go.transform.localScale = new Vector3(width, len, 1f);
            var mr = go.GetComponent<MeshRenderer>();
            mr.sharedMaterial = mat;
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        }

        static void Text(string s, Vector3 pos, float headingDeg, float size)
        {
            var go = new GameObject("Mark_" + s);
            go.transform.SetParent(marks, false);
            go.transform.position = pos + new Vector3(0f, 0.01f, 0f);
            go.transform.rotation = Quaternion.Euler(90f, headingDeg, 0f);
            var tm = go.AddComponent<TextMesh>();
            var font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            tm.font = font;
            tm.text = s;
            tm.characterSize = size;
            tm.fontSize = 48;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.color = new Color(0.95f, 0.95f, 0.92f);
            var mr = go.GetComponent<MeshRenderer>();
            mr.sharedMaterial = font.material;
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        }

        // ------------------------------------------------------------------ layout file

        static string F(float v) => v.ToString("0.###", Ic);

        static void Record(string id, string what, Vector3 centre, Vector3 size, string surface, string extra = "")
        {
            layout.Add($"{{\"id\": \"{id}\", \"what\": \"{what}\", \"centre\": [{F(centre.x)}, {F(centre.y)}, {F(centre.z)}], " +
                       $"\"size\": [{F(size.x)}, {F(size.y)}, {F(size.z)}], \"surface\": \"{surface}\"{(extra.Length > 0 ? ", " + extra : "")}}}");
        }

        static void WriteLayout()
        {
            string dir = Path.Combine(VehicleAssetSync.ProjectRoot, "docs", "p5");
            Directory.CreateDirectory(dir);
            var sb = new StringBuilder("{\n");
            sb.Append($"  \"scene\": \"{ScenePath}\",\n  \"extent_m\": [{F(2f * HalfX)}, {F(2f * HalfZ)}],\n  \"axes\": \"x east, z north, y up; origin at the centre\",\n");
            sb.Append("  \"surfaces\": {\"asphalt\": 1.0, \"concrete\": 0.9, \"grass\": 0.6, \"steel\": 0.6, \"note\": \"frictionScale x the node contact material's friction (params.json)\"},\n");
            sb.Append("  \"obstacles\": [\n    " + string.Join(",\n    ", layout) + "\n  ],\n");
            sb.Append("  \"lanes\": [\n    " + string.Join(",\n    ", lanes) + "\n  ]\n}\n");
            File.WriteAllText(Path.Combine(dir, "map_layout.json"), sb.ToString());
        }
    }
}
