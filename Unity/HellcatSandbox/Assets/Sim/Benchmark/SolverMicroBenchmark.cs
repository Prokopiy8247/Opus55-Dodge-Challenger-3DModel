using System;
using System.Collections.Generic;
using Unity.Burst;
using Unity.Jobs;
using Unity.Jobs.LowLevel.Unsafe;
using Unity.Mathematics;
using UnityEngine;

namespace Hellcat.Sim.Benchmark
{
    /// <summary>One multi-threaded configuration: job worker count (0 = maximum) and batch sizes.</summary>
    [Serializable]
    public struct MtConfig
    {
        public int workers;
        public int beamBatch;   // IJobParallelFor inner-loop batch sizes
        public int nodeBatch;

        public MtConfig(int workers, int beamBatch, int nodeBatch)
        {
            this.workers = workers;
            this.beamBatch = beamBatch;
            this.nodeBatch = nodeBatch;
        }
    }

    [Serializable]
    public class BenchmarkOptions
    {
        public LatticeConfig lattice;
        public SimParams sim;
        public int substepsPerFrame = 33;          // 2000 Hz physics / 60 fps display
        public float simSeconds = 5f;              // simulated time per measured run
        public MtConfig[] mtSweep =                // shuffled layout; the last entry repeats for determinism
        {
            new MtConfig(1, 256, 64), new MtConfig(2, 256, 64), new MtConfig(4, 256, 64),
            new MtConfig(8, 256, 64), new MtConfig(0, 256, 64),
            new MtConfig(4, 1024, 256), new MtConfig(8, 1024, 256), new MtConfig(0, 1024, 256),
            new MtConfig(0, 1024, 256),
        };
        public MtConfig[] mtOrdered = { new MtConfig(4, 1024, 256), new MtConfig(0, 1024, 256) };
        public bool includeOrderedLayout = true;

        /// <summary>P0 spec: 3,000 nodes / 15,000 beams at dt = 0.5 ms, car-sized box hitting a wall.</summary>
        public static BenchmarkOptions CreateDefault()
        {
            return new BenchmarkOptions
            {
                lattice = new LatticeConfig
                {
                    dims = new int3(30, 10, 10),
                    spacing = 0.15f,
                    targetBeams = 15000,
                    totalMass = 2000f,
                    spring = 40000f,
                    damp = 20f,
                    deform = 2000f,
                    hardening = 40000f,
                    strength = 3000f,
                    lift = 0.03f,
                    initialVelocity = new float3(15f, 0f, 0f),
                    shuffle = true,
                    seed = 12345u,
                },
                sim = new SimParams
                {
                    dt = 0.0005f,
                    gravity = new float3(0f, -9.81f, 0f),
                    contactBias = 0.025f,
                    contactStiffness = 100000f,
                    contactDamping = 50f,
                    friction = 0.8f,
                    wallX = 8f,
                },
            };
        }
    }

    [Serializable]
    public class RunResult
    {
        public string variant;              // "ST": one job per frame; "MT": parallel beam + node jobs per substep
        public string layout;               // "shuffled" (worst-case locality) or "ordered"
        public int workers;                 // job worker threads for MT (the main thread also helps in Complete)
        public int beamBatch;
        public int nodeBatch;
        public int frames;
        public int steps;
        public double totalMs;
        public double frameMsMean;
        public double frameMsP50;
        public double frameMsP95;
        public double frameMsP99;
        public double frameMsMax;
        public double usPerStep;
        public double stepsPerSecond;
        public double realtimeFactor;       // simulated seconds per wall-clock second at the given dt
        public double frameBudgetShare60;   // mean frame time / 16.67 ms
        public bool burst;
        public string stateHash;
        public int brokenBeams;
        public int plasticBeams;
        public float maxSpeed;
        public float minY;
        public float maxX;
        public int nonFinite;
    }

    [Serializable]
    public class BenchmarkReport
    {
        public string context;
        public string timestamp;
        public string unityVersion;
        public string platform;
        public bool burstEnabled;
        public string cpu;
        public int logicalCores;
        public int systemMemoryMB;
        public int jobWorkerMaximumCount;
        public int jobWorkerCountDefault;
        public int nodes;
        public int beams;
        public int maxValence;
        public float maxOmegaDt;
        public int omegaViolations;
        public BenchmarkOptions options;
        public List<RunResult> runs = new List<RunResult>();
        public List<string> notes = new List<string>();
    }

