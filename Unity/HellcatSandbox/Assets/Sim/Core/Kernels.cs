using System.Runtime.CompilerServices;
using Unity.Collections;
using Unity.Mathematics;

namespace Hellcat.Sim
{
    /// <summary>
    /// Per-beam force law shared by the single- and multi-threaded step jobs.
    /// Sign convention: positive scalar force = tension (pulls the nodes together);
    /// the returned vector is the force on node a, node b receives the negative.
    /// </summary>
    public static class BeamKernel
    {
        /// <param name="pretension">tension (N) added to the elastic force: tire cords balancing the cavity
        /// pressure (already scaled by the group's inflation, D-028)</param>
        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        /// <param name="stiffScale">spring scale (inflation-dependent carcass stiffness of tire beams, D-045; 1 otherwise)</param>
        /// <param name="relaxStep">fraction of the elastic deformation relaxed per step while an armed beam unloads (D-056)</param>
        /// <param name="armed">1 once the beam has flowed plastically, until it has unloaded (D-056)</param>
        public static float3 Compute(in BeamStatic s, float3 pa, float3 pb, float3 va, float3 vb,
            float hydroInput, float spawnBlend, float pretension, float stiffScale, float relaxStep, ref float rest, ref float yield,
            ref byte armed, ref byte broken, ref float plasticWork, ref float breakEnergy, out float stress, out byte triggered,
            out float dampPower)
        {
            triggered = 0;
            stress = 0f;
            dampPower = 0f;
            if (broken != 0)
                return float3.zero;

            float3 d = pb - pa;
            float len = math.length(d);
            if (len < 1e-6f)
                return float3.zero;
            float3 n = d / len;
            float vrel = math.dot(vb - va, n); // > 0: lengthening

            // Rest length: hydro beams follow their input; others blend in precompression at spawn.
            float l0;
            bool hydro = s.type == BeamType.Hydro;
            if (hydro)
                l0 = s.spawnRest * math.clamp(1f + s.hydroFactor * hydroInput, s.hydroMinRatio, s.hydroMaxRatio);
            else
                l0 = s.rampBase + (rest - s.rampBase) * spawnBlend;

            float x = len - l0;
            bool extended = x > 0f;
            float kE = ((s.type == BeamType.Anisotropic && extended) ? s.kExp : s.k) * stiffScale;
            bool slack = s.type == BeamType.Support && extended;

            // Elastic force, then plasticity (1-D return mapping with linear hardening).
            float fs = slack ? 0f : kE * x + pretension;
            if ((s.flags & BeamFlag.Deformable) != 0 && !hydro && !slack && spawnBlend >= 1f)
            {
                float excess = math.abs(fs) - yield;
                if (excess > 0f)
                {
                    float sgn = math.sign(fs);
                    float flow = excess / (kE + s.hardening);
                    float newRest = math.clamp(rest + sgn * flow, s.minRest, s.maxRest);
                    float applied = math.abs(newRest - rest);
                    float newYield = math.min(yield + s.hardening * applied, s.yieldCap);
                    plasticWork += 0.5f * (yield + newYield) * applied;
                    yield = newYield;
                    rest = newRest;
                    x = len - rest;
                    fs = kE * x + pretension;
                    if (relaxStep > 0f)
                        armed = 1;
                }
                else if (armed != 0)
                {
                    // Spring-back suppression (D-056): while a beam that has flowed unloads (|x| falling), its elastic
                    // deformation relaxes into a plastic one, so the crushed member does not hand its F^2 / 2k back. The
                    // relaxation only ever lowers |x| (a Maxwell element, unconditionally stable); disarmed once unloaded.
                    if (x * vrel < 0f)
                    {
                        float newRest = math.clamp(rest + relaxStep * x, s.minRest, s.maxRest);
                        float x1 = len - newRest;
                        plasticWork += 0.5f * kE * (x * x - x1 * x1);
                        rest = newRest;
                        x = x1;
                        fs = kE * x + pretension;
                    }
                    if (math.abs(fs) < 0.05f * yield)
                        armed = 0;
                }
            }

            // Bounds: SUPPORT auto-breaks when over-extended; BOUNDED adds a progressive limit spring.
            float limC = 0f;
            if (s.type == BeamType.Support)
            {
                if (s.longLen > 0f && len > s.longLen)
                {
                    broken = 1;
                    triggered = (byte)((s.flags & BeamFlag.GroupPassive) == 0 ? 1 : 0);
                    return float3.zero;
                }
            }
            else if (s.type == BeamType.Bounded)
            {
                if (len < s.shortLen)
                {
                    float e = s.shortLen - len;
                    float w = math.saturate(e / s.boundZone);
                    fs -= w * s.kLimit * e;
                    limC = w * (vrel > 0f ? s.cLimitReb : s.cLimit);
                }
                else if (len > s.longLen)
                {
                    float e = len - s.longLen;
                    float w = math.saturate(e / s.boundZone);
                    fs += w * s.kLimit * e;
                    limC = w * (vrel > 0f ? s.cLimitReb : s.cLimit);
                }
            }

            // Breaking uses the elastic force (damping spikes in contacts do not break beams).
            if ((s.flags & BeamFlag.Breakable) != 0 && math.abs(fs) > s.strength)
            {
                broken = 1;
                breakEnergy = 0.5f * kE * x * x;
                triggered = (byte)((s.flags & BeamFlag.GroupPassive) == 0 ? 1 : 0);
                return float3.zero;
            }

            // Damping: compression/extension and slow/fast branches (continuous at the split).
            float fd = 0f;
            if (!slack)
            {
                bool lengthening = vrel > 0f;
                float cs, cf, vs;
                if (s.type == BeamType.Anisotropic && extended)
                {
                    cs = s.cExp; cf = s.cExp; vs = float.MaxValue;
                }
                else
                {
                    cs = lengthening ? s.cReb : s.c;
                    cf = lengthening ? s.cRebFast : s.cFast;
                    vs = lengthening ? s.vSplitReb : s.vSplit;
                }
                float sp = math.abs(vrel);
                float mag = sp <= vs ? cs * sp : cs * vs + cf * (sp - vs);
                fd = math.sign(vrel) * mag;
            }
            fd += limC * vrel;
            dampPower = fd * vrel; // >= 0: power dissipated by the damper (energy ledger)

            float reference = (s.flags & BeamFlag.Deformable) != 0 ? yield
                : (s.flags & BeamFlag.Breakable) != 0 ? s.strength : math.max(1f, s.k * 0.05f * l0);
            stress = math.abs(fs) / math.max(reference, 1e-3f);
            return (fs + fd) * n;
        }
    }

