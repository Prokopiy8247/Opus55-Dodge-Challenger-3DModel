"""One-off (P3b): X10 variants round 2 (lateral stiffness sources, Stribeck friction) + static lateral stiffness."""
from pathlib import Path

P = Path("Unity/HellcatSandbox/Assets/Sim/Validation/TireTests.cs")
s = P.read_text(encoding="utf-8")


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:100]
    s = s.replace(old, new)


rep("""                new TireVariant { name = "base" },
                new TireVariant { name = "xbrace_40k", prm = p => AddCrossMaterial(p, 40000f), def = d => AddCrossBraces(d, "tire_side_x") },
                new TireVariant { name = "xbrace_100k", prm = p => AddCrossMaterial(p, 100000f), def = d => AddCrossBraces(d, "tire_side_x") },
                new TireVariant { name = "mu_1.3_1.05", prm = p => Mu(p, 1.3f, 1.05f) },
                new TireVariant { name = "xbrace_100k_mu_1.3_1.05", prm = p => { AddCrossMaterial(p, 100000f); Mu(p, 1.3f, 1.05f); }, def = d => AddCrossBraces(d, "tire_side_x") },""",
    """                new TireVariant { name = "base" },
                new TireVariant { name = "tread_lat_x2", prm = p => ScaleMaterial(p, "tire_tread_lat", 2f) },
                new TireVariant { name = "tread_diag_x2", prm = p => ScaleMaterial(p, "tire_tread_diag", 2f) },
                new TireVariant { name = "side_diag_x2", prm = p => ScaleMaterial(p, "tire_side_diag", 2f) },
                new TireVariant { name = "anchor_alpha_0.45", prm = p => { foreach (var c in p.contactMaterials) if (c.name == "tire") c.alphaTangent = 0.45f; } },
                new TireVariant { name = "stribeck_1.4_0.85_v3", prm = p =>
                {
                    foreach (var c in p.contactMaterials)
                        if (c.name == "tire") { c.muStatic = 1.4f; c.muSliding = 0.85f; c.stribeckVel = 3f; }
                } },""")

# static lateral stiffness in the tuning loop, after the static vertical load
rep("""                    double rate = LoadRear / (yc - rig.centre.y) / 1000.0;""",
    """                    double rate = LoadRear / (yc - rig.centre.y) / 1000.0;
                    // static lateral stiffness: the loaded tire held by its patch, the spindle moved 4 mm sideways
                    rig.velocity = double3.zero;
                    for (int k = 0; k < 400; k++)
                        rig.Step();
                    rig.Force(1.0, out _);
                    rig.velocity = new double3(0.008, 0, 0);
                    for (int k = 0; k < 1000; k++)
                        rig.Step();
                    rig.velocity = double3.zero;
                    for (int k = 0; k < 200; k++)
                        rig.Step();
                    double fyLat = rig.Force(200 * rig.w.dt, out _).x;
                    double kLat = -fyLat / 0.004 / 1000.0;""")
rep("""                    r.Info($"{v.name}", sv, "S",
                        $"rate {rate:F0} kN/m; C_a/Fz""",
    """                    r.Info($"{v.name}", sv, "S",
                        $"rate {rate:F0} kN/m, lateral {kLat:F0} kN/m; C_a/Fz""")
P.write_text(s, encoding="utf-8")
print("ok")
