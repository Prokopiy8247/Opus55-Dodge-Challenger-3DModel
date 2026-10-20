using System;
using System.Collections.Generic;
using Hellcat.Sim.Data;
using Hellcat.Sim.Vehicle;
using Unity.Mathematics;
using static Hellcat.Sim.Validation.ValidationSuite;

namespace Hellcat.Sim.Validation
{
    /// <summary>Attitude and motion of the car body (cabin floor frame) for the dynamics tests.</summary>
    public struct CarFrame
    {
        public double3 com, vel;            // centre of mass (m), velocity (m/s)
        public double3 forward, right, up;  // unit axes of the cabin floor
        public double heading;              // rad, atan2(forward.x, forward.z)
        public double rollDeg;              // right side down positive
        public double pitchDeg;             // nose down positive
        public double speed;                // m/s along forward
        public double lateralVel;           // m/s along right
        public double3 rearAxle, frontAxle; // axle centres (m)
    }

    /// <summary>Probes of a Hellcat body: cabin frame (polar decomposition of the floor nodes against the model),
    /// road-wheel angles, wheel slip, axle positions.</summary>
    public sealed class CarProbe
    {
        readonly SoftBodyWorld w;
        readonly int bi;
        readonly int[] floor;            // global node indices of the cabin floor (sill, floor, tunnel)
        readonly double3[] floorModel;   // model positions minus their centroid
        readonly double3 floorCentroid;  // model centroid of the floor nodes
        readonly SoftBodyWorld.Body b;

        public CarProbe(SoftBodyWorld w, int bi)
        {
            this.w = w;
            this.bi = bi;
            b = w.bodies[bi];
            var ids = new List<int>();
            for (int i = 0; i < b.nodeCount; i++)
            {
                var nd = b.def.nodes[i];
                if (nd.part == "body" && (nd.name.StartsWith("sill") || nd.name.StartsWith("floor") || nd.name.StartsWith("tunnel")))
                    ids.Add(i);
            }
            if (ids.Count < 4)
                for (int i = 0; i < b.nodeCount; i++)
                    if (b.def.nodes[i].part == "body")
                        ids.Add(i);
            floor = new int[ids.Count];
            floorModel = new double3[ids.Count];
            double3 c = double3.zero;
            for (int k = 0; k < ids.Count; k++)
            {
                var p = b.def.nodes[ids[k]].p;
                floorModel[k] = new double3(p[0], p[1], p[2]);
                c += floorModel[k];
                floor[k] = b.nodeStart + ids[k];
            }
            c /= ids.Count;
            for (int k = 0; k < ids.Count; k++)
                floorModel[k] -= c;
            floorCentroid = c;
        }

        /// <summary>Rigid pose of the cabin floor: the rotation from the model and where the model origin is now (the
        /// pose an undeformed car would have; reset to a safe position, repair in place, deformation displays).</summary>
        public double3x3 Pose(out double3 origin)
        {
            var rot = Rotation(out double3 centroid);
            origin = centroid - math.mul(rot, floorCentroid);
            return rot;
        }

        /// <summary>RMS distance of the floor nodes from their rigid fit (m): how far the cabin floor is bent.</summary>
        public double FloorResidual()
        {
            var rot = Rotation(out double3 centroid);
            double sum = 0.0;
            for (int k = 0; k < floor.Length; k++)
                sum += math.lengthsq((double3)w.pos[floor[k]] - centroid - math.mul(rot, floorModel[k]));
            return math.sqrt(sum / floor.Length);
        }

        /// <summary>Rotation of the cabin floor from the model to now: the orthogonal factor of sum q_i p0_i^T (Higham's
        /// iteration X = (X + X^-T) / 2), so a rigid floor gives its exact attitude.</summary>
        public double3x3 Rotation(out double3 centroid)
        {
            centroid = double3.zero;
            foreach (int n in floor)
                centroid += (double3)w.pos[n];
            centroid /= floor.Length;
            var a = double3x3.zero;
            for (int k = 0; k < floor.Length; k++)
            {
                double3 q = (double3)w.pos[floor[k]] - centroid;
                double3 p = floorModel[k];
                a += new double3x3(q.x * p.x, q.x * p.y, q.x * p.z, q.y * p.x, q.y * p.y, q.y * p.z, q.z * p.x, q.z * p.y, q.z * p.z);
            }
            var x = a;
            for (int it = 0; it < 30; it++)
            {
                var next = 0.5 * (x + math.transpose(math.inverse(x)));
                double d = 0;
                for (int r = 0; r < 3; r++)
                    d += math.lengthsq(next[r] - x[r]);
                x = next;
                if (d < 1e-24)
                    break;
            }
            return x;
        }

