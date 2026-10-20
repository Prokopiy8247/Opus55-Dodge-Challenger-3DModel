using System;
using System.Collections.Generic;
using System.Linq;
using Hellcat.Sim.Data;
using Hellcat.Sim.Vehicle;
using Unity.Mathematics;
using static Hellcat.Sim.Validation.ValidationSuite;

namespace Hellcat.Sim.Validation
{
    /// <summary>Validation tests 6-8 on the Hellcat skeleton, energy drift (G-Solver) and determinism.</summary>
    public static class VehicleTests
    {
        // parked: neutral (no parking pawl modelled), foot brake and handbrake
        static readonly DriverInput Parked = new DriverInput { brake = 1f, handbrake = 1f, gear = 0 };

        static SoftBodyWorld Hellcat(ValidationContext ctx, StaticWorldBuilder statics, float3 position, float3 velocity,
            float clearance, bool trackEnergy = true, Action<SimParamsDef> tweak = null, bool singleThread = false,
            Action<SoftBodyWorld> addMore = null)
        {
            var (def, prm) = LoadHellcat(ctx);
            tweak?.Invoke(prm);
            var w = new SoftBodyWorld(prm) { trackEnergy = trackEnergy, forceSingleThread = singleThread };
            int bi = w.AddBody("hellcat", def, prm, position, quaternion.identity, velocity, true);
            w.bodies[bi].spawnClearance = clearance;
            addMore?.Invoke(w);
            w.Build(statics ?? new StaticWorldBuilder());
            return w;
        }

        /// <summary>Plane fit of the body-part node heights against the model: dy = a + b x + c z (sag, roll, pitch).</summary>
        static void BodyPose(SoftBodyWorld w, out double sag, out double rollDeg, out double pitchDeg, out double frontSag, out double rearSag,
            bool cabinFloor = false)
        {
            var b = w.bodies[0];
            double sx = 0, sz = 0, sxx = 0, szz = 0, sxz = 0, sy = 0, sxy = 0, szy = 0;
            int n = 0;
            for (int i = 0; i < b.nodeCount; i++)
            {
                var nd = b.def.nodes[i];
                if (nd.part != "body")
                    continue;
                if (cabinFloor && !(nd.name.StartsWith("sill") || nd.name.StartsWith("floor") || nd.name.StartsWith("tunnel")))
                    continue;
                double x = nd.p[0], z = nd.p[2];
                double dy = w.pos[b.nodeStart + i].y - nd.p[1];
                sx += x; sz += z; sxx += x * x; szz += z * z; sxz += x * z; sy += dy; sxy += x * dy; szy += z * dy;
                n++;
            }
            // normal equations [n sx sz; sx sxx sxz; sz sxz szz] [a b c] = [sy sxy szy]
            var m = new double3x3(n, sx, sz, sx, sxx, sxz, sz, sxz, szz);
            double3 abc = math.mul(math.inverse(m), new double3(sy, sxy, szy));
            sag = abc.x;
            rollDeg = math.degrees(math.atan(abc.y));
            pitchDeg = math.degrees(math.atan(abc.z));
            frontSag = abc.x + abc.z * 1.4755;
            rearSag = abc.x - abc.z * 1.4755;
        }

        static double MaxNodeSpeed(SoftBodyWorld w, int bi)
        {
            var b = w.bodies[bi];
            double v = 0.0;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                v = math.max(v, math.length(w.vel[i]));
            return v;
        }

        /// <summary>Sum over the contacting nodes of the friction the contact law gives at their slip speed and load.</summary>
        static double LawFriction(SoftBodyWorld w, int bi, out double normal)
        {
            var b = w.bodies[bi];
            double f = 0.0;
            normal = 0.0;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
            {
                float fn = w.contactFn[i];
                if (fn <= 0f)
                    continue;
                var cm = w.cmats[w.nodeCmat[i]];
                int sid = w.contactSurface[i];
                float scale = sid >= 0 ? w.surfaces[sid].frictionScale : 1f;
                f += scale * ContactKernel.SlidingMu(cm, w.contactSlip[i]) * ContactKernel.LoadFactor(cm, fn) * fn;
                normal += fn;
            }
            return f;
        }

        /// <summary>Horizontal contact impulse applied to the body's nodes since the last ClearContactImp, projected on
        /// a direction. This is the honest reference for a friction test: the node's momentum change divided by the frame
        /// time is the mean force it felt, including the friction of the anti-tunnelling projection. The old check compared
        /// the measured deceleration against Coulomb friction alone (mu(slip) lf(load) fn), leaving out the sticking-anchor
        /// force the solver applies on top of it, and so reported a 12 % "error" that was pure bookkeeping (D-030).</summary>
        static double ImpulseAlong(SoftBodyWorld w, int bi, float3 dir)
        {
            var b = w.bodies[bi];
            double p = 0.0;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
            {
                float3 j = w.contactImp[i];
                if (!math.all(math.isfinite(j)))
                    continue;
                p += math.dot(j, dir);
            }
            return p;
        }

        // ------------------------------------------------------------------ T6

