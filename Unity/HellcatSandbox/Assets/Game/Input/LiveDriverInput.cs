using Hellcat.Game.Core;
using Hellcat.Sim.Vehicle;
using UnityEngine;
using UnityEngine.InputSystem;

namespace Hellcat.Game.Input
{
    /// <summary>
    /// Keyboard and gamepad driving controls (Unity Input System). W/RT throttle, S/LT brake (holding
    /// it at standstill engages reverse), A/D/left stick steer, Space/B handbrake, Q/E or LB/RB gears.
    /// Keyboard steering is digital; the vehicle controller rate-limits and speed-scales it. Runs before the simulation
    /// runner, so a key read this frame drives this frame's substeps (one frame less input latency).
    /// </summary>
    [DefaultExecutionOrder(-200)]
    public class LiveDriverInput : MonoBehaviour, IDriverInputSource
    {
        public SimRunner runner;
        public float reverseEngageDelay = 0.3f;
        public float throttleRise = 6f, throttleFall = 10f; // keyboard pedal smoothing (1/s)

        public int Priority => 0;
        public bool Active => enabled;
        public int SelectedGear { get; private set; } = 1;
        public bool Reverse => SelectedGear < 0;
        public int ManualGearRequest { get; set; } = 0; // engine mode: 0 = automatic
        public bool abs = true, tc = true;               // driver aids (F7 / F8, settings.json)
        /// <summary>The driver touched a pedal, the steering, the handbrake or a gear key this frame (ends a teleport's
        /// speed hold).</summary>
        public bool Touched { get; private set; }

        InputAction throttleAction, brakeAction, steerAction, handbrakeAction, gearUpAction, gearDownAction;
        float throttle, brake;
        float stopTimer;
        DriverInput current = DriverInput.Idle;

        void Awake()
        {
            throttleAction = new InputAction("throttle", InputActionType.Value);
            throttleAction.AddBinding("<Keyboard>/w");
            throttleAction.AddBinding("<Keyboard>/upArrow");
            throttleAction.AddBinding("<Gamepad>/rightTrigger");
            brakeAction = new InputAction("brake", InputActionType.Value);
            brakeAction.AddBinding("<Keyboard>/s");
            brakeAction.AddBinding("<Keyboard>/downArrow");
            brakeAction.AddBinding("<Gamepad>/leftTrigger");
            steerAction = new InputAction("steer", InputActionType.Value);
            steerAction.AddCompositeBinding("1DAxis").With("Negative", "<Keyboard>/a").With("Positive", "<Keyboard>/d");
            steerAction.AddCompositeBinding("1DAxis").With("Negative", "<Keyboard>/leftArrow").With("Positive", "<Keyboard>/rightArrow");
            steerAction.AddBinding("<Gamepad>/leftStick/x");
            handbrakeAction = new InputAction("handbrake", InputActionType.Value);
            handbrakeAction.AddBinding("<Keyboard>/space");
            handbrakeAction.AddBinding("<Gamepad>/buttonEast");
            gearUpAction = new InputAction("gearUp", InputActionType.Button);
            gearUpAction.AddBinding("<Keyboard>/e");
            gearUpAction.AddBinding("<Gamepad>/rightShoulder");
            gearDownAction = new InputAction("gearDown", InputActionType.Button);
            gearDownAction.AddBinding("<Keyboard>/q");
            gearDownAction.AddBinding("<Gamepad>/leftShoulder");
        }

        void OnEnable()
        {
            foreach (var a in new[] { throttleAction, brakeAction, steerAction, handbrakeAction, gearUpAction, gearDownAction })
                a.Enable();
            if (runner)
                runner.RegisterInput(this);
        }

        void OnDisable()
        {
            foreach (var a in new[] { throttleAction, brakeAction, steerAction, handbrakeAction, gearUpAction, gearDownAction })
                a.Disable();
            if (runner)
                runner.UnregisterInput(this);
        }

        void Update()
        {
            float dt = Time.unscaledDeltaTime;
            float tIn = Mathf.Clamp01(throttleAction.ReadValue<float>());
            float bIn = Mathf.Clamp01(brakeAction.ReadValue<float>());
            bool analog = Gamepad.current != null && (Gamepad.current.rightTrigger.IsActuated() || Gamepad.current.leftTrigger.IsActuated());
            throttle = analog ? tIn : Mathf.MoveTowards(throttle, tIn, (tIn > throttle ? throttleRise : throttleFall) * dt);
            brake = analog ? bIn : Mathf.MoveTowards(brake, bIn, (bIn > brake ? throttleRise : throttleFall) * dt);

            float speed = runner && runner.World != null ? runner.World.vehicleState[runner.VehicleIndex].speed : 0f;
            // Arcade reverse: hold brake at standstill to engage reverse; throttle at standstill returns to drive.
            if (Mathf.Abs(speed) < 0.8f)
            {
                bool wantsReverse = !Reverse && bIn > 0.5f && tIn < 0.1f;
                bool wantsDrive = Reverse && tIn > 0.5f && bIn < 0.1f;
                stopTimer = wantsReverse || wantsDrive ? stopTimer + dt : 0f;
                if (stopTimer > reverseEngageDelay)
                {
                    SelectedGear = wantsReverse ? -1 : 1;
                    stopTimer = 0f;
                }
            }
            else
            {
                stopTimer = 0f;
            }
            Touched = tIn > 0.05f || bIn > 0.05f || Mathf.Abs(steerAction.ReadValue<float>()) > 0.1f ||
                      handbrakeAction.ReadValue<float>() > 0.1f || gearUpAction.WasPressedThisFrame() || gearDownAction.WasPressedThisFrame();
            if (gearUpAction.WasPressedThisFrame())
                ManualGearRequest = Mathf.Max(ManualGearRequest, 0) + 1;
            if (gearDownAction.WasPressedThisFrame())
                ManualGearRequest = Mathf.Max(ManualGearRequest - 1, 0);

            current = new DriverInput
            {
                throttle = Reverse ? brake : throttle,
                brake = Reverse ? throttle : brake,
                handbrake = Mathf.Clamp01(handbrakeAction.ReadValue<float>()),
                steer = Mathf.Clamp(steerAction.ReadValue<float>(), -1f, 1f),
                gear = Reverse ? -1 : (ManualGearRequest > 0 ? ManualGearRequest : DriverInput.Drive),
                flags = (abs ? DriverInput.FlagAbs : 0) | (tc ? DriverInput.FlagTc : 0),
            };
            if (runner && runner.VehicleParams != null && runner.VehicleParams.powertrain.mode != "engine")
                current.gear = Reverse ? -1 : 1;
        }

        public DriverInput Sample(long substepIndex, in VehicleState state) => current;
    }
}
