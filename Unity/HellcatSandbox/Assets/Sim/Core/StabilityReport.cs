using System;
using System.Collections.Generic;
using System.Text;
using Unity.Mathematics;

namespace Hellcat.Sim
{
    /// <summary>
    /// Load-time stability check (decisions D-004, D-024):
    ///   hard limit: S = lambda_max(M^-1 (dt^2 K + 2 dt C + D_contact)) &lt; 2.5, the exact spectral measure of the
    ///     assembled system (symplectic Euler is stable for S &lt; 4), by Lanczos iteration. K holds the beams
    ///     (axial k, limit springs), the torsion bars and panel hinges (k_t g g^T, D-032) and the geometric stiffness of pre-tensioned
    ///     tire cords (T / L transverse); "S beams" leaves out torsion and cords, which is what
    ///     tools/skeleton/stability.py computes.
    ///   warnings: per-node block-Gershgorin bound S_i &gt;= 2 and the brief's omega*dt &gt;= 0.5,
    ///     omega = sqrt(sum k / m).
    /// </summary>
    public sealed class StabilityReport
    {
        public const float WarnOmegaDt = 0.5f;
        public const float WarnGershgorin = 2f;
        public const float HardLimitS = 2.5f;

        public int nodes;
        public float exactS, exactSBeams;          // lambda_max with and without torsion bars / cord geometric stiffness
        public int lanczosIterations;
        public double seconds;
        public float maxGershgorin, maxOmegaDt;
        public int gershgorinWarnings, omegaWarnings;
        public readonly List<(int node, float s, float omegaDt)> worst = new List<(int, float, float)>();
        public float[] perNodeS;
        public float[] perNodeOmegaDt;

        public bool Passed => exactS < HardLimitS && float.IsFinite(exactS);
        // kept for older callers
        public float maxS => exactS;
        public int errorCount => Passed ? 0 : 1;
        public int warnCount => omegaWarnings;

        public static StabilityReport Compute(SoftBodyWorld w, bool exact = true)
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            int n = w.NodeCount;
            var sumK = new double[n];
            var termK = new double[n];
            var termC = new double[n];
            for (int j = 0; j < w.BeamCount; j++)
            {
                var b = w.beams[j];
                BeamKC(b, out float k, out float c);
                Accumulate(w, b.a, b.b, k, c, sumK, termK, termC);
                Accumulate(w, b.b, b.a, k, c, sumK, termK, termC);
            }

            var r = new StabilityReport { nodes = n, perNodeS = new float[n], perNodeOmegaDt = new float[n] };
            float dt = w.dt;
            var order = new List<int>();
            for (int i = 0; i < n; i++)
            {
                float im = w.invMass[i];
                if (im <= 0f)
                    continue;
                double s = dt * dt * termK[i] + 2.0 * dt * termC[i] + ContactCoefficient(w, i);
                float omegaDt = (float)(math.sqrt(sumK[i] * im) * dt);
                r.perNodeS[i] = (float)s;
                r.perNodeOmegaDt[i] = omegaDt;
                r.maxGershgorin = math.max(r.maxGershgorin, (float)s);
                r.maxOmegaDt = math.max(r.maxOmegaDt, omegaDt);
                if (s >= WarnGershgorin)
                    r.gershgorinWarnings++;
                if (omegaDt >= WarnOmegaDt)
                    r.omegaWarnings++;
                order.Add(i);
            }
            order.Sort((a, b) => r.perNodeS[b].CompareTo(r.perNodeS[a]));
            for (int k = 0; k < math.min(12, order.Count); k++)
                r.worst.Add((order[k], r.perNodeS[order[k]], r.perNodeOmegaDt[order[k]]));

            if (exact)
            {
                r.exactSBeams = (float)Spectral(w, false, out _);
                r.exactS = (float)Spectral(w, true, out r.lanczosIterations);
            }
            else
            {
                r.exactS = r.exactSBeams = r.maxGershgorin; // upper bound
            }
            r.seconds = sw.Elapsed.TotalSeconds;
            return r;
        }

