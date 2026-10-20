"""One-off (P3b, D-051): the alignment element's body reaction goes to the nodes that define the body frame. The camber /
toe angles are measured against the frame of the four wind-up body sets (forward from the rear to the front set
centroids, right from the left to the right ones), so the reaction torque Q is applied as the frame's generalized force:
a force pair (Q x bF) / |F| on the front / rear centroids and (Q . bF) bU / |R| on the right / left ones, spread evenly
over the set nodes. Then the work of the reaction equals the energy change through the frame's rotation (first order)
and the element is conservative also while the body deforms; on the wheel's own set (D-049) a deforming body left a
6 % energy drift in E1 with the front element added."""
from pathlib import Path

P = Path("Unity/HellcatSandbox/Assets/Sim/Vehicle/VehicleControlJob.cs")
s = P.read_text(encoding="utf-8")


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:120]
    s = s.replace(old, new)


rep('''            float3 bF = float3.zero, bR = float3.zero;
            {
                float3 sf = float3.zero, sr = float3.zero, sR = float3.zero, sL = float3.zero;
                int cf = 0, cr = 0, cR = 0, cL = 0;''',
    '''            float3 bF = float3.zero, bR = float3.zero;
            float lenF = 0f, lenR = 0f;                 // |front - rear| and |right - left| of the set centroids
            int nSetF = 0, nSetR = 0, nSetRight = 0, nSetLeft = 0;
            {
                float3 sf = float3.zero, sr = float3.zero, sR = float3.zero, sL = float3.zero;
                int cf = 0, cr = 0, cR = 0, cL = 0;''')
rep('''                if (cf > 0 && cr > 0 && cR > 0 && cL > 0)
                {
                    bF = math.normalizesafe(sf / cf - sr / cr);
                    bR = math.normalizesafe(sR / cR - sL / cL);
                }''',
    '''                if (cf > 0 && cr > 0 && cR > 0 && cL > 0)
                {
                    bF = math.normalizesafe(sf / cf - sr / cr);
                    bR = math.normalizesafe(sR / cR - sL / cL);
                    lenF = math.length(sf / cf - sr / cr);
                    lenR = math.length(sR / cR - sL / cL);
                    nSetF = cf; nSetR = cr; nSetRight = cR; nSetLeft = cL;
                }''')
rep('''            // Pass 2: brakes (ABS), wind-up element, rolling resistance; apply the couples.
            for (int w = 0; w < vs.wheelCount; w++)
            {''',
    '''            // Pass 2: brakes (ABS), wind-up element, rolling resistance; apply the couples.
            float3 qFrame = float3.zero;                 // alignment reactions on the body frame (applied after the loop)
            for (int w = 0; w < vs.wheelCount; w++)
            {''')
rep('''                    ApplyCouple(windupNodes, ws.windupStart, ws.windupCount, bc, jBd, -windupT * axis + alignBodyT,
                        ws.slotStart + ws.rimCount + ws.knuckleCount + 2 + ws.driveCount, Up * (lift / ws.windupCount) - alignF / ws.windupCount);
                }
            }
''',
    '''                    ApplyCouple(windupNodes, ws.windupStart, ws.windupCount, bc, jBd, -windupT * axis,
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
''')
P.write_text(s, encoding="utf-8")
print("patched")
