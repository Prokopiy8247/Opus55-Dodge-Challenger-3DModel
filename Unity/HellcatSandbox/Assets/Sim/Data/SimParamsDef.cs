using System;
using System.IO;
using System.Text;
using UnityEngine;

namespace Hellcat.Sim.Data
{
    // Schema of sim/vehicle/<name>/params.json: all tunable values, separate from geometry.
    // Convention: a negative value means "unset" (infinite for limits, "same as" for variants).
    // Line comments (// ...) are allowed and stripped before parsing.

    [Serializable]
    public class BeamMaterialDef
    {
        public string name;
        public float spring;            // N/m
        public float damp;              // N/(m/s), while shortening
        public float dampRebound = -1;  // while lengthening (-1: = damp)
        public float dampFast = -1;     // above velSplit (-1: = damp)
        public float dampReboundFast = -1;
        public float velSplit = -1;     // m/s (-1: no split)
        public float velSplitRebound = -1;
        public float springExp = -1;    // anisotropic, while longer than rest (-1: = spring)
        public float dampExp = -1;
        public float deform = -1;       // initial deform threshold, N (-1: never deforms)
        public float hardening = 0;     // N/m of threshold increase per metre of plastic flow
        public float deformCap = -1;    // max threshold, N (-1: unlimited)
        public float strength = -1;     // break force, N (-1: unbreakable)
        public float deformLimitMin = 0; // min rest length as a fraction of spawn rest (0: none)
        public float deformLimitMax = 0; // max rest length as a fraction of spawn rest (0: none)
        public float inflationShare = 0; // tire cavity beams: share of the spring that comes from the inflation pressure
                                        // (D-045): k_eff = k (1 - share (1 - inflation)), inflation = gas content / spawn
        public float preload = 0;       // N, compression the beam carries at its spawn length (suspension springs at
                                        // ride height): rest = spawn * pre + preload / spring, so retuning the
                                        // spring rate keeps the ride height
        public float shortBound = 0;    // BOUNDED/SUPPORT: allowed compression, fraction of rest
        public float longBound = 0;     // allowed extension, fraction of rest (SUPPORT: auto-break)
        public float boundZone = 0.01f; // m
        public float limitSpring = 0;   // N/m beyond a bound
        public float limitDamp = 0;
        public float limitDampRebound = -1;
        public float hydroMinRatio = 0.5f;
        public float hydroMaxRatio = 1.5f;
        // spring-back suppression (D-056): rate (1/s) at which the elastic deformation of a beam that has flowed plastically
        // relaxes while the beam unloads (the stability-limited spring stores F^2 / 2k, 10-50x the elastic energy of a real
        // crushed member, and a crushed front gave it back as a 20 km/h rebound); 0: fully elastic unloading
        public float unloadRelax = 0;
    }

    /// <summary>
    /// Shell bending material of panel hinges (D-032). Per hinge the solver scales the plate values with the geometry of
    /// its two triangles: k = bend * |e|^2 / (A1 + A2) * HingeGeometry, c likewise, yield moment = yieldMoment * |e|.
    /// </summary>
    [Serializable]
    public class HingeMaterialDef
    {
        public string name;
        public float bend;              // N*m, plate bending stiffness D (homogenised: skin plus its stiffeners)
        public float damp;              // N*m*s, bending damping (same scaling as bend)
        public float yieldMoment = -1;  // N*m/m, bending moment per unit edge length at which the panel creases (-1: never)
        public float hardening = 0;     // N*m/m per rad of plastic rotation
        public float yieldCap = -1;     // N*m/m, max yield moment (-1: unlimited)
        public float dampCap = 0;       // rad/s: damping saturates above this bending rate (D-043), 0: viscous
    }

    /// <summary>Deformation damping group material (D-033): velocity damping rate towards the group's rigid motion.</summary>
    [Serializable]
    public class DampGroupMaterialDef
    {
        public string name;
        public float rate;              // 1/s; a mode inside the group gets the damping ratio rate / (2 omega)
        public float relRate;           // 1/s towards the reference group's rigid motion (D-038)
        public float vCap;              // m/s: RMS deformation speed above which the damping saturates (D-043), 0: none
        public bool spin;               // centripetal compensation of the group's rotation (wheels, D-044)
    }

