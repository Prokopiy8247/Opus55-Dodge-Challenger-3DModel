using System;
using System.Collections.Generic;
using Hellcat.Sim.Data;
using Unity.Mathematics;
using static Hellcat.Sim.Validation.ValidationSuite;

namespace Hellcat.Sim.Validation
{
    /// <summary>
    /// Single-wheel tire test rig: one wheel assembly (rim, tread, axle and knuckle nodes, tire beams, cavity, damp
    /// group) extracted from the Hellcat skeleton as its own body on the ground. The axle and knuckle nodes are
    /// kinematic (fixed nodes whose positions the rig writes every substep: a flat-track tire tester's spindle);
    /// optionally the rim nodes too (a driven spindle for the longitudinal slip sweep). Forces are the contact
    /// impulses the solver applied to the tire's nodes over the sample window (the force plate).
    /// </summary>
    public sealed class TireRig : IDisposable
    {
        public SoftBodyWorld w;
        public readonly int[] hub;          // global node indices of the kinematic spindle (axle + knuckle)
        public readonly int[] rim;          // global rim node indices
        public readonly int[] tread;
        readonly double3[] hubRef, rimRef;  // positions relative to the spindle centre at spawn (wheel frame)
        public readonly double3 centre0;    // spindle centre at spawn (lowest tread node at the clearance)
        public readonly double radius0;     // unloaded outer radius (m)
        public readonly bool kinematicRim;
        public readonly int pressureGroup;
        public double3 centre;              // current spindle centre
        public double yaw;                  // rad: wheel heading = (sin yaw, 0, cos yaw)
        public double spinAngle;            // rad (kinematic rim)
        public double spinRate;             // rad/s (kinematic rim)
        public double3 velocity;            // spindle velocity
        public double time;

        TireRig(SoftBodyWorld w, int[] hub, int[] rim, int[] tread, bool kinematicRim)
        {
            this.w = w;
            this.hub = hub;
            this.rim = rim;
            this.tread = tread;
            this.kinematicRim = kinematicRim;
            pressureGroup = 0;
            // spindle centre: mean of the two axle nodes (the first two hub entries)
            centre0 = 0.5 * ((double3)w.pos[hub[0]] + (double3)w.pos[hub[1]]);
            centre = centre0;
            hubRef = new double3[hub.Length];
            for (int k = 0; k < hub.Length; k++)
                hubRef[k] = (double3)w.pos[hub[k]] - centre0;
            rimRef = new double3[rim.Length];
            for (int k = 0; k < rim.Length; k++)
                rimRef[k] = (double3)w.pos[rim[k]] - centre0;
            double rMax = 0;
            foreach (int t in tread)
            {
                double3 d = (double3)w.pos[t] - centre0;
                rMax = math.max(rMax, math.length(new double2(d.y, d.z)));
            }
            radius0 = rMax;
        }

        public void Dispose() => w?.Dispose();