    /// <summary>
    /// Dihedral angle of four nodes and its gradient (torsion bars). phi = atan2(|b2| b1.n2, n1.n2) with
    /// b1 = x2 - x1, b2 = x3 - x2, b3 = x4 - x3, n1 = b1 x b2, n2 = b2 x b3 (Blondel and Karplus 1996;
    /// checked against finite differences by tools/p3/proto_dihedral.py). The gradients sum to zero and
    /// carry no net torque, so forces -tau * g conserve linear and angular momentum.
    /// </summary>
    public static class TorsionKernel
    {
        public static bool Gradient(float3 x1, float3 x2, float3 x3, float3 x4, out float phi,
            out float3 g1, out float3 g2, out float3 g3, out float3 g4)
        {
            float3 b1 = x2 - x1, b2 = x3 - x2, b3 = x4 - x3;
            float3 n1 = math.cross(b1, b2), n2 = math.cross(b2, b3);
            float lb2 = math.length(b2);
            float nn1 = math.lengthsq(n1), nn2 = math.lengthsq(n2);
            if (lb2 < 1e-6f || nn1 < 1e-14f || nn2 < 1e-14f)
            {
                phi = 0f;
                g1 = g2 = g3 = g4 = float3.zero;
                return false;
            }
            phi = math.atan2(lb2 * math.dot(b1, n2), math.dot(n1, n2));
            g1 = -lb2 / nn1 * n1;
            g4 = lb2 / nn2 * n2;
            float s1 = math.dot(b1, b2) / (lb2 * lb2);
            float s3 = math.dot(b3, b2) / (lb2 * lb2);
            g2 = -(1f + s1) * g1 + s3 * g4;
            g3 = -(g1 + g2 + g4);
            return true;
        }

        /// <summary>Distances of x1 and x4 from the axis line x2-x3 and the axis length.</summary>
        public static void Levers(float3 x1, float3 x2, float3 x3, float3 x4, out float r1, out float r4, out float axis)
        {
            float3 b2 = x3 - x2;
            axis = math.length(b2);
            float3 u = axis > 1e-9f ? b2 / axis : new float3(1f, 0f, 0f);
            r1 = math.length(math.cross(x1 - x2, u));
            r4 = math.length(math.cross(x4 - x3, u));
        }

