using Unity.Burst;
using Unity.Collections;
using Unity.Collections.LowLevel.Unsafe;
using Unity.Jobs;
using Unity.Mathematics;

namespace Hellcat.Sim.Vehicle
{
    /// <summary>
    /// Once per substep, before the beam forces: steering (drives the steering hydro input), wheel kinematics,
    /// powertrain (simple torque source, or engine + torque converter + automatic gearbox + limited-slip differential,
    /// D-042), brakes with ABS, rolling resistance and aerodynamics. Wheel torques are applied as pure couples:
    /// tangential forces on the rim nodes, reactions on the knuckle, differential and wind-up body nodes, written into
    /// the world's force slots (gathered by the node job in a fixed order). Aerodynamic drag is a uniform acceleration
    /// of the vehicle's nodes (bodyAccel, a force through the centre of mass); axle lift goes to the body mounts of the
    /// suspension (the wind-up body nodes).
    /// </summary>
    [BurstCompile(FloatMode = FloatMode.Strict, DisableSafetyChecks = true)]
    public struct VehicleControlJob : IJob
    {
        public float dt;
        public int substepIndex;
        public int maxSubsteps;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> pos;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> vel;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float> contactFn;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float> contactSlip;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> contactSurface;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<SurfaceMaterial> surfaces;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<VehicleStatic> vehicles;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<WheelStatic> wheels;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> rimNodes;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> knuckleNodes;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> driveNodes;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> windupNodes;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<byte> groupDone;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> treadNodes;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> refNodes;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float2> engineCurve; // (rad/s, N*m)
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float> gearRatios;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<DriverInput> inputs; // vehicle * maxSubsteps + substep
        [NativeDisableContainerSafetyRestriction] public NativeArray<VehicleState> vehicleState;
        [NativeDisableContainerSafetyRestriction] public NativeArray<WheelState> wheelState;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float> hydroInput;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> slotForce;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> bodyAccel;  // per body, m/s^2 (aero drag)

        const float RadPerRpm = 2f * math.PI / 60f;
        static float3 Up => new float3(0f, 1f, 0f);

        public void Execute()
        {
            for (int vi = 0; vi < vehicles.Length; vi++)
                StepVehicle(vi);
        }

