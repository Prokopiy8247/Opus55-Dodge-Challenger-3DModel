using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using Unity.Collections;
using Unity.Collections.LowLevel.Unsafe;
using Unity.Mathematics;

namespace Hellcat.Sim
{
    /// <summary>
    /// Snapshot of a built world's complete simulation state (record / replay, brief 4.12; D-070): every native array of
    /// the world - state and static data alike, found by reflection, so a state array added later cannot be forgotten -
    /// plus the bodies' spawn poses. Restored into the same world (same vehicle and parameters), the following steps are
    /// bit-identical to the steps that followed the capture, given the same frame partition and inputs. Serialised
    /// gzip-compressed into the recording files; <see cref="Hash"/> fingerprints a state for the replay checks.
    /// </summary>
    public sealed class WorldState
    {
        public const uint Magic = 0x54535748;   // "HWST"
        public const int Version = 1;

        sealed class Entry
        {
            public string name;
            public int elemSize, length;
            public byte[] data;
        }

        sealed class BodyPose
        {
            public float3 position, velocity, angularVelocity;
            public quaternion rotation;
            public float clearance, lift;
        }

        readonly List<Entry> entries = new List<Entry>();
        readonly List<BodyPose> poses = new List<BodyPose>();

        /// <summary>Substeps taken by the world when the state was captured.</summary>
        public long Steps { get; private set; }
        public int NodeCount { get; private set; }
        public int BeamCount { get; private set; }
        public long ByteCount
        {
            get
            {
                long n = 0;
                foreach (var e in entries) n += e.data.LongLength;
                return n;
            }
        }

        // ------------------------------------------------------------------ reflection over the world's arrays

        interface IArrayAccess
        {
            int ElemSize { get; }
            int Length(object boxed);
            byte[] Read(object boxed);
            void Write(object boxed, byte[] data);
        }

        sealed class ArrayAccess<T> : IArrayAccess where T : struct
        {
            public int ElemSize => UnsafeUtility.SizeOf<T>();
            public int Length(object boxed) => ((NativeArray<T>)boxed).Length;
            public byte[] Read(object boxed) => ((NativeArray<T>)boxed).Reinterpret<byte>(ElemSize).ToArray();
            public void Write(object boxed, byte[] data) => ((NativeArray<T>)boxed).Reinterpret<byte>(ElemSize).CopyFrom(data);
        }

        static List<(FieldInfo field, IArrayAccess access)> fields;

