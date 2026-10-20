using Unity.Burst;
using Unity.Collections;
using Unity.Collections.LowLevel.Unsafe;
using Unity.Jobs;
using Unity.Mathematics;

namespace Hellcat.Sim
{
    // Per-substep pipeline (see SoftBodyWorld.ScheduleSubsteps):
    //   SerialPhaseJob (break groups, clock, vehicle control) -> BeamForceJob (parallel over beams)
    //   -> NodeIntegrateJob (parallel over nodes).
    // Every node gathers its forces in a fixed order (CSR lists sorted by element index), so the
    // result is bit-identical for any thread count (verified by the P0 benchmark).
    // Fields carry [NativeDisableContainerSafetyRestriction] because the same containers are
    // shared by several jobs that are always chained, and because SingleThreadStepJob embeds the
    // other jobs (container aliasing would otherwise be rejected by the safety system).

    [BurstCompile(FloatMode = FloatMode.Strict, DisableSafetyChecks = true)]
    public struct BeamForceJob : IJobParallelFor
    {
        public float dt;
        public int trackEnergy;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> pos;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> vel;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<BeamStatic> beams;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float> hydroInput;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float> spawnBlend;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float> pressureScale;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<DampGroupRigid> dampRigid; // wheel spin (D-044)
        [NativeDisableContainerSafetyRestriction] public NativeArray<float> rest;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float> yield;
        [NativeDisableContainerSafetyRestriction] public NativeArray<byte> relaxArmed;   // spring-back suppression (D-056)
        [NativeDisableContainerSafetyRestriction] public NativeArray<byte> broken;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float> plasticWork;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float> breakEnergy;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float> stress;
        [NativeDisableContainerSafetyRestriction] public NativeArray<double> dampEnergy;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> beamForce;
        [NativeDisableContainerSafetyRestriction] [NativeDisableParallelForRestriction] public NativeArray<byte> groupTrigger;
        public int tailBeamStart;                                                     // sleeping debris (D-098)
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> tailSleep;

        public void Execute(int i)
        {
            if (i >= tailBeamStart && tailSleep[0] != 0)
                return;
            BeamStatic s = beams[i];
            float r = rest[i], y = yield[i], pw = plasticWork[i], be = breakEnergy[i];
            byte br = broken[i], arm = relaxArmed[i];
            byte wasBroken = br;
            float h = s.hydro >= 0 ? hydroInput[s.hydro] : 0f;
            float pre = 0f, stiff = 1f;
            if (s.pressureGroup >= 0)
            {
                float inflation = pressureScale[s.pressureGroup];
                pre = s.pretension * inflation;
                stiff = 1f - s.inflationShare * (1f - inflation);
            }
            // D-044: a ring of a spinning wheel carries the hoop tension mu v^2 (rigid rotation of its group, previous
            // substep), under which the moving ring follows any shape without inertial forces (no centrifugal growth,
            // no impact where the tread turns from the round onto the flat contact patch)
            if (s.spinGroup >= 0)
            {
                DampGroupRigid rg = dampRigid[s.spinGroup];
                if (rg.valid != 0)
                    pre += s.spinCoef * (float)math.lengthsq(rg.w);
            }
            float3 f = BeamKernel.Compute(s, pos[s.a], pos[s.b], vel[s.a], vel[s.b], h, spawnBlend[s.body], pre, stiff,
                math.min(s.relax * dt, 1f), ref r, ref y, ref arm, ref br, ref pw, ref be, out float st, out byte trig, out float dp);
            beamForce[i] = f;
            stress[i] = st;
            if (trackEnergy != 0)
                dampEnergy[i] += (double)dp * dt;
            if (br != wasBroken)
            {
                broken[i] = br;
                breakEnergy[i] = be;
                if (trig != 0 && s.breakGroup >= 0)
                    groupTrigger[s.breakGroup] = 1; // benign race: every writer stores 1
            }
            else
            {
                rest[i] = r;
                yield[i] = y;
                relaxArmed[i] = arm;
                plasticWork[i] = pw;
            }
        }
    }

