using Hellcat.Sim;
using UnityEngine;

namespace Hellcat.Game.World
{
    /// <summary>Cylinder along the transform's up axis (Unity cylinder primitive: height 2, radius 0.5 at scale 1).</summary>
    public class StaticCylinderSource : MonoBehaviour, IStaticGeometrySource
    {
        public string surface = "steel";

        public void AddTo(StaticWorldBuilder builder)
        {
            Vector3 s = transform.lossyScale;
            builder.AddCylinder(transform.position, transform.rotation, 0.5f * Mathf.Max(s.x, s.z), s.y, surface, name);
        }
    }
}
