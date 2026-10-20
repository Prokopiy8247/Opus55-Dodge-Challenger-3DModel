using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using Hellcat.Game.Cameras;
using Hellcat.Game.Capture;
using Hellcat.Game.Core;
using Hellcat.Game.UI;
using Hellcat.Game.World;
using Hellcat.Sim;
using Hellcat.Sim.Validation;
using Unity.Mathematics;
using UnityEngine;

namespace Hellcat.Game.Scenario
{
    /// <summary>
    /// P5 map check (<c>-scenario mapcheck</c> in the test-map player, D-082): (1) the debris settles: 6 s at rest, then the
    /// props' largest node speed and drift; (2) screenshots: the whole map top-down (orthographic, 10 px per metre) and a
    /// perspective view down every lane; (3) one run per lane with the teleport speed hold (D-080): O1 / O2 / O3 at 30 km/h,
    /// O4 40, O5 50, O6 60 (jump), O7 at 30 and 50 km/h (the brief's curbs and bumps at 30-50 km/h without self-destruction),
    /// O8 20 (debris), O9 30 (off the ledge): speed at the obstacle, damage, airborne time, debris moved, and the solver's
    /// health (non-finite values, nodes under the ground, nodes inside an obstacle). Writes mapcheck.json and the images.
    /// </summary>
    public class MapCheck : MonoBehaviour
    {
        public SimRunner runner;
        public CameraRig cameras;
        public GameControls controls;
        public Hud hud;
        public PropField props;

        readonly CultureInfo ic = CultureInfo.InvariantCulture;
        string outDir;
        readonly List<string> runs = new List<string>();

        static string Arg(string name, string fallback)
        {
            var a = Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++)
                if (a[i] == name)
                    return a[i + 1];
            return fallback;
        }

        void Start()
        {
            if (Arg("-scenario", "") != "mapcheck")
            {
                enabled = false;
                return;
            }
            string root = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", ".."));
            outDir = Arg("-mapOut", Path.Combine(root, "docs", "p5", "mapcheck"));
            Directory.CreateDirectory(outDir);
            StartCoroutine(Run());
        }

        string F(double v, string f = "F3") => double.IsFinite(v) ? v.ToString(f, ic) : "null";

        IEnumerator Run()
        {
            if (hud) hud.visible = false;
            for (int i = 0; i < 60; i++) yield return null;
            var spawns = FindObjectsByType<SpawnPoint>(FindObjectsInactive.Exclude).OrderBy(s => s.order).ToArray();

            // ---- 1. the debris at rest
            double settleStart = runner.SimTime;
            while (runner.SimTime - settleStart < 5.0) yield return null;
            float propSpeed = 0f;
            double t1 = runner.SimTime;
            while (runner.SimTime - t1 < 1.0)
            {
                propSpeed = math.max(propSpeed, PropNodeSpeed());
                yield return null;
            }
            int driftedCount = 0;
            float drift = props != null ? props.Displacement(0.05f, out driftedCount) : 0f;
            string movers = Movers();
            if (Arg("-mapSettleOnly", "0") == "1")
            {
                Write(propSpeed, drift, driftedCount, new List<double>(), movers);
                Application.Quit(0);
                yield break;
            }

            // ---- 2. screenshots
            TopDown();
            foreach (var sp in spawns)
                LaneShot(sp);
            Overview();

            // ---- 3. the lanes
            // speed and the time after reaching the obstacle (the run-up time is added from the lane length)
            var plan = new List<(string id, float kmh, double seconds)>
            {
                ("O1", 30f, 3.0), ("O2", 30f, 3.0), ("O3", 30f, 3.0), ("O4", 40f, 3.0), ("O5", 50f, 3.0), ("O6", 60f, 4.0),
                ("O7", 30f, 4.0), ("O7", 50f, 4.0), ("O8", 20f, 8.0), ("O9", 30f, 6.0),
            };
            var timing = new List<double>();
            foreach (var (id, kmh, seconds) in plan)
            {
                var sp = spawns.FirstOrDefault(s => s.label.StartsWith(id + " "));
                if (sp == null)
                {
                    runs.Add($"{{\"lane\": \"{id}\", \"error\": \"no spawn\"}}");
                    continue;
                }
                if (id == "O8" && props != null)
                    props.ResetAll();
                yield return LaneRun(id, sp, kmh, seconds, timing);
            }
            Write(propSpeed, drift, driftedCount, timing, movers);
            Debug.Log($"[MapCheck] done: {runs.Count} lane runs, results in {outDir}");
            yield return null;
            Application.Quit(0);
#if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
#endif
        }

