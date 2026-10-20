using System;
using System.Collections.Generic;
using System.IO;
using Hellcat.Game.Core;
using Unity.Collections;
using Unity.Mathematics;
using UnityEngine;

namespace Hellcat.Game.Views
{
    /// <summary>
    /// The live cockpit (D-021, brief 5.4): tach and speedometer needles, steering wheel and pedals driven by the simulation,
    /// and the three mirrors showing the scene. The moving parts are taken off the skin: each becomes a rigid copy of its
    /// mesh that follows the best-fit frame of the nodes it was skinned to (so it rides with the dash in a crash) and turns
    /// about its pivot from cockpit.json (car frame in Blender axes, converted to Unity: (x, z, y); a rotation sense flips
    /// with the axes, so Blender's clockwise -angle becomes Unity's +angle). Each mirror glass gets a render texture from a
    /// camera at the glass looking along the reflected eye ray, mapped across the glass with the image flipped left to
    /// right; the mirror cameras run only while the cockpit camera is active.
    /// </summary>
    [DefaultExecutionOrder(250)]   // after CameraRig (200): the mirrors aim from this frame's eye
    public class CockpitInstruments : MonoBehaviour
    {
        public SimRunner runner;
        public SoftBodyCarView view;
        public Camera eyeCamera;
        public Shader mirrorShader;
        [Tooltip("Render the mirrors (only while the eye camera looks from the cockpit)")]
        public bool mirrors = true;
        public bool mirrorsActive;   // set by the camera rig: the cockpit view is on
        public int mirrorResolution = 384;
        [Tooltip("Side mirrors as a driver sets them: the centre of the view this far outboard of straight back (deg)")]
        public float sideMirrorOutwardDeg = 6f;

        /// <summary>Rigid frame of a few nodes (best-fit rotation from the model pose, D-062).</summary>
        sealed class NodeFrame
        {
            public int[] nodes;          // world indices
            public float3[] rest;        // model positions minus their centroid
            public float3 restCentroid;
            public quaternion rot = quaternion.identity;
            public float4x4 modelToWorld = float4x4.identity;

            public void Update(NativeArray<float3> pos)
            {
                float3 c = float3.zero;
                foreach (int n in nodes) c += pos[n];
                c /= nodes.Length;
                float3x3 s = float3x3.zero;
                for (int k = 0; k < nodes.Length; k++)
                {
                    float3 x = pos[nodes[k]] - c, X = rest[k];
                    s += new float3x3(X * x.x, X * x.y, X * x.z);
                }
                rot = SoftBodyCarView.BestRotation(s, rot);
                modelToWorld = new float4x4(rot, c - math.mul(rot, restCentroid));
            }
        }

        sealed class Moving
        {
            public string name;
            public NodeFrame frame;
            public Transform rigid;
            public Matrix4x4 meshToModel;   // mesh local -> car model frame at the bind pose
            public float3 pivot, axis;      // model frame, Unity axes
            public Func<float> angle;       // degrees about the axis (Unity sense)
        }

        sealed class Mirror
        {
            public string name;
            public NodeFrame frame;
            public float3 centre, right, up, normal;   // model frame; normal towards the driver
            public float3 viewDir;                     // model frame: a fixed (adjusted) view; zero: reflect the eye ray
            public float width, height;
            public Camera cam;
            public RenderTexture rt;
            public Material mat;
        }

        readonly List<Moving> moving = new List<Moving>();
        readonly List<Mirror> mirrorList = new List<Mirror>();
        Dictionary<Transform, int> boneIndex;

        // gauge values (for the HUD / checks)
        public float TachDeg { get; private set; }
        public float SpeedoDeg { get; private set; }
        public float WheelDeg { get; private set; }
        public int MovingParts => moving.Count;
        public int MirrorCount => mirrorList.Count;

        [Serializable] class GaugeDef { public float min, max, a_min, a_max; }
        [Serializable] class NeedleDef { public string @object; public float[] pivot, axis_to_eye; public GaugeDef gauge; }
        [Serializable] class Needles { public NeedleDef tach, speedo; }
        [Serializable] class WheelDef { public string @object; public float[] centre, axis_to_driver; public float lock_to_lock_turns; }
        [Serializable] class PedalDef { public string @object; public float[] pivot, axis; public float travel_deg; }
        [Serializable] class Pedals { public PedalDef accelerator, brake; }
        [Serializable] class InteriorMirrorDef { public string @object; public float[] centre, normal, right, up, glass_size; }
        [Serializable] class SideMirrors { public string left, right; }
        [Serializable] class CockpitFile
        {
            public float[] eye;
            public float fov_h_deg;
            public WheelDef steering_wheel;
            public Needles needles;
            public Pedals pedals;
            public InteriorMirrorDef interior_mirror;
            public SideMirrors side_mirrors;
        }