        static void BeamKC(in BeamStatic b, out float k, out float c)
        {
            k = math.max(b.k, b.type == BeamType.Anisotropic ? b.kExp : 0f) + (b.type == BeamType.Bounded ? b.kLimit : 0f);
            c = math.max(math.max(b.c, b.cReb), math.max(b.cFast, b.cRebFast));
            if (b.type == BeamType.Anisotropic)
                c = math.max(c, b.cExp);
            if (b.type == BeamType.Bounded)
                c += math.max(b.cLimit, b.cLimitReb);
        }

        static float ContactCoefficient(SoftBodyWorld w, int i)
        {
            if ((w.nodeFlags[i] & NodeFlag.StaticCollision) == 0)
                return 0f;
            var cm = w.cmats[w.nodeCmat[i]];
            return math.max(cm.alphaNormal + 4f * cm.zetaNormal * math.sqrt(cm.alphaNormal),
                            cm.alphaTangent + 4f * cm.zetaTangent * math.sqrt(cm.alphaTangent));
        }

        /// <summary>lambda_max of M^-1/2 (dt^2 K + 2 dt C + D) M^-1/2 by Lanczos.</summary>
        static double Spectral(SoftBodyWorld w, bool extras, out int iterations)
        {
            int n = w.NodeCount;
            double dt = w.dt;
            var sInv = new double[n];
            var dc = new double[n];
            for (int i = 0; i < n; i++)
            {
                float im = w.invMass[i];
                sInv[i] = im > 0f ? Math.Sqrt(im) : 0.0;
                dc[i] = im > 0f ? ContactCoefficient(w, i) / im : 0.0; // contact term c_i * m_i
            }
            // deformation damping groups (D-033): at most 2 dt rate m_i (the rigid part of the group is not damped)
            for (int gi = 0; gi < w.DampGroupCount; gi++)
            {
                var dg = w.dampGroups[gi];
                for (int k = dg.nodeStart; k < dg.nodeStart + dg.nodeCount; k++)
                {
                    int i = w.dampGroupNodes[k];
                    float im = w.invMass[i];
                    if (im > 0f)
                        dc[i] += 2.0 * dt * (dg.rate + (dg.refGroup >= 0 ? dg.relRate : 0f)) / im;
                }
            }
            int nb = w.BeamCount;
            var ba = new int[nb];
            var bb = new int[nb];
            var bn = new double3[nb];
            var wAx = new double[nb];
            var wGeo = new double[nb];
            for (int j = 0; j < nb; j++)
            {
                var b = w.beams[j];
                ba[j] = b.a;
                bb[j] = b.b;
                double3 d = w.pos[b.b] - w.pos[b.a];
                double len = math.length(d);
                bn[j] = len > 1e-9 ? d / len : new double3(1, 0, 0);
                BeamKC(b, out float k, out float c);
                wAx[j] = w.broken[j] != 0 ? 0.0 : dt * dt * k + 2.0 * dt * c;
                // geometric stiffness of tensioned beams: tire cord pre-tension (D-028) and the hoop tension of a
                // spinning wheel's rings (D-044, state dependent: zero at rest)
                double t = (b.pressureGroup >= 0 ? b.pretension * w.pressureScale[b.pressureGroup] : 0.0) + w.SpinTension(j);
                wGeo[j] = extras && w.broken[j] == 0 && t > 0.0 && len > 1e-6 ? dt * dt * t / len : 0.0;
            }
            // dihedral elements: the torsion bars (with extras) and the panel hinges (always: they are panel stiffness)
            int ntb = extras ? w.TorsionBarCount : 0;
            int nt = ntb + w.HingeCount;
            var tg = new double3[nt * 4];
            var tn = new int[nt * 4];
            var tw = new double[nt];
            for (int t = 0; t < nt; t++)
            {
                int4 q4;
                float k, c;
                bool off;
                if (t < ntb)
                {
                    var tb = w.torsionBars[t];
                    q4 = new int4(tb.n1, tb.n2, tb.n3, tb.n4);
                    k = tb.k;
                    c = tb.c;
                    off = w.torsionBroken[t] != 0;
                }
                else
                {
                    var hb = w.hinges[t - ntb];
                    q4 = new int4(hb.n1, hb.n2, hb.n3, hb.n4);
                    k = hb.k;
                    c = hb.c;
                    off = w.hingeBroken[t - ntb] != 0;
                }
                tn[4 * t] = q4.x;
                tn[4 * t + 1] = q4.y;
                tn[4 * t + 2] = q4.z;
                tn[4 * t + 3] = q4.w;
                if (!off && TorsionKernel.Gradient(w.pos[q4.x], w.pos[q4.y], w.pos[q4.z], w.pos[q4.w], out _,
                        out float3 g1, out float3 g2, out float3 g3, out float3 g4))
                {
                    tg[4 * t] = g1;
                    tg[4 * t + 1] = g2;
                    tg[4 * t + 2] = g3;
                    tg[4 * t + 3] = g4;
                    tw[t] = dt * dt * k + 2.0 * dt * c;
                }
            }
            // vehicle couplings (D-036): brake holding springs and wind-up elements as rank-one terms
            var cpl = extras ? w.VehicleCouplings() : new List<(int[] nodes, double3[] grads, double weight)>();
            var z = new double3[n];
            var y = new double3[n];
            void Apply(double[] x, double[] outv)
            {
                for (int i = 0; i < n; i++)
                {
                    z[i] = new double3(x[3 * i], x[3 * i + 1], x[3 * i + 2]) * sInv[i];
                    y[i] = dc[i] * z[i];
                }
                for (int j = 0; j < nb; j++)
                {
                    double3 d = z[ba[j]] - z[bb[j]];
                    double3 e = bn[j];
                    double3 f = wAx[j] * math.dot(e, d) * e;
                    if (wGeo[j] != 0.0)
                        f += wGeo[j] * (d - math.dot(e, d) * e);
                    y[ba[j]] += f;
                    y[bb[j]] -= f;
                }
                for (int t = 0; t < nt; t++)
                {
                    if (tw[t] == 0.0)
                        continue;
                    double proj = 0.0;
                    for (int q = 0; q < 4; q++)
                        proj += math.dot(tg[4 * t + q], z[tn[4 * t + q]]);
                    for (int q = 0; q < 4; q++)
                        y[tn[4 * t + q]] += tw[t] * proj * tg[4 * t + q];
                }
                foreach (var (cn, cg, cw) in cpl)
                {
                    if (cw == 0.0)
                        continue;
                    double proj = 0.0;
                    for (int q = 0; q < cn.Length; q++)
                        proj += math.dot(cg[q], z[cn[q]]);
                    for (int q = 0; q < cn.Length; q++)
                        y[cn[q]] += cw * proj * cg[q];
                }
                for (int i = 0; i < n; i++)
                {
                    double3 v = y[i] * sInv[i];
                    outv[3 * i] = v.x;
                    outv[3 * i + 1] = v.y;
                    outv[3 * i + 2] = v.z;
                }
            }
            return LinearAlgebra.LargestEigenvalue(3 * n, Apply, 400, 2e-5, out iterations);
        }