        public static TestResult CarDrop(ValidationContext ctx)
        {
            var r = new TestResult();
            void Scenario(string tag, float clearance, double seconds, bool stability)
            {
                using var w = Hellcat(ctx, Ground(), float3.zero, float3.zero, clearance);
                var b = w.bodies[0];
                if (stability)
                {
                    var sr = StabilityReport.Compute(w);
                    r.Max("exact stability S = lambda_max(M^-1 (dt^2 K + 2 dt C + D)) (D-024)", sr.exactS, StabilityReport.HardLimitS);
                    if (!double.IsNaN(ctx.referenceS))
                        r.Near("S without torsion bars and cord geometric stiffness vs tools/skeleton/stability.py", sr.exactSBeams, ctx.referenceS, 0.02);
                    r.Info("Lanczos iterations / seconds", sr.lanczosIterations, "", $"{sr.seconds:F2} s");
                    r.Info("Gershgorin max (warning only, D-024)", sr.maxGershgorin);
                    r.Info("omega*dt max (warning only)", sr.maxOmegaDt, "", $"{sr.omegaWarnings} nodes >= 0.5");
                    r.Info("tire cords pre-tensioned (D-028)", b.pretensionedBeams, "beams", $"max {b.pretensionMax:F0} N");
                    r.Max("tire pre-tension residual force at spawn", b.pretensionResidual, 0.01, "N");
                    r.Info("node / beam / collision triangle / pressure group counts", w.NodeCount, "",
                        $"{w.BeamCount} beams, {w.CollTriCount} triangles, {w.PressureGroupCount} pressure groups, {w.TorsionBarCount} torsion bars");
                }
                w.SetInput(b.vehicleIndex, Parked);
                if (tag == "spawn")
                {
                    // the car at rest on the ground (brief 10.6 acceptance): settled spawn (D-037), not a drop from the
                    // unloaded model pose
                    var swS = System.Diagnostics.Stopwatch.StartNew();
                    int resets = w.Settle(0);
                    r.Min("settled spawn (D-037) converged (kinetic energy peak < 1 mJ)", resets, 1, "resets");
                    r.Info("settled spawn: simulated / wall time", w.StepsTaken * (double)w.dt, "s", $"{swS.Elapsed.TotalSeconds:F2} s wall");
                }
                var wheelNames = new string[b.wheelCount];
                for (int k = 0; k < b.wheelCount; k++)
                    wheelNames[k] = b.def.wheels[k].name;
                var cols = new List<string> { "t", "com_y", "max_node_speed", "kinetic", "mechanical", "contact_N", "sag", "front_sag", "rear_sag", "pitch_deg", "roll_deg", "min_y", "broken", "plastic" };
                foreach (var nm in wheelNames) cols.Add($"load_{nm}");
                foreach (var nm in wheelNames) cols.Add($"pgauge_{nm}");
                // diagnostics: fore-aft / lateral centre of mass, momentum, wheel brake state
                cols.AddRange(new[] { "com_x", "com_z", "vel_x", "vel_z", "angmom_x", "angmom_y", "angmom_z" });
                foreach (var nm in wheelNames) { cols.Add($"omega_{nm}"); cols.Add($"stuck_{nm}"); cols.Add($"brakeT_{nm}"); cols.Add($"stickA_{nm}"); }
                var s = new Series(cols.ToArray());
                // node position snapshots over 1.2 s of the rest phase (mode shape of any residual oscillation)
                var snap = new Series("t", "node", "x", "y", "z");
                double firstContact = -1.0;
                long steps0 = w.StepsTaken;
                // ground reaction from the contact impulses (penalty and hard projection, the force plate of T7 / T9):
                // the penalty forces alone miss what the projection carries
                var probe6 = new CarProbe(w, 0);
                w.ClearContactImp();
                double tLast = w.StepsTaken * (double)w.dt;
                var wheelFz = new double[b.wheelCount];
                double stepSeconds = Run(w, seconds, 20, t =>
                {
                    var m = w.Metrics(0);
                    BodyPose(w, out double sag, out double roll, out double pitch, out double fs, out double rs);
                    double cn = 0.0, minY = double.MaxValue, span = math.max(t - tLast, 1e-9);
                    for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                    {
                        cn += w.contactImp[i].y / span;
                        minY = math.min(minY, w.pos[i].y);
                    }
                    for (int k = 0; k < b.wheelCount; k++)
                        wheelFz[k] = probe6.TreadImpulse(k).y / span;
                    w.ClearContactImp();
                    tLast = t;
                    if (firstContact < 0.0 && cn > 0.0)
                        firstContact = t;
                    var row = new List<double> { t, m.centerOfMass.y, m.maxNodeSpeed, m.kinetic, m.Mechanical, cn, sag, fs, rs, pitch, roll, minY, m.brokenBeams, m.plasticBeams };
                    for (int k = 0; k < b.wheelCount; k++) row.Add(wheelFz[k]);
                    for (int k = 0; k < b.wheelCount; k++)
                    {
                        var ps = w.pressureState[b.pressureStart + k];
                        row.Add(ps.pAbs - w.pressureGroups[b.pressureStart + k].pAtm);
                    }
                    row.AddRange(new double[] { m.centerOfMass.x, m.centerOfMass.z, m.velocity.x, m.velocity.z,
                        m.angularMomentum.x, m.angularMomentum.y, m.angularMomentum.z });
                    for (int k = 0; k < b.wheelCount; k++)
                    {
                        var ws = w.wheelState[b.wheelStart + k];
                        row.Add(ws.omega);
                        row.Add(ws.stuck);
                        row.Add(ws.brakeTorque);
                        row.Add(ws.stickAngle);
                    }
                    s.Add(row.ToArray());
                    if (t >= seconds - 1.2 - 1e-6)
                        for (int i = 0; i < b.nodeCount; i++)
                        {
                            float3 q = w.pos[b.nodeStart + i];
                            snap.Add(t, i, q.x, q.y, q.z);
                        }
                    return true;
                });
                s.Write(ctx.FilePath(r, $"{tag}.csv"));
                snap.Write(ctx.FilePath(r, $"{tag}_snap.csv"));
                long steps = w.StepsTaken - steps0;
                if (stability)
                {
                    r.Info("physics time per substep (Burst, parallel, editor)", stepSeconds / steps * 1e6, "us",
                        $"{(w.UsesSingleThread ? "single-thread" : "parallel")}; real-time at 2 kHz needs < 500 us");
                    r.Max("physics time per substep vs the 2 kHz real-time budget", stepSeconds / steps * 1e6, 500.0, "us");
                }
                // settling: the last sample where a node moved faster than 1 cm/s
                double lastMoving = 0.0;
                for (int i = 0; i < s.Count; i++)
                    if (s[i][2] >= 0.01)
                        lastMoving = s[i][0];
                double settle = math.max(0.0, lastMoving - math.max(firstContact, 0.0));
                var last = s[s.Count - 1];
                int restFrom = s.Count / 2;
                double sagMin = double.MaxValue, sagMax = double.MinValue, keMax = 0.0, eStart = s[restFrom][4];
                for (int i = restFrom; i < s.Count; i++)
                {
                    sagMin = math.min(sagMin, s[i][6]);
                    sagMax = math.max(sagMax, s[i][6]);
                    keMax = math.max(keMax, s[i][3]);
                }
                double mass = b.totalMass, g = w.worldParams.gravity;
                // static axle loads of the rigid body (centre of mass between the axles)
                double zf = 0.0, zr = 0.0;
                int nf = 0, nr = 0;
                for (int k = 0; k < b.wheelCount; k++)
                {
                    var wd = b.def.wheels[k];
                    double z = 0.5 * (b.def.nodes[wd.axleInner].p[2] + b.def.nodes[wd.axleOuter].p[2]);
                    if (wd.steered != 0) { zf += z; nf++; } else { zr += z; nr++; }
                }
                zf /= math.max(nf, 1);
                zr /= math.max(nr, 1);
                double comZ = 0.0;
                foreach (var nd in b.def.nodes)
                    comZ += nd.m * nd.p[2];
                comZ /= mass;
                double frontShare = (comZ - zr) / (zf - zr);
                double front = 0.0, rear = 0.0, left = 0.0, right = 0.0;
                for (int k = 0; k < b.wheelCount; k++)
                {
                    double ld = last[14 + k];
                    if (b.def.wheels[k].steered != 0) front += ld; else rear += ld;
                    if (b.def.wheels[k].name.EndsWith("L")) left += ld; else right += ld;
                }
                string p = tag == "spawn" ? "on the ground" : "drop 0.2 m";
                // at rest (settled spawn): brief 10 acceptance, 1 s. Drop from 0.2 m (2 m/s impact): every node below
                // 1 cm/s takes ln(v0 / 0.01) / (zeta omega) ~3.3-3.7 s for the design heave / pitch damping (zeta 0.32 /
                // 0.2 at 1.2 Hz, parked); 4 s still catches any mode below zeta ~0.15 (D-039)
                r.Max($"{p}: settle time after the first contact (all nodes < 1 cm/s)", settle, tag == "spawn" ? 1.0 : 4.0, "s");
                r.Max($"{p}: max node speed at rest (second half)", MaxOver(s, 2, restFrom), 0.01, "m/s");
                r.Max($"{p}: ride height drift at rest (max - min of the body sag, second half)", sagMax - sagMin, 0.02, "m");
                r.Max($"{p}: kinetic energy at rest (no energy gain)", keMax, 1.0, "J");
                r.Info($"{p}: mechanical energy change over the rest window", last[4] - eStart, "J");
                r.Near($"{p}: total ground reaction vs m g", last[5], mass * g, 0.01, "N");
                r.Near($"{p}: front axle load share vs centre of mass ({frontShare:P1})", front / (front + rear), frontShare, 0.03);
                r.Near($"{p}: left / right load balance", left / math.max(right, 1.0), 1.0, 0.03);
                r.Max($"{p}: broken beams", last[12], 0);
                r.Max($"{p}: plastically deformed beams", last[13], 0);
                r.Min($"{p}: lowest node height over the run (no ground penetration)", MinOver(s, 11, 0), -1e-4, "m");
                Diagnose(ctx, w, r, tag);
                if (tag == "spawn")
                {
                    r.NearAbs("ride height vs the model at rest: mean body sag", last[6], 0.0, 0.02, "m");
                    r.Info("ride height vs the model: front axle / rear axle", last[7], "m", $"rear {last[8]:F4} m");
                    r.Info("pitch / roll at rest", last[9], "deg", $"roll {last[10]:F3} deg");
                    for (int k = 0; k < b.wheelCount; k++)
                        r.Info($"wheel load {wheelNames[k]}", last[14 + k], "N",
                            $"target {(b.def.wheels[k].steered != 0 ? frontShare : 1 - frontShare) * mass * g / 2:F0} N");
                    for (int k = 0; k < b.wheelCount; k++)
                        r.Info($"tire gauge pressure {wheelNames[k]} at rest", last[14 + b.wheelCount + k] / 1000.0, "kPa", "spawn 241 kPa");
                    r.Info("spawn lift (D-026)", b.spawnLift, "m");
                }
            }
            Scenario("spawn", 0.01f, ctx.quick ? 4.0 : 8.0, true);
            Scenario("drop", 0.2f, ctx.quick ? 4.0 : 8.0, false);
            return r;
        }