        float PropNodeSpeed()
        {
            if (props == null) return 0f;
            var w = runner.World;
            float best = 0f;
            foreach (int bi in props.Bodies)
            {
                var b = w.bodies[bi];
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                    if (w.invMass[i] > 0f)
                        best = math.max(best, math.length(w.vel[i]));
            }
            return best;
        }

        IEnumerator LaneRun(string id, SpawnPoint sp, float kmh, double after, List<double> timing)
        {
            double seconds = (sp.approachDistance > 0f ? sp.approachDistance : 40f) / (kmh / 3.6) + after;
            controls.Teleport(sp, kmh);
            cameras.mode = CameraMode.Chase;
            var w = runner.World;
            var b = w.bodies[runner.VehicleBody];
            var probe = new CarProbe(w, runner.VehicleBody);
            double t0 = runner.SimTime;
            float releaseKmh = float.NaN, maxSpeed = 0f, minY = float.MaxValue, maxLift = 0f, deepest = 0f, maxNode = 0f;
            int nonFinite = 0;
            double airborne = 0.0, lastT = t0;
            float groundY0 = MinNodeY(w, b);
            int moved0 = 0;
            if (props != null) props.Displacement(0.05f, out moved0);
            double stepMs = 0.0;
            long substeps = 0;
            while (runner.SimTime - t0 < seconds)
            {
                yield return null;
                stepMs += runner.LastStepMs;
                substeps += runner.LastSubsteps;
                var m = w.Metrics(runner.VehicleBody, false);
                nonFinite = math.max(nonFinite, m.nonFinite);
                maxNode = math.max(maxNode, m.maxNodeSpeed);
                var st = w.vehicleState[runner.VehicleIndex];
                maxSpeed = math.max(maxSpeed, math.abs(st.speed));
                if (float.IsNaN(releaseKmh) && controls.approach != null && !controls.approach.Holding && runner.SimTime - t0 > 0.1)
                    releaseKmh = controls.approach.ReleaseSpeed * 3.6f;
                float lowest = MinNodeY(w, b);
                minY = math.min(minY, lowest);
                maxLift = math.max(maxLift, lowest - groundY0);
                if (!TiresTouching(w, b))
                    airborne += runner.SimTime - lastT;
                lastT = runner.SimTime;
                deepest = math.min(deepest, Penetration(w, b));
                if (m.nonFinite > 0) break;
            }
            timing.Add(stepMs * 1000.0 / math.max(substeps, 1));
            var mEnd = w.Metrics(runner.VehicleBody, false);
            var f = probe.Frame();
            int moved = 0;
            if (props != null) props.Displacement(0.05f, out moved);
            var brokenBy = new SortedDictionary<string, int>();
            for (int k = 0; k < b.beamCount; k++)
                if (w.broken[b.beamStart + k] != 0)
                {
                    string mat = b.def.beams[k].mat;
                    brokenBy[mat] = brokenBy.TryGetValue(mat, out int c) ? c + 1 : 1;
                }
            string brokenText = string.Join(", ", brokenBy.Select(kv => $"{kv.Key} {kv.Value}"));
            // bent beams by material with their largest plastic change of length (a count alone includes 0.01 mm flows)
            var bentBy = new SortedDictionary<string, (int n, float mm)>();
            float bentMax = 0f;
            for (int k = 0; k < b.beamCount; k++)
            {
                float d = math.abs(w.RestChange(b.beamStart + k)) * 1000f;
                if (d <= 0.01f || w.broken[b.beamStart + k] != 0)
                    continue;
                string mat = b.def.beams[k].mat;
                (int n, float mm) e = bentBy.TryGetValue(mat, out var c) ? c : (0, 0f);
                bentBy[mat] = (e.n + 1, math.max(e.mm, d));
                bentMax = math.max(bentMax, d);
            }
            string bentText = string.Join(", ", bentBy.Select(kv => $"{kv.Key} {kv.Value.n} (max {kv.Value.mm.ToString("F2", CultureInfo.InvariantCulture)} mm)"));
            yield return new WaitForEndOfFrame();
            FrameCapture.Save(cameras.GetComponent<Camera>(), Path.Combine(outDir, $"run_{id}_{kmh:F0}kmh.png"), 1600, 900);
            runs.Add($"{{\"lane\": \"{id}\", \"label\": \"{sp.label}\", \"target_kmh\": {F(kmh, "F0")}, \"release_kmh\": {F(releaseKmh, "F1")}, " +
                     $"\"release\": \"{(controls.approach != null ? controls.approach.ReleaseReason : "")}\", \"max_speed_kmh\": {F(maxSpeed * 3.6, "F1")}, " +
                     $"\"end_speed_kmh\": {F(math.abs(f.speed) * 3.6, "F1")}, \"broken_beams\": {mEnd.brokenBeams}, \"bent_beams\": {mEnd.plasticBeams}, " +
                     $"\"non_finite\": {nonFinite}, \"lowest_node_m\": {F(minY)}, \"max_lift_m\": {F(maxLift)}, \"airborne_s\": {F(airborne)}, " +
                     $"\"deepest_in_obstacle_m\": {F(-deepest)}, \"max_node_speed\": {F(maxNode, "F2")}, \"up_end\": {F(f.up.y, "F3")}, " +
                     $"\"props_moved\": {math.max(0, moved - moved0)}, \"broken_by_material\": \"{brokenText}\", " +
                     $"\"bent_by_material\": \"{bentText}\", \"bent_max_mm\": {F(bentMax, "F2")}}}");
            Debug.Log($"[MapCheck] {id} at {kmh:F0} km/h: released at {releaseKmh:F1} km/h, broken {mEnd.brokenBeams}, bent {mEnd.plasticBeams}, " +
                      $"airborne {airborne:F2} s, deepest {-deepest * 1000:F0} mm, props moved {math.max(0, moved - moved0)}");
        }