        static void Accumulate(SoftBodyWorld w, int i, int j, float k, float c, double[] sumK, double[] termK, double[] termC)
        {
            float imi = w.invMass[i];
            if (imi <= 0f)
                return;
            float imj = w.invMass[j];
            double self = imi;
            double cross = imj > 0f ? math.sqrt(imi * imj) : 0.0;
            sumK[i] += k;
            termK[i] += k * (self + cross);
            termC[i] += c * (self + cross);
        }

        public string Summary(Func<int, string> nodeName)
        {
            var sb = new StringBuilder();
            sb.Append($"stability: nodes={nodes} exact S={exactS:F3} (beams only {exactSBeams:F3}; limit {HardLimitS}, ");
            sb.Append($"{lanczosIterations} Lanczos iterations, {seconds:F2} s) {(Passed ? "PASS" : "FAIL")}; ");
            sb.Append($"warnings: Gershgorin max {maxGershgorin:F3} ({gershgorinWarnings} nodes >= {WarnGershgorin}), ");
            sb.Append($"omega*dt max {maxOmegaDt:F3} ({omegaWarnings} nodes >= {WarnOmegaDt})");
            foreach (var (node, s, od) in worst)
                sb.Append($"\n  {nodeName(node)}: Gershgorin S={s:F3} omega*dt={od:F3}");
            return sb.ToString();
        }
    }
}