        /// <summary>Notes for tuning: hub heights, suspension beam states, fastest nodes, non-tire ground contacts.</summary>
        static void Diagnose(ValidationContext ctx, SoftBodyWorld w, TestResult r, string tag)
        {
            var b = w.bodies[0];
            var def = b.def;
            var ic = System.Globalization.CultureInfo.InvariantCulture;
            for (int k = 0; k < b.wheelCount; k++)
            {
                var wd = def.wheels[k];
                float3 hub = 0.5f * (w.pos[b.nodeStart + wd.axleInner] + w.pos[b.nodeStart + wd.axleOuter]);
                float model = 0.5f * (def.nodes[wd.axleInner].p[1] + def.nodes[wd.axleOuter].p[1]);
                double lowTread = double.MaxValue;
                foreach (int tn in wd.tread)
                    lowTread = math.min(lowTread, w.pos[b.nodeStart + tn].y);
                r.notes.Add($"{tag} wheel {wd.name}: hub y {hub.y.ToString("F4", ic)} (model {model.ToString("F4", ic)}), lowest tread node y {lowTread.ToString("F4", ic)}, " +
                            $"load {w.wheelState[b.wheelStart + k].load.ToString("F0", ic)} N, omega {w.wheelState[b.wheelStart + k].omega.ToString("F3", ic)} rad/s");
            }
            for (int j = b.beamStart; j < b.beamStart + b.beamCount; j++)
            {
                var bd = def.beams[j - b.beamStart];
                if (!(bd.mat.StartsWith("spring") || bd.mat.StartsWith("damper") || bd.mat.StartsWith("bumpstop") || bd.mat == "stop"))
                    continue;
                var s = w.beams[j];
                float len = math.distance(w.pos[s.a], w.pos[s.b]);
                string bound = s.type == BeamType.Bounded ? $", bounds {s.shortLen.ToString("F4", ic)}..{(s.longLen < 1e6f ? s.longLen.ToString("F4", ic) : "inf")}" : "";
                r.notes.Add($"{tag} {bd.mat} {def.nodes[bd.a].name}-{def.nodes[bd.b].name} ({bd.type}): length {len.ToString("F4", ic)}, spawn {s.spawnLength.ToString("F4", ic)}, " +
                            $"rest {w.rest[j].ToString("F4", ic)}{bound}, force {math.length(w.beamForce[j]).ToString("F0", ic)} N");
            }
            var speeds = new List<(float v, int i)>();
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                speeds.Add((math.length(w.vel[i]), i));
            speeds.Sort((x, y) => y.v.CompareTo(x.v));
            for (int k = 0; k < 8; k++)
            {
                int i = speeds[k].i;
                r.notes.Add($"{tag} fast node {def.nodes[i - b.nodeStart].name}: |v| {speeds[k].v.ToString("F3", ic)} m/s, v {w.vel[i]}, y {w.pos[i].y.ToString("F4", ic)}, fn {w.contactFn[i].ToString("F0", ic)} N");
            }
            var touching = new List<string>();
            double other = 0.0;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                if (w.contactFn[i] > 0f && (w.nodeFlags[i] & NodeFlag.Tire) == 0)
                {
                    other += w.contactFn[i];
                    if (touching.Count < 12)
                        touching.Add($"{def.nodes[i - b.nodeStart].name} {w.contactFn[i].ToString("F0", ic)} N");
                }
            r.notes.Add($"{tag} non-tire nodes on the ground: {other.ToString("F0", ic)} N: " + string.Join(", ", touching));
            var lowest = new List<(float y, int i)>();
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                lowest.Add((w.pos[i].y, i));
            lowest.Sort((x, y) => x.y.CompareTo(y.y));
            var low = new List<string>();
            for (int k = 0; k < 6; k++)
                low.Add($"{def.nodes[lowest[k].i - b.nodeStart].name} {lowest[k].y.ToString("F4", ic)} (flags {w.nodeFlags[lowest[k].i]})");
            r.notes.Add($"{tag} lowest nodes: " + string.Join(", ", low));
            // damaged beams: material, nodes, rest change / broken
            var damaged = new Dictionary<string, int>();
            var examples = new List<string>();
            for (int j = b.beamStart; j < b.beamStart + b.beamCount; j++)
            {
                var bd = def.beams[j - b.beamStart];
                bool brk = w.broken[j] != 0;
                float dr = w.rest[j] - w.SpawnRest(j);
                if (!brk && math.abs(dr) <= 1e-5f)
                    continue;
                string key = $"{bd.mat}{(brk ? " broken" : " plastic")}";
                damaged[key] = damaged.TryGetValue(key, out int c) ? c + 1 : 1;
                if (examples.Count < 24)
                    examples.Add($"{bd.mat} {def.nodes[bd.a].name}-{def.nodes[bd.b].name} {(brk ? "broken" : $"rest {dr * 1000:F1} mm")}");
            }
            var dl = new List<string>();
            foreach (var kv in damaged)
                dl.Add($"{kv.Key} x{kv.Value}");
            r.notes.Add($"{tag} damaged beams: " + string.Join(", ", dl));
            r.notes.Add($"{tag} damaged examples: " + string.Join("; ", examples));
            // full node dump (model vs final position, speed) for offline analysis
            var dump = new System.Text.StringBuilder("name,part,mass,flags,mx,my,mz,x,y,z,speed,contact_N\n");
            for (int i = 0; i < b.nodeCount; i++)
            {
                var nd = def.nodes[i];
                float3 p = w.pos[b.nodeStart + i];
                dump.Append(nd.name).Append(',').Append(nd.part).Append(',').Append(nd.m.ToString("R", ic)).Append(',').Append(nd.flags).Append(',')
                    .Append(nd.p[0].ToString("R", ic)).Append(',').Append(nd.p[1].ToString("R", ic)).Append(',').Append(nd.p[2].ToString("R", ic)).Append(',')
                    .Append(p.x.ToString("R", ic)).Append(',').Append(p.y.ToString("R", ic)).Append(',').Append(p.z.ToString("R", ic)).Append(',')
                    .Append(math.length(w.vel[b.nodeStart + i]).ToString("R", ic)).Append(',').Append(w.contactFn[b.nodeStart + i].ToString("R", ic)).Append('\n');
            }
            System.IO.File.WriteAllText(ctx.FilePath(r, $"{tag}_nodes.csv"), dump.ToString());
        }

