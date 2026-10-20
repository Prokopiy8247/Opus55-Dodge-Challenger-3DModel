using System.Collections.Generic;
using Hellcat.Game.Core;
using Hellcat.Sim.Validation;
using Unity.Mathematics;
using UnityEngine;

namespace Hellcat.Game.Views
{
    /// <summary>
    /// The debug and showcase views (brief 4.12, 16). N: node-beam view alone (paint hidden); Shift+N: the same as an x-ray
    /// overlay over the paint. H: beam stress heat-map (opens the node-beam view if it is closed). Shift+H: deformation
    /// heat-map on the visual mesh, colour by each vertex's distance from where the undeformed car would put it (the
    /// model-pose position in UV3 carried by the cabin floor's rigid frame, <see cref="CarProbe.Pose"/>); the wheels and
    /// suspension keep their paint (they turn and travel without deforming).
    /// </summary>
    [DefaultExecutionOrder(300)]   // after CockpitInstruments (250): its rigid copies and mirror materials exist at Start
    public class DebugViews : MonoBehaviour
    {
        public enum SkeletonMode { Off, Alone, Overlay }

        public SimRunner runner;
        public SkeletonDebugView skeleton;
        public SoftBodyCarView car;
        public Material deformationMaterial;
        [Tooltip("Displacement shown red (m)")]
        public float deformationRange = 0.3f;

        public SkeletonMode Skeleton { get; private set; }
        public bool Stress { get; private set; }
        public bool Deformation { get; private set; }

        bool skeletonForStress;
        readonly List<(Renderer r, Material[] paint, bool heat)> renderers = new List<(Renderer, Material[], bool)>();
        CarProbe probe;
        static readonly int FrameId = Shader.PropertyToID("_HellcatBodyFrame");

        void Start()
        {
            if (car != null)
            {
                var wheelVisuals = new HashSet<string>();
                foreach (var part in runner.World.bodies[runner.VehicleBody].def.parts)
                    if (part.name.StartsWith("wheel") && part.visuals != null)
                        wheelVisuals.UnionWith(part.visuals);
                foreach (var r in car.GetComponentsInChildren<Renderer>(true))
                    renderers.Add((r, r.sharedMaterials, !wheelVisuals.Contains(r.name.Replace("_Live", ""))));
            }
            probe = new CarProbe(runner.World, runner.VehicleBody);
            runner.Rebuilt += OnRebuilt;
            if (skeleton != null)
                skeleton.Show(false);
            Apply();
        }

        void OnRebuilt() => probe = new CarProbe(runner.World, runner.VehicleBody);

        void OnDestroy()
        {
            if (runner) runner.Rebuilt -= OnRebuilt;
        }

        public void ToggleSkeleton(bool overlay)
        {
            var want = overlay ? SkeletonMode.Overlay : SkeletonMode.Alone;
            Skeleton = Skeleton == want ? SkeletonMode.Off : want;
            skeletonForStress = false;
            if (Skeleton == SkeletonMode.Off)
                Stress = false;
            Apply();
        }

        public void ToggleStress()
        {
            Stress = !Stress;
            if (Stress && Skeleton == SkeletonMode.Off)
            {
                Skeleton = SkeletonMode.Alone;
                skeletonForStress = true;
            }
            else if (!Stress && skeletonForStress)
            {
                Skeleton = SkeletonMode.Off;
                skeletonForStress = false;
            }
            Apply();
        }

        public void ToggleDeformation()
        {
            Deformation = !Deformation;
            Apply();
        }

        public void Apply()
        {
            if (skeleton != null)
            {
                skeleton.showStress = Stress;
                skeleton.SetOverlay(Skeleton == SkeletonMode.Overlay);
                skeleton.Show(Skeleton != SkeletonMode.Off);
            }
            bool paint = Skeleton != SkeletonMode.Alone;
            foreach (var (r, mats, heat) in renderers)
            {
                if (r == null)
                    continue;
                // renderers that other components switch (intact / shattered glass, rigid cockpit copies) keep their own
                // enabled state; the views hide them through a disabled layer of materials instead
                if (r is SkinnedMeshRenderer || r is MeshRenderer)
                    r.forceRenderingOff = !paint;
                if (Deformation && heat && deformationMaterial != null)
                {
                    var m = new Material[mats.Length];
                    for (int k = 0; k < m.Length; k++) m[k] = deformationMaterial;
                    r.sharedMaterials = m;
                }
                else
                {
                    r.sharedMaterials = mats;
                }
            }
            if (deformationMaterial != null)
                deformationMaterial.SetFloat("_Range", deformationRange);
        }

        void LateUpdate()
        {
            if (!Deformation || runner == null || runner.World == null)
                return;
            var rot = probe.Pose(out double3 origin);
            var m = Matrix4x4.identity;
            for (int r = 0; r < 3; r++)
                for (int c = 0; c < 3; c++)
                    m[r, c] = (float)rot[c][r];
            m.SetColumn(3, new Vector4((float)origin.x, (float)origin.y, (float)origin.z, 1f));
            Shader.SetGlobalMatrix(FrameId, m);
        }

        /// <summary>One-line state for the HUD.</summary>
        public string Describe()
        {
            var parts = new List<string>();
            if (Skeleton == SkeletonMode.Alone) parts.Add("node-beam view");
            if (Skeleton == SkeletonMode.Overlay) parts.Add("node-beam overlay");
            if (Stress) parts.Add("stress heat-map");
            if (Deformation) parts.Add($"deformation heat-map (red {deformationRange * 100f:F0} cm)");
            return string.Join(", ", parts);
        }
    }
}