        public CarFrame Frame()
        {
            var f = new CarFrame();
            var rot = Rotation(out _);
            f.forward = math.normalize(math.mul(rot, new double3(0, 0, 1)));
            f.right = math.normalize(math.mul(rot, new double3(1, 0, 0)));
            f.up = math.normalize(math.mul(rot, new double3(0, 1, 0)));
            f.heading = math.atan2(f.forward.x, f.forward.z);
            f.rollDeg = math.degrees(math.asin(math.clamp(-f.right.y, -1.0, 1.0)));
            f.pitchDeg = math.degrees(math.asin(math.clamp(-f.forward.y, -1.0, 1.0)));
            double mt = 0.0;
            double3 mp = double3.zero, mv = double3.zero;
            for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
            {
                float im = w.invMass[i];
                if (im <= 0f)
                    continue;
                double m = 1.0 / im;
                mt += m;
                mp += m * (double3)w.pos[i];
                mv += m * (double3)w.vel[i];
            }
            f.com = mp / mt;
            f.vel = mv / mt;
            f.speed = math.dot(f.vel, f.forward);
            f.lateralVel = math.dot(f.vel, f.right);
            double3 fr = double3.zero, rr = double3.zero;
            int nf = 0, nr = 0;
            for (int k = 0; k < b.wheelCount; k++)
            {
                var wd = b.def.wheels[k];
                double3 hub = 0.5 * ((double3)w.pos[b.nodeStart + wd.axleInner] + (double3)w.pos[b.nodeStart + wd.axleOuter]);
                if (wd.steered != 0) { fr += hub; nf++; } else { rr += hub; nr++; }
            }
            f.frontAxle = nf > 0 ? fr / nf : f.com;
            f.rearAxle = nr > 0 ? rr / nr : f.com;
            return f;
        }

        /// <summary>Road-wheel angle of a wheel relative to the cabin (deg, steering right positive).</summary>
        public double RoadWheelDeg(int wheel, in CarFrame f)
        {
            var wd = b.def.wheels[wheel];
            var ws = w.wheels[b.wheelStart + wheel];
            double3 axis = ws.axisSign * math.normalize((double3)w.pos[b.nodeStart + wd.axleOuter] - (double3)w.pos[b.nodeStart + wd.axleInner]);
            double3 heading = math.normalize(math.cross(axis, f.up));
            return math.degrees(math.atan2(math.dot(heading, f.right), math.dot(heading, f.forward)));
        }

        /// <summary>Camber of a wheel relative to the cabin (deg, top of the wheel outward positive).</summary>
        public double CamberDeg(int wheel, in CarFrame f)
        {
            var wd = b.def.wheels[wheel];
            double3 outward = math.normalize((double3)w.pos[b.nodeStart + wd.axleOuter] - (double3)w.pos[b.nodeStart + wd.axleInner]);
            return -math.degrees(math.asin(math.clamp(math.dot(outward, f.up), -1.0, 1.0)));
        }

        /// <summary>Slip angle of a wheel (deg): hub velocity against the wheel heading, positive to the right.</summary>
        public double SlipAngleDeg(int wheel, in CarFrame f)
        {
            var wd = b.def.wheels[wheel];
            var ws = w.wheels[b.wheelStart + wheel];
            double3 axis = ws.axisSign * math.normalize((double3)w.pos[b.nodeStart + wd.axleOuter] - (double3)w.pos[b.nodeStart + wd.axleInner]);
            double3 heading = math.normalize(math.cross(axis, f.up));
            double3 v = 0.5 * ((double3)w.vel[b.nodeStart + wd.axleInner] + (double3)w.vel[b.nodeStart + wd.axleOuter]);
            return math.degrees(math.atan2(math.dot(v, axis), math.dot(v, heading)));
        }

        public int WheelIndex(string name)
        {
            for (int k = 0; k < b.wheelCount; k++)
                if (b.def.wheels[k].name == name)
                    return k;
            throw new ArgumentException($"no wheel {name}");
        }

        /// <summary>Hub height above its value at the model (m) per wheel.</summary>
        public double HubY(int wheel)
        {
            var wd = b.def.wheels[wheel];
            return 0.5 * (w.pos[b.nodeStart + wd.axleInner].y + w.pos[b.nodeStart + wd.axleOuter].y);
        }