        static double MaxOver(Series s, int col, int from)
        {
            double v = double.MinValue;
            for (int i = from; i < s.Count; i++)
                v = math.max(v, s[i][col]);
            return v;
        }

        static double MinOver(Series s, int col, int from)
        {
            double v = double.MaxValue;
            for (int i = from; i < s.Count; i++)
                v = math.min(v, s[i][col]);
            return v;
        }

        /// <summary>Knuckle wind-up of every wheel: rotation of the knuckle about the wheel's spin axis relative to the
        /// body's pitch since the reference (rad, + = top of the knuckle forward). Reference node: the upper ball joint
        /// (front) or the upper knuckle node (rear). With phi0 = null returns the absolute angles (the reference).</summary>
        static double[] Windup(SoftBodyWorld w, double[] phi0)
        {
            var b = w.bodies[0];
            var def = b.def;
            BodyPose(w, out _, out _, out double pitchDeg, out _, out _, true);
            double alpha = -math.tan(math.radians(pitchDeg));    // cabin floor rotation about +x (dy = c z -> alpha = -c)
            var res = new double[b.wheelCount];
            for (int k = 0; k < b.wheelCount; k++)
            {
                var wd = def.wheels[k];
                int top = KnuckleTop(def, wd);
                float3 a = w.pos[b.nodeStart + wd.axleInner], c = w.pos[b.nodeStart + wd.axleOuter];
                float3 e = math.normalize(c - a);
                float3 r = w.pos[b.nodeStart + top] - 0.5f * (a + c);
                r -= math.dot(r, e) * e;
                double phi = math.atan2(r.z, r.y);
                res[k] = phi0 != null ? (phi - phi0[k]) - alpha : phi + alpha;
            }
            return res;
        }

