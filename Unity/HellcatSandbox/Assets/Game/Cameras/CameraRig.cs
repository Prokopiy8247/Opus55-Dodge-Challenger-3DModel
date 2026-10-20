using Hellcat.Game.Core;
using Hellcat.Game.Views;
using Unity.Mathematics;
using UnityEngine;
using UnityEngine.InputSystem;

namespace Hellcat.Game.Cameras
{
    public enum CameraMode { Chase, Bumper, Cockpit, Free }

    /// <summary>
    /// The driving cameras (brief 4.12): a chase camera with damped follow, a bumper camera and the first-person cockpit
    /// camera at the driver's eye (brief 5.4), both riding on their camera mounts of the skeleton (geometry.json
    /// <c>cameras</c>: a few nodes and an offset; the mount turns with the best-fit rotation of its nodes, D-062), and a
    /// free camera for crash close-ups (hold the right mouse button to look, I/J/K/L to move, U/O down/up, Shift faster;
    /// gamepad right stick + shoulder-free d-pad). <see cref="Cycle"/> steps through the modes (C).
    /// </summary>
    [DefaultExecutionOrder(200)]   // after SoftBodyCarView (100): the mounts read this frame's node positions
    public class CameraRig : MonoBehaviour
    {
        public SimRunner runner;
        public CockpitInstruments instruments;
        public CameraMode mode = CameraMode.Chase;

        [Header("Chase")]
        public float distance = 6.4f;
        public float height = 1.9f;
        public float lookHeight = 0.85f;
        public float lookAhead = 2.5f;
        public float positionSmoothTime = 0.18f;
        public float headingSmoothTime = 0.3f;
        [Header("Field of view")]
        public float chaseFov = 55f, bumperFov = 72f, freeFov = 60f;
        [Tooltip("Horizontal degrees (cockpit.json, D-020)")]
        public float cockpitFovHorizontal = 85f;
        [Header("Free camera")]
        public float freeSpeed = 6f;
        public float freeLookSpeed = 0.12f;

        [Header("Bumper")]
        [Tooltip("Lens height above the ground and gap ahead of the front-most fascia node (m); the skeleton's mount sits behind the plastic")]
        public float bumperHeight = 0.62f, bumperGap = 0.09f;

        Camera cam;
        Vector3 offset, offsetVel, heading = Vector3.forward, headingVel;
        float smoothY, smoothYVel;
        bool chaseInitialized;
        float yaw, pitch;

        sealed class Mount
        {
            public int[] nodes;               // world node indices
            public float3[] rest;             // node offsets from the first node at the model pose
            public float3 offset;             // eye / lens position relative to the first node at the model pose
            public quaternion rot = quaternion.identity;
        }
        Mount cockpit, bumper;

        public string ModeName => mode.ToString();

        void Awake()
        {
            cam = GetComponent<Camera>();
        }

        void Start()
        {
            var s = GameSettings.Current;
            distance = s.chaseDistance;
            height = s.chaseHeight;
            chaseFov = s.chaseFov;
            bumperFov = s.bumperFov;
            cockpitFovHorizontal = s.cockpitFovHorizontal;
            freeSpeed = s.freeCameraSpeed;
            freeLookSpeed = s.mouseLookSpeed;
            if (runner == null || runner.World == null)
                return;
            var b = runner.World.bodies[runner.VehicleBody];
            foreach (var c in b.def.cameras)
            {
                if (c.nodes == null || c.nodes.Length < 3)
                    continue;
                var m = new Mount { nodes = new int[c.nodes.Length], rest = new float3[c.nodes.Length] };
                float3 p0 = P(b.def, c.nodes[0]);
                for (int k = 0; k < c.nodes.Length; k++)
                {
                    m.nodes[k] = b.nodeStart + c.nodes[k];
                    m.rest[k] = P(b.def, c.nodes[k]) - p0;
                }
                m.offset = c.offset != null && c.offset.Length == 3 ? new float3(c.offset[0], c.offset[1], c.offset[2]) : float3.zero;
                if (c.name == "bumper")
                {
                    // just ahead of the fascia at bumper height (D-071)
                    float front = float.MinValue;
                    foreach (var nd in b.def.nodes)
                        if (nd.name.StartsWith("fascia"))
                            front = math.max(front, nd.p[2]);
                    if (front > float.MinValue)
                        m.offset = new float3(0f, bumperHeight, front + bumperGap) - p0;
                }
                m.rot = runner.spawnPoint ? (quaternion)runner.spawnPoint.rotation : quaternion.identity;
                if (c.name == "cockpit") cockpit = m;
                else if (c.name == "bumper") bumper = m;
            }
            runner.Respawned += OnRespawned;
        }

        void OnDestroy()
        {
            if (runner) runner.Respawned -= OnRespawned;
        }

        static float3 P(Hellcat.Sim.Data.VehicleDef def, int i) => new float3(def.nodes[i].p[0], def.nodes[i].p[1], def.nodes[i].p[2]);

        void OnRespawned()
        {
            chaseInitialized = false;
            var st = runner.World.vehicleState[runner.VehicleIndex];
            float3 fwd = math.normalizesafe(new float3(st.forward.x, 0f, st.forward.z), new float3(0f, 0f, 1f));
            quaternion q = quaternion.LookRotationSafe(fwd, new float3(0f, 1f, 0f));
            if (cockpit != null) cockpit.rot = q;
            if (bumper != null) bumper.rot = q;
        }

        /// <summary>Puts the free camera at a pose (scripted captures); it stays there until moved.</summary>
        public void SetFreePose(Vector3 position, Vector3 lookAt)
        {
            mode = CameraMode.Free;
            transform.position = position;
            var e = Quaternion.LookRotation(lookAt - position, Vector3.up).eulerAngles;
            yaw = e.y;
            pitch = e.x > 180f ? e.x - 360f : e.x;
        }