        void StepVehicle(int vi)
        {
            VehicleStatic vs = vehicles[vi];
            VehicleState st = vehicleState[vi];
            DriverInput inp = inputs[vi * maxSubsteps + math.min(substepIndex, maxSubsteps - 1)];

            // Heading and speed from the chassis reference nodes.
            float3 vSum = float3.zero;
            for (int k = 0; k < vs.refCount; k++)
                vSum += vel[refNodes[vs.refStart + k]];
            float3 vMean = vs.refCount > 0 ? vSum / vs.refCount : float3.zero;
            float3 front = float3.zero, rear = float3.zero;
            int nf = 0, nr = 0;
            for (int w = 0; w < vs.wheelCount; w++)
            {
                WheelStatic ws = wheels[vs.wheelStart + w];
                float3 c = 0.5f * (pos[ws.axleInner] + pos[ws.axleOuter]);
                if (ws.steered != 0) { front += c; nf++; } else { rear += c; nr++; }
            }
            float3 fwd = (nf > 0 && nr > 0) ? math.normalizesafe(front / nf - rear / nr, st.forward) : st.forward;
            st.forward = fwd;
            st.velocity = vMean;
            st.speed = math.dot(vMean, fwd);

            // Steering: rate-limited, returns to centre, reduced with speed.
            float target = math.clamp(inp.steer, -1f, 1f);
            float speedAbs = math.abs(st.speed);
            float reduction = 1f;
            if (speedAbs > vs.steerReductionStart)
            {
                float t = math.saturate((speedAbs - vs.steerReductionStart) / math.max(60f - vs.steerReductionStart, 1f));
                reduction = math.lerp(1f, vs.steerReductionAt60, t);
            }
            target *= reduction;
            float rate = math.abs(target) < math.abs(st.steer) || target * st.steer < 0f ? vs.steerReturnRate : vs.steerRate;
            float maxDelta = rate * dt;
            st.steer += math.clamp(target - st.steer, -maxDelta, maxDelta);
            if (vs.steerHydro >= 0)
                hydroInput[vs.steerHydro] = st.steer;

            st.throttle = inp.throttle;
            st.brake = inp.brake;

            // Pass 1: wheel kinematics (rotation rates, hub speed along the heading, slip ratio).
            for (int w = 0; w < vs.wheelCount; w++)
            {
                int wi = vs.wheelStart + w;
                WheelStatic ws = wheels[wi];
                WheelState wst = wheelState[wi];
                float3 axis = Axis(ws);
                SetFrame(rimNodes, ws.rimStart, ws.rimCount, out _, out _, out float3 wRim);
                SetFrame(knuckleNodes, ws.knuckleStart, ws.knuckleCount, out _, out _, out float3 wKn);
                float omegaAbs = math.dot(wRim, axis);
                wst.omegaAbs = omegaAbs;
                wst.omega = omegaAbs - math.dot(wKn, axis);
                if (ws.driveCount > 0)
                {
                    SetFrame(driveNodes, ws.driveStart, ws.driveCount, out _, out _, out float3 wDr);
                    wst.omegaShaft = omegaAbs - math.dot(wDr, axis);
                }
                else
                {
                    wst.omegaShaft = wst.omega;
                }
                float3 vAxle = 0.5f * (vel[ws.axleInner] + vel[ws.axleOuter]);
                float3 heading = math.normalizesafe(math.cross(axis, Up), fwd);
                wst.vx = math.dot(vAxle, heading);
                wst.slipRatio = (omegaAbs * vs.rollingRadius - wst.vx) / math.max(math.abs(wst.vx), 1f);
                wheelState[wi] = wst;
            }

            // Powertrain: drive torque per wheel.
            if (vs.mode == PowertrainMode.Engine)
            {
                Driveline(vs, ref st, inp);
            }
            else
            {
                st.gear = inp.gear;
                float totalDrive = 0f;
                for (int w = 0; w < vs.wheelCount; w++)
                {
                    int wi = vs.wheelStart + w;
                    WheelStatic ws = wheels[wi];
                    WheelState wst = wheelState[wi];
                    float drive = 0f;
                    if (ws.driven != 0)
                    {
                        // simple mode: torque source with a shared power cap
                        float wAbs = math.max(math.abs(wst.omega), 1f);
                        float capByPower = vs.maxPower / math.max(vs.drivenCount, 1) / wAbs;
                        if (inp.gear > 0)
                            drive = inp.throttle * math.min(vs.maxWheelTorque, capByPower);
                        else if (inp.gear < 0)
                            drive = -inp.throttle * math.min(vs.reverseTorque, capByPower);
                    }
                    wst.driveTorque = drive;
                    totalDrive += drive;
                    wheelState[wi] = wst;
                }
                st.driveTorqueTotal = totalDrive;
            }

            // Aerodynamics (global mode): drag through the centre of mass as a uniform acceleration of the vehicle's
            // nodes, lift / downforce per axle on the suspension's body mounts (pass 2) or through the centre of mass.
            float vAir = math.length(vMean);
            float3 drag = -vs.dragK * vAir * vMean;
            float vf2 = st.speed * st.speed;
            float liftF = vs.liftKFront * vf2, liftR = vs.liftKRear * vf2;
            float3 accel = drag / math.max(vs.mass, 1f);
            if (vs.liftOnMounts == 0)
                accel += Up * ((liftF + liftR) / math.max(vs.mass, 1f));
            bodyAccel[vs.body] = accel;
            st.aeroForce = drag + Up * (liftF + liftR);
            st.aeroWork += (double)math.dot(st.aeroForce, vMean) * dt;
            int nFront = 0, nRear = 0;
            for (int w = 0; w < vs.wheelCount; w++)
                if (wheels[vs.wheelStart + w].front != 0) nFront++; else nRear++;

            // Body frame for the alignment element (D-049): forward from the rear to the front wind-up body sets, right
            // from the left to the right ones (the body nodes that carry the suspension).
            float3 bF = float3.zero, bR = float3.zero;
            float lenF = 0f, lenR = 0f;                 // |front - rear| and |right - left| of the set centroids
            int nSetF = 0, nSetR = 0, nSetRight = 0, nSetLeft = 0;
            float3 vFR = float3.zero, vRL = float3.zero; // velocity differences of the centroids: front - rear, right - left
            {
                float3 sf = float3.zero, sr = float3.zero, sR = float3.zero, sL = float3.zero;
                float3 uf = float3.zero, ur = float3.zero, uR = float3.zero, uL = float3.zero;
                int cf = 0, cr = 0, cR = 0, cL = 0;
                for (int w = 0; w < vs.wheelCount; w++)
                {
                    WheelStatic ws0 = wheels[vs.wheelStart + w];
                    if (ws0.windupCount == 0)
                        continue;
                    float3 cw = float3.zero, vw = float3.zero;
                    for (int k = 0; k < ws0.windupCount; k++)
                    {
                        cw += pos[windupNodes[ws0.windupStart + k]];
                        vw += vel[windupNodes[ws0.windupStart + k]];
                    }
                    cw /= ws0.windupCount;
                    vw /= ws0.windupCount;
                    if (ws0.front != 0) { sf += cw; uf += vw; cf++; } else { sr += cw; ur += vw; cr++; }
                    if (ws0.side > 0f) { sR += cw; uR += vw; cR++; } else { sL += cw; uL += vw; cL++; }
                }
                if (cf > 0 && cr > 0 && cR > 0 && cL > 0)
                {
                    bF = math.normalizesafe(sf / cf - sr / cr);
                    bR = math.normalizesafe(sR / cR - sL / cL);
                    lenF = math.length(sf / cf - sr / cr);
                    lenR = math.length(sR / cR - sL / cL);
                    nSetF = cf; nSetR = cr; nSetRight = cR; nSetLeft = cL;
                    vFR = uf / cf - ur / cr;
                    vRL = uR / cR - uL / cL;
                }
            }
            float3 bU = math.normalizesafe(math.cross(bF, bR));
            bool frameOk = math.lengthsq(bU) > 0.5f;
            if (frameOk)
                bR = math.cross(bU, bF);
            // the frame's angular velocity, conjugate to the reaction on its centroids (D-051)
            float3 wFrame = frameOk && lenF > 1e-3f && lenR > 1e-3f
                ? math.cross(bF, vFR) / lenF + bF * (math.dot(bU, vRL) / lenR) : float3.zero;

            // Pass 2: brakes (ABS), wind-up element, rolling resistance; apply the couples.
            float3 qFrame = float3.zero;                 // alignment reactions on the body frame (applied after the loop)
            for (int w = 0; w < vs.wheelCount; w++)
            {
                int wi = vs.wheelStart + w;
                WheelStatic ws = wheels[wi];
                WheelState wst = wheelState[wi];
                float3 axis = Axis(ws);

                // Rim, knuckle and wind-up body set: centroid, inverse inertia tensor, least-squares angular velocity
                // (every couple below is f_i = (J^-1 tau) x r_i: torque exactly tau, zero net force).
                SetFrame(rimNodes, ws.rimStart, ws.rimCount, out float3 c, out float3x3 jRim, out _);
                SetFrame(knuckleNodes, ws.knuckleStart, ws.knuckleCount, out float3 kc, out float3x3 jKn, out float3 wKn);
                float omegaKnuckle = math.dot(wKn, axis);
                float3 bc = float3.zero, wBd = float3.zero;
                float3x3 jBd = float3x3.identity;
                if (ws.windupCount > 0)
                    SetFrame(windupNodes, ws.windupStart, ws.windupCount, out bc, out jBd, out wBd);
                float omegaBody = math.dot(wBd, axis);
                float omega = wst.omega;

                // Tire load, slip and rolling resistance coefficient of the touched surface.
                float load = 0f, slipW = 0f, rr = 0f;
                for (int k = 0; k < ws.treadCount; k++)
                {
                    int n = treadNodes[ws.treadStart + k];
                    float fn = contactFn[n];
                    load += fn;
                    slipW += fn * contactSlip[n];
                    int sid = contactSurface[n];
                    if (sid >= 0)
                        rr += fn * surfaces[sid].rollingResistance;
                }
                wst.load = load;
                wst.slipSpeed = load > 1f ? slipW / load : 0f;
                // the surface's rolling resistance minus what the tire mesh dissipates by itself (D-043)
                float crr = load > 1f ? math.max(rr / load - ws.meshRollingResistance, 0f) : 0f;

                float drive = wst.driveTorque;

                // ABS (D-047): PI control of the brake pressure fraction on the braking slip speed v - omega R
                // (filtered), target absSlip x v. The slip speed, not the ratio: its response to the brake torque,
                // R / I_wheel, does not depend on the speed.
                if ((inp.flags & DriverInput.FlagAbs) != 0 && inp.brake > 0f && wst.vx > vs.absMinSpeed)
                {
                    float sb = wst.vx - wst.omegaAbs * vs.rollingRadius;
                    wst.absSlip += (sb - wst.absSlip) * math.saturate(dt / vs.absFilter);
                    float e = wst.absSlip - SlipTarget(vs, vs.absSlipLow, vs.absSlip, wst.vx) * wst.vx;
                    wst.absI = math.clamp(wst.absI - vs.absKi * e * dt, 0f, 1f);
                    wst.absFactor = math.clamp(wst.absI - vs.absKp * e, 0f, 1f);
                }
                else
                {
                    wst.absFactor = 1f;
                    wst.absI = 1f;
                    wst.absSlip = 0f;
                }

                // Brakes: holding spring while stuck, Coulomb torque while slipping.
                float capacity = inp.brake * ws.brakeTorque * wst.absFactor + inp.handbrake * ws.handbrakeTorque;
                float brake = 0f;
                if (capacity > 0f)
                {
                    if (wst.stuck != 0)
                    {
                        wst.stickAngle += omega * dt;
                        brake = -ws.stickK * wst.stickAngle - ws.stickC * omega;
                        if (math.abs(brake) > capacity)
                        {
                            brake = math.sign(brake) * capacity;
                            wst.stuck = 0;
                        }
                    }
                    else
                    {
                        brake = -math.sign(omega) * capacity;
                        // Stick when the friction torque could stop the rim within this step.
                        if (math.abs(omega) * ws.rimInertia <= capacity * dt * 2f)
                        {
                            wst.stuck = 1;
                            wst.stickAngle = 0f;
                            brake = -ws.stickC * omega;
                        }
                    }
                }
                else
                {
                    wst.stuck = 0;
                    wst.stickAngle = 0f;
                }

                // Wind-up element (D-036): rotational spring-damper between the knuckle and the body about the axis.
                float windupT = 0f;
                if (ws.windupCount > 0 && wst.windupBroken == 0)
                {
                    if (Torn(ws))
                        wst.windupBroken = 1;
                    else
                    {
                        float rel = omegaKnuckle - omegaBody;
                        wst.windupAngle += rel * dt;
                        if (frameOk && ws.windupRef >= 0)
                        {
                            // D-069: the integral of the two least-squares angular velocities drifted over minutes (their noise
                            // and bias random-walked into a spurious wind-up torque that steered the knuckles). It is pulled
                            // with a 1 s time constant towards the angle read from the pose - a reference knuckle node about
                            // the axle from the body frame's up, less its model value: the integral keeps the fast response
                            // (sensor and actuator on the same node sets), the pose the long-term zero. The pose angle alone
                            // fed the knuckle's own flex back into the 200 kN m/rad spring and tore it.
                            float3 hubW = 0.5f * (pos[ws.axleInner] + pos[ws.axleOuter]);
                            float3 u = pos[ws.windupRef] - hubW;
                            u -= math.dot(u, axis) * axis;
                            float3 up = bU - math.dot(bU, axis) * axis;
                            float e = math.atan2(math.dot(axis, math.cross(up, u)), math.dot(up, u)) - ws.windupPhi0 - wst.windupAngle;
                            e = math.atan2(math.sin(e), math.cos(e));
                            wst.windupAngle += e * math.min(dt / WindupAnchorTime, 1f);
                        }
                        float tS = -ws.windupK * wst.windupAngle;
                        if (math.abs(tS) > ws.windupStrength)
                            wst.windupBroken = 1;
                        else
                        {
                            float tD = -ws.windupC * rel;
                            windupT = tS + tD;
                            wst.windupDamped += (double)(-tD * rel) * dt;
                        }
                    }
                }
                wst.windupTorque = windupT;

                // Alignment element (D-049): camber and toe of the axle line relative to the body frame, spring-dampers
                // towards static + gain x travel; toe-in about -side x up, camber (top out) about -(axle x reference axis):
                // the reference axis is the steering axis of a steered knuckle (D-051: the camber is the angle between the
                // axle line and the kingpin, which steering leaves unchanged; no toe spring there, the toe is the rack's)
                // and up for the others (plain camber). It acts on
                // the axle line itself (a force pair on the two axle nodes, perpendicular to the axle: the gradient of
                // K e^2 / 2 of the angle measured on that line, so the element is conservative and the sensor and the
                // actuator are the same nodes), the body takes the opposite couple.
                float3 alignOut = float3.zero, alignIn = float3.zero, alignF = float3.zero, alignBodyT = float3.zero;
                if (frameOk && ws.windupCount > 0 && wst.windupBroken == 0 && ws.camberK + ws.camberC + ws.toeK + ws.toeC > 0f)
                {
                    float3 dAx = pos[ws.axleOuter] - pos[ws.axleInner];
                    float l2 = math.max(math.lengthsq(dAx), 1e-8f);
                    float3 aOut = dAx * math.rsqrt(l2);
                    float3 hub = 0.5f * (pos[ws.axleInner] + pos[ws.axleOuter]);
                    float travel = math.dot(hub - bc, bU) - ws.travel0;
                    float toe = math.asin(math.clamp(math.dot(aOut, bF), -1f, 1f));
                    float3 kp = ws.kingpin.x * bR + ws.kingpin.y * bU + ws.kingpin.z * bF;
                    float camber = math.acos(math.clamp(math.dot(aOut, kp), -1f, 1f)) - ws.kingpinPhi0;
                    float3 tAxis = -ws.side * bU, cAxis = -math.normalizesafe(math.cross(aOut, kp), ws.side * bF);
                    // the axle line's angular velocity (its part across the axle) relative to the body frame
                    float3 wAx = math.cross(dAx, vel[ws.axleOuter] - vel[ws.axleInner]) / l2;
                    float3 wRel = wAx - wFrame;
                    float rc = math.dot(wRel, cAxis), rt = math.dot(wRel, tAxis);
                    float eC = camber - (ws.camberStatic + ws.camberGain * travel);
                    float eT = toe - (ws.toeStatic + ws.bumpSteer * travel);
                    float tc = -ws.camberK * eC - ws.camberC * rc;
                    float tt = -ws.toeK * eT - ws.toeC * rt;
                    float3 tau = tc * cAxis + tt * tAxis;
                    float3 pair = math.cross(tau, dAx) / l2;                 // d x pair = tau (tau across the axle)
                    // the reference moves with the travel h = (hub - bc) . up: U also pushes along the travel, F_h = -dU/dh,
                    // on the axle nodes and back on the body nodes; the body couple F_h up x (hub - bc) keeps the pair
                    // torque-free (angular momentum)
                    float fh = ws.camberK * eC * ws.camberGain + ws.toeK * eT * ws.bumpSteer;
                    alignF = fh * bU;
                    alignOut = pair + 0.5f * alignF;
                    alignIn = -pair + 0.5f * alignF;
                    alignBodyT = -tau + fh * math.cross(bU, hub - bc);
                    wst.windupDamped += (double)(ws.camberC * rc * rc + ws.toeC * rt * rt) * dt;
                    wst.camber = camber;
                    wst.toe = toe;
                    wst.travel = travel;
                }

                float roll = -crr * load * ws.radius * math.tanh(omega / 0.5f);
                float total = drive + brake + roll;
                wst.brakeTorque = brake;
                wst.totalTorque = total;
                wheelState[wi] = wst;

                // Couple on the rim nodes.
                ApplyCouple(rimNodes, ws.rimStart, ws.rimCount, c, jRim, total * axis, ws.slotStart, float3.zero);
                // Reaction couples (D-036): the drive torque comes through the half-shaft from the differential, so the
                // differential nodes (body) take its reaction; the knuckle takes the brake (caliper) and rolling
                // resistance (bearing) torques. Without differential nodes the knuckle takes everything.
                float driveReact = ws.driveCount > 0 ? drive : 0f;
                ApplyCouple(knuckleNodes, ws.knuckleStart, ws.knuckleCount, kc, jKn, (-(total - driveReact) + windupT) * axis,
                    ws.slotStart + ws.rimCount, float3.zero);
                slotForce[ws.slotStart + ws.rimCount + ws.knuckleCount] = alignIn;           // axle slots: alignment element
                slotForce[ws.slotStart + ws.rimCount + ws.knuckleCount + 1] = alignOut;
                if (ws.driveCount > 0)
                {
                    SetFrame(driveNodes, ws.driveStart, ws.driveCount, out float3 dc, out float3x3 jDr, out _);
                    ApplyCouple(driveNodes, ws.driveStart, ws.driveCount, dc, jDr, -driveReact * axis,
                        ws.slotStart + ws.rimCount + ws.knuckleCount + 2, float3.zero);
                }
                if (ws.windupCount > 0)
                {
                    // aero lift of this wheel's share of the axle, spread over the suspension's body mounts
                    float lift = vs.liftOnMounts != 0 ? (ws.front != 0 ? liftF / math.max(nFront, 1) : liftR / math.max(nRear, 1)) : 0f;
                    ApplyCouple(windupNodes, ws.windupStart, ws.windupCount, bc, jBd, -windupT * axis,
                        ws.slotStart + ws.rimCount + ws.knuckleCount + 2 + ws.driveCount, Up * (lift / ws.windupCount) - alignF / ws.windupCount);
                    qFrame += alignBodyT;
                }
            }

            // Alignment reactions (D-051): the angles are measured against the frame of the wind-up body sets, so the
            // reaction torque goes to the nodes that define it - the frame's generalized force: (Q x bF) / |F| on the
            // front / rear set centroids, (Q . bF) bU / |R| on the right / left ones (torque Q, zero net force), each
            // centroid's share spread evenly over its set's nodes.
            if (frameOk && lenF > 1e-3f && lenR > 1e-3f && math.lengthsq(qFrame) > 0f)
            {
                float3 fF = math.cross(qFrame, bF) / lenF, fRl = math.dot(qFrame, bF) * bU / lenR;
                for (int w = 0; w < vs.wheelCount; w++)
                {
                    WheelStatic ws = wheels[vs.wheelStart + w];
                    if (ws.windupCount == 0)
                        continue;
                    float3 f = (ws.front != 0 ? fF / nSetF : -fF / nSetR) + (ws.side > 0f ? fRl / nSetRight : -fRl / nSetLeft);
                    f /= ws.windupCount;
                    int slot0 = ws.slotStart + ws.rimCount + ws.knuckleCount + 2 + ws.driveCount;
                    for (int k = 0; k < ws.windupCount; k++)
                        slotForce[slot0 + k] += f;
                }
            }

            vehicleState[vi] = st;
        }