    /// <summary>
    /// P0 Burst solver micro-benchmark. Measures wall time per 60 fps frame (33 substeps of 0.5 ms)
    /// for a single-threaded and a multi-threaded node-beam step, checks that Burst code actually ran,
    /// and hashes the final state to check run-to-run and thread-count determinism.
    /// </summary>
    public static class SolverMicroBenchmark
    {
        public static BenchmarkReport Run(BenchmarkOptions opt, string context)
        {
            var report = new BenchmarkReport
            {
                context = context,
                timestamp = DateTime.Now.ToString("s"),
                unityVersion = Application.unityVersion,
                platform = Application.platform.ToString(),
                burstEnabled = BurstCompiler.IsEnabled,
                cpu = SystemInfo.processorType,
                logicalCores = SystemInfo.processorCount,
                systemMemoryMB = SystemInfo.systemMemorySize,
                jobWorkerMaximumCount = JobsUtility.JobWorkerMaximumCount,
                jobWorkerCountDefault = JobsUtility.JobWorkerCount,
                options = opt,
            };
            int defaultWorkers = JobsUtility.JobWorkerCount;
            try
            {
                RunLayout(opt, true, report);
                if (opt.includeOrderedLayout)
                    RunLayout(opt, false, report);
            }
            finally
            {
                JobsUtility.JobWorkerCount = defaultWorkers;
            }
            return report;
        }

        static void RunLayout(BenchmarkOptions opt, bool shuffled, BenchmarkReport report)
        {
            LatticeConfig cfg = opt.lattice;
            cfg.shuffle = shuffled;
            using var world = new BenchmarkWorld(cfg, opt.sim.dt);
            if (shuffled)
            {
                report.nodes = world.nodeCount;
                report.beams = world.beamCount;
                report.maxValence = world.maxValence;
                report.maxOmegaDt = world.maxOmegaDt;
                report.omegaViolations = world.omegaViolations;
            }
            string layout = shuffled ? "shuffled" : "ordered";
            int frames = (int)math.ceil(opt.simSeconds / (opt.sim.dt * opt.substepsPerFrame));
            var frameMs = new double[frames];
            int maxWorkers = JobsUtility.JobWorkerMaximumCount;

            // Single-threaded, repeated to check run-to-run determinism.
            int stRepeats = shuffled ? 2 : 1;
            for (int r = 0; r < stRepeats; r++)
                report.runs.Add(Measure(false, layout, default, world, opt, frames, frameMs));

            foreach (MtConfig requested in shuffled ? opt.mtSweep : opt.mtOrdered)
            {
                MtConfig mt = requested;
                mt.workers = mt.workers <= 0 ? maxWorkers : math.min(mt.workers, maxWorkers);
                JobsUtility.JobWorkerCount = mt.workers;
                report.runs.Add(Measure(true, layout, mt, world, opt, frames, frameMs));
            }
        }

