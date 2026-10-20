using Unity.Mathematics;

namespace Hellcat.Sim
{
    /// <summary>Beam kinds (semantics in docs/physics_notes.md section 8.4).</summary>
    public static class BeamType
    {
        public const byte Normal = 0;       // linear spring-damper
        public const byte Anisotropic = 1;  // separate stiffness/damping when longer than rest (tire sidewalls, ropes)
        public const byte Bounded = 2;      // extra limit spring/damper beyond short/long bounds (bump stops, rebound limits)
        public const byte Support = 3;      // compression only; breaks when stretched past its long bound
        public const byte Hydro = 4;        // rest length driven by a control input (steering rack)
    }

    public static class BeamFlag
    {
        public const byte Deformable = 1;    // plastic deformation enabled
        public const byte Breakable = 2;     // can break when |elastic force| > strength
        public const byte GroupPassive = 4;  // breakGroupType 1: broken by its group but never triggers it
        public const byte Disabled = 8;      // spawned broken (e.g. optional beam that is absent)
    }

    public static class NodeFlag
    {
        public const int Collision = 1;        // collides with other bodies' triangles (dynamic)
        public const int SelfCollision = 2;    // collides with its own body's triangles
        public const int StaticCollision = 4;  // collides with the ground and static obstacles
        public const int Fixed = 8;            // does not move
        public const int Tire = 16;            // tread node (uses the tire compound and is counted for wheel loads)
    }

    /// <summary>Read-only per-beam parameters, resolved from the material table at load time.</summary>
    public struct BeamStatic
    {
        public int a, b;
        public byte type, flags;
        public short breakGroup;      // -1: none
        public int hydro;             // index into the hydro input array, -1: none
        public int body;              // owning body (spawn ramp)

        public float k, c, cReb;              // spring (N/m), damping compression / extension (N/(m/s))
        public float kExp, cExp;              // anisotropic: used while longer than rest
        public float cFast, cRebFast;         // damping above the split velocity
        public float vSplit, vSplitReb;       // split velocity (m/s); +inf disables
        public float yield0, hardening;       // initial deform threshold (N), hardening modulus (N/m)
        public float yieldCap, strength;      // max deform threshold (N), break strength (N)
        public float minRest, maxRest;        // plastic limits on the rest length (m)
        public float shortLen, longLen;       // bounds (m) for BOUNDED; longLen also auto-breaks SUPPORT
        public float boundZone;               // blend distance past a bound (m)
        public float kLimit, cLimit, cLimitReb;
        public float hydroFactor, hydroMinRatio, hydroMaxRatio;
        public float spawnLength;             // distance between the nodes at spawn (m)
        public float spawnRest;               // rest length after precompression and preload (m)
        public float rampBase;                // rest length at the start of the spawn ramp: spawn length + preload / k
                                              // (the preload holds the ride height from the first step; only the
                                              // geometric precompression "pre" is blended in)
        public short pressureGroup;           // -1: none; else the beam adds pretension * pressureScale[group] (D-028)
        public float pretension;              // N, tension at full inflation that balances the cavity pressure at spawn
        public float inflationShare;          // share of k that comes from the inflation: k (1 - share (1 - inflation))
                                              // for a cavity beam (D-045); the flat tire keeps the carcass part
        public float relax;                   // 1/s, spring-back suppression after plastic flow (D-056); 0: off
        public int spinGroup;                 // -1: none; else a ring beam of a spinning wheel group: tension spinCoef |w|^2
        public float spinCoef;                // N s^2: (m / L) R^2 of the ring, so the tension is the hoop tension mu v^2 (D-044)
    }

    /// <summary>Static collider shapes. All are solid; signed distance is negative inside.</summary>
    public static class PrimType
    {
        public const int Plane = 0;     // n = axis, d = halfExtents.x : dot(n,p) - d
        public const int Box = 1;       // oriented box
        public const int Cylinder = 2;  // axis = local y, radius = halfExtents.x, half height = halfExtents.y
        public const int Convex = 3;    // planes [planeStart, planeStart + planeCount) in world space
    }

    public struct StaticPrimitive
    {
        public int type;
        public int surface;
        public float3 center;
        public quaternion rotation;   // local -> world
        public float3 halfExtents;
        public float3 axis;           // plane normal
        public int planeStart, planeCount;
        public float3 aabbMin, aabbMax;
    }

    /// <summary>Per contact material (node side): friction law and contact zone.</summary>
    public struct ContactMaterial
    {
        public float muStatic, muSliding;   // on a reference surface (frictionScale 1)
        public float stribeckVel;           // slip speed where friction approaches muSliding (m/s)
        public float stribeckExp;           // shape exponent
        public float loadRef;               // normal force (N) at which the load factor equals 1
        public float loadSensitivity;       // relative friction loss per relative load increase
        public float minLoadFactor;
        public float bias;                  // contact zone thickness in front of a surface (m)
        public float alphaNormal;           // normal penalty stiffness = alpha * m / dt^2
        public float zetaNormal;            // normal damping ratio
        public float alphaTangent;          // friction anchor stiffness = alpha * m / dt^2
        public float zetaTangent;
        public float latExtra;              // friction ellipse (D-048): 1 / muLateral^2 - 1 (0: isotropic)
        public int hardContact;             // 1: inelastic after a projection until the node leaves the zone (D-055)
    }

    /// <summary>Per static surface: friction multiplier and rolling resistance.</summary>
    public struct SurfaceMaterial
    {
        public float frictionScale;
        public float rollingResistance;     // coefficient for tire rolling resistance
    }

    /// <summary>Global solver parameters for one step.</summary>
    public struct StepParams
    {
        public float dt;
        public float3 gravity;
        public float maxNodeSpeed;          // safety clamp (m/s); nodes above it are flagged unstable
    }