        // ------------------------------------------------------------------ engine-mode driveline (D-042)

        /// <summary>
        /// Engine (torque curve, closed-throttle friction, idle controller, rev limiter), torque converter in parallel
        /// with a slip/stick lock-up clutch, automatic gearbox (ratio blended over the shift time, ignition retard on
        /// upshifts, rev-match on downshifts), axle side as one carrier inertia with a half-shaft spring to the driven
        /// wheels, and a limited-slip differential (preload plus torque bias, stick/slip clutch pack). Writes the drive
        /// torque of every driven wheel.
        /// </summary>
        void Driveline(in VehicleStatic vs, ref VehicleState st, in DriverInput inp)
        {
            // driven wheels with an intact half-shaft (a wheel torn off its links gets no drive)
            float wSum = 0f, slipMax = 0f, slipSpeedMax = float.MinValue;
            int nIntact = 0;
            for (int w = 0; w < vs.wheelCount; w++)
            {
                WheelStatic ws = wheels[vs.wheelStart + w];
                if (ws.driven == 0 || Torn(ws))
                    continue;
                WheelState wst = wheelState[vs.wheelStart + w];
                wSum += wst.omegaShaft;
                nIntact++;
                // slip ratio for traction control, with a 3 m/s floor (standing start: 0.36 m/s of slip at the target)
                slipMax = math.max(slipMax, (wst.omegaAbs * vs.rollingRadius - wst.vx) / math.max(math.abs(wst.vx), 3f));
                slipSpeedMax = math.max(slipSpeedMax, wst.omegaAbs * vs.rollingRadius - wst.vx);
            }
            float omegaM = nIntact > 0 ? wSum / nIntact : st.carrierOmega;
            st.slipDriven = slipMax;
            if (st.engineOn != 0 && vs.engineGroup >= 0 && groupDone[vs.engineGroup] != 0)
                st.engineOn = 0;
            bool engineOn = st.engineOn != 0;

            Gearbox(vs, ref st, inp, omegaM);
            float g = Ratio(vs, ref st, out float gDot);
            if (!engineOn)
            {
                // the engine off its mounts tears the propshaft: the axle side runs free
                g = 0f;
                gDot = 0f;
            }

            // Engine torque: full-throttle net curve, closed-throttle friction and pumping, idle controller,
            // rev limiter (fuel cut), traction control and the upshift ignition retard (on the pedal part only).
            float we = st.engineOmega;
            float tWot = Curve(vs, we);
            float tFric = vs.fric0 + vs.fricPerOmega * math.max(we, 0f);
            float err = (vs.idleOmega - we) / vs.idleOmega;
            st.idleI = math.clamp(st.idleI + vs.idleKi * err * dt, -0.2f, 0.4f);
            float thrIdle = math.clamp(vs.idleFeedForward + vs.idleKp * err + st.idleI, 0f, 0.7f);
            // traction control (D-047): PI control of the torque factor on the driven wheels' slip speed (the larger,
            // filtered); the error is relative to the target tcSlip x max(|v|, floor)
            if ((inp.flags & DriverInput.FlagTc) != 0 && nIntact > 0)
            {
                st.tcSlipSpeed += (slipSpeedMax - st.tcSlipSpeed) * math.saturate(dt / vs.tcFilter);
                float target = SlipTarget(vs, vs.tcSlipLow, vs.tcSlip, math.abs(st.speed)) * math.max(math.abs(st.speed), vs.tcFloorSpeed);
                float e = (st.tcSlipSpeed - target) / target;
                st.tcI = math.clamp(st.tcI - vs.tcKi * e * dt, vs.tcMinFactor, 1f);
                st.tcFactor = math.clamp(st.tcI - vs.tcKp * e, vs.tcMinFactor, 1f);
            }
            else
            {
                st.tcFactor = 1f;
                st.tcI = 1f;
                st.tcSlipSpeed = 0f;
            }
            float reduce = st.tcFactor * (st.shiftTimer > 0f && st.shiftDir > 0 ? vs.shiftTorqueFactor : 1f);
            float thr = math.max(math.saturate(inp.throttle) * reduce, thrIdle);
            if (we > vs.revLimitOmega)
                st.revCut = 1;
            else if (we < vs.revLimitOmega - 100f * RadPerRpm)
                st.revCut = 0;
            if (st.revCut != 0 || !engineOn)
                thr = 0f;
            float te = thr * (tWot + tFric) - tFric;
            // rev-match on a downshift: the engine supplies its own speed-up (instead of the wheels)
            if (st.shiftTimer > 0f && st.shiftDir < 0 && engineOn && st.revCut == 0)
                te = math.min(math.max(te, te + vs.engineInertia * gDot * st.carrierOmega), tWot);
            if (we <= 0f)
                te = math.max(te, 0f);

            // Torque converter (impeller torque tp on the engine, turbine torque tt into the gearbox) and the lock-up
            // clutch (capacity ramped with its pressure; stuck: the engine and the turbine are one body).
            float wt = g * st.carrierOmega;
            float tp = 0f, tt = 0f;
            if (g != 0f)
                Converter(vs, we, wt, out tp, out tt);
            // the lock-up clutch does not start to close during a shift (its inertia phase would load the clutch with the
            // engine's speed drop; a closed clutch stays closed through upshifts in the higher gears)
            bool lockCmd = g != 0f && engineOn && st.gear >= vs.lockupMinGear && math.abs(st.speed) > vs.lockupSpeed &&
                           (st.locked != 0 || st.lockRamp > 0f || st.shiftTimer <= 0f);
            st.lockRamp = lockCmd ? math.min(st.lockRamp + dt / math.max(vs.lockupTime, dt), 1f) : 0f;
            float cap = vs.clutchCap * st.lockRamp;
            if (!lockCmd)
                st.locked = 0;
            float relShaft = st.carrierOmega - omegaM;
            float ts = vs.shaftK * st.shaftAngle + vs.shaftC * relShaft;   // carrier -> driven wheels
            float iOut = vs.outputInertia;
            float tcl = 0f, wcNew = st.carrierOmega, weNew = we;
            float tCarrier = 0f;   // gearbox output torque on the carrier (energy ledger)
            float gEnd = g + gDot * dt;
            if (st.locked != 0)
            {
                // omega_e = G omega_c: (I_out + eta (I_t + I_e) G^2) a_c = G eta (T_e - (I_t + I_e) G' omega_c) - T_s
                float iIn = vs.turbineInertia + vs.engineInertia;
                float tin = te - iIn * gDot * st.carrierOmega;
                float eta = tin * wt >= 0f ? vs.efficiency : 1f / vs.efficiency;
                float ac = (g * eta * tin - ts) / (iOut + eta * iIn * g * g);
                tcl = te - vs.engineInertia * (g * ac + gDot * st.carrierOmega);
                if (math.abs(tcl) <= cap)
                {
                    tCarrier = g * eta * tin;
                    wcNew = st.carrierOmega + ac * dt;
                    weNew = gEnd * wcNew;
                }
                else
                {
                    st.locked = 0;   // the clutch slips: integrate the two sides separately below
                }
            }
            if (st.locked == 0)
            {
                float slip = we - wt;
                tcl = cap > 0f ? cap * math.sign(slip) : 0f;
                float ae = (te - tp - tcl) / vs.engineInertia;
                float tin = tt + tcl - vs.turbineInertia * gDot * st.carrierOmega;
                float eta = tin * wt >= 0f ? vs.efficiency : 1f / vs.efficiency;
                float ac = (g * eta * tin - ts) / (iOut + eta * vs.turbineInertia * g * g);
                tCarrier = g * eta * tin;
                weNew = we + ae * dt;
                wcNew = st.carrierOmega + ac * dt;
                float slipNew = weNew - gEnd * wcNew;
                if (cap > 0f && slip * slipNew <= 0f)
                {
                    // the clutch catches: one body from here, angular momentum at the carrier conserved
                    float iC = iOut + vs.turbineInertia * gEnd * gEnd;
                    float iTot = iC + vs.engineInertia * gEnd * gEnd;
                    wcNew = (iC * wcNew + vs.engineInertia * gEnd * weNew) / iTot;
                    weNew = gEnd * wcNew;
                    st.locked = 1;
                }
            }
            st.engineOmega = math.max(weNew, 0f);
            st.driveWork += (double)tCarrier * 0.5 * (st.carrierOmega + wcNew) * dt;
            st.carrierOmega = wcNew;
            st.shaftAngle += (wcNew - omegaM) * dt;
            st.drivelineDamped += (double)(vs.shaftC * relShaft * relShaft) * dt;

            // Limited-slip differential between the two driven wheels: open split plus a clutch-pack torque moved from
            // the faster to the slower wheel, up to preload + bias |T|; holds (stick spring) once the slip stops.
            float tl = 0f;
            if (vs.diffLeft >= 0 && nIntact == 2)
            {
                WheelState wl = wheelState[vs.diffLeft], wr = wheelState[vs.diffRight];
                float dw = wr.omegaShaft - wl.omegaShaft;
                float capLsd = vs.diffPreload + (ts >= 0f ? vs.diffBiasDrive : vs.diffBiasCoast) * math.abs(ts);
                if (st.lsdStuck != 0)
                {
                    st.lsdAngle += dw * dt;
                    tl = vs.diffK * st.lsdAngle + vs.diffC * dw;
                    st.drivelineDamped += (double)(vs.diffC * dw * dw) * dt;
                    if (math.abs(tl) > capLsd)
                    {
                        tl = math.sign(tl) * capLsd;
                        st.lsdStuck = 0;
                    }
                }
                else
                {
                    tl = math.sign(dw) * capLsd;
                    st.drivelineDamped += (double)(capLsd * math.abs(dw)) * dt;
                    float iL = wheels[vs.diffLeft].rimInertia, iR = wheels[vs.diffRight].rimInertia;
                    if (math.abs(dw) <= capLsd * (1f / iL + 1f / iR) * dt * 2f)
                    {
                        st.lsdStuck = 1;
                        st.lsdAngle = 0f;
                        tl = vs.diffC * dw;
                    }
                }
            }
            else
            {
                st.lsdStuck = 0;
                st.lsdAngle = 0f;
            }

            for (int w = 0; w < vs.wheelCount; w++)
            {
                int wi = vs.wheelStart + w;
                WheelStatic ws = wheels[wi];
                WheelState wst = wheelState[wi];
                float drive = 0f;
                if (ws.driven != 0 && !Torn(ws) && nIntact > 0)
                {
                    if (vs.diffLeft >= 0 && nIntact == 2)
                        drive = wi == vs.diffLeft ? 0.5f * ts + tl : 0.5f * ts - tl;
                    else
                        drive = ts / nIntact;
                }
                wst.driveTorque = drive;
                wheelState[wi] = wst;
            }

            st.engineRpm = st.engineOmega / RadPerRpm;
            st.engineTorque = te;
            st.clutchTorque = tcl;
            st.turbineTorque = tt;
            st.converterSR = we > 1f ? wt / we : 0f;
            st.shaftTorque = ts;
            st.lsdTorque = tl;
            st.driveTorqueTotal = ts;
        }