        public float FovHorizontal { get; private set; } = 85f;

        static float3 U(float[] b) => new float3(b[0], b[2], b[1]);   // Blender (x, y fwd, z up) -> Unity (x, y up, z fwd)

        void Start()
        {
            if (runner == null || runner.World == null || view == null)
                return;
            string path = Path.Combine(SimRunner.VehicleFolder(runner.vehicleName), "cockpit.json");
            if (!File.Exists(path))
            {
                Debug.LogWarning($"[CockpitInstruments] {path} missing: no live cockpit");
                enabled = false;
                return;
            }
            var ck = JsonUtility.FromJson<CockpitFile>(File.ReadAllText(path));
            FovHorizontal = ck.fov_h_deg > 0f ? ck.fov_h_deg : 85f;
            boneIndex = new Dictionary<Transform, int>();
            for (int i = 0; i < view.nodeBones.Length; i++)
                boneIndex[view.nodeBones[i]] = i;
            var smrs = new Dictionary<string, SkinnedMeshRenderer>();
            foreach (var smr in view.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                smrs[smr.name] = smr;

            if (ck.needles?.tach != null)
                AddMoving(smrs, ck.needles.tach.@object, U(ck.needles.tach.pivot), U(ck.needles.tach.axis_to_eye),
                    () => TachDeg = Gauge(ck.needles.tach.gauge, runner.World.vehicleState[runner.VehicleIndex].engineRpm));
            if (ck.needles?.speedo != null)
                AddMoving(smrs, ck.needles.speedo.@object, U(ck.needles.speedo.pivot), U(ck.needles.speedo.axis_to_eye),
                    () => SpeedoDeg = Gauge(ck.needles.speedo.gauge, math.abs(runner.World.vehicleState[runner.VehicleIndex].speed) * 2.236936f));
            if (ck.steering_wheel != null)
            {
                float half = 0.5f * ck.steering_wheel.lock_to_lock_turns * 360f;
                AddMoving(smrs, ck.steering_wheel.@object, U(ck.steering_wheel.centre), U(ck.steering_wheel.axis_to_driver),
                    () => WheelDeg = runner.World.vehicleState[runner.VehicleIndex].steer * half);
            }
            if (ck.pedals?.accelerator != null)
                AddMoving(smrs, ck.pedals.accelerator.@object, U(ck.pedals.accelerator.pivot), U(ck.pedals.accelerator.axis),
                    () => ck.pedals.accelerator.travel_deg * runner.LastInput.throttle);
            if (ck.pedals?.brake != null)
                AddMoving(smrs, ck.pedals.brake.@object, U(ck.pedals.brake.pivot), U(ck.pedals.brake.axis),
                    () => ck.pedals.brake.travel_deg * math.max(runner.LastInput.brake, 0f));

            if (mirrorShader != null)
            {
                if (ck.interior_mirror != null && smrs.TryGetValue(ck.interior_mirror.@object, out var im))
                {
                    var g = ck.interior_mirror.glass_size;
                    AddMirror(im, "CH_Int_MirrorGlass", U(ck.interior_mirror.centre), U(ck.interior_mirror.right), U(ck.interior_mirror.up),
                        U(ck.interior_mirror.normal), g[0], g[1]);
                }
                foreach (var side in new[] { ck.side_mirrors?.left, ck.side_mirrors?.right })
                    if (side != null && smrs.TryGetValue(side, out var sm))
                        AddSideMirror(sm);
            }
            runner.Respawned += ResetFrames;
            Debug.Log($"[CockpitInstruments] {moving.Count} moving parts, {mirrorList.Count} mirrors, cockpit FOV {FovHorizontal:F0} deg horizontal");
        }

        void OnDestroy()
        {
            if (runner) runner.Respawned -= ResetFrames;
            foreach (var m in mirrorList)
                if (m.rt != null) m.rt.Release();
        }

        /// <summary>Writes each mirror's current image (checks, report).</summary>
        public void SaveMirrors(string folder)
        {
            Directory.CreateDirectory(folder);
            foreach (var m in mirrorList)
            {
                var prev = RenderTexture.active;
                RenderTexture.active = m.rt;
                var tex = new Texture2D(m.rt.width, m.rt.height, TextureFormat.RGB24, false);
                tex.ReadPixels(new Rect(0, 0, m.rt.width, m.rt.height), 0, 0);
                tex.Apply();
                RenderTexture.active = prev;
                File.WriteAllBytes(Path.Combine(folder, $"mirror_{m.name}.png"), tex.EncodeToPNG());
                Destroy(tex);
            }
        }

        static float Gauge(GaugeDef g, float value)
        {
            float t = math.saturate((value - g.min) / math.max(g.max - g.min, 1e-6f));
            return g.a_min + t * (g.a_max - g.a_min);
        }

        NodeFrame FrameOf(SkinnedMeshRenderer smr, out Matrix4x4 meshToModel)
        {
            var def = runner.World.bodies[runner.VehicleBody].def;
            int start = runner.World.bodies[runner.VehicleBody].nodeStart;
            var locals = new List<int>();
            foreach (var bone in smr.bones)
                if (bone != null && boneIndex.TryGetValue(bone, out int li) && !locals.Contains(li))
                    locals.Add(li);
            var f = new NodeFrame { nodes = new int[locals.Count], rest = new float3[locals.Count] };
            float3 c = float3.zero;
            for (int k = 0; k < locals.Count; k++)
            {
                var p = def.nodes[locals[k]].p;
                f.rest[k] = new float3(p[0], p[1], p[2]);
                c += f.rest[k];
                f.nodes[k] = start + locals[k];
            }
            c /= math.max(locals.Count, 1);
            for (int k = 0; k < locals.Count; k++)
                f.rest[k] -= c;
            f.restCentroid = c;
            var p0 = def.nodes[boneIndex[smr.bones[0]]].p;
            meshToModel = Matrix4x4.Translate(new Vector3(p0[0], p0[1], p0[2])) * smr.sharedMesh.bindposes[0];
            f.rot = runner.spawnPoint ? (quaternion)runner.spawnPoint.rotation : quaternion.identity;
            return f;
        }

        void AddMoving(Dictionary<string, SkinnedMeshRenderer> smrs, string obj, float3 pivot, float3 axis, Func<float> angle)
        {
            if (obj == null || !smrs.TryGetValue(obj, out var smr) || smr.bones.Length == 0)
                return;
            var f = FrameOf(smr, out var meshToModel);
            if (f.nodes.Length < 3)
                return;
            var go = new GameObject(obj + "_Live");
            go.transform.SetParent(transform, false);
            go.AddComponent<MeshFilter>().sharedMesh = smr.sharedMesh;
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterials = smr.sharedMaterials;
            mr.shadowCastingMode = smr.shadowCastingMode;
            smr.enabled = false;
            moving.Add(new Moving { name = obj, frame = f, rigid = go.transform, meshToModel = meshToModel, pivot = pivot, axis = math.normalize(axis), angle = angle });
        }

        void AddMirror(SkinnedMeshRenderer smr, string glassMaterial, float3 centre, float3 right, float3 up, float3 normal, float w, float h)
        {
            var f = FrameOf(smr, out _);
            if (f.nodes.Length < 3)
                return;
            var mats = smr.sharedMaterials;
            int slot = Array.FindIndex(mats, m => m != null && m.name.StartsWith(glassMaterial));
            if (slot < 0)
                slot = mats.Length - 1;
            var m = new Mirror { name = smr.name, frame = f, centre = centre, right = math.normalize(right), up = math.normalize(up), normal = math.normalize(normal), width = w, height = h };
            m.rt = new RenderTexture(mirrorResolution, math.max(16, (int)(mirrorResolution * h / w)), 16) { name = smr.name + "_Mirror" };
            m.mat = new Material(mirrorShader) { name = smr.name + "_MirrorGlass" };
            m.mat.SetTexture("_MirrorTex", m.rt);
            mats[slot] = m.mat;
            smr.sharedMaterials = mats;
            var camGo = new GameObject(smr.name + "_MirrorCamera");
            camGo.transform.SetParent(transform, false);
            m.cam = camGo.AddComponent<Camera>();
            m.cam.targetTexture = m.rt;
            m.cam.depth = -10;
            m.cam.nearClipPlane = 0.05f;
            m.cam.farClipPlane = 400f;
            CameraSky.Apply(m.cam);
            m.cam.enabled = false;
            mirrorList.Add(m);
        }

        /// <summary>Side mirror glass: a flat pane facing back; its frame from the mesh's bind-pose bounds.</summary>
        void AddSideMirror(SkinnedMeshRenderer smr)
        {
            var p0 = runner.World.bodies[runner.VehicleBody].def.nodes[boneIndex[smr.bones[0]]].p;
            var meshToModel = Matrix4x4.Translate(new Vector3(p0[0], p0[1], p0[2])) * smr.sharedMesh.bindposes[0];
            Vector3 lo = Vector3.positiveInfinity, hi = Vector3.negativeInfinity;
            foreach (var v in smr.sharedMesh.vertices)
            {
                var q = meshToModel.MultiplyPoint3x4(v);
                lo = Vector3.Min(lo, q);
                hi = Vector3.Max(hi, q);
            }
            float3 c = 0.5f * (float3)(lo + hi);
            AddMirror(smr, "CH_Mirror_Glass", c, new float3(1f, 0f, 0f), new float3(0f, 1f, 0f), new float3(0f, 0f, -1f), hi.x - lo.x, hi.y - lo.y);
            // the exported glass is flat, facing straight back; a driver turns it until the car's flank just shows
            float a = math.radians(sideMirrorOutwardDeg);
            mirrorList[mirrorList.Count - 1].viewDir = math.normalize(new float3(math.sign(c.x) * math.sin(a), -0.035f, -math.cos(a)));
        }

        void ResetFrames()
        {
            var st = runner.World.vehicleState[runner.VehicleIndex];
            float3 fwd = math.normalizesafe(new float3(st.forward.x, 0f, st.forward.z), new float3(0f, 0f, 1f));
            quaternion q = quaternion.LookRotationSafe(fwd, new float3(0f, 1f, 0f));
            foreach (var m in moving) m.frame.rot = q;
            foreach (var m in mirrorList) m.frame.rot = q;
        }

        void LateUpdate()
        {
            if (runner == null || runner.World == null || !runner.World.IsBuilt)
                return;
            var pos = runner.World.pos;
            foreach (var m in moving)
            {
                m.frame.Update(pos);
                Matrix4x4 pivotRot = Matrix4x4.Translate(m.pivot) * Matrix4x4.Rotate(Quaternion.AngleAxis(m.angle(), m.axis)) * Matrix4x4.Translate(-m.pivot);
                Matrix4x4 world = (Matrix4x4)m.frame.modelToWorld * pivotRot * m.meshToModel;
                m.rigid.SetPositionAndRotation(world.GetColumn(3), world.rotation);
            }
            bool render = mirrors && mirrorsActive && eyeCamera != null;
            foreach (var m in mirrorList)
            {
                m.cam.enabled = render;
                m.frame.Update(pos);
                float4x4 mw = m.frame.modelToWorld;
                float3 c = math.transform(mw, m.centre);
                float3 right = math.rotate(m.frame.rot, m.right), up = math.rotate(m.frame.rot, m.up), n = math.rotate(m.frame.rot, m.normal);
                m.mat.SetVector("_MirrorCentre", new Vector4(c.x, c.y, c.z, 0f));
                m.mat.SetVector("_MirrorRight", new Vector4(right.x, right.y, right.z, 0f) / m.width);
                m.mat.SetVector("_MirrorUp", new Vector4(up.x, up.y, up.z, 0f) / m.height);
                if (!render)
                    continue;
                float3 eye = eyeCamera.transform.position;
                float3 d = math.normalizesafe(c - eye);
                float3 r = math.lengthsq(m.viewDir) > 0f ? math.rotate(m.frame.rot, m.viewDir) : d - 2f * math.dot(d, n) * n;
                m.cam.transform.SetPositionAndRotation(c, Quaternion.LookRotation(r, up));
                float dist = math.max(math.distance(c, eye), 0.1f);
                m.cam.fieldOfView = 2f * math.degrees(math.atan(0.5f * m.height / dist)) * 1.6f;
                m.cam.aspect = m.width / m.height;
            }
        }
    }
}
