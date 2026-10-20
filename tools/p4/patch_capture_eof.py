"""One-off (P4): the crash scenario renders its capture cameras at the end of the frame, after Unity has skinned the car
for this frame (GPU skinning runs in PostLateUpdate; a Camera.Render() in Update drew skinned meshes from an older frame,
part of the car stale and part current), and every car SkinnedMeshRenderer is skinned also when the main camera culls it."""
from pathlib import Path


def edit(path, pairs):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    for o, n in pairs:
        assert s.count(o) == 1, (path, o[:80])
        s = s.replace(o, n)
    p.write_text(s, encoding="utf-8")


edit("Unity/HellcatSandbox/Assets/Game/Scenario/CarCrashScenario.cs", [
    ('''        readonly List<string> skinLog = new List<string>();   // per-mesh skin report every frame around the impact''',
     '''        readonly List<string> skinLog = new List<string>();   // per-mesh skin report every frame around the impact
        // captures are rendered at the end of the frame, after Unity has skinned the car for this frame (GPU skinning runs in
        // PostLateUpdate: a Camera.Render() in Update drew the skinned meshes of an older frame, partly stale)
        readonly List<(Camera cam, string path, int w, int h, bool jpg)> pending = new List<(Camera, string, int, int, bool)>();
        bool quitAfterCapture;'''),
    ('''            running = true;
            Debug.Log($"[CarCrash] {runId}: target''',
     '''            running = true;
            StartCoroutine(EndOfFrameCaptures());
            Debug.Log($"[CarCrash] {runId}: target'''),
    ('''                foreach (var cam in cameras)
                    if (cam) FrameCapture.Save(cam, Path.Combine(frames, $"{cam.name}_{frameIndex:D4}.jpg"), captureWidth, captureHeight, true);
                frameIndex++;''',
     '''                foreach (var cam in cameras)
                    if (cam) pending.Add((cam, Path.Combine(frames, $"{cam.name}_{frameIndex:D4}.jpg"), captureWidth, captureHeight, true));
                frameIndex++;'''),
    ('''        void Stills(string tag)
        {
            foreach (var cam in cameras)
                if (cam) FrameCapture.Save(cam, Path.Combine(outDir, $"{runId}_{tag}_{cam.name}.png"), 1920, 1080);
        }''',
     '''        void Stills(string tag)
        {
            foreach (var cam in cameras)
                if (cam) pending.Add((cam, Path.Combine(outDir, $"{runId}_{tag}_{cam.name}.png"), 1920, 1080, false));
        }

        System.Collections.IEnumerator EndOfFrameCaptures()
        {
            var eof = new WaitForEndOfFrame();
            while (true)
            {
                yield return eof;
                foreach (var (cam, path, w, h, jpg) in pending)
                    FrameCapture.Save(cam, path, w, h, jpg);
                pending.Clear();
                if (quitAfterCapture)
                {
                    Application.Quit(0);
#if UNITY_EDITOR
                    UnityEditor.EditorApplication.isPlaying = false;
#endif
                    yield break;
                }
            }
        }'''),
    ('''            Debug.Log($"[CarCrash] done: {sb}");
            Application.Quit(0);
#if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
#endif''',
     '''            Debug.Log($"[CarCrash] done: {sb}");
            quitAfterCapture = true;   // after the final stills (end of this frame)'''),
])

edit("Unity/HellcatSandbox/Assets/Editor/Car/CarImporter.cs", [
    ('''                    smr.updateWhenOffscreen = false;''',
     '''                    // skinned every frame even when the main camera culls it (capture cameras, mirrors; GPU skinning
                    // skips culled renderers and they would show an old pose)
                    smr.updateWhenOffscreen = true;'''),
])

edit("Unity/HellcatSandbox/Assets/Game/Views/SoftBodyCarView.cs", [
    ('''            access = new TransformAccessArray(nodeBones);''',
     '''            access = new TransformAccessArray(nodeBones);
            foreach (var smr in GetComponentsInChildren<SkinnedMeshRenderer>(true))
                smr.updateWhenOffscreen = true;   // skinned for every camera (see CarImporter)'''),
])
print("patched")
