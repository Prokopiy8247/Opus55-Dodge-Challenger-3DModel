using Hellcat.Sim;
using Unity.Mathematics;
using UnityEngine;

namespace Hellcat.Game.World
{
    /// <summary>Oriented box matching a unit cube scaled by the transform (Unity cube primitive).</summary>
    public class StaticBoxSource : MonoBehaviour, IStaticGeometrySource
    {
        public string surface = "concrete";

        public void AddTo(StaticWorldBuilder builder)
        {
            builder.AddBox(transform.position, transform.rotation, 0.5f * (float3)transform.lossyScale, surface, name);
        }
    }
}
