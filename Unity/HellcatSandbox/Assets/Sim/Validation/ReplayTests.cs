using System;
using System.Collections.Generic;
using System.IO;
using Hellcat.Sim.Vehicle;
using Unity.Mathematics;
using static Hellcat.Sim.Validation.ValidationSuite;

namespace Hellcat.Sim.Validation
{
    /// <summary>
    /// Test 15 (brief 10): record / replay determinism. A driver robot drives the settled Hellcat through a lane change
    /// into a rigid wall at about 55 km/h (contacts, plastic flow, breaking and self-collision in the recording) under a
    /// jittering frame partition (25-40 substeps per frame, as a game at 50-80 fps), recording each frame's substeps and
    /// input from a world snapshot (<see cref="WorldState"/>, <see cref="InputRecording"/>, D-070). Then:
    /// replay from the snapshot with the recorded partition (bit-identical end state), replay with a fixed 8 substeps per
    /// frame (the 250 fps capture: path within tolerance), the same through a recording file, and two replays that start
    /// from a respawn (settled car at a pose) after different histories (bit-identical: the respawn resets everything,
    /// the collision grid schedule included).
    /// </summary>
    public static class ReplayTests
    {
        const float WallZ = 90f;          // wall face (m)
        const double Seconds = 12.0;      // recorded run
        const double TargetKmh = 55.0;

        public static TestResult RecordReplay(ValidationContext ctx)
        {
            var r = new TestResult();
            double seconds = ctx.quick ? 8.0 : Seconds;
            var statics = Ground();
            statics.AddBox(new float3(0f, 1.5f, WallZ + 0.5f), quaternion.identity, new float3(6f, 1.5f, 0.5f), "concrete", "wall_O1");
            var w = Dyn.Car(ctx, statics, float3.zero, 0f);
            try
            {
                var (_, prm) = LoadHellcat(ctx);
                var b = w.bodies[0];
                int vi = b.vehicleIndex;
                var probe = new CarProbe(w, 0);
                long steps = (long)math.round(seconds / w.dt);

                // ---- run 1: record from a snapshot under a jittering partition
                var s0 = WorldState.Capture(w);
                ulong h0 = WorldState.Hash(w);
                var rec = new InputRecording
                {
                    vehicle = "hellcat", dt = w.dt, start = InputRecording.StartKind.Snapshot, state = s0, startStep = w.StepsTaken,
                    note = "T15", createdUtc = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                };
                var path = PolyPath.LaneChange(25.0, 30.0, 3.5, 30.0, 80.0);
                var robot = new DriverRobot(prm) { path = path, targetSpeed = (t, arc) => TargetKmh / 3.6 };
                var rng = new System.Random(15);
                var run1 = new List<(long step, double3 com)>();
                double impactKmh = double.NaN;
                long done = 0;
                var sw = System.Diagnostics.Stopwatch.StartNew();
                while (done < steps)
                {
                    int n = (int)math.min(25 + rng.Next(16), steps - done);
                    var f = probe.Frame();
                    if (double.IsNaN(impactKmh) && FrontZ(w, b) > WallZ - 0.05)
                        impactKmh = f.speed * 3.6;
                    var inp = robot.Control(done * (double)w.dt, n * (double)w.dt, f);
                    rec.Add(n, inp);
                    StepFrame(w, vi, n, i => inp);
                    done += n;
                    run1.Add((done, probe.Frame().com));
                }
                double recordSeconds = sw.Elapsed.TotalSeconds;
                ulong h1 = WorldState.Hash(w);
                var m1 = w.Metrics(0, false);
                r.Info("recorded run: duration / frames", rec.Duration, "s", $"{rec.frames.Count} frames, {rec.TotalSubsteps} substeps");
                r.Info("recorded run: speed at the wall", impactKmh, "km/h", "the run includes a crash");
                r.Info("recorded run: broken / plastic beams at the end", m1.brokenBeams, "", $"plastic {m1.plasticBeams}");
                r.Info("world snapshot size", s0.ByteCount / 1048576.0, "MB", "all native arrays of the world, uncompressed");

                // ---- run 2: replay from the snapshot with the recorded partition
                s0.Restore(w);
                r.Flag("snapshot restore reproduces the captured state", WorldState.Hash(w) == h0, "hash equal");
                var run2 = Replay(w, vi, probe, rec, null);
                ulong h2 = WorldState.Hash(w);
                r.Flag("replay, recorded partition: end state bit-identical", h2 == h1, "hash equal");
                r.Max("replay, recorded partition: largest path deviation", MaxDeviation(run1, run2), 1e-9, "m");

                // ---- run 3: replay at 8 substeps per frame (250 fps capture)
                s0.Restore(w);
                var run3 = Replay(w, vi, probe, rec, 8);
                double dev3 = MaxDeviation(run1, run3);
                r.Max("replay at 8 substeps per frame: largest path deviation", dev3, 0.05, "m");
                r.Info("replay at 8 substeps per frame: end state bit-identical", WorldState.Hash(w) == h1 ? 1 : 0, "",
                    "1 = the frame partition does not change the run");

                // ---- run 4: through a recording file
                byte[] file;
                using (var ms = new MemoryStream())
                {
                    rec.Write(ms);
                    file = ms.ToArray();
                }
                var rec4 = InputRecording.Read(new MemoryStream(file));
                rec4.state.Restore(w);
                Replay(w, vi, probe, rec4, null);
                r.Flag("recording file round trip: end state bit-identical", WorldState.Hash(w) == h1, "hash equal");
                r.Info("recording file size (gzip, snapshot included)", file.Length / 1048576.0, "MB", $"{rec.frames.Count} frames");

                // ---- run 5: respawn starts after different histories
                var pose = quaternion.identity;
                RespawnSettled(w, 0, float3.zero, pose);
                ulong hsA = WorldState.Hash(w, false);
                var runA = Replay(w, vi, probe, rec, null);
                ulong hA = WorldState.Hash(w, false);
                // another history: a burnout with full lock, then the same respawn
                RespawnSettled(w, 0, new float3(20f, 0f, -30f), quaternion.RotateY(1.1f));
                for (int k = 0; k < 120; k++)
                    StepFrame(w, vi, 33, i => new DriverInput { throttle = 1f, steer = 1f, gear = DriverInput.Drive });
                RespawnSettled(w, 0, float3.zero, pose);
                ulong hsB = WorldState.Hash(w, false);
                var runB = Replay(w, vi, probe, rec, null);
                ulong hB = WorldState.Hash(w, false);
                r.Flag("respawn start after another history: settled state identical", hsA == hsB, "hash equal (clock excluded)");
                r.Flag("respawn start after another history: replay bit-identical", hA == hB, "hash equal (clock excluded)");
                r.Info("respawn start: largest path deviation between the two replays", MaxDeviation(runA, runB), "m");
                r.Info("solver time of the recorded run (editor)", recordSeconds / rec.Duration, "s per simulated s");

                var series = new Series("step", "t_s", "x1", "z1", "dev_replay_m", "dev_250fps_m");
                var at3 = new Dictionary<long, double3>();
                foreach (var (s, c) in run3) at3[s] = c;
                for (int k = 0; k < run1.Count; k++)
                {
                    var (s, c) = run1[k];
                    double d3 = at3.TryGetValue(s, out var c3) ? math.distance(c, c3) : double.NaN;
                    series.Add(s, s * (double)w.dt, c.x, c.z, math.distance(c, run2[k].com), d3);
                }
                series.Write(ctx.FilePath(r, "paths.csv"));
                rec.WriteCsv(ctx.FilePath(r, "inputs.csv"));
                r.notes.Add($"Recorded {rec.Duration:F1} s: driver robot on a 3.5 m lane change at {TargetKmh:F0} km/h into a rigid wall " +
                            $"{WallZ:F0} m ahead, frames of 25-40 substeps (seeded). Path = centre of mass at every recorded frame end; the " +
                            "250 fps replay is compared where its frame ends coincide. Respawn runs: settled car at the origin, the " +
                            "second after a 2 s full-lock burnout elsewhere.");
            }
            finally
            {
                w.Dispose();
            }
            return r;
        }

