"""One-off (P3b): the alignment element (D-049) acts on the axle line itself - a force pair on the two axle nodes
perpendicular to the axle (the exact gradient of K e^2 / 2 of the angle measured on that line) plus the travel force;
the damping on the axle line's own angular velocity. The body takes the opposite couple and force. Tire contact normal
alpha back to the default 0.35."""
from pathlib import Path

ROOT = Path("Unity/HellcatSandbox/Assets/Sim")


def patch(path, pairs):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:120])
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")


patch("Vehicle/VehicleControlJob.cs", [(
    """                // Alignment element (D-049): camber and toe of the axle line relative to the body frame, spring-dampers
                // towards static + gain x travel. Toe-in about -side x up, camber (top out) about -side x forward.
                float3 alignT = float3.zero, alignF = float3.zero, alignBodyT = float3.zero;
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
                    float eC = camber - (ws.camberStatic + ws.camberGain * travel);
                    float eT = toe - (ws.toeStatic + ws.bumpSteer * travel);
                    float tc = -ws.camberK * eC - ws.camberC * rc;
                    float tt = -ws.toeK * eT - ws.toeC * rt;
                    alignT = tc * cAxis + tt * tAxis;
                    // conservative: the reference moves with the travel h = (hub - bc) . up, so U = K e^2 / 2 also pushes
                    // along the travel, F_h = -dU/dh, on the axle nodes and back on the body nodes; the body couple
                    // F_h up x (hub - bc) makes the pair torque-free (angular momentum kept)
                    float fh = ws.camberK * eC * ws.camberGain + ws.toeK * eT * ws.bumpSteer;
                    alignF = fh * bU;
                    alignBodyT = fh * math.cross(bU, hub - bc);
                    wst.windupDamped += (double)(ws.camberC * rc * rc + ws.toeC * rt * rt) * dt;
                    wst.camber = camber;
                    wst.toe = toe;
                    wst.travel = travel;
                }""",
    """                // Alignment element (D-049): camber and toe of the axle line relative to the body frame, spring-dampers
                // towards static + gain x travel; toe-in about -side x up, camber (top out) about -side x forward. It acts on
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
                    float camber = -math.asin(math.clamp(math.dot(aOut, bU), -1f, 1f));
                    float3 tAxis = -ws.side * bU, cAxis = -ws.side * bF;
                    // the axle line's angular velocity (its part across the axle) relative to the body
                    float3 wAx = math.cross(dAx, vel[ws.axleOuter] - vel[ws.axleInner]) / l2;
                    float3 wRel = wAx - wBd;
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
                }"""), (
    """                ApplyCouple(knuckleNodes, ws.knuckleStart, ws.knuckleCount, kc, jKn, (-(total - driveReact) + windupT) * axis + alignT,
                    ws.slotStart + ws.rimCount, float3.zero);""",
    """                ApplyCouple(knuckleNodes, ws.knuckleStart, ws.knuckleCount, kc, jKn, (-(total - driveReact) + windupT) * axis,
                    ws.slotStart + ws.rimCount, float3.zero);"""), (
    """                slotForce[ws.slotStart + ws.rimCount + ws.knuckleCount] = 0.5f * alignF;     // axle slots: alignment travel force
                slotForce[ws.slotStart + ws.rimCount + ws.knuckleCount + 1] = 0.5f * alignF;""",
    """                slotForce[ws.slotStart + ws.rimCount + ws.knuckleCount] = alignIn;           // axle slots: alignment element
                slotForce[ws.slotStart + ws.rimCount + ws.knuckleCount + 1] = alignOut;"""), (
    """                    ApplyCouple(windupNodes, ws.windupStart, ws.windupCount, bc, jBd, -windupT * axis - alignT + alignBodyT,""",
    """                    ApplyCouple(windupNodes, ws.windupStart, ws.windupCount, bc, jBd, -windupT * axis + alignBodyT,""")])
print("patched control job")