        /// <summary>Vertical displacement of the front frame rails / rear rails relative to the cabin floor plane (the plane
        /// fit of the sill, floor and tunnel nodes, extrapolated): the body's own bending between the cabin and its ends.</summary>
        static void EndDroop(SoftBodyWorld w, out double front, out double rear)
        {
            var b = w.bodies[0];
            // floor plane dy = a + bx x + c z, as BodyPose(cabinFloor)
            double sx = 0, sz = 0, sxx = 0, szz = 0, sxz = 0, sy = 0, sxy = 0, szy = 0;
            int n = 0;
            for (int i = 0; i < b.nodeCount; i++)
            {
                var nd = b.def.nodes[i];
                if (nd.part != "body" || !(nd.name.StartsWith("sill") || nd.name.StartsWith("floor") || nd.name.StartsWith("tunnel")))
                    continue;
                double x = nd.p[0], z = nd.p[2], dy = w.pos[b.nodeStart + i].y - nd.p[1];
                sx += x; sz += z; sxx += x * x; szz += z * z; sxz += x * z; sy += dy; sxy += x * dy; szy += z * dy;
                n++;
            }
            var m = new double3x3(n, sx, sz, sx, sxx, sxz, sz, sxz, szz);
            double3 abc = math.mul(math.inverse(m), new double3(sy, sxy, szy));
            double fs = 0, rs = 0;
            int fn = 0, rn = 0;
            for (int i = 0; i < b.nodeCount; i++)
            {
                var nd = b.def.nodes[i];
                bool f = nd.name.StartsWith("frail"), r = nd.name.StartsWith("rrail");
                if (nd.part != "body" || !(f || r))
                    continue;
                double dy = w.pos[b.nodeStart + i].y - nd.p[1];
                double plane = abc.x + abc.y * nd.p[0] + abc.z * nd.p[2];
                if (f) { fs += dy - plane; fn++; } else { rs += dy - plane; rn++; }
            }
            front = fn > 0 ? fs / fn : 0.0;
            rear = rn > 0 ? rs / rn : 0.0;
        }

        static int KnuckleTop(VehicleDef def, WheelDef wd)
        {
            string up = wd.name + "_ubj", kup = wd.name + "_kup";
            for (int i = 0; i < def.nodes.Length; i++)
                if (def.nodes[i].name == up || def.nodes[i].name == kup)
                    return i;
            return wd.arm;
        }

        // ------------------------------------------------------------------ T7

        public static TestResult CarSlide(ValidationContext ctx)
        {
            var r = new TestResult();
            void Slide(string tag, float3 v0, DriverInput input, out double measured, out double predicted, out double applied, out double distance, out double fullStop)
            {
                // a friction test: gearbox in neutral and no aerodynamic drag, so the contact forces are the only horizontal ones
                using var w = Hellcat(ctx, Ground(), float3.zero, v0, 0.01f, true, prm => prm.aero.airDensity = 0f);
                const int chunk = 10;
                double chunkSeconds = chunk * w.dt;
                var b = w.bodies[0];
                w.SetInput(b.vehicleIndex, input);
                float3 dir = math.normalize(v0);
                float3 c0 = w.Metrics(0, false).centerOfMass;
                var s = new Series("t", "speed", "distance", "decel_law", "normal_N", "pitch_deg", "decel_applied",
                                   "windup_FR_deg", "windup_FL_deg", "windup_RR_deg", "windup_RL_deg",
                                   "pitch_floor_deg", "front_droop_mm", "rear_droop_mm");
                var phi0 = Windup(w, null);
                Run(w, 6.0, chunk, t =>
                {
                    var m = w.Metrics(0, false);
                    var wu = Windup(w, phi0);
                    double f = LawFriction(w, 0, out double n);
                    double imp = -ImpulseAlong(w, 0, dir) / (chunkSeconds * b.totalMass);
                    BodyPose(w, out _, out _, out double pitch, out _, out _);
                    double sp = math.dot(m.velocity, dir);
                    BodyPose(w, out _, out _, out double pitchFloor, out _, out _, true);
                    EndDroop(w, out double fd, out double rd);
                    s.Add(t, sp, math.dot(m.centerOfMass - c0, dir), f / b.totalMass, n, pitch, imp,
                          math.degrees(wu[0]), math.degrees(wu[1]), math.degrees(wu[2]), math.degrees(wu[3]),
                          pitchFloor, fd * 1000, rd * 1000);
                    w.ClearContactImp();
                    return sp > 0.05;
                });
                s.Write(ctx.FilePath(r, $"{tag}.csv"));
                // window: from 85 % to 30 % of the initial speed (wheels locked or sliding sideways, past the landing)
                double vHi = 0.85 * math.length(v0), vLo = 0.30 * math.length(v0);
                int i0 = -1, i1 = -1;
                for (int i = 0; i < s.Count; i++)
                {
                    if (i0 < 0 && s[i][1] <= vHi) i0 = i;
                    if (i1 < 0 && s[i][1] <= vLo) i1 = i;
                }
                measured = predicted = applied = double.NaN;
                if (i0 >= 0 && i1 > i0)
                {
                    measured = (s[i0][1] - s[i1][1]) / (s[i1][0] - s[i0][0]);
                    double sum = 0.0, sumA = 0.0;
                    for (int i = i0; i <= i1; i++)
                    {
                        sum += s[i][3];
                        sumA += s[i][6];
                    }
                    predicted = sum / (i1 - i0 + 1);
                    applied = sumA / (i1 - i0 + 1);
                }
                distance = s[s.Count - 1][2];
                fullStop = s[s.Count - 1][0];
                double wf = 0.0, wr = 0.0;
                for (int i = 0; i < s.Count; i++)
                {
                    wf = math.max(wf, math.max(math.abs(s[i][7]), math.abs(s[i][8])));
                    wr = math.max(wr, math.max(math.abs(s[i][9]), math.abs(s[i][10])));
                }
                r.Info($"{tag}: peak knuckle wind-up front / rear", wf, "deg", $"rear {wr:F2} deg");
                double fdMax = 0.0, rdMax = 0.0, pfMax = 0.0;
                for (int i = 0; i < s.Count; i++)
                {
                    pfMax = math.max(pfMax, math.abs(s[i][11]));
                    fdMax = math.max(fdMax, math.abs(s[i][12]));
                    rdMax = math.max(rdMax, math.abs(s[i][13]));
                }
                r.Info($"{tag}: peak cabin floor pitch", pfMax, "deg");
                r.Info($"{tag}: peak front / rear structure droop vs the cabin floor plane", fdMax, "mm", $"rear {rdMax:F1} mm");
            }
            float v50 = 50f / 3.6f;
            Slide("locked_50kmh", new float3(0f, 0f, v50), new DriverInput { brake = 1f, gear = 0 }, out double aL, out double aLp, out double aLa, out double dL, out double tL);
            // the body decelerates exactly as the contact forces on it say: this is the physics check
            r.Near("locked wheels from 50 km/h: deceleration vs the tangential contact force the solver applied", aL, aLa, 0.03, "m/s^2");
            // and the contact force is a little above pure Coulomb friction, which is what the anchor spring adds
            r.Info("locked wheels from 50 km/h: deceleration vs the Coulomb law mu(slip) lf(load) fn alone", aLp, "m/s^2",
                   $"{aL / math.max(aLp, 1e-9):F3}x, ratio = 1 + kt dpt / (mu fn)");
            r.Info("locked wheels: mean deceleration in g", aL / 9.81, "g");
            r.Info("locked wheels: stopping distance from 50 km/h", dL, "m", $"v^2 / (2 a) = {v50 * v50 / (2 * aL):F2} m, {tL:F2} s");
            Slide("lateral_10ms", new float3(10f, 0f, 0f), new DriverInput { gear = 0 }, out double aS, out double aSp, out double aSa, out double dS, out _);
            r.Near("sideways slide from 10 m/s: deceleration vs the applied tangential contact force", aS, aSa, 0.03, "m/s^2");
            r.Info("sideways slide: deceleration vs the Coulomb law alone", aSp, "m/s^2", $"{aS / math.max(aSp, 1e-9):F3}x");
            r.Info("sideways slide: mean deceleration in g", aS / 9.81, "g");
            r.Info("sideways slide: distance", dS, "m");
            r.notes.Add("Gearbox in neutral, aerodynamic drag off: the locked-wheel stop is pure tire sliding friction. " +
                        "The 100-0 km/h target of brief 4.13 (33-38 m, with ABS near peak friction) is test T13.");
            return r;
        }

