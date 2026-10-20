"""One-off (P5): fence posts anchored by two buried nodes each (front and back, a triangle against tipping); box stacks
aligned (corner on corner: the node contact needs the upper box's corners over the lower box's top)."""
from pathlib import Path

A = Path(__file__).resolve().parents[2] / "Unity/HellcatSandbox/Assets"


def patch(rel, pairs):
    p = A / rel
    s = p.read_text(encoding="utf-8")
    for o, n in pairs:
        assert s.count(o) == 1, (rel, o[:70])
        s = s.replace(o, n)
    p.write_text(s, encoding="utf-8")


patch("Sim/Props/PropFactory.cs", [
    ("""            // posts set in the ground: fixed nodes 0.3 m down, two breakable beams from each post's foot
            foreach (int c in new[] { 0, cols - 1 })
            {
                float x = -0.5f * FenceWidth + FenceWidth * c / (cols - 1);
                int g = b.Node($"ground{c}", new float3(x, -0.3f, 0f), 0f, TestBody.Free, "prop_wood");
                b.Beam(g, id[c, 0, 0], "fence_anchor");
                b.Beam(g, id[c, 0, 1], "fence_anchor");
                b.Beam(g, id[c, 1, 0], "fence_anchor");
                b.Beam(g, id[c, 1, 1], "fence_anchor");
            }""",
     """            // posts set in the ground: two fixed nodes 0.3 m down, 0.4 m in front of and behind each post, each tied to the
            // post's four nodes by breakable beams (a triangle in the panel's normal plane holds it upright)
            foreach (int c in new[] { 0, cols - 1 })
            {
                float x = -0.5f * FenceWidth + FenceWidth * c / (cols - 1);
                for (int side = 0; side < 2; side++)
                {
                    int g = b.Node($"ground{c}{side}", new float3(x, -0.3f, side == 0 ? -0.4f : 0.4f), 0f, TestBody.Free, "prop_wood");
                    b.Beam(g, id[c, 0, 0], "fence_anchor");
                    b.Beam(g, id[c, 0, 1], "fence_anchor");
                    b.Beam(g, id[c, 1, 0], "fence_anchor");
                    b.Beam(g, id[c, 1, 1], "fence_anchor");
                }
            }"""),
])

patch("Editor/Build/TestMapBuilder.cs", [
    ("""                    field.props.Add(new PropField.Spot { kind = PropFactory.Kind.Box, position = new Vector3(fx - 1.55f + 0.62f * c, 0f, -3.5f - 0.62f * r), yawDeg = 7f * ((c + r) % 3) });""",
     """                    field.props.Add(new PropField.Spot { kind = PropFactory.Kind.Box, position = new Vector3(fx - 1.55f + 0.62f * c, 0f, -3.5f - 0.62f * r) });"""),
    ("""                    field.props.Add(new PropField.Spot { kind = PropFactory.Kind.Box, position = new Vector3(fx - 0.93f + 0.62f * c, PropFactory.BoxSize + PropField.SpawnGap, -3.5f - 0.62f * r), yawDeg = 4f * c });""",
     """                    field.props.Add(new PropField.Spot { kind = PropFactory.Kind.Box, position = new Vector3(fx - 0.93f + 0.62f * c, PropFactory.BoxSize + PropField.SpawnGap, -3.5f - 0.62f * r) });"""),
])
print("patched")
