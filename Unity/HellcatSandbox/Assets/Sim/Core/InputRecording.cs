using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Text;
using Hellcat.Sim.Vehicle;
using Unity.Mathematics;

namespace Hellcat.Sim
{
    /// <summary>
    /// A run's driver inputs frame by frame plus the state it started from (brief 4.12 record / replay, test 15; D-070).
    /// Each frame holds the number of substeps it advanced and the input applied to all of them, so a frame starts at
    /// t = (sum of the substeps before it) * dt. The start is either a full <see cref="WorldState"/> snapshot (recording
    /// begun at any moment, damage included) or a respawn (a settled car at a pose and speed: scripted scenarios, small
    /// files). Replaying the frames with the same partition from the same start is bit-identical; the inputs can also
    /// be fed per substep under another partition (<see cref="InputAt"/>: video capture at a higher frame rate).
    /// Files: gzip binary (*.hrec), the inputs also as CSV for reading.
    /// </summary>
    public sealed class InputRecording
    {
        public const uint Magic = 0x43455248;   // "HREC"
        public const int Version = 1;

        public enum StartKind { Snapshot = 0, Respawn = 1 }

        public struct Frame
        {
            public int substeps;
            public DriverInput input;
        }

        public string vehicle = "";
        public string note = "";
        public string createdUtc = "";
        public ulong dataHash;                 // geometry + parameters the run was made with (FNV-1a of the files)
        public float dt;
        public long startStep;                 // world substeps at the start (informational)
        public StartKind start;
        public float3 spawnPosition;           // respawn start: pose and speed of the settled car
        public quaternion spawnRotation = quaternion.identity;
        public float spawnSpeed;
        public WorldState state;               // snapshot start
        public readonly List<Frame> frames = new List<Frame>();

        long[] cumulative;                     // substeps before each frame (lazy, for InputAt)

        public long TotalSubsteps
        {
            get
            {
                long n = 0;
                foreach (var f in frames) n += f.substeps;
                return n;
            }
        }

        public double Duration => TotalSubsteps * (double)dt;

        public void Add(int substeps, in DriverInput input)
        {
            frames.Add(new Frame { substeps = substeps, input = input });
            cumulative = null;
        }

        void EnsureCumulative()
        {
            if (cumulative != null && cumulative.Length == frames.Count + 1)
                return;
            cumulative = new long[frames.Count + 1];
            for (int i = 0; i < frames.Count; i++)
                cumulative[i + 1] = cumulative[i] + frames[i].substeps;
        }

        /// <summary>Substeps before frame <paramref name="frame"/> (the total for frames.Count).</summary>
        public long StartOf(int frame)
        {
            EnsureCumulative();
            return cumulative[Math.Max(0, Math.Min(frame, frames.Count))];
        }

        /// <summary>The input of the frame that contains substep <paramref name="substep"/> (counted from the start); the
        /// last frame's input after the end.</summary>
        public DriverInput InputAt(long substep)
        {
            if (frames.Count == 0)
                return DriverInput.Idle;
            EnsureCumulative();
            int lo = 0, hi = frames.Count;   // find the last frame i with cumulative[i] <= substep
            while (hi - lo > 1)
            {
                int mid = (lo + hi) >> 1;
                if (cumulative[mid] <= substep) lo = mid; else hi = mid;
            }
            return frames[lo].input;
        }

        /// <summary>FNV-1a 64 over files (geometry.json and params.json): a recording names the data it was made with.</summary>
        public static ulong HashFiles(params string[] paths)
        {
            ulong h = 1469598103934665603UL;
            foreach (var p in paths)
                foreach (byte x in File.ReadAllBytes(p))
                {
                    h ^= x;
                    h *= 1099511628211UL;
                }
            return h;
        }

        // ------------------------------------------------------------------ files

