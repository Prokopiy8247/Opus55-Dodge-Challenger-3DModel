"""One-off (P3b): knuckle alignment element (D-049) - camber and toe spring-dampers of every knuckle relative to the body,
towards the kinematic alignment at the current wheel travel; an extension of the wind-up element (D-036)."""
from pathlib import Path

ROOT = Path("Unity/HellcatSandbox/Assets/Sim")


def patch(path, pairs):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:120])
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")


patch("Data/SimParamsDef.cs", [(
    """        public float strength = -1f;         // N*m elastic torque that tears it (bushings), <= 0: never
    }""",
    """        public float strength = -1f;         // N*m elastic torque that tears it (bushings), <= 0: never
        // alignment (D-049): spring-dampers on the knuckle's camber and toe relative to the body, towards the kinematic
        // alignment at the current wheel travel (static value + gain x travel): the lumped stiffness and hysteresis of
        // the links and their bushings, which the node-beam links alone cannot carry at the solver's step. Toe only on
        // unsteered wheels (the steering sets it on the others).
        public float camberStiffness = 0f;   // N*m/rad (0: off)
        public float camberDamping = 0f;     // N*m*s/rad
        public float toeStiffness = 0f;      // N*m/rad (0: off)
        public float toeDamping = 0f;        // N*m*s/rad
        public float camberStatic = 0f;      // deg at ride height, top outward positive
        public float toeStatic = 0f;         // deg at ride height, toe-in positive
        public float camberGain = 0f;        // deg per m of bump (wheel up against the body), top outward positive
        public float bumpSteer = 0f;         // deg of toe-in per m of bump
    }""")])

patch("Vehicle/VehicleTypes.cs", [(
    """        public float windupK, windupC, windupStrength; // N*m/rad, N*m*s/rad, N*m (float.MaxValue: never tears)""",
    """        public float windupK, windupC, windupStrength; // N*m/rad, N*m*s/rad, N*m (float.MaxValue: never tears)
        // alignment element (D-049): camber / toe spring-dampers towards static + gain x travel (rad, rad/m)
        public float camberK, camberC, toeK, toeC, camberStatic, toeStatic, camberGain, bumpSteer;
        public float travel0;                // m: hub height over the wind-up body nodes along the body's up at spawn
        public float side;                   // +1 right, -1 left (model x)"""), (
    """        public float windupTorque; // telemetry, N*m on the knuckle""",
    """        public float windupTorque; // telemetry, N*m on the knuckle
        public float camber, toe, travel; // telemetry (D-049): rad relative to the body (top out, toe-in positive), m of bump""")])

patch("Core/SoftBodyWorld.cs", [(
    """                    ws.windupK = math.max(wu.stiffness, 0f);
                    ws.windupC = math.max(wu.damping, 0f);
                    ws.windupStrength = wu.strength > 0f ? wu.strength : float.MaxValue;
                }""",
    """                    ws.windupK = math.max(wu.stiffness, 0f);
                    ws.windupC = math.max(wu.damping, 0f);
                    ws.windupStrength = wu.strength > 0f ? wu.strength : float.MaxValue;
                    // alignment element (D-049)
                    ws.camberK = math.max(wu.camberStiffness, 0f);
                    ws.camberC = math.max(wu.camberDamping, 0f);
                    ws.toeK = wd.steered != 0 ? 0f : math.max(wu.toeStiffness, 0f);
                    ws.toeC = wd.steered != 0 ? 0f : math.max(wu.toeDamping, 0f);
                    ws.camberStatic = math.radians(wu.camberStatic);
                    ws.toeStatic = math.radians(wu.toeStatic);
                    ws.camberGain = math.radians(wu.camberGain);
                    ws.bumpSteer = math.radians(wu.bumpSteer);
                    float3 hubM = 0.5f * (ModelPos(def, wd.axleInner) + ModelPos(def, wd.axleOuter));
                    float3 bcM = float3.zero;
                    foreach (int n in wd.windupBody)
                        bcM += ModelPos(def, n) / wd.windupBody.Length;
                    ws.travel0 = hubM.y - bcM.y;
                    ws.side = hubM.x >= 0f ? 1f : -1f;
                }"""), (
    """                float load = math.max(qr * (dt * dt * kRim + 2f * dt * cRim), qk * (dt * dt * kTot + 2f * dt * cTot));
                load = math.max(load, (dt * dt * kTot + 2f * dt * cTot) / math.max(iK, 1e-6f) / 2f);""",
    """                float load = math.max(qr * (dt * dt * kRim + 2f * dt * cRim), qk * (dt * dt * kTot + 2f * dt * cTot));
                load = math.max(load, (dt * dt * kTot + 2f * dt * cTot) / math.max(iK, 1e-6f) / 2f);
                // the alignment couples about the toe (up) and camber (forward) axes: the same budget on those axes
                float alignLoad = 0f;
                if (ws.camberK + ws.camberC + ws.toeK + ws.toeC > 0f)
                {
                    float qc = CoupleCompliance(b, knSet, Centroid(b, knSet), new float3(0f, 0f, 1f), out float iC);
                    float qt = CoupleCompliance(b, knSet, Centroid(b, knSet), new float3(0f, 1f, 0f), out float iT);
                    alignLoad = math.max(qc * (dt * dt * ws.camberK + 2f * dt * ws.camberC), qt * (dt * dt * ws.toeK + 2f * dt * ws.toeC));
                    alignLoad = math.max(alignLoad, math.max((dt * dt * ws.camberK + 2f * dt * ws.camberC) / math.max(iC, 1e-6f),
                        (dt * dt * ws.toeK + 2f * dt * ws.toeC) / math.max(iT, 1e-6f)) / 2f);
                    if (alignLoad > 1f)
                    {
                        ws.camberK /= alignLoad;
                        ws.camberC /= alignLoad;
                        ws.toeK /= alignLoad;
                        ws.toeC /= alignLoad;
                        b.couplingScale = math.min(b.couplingScale, 1f / alignLoad);
                    }
                }""")])