    [Serializable]
    public class ContactMaterialDef
    {
        public string name;
        public float muStatic = 1f;
        public float muSliding = 0.8f;
        public float stribeckVel = 0.5f;
        public float stribeckExp = 1.75f;
        public float loadRef = 1000f;
        public float loadSensitivity = 0f;
        public float minLoadFactor = 0.5f;
        public float bias = 0.025f;
        public float alphaNormal = 0.35f;
        public float zetaNormal = 0.15f;
        public float alphaTangent = 0.3f;
        public float zetaTangent = 0.15f;
        // anisotropic friction (tire tread, D-048): lateral / longitudinal friction of a node whose lateral axis runs
        // along its beams of material lateralBeams (both ends: the axis through the two neighbours); 1: isotropic
        public float muLateral = 1f;
        public string lateralBeams = "";
        // hard contact (D-055): after a node is projected out of a static solid its normal contact stays inelastic (the
        // projection carries the load, no penalty spring) until it leaves the contact zone
        public bool hardContact = false;
    }

    [Serializable]
    public class SurfaceDef
    {
        public string name;
        public float frictionScale = 1f;
        public float rollingResistance = 0.012f;
    }

    [Serializable]
    public class BrakeDef
    {
        public string name;
        public float maxTorque = 2000f;      // N*m at full pedal
        public float handbrakeTorque = 0f;   // N*m (rear only)
        public float stickStiffness = 0f;    // N*m/rad holding spring when locked (0: auto from inertia)
        public float stickDamping = 0f;
    }

    /// <summary>Wind-up element of a wheel (D-036): knuckle rotation about the spin axis relative to the body.</summary>
    [Serializable]
    public class WindupDef
    {
        public string name;
        public float stiffness;              // N*m/rad
        public float damping;                // N*m*s/rad
        public float strength = -1f;         // N*m elastic torque that tears it (bushings), <= 0: never
        public bool geometricAngle = true;   // D-069: anchor the integrated angle to the pose (false: plain integral, X24)
        // alignment (D-049): spring-dampers on the knuckle's camber and toe relative to the body, towards the kinematic
        // alignment at the current wheel travel (static value + gain x travel): the lumped stiffness and hysteresis of
        // the links and their bushings, which the node-beam links alone cannot carry at the solver's step. Toe only on
        // unsteered wheels (the steering sets it on the others).
        public float camberStiffness = 0f;   // N*m/rad (0: off)
        public float camberDamping = 0f;     // N*m*s/rad
        public float toeStiffness = 0f;      // N*m/rad (0: off)
        public float toeDamping = 0f;        // N*m*s/rad
        public float steerDamping = 0f;      // N*m*s/rad: steered knuckles, damping of the toe rate relative to the body (the
                                             // steering gear's damping, D-054); they have no toe spring
        public float camberStatic = 0f;      // deg at ride height, top outward positive
        public float toeStatic = 0f;         // deg at ride height, toe-in positive
        public float camberGain = 0f;        // deg per m of bump (wheel up against the body), top outward positive
        public float bumpSteer = 0f;         // deg of toe-in per m of bump
    }