        // ------------------------------------------------------------------ T8

        public static TestResult Tunnelling(ValidationContext ctx)
        {
            var r = new TestResult();
            const float v120 = 120f / 3.6f;

            // (a) the Hellcat at 120 km/h into a 20 cm static concrete wall
            {
                const float wallZ = 4.0f, wallT = 0.2f;
                var statics = Ground();
                statics.AddBox(new float3(0f, 1.5f, wallZ + 0.5f * wallT), quaternion.identity, new float3(3f, 1.5f, 0.5f * wallT), "concrete", "wall_20cm");
                using var w = Hellcat(ctx, statics, float3.zero, new float3(0f, 0f, v120), 0.01f);
                var b = w.bodies[0];
                w.SetInput(b.vehicleIndex, DriverInput.Neutral);
                int behind = 0, nonFinite = 0;
                double minDist = double.MaxValue, maxSpeed = 0.0;
                var wallPrim = w.prims[1];
                var s = new Series("t", "com_speed", "max_node_speed", "front_z", "broken", "min_wall_distance");
                Run(w, ctx.quick ? 0.4 : 0.8, 4, t =>
                {
                    double front = double.MinValue, md = double.MaxValue;
                    int bh = 0;
                    for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                    {
                        float3 p = w.pos[i];
                        if (!math.all(math.isfinite(p)))
                        {
                            nonFinite++;
                            continue;
                        }
                        // only nodes the solver is asked to collide: 317 of the 1819 Hellcat nodes are interior
                        // panel grids, dash ribs, wheel-internal and rack boots, which carry no collision flag by
                        // design and must be allowed to sit inside an obstacle.
                        if ((b.def.nodes[i - b.nodeStart].flags & NodeFlag.StaticCollision) == 0)
                            continue;
                        front = math.max(front, p.z);
                        if (p.z > wallZ + wallT && math.abs(p.x) < 3f && p.y < 3f)
                            bh++;
                        md = math.min(md, StaticSdf.Distance(wallPrim, w.planes, p, out _));
                    }
                    behind = math.max(behind, bh);
                    minDist = math.min(minDist, md);
                    double vmax = MaxNodeSpeed(w, 0);
                    maxSpeed = math.max(maxSpeed, vmax);
                    var m = w.Metrics(0, false);
                    s.Add(t, m.velocity.z, vmax, front, m.brokenBeams, md);
                    return true;
                });
                s.Write(ctx.FilePath(r, "static_wall_120kmh.csv"));
                r.Max("static 20 cm wall at 120 km/h: nodes behind the wall", behind, 0);
                r.Min("static wall: smallest signed distance of any node to the wall", minDist, -1e-3, "m");
                r.Max("static wall: non-finite node states", nonFinite, 0);
                r.Info("static wall: peak node speed", maxSpeed, "m/s");
                r.Info("static wall: broken beams after 0.8 s", s[s.Count - 1][4]);
            }

            // (b) node-vs-triangle: a 20 cm thick node-beam slab (fixed nodes, triangles on both faces) hit at 120 km/h
            //     by 35 free nodes (on vertices, edges and cell centres) and by a 10 kg braced box
            TestBody Slab(bool fixedNodes, out float zFront)
            {
                var tb = new TestBody();
                const int nx = 9, ny = 7;
                zFront = 6.0f;
                var F = new int[nx, ny];
                var B = new int[nx, ny];
                int flags = fixedNodes ? NodeFlag.Fixed : NodeFlag.Collision;
                for (int i = 0; i < nx; i++)
                    for (int j = 0; j < ny; j++)
                    {
                        float x = -1f + 0.25f * i, y = 0.25f + 0.25f * j;
                        F[i, j] = tb.Node($"f{i}_{j}", new float3(x, y, zFront), 2f, flags, part: "slab");
                        B[i, j] = tb.Node($"b{i}_{j}", new float3(x, y, zFront + 0.2f), 2f, flags, part: "slab");
                    }
                for (int i = 0; i < nx; i++)
                    for (int j = 0; j < ny; j++)
                    {
                        tb.Beam(F[i, j], B[i, j], "slab");
                        if (i + 1 < nx) { tb.Beam(F[i, j], F[i + 1, j], "slab"); tb.Beam(B[i, j], B[i + 1, j], "slab"); tb.Beam(F[i, j], B[i + 1, j], "slab"); }
                        if (j + 1 < ny) { tb.Beam(F[i, j], F[i, j + 1], "slab"); tb.Beam(B[i, j], B[i, j + 1], "slab"); tb.Beam(F[i, j], B[i, j + 1], "slab"); }
                        if (i + 1 < nx && j + 1 < ny) { tb.Beam(F[i, j], F[i + 1, j + 1], "slab"); tb.Beam(B[i, j], B[i + 1, j + 1], "slab"); }
                        if (i + 1 < nx && j + 1 < ny)
                        {
                            tb.Quad(F[i, j], F[i, j + 1], F[i + 1, j + 1], F[i + 1, j], "slab");   // front face, normal -z
                            tb.Quad(B[i, j], B[i + 1, j], B[i + 1, j + 1], B[i, j + 1], "slab");   // back face, normal +z
                        }
                    }
                return tb;
            }
            TestBody Projectiles(out List<int> loose, out int[] box)
            {
                var tb = new TestBody();
                loose = new List<int>();
                for (int i = 0; i < 7; i++)
                    for (int j = 0; j < 5; j++)
                        loose.Add(tb.Node($"n{i}_{j}", new float3(-0.75f + 0.125f * i, 0.5f + 0.125f * j, 5.5f), 0.5f, NodeFlag.Collision, part: "loose"));
                box = tb.Box("bx", new float3(0.45f, 1.25f, 5.35f), new float3(0.15f), 10f, "rigid", NodeFlag.Collision, part: "box");
                return tb;
            }
            void Shoot(string tag, bool fixedSlab, out double maxPast, out double momentumError, out int projections)
            {
                var slab = Slab(fixedSlab, out float zFront);
                var proj = Projectiles(out var loose, out var box);
                var prm = TestBody.Params(0f, TestBody.Mat("slab", 1e6f, 50f), TestBody.Mat("rigid", 5e5f, 20f));
                using var w = Build(prm, null, ww =>
                {
                    ww.AddBody("slab", slab.Def("slab"), prm, float3.zero, quaternion.identity, float3.zero, false);
                    ww.AddBody("projectiles", proj.Def("projectiles"), prm, float3.zero, quaternion.identity, new float3(0f, 0f, v120), false);
                });
                var pb = w.bodies[1];
                double3 P0 = Momentum(w);
                maxPast = double.MinValue;
                var s = new Series("t", "max_past_front", "projectile_mean_vz", "contacts", "projections");
                double mp = double.MinValue;
                Run(w, 0.25, 1, t =>
                {
                    double past = double.MinValue, vz = 0.0;
                    for (int i = pb.nodeStart; i < pb.nodeStart + pb.nodeCount; i++)
                    {
                        float3 p = w.pos[i];
                        if (math.abs(p.x) < 1f && p.y > 0.25f && p.y < 1.75f)
                            past = math.max(past, p.z - FrontZAt(w, p));
                        vz += w.vel[i].z / pb.nodeCount;
                    }
                    mp = math.max(mp, past);
                    s.Add(t, past, vz, w.collCounters[CollisionCounter.Contacts], w.collCounters[CollisionCounter.Projections]);
                    return true;
                });
                s.Write(ctx.FilePath(r, $"{tag}.csv"));
                maxPast = mp;
                double3 P1 = Momentum(w);
                momentumError = math.length(P1 - P0) / math.length(P0);
                projections = w.collCounters[CollisionCounter.Projections];
                _ = zFront;
            }
            Shoot("slab_fixed", true, out double pastFixed, out _, out int projFixed);
            r.Max("node-beam slab (fixed) at 120 km/h: deepest projectile node past the front face", pastFixed, 1e-3, "m");
            r.Info("fixed slab: anti-tunnelling projections", projFixed);
            Shoot("slab_free", false, out double pastFree, out double pErr, out int projFree);
            r.Max("node-beam slab (free, 252 kg) at 120 km/h: deepest node past the front face", pastFree, 1e-3, "m");
            r.Max("free slab: total momentum error after the impacts", pErr, 0.005);
            r.Info("free slab: anti-tunnelling projections", projFree);
            return r;
        }