        /// <summary>Automatic and manual gear selection; starts a shift when the gear changes.</summary>
        void Gearbox(in VehicleStatic vs, ref VehicleState st, in DriverInput inp, float omegaWheel)
        {
            if (st.shiftTimer > 0f)
                st.shiftTimer = math.max(st.shiftTimer - dt, 0f);
            if (st.shiftHoldTimer > 0f)
                st.shiftHoldTimer = math.max(st.shiftHoldTimer - dt, 0f);
            if (st.shiftTimer <= 0f)
                st.shiftDir = 0;
            int cur = st.gear, n = vs.gearCount, req = inp.gear;
            float wheel = math.max(omegaWheel, 0f);
            int next = cur;
            if (req == 0)
            {
                next = 0;
            }
            else if (req < 0)
            {
                next = st.speed < 1.5f ? -1 : cur;               // no reverse while rolling forward
            }
            else if (cur <= 0)
            {
                next = st.speed > -1.5f ? GearForSpeed(vs, wheel, inp.throttle) : cur;   // into drive: the gear for the speed
            }
            else if (req >= DriverInput.Drive)
            {
                if (st.shiftTimer <= 0f)
                {
                    float thr = math.saturate(inp.throttle);
                    float up = math.lerp(vs.shiftUpLightOmega, vs.shiftUpOmega, thr);
                    float down = math.lerp(vs.shiftDownLightOmega, vs.shiftDownOmega, thr);
                    float weCur = wheel * Gear(vs, cur);
                    if (cur < n && weCur > up && st.shiftHoldTimer <= 0f)
                    {
                        next = cur + 1;
                    }
                    else if (cur > 1 && weCur < down)
                    {
                        // kick-down / coast-down: the highest lower gear that turns the engine above the downshift speed,
                        // but not above 92 % of the upshift speed (no immediate upshift)
                        next = 1;
                        for (int gi = cur - 1; gi >= 1; gi--)
                            if (wheel * Gear(vs, gi) >= down)
                            {
                                next = gi;
                                break;
                            }
                        while (next < cur && wheel * Gear(vs, next) > 0.92f * up)
                            next++;
                    }
                }
            }
            else
            {
                // manual: hold the requested gear; refuse a downshift that would over-rev
                next = math.clamp(req, 1, n);
                if (next < cur && wheel * Gear(vs, next) > vs.revLimitOmega - 200f * RadPerRpm)
                    next = cur;
            }
            if (next != st.gear)
            {
                float gNow = st.ratio;
                float gTo = next == 0 ? 0f : next > 0 ? Gear(vs, next) : -vs.reverseRatio * vs.finalDrive;
                bool blend = st.gear > 0 && next > 0 && vs.shiftTime > 0f;
                st.shiftDir = next > st.gear ? 1 : -1;
                st.ratioFrom = gNow;
                st.ratioTo = gTo;
                st.shiftTimer = blend ? vs.shiftTime : 0f;
                if (!blend)
                    st.ratio = gTo;
                st.shiftHoldTimer = vs.shiftHold;
                st.gear = next;
            }
        }

