using System;
using System.Collections;
using System.IO;
using System.Linq;
using Hellcat.Sim;
using Hellcat.Sim.Vehicle;
using UnityEngine;

namespace Hellcat.Game.Core
{
    /// <summary>
    /// Input recording and replay (brief 4.12, F5 / F6; D-070). F5 snapshots the whole world (<see cref="WorldState"/>)
    /// and then records every frame's substep count and input; F5 again saves the run to
    /// <c>recordings/rec_*.hrec</c> (inputs also as CSV). F6 restores the snapshot and plays the frames back as the
    /// highest-priority input source: at time scale 1 with the recorded frame partition (bit-identical, test 15), in slow
    /// motion or while stepping with the inputs looked up per substep (deterministic as well; T15 found the partition does
    /// not change the run). A respawn, reset or teleport ends a recording (saved) or a replay.
    /// </summary>
    [DefaultExecutionOrder(-150)]   // before SimRunner (-100): the replay hands it this frame's substep count
    public class ReplayController : MonoBehaviour, IDriverInputSource
    {
        public enum Mode { Idle, Recording, Replaying }

        public SimRunner runner;

        public Mode State { get; private set; }
        public InputRecording Last { get; private set; }
        public string LastPath { get; private set; }
        public string Message { get; private set; } = "";
        public float MessageTime { get; private set; } = -100f;
        /// <summary>Replay: the frames are played with their recorded partition (bit-identical to the recording).</summary>
        public bool Exact { get; private set; }

        public int Priority => 100;
        public bool Active => State == Mode.Replaying;

        InputRecording rec;
        long startStep;      // world substeps when the recording / replay started
        int frame;           // replay: next recorded frame
        bool varied;

        public double Elapsed => State == Mode.Idle || runner == null || runner.World == null ? 0.0 : (runner.World.StepsTaken - startStep) * (double)runner.World.dt;
        public double Duration => State == Mode.Replaying && rec != null ? rec.Duration : Elapsed;

        void OnEnable()
        {
            if (!runner) return;
            runner.RegisterInput(this);
            runner.Stepped += OnStepped;
        }

        void OnDisable()
        {
            if (!runner) return;
            runner.UnregisterInput(this);
            runner.Stepped -= OnStepped;
            if (runner.SubstepOverride == ReplayFrameSubsteps)
                runner.SubstepOverride = null;
        }

        /// <summary><c>-replay &lt;file.hrec&gt;</c>: plays that recording once the world is up (a scenario's run from
        /// sim/cache, a driven run); afterwards the car is the player's.</summary>
        IEnumerator Start()
        {
            string file = SimRunner.CommandLine("-replay");
            if (string.IsNullOrEmpty(file) || !runner)
                yield break;
            yield return null;
            try
            {
                var r = InputRecording.Read(file);
                Last = r;
                LastPath = file;
                StartReplay(r);
            }
            catch (Exception e)
            {
                Say($"cannot read {file}: {e.Message}");
            }
        }

        void Say(string msg)
        {
            Message = msg;
            MessageTime = Time.unscaledTime;
            Debug.Log("[Replay] " + msg);
        }

        // ------------------------------------------------------------------ recording

        public void ToggleRecording()
        {
            if (State == Mode.Recording) StopRecording(true);
            else StartRecording();
        }

        public void StartRecording(string note = "")
        {
            if (State == Mode.Replaying)
                StopReplay("replay stopped");
            rec = new InputRecording
            {
                vehicle = runner.vehicleName,
                note = note,
                createdUtc = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                dataHash = runner.DataHash,
                dt = runner.World.dt,
                startStep = runner.World.StepsTaken,
                start = InputRecording.StartKind.Snapshot,
                state = WorldState.Capture(runner.World),
            };
            startStep = runner.World.StepsTaken;
            varied = false;
            State = Mode.Recording;
            Say("recording");
        }

