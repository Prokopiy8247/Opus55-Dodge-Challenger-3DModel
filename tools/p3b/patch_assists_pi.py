"""One-off (P3b): ABS and traction control as PI controllers on the slip speed (D-047), replacing the bang-bang
release / apply and cut / recover logic."""
from pathlib import Path

ROOT = Path("Unity/HellcatSandbox/Assets/Sim")


def patch(path, pairs):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:100])
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")


patch("Data/SimParamsDef.cs", [(
    """        public float absSlipRelease = 0.15f; // |slip ratio| above which ABS releases brake pressure
        public float absSlipApply = 0.07f;   // and below which it builds pressure again
        public float absReleaseRate = 12f;   // 1/s, brake pressure fraction
        public float absApplyRate = 5f;      // 1/s
        public float absMinSpeed = 2.5f;     // m/s, ABS off below
        public float tcSlip = 0.12f;         // driven-wheel slip ratio target
        public float tcCutRate = 10f;        // 1/s, engine torque factor
        public float tcRecoverRate = 3f;     // 1/s""",
    """        // ABS (D-047): per wheel, PI control of the brake pressure fraction on the braking slip speed v - omega R
        // (filtered), target absSlip x v
        public float absSlip = 0.12f;        // target braking slip ratio
        public float absKp = 0.3f;           // pressure fraction per m/s of slip speed over the target
        public float absKi = 10f;            // pressure fraction per m/s per s
        public float absFilter = 0.004f;     // s, first-order filter of the slip speed
        public float absMinSpeed = 2.5f;     // m/s, ABS off below
        // traction control (D-047): PI control of an engine torque factor on the driven wheels' slip speed (the larger,
        // filtered), target tcSlip x max(|v|, tcFloorSpeed); the error is relative to the target
        public float tcSlip = 0.12f;         // target driven-wheel slip ratio
        public float tcFloorSpeed = 3f;      // m/s: the slip-speed target does not fall below tcSlip x this
        public float tcKp = 1f;              // torque factor per unit relative error
        public float tcKi = 8f;              // torque factor per unit relative error per s
        public float tcFilter = 0.01f;       // s
        public float tcMinFactor = 0.05f;""")])

patch("Vehicle/VehicleTypes.cs", [(
    """        public float absFactor;    // ABS brake pressure fraction (1: full)
        public int absRelease;     // 1 while ABS releases""",
    """        public float absFactor;    // ABS brake pressure fraction (1: full)
        public float absI;         // ABS integrator (pressure fraction)
        public float absSlip;      // m/s, filtered braking slip speed v - omega R (ABS input)"""), (
    """        public float absRelease, absApply, absReleaseRate, absApplyRate, absMinSpeed, tcSlip, tcCutRate, tcRecoverRate;""",
    """        public float absSlip, absKp, absKi, absFilter, absMinSpeed;              // D-047
        public float tcSlip, tcFloorSpeed, tcKp, tcKi, tcFilter, tcMinFactor;"""), (
    """        public float tcFactor;     // traction control engine torque factor""",
    """        public float tcFactor;     // traction control engine torque factor
        public float tcI;          // traction control integrator
        public float tcSlipSpeed;  // m/s, filtered driven-wheel slip speed (traction control input)""")])

patch("Core/SoftBodyWorld.cs", [(
    """                absRelease = asst.absSlipRelease,
                absApply = asst.absSlipApply,
                absReleaseRate = asst.absReleaseRate,
                absApplyRate = asst.absApplyRate,
                absMinSpeed = asst.absMinSpeed,
                tcSlip = asst.tcSlip,
                tcCutRate = asst.tcCutRate,
                tcRecoverRate = asst.tcRecoverRate,""",
    """                absSlip = math.max(asst.absSlip, 0.01f),
                absKp = math.max(asst.absKp, 0f),
                absKi = math.max(asst.absKi, 0f),
                absFilter = math.max(asst.absFilter, 1e-4f),
                absMinSpeed = asst.absMinSpeed,
                tcSlip = math.max(asst.tcSlip, 0.01f),
                tcFloorSpeed = math.max(asst.tcFloorSpeed, 0.5f),
                tcKp = math.max(asst.tcKp, 0f),
                tcKi = math.max(asst.tcKi, 0f),
                tcFilter = math.max(asst.tcFilter, 1e-4f),
                tcMinFactor = math.saturate(asst.tcMinFactor),"""), (
    """                wheelState[w] = new WheelState { absFactor = 1f };""",
    """                wheelState[w] = new WheelState { absFactor = 1f, absI = 1f };"""), (
    """                st.tcFactor = 1f;
                st.engineOn = 1;""",
    """                st.tcFactor = 1f;
                st.tcI = 1f;
                st.engineOn = 1;""")])