    /// <summary>
    /// Four-node torsion bar (anti-roll bar): resists the change of the dihedral angle about the axis n2-n3
    /// between the planes (n1, n2, n3) and (n2, n3, n4). Forces in four force slots (gathered by the node job).
    /// </summary>
    public struct TorsionBarStatic
    {
        public int n1, n2, n3, n4;          // lever tip 1, axis node 1, axis node 2, lever tip 2
        public float k, c;                  // N*m/rad, N*m*s/rad
        public float strength;              // N*m, breaks above this elastic torque (float.MaxValue: never)
        public float phi0;                  // dihedral angle at spawn (rad)
        public float lever1, lever2, axis;  // spawn distances of the lever tips from the axis line and the axis length (m):
                                            // the bar is gone when its geometry collapses (D-060)
        public int beam12, beam23, beam34;  // the bar is gone once one of these beams breaks (-1: no such beam)
        public int breakGroup;              // ... or once this break group fires (-1: none), e.g. a wind-up bar's wheel
        public int slotStart;               // 4 slots: n1, n2, n3, n4
        public int body;
    }

    /// <summary>
    /// Shell bending element of a panel skin (D-032): a dihedral spring-damper across the edge n2-n3 shared by the
    /// triangles (n1, n2, n3) and (n2, n3, n4), with a plastic rest angle (dents, creases). Same kernel as the torsion
    /// bars; evaluated in parallel by <see cref="HingeForceJob"/>, forces in four slots per hinge.
    /// </summary>
    public struct HingeStatic
    {
        public float dampCap;               // rad/s: the damping torque saturates above this bending rate (0: viscous)
        public int n1, n2, n3, n4;
        public float k, c;                  // N*m/rad, N*m*s/rad
        public float yield0;                // N*m, initial yield moment (float.MaxValue: elastic)
        public float hardening;             // N*m per rad of plastic rotation
        public float yieldCap;              // N*m
        public float phi0;                  // spawn dihedral angle (rad)
        public float g0sq;                  // 1/m^2, largest squared dihedral gradient of the four nodes at spawn
        public int beam12, beam23, beam34;  // the hinge is gone once one of these beams breaks (-1: no such beam)
        public int slotStart;
        public int body;
    }

    /// <summary>Closed air volume (tire cavity): isothermal ideal gas, p_abs * V = gas (D-028).</summary>
    public struct PressureGroupStatic
    {
        public int triStart, triCount;      // into the pressure triangle list (closed, outward winding)
        public int slotStart;               // 3 force slots per triangle
        public int leakBeamStart, leakBeamCount; // breakable beams between cavity nodes: a broken one opens a leak
        public float gas0;                  // p_abs * V at spawn (J)
        public float volume0;               // m^3 at spawn
        public float pAtm;                  // Pa
        public float maxAbs;                // absolute pressure cap (Pa)
        public float minVolume;             // m^3, floor of the volume used for the pressure (crushed tire)
        public float leakPerBeam, leakMax;  // 1/s
        public int body;
    }

    public struct PressureState
    {
        public float volume;                // m^3
        public float pAbs;                  // Pa
        public float gas;                   // p_abs * V (J); falls while leaking
        public int brokenBeams;             // broken leak beams (telemetry)
        public float puncture;              // 1/s extra leak rate of a punctured (flagged) tread or sidewall patch
    }

    /// <summary>Collision triangle for node-vs-triangle contact between bodies (and self-collision).</summary>
    public struct CollTri
    {
        public int a, b, c;                 // global node indices, cross(b - a, c - a) points to the front side
        public int body;
        public int part;                    // world-unique part id: a node never collides with its own part's triangles
        public int breakGroup;              // the triangle disappears when this group fires (-1: never)
    }

    /// <summary>Dynamic (node-vs-triangle) contact of one node in one substep, written by NodeContactJob.</summary>
    public struct NodeContact
    {
        public int tri;                     // contact (or watched) triangle, -1: none
        public float3 w;                    // clamped barycentric weights of the contact point on (a, b, c)
        public float3 force;                // force on the node; the triangle nodes receive -w * force
        public float fn;                    // normal force (N)
        public float side;                  // +1: the node is on the front side of the triangle, -1: behind
    }

    /// <summary>Velocity change applied by the anti-tunnelling projection; the triangle gets the reaction next substep.</summary>
    public struct NodeImpulse
    {
        public int tri;
        public float3 w;
        public float3 impulse;              // N*s removed from the node (the triangle nodes receive +w * impulse)
    }

    /// <summary>World-wide tuning of node-vs-triangle collision (params.json "collision").</summary>
    public struct CollisionParams
    {
        public float cellSize;              // spatial hash cell (m)
        public int rebuildEvery;            // substeps between hash rebuilds
        public float frontBias;             // contact zone in front of a triangle (m), max over the node materials
        public float backBias;              // contact zone behind a triangle (m)
        public float alpha, zeta;           // penalty stiffness alpha * m_eff / dt^2 and damping ratio
        public float frictionScale;         // multiplies the node material's sliding friction
        public float footprintTolerance;    // barycentric slack at triangle edges
        public ulong bucketMask;            // hash table size - 1 (power of two)
        public int entryCapacity;
    }

    public static class CollisionCounter
    {
        public const int Entries = 0;       // grid entries after the last rebuild
        public const int Overflow = 1;      // entries dropped (capacity) since build
        public const int Rebuilds = 2;
        public const int Contacts = 3;      // nodes in dynamic contact in the last substep
        public const int Candidates = 4;    // node-triangle pairs tested in the last substep
        public const int Projections = 5;   // anti-tunnelling projections since build
        public const int InsertedTris = 6;
        public const int Count = 8;
    }
}
