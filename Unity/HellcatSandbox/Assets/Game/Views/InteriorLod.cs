using System;
using System.Collections.Generic;
using System.Linq;
using Hellcat.Game.Cameras;
using UnityEngine;

namespace Hellcat.Game.Views
{
    /// <summary>
    /// Interior level of detail while driving outside the car (brief 4.12, P7). The cockpit camera, or any camera inside the
    /// cabin, draws the whole interior; from outside only the parts seen through the glass are drawn (seats, dash, steering
    /// wheel, headliner, pillar and quarter trims, parcel shelf); far away only the seats; beyond that none. Disabled
    /// renderers are not skinned either. Crash scenarios and the map check draw everything (their capture cameras are not
    /// the main camera); the drive test, the controls check and the showcase measure the game as it is played.
    /// </summary>
    [DefaultExecutionOrder(300)]   // after the camera rig (200) placed the camera and the cockpit (250) made its live copies
    public class InteriorLod : MonoBehaviour
    {
        public enum Level { Full, Outside, Far, Culled }

        public SoftBodyCarView view;
        public CameraRig cameras;
        public Camera eye;
        [Tooltip("m from the cabin within which a camera counts as inside (free camera)")]
        public float insideRadius = 2.2f;
        [Tooltip("m from the cabin beyond which only the seats are drawn")]
        public float farDistance = 35f;
        [Tooltip("m from the cabin beyond which no interior part is drawn")]
        public float cullDistance = 90f;

        static readonly string[] OutsideParts = { "CH_Int_Seat", "CH_Int_Dash", "CH_Int_SteeringWheel", "CH_Int_Headliner",
            "CH_Int_APillar", "CH_Int_BPillar", "CH_Int_QuarterTrim", "CH_Int_PackageShelf", "CH_Int_ClusterHood" };
        static readonly string[] FarParts = { "CH_Int_Seat" };

        public Level Current { get; private set; } = Level.Full;
        public int Managed => parts.Count;
        public int TrianglesFull { get; private set; }
        public int TrianglesOutside { get; private set; }

        struct Part
        {
            public Renderer renderer;
            public bool outside, far;
        }

        readonly List<Part> parts = new List<Part>();
        Transform cabin;

        static readonly string[] FullDetailScenarios = { "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "mapcheck", "wall", "crash" };

        void Start()
        {
            var args = Environment.GetCommandLineArgs();
            int si = Array.FindIndex(args, a => string.Equals(a, "-scenario", StringComparison.OrdinalIgnoreCase));
            if (si >= 0 && si + 1 < args.Length && FullDetailScenarios.Any(s => string.Equals(s, args[si + 1], StringComparison.OrdinalIgnoreCase)))
            {
                enabled = false;
                return;
            }
            if (view == null)
                view = GetComponent<SoftBodyCarView>();
            if (eye == null)
                eye = Camera.main;
            if (view == null || eye == null)
            {
                enabled = false;
                return;
            }
            // the skinned interior parts and the cockpit's rigid live copies of its moving parts (needles, wheel, pedals:
            // "<part>_Live", their skinned originals already switched off); the mirrors and parts already off are left alone
            foreach (var r in view.GetComponentsInChildren<Renderer>(true))
            {
                if (!(r is SkinnedMeshRenderer || r is MeshRenderer) || !r.name.StartsWith("CH_Int_", StringComparison.Ordinal) ||
                    r.name.Contains("Mirror") || !r.enabled)
                    continue;
                bool outside = OutsideParts.Any(p => r.name.StartsWith(p, StringComparison.Ordinal));
                bool far = FarParts.Any(p => r.name.StartsWith(p, StringComparison.Ordinal));
                parts.Add(new Part { renderer = r, outside = outside, far = far });
                Mesh mesh = null;
                if (r is SkinnedMeshRenderer smr)
                    mesh = smr.sharedMesh;
                else if (r.TryGetComponent<MeshFilter>(out var mf))
                    mesh = mf.sharedMesh;
                int tris = mesh != null ? (int)(mesh.triangles.LongLength / 3) : 0;
                TrianglesFull += tris;
                if (outside) TrianglesOutside += tris;
            }
            // the cabin reference: the node bone nearest the driver's seat
            var seat = parts.FirstOrDefault(p => p.renderer.name.StartsWith("CH_Int_Seat_FL", StringComparison.Ordinal)).renderer;
            Vector3 c = seat != null ? seat.bounds.center : view.transform.position;
            float best = float.MaxValue;
            foreach (var t in view.nodeBones ?? new Transform[0])
            {
                float d = (t.position - c).sqrMagnitude;
                if (d < best)
                {
                    best = d;
                    cabin = t;
                }
            }
            if (cabin == null)
                cabin = view.transform;
            Debug.Log($"[InteriorLod] {parts.Count} interior parts, {TrianglesFull} triangles; {TrianglesOutside} drawn from outside");
        }

        void LateUpdate()
        {
            Level want;
            if (cameras != null && cameras.mode == CameraMode.Cockpit)
                want = Level.Full;
            else
            {
                float d = Vector3.Distance(eye.transform.position, cabin.position);
                want = d < insideRadius ? Level.Full : d < farDistance ? Level.Outside : d < cullDistance ? Level.Far : Level.Culled;
            }
            if (want != Current)
                Apply(want);
        }

        void Apply(Level level)
        {
            Current = level;
            foreach (var p in parts)
            {
                if (p.renderer == null)
                    continue;
                p.renderer.enabled = level == Level.Full || (level == Level.Outside && p.outside) || (level == Level.Far && p.far);
            }
        }

        void OnDisable()
        {
            if (parts.Count > 0)
                Apply(Level.Full);
        }
    }
}
