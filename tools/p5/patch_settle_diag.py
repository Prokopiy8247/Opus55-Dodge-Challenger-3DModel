"""One-off (P5): the map check lists the props that move at rest (kind, drift, node speed) so the settle can be judged."""
from pathlib import Path

A = Path(__file__).resolve().parents[2] / "Unity/HellcatSandbox/Assets"
p = A / "Game/Scenario/MapCheck.cs"
s = p.read_text(encoding="utf-8")
pairs = [
    ("""            int driftedCount = 0;
            float drift = props != null ? props.Displacement(0.05f, out driftedCount) : 0f;""",
     """            int driftedCount = 0;
            float drift = props != null ? props.Displacement(0.05f, out driftedCount) : 0f;
            string movers = Movers();"""),
    ("""            Write(propSpeed, drift, driftedCount, timing);""",
     """            Write(propSpeed, drift, driftedCount, timing, movers);"""),
    ("""        void Write(float propSpeed, float drift, int drifted, List<double> timing)
        {""",
     """        /// <summary>The props that moved at rest: kind, index, drift from the start (m), fastest node (m/s).</summary>
        string Movers()
        {
            if (props == null) return "";
            var w = runner.World;
            var list = new List<(float d, string text)>();
            for (int k = 0; k < props.Bodies.Count; k++)
            {
                var b = w.bodies[props.Bodies[k]];
                float3 c = float3.zero, c0 = float3.zero;
                float v = 0f;
                int n = 0;
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                {
                    if (w.invMass[i] <= 0f) continue;
                    c += w.pos[i];
                    c0 += w.SpawnPosition(i);
                    v = math.max(v, math.length(w.vel[i]));
                    n++;
                }
                float d = math.distance(c / n, c0 / n);
                if (d > 0.02f || v > 0.05f)
                    list.Add((d, $"{props.props[k].kind} {k}: drift {d:F3} m, node speed {v:F3} m/s, height {(c / n).y:F2} m"));
            }
            return string.Join("; ", list.OrderByDescending(x => x.d).Take(12).Select(x => x.text));
        }

        void Write(float propSpeed, float drift, int drifted, List<double> timing, string movers)
        {"""),
    ("""            sb.Append($"  \\"settle\\": {{\\"prop_max_node_speed\\": {F(propSpeed, "F4")}, \\"prop_max_drift_m\\": {F(drift, "F4")}, \\"props_drifted_5cm\\": {drifted}}},\\n");""",
     """            sb.Append($"  \\"settle\\": {{\\"prop_max_node_speed\\": {F(propSpeed, "F4")}, \\"prop_max_drift_m\\": {F(drift, "F4")}, \\"props_drifted_5cm\\": {drifted}, \\"movers\\": \\"{movers}\\"}},\\n");"""),
]
for o, n in pairs:
    assert s.count(o) == 1, o[:70]
    s = s.replace(o, n)
p.write_text(s, encoding="utf-8")
print("patched")