    [Serializable]
    public class PowertrainDef
    {
        public string mode = "simple";       // "simple" (P0.5) or "engine"
        // simple mode
        public float maxWheelTorque = 1500f; // N*m per driven wheel
        public float maxPower = 150000f;     // W, all driven wheels
        public float reverseTorque = 800f;
        // engine mode (P3b): engine, torque converter with lock-up clutch, automatic gearbox, limited-slip differential
        public float[] torqueRpm;            // full-throttle (net) torque curve
        public float[] torqueNm;
        public float idleRpm = 700f;
        public float revLimitRpm = 6200f;    // fuel cut (hysteresis 100 rpm)
        public float engineInertia = 0.25f;  // kg*m^2, crank, flywheel, converter impeller
        public float frictionTorque0 = 20f;  // N*m at 0 rpm: closed-throttle friction and pumping (engine braking)
        public float frictionTorquePerRpm = 0.012f;
        public float idleKp = 1.5f;          // idle speed controller: throttle per relative speed error
        public float idleKi = 4f;            // 1/s
        public float[] gearRatios;
        public float reverseRatio = 3.3f;    // magnitude
        public float finalDrive = 2.62f;
        public float efficiency = 0.92f;     // gearbox and axle, both power flow directions
        public float shiftUpRpm = 6000f;     // automatic: upshift at full throttle
        public float shiftUpLightRpm = 2000f; // upshift at closed throttle
        public float shiftDownRpm = 3500f;   // automatic: downshift (kick-down) below this at full throttle
        public float shiftDownLightRpm = 1100f; // downshift at closed throttle
        public float shiftTime = 0.15f;      // s, ratio change (inertia phase)
        public float shiftHold = 0.6f;       // s, no automatic upshift this soon after a shift
        public float shiftTorqueFactor = 0.5f; // engine torque during an upshift (ignition retard)
        public float converterStallRpm = 2400f; // full-throttle stall speed (sets the capacity factor)
        public float converterTorqueRatio = 1.9f; // torque multiplication at stall
        public float converterCouplingSR = 0.87f; // speed ratio where the multiplication ends
        public float converterOverrun = 0.6f;     // capacity when the turbine drives the impeller (coasting)
        public float converterLockupSpeed = 15f;  // m/s, lock-up clutch from this speed (gear >= lockupMinGear)
        public int lockupMinGear = 2;
        public float lockupTime = 0.3f;      // s, lock-up clutch pressure ramp
        public float clutchMaxTorque = 1400f; // N*m lock-up clutch capacity at the engine
        public float turbineInertia = 0.06f;  // kg*m^2 turbine and gearbox input (reflected through the ratio)
        public float outputInertia = 0.25f;   // kg*m^2 propshaft, differential and half-shafts at the axle
        public float driveshaftStiffness = 16000f; // N*m/rad at the axle: both half-shafts through the differential
        public float driveshaftDamping = 30f;      // N*m*s/rad
        public float diffPreload = 100f;     // N*m, limited-slip clutch preload
        public float diffBias = 2.5f;        // torque bias ratio on power
        public float diffBiasCoast = 2.5f;   // torque bias ratio off power (asymmetric LSD)
        public float diffStiffness = 50000f; // N*m/rad, the clutch pack while it holds (stick spring, like the brakes)
        public float diffDamping = 60f;      // N*m*s/rad
        public string engineGroup = "";      // break group of the engine mounts: the engine stops when it fires
        public float rollingRadius = 0.35f;  // m, effective rolling radius (slip ratio, automatic gear choice)
    }

    /// <summary>Driver assists: ABS (DriverInput.flags bit 0) and traction control (bit 1).</summary>
    [Serializable]
    public class AssistDef
    {
        // ABS (D-047): per wheel, PI control of the brake pressure fraction on the braking slip speed v - omega R
        // (filtered), target absSlip x v
        public float absSlip = 0.12f;        // target braking slip ratio at and above slipBlendHigh
        public float absSlipLow = 0.12f;     // at and below slipBlendLow (the tire's peak slip ratio falls with the speed)
        public float absKp = 0.3f;           // pressure fraction per m/s of slip speed over the target
        public float absKi = 10f;            // pressure fraction per m/s per s
        public float absFilter = 0.004f;     // s, first-order filter of the slip speed
        public float absMinSpeed = 2.5f;     // m/s, ABS off below
        // traction control (D-047): PI control of an engine torque factor on the driven wheels' slip speed (the larger,
        // filtered), target tcSlip x max(|v|, tcFloorSpeed); the error is relative to the target
        public float tcSlip = 0.12f;         // target driven-wheel slip ratio at and above slipBlendHigh
        public float tcSlipLow = 0.12f;      // at and below slipBlendLow
        public float tcFloorSpeed = 3f;      // m/s: the slip-speed target does not fall below tcSlip x this
        public float tcKp = 1f;              // torque factor per unit relative error
        public float tcKi = 8f;              // torque factor per unit relative error per s
        public float tcFilter = 0.01f;       // s
        public float tcMinFactor = 0.05f;
        public float slipBlendLow = 5f;      // m/s: the slip targets blend linearly between these speeds
        public float slipBlendHigh = 25f;
    }