    [BurstCompile(FloatMode = FloatMode.Strict, DisableSafetyChecks = true)]
    public struct NodeIntegrateJob : IJobParallelFor
    {
        public StepParams prm;
        public int useDynamic;                // node-vs-triangle contact forces (ContactScatterJob) in dynForce
        public int trackEnergy;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> dynForce;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> dampForce;  // deformation damping (D-033)
        [NativeDisableContainerSafetyRestriction] public NativeArray<double> contactWork; // J, static + dynamic contact
        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> pos;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> vel;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float> invMass;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> flags;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> nodeBody;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> nodeCmat;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> beamAdjStart;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> beamAdjCode;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> beamForce;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> slotAdjStart;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> slotAdjIndex;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> slotForce;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> extForce;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> bodyAccel;  // per body (aerodynamic drag)
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<StaticPrimitive> prims;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float4> planes;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> nearStart;   // per body
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> nearCount;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> nearPrims;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<ContactMaterial> cmats;
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<SurfaceMaterial> surfaces;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> anchor;
        [NativeDisableContainerSafetyRestriction] public NativeArray<int> anchorPrim;
        [NativeDisableContainerSafetyRestriction] public NativeArray<byte> contactLatch;  // hard contact since a projection (D-055)
        [NativeDisableContainerSafetyRestriction] public NativeArray<float> contactFn;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float> contactSlip;
        [NativeDisableContainerSafetyRestriction] public NativeArray<int> contactSurface;
        [NativeDisableContainerSafetyRestriction] public NativeArray<float> frictionPower; // W dissipated by static friction
        [NativeDisableContainerSafetyRestriction] public NativeArray<float3> contactImp;   // contact impulse accumulated since the last ClearContactImp
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<float3> nodeLat;  // lateral friction axis (D-048), zero: isotropic
        public int tailNodeStart;                                                     // sleeping debris (D-098)
        [NativeDisableContainerSafetyRestriction] [ReadOnly] public NativeArray<int> tailSleep;