        /// <summary>Gear for driving off or for a speed: the highest gear that keeps the engine above the light-throttle
        /// upshift speed (first gear from a standstill).</summary>
        int GearForSpeed(in VehicleStatic vs, float wheel, float throttle)
        {
            float up = math.lerp(vs.shiftUpLightOmega, vs.shiftUpOmega, math.saturate(throttle));
            int g = 1;
            while (g < vs.gearCount && wheel * Gear(vs, g) > up)
                g++;
            return g;
        }

        /// <summary>Overall ratio of a forward gear (gearbox times final drive).</summary>
        float Gear(in VehicleStatic vs, int gear) => gearRatios[vs.gearStart + math.clamp(gear, 1, vs.gearCount) - 1] * vs.finalDrive;

        /// <summary>Current overall ratio (turbine / carrier) and its rate: smoothstep blend during a shift.</summary>
        float Ratio(in VehicleStatic vs, ref VehicleState st, out float gDot)
        {
            if (st.shiftTimer > 0f && vs.shiftTime > 0f)
            {
                float u = 1f - st.shiftTimer / vs.shiftTime;
                st.ratio = math.lerp(st.ratioFrom, st.ratioTo, u * u * (3f - 2f * u));
                gDot = (st.ratioTo - st.ratioFrom) * 6f * u * (1f - u) / vs.shiftTime;
            }
            else
            {
                st.ratio = st.gear == 0 ? 0f : st.gear > 0 ? Gear(vs, st.gear) : -vs.reverseRatio * vs.finalDrive;
                gDot = 0f;
            }
            return st.ratio;
        }

