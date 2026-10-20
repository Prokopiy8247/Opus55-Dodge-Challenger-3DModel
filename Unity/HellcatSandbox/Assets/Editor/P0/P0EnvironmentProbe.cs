using System;
using System.Collections.Generic;
using System.IO;
using Unity.Burst;
using UnityEditor;
using UnityEditor.Build;
using UnityEngine;
using UnityEngine.Rendering;

namespace Hellcat.EditorTools.P0
{
    /// <summary>
    /// P0: records the editor/GPU environment, resolved packages and project settings, checks that
    /// the planned package assemblies load, and runs a compute-shader smoke test on the GPU.
    /// Batch entry point (run WITHOUT -nographics so a graphics device exists):
    ///   -executeMethod Hellcat.EditorTools.P0.P0EnvironmentProbe.Run -p0Out &lt;file.json&gt;
    /// </summary>
    public static class P0EnvironmentProbe
    {
        const string ComputeShaderPath = "Assets/Sim/Benchmark/P0ComputeSmoke.compute";

        [Serializable]
        class Item
        {
            public string key;
            public string value;
        }

        [Serializable]
        class Report
        {
            public string timestamp;
            public List<Item> items = new List<Item>();
            public List<string> packages = new List<string>();
        }

        public static void Run()
        {
            string outPath = P0CommandLine.GetValue("-p0Out", Path.GetFullPath("p0_environment.json"));
            int exitCode = 0;
            try
            {
                var report = new Report { timestamp = DateTime.Now.ToString("s") };
                void Add(string key, object value) =>
                    report.items.Add(new Item { key = key, value = value == null ? "null" : value.ToString() });

                Add("unityVersion", Application.unityVersion);
                Add("isBatchMode", Application.isBatchMode);
                Add("os", SystemInfo.operatingSystem);
                Add("cpu", SystemInfo.processorType);
                Add("cpuLogicalCount", SystemInfo.processorCount);
                Add("cpuFrequencyMHz", SystemInfo.processorFrequency);
                Add("systemMemoryMB", SystemInfo.systemMemorySize);
                Add("gpu", SystemInfo.graphicsDeviceName);
                Add("gpuVendor", SystemInfo.graphicsDeviceVendor);
                Add("gpuApi", SystemInfo.graphicsDeviceType);
                Add("gpuApiVersion", SystemInfo.graphicsDeviceVersion);
                Add("gpuMemoryMB", SystemInfo.graphicsMemorySize);
                Add("gpuShaderLevel", SystemInfo.graphicsShaderLevel);
                Add("supportsComputeShaders", SystemInfo.supportsComputeShaders);
                Add("supportsAsyncGPUReadback", SystemInfo.supportsAsyncGPUReadback);
                Add("maxComputeWorkGroupSize", SystemInfo.maxComputeWorkGroupSize);
                Add("computeSmokeTest", ComputeSmokeTest());

                Add("renderPipelineAsset", GraphicsSettings.defaultRenderPipeline != null
                    ? GraphicsSettings.defaultRenderPipeline.name : "none (built-in)");
                Add("qualityLevels", string.Join(",", QualitySettings.names));
                Add("colorSpace", PlayerSettings.colorSpace);
                Add("scriptingBackendStandalone", PlayerSettings.GetScriptingBackend(NamedBuildTarget.Standalone));
                Add("apiCompatibilityStandalone", PlayerSettings.GetApiCompatibilityLevel(NamedBuildTarget.Standalone));
                Add("graphicsApisWin64", string.Join(",", PlayerSettings.GetGraphicsAPIs(BuildTarget.StandaloneWindows64)));
                Add("activeInputHandler (0 old, 1 new, 2 both)", ReadProjectSetting("activeInputHandler"));
                Add("burstEnabled", BurstCompiler.IsEnabled);

                Add("assembly:Unity.Mathematics.float3", typeof(Unity.Mathematics.float3).Assembly.GetName().Name);
                Add("assembly:Unity.Burst.BurstCompileAttribute", typeof(BurstCompileAttribute).Assembly.GetName().Name);
                Add("type:Unity.Collections.NativeList", TypeStatus("Unity.Collections.NativeList`1, Unity.Collections"));
                Add("type:InputSystem", TypeStatus("UnityEngine.InputSystem.InputSystem, Unity.InputSystem"));
                Add("type:Recorder", TypeStatus("UnityEditor.Recorder.RecorderController, Unity.Recorder.Editor"));
                Add("type:TestRunnerApi", TypeStatus("UnityEditor.TestTools.TestRunner.Api.TestRunnerApi, UnityEditor.TestRunner"));
                Add("type:NUnit", TypeStatus("NUnit.Framework.TestAttribute, nunit.framework"));
                Add("type:Cinemachine (not installed on purpose)", TypeStatus("Unity.Cinemachine.CinemachineCamera, Unity.Cinemachine"));

                foreach (var p in UnityEditor.PackageManager.PackageInfo.GetAllRegisteredPackages())
                    report.packages.Add($"{p.name}@{p.version} ({p.source})");
                report.packages.Sort(StringComparer.Ordinal);

                File.WriteAllText(outPath, JsonUtility.ToJson(report, true));
                Debug.Log($"[P0EnvironmentProbe] wrote {outPath}");
            }
            catch (Exception e)
            {
                Debug.LogException(e);
                exitCode = 1;
            }
            EditorApplication.Exit(exitCode);
        }

        static string TypeStatus(string assemblyQualifiedName)
        {
            var type = Type.GetType(assemblyQualifiedName);
            return type != null ? "loaded from " + type.Assembly.GetName().Name : "missing";
        }

        static string ReadProjectSetting(string key)
        {
            foreach (string line in File.ReadAllLines("ProjectSettings/ProjectSettings.asset"))
            {
                string trimmed = line.Trim();
                if (trimmed.StartsWith(key + ":", StringComparison.Ordinal))
                    return trimmed.Substring(key.Length + 1).Trim();
            }
            return "not found";
        }

        static string ComputeSmokeTest()
        {
            if (!SystemInfo.supportsComputeShaders)
                return "skipped: no compute support (device " + SystemInfo.graphicsDeviceType + ")";
            var shader = AssetDatabase.LoadAssetAtPath<ComputeShader>(ComputeShaderPath);
            if (shader == null)
                return "failed: " + ComputeShaderPath + " not found";

            const int count = 4096;
            var data = new float[count];
            for (int i = 0; i < count; i++)
                data[i] = i;
            var buffer = new ComputeBuffer(count, sizeof(float));
            try
            {
                int kernel = shader.FindKernel("CSMain");
                buffer.SetData(data);
                shader.SetBuffer(kernel, "Data", buffer);
                shader.SetFloat("Scale", 2f);
                var watch = System.Diagnostics.Stopwatch.StartNew();
                shader.Dispatch(kernel, count / 64, 1, 1);
                buffer.GetData(data);
                watch.Stop();
                int wrong = 0;
                for (int i = 0; i < count; i++)
                {
                    if (data[i] != 2f * i + 1f)
                        wrong++;
                }
                return wrong == 0
                    ? $"ok: {count} values verified, dispatch + readback {watch.Elapsed.TotalMilliseconds:F2} ms"
                    : $"failed: {wrong} of {count} values wrong";
            }
            finally
            {
                buffer.Release();
            }
        }
    }
}