        /// <summary>Ends the recording; saves it when asked (and when it holds any frames).</summary>
        public InputRecording StopRecording(bool save, string path = null)
        {
            if (State != Mode.Recording)
                return null;
            State = Mode.Idle;
            Last = rec;
            if (rec.frames.Count == 0)
            {
                Say("recording empty, discarded");
                return rec;
            }
            if (save)
            {
                try
                {
                    path ??= Path.Combine(GameSettings.RecordingsPath, $"rec_{DateTime.Now:yyyyMMdd_HHmmss}.hrec");
                    rec.Write(path);
                    rec.WriteCsv(Path.ChangeExtension(path, ".csv"));
                    LastPath = path;
                    Say($"saved {rec.Duration:F1} s to {Path.GetFileName(path)}" + (varied ? " (inputs varied within frames: replay approximate)" : ""));
                }
                catch (Exception e)
                {
                    Say("save failed: " + e.Message);
                }
            }
            else
            {
                Say($"recorded {rec.Duration:F1} s");
            }
            return rec;
        }

        // ------------------------------------------------------------------ replay

        /// <summary>F6: replays the last recording (or the newest file in the recordings folder); stops a running replay.</summary>
        public void ToggleReplay()
        {
            if (State == Mode.Replaying)
            {
                StopReplay("replay stopped");
                return;
            }
            if (State == Mode.Recording)
                StopRecording(true);
            var r = Last ?? LoadNewest();
            if (r == null)
            {
                Say("nothing to replay: record with F5 first");
                return;
            }
            StartReplay(r);
        }

        InputRecording LoadNewest()
        {
            try
            {
                if (!Directory.Exists(GameSettings.RecordingsPath))
                    return null;
                var f = new DirectoryInfo(GameSettings.RecordingsPath).GetFiles("*.hrec").OrderByDescending(x => x.LastWriteTimeUtc).FirstOrDefault();
                if (f == null)
                    return null;
                LastPath = f.FullName;
                return Last = InputRecording.Read(f.FullName);
            }
            catch (Exception e)
            {
                Say("cannot read the recording: " + e.Message);
                return null;
            }
        }

        public bool StartReplay(InputRecording r)
        {
            if (r.state == null && r.start == InputRecording.StartKind.Snapshot)
            {
                Say("the recording has no start state");
                return false;
            }
            if (r.dataHash != 0 && r.dataHash != runner.DataHash)
                Say("warning: recorded with other vehicle data (geometry / params changed): the replay may differ");
            try
            {
                if (r.start == InputRecording.StartKind.Snapshot)
                    runner.RestoreState(r.state);
                else
                    runner.RespawnSettled(r.spawnPosition, r.spawnRotation, r.spawnSpeed);
            }
            catch (Exception e)
            {
                Say("cannot restore the start state: " + e.Message);
                return false;
            }
            rec = r;
            frame = 0;
            startStep = runner.World.StepsTaken;
            State = Mode.Replaying;
            runner.SubstepOverride = ReplayFrameSubsteps;
            Say($"replay {r.Duration:F1} s");
            return true;
        }

        /// <summary>The recorded partition at time scale 1 while running; otherwise the runner's own (-1).</summary>
        int ReplayFrameSubsteps()
        {
            Exact = State == Mode.Replaying && frame < rec.frames.Count && Mathf.Approximately(runner.timeScale, 1f) &&
                    runner.World.StepsTaken - startStep == rec.StartOf(frame);
            return Exact ? rec.frames[frame].substeps : -1;
        }

        public void StopReplay(string why)
        {
            if (State != Mode.Replaying)
                return;
            State = Mode.Idle;
            if (runner.SubstepOverride == ReplayFrameSubsteps)
                runner.SubstepOverride = null;
            Say(why);
        }

        /// <summary>A respawn, reset or teleport: the inputs alone no longer describe the run.</summary>
        public void Interrupt()
        {
            if (State == Mode.Recording) StopRecording(true);
            else if (State == Mode.Replaying) StopReplay("replay ended by a reset");
        }

        public DriverInput Sample(long substepIndex, in VehicleState state) => rec.InputAt(substepIndex - startStep);

        void OnStepped(int n)
        {
            if (State == Mode.Recording)
            {
                rec.Add(n, runner.LastInput);
                varied |= runner.InputVariedInFrame;
            }
            else if (State == Mode.Replaying)
            {
                // advance to the frame that contains the next substep
                long done = runner.World.StepsTaken - startStep;
                while (frame < rec.frames.Count && rec.StartOf(frame + 1) <= done)
                    frame++;
                if (done >= rec.TotalSubsteps)
                    StopReplay($"replay finished ({rec.Duration:F1} s): you are driving");
            }
        }
    }
}