        static double3 Momentum(SoftBodyWorld w)
        {
            double3 p = double3.zero;
            for (int i = 0; i < w.NodeCount; i++)
                if (w.invMass[i] > 0f)
                    p += (double3)w.vel[i] / w.invMass[i];
            return p;
        }

        /// <summary>z of the slab's front face at a point, bilinearly interpolated over the front grid (the slab moves
        /// when it is free). A single nearest node is not good enough: the grid is 0.25 m while the measured band is
        /// 1 m wide, so the nearest-node baseline is off by up to half a cell and swamps the 1 mm penetration limit.</summary>
        static double FrontZAt(SoftBodyWorld w, float3 p)
        {
            var sb = w.bodies[0];
            const int nx = 9, ny = 7;
            const float x0 = -1f, dx = 0.25f, y0 = 0.25f, dy = 0.25f;
            float fx = (p.x - x0) / dx, fy = (p.y - y0) / dy;
            int i0 = math.clamp((int)math.floor(fx), 0, nx - 2);
            int j0 = math.clamp((int)math.floor(fy), 0, ny - 2);
            float tx = math.clamp(fx - i0, 0f, 1f), ty = math.clamp(fy - j0, 0f, 1f);
            double z00 = w.pos[sb.nodeStart + (i0 * ny + j0) * 2].z;
            double z10 = w.pos[sb.nodeStart + ((i0 + 1) * ny + j0) * 2].z;
            double z01 = w.pos[sb.nodeStart + (i0 * ny + j0 + 1) * 2].z;
            double z11 = w.pos[sb.nodeStart + ((i0 + 1) * ny + j0 + 1) * 2].z;
            double za = z00 + (z10 - z00) * tx;
            double zb = z01 + (z11 - z01) * tx;
            return za + (zb - za) * ty;
        }

        // ------------------------------------------------------------------ E1