        /// <summary>Angle difference wrapped to (-pi, pi].</summary>
        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public static float Wrap(float a)
        {
            const float twoPi = 2f * math.PI;
            a -= twoPi * math.floor((a + math.PI) / twoPi);
            return a;
        }
    }

    /// <summary>Point-vs-triangle geometry for node-vs-triangle contact.</summary>
    public static class TriangleKernel
    {
        /// <summary>
        /// Signed distance of p to the plane of (a, b, c) along the unit normal cross(b - a, c - a) and the
        /// barycentric coordinates of its projection. Returns false for a degenerate triangle.
        /// </summary>
        public static bool Project(float3 p, float3 a, float3 b, float3 c, out float s, out float3 n, out float3 bary)
        {
            float3 e0 = b - a, e1 = c - a;
            float3 nn = math.cross(e0, e1);
            float len = math.length(nn);
            if (len < 1e-10f)
            {
                s = 0f;
                n = float3.zero;
                bary = float3.zero;
                return false;
            }
            n = nn / len;
            float3 ap = p - a;
            s = math.dot(ap, n);
            float3 q = ap - s * n;
            float d00 = math.dot(e0, e0), d01 = math.dot(e0, e1), d11 = math.dot(e1, e1);
            float d20 = math.dot(q, e0), d21 = math.dot(q, e1);
            float den = d00 * d11 - d01 * d01;
            float v = (d11 * d20 - d01 * d21) / den;
            float w = (d00 * d21 - d01 * d20) / den;
            bary = new float3(1f - v - w, v, w);
            return true;
        }

        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public static bool Inside(float3 bary, float tol) => bary.x >= -tol && bary.y >= -tol && bary.z >= -tol;

        /// <summary>Barycentric weights clamped to the triangle and renormalised (force distribution).</summary>
        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public static float3 Weights(float3 bary)
        {
            float3 w = math.max(bary, 0f);
            float sum = w.x + w.y + w.z;
            return sum > 1e-9f ? w / sum : new float3(1f / 3f);
        }
    }

    /// <summary>Signed distance to static primitives (negative inside) with outward normals.</summary>
    public static class StaticSdf
    {
        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        static float SignNonZero(float v) => v < 0f ? -1f : 1f;

        public static float Distance(in StaticPrimitive prim, in NativeArray<float4> planes, float3 p, out float3 normal)
        {
            switch (prim.type)
            {
                case PrimType.Plane:
                    normal = prim.axis;
                    return math.dot(prim.axis, p) - prim.halfExtents.x;

                case PrimType.Box:
                {
                    quaternion inv = math.conjugate(prim.rotation);
                    float3 q = math.rotate(inv, p - prim.center);
                    float3 d = math.abs(q) - prim.halfExtents;
                    float3 nl;
                    float dist;
                    // on the surface (largest d exactly 0) as inside: the outside branch had no direction there and fell back
                    // to "up", which turned a node lying on a wall's face out of the wall vertically (D-055)
                    if (d.x <= 0f && d.y <= 0f && d.z <= 0f)
                    {
                        if (d.x >= d.y && d.x >= d.z) { dist = d.x; nl = new float3(SignNonZero(q.x), 0f, 0f); }
                        else if (d.y >= d.z) { dist = d.y; nl = new float3(0f, SignNonZero(q.y), 0f); }
                        else { dist = d.z; nl = new float3(0f, 0f, SignNonZero(q.z)); }
                    }
                    else
                    {
                        float3 dc = math.max(d, 0f);
                        dist = math.length(dc);
                        nl = dist > 1e-9f
                            ? dc / dist * new float3(SignNonZero(q.x), SignNonZero(q.y), SignNonZero(q.z))
                            : new float3(0f, 1f, 0f);
                    }
                    normal = math.rotate(prim.rotation, nl);
                    return dist;
                }

                case PrimType.Cylinder:
                {
                    quaternion inv = math.conjugate(prim.rotation);
                    float3 q = math.rotate(inv, p - prim.center);
                    float r = math.length(q.xz);
                    float3 radial = r > 1e-9f ? new float3(q.x / r, 0f, q.z / r) : new float3(1f, 0f, 0f);
                    float3 axial = new float3(0f, SignNonZero(q.y), 0f);
                    float dr = r - prim.halfExtents.x;
                    float dy = math.abs(q.y) - prim.halfExtents.y;
                    float dist;
                    float3 nl;
                    if (dr <= 0f && dy <= 0f)
                    {
                        if (dr > dy) { dist = dr; nl = radial; }
                        else { dist = dy; nl = axial; }
                    }
                    else
                    {
                        float a = math.max(dr, 0f), b = math.max(dy, 0f);
                        dist = math.sqrt(a * a + b * b);
                        nl = math.normalizesafe(a * radial + b * axial, axial);
                    }
                    normal = math.rotate(prim.rotation, nl);
                    return dist;
                }

                default: // Convex: max over outward planes (exact on faces, conservative near edges)
                {
                    float best = float.MinValue;
                    normal = new float3(0f, 1f, 0f);
                    for (int i = 0; i < prim.planeCount; i++)
                    {
                        float4 pl = planes[prim.planeStart + i];
                        float s = math.dot(pl.xyz, p) - pl.w;
                        if (s > best) { best = s; normal = pl.xyz; }
                    }
                    return best;
                }
            }
        }
    }