        public void Execute(int i)
        {
            if (i >= tailNodeStart && tailSleep[0] != 0)
                return;
            float im = invMass[i];
            if (im <= 0f)
                return;
            float m = 1f / im;
            float3 p = pos[i];
            float3 v = vel[i];

            int body = nodeBody[i];
            float3 f = (prm.gravity + bodyAccel[body]) * m + extForce[i] + dampForce[i];
            for (int k = beamAdjStart[i]; k < beamAdjStart[i + 1]; k++)
            {
                int code = beamAdjCode[k];
                float3 bf = beamForce[code >> 1];
                f += (code & 1) == 0 ? bf : -bf;
            }
            for (int k = slotAdjStart[i]; k < slotAdjStart[i + 1]; k++)
                f += slotForce[slotAdjIndex[k]];
            float3 fBase = f;
            if (useDynamic != 0)
                f += dynForce[i];

            float fnSum = 0f, slip = 0f, fricP = 0f;
            int surfId = -1;
            int fl = flags[i];
            int ns = nearStart[body], nc = nearCount[body];
            float3 anc = anchor[i];
            int ancPrim = anchorPrim[i];
            bool touching = false, keepAnchor = false;
            byte latch = contactLatch[i];
            if ((fl & NodeFlag.StaticCollision) != 0)
            {
                ContactMaterial cm = cmats[nodeCmat[i]];
                bool inZone = false;
                for (int k = 0; k < nc; k++)
                {
                    int pi = nearPrims[ns + k];
                    StaticPrimitive prim = prims[pi];
                    float s = StaticSdf.Distance(prim, planes, p, out float3 nrm);
                    if (s >= cm.bias)
                    {
                        // Hysteresis: a micro-separation (vibration at rest) keeps the stick point.
                        if (pi == ancPrim && s < 1.5f * cm.bias + 0.002f)
                            keepAnchor = true;
                        continue;
                    }
                    inZone = true;
                    // Hard contact (D-055): a node that was projected out of a solid stays on the projection until it
                    // leaves the zone. Its penalty spring sits at full depth after the projection without the node's
                    // motion having compressed it, and on unloading would hand back up to 1/2 k bias^2 that no work paid
                    // for (a 50 km/h wall impact gained ~140 kJ that way and the car flipped over its nose).
                    if (latch != 0)
                        continue;
                    SurfaceMaterial surf = surfaces[prim.surface];
                    float3 before = f;
                    float fn = ContactKernel.Apply(p, v, m, prm.dt, s, nrm, pi, cm, surf, nodeLat[i], ref anc, ref ancPrim, ref f, out float sl);
                    fricP += math.abs(math.dot(f - before - nrm * fn, v));
                    if (fn > fnSum)
                    {
                        surfId = prim.surface;
                        slip = sl;
                    }
                    fnSum += fn;
                    touching = true;
                }
                if (!inZone)
                    latch = 0;
            }
            if (!touching && !keepAnchor)
                ancPrim = -1;

            float3 vOld = v, pStart = p;
            v += f * (im * prm.dt);
            p += v * prm.dt;
            // work of the contact forces: their share of the kinetic energy change, f . (v_old + v_new) / 2 dt (with the
            // new velocity alone the ledger gained 1/2 |f|^2 dt^2 / m per step of a hard contact)
            if (trackEnergy != 0)
                contactWork[i] += (double)math.dot(f - fBase, 0.5f * (vOld + v)) * prm.dt;
            contactImp[i] += (f - fBase) * prm.dt;

            // Hard non-penetration for every colliding node (also one that entered a solid within this step).
            if ((fl & NodeFlag.StaticCollision) != 0)
            {
                ContactMaterial cm = cmats[nodeCmat[i]];
                for (int k = 0; k < nc; k++)
                {
                    StaticPrimitive prim = prims[nearPrims[ns + k]];
                    float s = StaticSdf.Distance(prim, planes, p, out float3 nrm);
                    if (s < 0f)
                    {
                        // thin-wall protection (D-055): out through the face the node was nearest at the start of the step
                        // (where it came in), not the face nearest to it now - a node the structure drove 10 cm into a
                        // 20 cm wall in one step left through the back face (T8 at 120 km/h)
                        float sOld = StaticSdf.Distance(prim, planes, pStart, out float3 nOld);
                        float sFace = sOld + math.dot(nOld, p - pStart);
                        if (sFace < 0f)
                        {
                            s = sFace;
                            nrm = nOld;
                        }
                        float3 vProj = v;
                        // the hard contact rubs with the compound's friction at the node's slip speed (D-048), like the
                        // penalty contact (with muSliding alone a tire lost ~10 % of its grip on the leading-edge impacts)
                        float vtp = math.length(v - math.dot(v, nrm) * nrm);
                        ContactKernel.Project(ref p, ref v, s, nrm, surfaces[prim.surface].frictionScale * ContactKernel.SlidingMu(cm, vtp));
                        // the projection is a hard impulse too: count it, so the contact accounting used by the
                        // friction validation is the momentum the node actually lost, not just the penalty force.
                        contactImp[i] += (v - vProj) * m;
                        if (trackEnergy != 0)
                            contactWork[i] += 0.5 * m * (math.lengthsq((double3)v) - math.lengthsq((double3)vProj));
                        if (cm.hardContact != 0)
                            latch = 1;
                    }
                }
            }

            float sp = math.length(v);
            if (!(sp <= prm.maxNodeSpeed)) // also catches NaN
                v = sp > 0f && math.isfinite(sp) ? v * (prm.maxNodeSpeed / sp) : float3.zero;

            pos[i] = p;
            vel[i] = v;
            anchor[i] = anc;
            anchorPrim[i] = ancPrim;
            contactLatch[i] = latch;
            contactFn[i] = fnSum;
            contactSlip[i] = slip;
            contactSurface[i] = surfId;
            frictionPower[i] = fricP;
        }
    }
}
