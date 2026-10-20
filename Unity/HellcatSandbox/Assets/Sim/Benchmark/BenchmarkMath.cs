using System.Runtime.CompilerServices;
using Unity.Mathematics;

namespace Hellcat.Sim.Benchmark
{
    /// <summary>
    /// Per-beam and per-node kernels shared by the single- and multi-threaded jobs, so both
    /// variants execute exactly the same arithmetic in the same order.
    /// </summary>
    public static class BenchmarkMath
    {
        /// <summary>
        /// Scalar beam force along <paramref name="dir"/> (from node a to node b), positive = tension.
        /// coef = (spring N/m, damp N/(m/s), hardening N/m, strength N); bounds = (short, long)
        /// fractions of the rest length for BOUNDED beams. <paramref name="yieldForce"/> is the current
        /// deform threshold: plastic flow moves the rest length and raises the threshold (linear
        /// hardening), so a beam that keeps yielding eventually reaches its strength and breaks.
        /// </summary>
        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public static float BeamForce(float3 pa, float3 pb, float3 va, float3 vb, float4 coef, float2 bounds,
            byte kind, ref float restLength, ref float yieldForce, ref byte broken, out float3 dir)
        {
            float3 d = pb - pa;
            float len = math.length(d);
            dir = d / math.max(len, 1e-6f);

            float springForce = coef.x * (len - restLength);
            float excess = math.abs(springForce) - yieldForce;
            if (excess > 0f)
            {
                // Return mapping for 1D plasticity with linear hardening.
                float s = math.sign(springForce);
                float flow = excess / (coef.x + coef.z);
                restLength += s * flow;
                yieldForce += coef.z * flow;
                springForce = s * yieldForce;
            }
            float force = springForce + coef.y * math.dot(vb - va, dir);

            if (kind == BeamKind.Support)
            {
                if (len > restLength)
                    force = 0f; // acts in compression only
            }
            else if (kind == BeamKind.Bounded)
            {
                float lo = restLength * (1f - bounds.x);
                float hi = restLength * (1f + bounds.y);
                if (len < lo)
                    force += 4f * coef.x * (len - lo);
                else if (len > hi)
                    force += 4f * coef.x * (len - hi);
            }

            if (math.abs(force) > coef.w)
            {
                broken = 1;
                return 0f;
            }
            return force;
        }

        /// <summary>
        /// Adds gravity and ground/wall contact to the accumulated beam force, then integrates the
        /// node with semi-implicit (symplectic) Euler. Nodes with zero inverse mass are fixed.
        /// </summary>
        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public static void IntegrateNode(ref float3 p, ref float3 v, float3 force, float invMass, in SimParams prm)
        {
            if (invMass <= 0f)
                return;
            float mass = 1f / invMass;
            force += prm.gravity * mass;
            PlaneContact(new float3(0f, 1f, 0f), 0f, p, v, mass, prm, ref force);
            PlaneContact(new float3(-1f, 0f, 0f), -prm.wallX, p, v, mass, prm, ref force);
            v += force * (invMass * prm.dt);
            p += v * prm.dt;
        }

        /// <summary>Penalty contact against the plane dot(n, p) = d with Coulomb friction.</summary>
        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        static void PlaneContact(float3 n, float d, float3 p, float3 v, float mass, in SimParams prm, ref float3 force)
        {
            float penetration = prm.contactBias - (math.dot(n, p) - d);
            if (penetration <= 0f)
                return;
            float vn = math.dot(v, n);
            float fn = math.max(0f, prm.contactStiffness * penetration - prm.contactDamping * vn);
            force += n * fn;
            float3 vt = v - vn * n;
            float vtLen = math.length(vt);
            if (vtLen > 1e-6f)
            {
                // Capped so friction can at most stop the sliding within one step (no reversal jitter).
                float ft = math.min(prm.friction * fn, vtLen * mass / prm.dt);
                force -= vt * (ft / vtLen);
            }
        }
    }
}