    /// <summary>Static-world contact for one node: penalty zone + friction anchor (stick/slip).</summary>
    public static class ContactKernel
    {
        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public static float LoadFactor(in ContactMaterial cm, float fn)
        {
            float lf = 1f - cm.loadSensitivity * (fn / cm.loadRef - 1f);
            return math.clamp(lf, cm.minLoadFactor, 1f + cm.loadSensitivity);
        }

        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public static float SlidingMu(in ContactMaterial cm, float slip)
        {
            float t = math.pow(slip / math.max(cm.stribeckVel, 1e-4f), cm.stribeckExp);
            return cm.muSliding + (cm.muStatic - cm.muSliding) * math.exp(-t);
        }

        /// <summary>
        /// Adds the contact force of one primitive to <paramref name="force"/>. Returns the normal force.
        /// The anchor (stick point on the surface) is kept while the node stays in contact with the same primitive.
        /// </summary>
        public static float Apply(float3 p, float3 v, float m, float dt, float s, float3 n, int primIndex,
            in ContactMaterial cm, in SurfaceMaterial surf, float3 lat, ref float3 anchor, ref int anchorPrim, ref float3 force,
            out float slipSpeed)
        {
            slipSpeed = 0f;
            float pen = cm.bias - s;
            float vn = math.dot(v, n);
            float kc = cm.alphaNormal * m / (dt * dt);
            float cc = 2f * cm.zetaNormal * m * math.sqrt(cm.alphaNormal) / dt;
            float fn = math.max(0f, kc * pen - cc * vn);
            force += n * fn;

            float3 vt = v - vn * n;
            float3 surfacePoint = p - n * s;
            float kt = cm.alphaTangent * m / (dt * dt);
            float ct = 2f * cm.zetaTangent * m * math.sqrt(cm.alphaTangent) / dt;
            float3 dpt;
            if (anchorPrim == primIndex)
            {
                dpt = p - anchor;
                dpt -= math.dot(dpt, n) * n;
            }
            else
            {
                anchor = surfacePoint;
                anchorPrim = primIndex;
                dpt = float3.zero;
            }

            float lf = LoadFactor(cm, fn);
            float muStatic = surf.frictionScale * cm.muStatic * lf;
            float3 ft = -kt * dpt - ct * vt;
            // friction ellipse (D-048): the component along the lateral axis lat counts 1 / muLateral times (lat zero:
            // isotropic); the limit scales the trial force back onto the ellipse
            float ftLat = math.dot(ft, lat);
            float ftLen = math.sqrt(math.lengthsq(ft) + cm.latExtra * ftLat * ftLat);
            float limit = muStatic * fn;
            slipSpeed = math.length(vt);
            if (ftLen > limit)
            {
                float mu = surf.frictionScale * SlidingMu(cm, slipSpeed) * lf;
                ft *= math.min(mu * fn / ftLen, 1f);
                // Keep the anchor at the distance where the spring alone gives the sliding force.
                anchor = surfacePoint + ft / kt;
            }
            force += ft;
            return fn;
        }

        /// <summary>Hard non-penetration after integration: no node ends a step inside a static solid.</summary>
        public static void Project(ref float3 p, ref float3 v, float s, float3 n, float mu)
        {
            if (s >= 0f)
                return;
            p -= n * s;
            float vn = math.dot(v, n);
            if (vn < 0f)
            {
                float3 vt = v - vn * n;
                float vtLen = math.length(vt);
                float dvt = math.min(vtLen, mu * -vn);
                v = vt - (vtLen > 1e-9f ? vt / vtLen * dvt : float3.zero);
            }
        }
    }
}