        /// <summary>Builds the rig from a Hellcat wheel (axle along x, rolling along +z).</summary>
        public static TireRig Build(ValidationContext ctx, string wheelName, bool kinematicRim, Action<SimParamsDef> tweak = null,
            float clearance = 0.002f, Action<VehicleDef> defTweak = null)
        {
            var (def, prm) = LoadHellcat(ctx);
            tweak?.Invoke(prm);
            defTweak?.Invoke(def);
            WheelDef wd = null;
            foreach (var x in def.wheels)
                if (x.name == wheelName)
                    wd = x;
            if (wd == null)
                throw new ArgumentException($"no wheel {wheelName}");
            string part = def.nodes[wd.axleInner].part;
            var map = new Dictionary<int, int>();
            var nodes = new List<NodeDef>();
            var rimSet = new HashSet<int>(wd.rim);
            var treadSet = new HashSet<int>(wd.tread);
            for (int i = 0; i < def.nodes.Length; i++)
            {
                var nd = def.nodes[i];
                if (nd.part != part)
                    continue;
                bool spindle = !rimSet.Contains(i) && !treadSet.Contains(i);   // axle and knuckle nodes
                var c = new NodeDef
                {
                    name = nd.name, p = (float[])nd.p.Clone(), m = nd.m, cmat = nd.cmat, group = nd.group, part = nd.part,
                    flags = spindle || (kinematicRim && rimSet.Contains(i)) ? (nd.flags | NodeFlag.Fixed) : nd.flags,
                };
                // the wheel sits at the origin: hub at x = 0, z = 0
                float3 hubP = 0.5f * (new float3(def.nodes[wd.axleInner].p[0], def.nodes[wd.axleInner].p[1], def.nodes[wd.axleInner].p[2]) +
                                      new float3(def.nodes[wd.axleOuter].p[0], def.nodes[wd.axleOuter].p[1], def.nodes[wd.axleOuter].p[2]));
                c.p[0] -= hubP.x;
                c.p[2] -= hubP.z;
                map[i] = nodes.Count;
                nodes.Add(c);
            }
            var beams = new List<BeamDef>();
            foreach (var bd in def.beams)
                if (map.TryGetValue(bd.a, out int a) && map.TryGetValue(bd.b, out int b))
                    beams.Add(new BeamDef { a = a, b = b, type = bd.type, mat = bd.mat, bg = bd.bg, bgt = bd.bgt, pre = bd.pre, hydro = bd.hydro, hf = bd.hf });
            var triMap = new Dictionary<int, int>();
            var tris = new List<TriDef>();
            for (int t = 0; t < def.triangles.Length; t++)
            {
                var td = def.triangles[t];
                if (map.TryGetValue(td.a, out int a) && map.TryGetValue(td.b, out int b) && map.TryGetValue(td.c, out int c))
                {
                    triMap[t] = tris.Count;
                    tris.Add(new TriDef { a = a, b = b, c = c, type = td.type, group = td.group, bg = td.bg, drag = td.drag, lift = td.lift });
                }
            }
            var pgs = new List<PressureGroupDef>();
            foreach (var pg in def.pressureGroups)
                if (pg.wheel == wheelName)
                {
                    var ti = new List<int>();
                    foreach (int t in pg.tris)
                        ti.Add(triMap[t]);
                    pgs.Add(new PressureGroupDef { name = pg.name, tris = ti.ToArray(), pressure = pg.pressure, wheel = pg.wheel });
                }
            var hinges = new List<HingeDef>();
            foreach (var h in def.hinges)
                if (map.ContainsKey(h.n[0]) && map.ContainsKey(h.n[1]) && map.ContainsKey(h.n[2]) && map.ContainsKey(h.n[3]))
                    hinges.Add(new HingeDef { n = new[] { map[h.n[0]], map[h.n[1]], map[h.n[2]], map[h.n[3]] }, mat = h.mat });
            var dgs = new List<DampGroupDef>();
            foreach (var dg in def.dampGroups)
            {
                bool all = dg.nodes.Length > 0;
                foreach (int n in dg.nodes)
                    all &= map.ContainsKey(n);
                if (!all)
                    continue;
                var ids = new int[dg.nodes.Length];
                for (int k = 0; k < ids.Length; k++)
                    ids[k] = map[dg.nodes[k]];
                dgs.Add(new DampGroupDef { name = dg.name, nodes = ids, mat = dg.mat, bg = dg.bg, nodeBg = dg.nodeBg, reference = "", refBg = Array.Empty<string>() });
            }
            var rig = new VehicleDef
            {
                format = "hellcat-softbody", version = 1, name = $"tire_{wheelName}", units = def.units,
                nodes = nodes.ToArray(), beams = beams.ToArray(), triangles = tris.ToArray(), pressureGroups = pgs.ToArray(),
                hinges = hinges.ToArray(), dampGroups = dgs.ToArray(),
                parts = new[] { new PartDef { name = part, nodes = new int[0], visuals = Array.Empty<string>() } },
            };
            VehicleDef.Normalize(rig);
            var world = new SoftBodyWorld(prm) { trackEnergy = false, forceSingleThread = true };
            int bi = world.AddBody(rig.name, rig, prm, float3.zero, quaternion.identity, float3.zero, false);
            world.bodies[bi].spawnClearance = clearance;
            world.Build(Ground());
            var hubIds = new List<int> { map[wd.axleInner], map[wd.axleOuter] };
            foreach (var kv in map)
                if (!rimSet.Contains(kv.Key) && !treadSet.Contains(kv.Key) && kv.Key != wd.axleInner && kv.Key != wd.axleOuter)
                    hubIds.Add(kv.Value);
            var rimIds = new List<int>();
            foreach (int n in wd.rim)
                rimIds.Add(map[n]);
            var trIds = new List<int>();
            foreach (int n in wd.tread)
                trIds.Add(map[n]);
            return new TireRig(world, hubIds.ToArray(), rimIds.ToArray(), trIds.ToArray(), kinematicRim);
        }

        /// <summary>Spins the free rim and tread up to rolling at the spindle speed (no spin-up transient).</summary>
        public void SetRolling(double3 vel, double omega)
        {
            velocity = vel;
            double3 axis = new double3(math.cos(yaw), 0, -math.sin(yaw));
            foreach (int n in rim)
                if (w.invMass[n] > 0f)
                    w.vel[n] = (float3)(vel + math.cross(axis * omega, (double3)w.pos[n] - centre));
            foreach (int n in tread)
                w.vel[n] = (float3)(vel + math.cross(axis * omega, (double3)w.pos[n] - centre));
            spinRate = omega;
        }

