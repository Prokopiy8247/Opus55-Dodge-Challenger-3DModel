using System;
using System.Collections.Generic;
using Hellcat.Sim.Data;
using Hellcat.Sim.Vehicle;
using Unity.Mathematics;
using static Hellcat.Sim.Validation.ValidationSuite;

namespace Hellcat.Sim.Validation
{
    /// <summary>X20 (diagnostic): the T6 drop from 0.2 m for parameter variants - settle time, residual node speed, the fastest
    /// nodes and the frequency of the residual ringing (zero crossings of the fastest node's velocity at 2 kHz sampling).</summary>
    public static class DropDiagnostics
    {
        static readonly DriverInput Parked = new DriverInput { brake = 1f, handbrake = 1f, gear = 0 };

        public static TestResult DropVariants(ValidationContext ctx)
        {
            var r = new TestResult();
            Action<SimParamsDef> Windup(string set, float kScale, float cScale) => p =>
            {
                foreach (var wu in p.windup)
                    if (set == "" || wu.name == set)
                    {
                        wu.camberStiffness *= kScale; wu.toeStiffness *= kScale;
                        wu.camberDamping *= cScale; wu.toeDamping *= cScale;
                    }
            };
            Action<SimParamsDef> Mat(string name, float spring) => p =>
            {
                foreach (var m in p.materials)
                    if (m.name == name) m.spring = spring;
            };
            int Node(VehicleDef d, string n) => Array.FindIndex(d.nodes, x => x.name == n);
            // front anti-roll-bar link back on the lower arm's shock node, the lever tips back at x 0.62 (before D-051)
            Action<VehicleDef> OldArbPick = d =>
            {
                foreach (var s in new[] { "R", "L" })
                {
                    int lbj = Node(d, $"F{s}_lbj"), sh = Node(d, $"F{s}_lca_sh"), tip = Node(d, $"arbF_tip_{s}");
                    foreach (var bm in d.beams)
                        if (bm.mat == "arb_link" && (bm.a == tip || bm.b == tip))
                        {
                            if (bm.a == lbj) bm.a = sh;
                            if (bm.b == lbj) bm.b = sh;
                        }
                    d.nodes[tip].p[0] = (s == "R" ? 1f : -1f) * 0.62f;
                }
            };
            Action<VehicleDef> EqualKnuckle = d =>
            {
                foreach (var s in new[] { "R", "L" })
                {
                    var ids = new[] { "lbj", "ubj", "tre", "axle_in", "axle_out" };
                    float tot = 0f;
                    foreach (var k in ids) tot += d.nodes[Node(d, $"F{s}_{k}")].m;
                    foreach (var k in ids) d.nodes[Node(d, $"F{s}_{k}")].m = tot / ids.Length;
                }
            };
            Action<VehicleDef> OldTre = d =>
            {
                foreach (var s in new[] { "R", "L" })
                    d.nodes[Node(d, $"F{s}_tre")].p[0] = (s == "R" ? 1f : -1f) * 0.735f;
            };
            Action<VehicleDef> Tips062 = d =>
            {
                foreach (var s in new[] { "R", "L" })
                    d.nodes[Node(d, $"arbF_tip_{s}")].p[0] = (s == "R" ? 1f : -1f) * 0.62f;
            };
            Action<SimParamsDef> Bushings = p =>
            {
                foreach (var m in p.materials)
                {
                    if (m.name == "arm" || m.name == "link" || m.name == "subframe_mount") m.damp = 300f;
                    if (m.name == "knuckle_f") m.damp = 600f;
                }
            };
            Action<SimParamsDef> TireRate(float rate) => p => { foreach (var g in p.dampGroupMaterials) if (g.name == "tire") g.rate = rate; };
            Action<SimParamsDef> Steer(float c) => p => { foreach (var wu in p.windup) if (wu.name == "front") wu.steerDamping = c; };
            var variants = new List<(string name, Action<SimParamsDef> tweak, Action<VehicleDef> defTweak)>
            {
                ("base", null, null),
                ("tips 0.62 + steering damper 15", Steer(15f), Tips062),
                ("tips 0.62 + steering damper 30", Steer(30f), Tips062),
                ("tips 0.62 + steering damper 30 + bushings", p => { Steer(30f)(p); Bushings(p); }, Tips062),
                ("tips 0.62 + steering damper 30 + bushings + tire rate 8", p => { Steer(30f)(p); Bushings(p); TireRate(8f)(p); }, Tips062),
                ("tips 0.70 + steering damper 30 + bushings", p => { Steer(30f)(p); Bushings(p); }, null),
            };
            foreach (var (name, tweak, defTweak) in variants)
            {
                var (def, prm) = LoadHellcat(ctx);
                tweak?.Invoke(prm);
                defTweak?.Invoke(def);
                using var w = new SoftBodyWorld(prm) { trackEnergy = false };
                int bi = w.AddBody("hellcat", def, prm, float3.zero, quaternion.identity, float3.zero, true);
                w.bodies[bi].spawnClearance = 0.2f;
                w.Build(Ground());
                var b = w.bodies[bi];
                w.SetInput(b.vehicleIndex, Parked);
                double firstContact = -1, lastMoving = 0, maxLate = 0;
                const double T = 8.0;
                string mid = "";
                Run(w, T, 20, t =>
                {
                    if (mid == "" && t >= 4.0)
                        mid = Ringing(w, b);
                    double vmax = 0, cn = 0;
                    for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                    {
                        vmax = math.max(vmax, math.length(w.vel[i]));
                        cn += w.contactFn[i];
                    }
                    if (firstContact < 0 && cn > 0) firstContact = t;
                    if (vmax >= 0.01) lastMoving = t;
                    if (t >= T / 2) maxLate = math.max(maxLate, vmax);
                    return true;
                });
                // the fastest nodes now, then 0.5 s of the fastest one's velocity at every step
                var speed = new List<(float v, int i)>();
                for (int i = 0; i < b.nodeCount; i++) speed.Add((math.length(w.vel[b.nodeStart + i]), i));
                speed.Sort((x, y) => y.v.CompareTo(x.v));
                int probe = b.nodeStart + speed[0].i;
                float3 dir = math.normalizesafe(w.vel[probe], new float3(1f, 0f, 0f));
                var vs = new List<double>();
                for (int k = 0; k < 1000; k++)
                {
                    w.Step(1);
                    vs.Add(math.dot(w.vel[probe], dir));
                }
                double mean = 0;
                foreach (var v in vs) mean += v;
                mean /= vs.Count;
                int cross = 0;
                double amp = 0;
                for (int k = 1; k < vs.Count; k++)
                {
                    if ((vs[k - 1] - mean) * (vs[k] - mean) < 0) cross++;
                    amp = math.max(amp, math.abs(vs[k] - mean));
                }
                double freq = cross / 2.0 / (vs.Count * w.dt);
                var top = new List<string>();
                for (int k = 0; k < 5; k++) top.Add($"{b.def.nodes[speed[k].i].name} {speed[k].v * 1000:F1}");
                r.Info($"{name}: settle time after the first contact (all nodes < 1 cm/s)", lastMoving - math.max(firstContact, 0), "s",
                    $"max node speed over the second half {maxLate * 1000:F1} mm/s; at 4 s: {mid}; at {T:F0} s fastest (mm/s): {string.Join(", ", top)}; " +
                    $"ringing of {b.def.nodes[speed[0].i].name}: {freq:F0} Hz, amplitude {amp * 1000:F2} mm/s");
            }
            return r;
        }

