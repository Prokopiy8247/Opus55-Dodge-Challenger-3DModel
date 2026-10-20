using System;
using System.IO;
using UnityEngine;

namespace Hellcat.Sim.Benchmark
{
    /// <summary>
    /// Lets a player build run the solver micro-benchmark from the command line:
    ///   HellcatSolverBench.exe -batchmode -nographics -solverBenchOut &lt;file.json&gt; -logFile &lt;file.log&gt;
    /// Does nothing when the argument is absent.
    /// </summary>
    static class BenchmarkPlayerEntry
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot()
        {
            if (Application.isEditor)
                return;
            string outPath = GetArg("-solverBenchOut");
            if (string.IsNullOrEmpty(outPath))
                return;
            int exitCode = 0;
            try
            {
                var report = SolverMicroBenchmark.Run(BenchmarkOptions.CreateDefault(), "player");
                File.WriteAllText(outPath, JsonUtility.ToJson(report, true));
            }
            catch (Exception e)
            {
                Debug.LogException(e);
                exitCode = 1;
            }
            Application.Quit(exitCode);
        }

        static string GetArg(string name)
        {
            string[] args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
            {
                if (string.Equals(args[i], name, StringComparison.OrdinalIgnoreCase))
                    return args[i + 1];
            }
            return null;
        }
    }
}
