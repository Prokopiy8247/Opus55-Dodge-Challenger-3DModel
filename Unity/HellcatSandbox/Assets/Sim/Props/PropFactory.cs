using System;
using Hellcat.Sim.Data;
using Hellcat.Sim.Validation;
using Unity.Mathematics;

namespace Hellcat.Sim.Props
{
    /// <summary>
    /// Debris of the test map's O8 field (brief 8; D-081): small node-beam bodies in the same solver as the car, so they
    /// collide with it both ways (its nodes on their triangles, their nodes on its triangles) and with the statics. Sizes
    /// and masses from the brief: barrel 0.58 m x 0.88 m, 20 kg (steel drum: two rings of 8, braced, capped); box 0.5 m
    /// cube, 5 kg; traffic cone 0.70 m, 1.5 kg (weighted square base, ring, apex); wooden fence panel 2.4 x 1.2 m, 15 kg,
    /// held upright by two posts set in the ground (fixed anchor nodes, breakable at 4 kN). Each body is braced to stay
    /// rigid (they are drawn as rigid meshes on the best-fit frame of their nodes). The explicit step's criterion S (the
    /// largest eigenvalue of dt^2 K + 2 dt C plus the contact term, per unit mass; the car's is 2.44, the limit 2.5) counts
    /// stiffness, damping and contact of every node: the rates are sized from the most connected node of each prop for
    /// about 0.6 of stiffness, 0.3 of damping and 0.7 of contact (S near 1.6), so the debris never sets the step's limit.
    /// Local frame: origin on the ground at the centre of the footprint, y up, +z forward.
    /// </summary>
    public static class PropFactory
    {
        public enum Kind { Barrel, Box, Cone, FencePanel }

        public const float BarrelRadius = 0.29f, BarrelHeight = 0.88f, BarrelMass = 20f;
        public const float BoxSize = 0.5f, BoxMass = 5f;
        public const float ConeHeight = 0.70f, ConeBase = 0.38f, ConeMass = 1.5f;
        public const float FenceWidth = 2.4f, FenceHeight = 1.2f, FenceThickness = 0.06f, FenceMass = 15f;
        public const float FenceAnchorStrength = 4000f;   // N per anchor beam

        public static (VehicleDef def, SimParamsDef prm) Build(Kind kind)
        {
            switch (kind)
            {
                case Kind.Barrel: return Barrel();
                case Kind.Box: return Box();
                case Kind.Cone: return Cone();
                case Kind.FencePanel: return FencePanel();
                default: throw new ArgumentOutOfRangeException(nameof(kind));
            }
        }

        /// <summary>Approximate collision footprint radius (m) for placement checks.</summary>
        public static float Radius(Kind kind) => kind switch
        {
            Kind.Barrel => BarrelRadius,
            Kind.Box => 0.36f,
            Kind.Cone => 0.27f,
            _ => 0.5f * FenceWidth,
        };

        public static float Mass(Kind kind) => kind switch
        {
            Kind.Barrel => BarrelMass,
            Kind.Box => BoxMass,
            Kind.Cone => ConeMass,
            _ => FenceMass,
        };

        static SimParamsDef Params(BeamMaterialDef[] mats, ContactMaterialDef cmat)
        {
            var p = new SimParamsDef
            {
                materials = mats,
                contactMaterials = new[] { cmat },
            };
            p.Normalize();
            return p;
        }

        static ContactMaterialDef Contact(string name, float muStatic, float muSliding) => new ContactMaterialDef
        {
            name = name, muStatic = muStatic, muSliding = muSliding, stribeckVel = 0.3f, zetaNormal = 0.15f, bias = 0.01f,
        };

        static (VehicleDef, SimParamsDef) Barrel()
        {
            var b = new TestBody();
            const int n = 8;
            const string mat = "prop_barrel";
            float m = BarrelMass / (2 * n + 2);
            var lo = new int[n];
            var hi = new int[n];
            for (int k = 0; k < n; k++)
            {
                float a = 2f * math.PI * k / n;
                var dir = new float3(math.cos(a), 0f, math.sin(a)) * BarrelRadius;
                lo[k] = b.Node($"lo{k}", dir, m, TestBody.Solid, "prop_steel");
                hi[k] = b.Node($"hi{k}", dir + new float3(0f, BarrelHeight, 0f), m, TestBody.Solid, "prop_steel");
            }
            int cl = b.Node("clo", float3.zero, m, TestBody.Solid, "prop_steel");
            int ch = b.Node("chi", new float3(0f, BarrelHeight, 0f), m, TestBody.Solid, "prop_steel");
            b.Beam(cl, ch, mat);
            for (int k = 0; k < n; k++)
            {
                int k1 = (k + 1) % n;
                b.Beam(lo[k], lo[k1], mat);
                b.Beam(hi[k], hi[k1], mat);
                b.Beam(lo[k], hi[k], mat);
                b.Beam(lo[k], hi[k1], mat);
                b.Beam(hi[k], lo[k1], mat);
                b.Beam(lo[k], cl, mat);
                b.Beam(hi[k], ch, mat);
                b.Beam(lo[k], hi[(k + n / 2) % n], mat);   // diametral braces keep the drum round
                b.Beam(lo[k], ch, mat);
                b.Beam(hi[k], cl, mat);
            }
            for (int k = 0; k < n; k++)
            {
                int k1 = (k + 1) % n;
                b.Quad(lo[k], hi[k], hi[k1], lo[k1]);
                b.Tri(cl, lo[k1], lo[k]);
                b.Tri(ch, hi[k], hi[k1]);
            }
            // the end-cap centres carry 17 beams each: 6e4 N/m and 8 N s/m keep them at S ~ 0.6 + 0.3
            var mats = new[] { TestBody.Mat(mat, 6.0e4f, 8f) };
            return (b.Def("barrel"), Params(mats, Contact("prop_steel", 0.45f, 0.40f)));
        }

