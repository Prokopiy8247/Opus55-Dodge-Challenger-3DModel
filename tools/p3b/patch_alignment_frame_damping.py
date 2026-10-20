"""One-off (P3b, D-051): the alignment element's damping uses the angular velocity of the body frame it is measured against
(the velocity conjugate to its reaction on the frame centroids: bF x (v_front - v_rear) / |F| + bF (bU . (v_right -
v_left)) / |R|), so the damper's power is -C w_rel^2 exactly; with the wheel's own set (D-049) a deforming body let it
feed the 0.2 m drop's tire modes (T6 settled in 5.8 s)."""
from pathlib import Path

P = Path("Unity/HellcatSandbox/Assets/Sim/Vehicle/VehicleControlJob.cs")
s = P.read_text(encoding="utf-8")


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:120]
    s = s.replace(old, new)


rep('''            float lenF = 0f, lenR = 0f;                 // |front - rear| and |right - left| of the set centroids
            int nSetF = 0, nSetR = 0, nSetRight = 0, nSetLeft = 0;
            {
                float3 sf = float3.zero, sr = float3.zero, sR = float3.zero, sL = float3.zero;
                int cf = 0, cr = 0, cR = 0, cL = 0;
                for (int w = 0; w < vs.wheelCount; w++)
                {
                    WheelStatic ws0 = wheels[vs.wheelStart + w];
                    if (ws0.windupCount == 0)
                        continue;
                    float3 cw = float3.zero;
                    for (int k = 0; k < ws0.windupCount; k++)
                        cw += pos[windupNodes[ws0.windupStart + k]];
                    cw /= ws0.windupCount;
                    if (ws0.front != 0) { sf += cw; cf++; } else { sr += cw; cr++; }
                    if (ws0.side > 0f) { sR += cw; cR++; } else { sL += cw; cL++; }
                }
                if (cf > 0 && cr > 0 && cR > 0 && cL > 0)
                {
                    bF = math.normalizesafe(sf / cf - sr / cr);
                    bR = math.normalizesafe(sR / cR - sL / cL);
                    lenF = math.length(sf / cf - sr / cr);
                    lenR = math.length(sR / cR - sL / cL);
                    nSetF = cf; nSetR = cr; nSetRight = cR; nSetLeft = cL;
                }
            }
            float3 bU = math.normalizesafe(math.cross(bF, bR));
            bool frameOk = math.lengthsq(bU) > 0.5f;
            if (frameOk)
                bR = math.cross(bU, bF);''',
    '''            float lenF = 0f, lenR = 0f;                 // |front - rear| and |right - left| of the set centroids
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
                ? math.cross(bF, vFR) / lenF + bF * (math.dot(bU, vRL) / lenR) : float3.zero;''')
rep('''                    // the axle line's angular velocity (its part across the axle) relative to the body
                    float3 wAx = math.cross(dAx, vel[ws.axleOuter] - vel[ws.axleInner]) / l2;
                    float3 wRel = wAx - wBd;''',
    '''                    // the axle line's angular velocity (its part across the axle) relative to the body frame
                    float3 wAx = math.cross(dAx, vel[ws.axleOuter] - vel[ws.axleInner]) / l2;
                    float3 wRel = wAx - wFrame;''')
P.write_text(s, encoding="utf-8")
print("patched")