# model position helper next to Centroid
s = (ROOT / "Core/SoftBodyWorld.cs").read_text(encoding="utf-8")
assert s.count("float3 Centroid(") == 1, "Centroid helper"
patch("Core/SoftBodyWorld.cs", [(
    """float3 Centroid(""",
    """float3 ModelPos(VehicleDef def, int n) => new float3(def.nodes[n].p[0], def.nodes[n].p[1], def.nodes[n].p[2]);

        static float3 Centroid(""" if "static float3 Centroid(" in s else """float3 ModelPos(VehicleDef def, int n) => new float3(def.nodes[n].p[0], def.nodes[n].p[1], def.nodes[n].p[2]);

        float3 Centroid(""")])

patch("Vehicle/VehicleControlJob.cs", [(
    """            // Pass 2: brakes (ABS), wind-up element, rolling resistance; apply the couples.
            for (int w = 0; w < vs.wheelCount; w++)
            {""",
    """            // Body frame for the alignment element (D-049): forward from the rear to the front wind-up body sets, right
            // from the left to the right ones (the body nodes that carry the suspension).
            float3 bF = float3.zero, bR = float3.zero;
            {
                float3 sf = float3.zero, sr = float3.zero, sR = float3.zero, sL = float3.zero;
                int nf = 0, nr = 0, nR = 0, nL = 0;
                for (int w = 0; w < vs.wheelCount; w++)
                {
                    WheelStatic ws0 = wheels[vs.wheelStart + w];
                    if (ws0.windupCount == 0)
                        continue;
                    float3 cw = float3.zero;
                    for (int k = 0; k < ws0.windupCount; k++)
                        cw += pos[windupNodes[ws0.windupStart + k]];
                    cw /= ws0.windupCount;
                    if (ws0.front != 0) { sf += cw; nf++; } else { sr += cw; nr++; }
                    if (ws0.side > 0f) { sR += cw; nR++; } else { sL += cw; nL++; }
                }
                if (nf > 0 && nr > 0 && nR > 0 && nL > 0)
                {
                    bF = math.normalizesafe(sf / nf - sr / nr);
                    bR = math.normalizesafe(sR / nR - sL / nL);
                }
            }
            float3 bU = math.normalizesafe(math.cross(bF, bR));
            bool frameOk = math.lengthsq(bU) > 0.5f;
            if (frameOk)
                bR = math.cross(bU, bF);

            // Pass 2: brakes (ABS), wind-up element, rolling resistance; apply the couples.
            for (int w = 0; w < vs.wheelCount; w++)
            {"""), (
    """                wst.windupTorque = windupT;""",
    """                wst.windupTorque = windupT;

                // Alignment element (D-049): camber and toe of the axle line relative to the body frame, spring-dampers
                // towards static + gain x travel. Toe-in about -side x up, camber (top out) about -side x forward.
                float3 alignT = float3.zero;
                if (frameOk && ws.windupCount > 0 && wst.windupBroken == 0 && ws.camberK + ws.camberC + ws.toeK + ws.toeC > 0f)
                {
                    float3 aOut = math.normalizesafe(pos[ws.axleOuter] - pos[ws.axleInner]);
                    float3 hub = 0.5f * (pos[ws.axleInner] + pos[ws.axleOuter]);
                    float travel = math.dot(hub - bc, bU) - ws.travel0;
                    float toe = math.asin(math.clamp(math.dot(aOut, bF), -1f, 1f));
                    float camber = -math.asin(math.clamp(math.dot(aOut, bU), -1f, 1f));
                    float3 tAxis = -ws.side * bU, cAxis = -ws.side * bF;
                    float3 wRel = wKn - wBd;
                    float rc = math.dot(wRel, cAxis), rt = math.dot(wRel, tAxis);
                    float tc = -ws.camberK * (camber - (ws.camberStatic + ws.camberGain * travel)) - ws.camberC * rc;
                    float tt = -ws.toeK * (toe - (ws.toeStatic + ws.bumpSteer * travel)) - ws.toeC * rt;
                    alignT = tc * cAxis + tt * tAxis;
                    wst.windupDamped += (double)(ws.camberC * rc * rc + ws.toeC * rt * rt) * dt;
                    wst.camber = camber;
                    wst.toe = toe;
                    wst.travel = travel;
                }"""), (
    """                ApplyCouple(knuckleNodes, ws.knuckleStart, ws.knuckleCount, kc, jKn, (-(total - driveReact) + windupT) * axis,
                    ws.slotStart + ws.rimCount, float3.zero);""",
    """                ApplyCouple(knuckleNodes, ws.knuckleStart, ws.knuckleCount, kc, jKn, (-(total - driveReact) + windupT) * axis + alignT,
                    ws.slotStart + ws.rimCount, float3.zero);"""), (
    """                    ApplyCouple(windupNodes, ws.windupStart, ws.windupCount, bc, jBd, -windupT * axis,""",
    """                    ApplyCouple(windupNodes, ws.windupStart, ws.windupCount, bc, jBd, -windupT * axis - alignT,""")])
print("patched")