        static RunResult Measure(bool multiThreaded, string layout, MtConfig mt, BenchmarkWorld w,
            BenchmarkOptions opt, int frames, double[] frameMs)
        {
            var single = new SingleThreadStepJob
            {
                substeps = opt.substepsPerFrame,
                prm = opt.sim,
                pos = w.pos,
                vel = w.vel,
                force = w.force,
                invMass = w.invMass,
                beamNodes = w.beamNodes,
                beamCoef = w.beamCoef,
                beamBounds = w.beamBounds,
                beamKind = w.beamKind,
                restLength = w.restLength,
                yieldForce = w.yieldForce,
                broken = w.broken,
                burstFlag = w.burstFlag,
            };
            var beamJob = new BeamForceJob
            {
                pos = w.pos,
                vel = w.vel,
                beamNodes = w.beamNodes,
                beamCoef = w.beamCoef,
                beamBounds = w.beamBounds,
                beamKind = w.beamKind,
                restLength = w.restLength,
                yieldForce = w.yieldForce,
                broken = w.broken,
                beamForce = w.beamForce,
            };
            var nodeJob = new NodeGatherIntegrateJob
            {
                prm = opt.sim,
                pos = w.pos,
                vel = w.vel,
                invMass = w.invMass,
                adjStart = w.adjStart,
                adjCode = w.adjCode,
                beamForce = w.beamForce,
                burstFlag = w.burstFlag,
            };

            // Warm-up frame (loads/compiles the Burst code, warms the caches), then restart.
            w.Reset();
            RunFrame(multiThreaded, mt, single, beamJob, nodeJob, w, opt);
            w.Reset();

            double toMs = 1000.0 / System.Diagnostics.Stopwatch.Frequency;
            long start = System.Diagnostics.Stopwatch.GetTimestamp();
            for (int f = 0; f < frames; f++)
            {
                long t = System.Diagnostics.Stopwatch.GetTimestamp();
                RunFrame(multiThreaded, mt, single, beamJob, nodeJob, w, opt);
                frameMs[f] = (System.Diagnostics.Stopwatch.GetTimestamp() - t) * toMs;
            }
            double totalMs = (System.Diagnostics.Stopwatch.GetTimestamp() - start) * toMs;

            var sorted = (double[])frameMs.Clone();
            Array.Sort(sorted);
            double sum = 0;
            foreach (double ms in sorted)
                sum += ms;
            int steps = frames * opt.substepsPerFrame;
            var result = new RunResult
            {
                variant = multiThreaded ? "MT" : "ST",
                layout = layout,
                workers = multiThreaded ? mt.workers : 0,
                beamBatch = multiThreaded ? mt.beamBatch : 0,
                nodeBatch = multiThreaded ? mt.nodeBatch : 0,
                frames = frames,
                steps = steps,
                totalMs = totalMs,
                frameMsMean = sum / frames,
                frameMsP50 = Percentile(sorted, 0.50),
                frameMsP95 = Percentile(sorted, 0.95),
                frameMsP99 = Percentile(sorted, 0.99),
                frameMsMax = sorted[sorted.Length - 1],
                usPerStep = totalMs * 1000.0 / steps,
                stepsPerSecond = steps / (totalMs / 1000.0),
                realtimeFactor = steps * opt.sim.dt / (totalMs / 1000.0),
                frameBudgetShare60 = (sum / frames) / (1000.0 / 60.0),
                burst = w.burstFlag[0] == 1,
                stateHash = w.StateHash(),
                brokenBeams = w.CountBroken(),
                plasticBeams = w.CountPlastic(),
                minY = float.MaxValue,
                maxX = float.MinValue,
            };
            for (int i = 0; i < w.nodeCount; i++)
            {
                float3 p = w.pos[i];
                float3 v = w.vel[i];
                if (!math.all(math.isfinite(p)) || !math.all(math.isfinite(v)))
                {
                    result.nonFinite++;
                    continue;
                }
                result.maxSpeed = math.max(result.maxSpeed, math.length(v));
                result.minY = math.min(result.minY, p.y);
                result.maxX = math.max(result.maxX, p.x);
            }
            Debug.Log($"[SolverBench] {result.variant} {layout} workers={result.workers} batch={result.beamBatch}/{result.nodeBatch} burst={result.burst} " +
                      $"{result.stepsPerSecond:F0} steps/s, {result.usPerStep:F1} us/step, frame mean {result.frameMsMean:F3} ms " +
                      $"p99 {result.frameMsP99:F3} ms, broken={result.brokenBeams} plastic={result.plasticBeams} hash={result.stateHash}");
            return result;
        }

        static void RunFrame(bool multiThreaded, MtConfig mt, SingleThreadStepJob single, BeamForceJob beamJob,
            NodeGatherIntegrateJob nodeJob, BenchmarkWorld w, BenchmarkOptions opt)
        {
            if (!multiThreaded)
            {
                single.Schedule().Complete();
                return;
            }
            JobHandle handle = default;
            for (int s = 0; s < opt.substepsPerFrame; s++)
            {
                handle = beamJob.Schedule(w.beamCount, mt.beamBatch, handle);
                handle = nodeJob.Schedule(w.nodeCount, mt.nodeBatch, handle);
            }
            handle.Complete();
        }

        static double Percentile(double[] sorted, double q)
        {
            int index = (int)math.ceil(q * sorted.Length) - 1;
            return sorted[math.clamp(index, 0, sorted.Length - 1)];
        }
    }
}