        public static TestResult EnergyDrift(ValidationContext ctx)
        {
            var r = new TestResult();
            double seconds = ctx.quick ? 3.0 : 10.0;
            void Drift(string tag, bool damping, out double windowDrift, out double maxDev, out double lErr, out double e0)
            {
                using var w = Hellcat(ctx, new StaticWorldBuilder(), new float3(0f, 3f, 0f), float3.zero, float.NaN, true, prm =>
                {
                    prm.gravity = 0f;
                    prm.spawnRamp = 0f;
                    prm.aero.airDensity = 0f;     // no air: the ledger is the solver's (aero work is external)
                    if (!damping)
                        foreach (var wu in prm.windup)
                        {
                            wu.damping = 0f;
                            wu.camberDamping = 0f;   // alignment element (D-049)
                            wu.toeDamping = 0f;
                        }
                    if (!damping)
                        foreach (var m in prm.materials)
                        {
                            m.damp = 0f;
                            m.dampRebound = 0f;
                            m.dampFast = 0f;
                            m.dampReboundFast = 0f;
                            m.dampExp = 0f;
                            m.limitDamp = 0f;
                            m.limitDampRebound = 0f;
                        }
                });
                // rigid spin plus a small random velocity field (deterministic)
                var b = w.bodies[0];
                var rng = new System.Random(7);
                float3 omega = new float3(0.5f, 1.0f, 0.3f);
                float3 com = w.Metrics(0, false).centerOfMass;
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                {
                    if (w.invMass[i] <= 0f)
                        continue;
                    float3 noise = new float3((float)Gauss(rng), (float)Gauss(rng), (float)Gauss(rng)) * 0.02f;
                    w.vel[i] = math.cross(omega, w.pos[i] - com) + noise;
                }
                // neutral: the engine is decoupled; the axle side (carrier, half-shaft and LSD springs) is in the ledger
                w.SetInput(b.vehicleIndex, DriverInput.Neutral);
                var mInit = w.Metrics(0);
                double3 L0 = mInit.angularMomentum;
                e0 = mInit.Mechanical;
                var s = new Series("t", "mechanical", "dissipated", "total", "kinetic", "elastic", "pressure", "torsion");
                var vPrev = new float3[b.nodeCount];
                const int chunk = 40;
                long total = (long)(seconds / w.dt);
                while (w.StepsTaken < total)
                {
                    w.Step(chunk - 1);
                    var m = w.Metrics(0);
                    for (int i = 0; i < b.nodeCount; i++)
                        vPrev[i] = w.vel[b.nodeStart + i];
                    w.Step(1);
                    // leapfrog kinetic energy at the positions of the metrics call: mean of the two half-step velocities
                    double ke = 0.0;
                    for (int i = 0; i < b.nodeCount; i++)
                    {
                        float im = w.invMass[b.nodeStart + i];
                        if (im > 0f)
                            ke += 0.5 / im * math.lengthsq((double3)(0.5f * (vPrev[i] + w.vel[b.nodeStart + i])));
                    }
                    double mech = ke + m.elastic + m.torsion + m.pressure + m.gravity + m.driveline;
                    s.Add((w.StepsTaken - 1) * (double)w.dt, mech, m.Dissipated, mech + m.Dissipated, ke, m.elastic, m.pressure, m.torsion);
                }
                s.Write(ctx.FilePath(r, $"{tag}.csv"));
                double first = 0.0, last = 0.0;
                int nf = 0, nl = 0;
                maxDev = 0.0;
                double ref0 = s[0][3];
                for (int i = 0; i < s.Count; i++)
                {
                    double t = s[i][0];
                    if (t <= 1.0) { first += s[i][3]; nf++; }
                    if (t >= seconds - 1.0) { last += s[i][3]; nl++; }
                    maxDev = math.max(maxDev, math.abs(s[i][3] - ref0) / e0);
                }
                windowDrift = (last / nl - first / nf) / e0;
                lErr = math.length(w.Metrics(0).angularMomentum - L0) / math.length(L0);
            }
            Drift("damped", true, out double dA, out double mA, out double lA, out double eA);
            r.Max("free Hellcat, damping on: |drift of (mechanical + dissipated)|, 1 s windows, 10 s", math.abs(dA), 0.01);
            r.Info("damping on: largest instantaneous deviation", mA, "", $"initial energy {eA:F0} J");
            r.Max("damping on: angular momentum error", lA, 1e-3);
            Drift("undamped", false, out double dB, out double mB, out double lB, out double eB);
            r.Max("free Hellcat, damping off: |drift of the mechanical energy|, 1 s windows, 10 s", math.abs(dB), 0.01);
            r.Info("damping off: largest instantaneous deviation", mB, "", $"initial energy {eB:F0} J");
            r.Max("damping off: angular momentum error", lB, 1e-3);
            r.notes.Add("Rigid spin (0.5, 1.0, 0.3) rad/s plus 2 cm/s random node velocities, zero gravity, no contact. " +
                        "Kinetic energy uses the leapfrog mean of the half-step velocities; symplectic Euler conserves a shadow energy, " +
                        "so the drift is the change of the 1 s window means.");
            return r;
        }

        static double Gauss(System.Random rng)
        {
            double u1 = 1.0 - rng.NextDouble(), u2 = rng.NextDouble();
            return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.PI * u2);
        }

        // ------------------------------------------------------------------ D1

        public static TestResult Determinism(ValidationContext ctx)
        {
            var r = new TestResult();
            double seconds = ctx.quick ? 1.0 : 2.0;
            ulong RunOnce(bool single, out double us)
            {
                using var w = Hellcat(ctx, Ground(), float3.zero, new float3(0f, 0f, 5f), 0.05f, false, null, single);
                w.SetInput(w.bodies[0].vehicleIndex, new DriverInput { throttle = 0.3f, steer = 0.4f, gear = DriverInput.Drive });
                double sec = Run(w, seconds, 33);
                us = sec / w.StepsTaken * 1e6;
                return StateHash(w);
            }
            ulong a = RunOnce(false, out double usA);
            ulong b2 = RunOnce(false, out _);
            ulong c = RunOnce(true, out double usC);
            r.Flag("re-run with the same inputs gives bit-identical node states (parallel)", a == b2, "hash equal");
            r.Flag("single-thread run gives bit-identical node states", a == c, "hash equal");
            r.Info("state hash", (double)(a & 0xFFFFFFFF), "", $"{a:X16}");
            r.Info("time per substep: parallel / single thread", usA, "us", $"single {usC:F1} us");
            return r;
        }
    }
}
