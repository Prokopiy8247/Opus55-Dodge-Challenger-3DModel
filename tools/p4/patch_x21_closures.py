"""One-off (P4): X21 tracks closures and skins (door apertures, latch forces, offsets from the cabin's rigid motion)."""
from pathlib import Path

p = Path("Unity/HellcatSandbox/Assets/Sim/Validation/CrashDiagnostics.cs")
s = p.read_text(encoding="utf-8")
WATCH = r'''        /// <summary>Closures and skins during a crash: per door the hinge-pillar to latch-pillar distance on the body (the
        /// door aperture), the largest latch force and when the latch broke, and per part (roof skin, doors, hood) the
        /// largest distance of a node from where the cabin's rigid motion would carry it.</summary>
        public sealed class ClosureWatch
        {
            readonly SoftBodyWorld w;
            readonly SoftBodyWorld.Body b;
            readonly int[] cabin;
            readonly double3[] cab0, rest;
            readonly double3 c0;
            readonly List<(string name, int[] nodes)> parts = new List<(string, int[])>();
            readonly List<(string door, int[] hingeBody, int[] latchBody, double len0, List<int> latchBeams)> doors =
                new List<(string, int[], int[], double, List<int>)>();
            public readonly Dictionary<string, double> maxOffset = new Dictionary<string, double>();
            public readonly Dictionary<string, double> maxApertureChange = new Dictionary<string, double>();
            public readonly Dictionary<string, double> maxLatchForce = new Dictionary<string, double>();
            public readonly Dictionary<string, double> latchBreak = new Dictionary<string, double>();

            public ClosureWatch(SoftBodyWorld world, int bi, int[] cabinNodes)
            {
                w = world;
                b = world.bodies[bi];
                cabin = cabinNodes;
                var d = b.def;
                rest = new double3[b.nodeCount];
                for (int i = 0; i < b.nodeCount; i++) rest[i] = (double3)w.pos[b.nodeStart + i];
                cab0 = new double3[cabin.Length];
                for (int k = 0; k < cabin.Length; k++) { cab0[k] = rest[cabin[k]]; c0 += cab0[k]; }
                c0 /= cabin.Length;
                if (d.dampGroups != null)
                    foreach (var g in d.dampGroups)
                        if (g.name == "roof") parts.Add(("roof skin", g.nodes));
                foreach (var part in new[] { "door_FL", "door_FR", "hood" })
                {
                    var l = new List<int>();
                    for (int i = 0; i < d.nodes.Length; i++) if (d.nodes[i].part == part) l.Add(i);
                    parts.Add((part, l.ToArray()));
                }
                foreach (var door in new[] { "door_FL", "door_FR" })
                {
                    var hinge = new List<int>();
                    var latch = new List<int>();
                    var beams = new List<int>();
                    for (int k = 0; k < b.beamCount; k++)
                    {
                        var bd = d.beams[k];
                        bool aIn = d.nodes[bd.a].part == door, bIn = d.nodes[bd.b].part == door;
                        if (aIn == bIn) continue;
                        int body = aIn ? bd.b : bd.a;
                        if (bd.mat == "hinge") hinge.Add(body);
                        if (bd.mat == "latch") { latch.Add(body); beams.Add(b.beamStart + k); }
                    }
                    if (hinge.Count == 0 || latch.Count == 0) continue;
                    doors.Add((door, hinge.ToArray(), latch.ToArray(), math.distance(Mean(hinge.ToArray()), Mean(latch.ToArray())), beams));
                }
            }

            double3 Mean(int[] ids)
            {
                double3 s = 0;
                foreach (int i in ids) s += (double3)w.pos[b.nodeStart + i];
                return s / ids.Length;
            }

            /// <summary>Rotation of the cabin since the start: polar factor of the cross-covariance (Higham iteration).</summary>
            double3x3 CabinRotation(out double3 c)
            {
                c = 0;
                for (int k = 0; k < cabin.Length; k++) c += (double3)w.pos[b.nodeStart + cabin[k]];
                c /= cabin.Length;
                double3x3 a = double3x3.zero;
                for (int k = 0; k < cabin.Length; k++)
                {
                    double3 p = (double3)w.pos[b.nodeStart + cabin[k]] - c, q = cab0[k] - c0;
                    a += new double3x3(p.x * q, p.y * q, p.z * q);
                }
                double3x3 r = a;
                for (int it = 0; it < 30; it++)
                    r = 0.5 * (r + math.transpose(math.inverse(r)));
                return r;
            }

            public void Sample(double t)
            {
                var r = CabinRotation(out double3 c);
                foreach (var (name, nodes) in parts)
                {
                    double m = 0;
                    foreach (int i in nodes)
                    {
                        double3 rigid = c + math.mul(r, rest[i] - c0);
                        m = math.max(m, math.distance((double3)w.pos[b.nodeStart + i], rigid));
                    }
                    maxOffset.TryGetValue(name, out double old);
                    maxOffset[name] = math.max(old, m);
                }
                foreach (var (door, hinge, latch, len0, beams) in doors)
                {
                    double dl = math.abs(math.distance(Mean(hinge), Mean(latch)) - len0);
                    maxApertureChange.TryGetValue(door, out double o1);
                    maxApertureChange[door] = math.max(o1, dl);
                    double f = 0;
                    bool broken = false;
                    foreach (int j in beams)
                    {
                        if (w.broken[j] != 0) { broken = true; continue; }
                        f = math.max(f, w.stress[j] * w.beams[j].strength);
                    }
                    maxLatchForce.TryGetValue(door, out double o2);
                    maxLatchForce[door] = math.max(o2, f);
                    if (broken && !latchBreak.ContainsKey(door)) latchBreak[door] = t;
                }
            }

            public string Report()
            {
                var sb = new System.Text.StringBuilder("offsets from the cabin rigid motion (m):");
                foreach (var kv in maxOffset) sb.Append($" {kv.Key} {kv.Value:F3}");
                foreach (var (door, _, _, len0, _) in doors)
                {
                    maxApertureChange.TryGetValue(door, out double ap);
                    maxLatchForce.TryGetValue(door, out double lf);
                    sb.Append($" | {door}: aperture {len0:F3} m changed by up to {ap * 1000:F0} mm, latch force up to {lf / 1000:F1} kN");
                    if (latchBreak.TryGetValue(door, out double tb)) sb.Append($", latch broke at {tb * 1000:F0} ms");
                }
                return sb.ToString();
            }
        }

'''
pairs = [
    ("        public static readonly string[] FrontCrush", WATCH + "        public static readonly string[] FrontCrush"),
    ("            double Pitch() => math.degrees(",
     "            var closures = new ClosureWatch(w, bi, cabin);\n            double Pitch() => math.degrees("),
    ("                if (tContact >= 0)\n                {\n                    excess = math.max(excess, balance - bal0);",
     "                if (tContact >= 0)\n                {\n                    closures.Sample(t - tContact);\n"
     "                    excess = math.max(excess, balance - bal0);"),
    ('                atEnd = $"elastic by material: {ByMaterial(w, bi, true)} | plastic: {ByMaterial(w, bi, false, 14)} | {Damage(w, bi)}",',
     '                atEnd = $"elastic by material: {ByMaterial(w, bi, true)} | plastic: {ByMaterial(w, bi, false, 14)} | {Damage(w, bi)} | " +\n'
     '                        closures.Report(),'),
]
for o, n in pairs:
    assert s.count(o) == 1, o[:80]
    s = s.replace(o, n)
p.write_text(s, encoding="utf-8")
print("patched")