    [Serializable]
    public class SteeringDef
    {
        public float rate = 3.5f;            // input units per second (keyboard)
        public float returnRate = 5f;
        public float speedReductionStart = 15f; // m/s
        public float speedReductionAt60 = 0.35f; // input scale at 60 m/s
        public float wheelLockDeg = 33f;     // road-wheel angle at full input (reported, set by geometry)
        public float steeringWheelTurnsLockToLock = 2.6f;
    }

    [Serializable]
    public class AeroDef
    {
        public string mode = "global";       // "global" (frontal-area model; per-triangle aero is not implemented)
        public float dragArea = 0.75f;       // Cd*A (m^2): drag through the centre of mass
        public float liftFront = 0f;         // Cl*A (m^2) at the front axle (positive: lift, negative: downforce)
        public float liftRear = 0f;          // Cl*A (m^2) at the rear axle
        public float airDensity = 1.225f;    // kg/m^3
    }

    /// <summary>Tire model values that are not beam, hinge, damp-group or contact materials.</summary>
    [Serializable]
    public class TireDef
    {
        // rolling resistance the tire mesh produces by itself at moderate speed (carcass hysteresis, contact, D-043):
        // the wheel couple adds only the rest of the surface's coefficient
        public float meshRollingResistance = 0f;
    }

    /// <summary>The plastic and break thresholds of one part's beams whose midpoint (model space) lies in a box, scaled:
    /// crease initiators and softened or reinforced sections tuned without regenerating the skeleton (P6). Springs and
    /// dampers are left alone (the stability criterion does not change).</summary>
    [Serializable]
    public class MaterialZoneDef
    {
        public string part;                  // both nodes of the beam in this part
        public string[] materials;           // only these beam materials (empty: all)
        public float[] min, max;             // model-space box of the beam's midpoint (m)
        public float deformScale = 1f, hardeningScale = 1f, capScale = 1f, strengthScale = 1f;
    }

    [Serializable]
    public class PressureParamsDef
    {
        public float atmosphere = 101325f;   // Pa
        public float gaugeScale = 1f;        // multiplies the geometry's gauge pressures (tuning, P6 sweep)
        public float maxAbsRatio = 4f;       // absolute pressure cap as a multiple of the spawn absolute pressure
        public float minVolumeRatio = 0.1f;  // volume floor for the pressure law (fraction of the spawn volume)
        public float leakPerBeam = 1.5f;     // 1/s leak rate per broken tire beam: d(pV)/dt = -rate * (p - p_atm) * V
        public float leakMax = 20f;          // 1/s
        public bool pretension = true;       // pre-tension the tire beams so the spawn shape balances the pressure (D-028)
    }

    [Serializable]
    public class CollisionParamsDef
    {
        public float cellSize = 0.3f;        // m, spatial hash cell for node-vs-triangle contact
        public int rebuildEvery = 4;         // substeps between hash rebuilds (margin covers the motion in between)
        public float backBias = 0.01f;       // m, contact zone behind a triangle (front zone = node material bias)
        public float alpha = 0.25f;          // penalty stiffness alpha * m_eff / dt^2
        public float zeta = 0.2f;            // penalty damping ratio
        public float frictionScale = 1f;     // x node material sliding friction
        public float footprintTolerance = 0.02f; // barycentric slack at triangle edges
    }