        /// <summary>Contact impulse on a wheel's tread nodes since the last ClearContactImp (N s, world).</summary>
        public double3 TreadImpulse(int wheel)
        {
            var wd = b.def.wheels[wheel];
            double3 sum = double3.zero;
            foreach (int t in wd.tread)
                sum += (double3)w.contactImp[b.nodeStart + t];
            return sum;
        }

        /// <summary>Lowest tread node height of a wheel (m): above the ground means the wheel is off it.</summary>
        public double LowestTread(int wheel)
        {
            var wd = b.def.wheels[wheel];
            double y = double.MaxValue;
            foreach (int t in wd.tread)
                y = math.min(y, w.pos[b.nodeStart + t].y);
            return y;
        }
    }

    /// <summary>Path on the ground plane (x, z) as a dense polyline with arc length; open or closed.</summary>
    public sealed class PolyPath
    {
        public readonly List<double2> pts = new List<double2>();
        public readonly List<double> s = new List<double>();
        public bool closed;
        public double Length => s[s.Count - 1];

        public void Add(double2 p)
        {
            if (pts.Count > 0)
            {
                double d = math.distance(p, pts[pts.Count - 1]);
                if (d < 1e-6)
                    return;
                s.Add(s[s.Count - 1] + d);
            }
            else
            {
                s.Add(0.0);
            }
            pts.Add(p);
        }

        public static PolyPath FromFunction(Func<double, double2> f, double t0, double t1, int n, bool closed = false)
        {
            var path = new PolyPath { closed = closed };
            for (int i = 0; i <= n; i++)
                path.Add(f(t0 + (t1 - t0) * i / n));
            return path;
        }

        /// <summary>Straight line from origin along a unit direction (x, z).</summary>
        public static PolyPath Line(double2 origin, double2 dir, double length) =>
            FromFunction(t => origin + dir * t, -20.0, length, (int)math.ceil((length + 20.0) / 0.5));

        /// <summary>Circle through centre + radius (cos a, sin a) in (x, z): increasing a runs counter-clockwise seen from
        /// above with x right and z up on the page, which is a left turn for the car (Unity: x right, z forward).</summary>
        public static PolyPath Circle(double2 centre, double radius, double startAngle, bool leftTurn) =>
            FromFunction(t => centre + radius * new double2(math.cos(startAngle + (leftTurn ? t : -t)), math.sin(startAngle + (leftTurn ? t : -t))),
                0.0, 2.0 * math.PI, (int)math.ceil(2.0 * math.PI * radius / 0.25), true);

        /// <summary>Figure eight of two circles touching at the origin; the car enters along +z (left circle first).</summary>
        public static PolyPath FigureEight(double radius)
        {
            var path = new PolyPath { closed = true };
            int n = (int)math.ceil(2.0 * math.PI * radius / 0.25);
            // left loop: centre (-R, 0), start at the origin heading +z (counter-clockwise from above is a left turn
            // in Unity's left-handed frame: x right, z forward)
            for (int i = 0; i < n; i++)
            {
                double a = 2.0 * math.PI * i / n;
                path.Add(new double2(-radius + radius * math.cos(a), radius * math.sin(a)));
            }
            for (int i = 0; i <= n; i++)
            {
                double a = 2.0 * math.PI * i / n;
                path.Add(new double2(radius - radius * math.cos(a), radius * math.sin(a)));
            }
            return path;
        }

        /// <summary>Slalom along +z from z0: lateral offset amplitude * sin(pi (z - z0) / spacing) over count gates,
        /// straight before and after.</summary>
        public static PolyPath Slalom(double z0, double spacing, double amplitude, int count, double runIn, double runOut)
        {
            double zEnd = z0 + spacing * count;
            return FromFunction(z =>
            {
                if (z < z0 || z > zEnd)
                    return new double2(0.0, z);
                return new double2(amplitude * math.sin(math.PI * (z - z0) / spacing), z);
            }, z0 - runIn, zEnd + runOut, (int)math.ceil((runIn + runOut + spacing * count) / 0.25));
        }

        /// <summary>Lane change along +z: offset 0 before zStart, a raised-cosine transition of the given length, then
        /// offset (x) after.</summary>
        public static PolyPath LaneChange(double zStart, double length, double offset, double runIn, double runOut) =>
            FromFunction(z =>
            {
                double u = math.saturate((z - zStart) / length);
                return new double2(offset * 0.5 * (1.0 - math.cos(math.PI * u)), z);
            }, zStart - runIn, zStart + length + runOut, (int)math.ceil((runIn + runOut + length) / 0.25));

