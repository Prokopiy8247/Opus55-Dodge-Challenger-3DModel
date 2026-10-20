using Hellcat.Sim;
using Unity.Mathematics;
using UnityEngine;

namespace Hellcat.Game.World
{
    /// <summary>Infinite ground plane through this transform's position, normal = transform.up.</summary>
    public class StaticPlaneSource : MonoBehaviour, IStaticGeometrySource
    {
        public string surface = "asphalt";

        public void AddTo(StaticWorldBuilder builder)
        {
            float3 n = transform.up;
            builder.AddPlane(n, math.dot(n, (float3)transform.position), surface, name);
        }
    }
}
