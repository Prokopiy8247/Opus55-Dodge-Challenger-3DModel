using System;
using System.Collections.Generic;

namespace Hellcat.Sim
{
    /// <summary>Small dense and iterative solvers used at load time (managed code, double precision).</summary>
    public static class LinearAlgebra
    {
        /// <summary>In-place Cholesky factorisation of a symmetric positive definite n x n matrix (row major); lower factor.</summary>
        public static bool Cholesky(double[] a, int n)
        {
            for (int j = 0; j < n; j++)
            {
                int rj = j * n;
                double s = a[rj + j];
                for (int k = 0; k < j; k++)
                    s -= a[rj + k] * a[rj + k];
                if (!(s > 0.0))
                    return false;
                double d = Math.Sqrt(s);
                a[rj + j] = d;
                double inv = 1.0 / d;
                for (int i = j + 1; i < n; i++)
                {
                    int ri = i * n;
                    double t = a[ri + j];
                    for (int k = 0; k < j; k++)
                        t -= a[ri + k] * a[rj + k];
                    a[ri + j] = t * inv;
                }
            }
            return true;
        }

        /// <summary>Solves L L^T x = b in place with the factor from <see cref="Cholesky"/>.</summary>
        public static void CholeskySolve(double[] l, int n, double[] b)
        {
            for (int i = 0; i < n; i++)
            {
                int ri = i * n;
                double t = b[i];
                for (int k = 0; k < i; k++)
                    t -= l[ri + k] * b[k];
                b[i] = t / l[ri + i];
            }
            for (int i = n - 1; i >= 0; i--)
            {
                double t = b[i];
                for (int k = i + 1; k < n; k++)
                    t -= l[k * n + i] * b[k];
                b[i] = t / l[i * n + i];
            }
        }

        static double Dot(double[] a, double[] b)
        {
            double s = 0.0;
            for (int i = 0; i < a.Length; i++)
                s += a[i] * b[i];
            return s;
        }

        /// <summary>
        /// Largest eigenvalue of a symmetric operator by Lanczos with full reorthogonalisation. The Ritz value
        /// approaches the eigenvalue from below; iteration stops when it changed less than relTol over the
        /// last five steps.
        /// </summary>
        public static double LargestEigenvalue(int n, Action<double[], double[]> apply, int maxIter, double relTol,
            out int iterations)
        {
            var rng = new Random(20261011);
            var basis = new List<double[]>();
            var alpha = new List<double>();
            var beta = new List<double>();
            var history = new List<double>();
            var q = new double[n];
            for (int i = 0; i < n; i++)
                q[i] = rng.NextDouble() - 0.5;
            double norm = Math.Sqrt(Dot(q, q));
            for (int i = 0; i < n; i++)
                q[i] /= norm;
            var w = new double[n];
            double theta = 0.0;
            iterations = 0;
            for (int j = 0; j < maxIter; j++)
            {
                basis.Add(q);
                apply(q, w);
                double a = Dot(q, w);
                alpha.Add(a);
                for (int pass = 0; pass < 2; pass++)
                    foreach (var b in basis)
                    {
                        double c = Dot(b, w);
                        for (int i = 0; i < n; i++)
                            w[i] -= c * b[i];
                    }
                double bn = Math.Sqrt(Dot(w, w));
                theta = TridiagonalMax(alpha, beta);
                history.Add(theta);
                iterations = j + 1;
                if (j >= 10 && Math.Abs(theta - history[j - 5]) <= relTol * Math.Abs(theta))
                    break;
                if (bn <= 1e-13 * Math.Max(Math.Abs(theta), 1e-30))
                    break;
                beta.Add(bn);
                q = new double[n];
                for (int i = 0; i < n; i++)
                    q[i] = w[i] / bn;
            }
            return theta;
        }

        /// <summary>Largest eigenvalue of the symmetric tridiagonal matrix (diagonal a, off-diagonal b) by bisection.</summary>
        public static double TridiagonalMax(List<double> a, List<double> b)
        {
            int m = a.Count;
            double lo = double.MaxValue, hi = double.MinValue;
            for (int i = 0; i < m; i++)
            {
                double r = (i > 0 ? Math.Abs(b[i - 1]) : 0.0) + (i < m - 1 ? Math.Abs(b[i]) : 0.0);
                lo = Math.Min(lo, a[i] - r);
                hi = Math.Max(hi, a[i] + r);
            }
            for (int it = 0; it < 200 && hi - lo > 1e-15 * Math.Max(1.0, Math.Abs(hi)); it++)
            {
                double x = 0.5 * (lo + hi);
                if (CountBelow(a, b, x) == m)
                    hi = x;
                else
                    lo = x;
            }
            return hi;
        }

        // Sturm count: eigenvalues below x.
        static int CountBelow(List<double> a, List<double> b, double x)
        {
            int count = 0;
            double d = 1.0;
            for (int i = 0; i < a.Count; i++)
            {
                double off = i > 0 ? b[i - 1] * b[i - 1] / d : 0.0;
                d = a[i] - x - off;
                if (d == 0.0)
                    d = -1e-300;
                if (d < 0.0)
                    count++;
            }
            return count;
        }
    }
}