        /// <summary>Writes the kinematic spindle (and rim) for the current centre, yaw and spin; velocities included.</summary>
        void Place()
        {
            var rotYaw = RotY(yaw);
            double3 axis = math.mul(rotYaw, new double3(1, 0, 0));
            for (int k = 0; k < hub.Length; k++)
            {
                double3 rr = math.mul(rotYaw, hubRef[k]);
                w.pos[hub[k]] = (float3)(centre + rr);
                w.vel[hub[k]] = (float3)velocity;
            }
            if (kinematicRim)
            {
                // rim spin about the axle: positive omega = rolling forward along the heading (top moving forward)
                var rotSpin = RotX(spinAngle);
                for (int k = 0; k < rim.Length; k++)
                {
                    double3 rr = math.mul(rotYaw, math.mul(rotSpin, rimRef[k]));
                    w.pos[rim[k]] = (float3)(centre + rr);
                    w.vel[rim[k]] = (float3)(velocity + math.cross(axis * spinRate, rr));
                }
            }
        }

        /// <summary>Rotation about +y (heading +z turns towards +x for a positive angle).</summary>
        static double3x3 RotY(double a)
        {
            double c = math.cos(a), s = math.sin(a);
            return new double3x3(c, 0, s, 0, 1, 0, -s, 0, c);
        }

        /// <summary>Rotation about +x (the top of a wheel moves towards +z for a positive angle).</summary>
        static double3x3 RotX(double a)
        {
            double c = math.cos(a), s = math.sin(a);
            return new double3x3(1, 0, 0, 0, c, -s, 0, s, c);
        }

        /// <summary>One substep with the spindle moved by its velocity first.</summary>
        public void Step()
        {
            double dt = w.dt;
            centre += velocity * dt;
            spinAngle += spinRate * dt;
            Place();
            if (w.StepsTaken % 20 == 0)
                w.UpdateNearLists(0.05f);
            w.Step(1);
            time += dt;
        }

        public void Begin()
        {
            Place();
            w.UpdateNearLists(0.05f);
        }

        /// <summary>Mean contact force (world frame) and aligning moment about the vertical through the spindle over the
        /// steps since the last call (from the accumulated contact impulses), then clears the accumulator.</summary>
        public double3 Force(double seconds, out double mz)
        {
            double3 f = double3.zero;
            mz = 0.0;
            var b = w.bodies[0];
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
            {
                double3 j = (double3)w.contactImp[i];
                if (math.lengthsq(j) == 0.0)
                    continue;
                f += j;
                double3 r = (double3)w.pos[i] - centre;
                mz += r.z * j.x - r.x * j.z;   // (r x j).y with x right, y up, z forward
            }
            w.ClearContactImp();
            mz /= seconds;
            return f / seconds;
        }

        /// <summary>Wheel spin rate about the axle (least squares of the rim nodes), positive rolling forward.</summary>
        public double Omega()
        {
            double3 axis = new double3(math.cos(yaw), 0, -math.sin(yaw));
            double3 c = double3.zero, vm = double3.zero;
            foreach (int n in rim) { c += (double3)w.pos[n]; vm += (double3)w.vel[n]; }
            c /= rim.Length;
            vm /= rim.Length;
            double num = 0, den = 0;
            foreach (int n in rim)
            {
                double3 r = (double3)w.pos[n] - c;
                r -= math.dot(r, axis) * axis;
                num += math.dot(math.cross(r, (double3)w.vel[n] - vm), axis);
                den += math.lengthsq(r);
            }
            return den > 0 ? num / den : 0.0;
        }

        public double CavityVolume() => w.pressureState[pressureGroup].volume;
        public double GaugePressure() => w.pressureState[pressureGroup].pAbs - w.pressureGroups[pressureGroup].pAtm;
        public double AbsPressure() => w.pressureState[pressureGroup].pAbs;
        public double Gas() => w.pressureState[pressureGroup].gas;

        /// <summary>Lowest tread node above the ground plane (m).</summary>
        public double LowestTread()
        {
            double y = double.MaxValue;
            foreach (int t in tread)
                y = math.min(y, w.pos[t].y);
            return y;
        }

        /// <summary>Mean radius of the tread nodes from the spindle axis (m).</summary>
        public double TreadRadius()
        {
            double3 axis = new double3(math.cos(yaw), 0, -math.sin(yaw));
            double s = 0;
            foreach (int t in tread)
            {
                double3 d = (double3)w.pos[t] - centre;
                d -= math.dot(d, axis) * axis;
                s += math.length(d);
            }
            return s / tread.Length;
        }

        /// <summary>Sets the gas content to a gauge pressure at the current cavity volume (inflate / deflate).</summary>
        public void SetGauge(double gauge)
        {
            var st = w.pressureState[pressureGroup];
            var pg = w.pressureGroups[pressureGroup];
            st.gas = (float)((gauge + pg.pAtm) * math.max(st.volume, pg.minVolume));
            w.pressureState[pressureGroup] = st;
        }
    }
}
