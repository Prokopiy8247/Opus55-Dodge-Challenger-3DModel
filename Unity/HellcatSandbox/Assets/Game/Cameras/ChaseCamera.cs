using Hellcat.Game.Core;
using Unity.Mathematics;
using UnityEngine;

namespace Hellcat.Game.Cameras
{
    /// <summary>Damped follow camera behind the vehicle (heading from the vehicle controller).</summary>
    public class ChaseCamera : MonoBehaviour
    {
        public SimRunner runner;
        public float distance = 7.5f;
        public float height = 2.4f;
        public float lookHeight = 0.8f;
        public float lookAhead = 2f;
        public float positionSmoothTime = 0.25f;
        public float headingSmoothTime = 0.35f;

        Vector3 velocity;
        Vector3 heading = Vector3.forward;
        Vector3 headingVel;
        bool initialized;

        public Vector3 Target { get; private set; }

        void LateUpdate()
        {
            if (runner == null || runner.World == null)
                return;
            var m = runner.World.Metrics(runner.VehicleBody, false);
            var st = runner.World.vehicleState[runner.VehicleIndex];
            Vector3 fwd = st.forward;
            fwd.y = 0f;
            if (fwd.sqrMagnitude < 1e-4f)
                fwd = heading;
            fwd.Normalize();
            Target = (Vector3)(float3)m.centerOfMass;
            if (!initialized)
            {
                heading = fwd;
                transform.position = Target - heading * distance + Vector3.up * height;
                initialized = true;
            }
            heading = Vector3.SmoothDamp(heading, fwd, ref headingVel, headingSmoothTime).normalized;
            Vector3 desired = Target - heading * distance + Vector3.up * height;
            transform.position = Vector3.SmoothDamp(transform.position, desired, ref velocity, positionSmoothTime);
            transform.rotation = Quaternion.LookRotation(Target + heading * lookAhead + Vector3.up * lookHeight - transform.position, Vector3.up);
        }

        public void Snap()
        {
            initialized = false;
            velocity = Vector3.zero;
        }
    }
}
