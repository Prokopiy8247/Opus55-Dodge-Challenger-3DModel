"""One-off (P3b): the alignment element (D-049) made conservative - the travel force -dU/dh on the axle nodes and the wind-up
body nodes plus the body couple that keeps the angular momentum; its elastic energy in the energy ledger."""
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
    """                float3 alignT = float3.zero;
                if (frameOk && ws.windupCount > 0 && wst.windupBroken == 0 && ws.camberK + ws.camberC + ws.toeK + ws.toeC > 0f)""",
    """                float3 alignT = float3.zero, alignF = float3.zero, alignBodyT = float3.zero;
                if (frameOk && ws.windupCount > 0 && wst.windupBroken == 0 && ws.camberK + ws.camberC + ws.toeK + ws.toeC > 0f)"""), (
    """                    float tc = -ws.camberK * (camber - (ws.camberStatic + ws.camberGain * travel)) - ws.camberC * rc;
                    float tt = -ws.toeK * (toe - (ws.toeStatic + ws.bumpSteer * travel)) - ws.toeC * rt;
                    alignT = tc * cAxis + tt * tAxis;""",
    """                    float eC = camber - (ws.camberStatic + ws.camberGain * travel);
                    float eT = toe - (ws.toeStatic + ws.bumpSteer * travel);
                    float tc = -ws.camberK * eC - ws.camberC * rc;
                    float tt = -ws.toeK * eT - ws.toeC * rt;
                    alignT = tc * cAxis + tt * tAxis;
                    // conservative: the reference moves with the travel h = (hub - bc) . up, so U = K e^2 / 2 also pushes
                    // along the travel, F_h = -dU/dh, on the axle nodes and back on the body nodes; the body couple
                    // F_h up x (hub - bc) makes the pair torque-free (angular momentum kept)
                    float fh = ws.camberK * eC * ws.camberGain + ws.toeK * eT * ws.bumpSteer;
                    alignF = fh * bU;
                    alignBodyT = fh * math.cross(bU, hub - bc);"""), (
    """                slotForce[ws.slotStart + ws.rimCount + ws.knuckleCount] = float3.zero;       // axle slots: unused
                slotForce[ws.slotStart + ws.rimCount + ws.knuckleCount + 1] = float3.zero;""",
    """                slotForce[ws.slotStart + ws.rimCount + ws.knuckleCount] = 0.5f * alignF;     // axle slots: alignment travel force
                slotForce[ws.slotStart + ws.rimCount + ws.knuckleCount + 1] = 0.5f * alignF;"""), (
    """                    ApplyCouple(windupNodes, ws.windupStart, ws.windupCount, bc, jBd, -windupT * axis - alignT,
                        ws.slotStart + ws.rimCount + ws.knuckleCount + 2 + ws.driveCount, Up * (lift / ws.windupCount));""",
    """                    ApplyCouple(windupNodes, ws.windupStart, ws.windupCount, bc, jBd, -windupT * axis - alignT + alignBodyT,
                        ws.slotStart + ws.rimCount + ws.knuckleCount + 2 + ws.driveCount, Up * (lift / ws.windupCount) - alignF / ws.windupCount);""")])

patch("Core/SoftBodyWorld.cs", [(
    """            // wind-up elements (D-036): spring energy 1/2 K theta^2, damper dissipation
            for (int k = b.wheelStart; k < b.wheelStart + b.wheelCount && b.vehicleIndex >= 0; k++)
            {
                var wst = wheelState[k];
                r.damping += wst.windupDamped;
                if (energies && wst.windupBroken == 0)
                    r.torsion += 0.5 * wheels[k].windupK * wst.windupAngle * wst.windupAngle;
            }""",
    """            // wind-up elements (D-036): spring energy 1/2 K theta^2, damper dissipation; alignment springs (D-049)
            for (int k = b.wheelStart; k < b.wheelStart + b.wheelCount && b.vehicleIndex >= 0; k++)
            {
                var wst = wheelState[k];
                r.damping += wst.windupDamped;
                if (energies && wst.windupBroken == 0)
                    r.torsion += 0.5 * wheels[k].windupK * wst.windupAngle * wst.windupAngle;
            }
            if (energies && b.vehicleIndex >= 0)
                r.torsion += AlignmentEnergy(b);"""), (
    """        /// <summary>Elastic energy of one intact beam, consistent with the force law of BeamKernel.</summary>""",
    """        /// <summary>Elastic energy of the alignment springs (D-049) at the current positions, as the control job measures them:
        /// body frame from the wind-up body sets, camber / toe of every axle line against static + gain x travel.</summary>
        double AlignmentEnergy(Body b)
        {
            float3 sf = float3.zero, sr = float3.zero, sR = float3.zero, sL = float3.zero;
            int cf = 0, cr = 0, cR = 0, cL = 0;
            for (int k = b.wheelStart; k < b.wheelStart + b.wheelCount; k++)
            {
                var ws = wheels[k];
                if (ws.windupCount == 0)
                    continue;
                float3 cw = float3.zero;
                for (int q = 0; q < ws.windupCount; q++)
                    cw += pos[windupNodes[ws.windupStart + q]];
                cw /= ws.windupCount;
                if (ws.front != 0) { sf += cw; cf++; } else { sr += cw; cr++; }
                if (ws.side > 0f) { sR += cw; cR++; } else { sL += cw; cL++; }
            }
            if (cf == 0 || cr == 0 || cR == 0 || cL == 0)
                return 0.0;
            float3 bF = math.normalizesafe(sf / cf - sr / cr), bR = math.normalizesafe(sR / cR - sL / cL);
            float3 bU = math.normalizesafe(math.cross(bF, bR));
            if (math.lengthsq(bU) < 0.5f)
                return 0.0;
            double e = 0.0;
            for (int k = b.wheelStart; k < b.wheelStart + b.wheelCount; k++)
            {
                var ws = wheels[k];
                if (ws.windupCount == 0 || wheelState[k].windupBroken != 0 || ws.camberK + ws.toeK <= 0f)
                    continue;
                float3 bc = float3.zero;
                for (int q = 0; q < ws.windupCount; q++)
                    bc += pos[windupNodes[ws.windupStart + q]];
                bc /= ws.windupCount;
                float3 aOut = math.normalizesafe(pos[ws.axleOuter] - pos[ws.axleInner]);
                float3 hub = 0.5f * (pos[ws.axleInner] + pos[ws.axleOuter]);
                float travel = math.dot(hub - bc, bU) - ws.travel0;
                float toe = math.asin(math.clamp(math.dot(aOut, bF), -1f, 1f));
                float camber = -math.asin(math.clamp(math.dot(aOut, bU), -1f, 1f));
                double eC = camber - (ws.camberStatic + ws.camberGain * travel);
                double eT = toe - (ws.toeStatic + ws.bumpSteer * travel);
                e += 0.5 * ws.camberK * eC * eC + 0.5 * ws.toeK * eT * eT;
            }
            return e;
        }

        /// <summary>Elastic energy of one intact beam, consistent with the force law of BeamKernel.</summary>""")])
print("patched")
