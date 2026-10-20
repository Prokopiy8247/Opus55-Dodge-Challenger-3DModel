using System.Collections.Generic;
using Hellcat.Sim.Data;
using Unity.Mathematics;

namespace Hellcat.Sim.Validation
{
    /// <summary>Builds small node-beam bodies in code for the validation tests (same data types as geometry.json).</summary>
    public sealed class TestBody
    {
        readonly List<NodeDef> nodes = new List<NodeDef>();
        readonly List<BeamDef> beams = new List<BeamDef>();
        readonly List<TriDef> tris = new List<TriDef>();
        readonly HashSet<long> pairs = new HashSet<long>();

        public const int Free = 0;
        public const int Ground = NodeFlag.StaticCollision;
        public const int Solid = NodeFlag.StaticCollision | NodeFlag.Collision;

        public int Count => nodes.Count;
        public float3 P(int i) => new float3(nodes[i].p[0], nodes[i].p[1], nodes[i].p[2]);

        public int Node(string name, float3 p, float m, int flags = Solid, string cmat = "default", string part = "main")
        {
            nodes.Add(new NodeDef { name = name, p = new[] { p.x, p.y, p.z }, m = m, flags = flags, cmat = cmat, group = part, part = part });
            return nodes.Count - 1;
        }

        /// <summary>Adds a beam unless the pair already has one.</summary>
        public int Beam(int a, int b, string mat, string type = "NORMAL", string bg = "", float pre = 1f)
        {
            long key = a < b ? ((long)a << 32) | (uint)b : ((long)b << 32) | (uint)a;
            if (!pairs.Add(key))
                return -1;
            beams.Add(new BeamDef { a = a, b = b, type = type, mat = mat, bg = bg ?? "", bgt = 0, pre = pre, hydro = "", hf = 0f });
            return beams.Count - 1;
        }

        public void Tri(int a, int b, int c, string group = "main", string type = "COLLIDE")
        {
            tris.Add(new TriDef { a = a, b = b, c = c, type = type, group = group, bg = "" });
        }

        /// <summary>Quad (a, b, c, d counter-clockwise seen from the front side) as two triangles.</summary>
        public void Quad(int a, int b, int c, int d, string group = "main")
        {
            Tri(a, b, c, group);
            Tri(a, c, d, group);
        }

        /// <summary>Box of 8 nodes (corners of the half extents h around c), every pair braced, outward triangles.</summary>
        public int[] Box(string prefix, float3 c, float3 h, float mass, string mat, int flags = Solid, string cmat = "default",
            bool brace = true, string part = "main")
        {
            var id = new int[8];
            for (int k = 0; k < 8; k++)
            {
                float3 s = new float3((k & 1) != 0 ? 1 : -1, (k & 2) != 0 ? 1 : -1, (k & 4) != 0 ? 1 : -1);
                id[k] = Node($"{prefix}{k}", c + s * h, mass / 8f, flags, cmat, part);
            }
            for (int a = 0; a < 8; a++)
                for (int b = a + 1; b < 8; b++)
                {
                    int diff = math.countbits(a ^ b);
                    if (diff == 1 || brace)
                        Beam(id[a], id[b], mat);
                }
            // faces (outward): -x, +x, -y, +y, -z, +z
            Quad(id[0], id[4], id[6], id[2], part);
            Quad(id[1], id[3], id[7], id[5], part);
            Quad(id[0], id[1], id[5], id[4], part);
            Quad(id[2], id[6], id[7], id[3], part);
            Quad(id[0], id[2], id[3], id[1], part);
            Quad(id[4], id[5], id[7], id[6], part);
            return id;
        }

        public VehicleDef Def(string name) => new VehicleDef
        {
            format = "hellcat-softbody",
            version = 1,
            name = name,
            units = "SI",
            nodes = nodes.ToArray(),
            beams = beams.ToArray(),
            triangles = tris.ToArray(),
            wheels = new WheelDef[0],
            pressureGroups = new PressureGroupDef[0],
            torsionBars = new TorsionBarDef[0],
            parts = new PartDef[0],
            cameras = new CameraMountDef[0],
            hydros = new string[0],
        };

        public static BeamMaterialDef Mat(string name, float spring, float damp, float deform = -1, float strength = -1,
            float hardening = 0, float deformCap = -1) => new BeamMaterialDef
        {
            name = name,
            spring = spring,
            damp = damp,
            deform = deform,
            strength = strength,
            hardening = hardening,
            deformCap = deformCap,
        };

        /// <summary>Test parameters: no spawn ramp, given gravity, the listed materials, default contact and surfaces.</summary>
        public static SimParamsDef Params(float gravity, params BeamMaterialDef[] mats)
        {
            var p = new SimParamsDef
            {
                dt = 0.0005f,
                gravity = gravity,
                spawnRamp = 0f,
                maxNodeSpeed = 400f,
                materials = mats,
                contactMaterials = new[]
                {
                    new ContactMaterialDef { name = "default", muStatic = 0.6f, muSliding = 0.5f, stribeckVel = 0.1f, stribeckExp = 1.75f, loadSensitivity = 0f, zetaNormal = 0.3f },
                },
                surfaces = new[] { new SurfaceDef { name = "asphalt", frictionScale = 1f, rollingResistance = 0.012f } },
            };
            p.Normalize();
            return p;
        }
    }
}
