using Unity.Mathematics;

namespace Hellcat.Sim.Vehicle
{
    /// <summary>Driver controls for one substep (game layer or replay).</summary>
    public struct DriverInput
    {
        public float throttle;   // 0..1
        public float brake;      // 0..1
        public float handbrake;  // 0..1
        public float steer;      // -1 (left) .. +1 (right), raw (smoothing happens in the control job)
        public int gear;         // requested gear: -1 reverse, 0 neutral, 1..n hold that gear (manual), Drive = automatic
        public int flags;        // bit 0: ABS on, bit 1: traction control on

        public const int Drive = 99;
        public const int FlagAbs = 1, FlagTc = 2;

        /// <summary>No pedals, automatic drive (the default input).</summary>
        public static DriverInput Idle => new DriverInput { gear = Drive };
        /// <summary>No pedals, gearbox in neutral.</summary>
        public static DriverInput Neutral => new DriverInput { gear = 0 };
    }

    public static class PowertrainMode
    {
        public const int Simple = 0; // torque source with a power cap (vertical slice)
        public const int Engine = 1; // torque curve, converter, automatic gearbox, LSD (P3b, D-042)
    }

    public struct WheelStatic
    {
        public int vehicle;
        public int axleInner, axleOuter, arm;
        public float axisSign;               // +1 right wheels, -1 left: spin axis = sign * (outer - inner) points to the car's right,
                                             // so omega > 0 and drive torque > 0 mean forward rolling on every wheel
        public int rimStart, rimCount;       // into rimNodes
        public int treadStart, treadCount;   // into treadNodes
        public int knuckleStart, knuckleCount; // into knuckleNodes: off-axis nodes braced to both axle nodes (reaction couple)
        public int slotStart;                // rimCount + knuckleCount + 2 + driveCount + windupCount slots: rim nodes, knuckle
                                             // nodes, axle inner, axle outer, drive reaction nodes, wind-up body nodes
        public int driveStart, driveCount;   // into driveNodes: the differential (drive torque reaction, D-036)
        public int windupStart, windupCount; // into windupNodes: body nodes of the wind-up couple (D-036), after the drive slots
        public float windupK, windupC, windupStrength; // N*m/rad, N*m*s/rad, N*m (float.MaxValue: never tears)
        public int windupRef;                // global node: the knuckle node farthest from the axle line (-1: integrate)
        public float windupPhi0;             // rad: its angle about the axle from the body frame's up at the model pose (D-069)
        // alignment element (D-049): camber / toe spring-dampers towards static + gain x travel (rad, rad/m)
        public float camberK, camberC, toeK, toeC, camberStatic, toeStatic, camberGain, bumpSteer;
        public float travel0;                // m: hub height over the wind-up body nodes along the body's up at spawn
        public float3 kingpin;               // camber reference axis in model coordinates: the steering axis (lower to upper
                                             // ball joint) of a steered knuckle, up otherwise (D-051)
        public float kingpinPhi0;            // rad: model angle between the axle line and that axis, less the model camber
        public float side;                   // +1 right, -1 left (model x)
        public int wheelGroup;               // break group of the wheel's links (torn off: no wind-up couple, no drive), -1 none
        public float knuckleInertia;         // kg*m^2 of the knuckle reaction nodes about the axis (centroid radii)
        public int driven, steered;
        public int front;                    // 1: front axle (aero lift share)
        public float brakeTorque, handbrakeTorque;
        public float stickK, stickC;         // brake holding spring (N*m/rad) and damping (N*m*s/rad)
        public float radius;
        public float rimInertia;             // kg*m^2 of the rim ring nodes about the axis
        public float meshRollingResistance;  // C_rr the tire mesh produces itself (subtracted from the surface value, D-043)
    }

    public struct WheelState
    {
        public float omega;        // rad/s about the axle axis (inner -> outer), relative to the knuckle
        public float omegaAbs;     // rad/s, rim rotation about the axis in the world (rolling over the ground)
        public float omegaShaft;   // rad/s, rim rotation relative to the differential housing (half-shaft twist rate)
        public float vx;           // m/s, hub velocity along the wheel's heading
        public float slipRatio;    // (omegaAbs R - vx) / max(|vx|, 1 m/s): > 0 spinning, < 0 braking slip
        public float stickAngle;   // rad, brake holding spring deflection
        public int stuck;          // 1 while the brake holds the wheel
        public float absFactor;    // ABS brake pressure fraction (1: full)
        public float absI;         // ABS integrator (pressure fraction)
        public float absSlip;      // m/s, filtered braking slip speed v - omega R (ABS input)
        public float load;         // N, sum of tread contact normal forces
        public float driveTorque, brakeTorque, totalTorque; // telemetry, N*m
        public float slipSpeed;    // m/s, mean tread slip speed of loaded nodes
        public float windupAngle;  // rad, knuckle rotation about the axis relative to the body (D-036): integrated, and
                                   // pulled towards the angle read from the pose with a 1 s time constant (D-069)
        public int windupBroken;   // 1 once torn (wheel off, or above the strength)
        public float windupTorque; // telemetry, N*m on the knuckle
        public float camber, toe, travel; // telemetry (D-049): rad relative to the body (top out, toe-in positive), m of bump
        public double windupDamped; // J dissipated by the wind-up damper
    }

