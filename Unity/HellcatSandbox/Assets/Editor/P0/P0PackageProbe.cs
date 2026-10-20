using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.PackageManager;
using UnityEditor.PackageManager.Requests;
using UnityEngine;

namespace Hellcat.EditorTools.P0
{
    /// <summary>
    /// P0: asks the Package Manager which versions of the planned packages exist and
    /// which are compatible with / recommended for this editor, and writes them as JSON.
    /// Batch entry point:
    ///   -executeMethod Hellcat.EditorTools.P0.P0PackageProbe.Run -p0Out &lt;file.json&gt;
    /// The editor exits by itself when all searches are done (do not pass -quit).
    /// </summary>
    public static class P0PackageProbe
    {
        static readonly string[] PackageNames =
        {
            "com.unity.burst",
            "com.unity.collections",
            "com.unity.mathematics",
            "com.unity.jobs",
            "com.unity.inputsystem",
            "com.unity.test-framework",
            "com.unity.recorder",
            "com.unity.cinemachine",
            "com.unity.render-pipelines.universal",
        };

        [Serializable]
        class PackageEntry
        {
            public string name;
            public bool found;
            public string error;
            public string displayName;
            public string source;
            public string recommended;
            public string latestCompatible;
            public string latest;
            public string[] compatible;
        }

        [Serializable]
        class Report
        {
            public string unityVersion;
            public string timestamp;
            public List<PackageEntry> packages = new List<PackageEntry>();
        }

        static readonly Queue<string> Pending = new Queue<string>();
        static readonly Report Result = new Report();
        static SearchRequest current;
        static string currentName;
        static string outPath;

        public static void Run()
        {
            outPath = P0CommandLine.GetValue("-p0Out", Path.GetFullPath("p0_packages.json"));
            Result.unityVersion = Application.unityVersion;
            Result.timestamp = DateTime.Now.ToString("s");
            foreach (string name in PackageNames)
                Pending.Enqueue(name);
            EditorApplication.update += Tick;
        }

        static void Tick()
        {
            if (current != null && !current.IsCompleted)
                return;
            if (current != null)
                Result.packages.Add(Describe(currentName, current));
            if (Pending.Count == 0)
            {
                EditorApplication.update -= Tick;
                File.WriteAllText(outPath, JsonUtility.ToJson(Result, true));
                Debug.Log($"[P0PackageProbe] wrote {outPath}");
                EditorApplication.Exit(0);
                return;
            }
            currentName = Pending.Dequeue();
            current = Client.Search(currentName, false);
        }

        static PackageEntry Describe(string name, SearchRequest request)
        {
            var entry = new PackageEntry { name = name };
            if (request.Status != StatusCode.Success || request.Result == null || request.Result.Length == 0)
            {
                entry.error = request.Error != null ? request.Error.message : "no result";
                return entry;
            }
            var info = request.Result[0];
            entry.found = true;
            entry.displayName = info.displayName;
            entry.source = info.source.ToString();
            entry.recommended = info.versions.recommended;
            entry.latestCompatible = info.versions.latestCompatible;
            entry.latest = info.versions.latest;
            entry.compatible = info.versions.compatible;
            return entry;
        }
    }
}