        /// <summary>Next camera mode (C / gamepad Y); entering the free camera starts from the current view.</summary>
        public void Cycle()
        {
            mode = (CameraMode)(((int)mode + 1) % 4);
            if (mode == CameraMode.Chase)
                chaseInitialized = false;
            if (mode == CameraMode.Free)
            {
                var e = transform.rotation.eulerAngles;
                yaw = e.y;
                pitch = e.x > 180f ? e.x - 360f : e.x;
            }
        }

        void LateUpdate()
        {
            if (runner == null || runner.World == null || !runner.World.IsBuilt)
                return;
            float aspect = cam ? cam.aspect : 16f / 9f;
            switch (mode)
            {
                case CameraMode.Chase: Chase(); break;
                case CameraMode.Bumper: if (!OnMount(bumper, bumperFov, 0.05f)) Chase(); break;
                case CameraMode.Cockpit:
                    if (!OnMount(cockpit, Camera.HorizontalToVerticalFieldOfView(cockpitFovHorizontal, aspect), 0.01f)) Chase();
                    break;
                case CameraMode.Free: Free(); break;
            }
            if (instruments != null)
                instruments.mirrorsActive = mode == CameraMode.Cockpit;
        }

        void Chase()
        {
            if (cam) { cam.fieldOfView = chaseFov; cam.nearClipPlane = 0.1f; }
            var m = runner.World.Metrics(runner.VehicleBody, false);
            var st = runner.World.vehicleState[runner.VehicleIndex];
            Vector3 fwd = st.forward;
            fwd.y = 0f;
            if (fwd.sqrMagnitude < 1e-4f)
                fwd = heading;
            fwd.Normalize();
            Vector3 target = (Vector3)(float3)m.centerOfMass;
            if (!chaseInitialized)
            {
                heading = fwd;
                offset = -heading * distance + Vector3.up * height;
                offsetVel = headingVel = Vector3.zero;
                smoothY = target.y;
                chaseInitialized = true;
            }
            // the camera keeps its distance at any speed (the offset is damped, not the position): the heading lags a
            // little in turns and the height follows bumps softly
            float dt = Time.unscaledDeltaTime;
            heading = Vector3.SmoothDamp(heading, fwd, ref headingVel, headingSmoothTime, Mathf.Infinity, dt).normalized;
            offset = Vector3.SmoothDamp(offset, -heading * distance + Vector3.up * height, ref offsetVel, positionSmoothTime, Mathf.Infinity, dt);
            smoothY = Mathf.SmoothDamp(smoothY, target.y, ref smoothYVel, 0.12f, Mathf.Infinity, dt);
            var t = new Vector3(target.x, smoothY, target.z);
            transform.position = t + offset;
            transform.rotation = Quaternion.LookRotation(t + heading * lookAhead + Vector3.up * lookHeight - transform.position, Vector3.up);
        }

        /// <summary>Camera on a skeleton mount: position = first node + R offset, rotation R, R the best-fit rotation of the
        /// mount's nodes from the model pose (warm-started; the identity at the model pose looks along the car's +z).</summary>
        bool OnMount(Mount m, float fov, float near)
        {
            if (m == null)
                return false;
            var pos = runner.World.pos;
            float3 p0 = pos[m.nodes[0]];
            float3x3 s = float3x3.zero;
            for (int k = 1; k < m.nodes.Length; k++)
            {
                float3 x = pos[m.nodes[k]] - p0, X = m.rest[k];
                s += new float3x3(X * x.x, X * x.y, X * x.z);
            }
            m.rot = SoftBodyCarView.BestRotation(s, m.rot);
            transform.SetPositionAndRotation(p0 + math.mul(m.rot, m.offset), m.rot);
            if (cam) { cam.fieldOfView = fov; cam.nearClipPlane = near; }
            return true;
        }

        void Free()
        {
            if (cam) { cam.fieldOfView = freeFov; cam.nearClipPlane = 0.05f; }
            float dt = Time.unscaledDeltaTime;
            var kb = Keyboard.current;
            var mouse = Mouse.current;
            var pad = Gamepad.current;
            if (mouse != null && mouse.rightButton.isPressed)
            {
                Vector2 d = mouse.delta.ReadValue();
                yaw += d.x * freeLookSpeed;
                pitch = Mathf.Clamp(pitch - d.y * freeLookSpeed, -85f, 85f);
            }
            if (pad != null)
            {
                Vector2 r = pad.rightStick.ReadValue();
                yaw += r.x * 90f * dt;
                pitch = Mathf.Clamp(pitch - r.y * 90f * dt, -85f, 85f);
            }
            transform.rotation = Quaternion.Euler(pitch, yaw, 0f);
            Vector3 move = Vector3.zero;
            if (kb != null)
            {
                if (kb.iKey.isPressed) move += Vector3.forward;
                if (kb.kKey.isPressed) move += Vector3.back;
                if (kb.jKey.isPressed) move += Vector3.left;
                if (kb.lKey.isPressed) move += Vector3.right;
                if (kb.oKey.isPressed) move += Vector3.up;
                if (kb.uKey.isPressed) move += Vector3.down;
            }
            if (pad != null)
            {
                Vector2 dp = pad.dpad.ReadValue();
                move += new Vector3(dp.x, 0f, dp.y);
            }
            float speed = freeSpeed * (kb != null && kb.leftShiftKey.isPressed ? 4f : 1f);
            transform.position += transform.rotation * move * (speed * dt);
        }
    }
}