    public struct VehicleStatic
    {
        public int wheelStart, wheelCount;
        public int steerHydro;               // hydro input index, -1 none
        public int refStart, refCount;       // into refNodes: chassis nodes used for speed/heading
        public int mode;                     // PowertrainMode
        public float maxWheelTorque, maxPower, reverseTorque;
        public float steerRate, steerReturnRate, steerReductionStart, steerReductionAt60;
        public int drivenCount;
        public int body;
        public float mass;                   // kg (aero acceleration)
        // engine mode (D-042); speeds in rad/s
        public int curveStart, curveCount;   // into engineCurve: (rad/s, N*m) full-throttle net torque
        public int gearStart, gearCount;     // into gearRatios: forward gears
        public float reverseRatio, finalDrive, efficiency;
        public float idleOmega, revLimitOmega, engineInertia, fric0, fricPerOmega, idleKp, idleKi, idleFeedForward;
        public float shiftUpOmega, shiftUpLightOmega, shiftDownOmega, shiftDownLightOmega, shiftTime, shiftHold, shiftTorqueFactor;
        public float converterK, converterTR0, converterSRc, converterOverrun; // impeller torque at stall = K omega^2
        public float lockupSpeed, lockupTime, clutchCap;
        public int lockupMinGear;
        public float turbineInertia, outputInertia, shaftK, shaftC;
        public float diffPreload, diffBiasDrive, diffBiasCoast, diffK, diffC; // bias as (B - 1) / (B + 1)
        public int diffLeft, diffRight;      // wheel indices of the LSD pair (-1: none)
        public int engineGroup;              // break group of the engine mounts (-1: none)
        public float rollingRadius;
        // assists
        public float absSlip, absSlipLow, absKp, absKi, absFilter, absMinSpeed;  // D-047
        public float tcSlip, tcSlipLow, tcFloorSpeed, tcKp, tcKi, tcFilter, tcMinFactor;
        public float slipBlendLow, slipBlendHigh;
        // aero (global mode): F = -dragK |v| v through the centre of mass, lift liftK v^2 at each axle's body mounts
        public float dragK, liftKFront, liftKRear;
        public int liftOnMounts;             // 1: every wheel has wind-up body nodes (the lift goes to the suspension mounts)
    }

    public struct VehicleState
    {
        public float steer;        // smoothed steering input
        public float speed;        // m/s along the vehicle's forward axis
        public float3 velocity;    // m/s, mean of the reference nodes
        public float3 forward;
        public float engineRpm;
        public int gear;           // current gear: -1 R, 0 N, 1..n (engine mode); the request (simple mode)
        public float throttle, brake;
        public float driveTorqueTotal;
        // engine mode state (D-042)
        public float engineOmega;  // rad/s
        public float carrierOmega; // rad/s, differential carrier (axle side of the gearbox)
        public float shaftAngle;   // rad, half-shaft wind-up (carrier vs mean driven wheel)
        public float ratio;        // current overall ratio turbine / carrier (blends during a shift, 0 neutral)
        public float ratioFrom, ratioTo;
        public float shiftTimer, shiftHoldTimer;
        public int shiftDir;       // +1 upshift, -1 downshift in progress
        public int locked;         // 1: lock-up clutch stuck, engine merged with the turbine
        public float lockRamp;     // lock-up clutch pressure 0..1
        public int engineOn;       // 0 once the engine mounts broke
        public int revCut;         // fuel cut by the rev limiter
        public float idleI;        // idle controller integrator
        public float tcFactor;     // traction control engine torque factor
        public float tcI;          // traction control integrator
        public float tcSlipSpeed;  // m/s, filtered driven-wheel slip speed (traction control input)
        public int lsdStuck;       // 1 while the LSD clutch pack holds
        public float lsdAngle;     // rad, LSD stick spring deflection (right minus left wheel)
        // telemetry
        public float engineTorque, clutchTorque, converterSR, turbineTorque, shaftTorque, lsdTorque, slipDriven;
        public float3 aeroForce;   // N
        public double drivelineDamped; // J: half-shaft damper, LSD slip and stick damper (axle side energy ledger)
        public double aeroWork;    // J, work of the aerodynamic forces (negative: drag)
        public double driveWork;   // J, work of the gearbox output on the axle side (the engine's input to the ledger)
    }
}