patch("Vehicle/VehicleControlJob.cs", [(
    """                // ABS: brake pressure modulation on the slip ratio (release above absRelease, build below absApply).
                if ((inp.flags & DriverInput.FlagAbs) != 0 && inp.brake > 0f && wst.vx > vs.absMinSpeed)
                {
                    float k = -wst.slipRatio;
                    if (k > vs.absRelease)
                        wst.absRelease = 1;
                    else if (k < vs.absApply)
                        wst.absRelease = 0;
                    wst.absFactor = math.clamp(wst.absFactor + (wst.absRelease != 0 ? -vs.absReleaseRate : vs.absApplyRate) * dt, 0f, 1f);
                }
                else
                {
                    wst.absFactor = 1f;
                    wst.absRelease = 0;
                }""",
    """                // ABS (D-047): PI control of the brake pressure fraction on the braking slip speed v - omega R
                // (filtered), target absSlip x v. The slip speed, not the ratio: its response to the brake torque,
                // R / I_wheel, does not depend on the speed.
                if ((inp.flags & DriverInput.FlagAbs) != 0 && inp.brake > 0f && wst.vx > vs.absMinSpeed)
                {
                    float sb = wst.vx - wst.omegaAbs * vs.rollingRadius;
                    wst.absSlip += (sb - wst.absSlip) * math.saturate(dt / vs.absFilter);
                    float e = wst.absSlip - vs.absSlip * wst.vx;
                    wst.absI = math.clamp(wst.absI - vs.absKi * e * dt, 0f, 1f);
                    wst.absFactor = math.clamp(wst.absI - vs.absKp * e, 0f, 1f);
                }
                else
                {
                    wst.absFactor = 1f;
                    wst.absI = 1f;
                    wst.absSlip = 0f;
                }"""), (
    """            float wSum = 0f, slipMax = 0f;""",
    """            float wSum = 0f, slipMax = 0f, slipSpeedMax = float.MinValue;"""), (
    """                slipMax = math.max(slipMax, (wst.omegaAbs * vs.rollingRadius - wst.vx) / math.max(math.abs(wst.vx), 3f));""",
    """                slipMax = math.max(slipMax, (wst.omegaAbs * vs.rollingRadius - wst.vx) / math.max(math.abs(wst.vx), 3f));
                slipSpeedMax = math.max(slipSpeedMax, wst.omegaAbs * vs.rollingRadius - wst.vx);"""), (
    """            if ((inp.flags & DriverInput.FlagTc) != 0)
            {
                if (slipMax > vs.tcSlip)
                    st.tcFactor = math.max(st.tcFactor - vs.tcCutRate * dt, 0.05f);
                else if (slipMax < 0.6f * vs.tcSlip)
                    st.tcFactor = math.min(st.tcFactor + vs.tcRecoverRate * dt, 1f);
            }
            else
            {
                st.tcFactor = 1f;
            }""",
    """            // traction control (D-047): PI control of the torque factor on the driven wheels' slip speed (the larger,
            // filtered); the error is relative to the target tcSlip x max(|v|, floor)
            if ((inp.flags & DriverInput.FlagTc) != 0 && nIntact > 0)
            {
                st.tcSlipSpeed += (slipSpeedMax - st.tcSlipSpeed) * math.saturate(dt / vs.tcFilter);
                float target = vs.tcSlip * math.max(math.abs(st.speed), vs.tcFloorSpeed);
                float e = (st.tcSlipSpeed - target) / target;
                st.tcI = math.clamp(st.tcI - vs.tcKi * e * dt, vs.tcMinFactor, 1f);
                st.tcFactor = math.clamp(st.tcI - vs.tcKp * e, vs.tcMinFactor, 1f);
            }
            else
            {
                st.tcFactor = 1f;
                st.tcI = 1f;
                st.tcSlipSpeed = 0f;
            }""")])
print("patched")
