using UnityEngine;

namespace Hellcat.Game.World
{
    /// <summary>
    /// A named place to spawn the car (pause menu) and the approach to an obstacle for "teleport to obstacle N at speed V"
    /// (brief 4.12): the car is placed at this transform facing along its forward axis, settled, and launched at the
    /// chosen speed; <see cref="approachDistance"/> is the distance from the spawn to the obstacle face (shown in the menu).
    /// </summary>
    public class SpawnPoint : MonoBehaviour
    {
        public string label = "Spawn";
        [Tooltip("Order in the menu (obstacle number)")]
        public int order;
        [Tooltip("Distance from the spawn to the obstacle face along the heading (m); 0: not an obstacle approach")]
        public float approachDistance;
        [Tooltip("Default teleport speed (km/h)")]
        public float defaultKmh = 50f;
        [Tooltip("The teleport speed hold keeps going through drivable obstacles (ramps, ledges, debris) until the run-up time is over")]
        public bool holdThrough;

        void OnDrawGizmos()
        {
            Gizmos.color = new Color(0.2f, 0.9f, 0.3f, 0.8f);
            Gizmos.DrawWireCube(transform.position + Vector3.up * 0.7f, new Vector3(2f, 1.4f, 5f));
            Gizmos.DrawLine(transform.position + Vector3.up * 0.7f, transform.position + Vector3.up * 0.7f + transform.forward * 4f);
        }
    }
}
