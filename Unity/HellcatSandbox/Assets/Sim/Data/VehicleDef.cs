using System;
using System.IO;
using UnityEngine;

namespace Hellcat.Sim.Data
{
    // JSON schema of sim/vehicle/<name>/geometry.json ("hellcat-softbody" v1), written by
    // tools/blender/hcar/sk.py. Frame: Unity (x right, y up, z forward), SI units.
    // Triangle winding: cross(b - a, c - a) points out of the body.
    // All fields are always written by the exporter, so no defaults are relied on.

    [Serializable]
    public class NodeDef
    {
        public string name;
        public float[] p;          // position (m)
        public float m;            // mass (kg)
        public int flags;          // NodeFlag bits
        public string cmat;        // contact material name (params.json)
        public string group;       // collision/skinning group
        public string part;        // part name (break-off unit, skinning)
    }

    [Serializable]
    public class BeamDef
    {
        public int a, b;
        public string type;        // NORMAL, ANISOTROPIC, BOUNDED, SUPPORT, HYDRO
        public string mat;         // material name (params.json)
        public string bg;          // break group name ("" none)
        public int bgt;            // break group type: 0 triggers the group, 1 passive
        public float pre;          // precompression factor (rest = spawn length * pre)
        public string hydro;       // hydro input name for HYDRO beams
        public float hf;           // hydro factor: rest = spawnRest * (1 + hf * input)
    }

    [Serializable]
    public class TriDef
    {
        public int a, b, c;
        public string type;        // COLLIDE, NONCOLLIDABLE, PRESSURE (cavity only), AERO (aero only)
        public string group;
        public string bg;
        public float drag, lift;   // % of a flat plate (BeamNG convention)
    }

    [Serializable]
    public class WheelDef
    {
        public string name;        // FL, FR, RL, RR
        public int axleInner, axleOuter; // nodes on the rotation axis (inner = toward the car centre)
        public int[] rim;          // nodes that receive the drive/brake couple (on the rim)
        public int[] tread;        // ground-contact nodes (load/slip telemetry)
        public int arm;            // reaction node on the knuckle/body, off the axis
        public int driven;         // 1: receives drive torque
        public int steered;
        public string brake;       // brake parameter set name in params ("front"/"rear")
        public float radius;       // rolling radius (m)
        public string pressureGroup; // "" for wheels without a pressurized tire
        public int[] driveReaction;  // body nodes taking the drive torque reaction (the differential); empty: none driven
        public string windup;        // wind-up element parameter set in params ("front"/"rear"), "" none (D-036)
        public int[] windupBody;     // body nodes taking the wind-up couple (link pivots, their mounts, the spring tower)
        public int[] kingpin;        // steered knuckles: lower and upper ball joint (alignment element's camber axis, D-051)
    }

    [Serializable]
    public class PressureGroupDef
    {
        public string name;
        public int[] tris;         // indices into triangles (closed, outward winding)
        public float pressure;     // gauge pressure at spawn (Pa)
        public string wheel;
    }

    [Serializable]
    public class TorsionBarDef
    {
        public int[] n;            // 4 nodes: lever tip 1, axis 1, axis 2, lever tip 2
        public string mat;
        public string bg;
    }

    [Serializable]
    public class HingeDef
    {
        public int[] n;            // 4 nodes: wing 1, edge node 1, edge node 2, wing 2 (triangles (n0, n1, n2), (n1, n2, n3))
        public string mat;         // hinge material (params.json "hingeMaterials")
    }

    [Serializable]
    public class DampGroupDef
    {
        public string name;
        public int[] nodes;        // each node in at most one damp group
        public string mat;         // params.json "dampGroupMaterials"
        public string bg;          // break group that ends the damping (a shattered pane), "" never
        public string[] nodeBg;    // per node: break group that detaches the node from the group ("" never; may be absent)
        public string reference;   // damp group whose rigid motion the part is also damped towards (D-038), "" none
        public string[] refBg;     // break groups that end the relative damping (the part's latch / hinges / clips)
    }

    [Serializable]
    public class PartDef
    {
        public string name;
        public int[] nodes;
        public string[] visuals;   // visual object names (skinning)
    }

    [Serializable]
    public class CameraMountDef
    {
        public string name;        // cockpit, bumper, chase_target
        public int[] nodes;        // 3 or 4 nodes that define a local frame
        public float[] offset;     // eye/camera position in that frame's rest coordinates (m)
    }

    [Serializable]
    public class VehicleDef
    {
        public string format;
        public int version;
        public string name;
        public string units;
        public NodeDef[] nodes;
        public BeamDef[] beams;
        public TriDef[] triangles;
        public WheelDef[] wheels;
        public PressureGroupDef[] pressureGroups;
        public TorsionBarDef[] torsionBars;
        public HingeDef[] hinges;  // shell bending elements of the panel skins (D-032)
        public DampGroupDef[] dampGroups; // deformation damping relative to the group's rigid motion (D-033)
        public PartDef[] parts;
        public CameraMountDef[] cameras;
        public string[] hydros;    // control inputs used by HYDRO beams

        /// <summary>Fills absent arrays (hand-built test bodies do not go through <see cref="Load"/>).</summary>
        public static void Normalize(VehicleDef def)
        {
            def.nodes ??= Array.Empty<NodeDef>();
            def.beams ??= Array.Empty<BeamDef>();
            def.triangles ??= Array.Empty<TriDef>();
            def.wheels ??= Array.Empty<WheelDef>();
            def.pressureGroups ??= Array.Empty<PressureGroupDef>();
            def.torsionBars ??= Array.Empty<TorsionBarDef>();
            def.hinges ??= Array.Empty<HingeDef>();
            def.dampGroups ??= Array.Empty<DampGroupDef>();
            def.parts ??= Array.Empty<PartDef>();
            def.cameras ??= Array.Empty<CameraMountDef>();
            def.hydros ??= Array.Empty<string>();
        }

        public static VehicleDef Load(string path)
        {
            var def = JsonUtility.FromJson<VehicleDef>(File.ReadAllText(path));
            if (def == null || def.format != "hellcat-softbody")
                throw new InvalidDataException($"{path}: not a hellcat-softbody geometry file");
            def.triangles ??= Array.Empty<TriDef>();
            def.wheels ??= Array.Empty<WheelDef>();
            def.pressureGroups ??= Array.Empty<PressureGroupDef>();
            def.torsionBars ??= Array.Empty<TorsionBarDef>();
            def.hinges ??= Array.Empty<HingeDef>();
            def.dampGroups ??= Array.Empty<DampGroupDef>();
            Normalize(def);
            def.parts ??= Array.Empty<PartDef>();
            def.cameras ??= Array.Empty<CameraMountDef>();
            def.hydros ??= Array.Empty<string>();
            return def;
        }
    }
}