        /// <summary>
        /// Torque converter: impeller torque K omega_e^2 (1 - SR^4) with SR = omega_t / omega_e (K from the stall speed),
        /// torque multiplication falling linearly from TR0 at stall to 1 at the coupling point; in overrun (the turbine
        /// faster) the fluid drives the impeller with a reduced capacity and no multiplication.
        /// </summary>
        /// <summary>Slip-ratio target of an assist at a speed: low below slipBlendLow, high above slipBlendHigh, linear
        /// between (the tire's peak slip ratio falls with the speed, rig X14 / X15).</summary>
        static float SlipTarget(in VehicleStatic vs, float low, float high, float speed) =>
            math.lerp(low, high, math.saturate((speed - vs.slipBlendLow) / (vs.slipBlendHigh - vs.slipBlendLow)));

        static void Converter(in VehicleStatic vs, float we, float wt, out float tp, out float tt)
        {
            if (we >= wt)
            {
                float sr = we > 1e-3f ? math.clamp(wt / we, 0f, 1f) : 0f;   // turbine turning backwards: as at stall
                float sr2 = sr * sr;
                tp = vs.converterK * we * we * (1f - sr2 * sr2);
                float tr = sr < vs.converterSRc ? vs.converterTR0 - (vs.converterTR0 - 1f) * sr / vs.converterSRc : 1f;
                tt = tr * tp;
            }
            else
            {
                float sr = wt > 1e-3f ? math.clamp(we / wt, 0f, 1f) : 0f;
                float sr2 = sr * sr;
                tp = -vs.converterOverrun * vs.converterK * wt * wt * (1f - sr2 * sr2);
                tt = tp;
            }
        }

