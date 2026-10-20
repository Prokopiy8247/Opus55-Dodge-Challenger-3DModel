using System;
using System.IO;
using Hellcat.Sim.Benchmark;
using Unity.Collections;
using Unity.Jobs.LowLevel.Unsafe;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Hellcat.EditorTools.P0
{
    /// <summary>
    /// P0 batch entry points for the Burst solver micro-benchmark:
    ///   -executeMethod Hellcat.EditorTools.P0.P0BenchmarkTasks.RunInEditor -p0Out &lt;file.json&gt;
    ///   -executeMethod Hellcat.EditorTools.P0.P0BenchmarkTasks.BuildBenchmarkPlayer -p0BuildDir &lt;dir&gt;
    /// Both exit the editor themselves (do not pass -quit).
    /// </summary>
    public static class P0BenchmarkTasks
    {
        const string BenchmarkScenePath = "Assets/Scenes/P0/P0_SolverBenchmark.unity";

        public static void RunInEditor()
        {
            string outPath = P0CommandLine.GetValue("-p0Out", Path.GetFullPath("p0_bench_editor.json"));
            int exitCode = 0;
            try
            {
                // Remove editor-only overheads that a release player does not have.
                JobsUtility.JobDebuggerEnabled = false;
                NativeLeakDetection.Mode = NativeLeakDetectionMode.Disabled;
                var report = SolverMicroBenchmark.Run(BenchmarkOptions.CreateDefault(), "editor-batchmode");
                report.notes.Add("Editor batch mode: job debugger and leak detection off; jobs use DisableSafetyChecks.");
                File.WriteAllText(outPath, JsonUtility.ToJson(report, true));
                Debug.Log($"[P0BenchmarkTasks] wrote {outPath}");
            }
            catch (Exception e)
            {
                Debug.LogException(e);
                exitCode = 1;
            }
            EditorApplication.Exit(exitCode);
        }

        public static void BuildBenchmarkPlayer()
        {
            string buildDir = P0CommandLine.GetValue("-p0BuildDir", Path.GetFullPath("Builds/P0_SolverBench"));
            int exitCode = 1;
            try
            {
                // An empty scene is enough: the benchmark starts from RuntimeInitializeOnLoadMethod.
                Directory.CreateDirectory(Path.GetDirectoryName(BenchmarkScenePath));
                var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                EditorSceneManager.SaveScene(scene, BenchmarkScenePath);

                var options = new BuildPlayerOptions
                {
                    scenes = new[] { BenchmarkScenePath },
                    locationPathName = Path.Combine(buildDir, "HellcatSolverBench.exe"),
                    target = BuildTarget.StandaloneWindows64,
                    options = BuildOptions.None,
                };
                BuildReport report = BuildPipeline.BuildPlayer(options);
                BuildSummary s = report.summary;
                Debug.Log($"[P0BenchmarkTasks] build result={s.result} size={s.totalSize} bytes time={s.totalTime} " +
                          $"errors={s.totalErrors} warnings={s.totalWarnings} path={options.locationPathName}");
                exitCode = s.result == BuildResult.Succeeded ? 0 : 1;
            }
            catch (Exception e)
            {
                Debug.LogException(e);
            }
            EditorApplication.Exit(exitCode);
        }
    }
}