        static List<(FieldInfo field, IArrayAccess access)> Fields()
        {
            if (fields != null)
                return fields;
            var list = new List<(FieldInfo, IArrayAccess)>();
            foreach (var f in typeof(SoftBodyWorld).GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
            {
                var t = f.FieldType;
                if (!t.IsGenericType || t.GetGenericTypeDefinition() != typeof(NativeArray<>))
                    continue;
                var access = (IArrayAccess)Activator.CreateInstance(typeof(ArrayAccess<>).MakeGenericType(t.GetGenericArguments()[0]));
                list.Add((f, access));
            }
            list.Sort((a, b) => string.CompareOrdinal(a.Item1.Name, b.Item1.Name));
            fields = list;
            return fields;
        }

        // ------------------------------------------------------------------ capture / restore

        public static WorldState Capture(SoftBodyWorld w)
        {
            if (!w.IsBuilt)
                throw new InvalidOperationException("the world is not built");
            var s = new WorldState { Steps = w.StepsTaken, NodeCount = w.NodeCount, BeamCount = w.BeamCount };
            foreach (var (f, access) in Fields())
            {
                object boxed = f.GetValue(w);
                if (!IsCreated(boxed))
                    continue;
                s.entries.Add(new Entry { name = f.Name, elemSize = access.ElemSize, length = access.Length(boxed), data = access.Read(boxed) });
            }
            foreach (var b in w.bodies)
                s.poses.Add(new BodyPose
                {
                    position = b.spawnPosition, rotation = b.spawnRotation, velocity = b.spawnVelocity,
                    angularVelocity = b.spawnAngularVelocity, clearance = b.spawnClearance, lift = b.spawnLift,
                });
            return s;
        }

        static bool IsCreated(object boxed) =>
            boxed != null && (bool)boxed.GetType().GetProperty("IsCreated").GetValue(boxed);

        /// <summary>Writes the captured arrays back into the world. Throws if the world's layout differs (another vehicle,
        /// other parameters that change the array sizes); nothing is written then.</summary>
        public void Restore(SoftBodyWorld w)
        {
            if (!w.IsBuilt)
                throw new InvalidOperationException("the world is not built");
            var byName = new Dictionary<string, (FieldInfo f, IArrayAccess a)>();
            foreach (var fa in Fields())
                byName[fa.field.Name] = fa;
            var targets = new List<(object boxed, IArrayAccess a, Entry e)>();
            foreach (var e in entries)
            {
                if (!byName.TryGetValue(e.name, out var fa))
                    throw new InvalidDataException($"state array {e.name} does not exist in this build");
                object boxed = fa.f.GetValue(w);
                if (!IsCreated(boxed) || fa.a.Length(boxed) != e.length || fa.a.ElemSize != e.elemSize)
                    throw new InvalidDataException($"state array {e.name}: {e.length} x {e.elemSize} B captured, the world differs");
                targets.Add((boxed, fa.a, e));
            }
            if (poses.Count != w.bodies.Count)
                throw new InvalidDataException($"{poses.Count} bodies captured, the world has {w.bodies.Count}");
            foreach (var (boxed, a, e) in targets)
                a.Write(boxed, e.data);
            for (int i = 0; i < poses.Count; i++)
            {
                var b = w.bodies[i];
                var p = poses[i];
                b.spawnPosition = p.position;
                b.spawnRotation = p.rotation;
                b.spawnVelocity = p.velocity;
                b.spawnAngularVelocity = p.angularVelocity;
                b.spawnClearance = p.clearance;
                b.spawnLift = p.lift;
            }
        }

        // ------------------------------------------------------------------ fingerprint

        /// <summary>FNV-1a 64 over the dynamic state of the world (positions, velocities, rest lengths, yields, breaks,
        /// vehicle and wheel states, clock): equal hashes mean bit-identical runs. Without the clock, runs that started at
        /// different substep counts (respawns after different histories) compare.</summary>
        public static ulong Hash(SoftBodyWorld w, bool includeClock = true)
        {
            ulong h = 1469598103934665603UL;
            foreach (var (f, access) in Fields())
            {
                if (Array.IndexOf(HashedArrays, f.Name) < 0 || (!includeClock && f.Name == "clock"))
                    continue;
                object boxed = f.GetValue(w);
                if (!IsCreated(boxed))
                    continue;
                foreach (byte x in access.Read(boxed))
                {
                    h ^= x;
                    h *= 1099511628211UL;
                }
            }
            return h;
        }

        static readonly string[] HashedArrays =
        {
            "pos", "vel", "rest", "yield", "broken", "plasticWork", "hingeRest", "hingeBroken", "torsionBroken",
            "vehicleState", "wheelState", "pressureState", "clock",
        };

        // ------------------------------------------------------------------ files

        /// <summary>Standalone file: gzip-compressed.</summary>
        public void Write(Stream stream)
        {
            using var gz = new GZipStream(stream, CompressionLevel.Fastest, true);
            using var w = new BinaryWriter(gz);
            Write(w);
        }

        public static WorldState Read(Stream stream)
        {
            using var gz = new GZipStream(stream, CompressionMode.Decompress, true);
            using var r = new BinaryReader(gz);
            return Read(r);
        }

        /// <summary>Raw, into a writer (a recording embeds the state in its own compressed stream).</summary>
        public void Write(BinaryWriter w)
        {
            w.Write(Magic);
            w.Write(Version);
            w.Write(Steps);
            w.Write(NodeCount);
            w.Write(BeamCount);
            w.Write(entries.Count);
            foreach (var e in entries)
            {
                w.Write(e.name);
                w.Write(e.elemSize);
                w.Write(e.length);
                w.Write(e.data.Length);
                w.Write(e.data);
            }
            w.Write(poses.Count);
            foreach (var p in poses)
            {
                W3(w, p.position); W3(w, p.velocity); W3(w, p.angularVelocity);
                w.Write(p.rotation.value.x); w.Write(p.rotation.value.y); w.Write(p.rotation.value.z); w.Write(p.rotation.value.w);
                w.Write(p.clearance);
                w.Write(p.lift);
            }
        }

        public static WorldState Read(BinaryReader r)
        {
            if (r.ReadUInt32() != Magic)
                throw new InvalidDataException("not a world state");
            int ver = r.ReadInt32();
            if (ver != Version)
                throw new InvalidDataException($"world state version {ver}, expected {Version}");
            var s = new WorldState { Steps = r.ReadInt64(), NodeCount = r.ReadInt32(), BeamCount = r.ReadInt32() };
            int n = r.ReadInt32();
            for (int i = 0; i < n; i++)
            {
                var e = new Entry { name = r.ReadString(), elemSize = r.ReadInt32(), length = r.ReadInt32() };
                e.data = r.ReadBytes(r.ReadInt32());
                s.entries.Add(e);
            }
            int np = r.ReadInt32();
            for (int i = 0; i < np; i++)
            {
                var p = new BodyPose { position = R3(r), velocity = R3(r), angularVelocity = R3(r) };
                p.rotation = new quaternion(r.ReadSingle(), r.ReadSingle(), r.ReadSingle(), r.ReadSingle());
                p.clearance = r.ReadSingle();
                p.lift = r.ReadSingle();
                s.poses.Add(p);
            }
            return s;
        }

        static void W3(BinaryWriter w, float3 v)
        {
            w.Write(v.x); w.Write(v.y); w.Write(v.z);
        }

        static float3 R3(BinaryReader r) => new float3(r.ReadSingle(), r.ReadSingle(), r.ReadSingle());
    }
}