        /// <summary>Arc length of the closest point, searched around a hint index (monotonic progress).</summary>
        public double Project(double2 p, ref int hint, out double lateral)
        {
            int n = pts.Count;
            int best = hint;
            double bestD = double.MaxValue;
            int lo = closed ? hint - 200 : math.max(hint - 200, 0);
            int hi = closed ? hint + 400 : math.min(hint + 400, n - 2);
            for (int k = lo; k <= hi; k++)
            {
                int i = ((k % (n - 1)) + (n - 1)) % (n - 1);
                double d = math.distancesq(p, pts[i]);
                if (d < bestD)
                {
                    bestD = d;
                    best = i;
                }
            }
            hint = best;
            int j = math.min(best + 1, n - 1);
            double2 a = pts[best], b2 = pts[j];
            double2 seg = b2 - a;
            double len = math.length(seg);
            double t = len > 1e-9 ? math.clamp(math.dot(p - a, seg) / (len * len), 0.0, 1.0) : 0.0;
            double2 q = a + seg * t;
            double2 dir = len > 1e-9 ? seg / len : new double2(0, 1);
            // lateral offset: positive when p is to the right of the path direction (x right, z forward: right of
            // (dx, dz) is (dz, -dx))
            lateral = math.dot(p - q, new double2(dir.y, -dir.x));
            return s[best] + t * len;
        }

        public double2 At(double arc)
        {
            double total = Length;
            if (closed)
                arc = arc - total * math.floor(arc / total);
            else
                arc = math.clamp(arc, 0.0, total);
            int lo = 0, hi = s.Count - 1;
            while (hi - lo > 1)
            {
                int mid = (lo + hi) >> 1;
                if (s[mid] <= arc) lo = mid; else hi = mid;
            }
            double seg = s[hi] - s[lo];
            double t = seg > 1e-9 ? (arc - s[lo]) / seg : 0.0;
            return math.lerp(pts[lo], pts[hi], t);
        }

        /// <summary>Path curvature at an arc length (1/m, positive turning right).</summary>
        public double Curvature(double arc)
        {
            double2 a = At(arc - 1.0), m = At(arc), c = At(arc + 1.0);
            double2 d1 = m - a, d2 = c - m;
            double cross = d1.y * d2.x - d1.x * d2.y;   // right turn positive in (x right, z forward)
            double l = math.length(d1) * math.length(d2) * math.length(c - a);
            return l > 1e-9 ? 2.0 * cross / l : 0.0;
        }
    }

    /// <summary>
    /// Driver robot for the dynamics tests: PI speed controller (throttle / brake) and a pure-pursuit path follower
    /// on the rear axle with a cross-track integral, inverting the speed-sensitive steering reduction of the control
    /// job. Runs once per control chunk.
    /// </summary>
    public sealed class DriverRobot
    {
        public PolyPath path;
        public Func<double, double, double> targetSpeed;   // (time, arc length) -> m/s
        public double kp = 0.35, ki = 0.25, brakeGain = 0.35;
        public double lookMin = 6.0, lookGain = 0.55, lookMax = 40.0;
        // at speed: the look-ahead gain rises to lookGainHigh at lookHighSpeed (a longer preview lowers the lateral gain),
        // the measured yaw rate against the commanded path curvature damps the yaw response, the command is filtered
        public double lookGainHigh = 0.55, lookHighSpeed = 60.0, lookMaxHigh = 40.0;
        public double kYaw = 0.15;             // rad of road-wheel angle per rad/s of yaw-rate error (X16: 0.19 m path
                                               // offset over 45 s at 282 km/h; without it the integral weaves)
        public double steerTau = 0.0;          // s, first-order filter of the road-wheel angle command
        public double kCross = 0.012;          // rad per m*s of the cross-track integral (time constant ~5 s on the skidpad)
        public double crossSpeedExp = 1.0;     // the integral gain falls as (15 m/s / v)^exp above 15 m/s (D-066, X16 on the
                                               // P4 car: exp 1 holds the lane at 282 km/h within 0.39 m, exp 2 drifted 0.6-1.2 m
                                               // on a steady pull; exp 1 with a 0.1 s command filter weaves into a slide)
        public double wheelbase = 2.95;
        public double lockDeg = 33.0;          // mean road-wheel angle at full input (measured in T11)
        public float reductionStart = 15f, reductionAt60 = 0.35f;
        public int gear = DriverInput.Drive;
        public int flags = DriverInput.FlagTc;  // a driver with traction control on (tests that want it off say so)
        public bool steerOnly;                 // pedals from pedalOverride
        public Func<double, CarFrame, DriverInput> pedalOverride;
        public double curveFade = 1.0;         // s: the curve integral fades on straights
        double integ, cross, crossCurve;       // speed integral; cross-track integrals on straights and in curves
        int turnSign;                          // side of the last curve (sign of the path curvature ahead), 0 before any
        double hPrev = double.NaN, tPrev, deltaF;
        int hint;
        public double arc, lateral;            // progress along the path and offset (rear axle, m)

