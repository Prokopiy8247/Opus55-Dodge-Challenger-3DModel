using System;
using System.IO;
using UnityEngine;

namespace Hellcat.Game.Core
{
    /// <summary>
    /// The sandbox settings file (brief 4.12 quality of life): <c>settings.json</c> next to the player executable (in the
    /// editor: the persistent data folder), written with the defaults on the first start and read on every start. The
    /// vehicle's simulation parameters stay in StreamingAssets/Vehicles/hellcat/params.json (F9 reloads them).
    /// </summary>
    [Serializable]
    public class GameSettings
    {
        [Header("Cameras")]
        public float chaseDistance = 6.4f;
        public float chaseHeight = 1.9f;
        public float chaseFov = 55f;            // vertical degrees
        public float bumperFov = 72f;           // vertical degrees
        public float cockpitFovHorizontal = 85f; // horizontal degrees (cockpit.json, D-020)
        public float freeCameraSpeed = 6f;
        public float mouseLookSpeed = 0.12f;
        [Header("Driving")]
        public bool abs = true;
        public bool tractionControl = true;
        public float slowMotionScale = 0.1f;
        [Header("Simulation")]
        public int maxSubstepsPerFrame = 66;    // 2 frames of real time at 60 fps; more and the car slows down visibly
        public bool singleThread;
        [Header("Display")]
        public bool vSync = true;
        public int targetFrameRate = -1;
        public bool hud = true;
        public int screenshotSuperSize = 1;

        // next to the executable on Windows; the editor and macOS (inside the .app bundle is no place for files) use the
        // per-user data folder
        public static string FolderPath =>
            Application.isEditor || Application.platform == RuntimePlatform.OSXPlayer ? Application.persistentDataPath
                                                                                       : Path.GetDirectoryName(Application.dataPath);

        public static string FilePath => Path.Combine(FolderPath, "settings.json");

        /// <summary>Recordings (F5) and screenshots go here.</summary>
        public static string RecordingsPath => Path.Combine(FolderPath, "recordings");

        static GameSettings current;

        public static GameSettings Current => current ??= Load();

        public static GameSettings Load()
        {
            var s = new GameSettings();
            try
            {
                if (File.Exists(FilePath))
                    JsonUtility.FromJsonOverwrite(File.ReadAllText(FilePath), s);
                else
                    s.Save();
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[GameSettings] {FilePath}: {e.Message}; defaults used");
            }
            return s;
        }

        public void Save()
        {
            try
            {
                Directory.CreateDirectory(FolderPath);
                File.WriteAllText(FilePath, JsonUtility.ToJson(this, true));
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[GameSettings] cannot write {FilePath}: {e.Message}");
            }
        }

        public void Apply()
        {
            QualitySettings.vSyncCount = vSync ? 1 : 0;
            Application.targetFrameRate = targetFrameRate;
        }
    }
}