        public void Write(string path)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path)));
            using var fs = File.Create(path);
            Write(fs);
        }

        public void Write(Stream stream)
        {
            using (var gz = new GZipStream(stream, CompressionLevel.Optimal, true))
            using (var w = new BinaryWriter(gz, Encoding.UTF8, true))
            {
                w.Write(Magic);
                w.Write(Version);
                w.Write(vehicle ?? "");
                w.Write(note ?? "");
                w.Write(createdUtc ?? "");
                w.Write(dataHash);
                w.Write(dt);
                w.Write(startStep);
                w.Write((int)start);
                w.Write(spawnPosition.x); w.Write(spawnPosition.y); w.Write(spawnPosition.z);
                w.Write(spawnRotation.value.x); w.Write(spawnRotation.value.y); w.Write(spawnRotation.value.z); w.Write(spawnRotation.value.w);
                w.Write(spawnSpeed);
                w.Write(frames.Count);
                foreach (var f in frames)
                {
                    w.Write(f.substeps);
                    w.Write(f.input.throttle);
                    w.Write(f.input.brake);
                    w.Write(f.input.handbrake);
                    w.Write(f.input.steer);
                    w.Write(f.input.gear);
                    w.Write(f.input.flags);
                }
                w.Write(state != null);
                state?.Write(w);
            }
        }

        public static InputRecording Read(string path)
        {
            using var fs = File.OpenRead(path);
            return Read(fs);
        }

        public static InputRecording Read(Stream stream)
        {
            var rec = new InputRecording();
            using (var gz = new GZipStream(stream, CompressionMode.Decompress, true))
            using (var r = new BinaryReader(gz, Encoding.UTF8, true))
            {
                if (r.ReadUInt32() != Magic)
                    throw new InvalidDataException("not an input recording");
                int ver = r.ReadInt32();
                if (ver != Version)
                    throw new InvalidDataException($"recording version {ver}, expected {Version}");
                rec.vehicle = r.ReadString();
                rec.note = r.ReadString();
                rec.createdUtc = r.ReadString();
                rec.dataHash = r.ReadUInt64();
                rec.dt = r.ReadSingle();
                rec.startStep = r.ReadInt64();
                rec.start = (StartKind)r.ReadInt32();
                rec.spawnPosition = new float3(r.ReadSingle(), r.ReadSingle(), r.ReadSingle());
                rec.spawnRotation = new quaternion(r.ReadSingle(), r.ReadSingle(), r.ReadSingle(), r.ReadSingle());
                rec.spawnSpeed = r.ReadSingle();
                int n = r.ReadInt32();
                for (int i = 0; i < n; i++)
                {
                    var f = new Frame { substeps = r.ReadInt32() };
                    f.input.throttle = r.ReadSingle();
                    f.input.brake = r.ReadSingle();
                    f.input.handbrake = r.ReadSingle();
                    f.input.steer = r.ReadSingle();
                    f.input.gear = r.ReadInt32();
                    f.input.flags = r.ReadInt32();
                    rec.frames.Add(f);
                }
                if (r.ReadBoolean())
                    rec.state = WorldState.Read(r);
            }
            return rec;
        }

        /// <summary>The inputs as text: frame start time, substeps, pedals, steering, gear, flags.</summary>
        public void WriteCsv(string path)
        {
            var ic = CultureInfo.InvariantCulture;
            var sb = new StringBuilder("t_s,substeps,throttle,brake,handbrake,steer,gear,flags\n");
            long n = 0;
            foreach (var f in frames)
            {
                sb.Append((n * (double)dt).ToString("F4", ic)).Append(',').Append(f.substeps).Append(',')
                  .Append(f.input.throttle.ToString("R", ic)).Append(',').Append(f.input.brake.ToString("R", ic)).Append(',')
                  .Append(f.input.handbrake.ToString("R", ic)).Append(',').Append(f.input.steer.ToString("R", ic)).Append(',')
                  .Append(f.input.gear).Append(',').Append(f.input.flags).Append('\n');
                n += f.substeps;
            }
            File.WriteAllText(path, sb.ToString());
        }
    }
}