        /// <summary>The peak speed of every node over the next 0.1 s (every step), the five fastest, and the ringing frequency of the
        /// fastest one (zero crossings of its velocity along its peak direction).</summary>
        static string Ringing(SoftBodyWorld w, SoftBodyWorld.Body b)
        {
            var peak = new float[b.nodeCount];
            var hist = new List<float3>[b.nodeCount];
            for (int i = 0; i < b.nodeCount; i++) hist[i] = new List<float3>();
            for (int k = 0; k < 200; k++)
            {
                w.Step(1);
                for (int i = 0; i < b.nodeCount; i++)
                {
                    float3 v = w.vel[b.nodeStart + i];
                    peak[i] = math.max(peak[i], math.length(v));
                    hist[i].Add(v);
                }
            }
            var order = new List<int>();
            for (int i = 0; i < b.nodeCount; i++) order.Add(i);
            order.Sort((x, y) => peak[y].CompareTo(peak[x]));
            int f0 = order[0];
            float3 dir = float3.zero;
            foreach (var v in hist[f0]) if (math.lengthsq(v) > math.lengthsq(dir)) dir = v;
            dir = math.normalizesafe(dir, new float3(1f, 0f, 0f));
            int cross = 0;
            for (int k = 1; k < hist[f0].Count; k++)
                if (math.dot(hist[f0][k - 1], dir) * math.dot(hist[f0][k], dir) < 0f) cross++;
            var top = new List<string>();
            for (int k = 0; k < 5; k++) top.Add($"{b.def.nodes[order[k]].name} {peak[order[k]] * 1000:F0}");
            return $"peak (mm/s) {string.Join(", ", top)}; {b.def.nodes[f0].name} rings at {cross / 2.0 / (200 * w.dt):F0} Hz along ({dir.x:F2}, {dir.y:F2}, {dir.z:F2})";
        }
    }
}