        public DriverRobot(SimParamsDef prm)
        {
            reductionStart = prm.steering.speedReductionStart;
            reductionAt60 = prm.steering.speedReductionAt60;
            lockDeg = prm.steering.wheelLockDeg;
        }

        public DriverInput Control(double t, double dt, in CarFrame f)
        {
            var inp = new DriverInput { gear = gear, flags = flags };
            // path: pure pursuit from the rear axle
            if (path != null)
            {
                double2 rear = new double2(f.rearAxle.x, f.rearAxle.z);
                arc = path.Project(rear, ref hint, out lateral);
                double v = math.max(f.speed, 0.0);
                double hi = math.saturate((v - 30.0) / math.max(lookHighSpeed - 30.0, 1.0));
                double look = math.clamp(math.lerp(lookGain, lookGainHigh, hi) * v, lookMin, math.lerp(lookMax, lookMaxHigh, hi));
                double2 target = path.At(arc + look);
                double2 d = target - rear;
                double2 fw = math.normalize(new double2(f.forward.x, f.forward.z));
                double2 rt = new double2(fw.y, -fw.x);
                double alpha = math.atan2(math.dot(d, rt), math.dot(d, fw));
                double ld = math.max(math.length(d), 1e-3);
                double delta = math.atan(2.0 * wheelbase * math.sin(alpha) / ld);
                // cross-track integral (the steady understeer offset on circles); its gain falls with the speed squared
                // above 15 m/s: on a straight at speed it only adds phase lag (a 5 s weave grew into a spin at 250 km/h)
                double kc = kCross * math.min(1.0, math.pow(15.0 / math.max(v, 1.0), crossSpeedExp));
                // in curves the integral is the understeer offset: it changes side with the turn and fades on straights;
                // on straights a separate integral takes a steady pull
                double kAhead = path.Curvature(arc + 0.5 * look);
                int sideNow = kAhead > 1.0 / 150.0 ? 1 : kAhead < -1.0 / 150.0 ? -1 : 0;
                if (sideNow != 0)
                {
                    if (turnSign != 0 && sideNow != turnSign)
                        crossCurve = -crossCurve;
                    turnSign = sideNow;
                    crossCurve = math.clamp(crossCurve + lateral * dt, -50.0, 50.0);
                }
                else
                {
                    crossCurve *= math.exp(-dt / math.max(curveFade, 1e-3));
                    cross = math.clamp(cross + lateral * dt, -50.0, 50.0);
                }
                delta -= kc * (cross + crossCurve);
                if (kYaw > 0.0 && !double.IsNaN(hPrev) && t > tPrev)
                {
                    double yawRate = Dyn.WrapRad(f.heading - hPrev) / (t - tPrev);
                    delta -= kYaw * (yawRate - 2.0 * math.sin(alpha) / ld * v);
                }
                hPrev = f.heading;
                tPrev = t;
                deltaF = steerTau > 0.0 ? deltaF + (delta - deltaF) * math.saturate(dt / steerTau) : delta;
                delta = deltaF;
                double red = 1.0;
                if (v > reductionStart)
                    red = math.lerp(1.0, reductionAt60, math.saturate((v - reductionStart) / math.max(60.0 - reductionStart, 1.0)));
                inp.steer = (float)math.clamp(math.degrees(delta) / (lockDeg * red), -1.0, 1.0);
            }
            if (pedalOverride != null)
            {
                var p = pedalOverride(t, f);
                inp.throttle = p.throttle;
                inp.brake = p.brake;
                inp.handbrake = p.handbrake;
                inp.gear = p.gear;
                inp.flags = p.flags;
                if (path == null)
                    inp.steer = p.steer;
                return inp;
            }
            double vt = targetSpeed != null ? targetSpeed(t, arc) : 0.0;
            double e = vt - f.speed;
            integ = math.clamp(integ + ki * e * dt, -0.6, 0.8);
            double u = kp * e + integ;
            if (u >= 0.0)
            {
                inp.throttle = (float)math.saturate(u);
            }
            else
            {
                inp.brake = (float)math.saturate(-u * brakeGain);
                if (integ > 0.0)
                    integ = 0.0;   // no wind-up against the brake
            }
            return inp;
        }
    }