    [Serializable]
    public class SimParamsDef
    {
        public float dt = 0.0005f;
        public float gravity = 9.81f;
        public float spawnRamp = 0.25f;      // s, precompression blend-in
        public float maxNodeSpeed = 400f;
        public float spawnClearance = 0.01f; // m, lowest static-collision node above the ground at spawn (D-026)
        public BeamMaterialDef[] materials;
        public HingeMaterialDef[] hingeMaterials;
        public DampGroupMaterialDef[] dampGroupMaterials;
        public ContactMaterialDef[] contactMaterials;
        public SurfaceDef[] surfaces;
        public BrakeDef[] brakes;
        public WindupDef[] windup;
        public PowertrainDef powertrain;
        public AssistDef assists;
        public SteeringDef steering;
        public AeroDef aero;
        public TireDef tire;
        public PressureParamsDef pressure;
        public MaterialZoneDef[] materialZones;
        public CollisionParamsDef collision;

        public static SimParamsDef Load(string path) => Parse(File.ReadAllText(path));

        public static SimParamsDef Parse(string json)
        {
            var p = JsonUtility.FromJson<SimParamsDef>(StripComments(json));
            p.Normalize();
            return p;
        }

        /// <summary>Fills absent sections with defaults (JsonUtility leaves missing arrays null).</summary>
        public void Normalize()
        {
            materials ??= Array.Empty<BeamMaterialDef>();
            hingeMaterials ??= Array.Empty<HingeMaterialDef>();
            dampGroupMaterials ??= Array.Empty<DampGroupMaterialDef>();
            contactMaterials ??= Array.Empty<ContactMaterialDef>();
            surfaces ??= Array.Empty<SurfaceDef>();
            brakes ??= Array.Empty<BrakeDef>();
            windup ??= Array.Empty<WindupDef>();
            powertrain ??= new PowertrainDef();
            assists ??= new AssistDef();
            steering ??= new SteeringDef();
            aero ??= new AeroDef();
            tire ??= new TireDef();
            pressure ??= new PressureParamsDef();
            materialZones ??= Array.Empty<MaterialZoneDef>();
            collision ??= new CollisionParamsDef();
        }

        /// <summary>Removes // line comments outside string literals.</summary>
        public static string StripComments(string text)
        {
            var sb = new StringBuilder(text.Length);
            bool inString = false;
            for (int i = 0; i < text.Length; i++)
            {
                char ch = text[i];
                if (inString)
                {
                    sb.Append(ch);
                    if (ch == '\\' && i + 1 < text.Length)
                        sb.Append(text[++i]);
                    else if (ch == '"')
                        inString = false;
                    continue;
                }
                if (ch == '"')
                {
                    inString = true;
                    sb.Append(ch);
                }
                else if (ch == '/' && i + 1 < text.Length && text[i + 1] == '/')
                {
                    while (i < text.Length && text[i] != '\n')
                        i++;
                    sb.Append('\n');
                }
                else
                {
                    sb.Append(ch);
                }
            }
            return sb.ToString();
        }

        public int MaterialIndex(string name)
        {
            for (int i = 0; i < materials.Length; i++)
                if (materials[i].name == name)
                    return i;
            throw new InvalidDataException($"params.json: unknown beam material '{name}'");
        }

        public BeamMaterialDef Material(string name) => materials[MaterialIndex(name)];

        public DampGroupMaterialDef DampGroupMaterial(string name)
        {
            foreach (var m in dampGroupMaterials)
                if (m.name == name)
                    return m;
            throw new InvalidDataException($"params.json: unknown damp group material '{name}'");
        }

        public HingeMaterialDef HingeMaterial(string name)
        {
            foreach (var m in hingeMaterials)
                if (m.name == name)
                    return m;
            throw new InvalidDataException($"params.json: unknown hinge material '{name}'");
        }

        public int ContactMaterialIndex(string name)
        {
            for (int i = 0; i < contactMaterials.Length; i++)
                if (contactMaterials[i].name == name)
                    return i;
            throw new InvalidDataException($"params.json: unknown contact material '{name}'");
        }

        public BrakeDef Brake(string name)
        {
            foreach (var b in brakes)
                if (b.name == name)
                    return b;
            return new BrakeDef { name = name };
        }

        public WindupDef Windup(string name)
        {
            foreach (var w in windup)
                if (w.name == name)
                    return w;
            return null;
        }
    }
}
