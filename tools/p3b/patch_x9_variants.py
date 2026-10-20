"""One-off (P3b): X9 diagnostic variants for the current tire (belt hinges now in the geometry), hinge losses."""
from pathlib import Path

P = Path("Unity/HellcatSandbox/Assets/Sim/Validation/TireTests.cs")
s = P.read_text(encoding="utf-8")


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:100]
    s = s.replace(old, new)


rep("""            var variants = new List<(string name, Action<SimParamsDef> tweak, Action<VehicleDef> defTweak)>
            {
                ("belt_D400", Belt(400f), d => AddBeltHinges(d)),
                ("belt_D600", Belt(600f), d => AddBeltHinges(d)),
                ("belt_D800", Belt(800f), d => AddBeltHinges(d)),
                ("mass_0.8_belt_D400", Belt(400f), d => { Mass(d, 0.8f); AddBeltHinges(d); }),
            };""",
    """            void TireGroup(SimParamsDef p, Action<DampGroupMaterialDef> f)
            {
                foreach (var g in p.dampGroupMaterials)
                    if (g.name == "tire")
                        f(g);
            }
            _ = (Action<VehicleDef>)HalfMass;
            _ = (Func<float, Action<SimParamsDef>>)Belt;
            _ = (Action<VehicleDef, float>)Mass;
            var variants = new List<(string name, Action<SimParamsDef> tweak, Action<VehicleDef> defTweak)>
            {
                ("current", null, null),
                ("beam_damp_0.5", p => TireMat(p, m => { m.damp *= 0.5f; if (m.dampRebound > 0) m.dampRebound *= 0.5f; }), null),
                ("group_rate_4", p => TireGroup(p, g => g.rate = 4f), null),
                ("contact_zeta_0.05", p => TireContact(p, c => c.zetaNormal = 0.05f), null),
                ("anchor_alpha_0.15", p => TireContact(p, c => c.alphaTangent = 0.15f), null),
                ("all_low_damping", p =>
                {
                    TireMat(p, m => { m.damp *= 0.5f; if (m.dampRebound > 0) m.dampRebound *= 0.5f; });
                    TireGroup(p, g => g.rate = 4f);
                    TireContact(p, c => c.zetaNormal = 0.05f);
                }, null),
            };""")

rep("""            contact = 0;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                contact -= w.contactWork[i];
            return beams + groups + contact;""",
    """            contact = 0;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                contact -= w.contactWork[i];
            for (int h = b.hingeStart; h < b.hingeStart + b.hingeCount; h++)
                beams += w.hingeDampEnergy[h];   // belt hinges counted with the beams
            return beams + groups + contact;""")

rep("""            foreach (double v in new[] { 10.0, 20.0, 30.0, 45.0, 60.0, 75.0, 90.0 })
            {
                using var rig = TireRig.Build(ctx, "RR", false, tweak, 0.002f, defTweak);""",
    """            foreach (double v in new[] { 5.0, 20.0, 45.0, 90.0 })
            {
                using var rig = TireRig.Build(ctx, "RR", false, tweak, 0.002f, defTweak);""")
P.write_text(s, encoding="utf-8")
print("ok")