    /// <summary>Shared builders and loops of the dynamics tests (T9-T14).</summary>
    public static class Dyn
    {
        public const double G = 9.81;

        /// <summary>The Hellcat on a static world, optionally rotated, settled at rest (D-037) with the given input.</summary>
        public static SoftBodyWorld Car(ValidationContext ctx, StaticWorldBuilder statics, float3 position, float headingDeg,
            Action<SimParamsDef> tweak = null, bool settle = true, DriverInput? settleInput = null, Action<SoftBodyWorld> addMore = null,
            Action<VehicleDef> defTweak = null)
        {
            var (def, prm) = LoadHellcat(ctx);
            tweak?.Invoke(prm);
            defTweak?.Invoke(def);
            var w = new SoftBodyWorld(prm) { trackEnergy = false };
            int bi = w.AddBody("hellcat", def, prm, position, quaternion.RotateY(math.radians(headingDeg)), float3.zero, true);
            w.bodies[bi].spawnClearance = 0.01f;
            addMore?.Invoke(w);
            w.Build(statics ?? Ground());
            if (settle)
            {
                w.SetInput(w.bodies[bi].vehicleIndex, settleInput ?? new DriverInput { brake = 1f, handbrake = 1f, gear = 0 });
                w.Settle(bi);
            }
            return w;
        }

        /// <summary>Settled car launched at a speed along its heading (rolling wheels, gear for the speed).</summary>
        public static void LaunchAt(SoftBodyWorld w, double speed)
        {
            var probe = new CarProbe(w, 0);
            var f = probe.Frame();
            w.Launch(0, (float3)(f.forward * speed));
        }

        /// <summary>Runs the car with a controller called every chunk; the sample callback returns false to stop.</summary>
        public static void Drive(SoftBodyWorld w, double seconds, int chunk, Func<double, CarFrame, DriverInput> control,
            Func<double, CarFrame, bool> sample, CarProbe probe = null)
        {
            probe ??= new CarProbe(w, 0);
            var b = w.bodies[0];
            long steps = (long)math.round(seconds / w.dt);
            long t0 = w.StepsTaken;
            double t = 0.0;
            var f = probe.Frame();
            while (w.StepsTaken - t0 < steps)
            {
                w.SetInput(b.vehicleIndex, control(t, f));
                w.UpdateNearLists(chunk * w.dt + 0.05f);
                w.Step(chunk);
                t = (w.StepsTaken - t0) * (double)w.dt;
                f = probe.Frame();
                if (!sample(t, f))
                    break;
            }
        }

        public static double WrapRad(double a)
        {
            while (a > math.PI) a -= 2.0 * math.PI;
            while (a < -math.PI) a += 2.0 * math.PI;
            return a;
        }

        public static double WrapDeg(double a) => a - 360.0 * math.floor((a + 180.0) / 360.0);

        /// <summary>Linear least-squares slope and intercept.</summary>
        public static (double slope, double intercept, double r2) Fit(IList<double> x, IList<double> y)
        {
            int n = x.Count;
            double sx = 0, sy = 0, sxx = 0, sxy = 0, syy = 0;
            for (int i = 0; i < n; i++)
            {
                sx += x[i]; sy += y[i]; sxx += x[i] * x[i]; sxy += x[i] * y[i]; syy += y[i] * y[i];
            }
            double den = n * sxx - sx * sx;
            if (n < 2 || math.abs(den) < 1e-18)
                return (double.NaN, double.NaN, double.NaN);
            double slope = (n * sxy - sx * sy) / den;
            double icpt = (sy - slope * sx) / n;
            double ssTot = syy - sy * sy / n, ssRes = 0;
            for (int i = 0; i < n; i++)
            {
                double e = y[i] - (slope * x[i] + icpt);
                ssRes += e * e;
            }
            return (slope, icpt, ssTot > 0 ? 1.0 - ssRes / ssTot : 1.0);
        }
    }
}