        /// <summary>Any tread node with a contact force (static or dynamic) this substep.</summary>
        static bool TiresTouching(SoftBodyWorld w, SoftBodyWorld.Body b)
        {
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                if ((w.nodeFlags[i] & NodeFlag.Tire) != 0 && w.contactFn[i] > 0f)
                    return true;
            return false;
        }

        static float MinNodeY(SoftBodyWorld w, SoftBodyWorld.Body b)
        {
            float y = float.MaxValue;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                y = math.min(y, w.pos[i].y);
            return y;
        }

        /// <summary>Deepest signed distance of a static-colliding car node inside a non-plane obstacle (negative = inside).</summary>
        static float Penetration(SoftBodyWorld w, SoftBodyWorld.Body b)
        {
            float worst = 0f;
            float3 c = w.pos[b.nodeStart];
            for (int p = 0; p < w.prims.Length; p++)
            {
                var prim = w.prims[p];
                if (prim.type == PrimType.Plane) continue;
                if (math.any(c < prim.aabbMin - 8f) || math.any(c > prim.aabbMax + 8f)) continue;
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                {
                    if ((w.nodeFlags[i] & NodeFlag.StaticCollision) == 0) continue;
                    worst = math.min(worst, StaticSdf.Distance(prim, w.planes, w.pos[i], out _));
                }
            }
            return worst;
        }

        // ------------------------------------------------------------------ screenshots

        Camera ShotCamera()
        {
            var go = new GameObject("ShotCamera");
            var cam = go.AddComponent<Camera>();
            cam.enabled = false;
            CameraSky.Apply(cam);
            cam.farClipPlane = 2000f;
            return cam;
        }

        void TopDown()
        {
            var cam = ShotCamera();
            cam.orthographic = true;
            cam.orthographicSize = 101f;
            cam.transform.SetPositionAndRotation(new Vector3(0f, 300f, 0f), Quaternion.Euler(90f, 0f, 0f));
            FrameCapture.Save(cam, Path.Combine(outDir, "map_topdown.png"), 3030, 2020);
            Destroy(cam.gameObject);
        }