        /// <summary>Full-throttle net engine torque at an engine speed (linear in the table, falling to 0 at 0 rad/s).</summary>
        float Curve(in VehicleStatic vs, float we)
        {
            int s = vs.curveStart, n = vs.curveCount;
            if (n == 0)
                return 0f;
            float2 first = engineCurve[s];
            if (we <= first.x)
                return first.y * math.saturate(we / math.max(first.x, 1f));
            for (int k = 1; k < n; k++)
            {
                float2 b = engineCurve[s + k];
                if (we <= b.x)
                {
                    float2 a = engineCurve[s + k - 1];
                    return math.lerp(a.y, b.y, (we - a.x) / math.max(b.x - a.x, 1e-3f));
                }
            }
            return engineCurve[s + n - 1].y;
        }

        bool Torn(in WheelStatic ws) => ws.wheelGroup >= 0 && groupDone[ws.wheelGroup] != 0;

        /// <summary>s: time constant pulling the integrated wind-up angle towards the angle read from the pose (D-069).</summary>
        const float WindupAnchorTime = 1f;

        float3 Axis(in WheelStatic ws) => ws.axisSign * math.normalizesafe(pos[ws.axleOuter] - pos[ws.axleInner], new float3(1f, 0f, 0f));

        /// <summary>Centroid, inverse unweighted inertia tensor and least-squares angular velocity of a node set.</summary>
        void SetFrame(NativeArray<int> list, int start, int count, out float3 c, out float3x3 jInv, out float3 omega)
        {
            c = float3.zero;
            float3 vm = float3.zero;
            for (int k = 0; k < count; k++)
            {
                int n = list[start + k];
                c += pos[n];
                vm += vel[n];
            }
            float inv = 1f / math.max(count, 1);
            c *= inv;
            vm *= inv;
            float xx = 0f, yy = 0f, zz = 0f, xy = 0f, xz = 0f, yz = 0f;
            float3 l = float3.zero;
            for (int k = 0; k < count; k++)
            {
                int n = list[start + k];
                float3 r = pos[n] - c;
                xx += r.y * r.y + r.z * r.z;
                yy += r.x * r.x + r.z * r.z;
                zz += r.x * r.x + r.y * r.y;
                xy -= r.x * r.y;
                xz -= r.x * r.z;
                yz -= r.y * r.z;
                l += math.cross(r, vel[n] - vm);
            }
            float reg = 1e-6f * (xx + yy + zz) + 1e-12f;
            var j = new float3x3(xx + reg, xy, xz, xy, yy + reg, yz, xz, yz, zz + reg);
            jInv = count > 0 ? math.inverse(j) : float3x3.identity;
            omega = count > 0 ? math.mul(jInv, l) : float3.zero;
        }

        /// <summary>Pure couple tau on a node set, f_i = (J^-1 tau) x r_i (zero net force, torque exactly tau), plus an
        /// optional equal force on every node.</summary>
        void ApplyCouple(NativeArray<int> list, int start, int count, float3 c, float3x3 jInv, float3 tau, int slot0, float3 perNode)
        {
            float3 alpha = math.mul(jInv, tau);
            for (int k = 0; k < count; k++)
                slotForce[slot0 + k] = math.cross(alpha, pos[list[start + k]] - c) + perNode;
        }
    }
}