        /// <summary>One game frame as SimRunner.StepNow does it: per-substep inputs, near lists, the substeps.</summary>
        static void StepFrame(SoftBodyWorld w, int vi, int n, Func<int, DriverInput> input)
        {
            for (int s = 0; s < n; s++)
                w.SetInput(vi, s, input(s));
            w.UpdateNearLists(n * w.dt + 0.05f);
            w.Step(n);
        }

        /// <summary>Replays a recording from the world's current state: the recorded frames, or <paramref name="fixedN"/>
        /// substeps per frame with each substep's input looked up. Returns the centre of mass at every frame end.</summary>
        static List<(long step, double3 com)> Replay(SoftBodyWorld w, int vi, CarProbe probe, InputRecording rec, int? fixedN)
        {
            var path = new List<(long, double3)>();
            long done = 0, total = rec.TotalSubsteps;
            int frame = 0;
            while (done < total)
            {
                int n = fixedN.HasValue ? (int)math.min(fixedN.Value, total - done) : rec.frames[frame].substeps;
                long first = done;
                if (fixedN.HasValue)
                    StepFrame(w, vi, n, s => rec.InputAt(first + s));
                else
                {
                    var inp = rec.frames[frame].input;
                    StepFrame(w, vi, n, s => inp);
                }
                frame++;
                done += n;
                path.Add((done, probe.Frame().com));
            }
            return path;
        }

        /// <summary>The game's settled respawn (SimRunner.RespawnSettled): pose, brakes on, settle, inputs idle.</summary>
        static void RespawnSettled(SoftBodyWorld w, int bi, float3 position, quaternion rotation)
        {
            var b = w.bodies[bi];
            b.spawnClearance = 0.01f;
            w.Respawn(bi, position, rotation, float3.zero);
            w.SetInput(b.vehicleIndex, new DriverInput { brake = 1f, handbrake = 1f, gear = 0 });
            w.Settle(bi);
            w.SetInput(b.vehicleIndex, DriverInput.Idle);
        }

        static double MaxDeviation(List<(long step, double3 com)> a, List<(long step, double3 com)> b)
        {
            var at = new Dictionary<long, double3>();
            foreach (var (s, c) in b) at[s] = c;
            double worst = 0.0;
            int matched = 0;
            foreach (var (s, c) in a)
                if (at.TryGetValue(s, out var cb))
                {
                    worst = math.max(worst, math.distance(c, cb));
                    matched++;
                }
            return matched > 0 ? worst : double.NaN;
        }

        static double FrontZ(SoftBodyWorld w, SoftBodyWorld.Body b)
        {
            float z = float.MinValue;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                z = math.max(z, w.pos[i].z);
            return z;
        }
    }
}