        static (VehicleDef, SimParamsDef) Box()
        {
            var b = new TestBody();
            float h = 0.5f * BoxSize;
            b.Box("c", new float3(0f, h, 0f), new float3(h), BoxMass, "prop_box", TestBody.Solid, "prop_cardboard");
            var mats = new[] { TestBody.Mat("prop_box", 6.0e4f, 8f) };
            return (b.Def("box"), Params(mats, Contact("prop_cardboard", 0.6f, 0.5f)));
        }

        static (VehicleDef, SimParamsDef) Cone()
        {
            var b = new TestBody();
            const string mat = "prop_cone";
            float hb = 0.5f * ConeBase, hr = 0.14f;
            var ids = new int[9];
            // weighted base plate corners, the cone's foot ring, the tip
            for (int k = 0; k < 4; k++)
            {
                float sx = (k & 1) != 0 ? 1f : -1f, sz = (k & 2) != 0 ? 1f : -1f;
                ids[k] = b.Node($"base{k}", new float3(sx * hb, 0f, sz * hb), 0.22f, TestBody.Solid, "prop_rubber");
                ids[4 + k] = b.Node($"ring{k}", new float3(sx * hr, 0.05f, sz * hr), 0.1f, TestBody.Solid, "prop_rubber");
            }
            ids[8] = b.Node("tip", new float3(0f, ConeHeight, 0f), ConeMass - 4 * 0.22f - 4 * 0.1f, TestBody.Solid, "prop_rubber");
            for (int a = 0; a < 9; a++)
                for (int c = a + 1; c < 9; c++)
                    b.Beam(ids[a], ids[c], mat);
            // corners in the ring order 0, 1, 3, 2 (k bits: x then z)
            int[] o = { 0, 1, 3, 2 };
            for (int k = 0; k < 4; k++)
            {
                int a = o[k], c = o[(k + 1) % 4];
                b.Tri(ids[4 + a], ids[8], ids[4 + c]);                 // cone side
                b.Quad(ids[a], ids[4 + a], ids[4 + c], ids[c]);         // base skirt
            }
            b.Quad(ids[0], ids[2], ids[3], ids[1]);                     // underside
            var mats = new[] { TestBody.Mat(mat, 1.2e4f, 1.5f) };
            return (b.Def("cone"), Params(mats, Contact("prop_rubber", 0.9f, 0.8f)));
        }

        static (VehicleDef, SimParamsDef) FencePanel()
        {
            var b = new TestBody();
            const string mat = "prop_fence";
            const int cols = 4;   // nodes along the width: posts at the ends, two in between
            float m = FenceMass / (cols * 4);
            var id = new int[cols, 2, 2];   // [column, bottom/top, front/back]
            for (int c = 0; c < cols; c++)
                for (int v = 0; v < 2; v++)
                    for (int s = 0; s < 2; s++)
                    {
                        float x = -0.5f * FenceWidth + FenceWidth * c / (cols - 1);
                        float y = v == 0 ? 0.05f : FenceHeight;
                        float z = s == 0 ? -0.5f * FenceThickness : 0.5f * FenceThickness;
                        id[c, v, s] = b.Node($"n{c}{v}{s}", new float3(x, y, z), m, TestBody.Solid, "prop_wood");
                    }
            // every pair inside a column and between neighbouring columns: a stiff board
            for (int c = 0; c < cols; c++)
                for (int a = 0; a < 4; a++)
                    for (int q = a + 1; q < 4; q++)
                        b.Beam(id[c, a >> 1, a & 1], id[c, q >> 1, q & 1], mat);
            for (int c = 0; c + 1 < cols; c++)
                for (int a = 0; a < 4; a++)
                    for (int q = 0; q < 4; q++)
                        b.Beam(id[c, a >> 1, a & 1], id[c + 1, q >> 1, q & 1], mat);
            // the outer surface: front and back faces, ends, top and bottom strips
            for (int c = 0; c + 1 < cols; c++)
            {
                b.Quad(id[c, 0, 0], id[c, 1, 0], id[c + 1, 1, 0], id[c + 1, 0, 0]);   // front (-z)
                b.Quad(id[c, 0, 1], id[c + 1, 0, 1], id[c + 1, 1, 1], id[c, 1, 1]);   // back (+z)
                b.Quad(id[c, 1, 0], id[c, 1, 1], id[c + 1, 1, 1], id[c + 1, 1, 0]);   // top
                b.Quad(id[c, 0, 0], id[c + 1, 0, 0], id[c + 1, 0, 1], id[c, 0, 1]);   // bottom
            }
            b.Quad(id[0, 0, 0], id[0, 0, 1], id[0, 1, 1], id[0, 1, 0]);
            b.Quad(id[cols - 1, 0, 0], id[cols - 1, 1, 0], id[cols - 1, 1, 1], id[cols - 1, 0, 1]);
            // posts set in the ground: two fixed nodes 0.3 m down, 0.4 m in front of and behind each post, each tied to the
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
            }
            var mats = new[]
            {
                TestBody.Mat(mat, 7.0e4f, 12f),
                TestBody.Mat("fence_anchor", 5.0e4f, 15f, strength: FenceAnchorStrength),
            };
            return (b.Def("fence_panel"), Params(mats, Contact("prop_wood", 0.6f, 0.5f)));
        }
    }
}
