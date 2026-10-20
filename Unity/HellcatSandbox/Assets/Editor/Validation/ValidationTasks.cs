using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text.RegularExpressions;
using Hellcat.EditorTools.Build;
using Hellcat.EditorTools.P0;
using Hellcat.Sim.Validation;
using Unity.Collections;
using Unity.Jobs.LowLevel.Unsafe;
using UnityEditor;
using UnityEngine;

namespace Hellcat.EditorTools.Validation
{
    /// <summary>
    /// Batch entry point of the validation suite (brief section 10, tests 1-8, energy drift, determinism):
    ///   -executeMethod Hellcat.EditorTools.Validation.ValidationTasks.RunAll [-valOut &lt;dir&gt;] [-valTests T1,T6] [-valQuick 1]
    /// Syncs sim/vehicle into StreamingAssets first. Exit code 0 = all PASS, 2 = a test failed, 1 = error.
    /// </summary>
    public static class ValidationTasks
    {
        public static void RunAll() => RunSuite(Path.Combine("docs", "p3", "validation"), "validation_results.json", ValidationSuite.Tests);

        /// <summary>Vehicle dynamics tests 9-14 (P3b): -executeMethod ...ValidationTasks.RunDynamics [-valOut] [-valTests T12]
        /// [-valQuick 1]; results in docs/p3b/validation/dynamics_results.json.</summary>
        public static void RunDynamics() => RunSuite(Path.Combine("docs", "p3b", "validation"), "dynamics_results.json", ValidationSuite.DynamicsTests);

        /// <summary>Game-layer tests (P4b): test 15, record / replay determinism; results in
        /// docs/p4b/validation/game_results.json.</summary>
        public static void RunGame() => RunSuite(Path.Combine("docs", "p4b", "validation"), "game_results.json", ValidationSuite.GameTests);

        static void RunSuite(string defaultOut, string resultsFile, List<(string id, string title, ValidationSuite.TestFn fn)> tests)
        {
            int code = 1;
            try
            {
                Application.SetStackTraceLogType(LogType.Log, StackTraceLogType.None);
                // reports are English: '.' decimals and "NaN" in every interpolated note, whatever the OS locale
                CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;
                CultureInfo.DefaultThreadCurrentCulture = CultureInfo.InvariantCulture;
                JobsUtility.JobDebuggerEnabled = false;
                // the editor compiles Burst jobs asynchronously and runs them as managed code until then: right after a
                // script change the first substeps would use other float arithmetic and the run would differ from a run
                // in a warm session (players are compiled ahead of time and unaffected)
                Unity.Burst.BurstCompiler.Options.EnableBurstCompileSynchronously = true;
                NativeLeakDetection.Mode = NativeLeakDetectionMode.Disabled;
                VehicleAssetSync.SyncAll();
                string root = VehicleAssetSync.ProjectRoot;
                var ctx = new ValidationContext
                {
                    outDir = P0CommandLine.GetValue("-valOut", Path.Combine(root, defaultOut)),
                    resultsFile = resultsFile,
                    vehicleFolder = Path.Combine(Application.streamingAssetsPath, "Vehicles", "hellcat"),
                    quick = P0CommandLine.GetValue("-valQuick", "0") == "1",
                    log = s => Debug.Log(s),
                    referenceS = ReadReferenceS(Path.Combine(root, "docs", "p2_stability.json")),
                };
                var ids = new List<string>();
                foreach (var s in P0CommandLine.GetValue("-valTests", "").Split(new[] { ',', ';' }, StringSplitOptions.RemoveEmptyEntries))
                    ids.Add(s.Trim());
                var results = ValidationSuite.Run(ctx, ids, tests);
                bool all = results.TrueForAll(r => r.Pass);
                Debug.Log($"[ValidationTasks] {results.Count} tests, {(all ? "all PASS" : "FAILURES")}; results in {ctx.outDir}");
                code = all ? 0 : 2;
            }
            catch (Exception e)
            {
                Debug.LogException(e);
            }
            EditorApplication.Exit(code);
        }

        static double ReadReferenceS(string path)
        {
            if (!File.Exists(path))
                return double.NaN;
            var m = Regex.Match(File.ReadAllText(path), "\"S_exact_max\"\\s*:\\s*([0-9.eE+-]+)");
            return m.Success ? double.Parse(m.Groups[1].Value, CultureInfo.InvariantCulture) : double.NaN;
        }
    }
}
