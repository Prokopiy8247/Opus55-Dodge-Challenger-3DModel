using System;
using System.IO;
using Hellcat.EditorTools.P0;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace Hellcat.EditorTools.Build
{
    /// <summary>
    /// Batch entry points for Windows player builds. They exit the editor themselves (no -quit):
    ///   -executeMethod Hellcat.EditorTools.Build.BuildTasks.BuildSlice -buildDir &lt;dir&gt;
    /// </summary>
    public static class BuildTasks
    {
        public static void ApplyPlayerSettings()
        {
            PlayerSettings.companyName = "Hellcat Sandbox";
            PlayerSettings.productName = "Hellcat Sandbox";
            PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
            PlayerSettings.defaultScreenWidth = 1600;
            PlayerSettings.defaultScreenHeight = 900;
            PlayerSettings.resizableWindow = true;
            PlayerSettings.runInBackground = true;
            PlayerSettings.visibleInBackground = true;
            PlayerSettings.SplashScreen.show = false;
        }

        public static void BuildSlice()
        {
            int code = 1;
            try
            {
                SliceSceneBuilder.Build();
                ApplyPlayerSettings();
                string dir = P0CommandLine.GetValue("-buildDir", Path.Combine(VehicleAssetSync.ProjectRoot, "Builds", "P05_Slice"));
                code = Build(new[] { SliceSceneBuilder.ScenePath }, Path.Combine(dir, "HellcatSlice.exe"));
            }
            catch (Exception e)
            {
                Debug.LogException(e);
            }
            EditorApplication.Exit(code);
        }

        /// <summary>P4 crash player: -executeMethod Hellcat.EditorTools.Build.BuildTasks.BuildCrash [-buildDir dir]</summary>
        public static void BuildCrash()
        {
            int code = 1;
            try
            {
                CrashSceneBuilder.Build();
                ApplyPlayerSettings();
                string dir = P0CommandLine.GetValue("-buildDir", Path.Combine(VehicleAssetSync.ProjectRoot, "Builds", "P4_Crash"));
                code = Build(new[] { CrashSceneBuilder.ScenePath }, Path.Combine(dir, "HellcatCrash.exe"));
            }
            catch (Exception e)
            {
                Debug.LogException(e);
            }
            EditorApplication.Exit(code);
        }

        /// <summary>P4b drive player (the sandbox): -executeMethod Hellcat.EditorTools.Build.BuildTasks.BuildDrive [-buildDir dir]</summary>
        public static void BuildDrive()
        {
            int code = 1;
            try
            {
                DriveSceneBuilder.Build();
                ApplyPlayerSettings();
                string dir = P0CommandLine.GetValue("-buildDir", Path.Combine(VehicleAssetSync.ProjectRoot, "Builds", "P4b_Drive"));
                code = Build(new[] { DriveSceneBuilder.ScenePath }, Path.Combine(dir, "HellcatDrive.exe"));
            }
            catch (Exception e)
            {
                Debug.LogException(e);
            }
            EditorApplication.Exit(code);
        }

        /// <summary>P5 test-map player: -executeMethod Hellcat.EditorTools.Build.BuildTasks.BuildTestMap [-buildDir dir]</summary>
        public static void BuildTestMap()
        {
            int code = 1;
            try
            {
                TestMapBuilder.Build();
                ApplyPlayerSettings();
                string dir = P0CommandLine.GetValue("-buildDir", Path.Combine(VehicleAssetSync.ProjectRoot, "Builds", "TestMap"));
                code = Build(new[] { TestMapBuilder.ScenePath }, Path.Combine(dir, "HellcatTestMap.exe"));
            }
            catch (Exception e)
            {
                Debug.LogException(e);
            }
            EditorApplication.Exit(code);
        }

        /// <summary>P7 standalone sandbox (the test map scene with the game rig, its tests and the start screen):
        /// -executeMethod Hellcat.EditorTools.Build.BuildTasks.BuildSandbox [-buildDir dir]</summary>
        public static void BuildSandbox()
        {
            int code = 1;
            try
            {
                TestMapBuilder.Build();
                ApplyPlayerSettings();
                string dir = P0CommandLine.GetValue("-buildDir", Path.Combine(VehicleAssetSync.ProjectRoot, "Builds", "HellcatSandbox"));
                code = Build(new[] { TestMapBuilder.ScenePath }, Path.Combine(dir, "HellcatSandbox.exe"));
            }
            catch (Exception e)
            {
                Debug.LogException(e);
            }
            EditorApplication.Exit(code);
        }

        /// <summary>The sandbox for macOS (Apple Silicon and Intel in one app): -executeMethod
        /// Hellcat.EditorTools.Build.BuildTasks.BuildSandboxMac [-buildDir dir] -> HellcatSandbox.app. Switches the editor's
        /// active build target (the next Windows build switches it back).</summary>
        public static void BuildSandboxMac()
        {
            int code = 1;
            try
            {
                TestMapBuilder.Build();
                ApplyPlayerSettings();
                PlayerSettings.SetApplicationIdentifier(UnityEditor.Build.NamedBuildTarget.Standalone, "com.hellcatsandbox.sandbox");
                EditorUserBuildSettings.SetPlatformSettings("OSXUniversal", "Architecture", "x64ARM64");
                string dir = P0CommandLine.GetValue("-buildDir", Path.Combine(VehicleAssetSync.ProjectRoot, "Builds", "HellcatSandbox_Mac"));
                code = Build(new[] { TestMapBuilder.ScenePath }, Path.Combine(dir, "HellcatSandbox.app"), BuildTarget.StandaloneOSX);
            }
            catch (Exception e)
            {
                Debug.LogException(e);
            }
            EditorApplication.Exit(code);
        }

        public static int Build(string[] scenes, string exePath, BuildTarget target = BuildTarget.StandaloneWindows64)
        {
            var options = new BuildPlayerOptions
            {
                scenes = scenes,
                locationPathName = exePath,
                target = target,
                options = BuildOptions.None,
            };
            BuildReport report = BuildPipeline.BuildPlayer(options);
            var s = report.summary;
            Debug.Log($"[BuildTasks] {exePath}: result={s.result} size={s.totalSize} time={s.totalTime} errors={s.totalErrors} warnings={s.totalWarnings}");
            return s.result == BuildResult.Succeeded ? 0 : 1;
        }
    }
}