        void Overview()
        {
            var cam = ShotCamera();
            cam.fieldOfView = 40f;
            var from = new Vector3(-175f, 70f, -150f);
            cam.transform.SetPositionAndRotation(from, Quaternion.LookRotation(new Vector3(-40f, 0f, 0f) - from, Vector3.up));
            FrameCapture.Save(cam, Path.Combine(outDir, "map_overview.png"), 1920, 1080);
            Destroy(cam.gameObject);
        }

        void LaneShot(SpawnPoint sp)
        {
            var cam = ShotCamera();
            cam.fieldOfView = 45f;
            var fwd = sp.transform.forward;
            float run = sp.approachDistance > 0f ? sp.approachDistance : 30f;
            var target = sp.transform.position + fwd * run;
            var from = target - fwd * 22f + Vector3.up * 7f + sp.transform.right * 9f;
            cam.transform.SetPositionAndRotation(from, Quaternion.LookRotation(target + Vector3.up * 0.8f - from, Vector3.up));
            string id = sp.label.Split(' ')[0];
            FrameCapture.Save(cam, Path.Combine(outDir, $"lane_{sp.order:D2}_{id}.png"), 1600, 900);
            Destroy(cam.gameObject);
        }

        /// <summary>The props that moved at rest: kind, index, drift from the start (m), fastest node (m/s).</summary>
        string Movers()
        {
            if (props == null) return "";
            var w = runner.World;
            var list = new List<(float d, string text)>();
            for (int k = 0; k < props.Bodies.Count; k++)
            {
                var b = w.bodies[props.Bodies[k]];
                float3 c = float3.zero, c0 = float3.zero;
                float v = 0f;
                int n = 0;
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                {
                    if (w.invMass[i] <= 0f) continue;
                    c += w.pos[i];
                    c0 += w.SpawnPosition(i);
                    v = math.max(v, math.length(w.vel[i]));
                    n++;
                }
                float d = math.distance(c / n, c0 / n);
                if (d > 0.02f || v > 0.05f)
                    list.Add((d, $"{props.props[k].kind} {k}: drift {d:F3} m, node speed {v:F3} m/s, height {(c / n).y:F2} m"));
            }
            return string.Join("; ", list.OrderByDescending(x => x.d).Take(12).Select(x => x.text));
        }

        void Write(float propSpeed, float drift, int drifted, List<double> timing, string movers)
        {
            var w = runner.World;
            int propBodies = props != null ? props.Bodies.Count : 0;
            int propNodes = 0;
            if (props != null)
                foreach (int bi in props.Bodies) propNodes += w.bodies[bi].nodeCount;
            var sb = new StringBuilder("{\n");
            sb.Append($"  \"scenario\": \"mapcheck\",\n  \"time_utc\": \"{DateTime.UtcNow:yyyy-MM-ddTHH:mm:ssZ}\",\n");
            sb.Append($"  \"world\": {{\"bodies\": {w.bodies.Count}, \"nodes\": {w.NodeCount}, \"beams\": {w.BeamCount}, \"static_primitives\": {w.prims.Length}, " +
                      $"\"prop_bodies\": {propBodies}, \"prop_nodes\": {propNodes}, \"stability_S\": {F(runner.Stability != null ? runner.Stability.exactS : double.NaN, "F4")}}},\n");
            sb.Append($"  \"settle\": {{\"prop_max_node_speed\": {F(propSpeed, "F4")}, \"prop_max_drift_m\": {F(drift, "F4")}, \"props_drifted_5cm\": {drifted}, \"movers\": \"{movers}\"}},\n");
            sb.Append($"  \"us_per_substep\": {F(timing.Count > 0 ? timing.Average() : double.NaN, "F1")},\n");
            sb.Append("  \"runs\": [\n    " + string.Join(",\n    ", runs) + "\n  ]\n}\n");
            File.WriteAllText(Path.Combine(outDir, "mapcheck.json"), sb.ToString());
        }
    }
}
