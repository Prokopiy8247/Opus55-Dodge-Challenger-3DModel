"""One-off (P3b, D-051): the alignment element's camber measured against a per-wheel reference axis - the steering axis of
a steered knuckle (lower to upper ball joint), up for the others - as the angle between the axle line and that axis minus
its model value: steering (rotation about the kingpin) leaves it unchanged, for up it is the plain camber of D-049."""
from pathlib import Path

ROOT = Path("Unity/HellcatSandbox/Assets/Sim")


def patch(path, pairs):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:120])
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")


patch("Vehicle/VehicleTypes.cs", [(
    """        public float travel0;                // m: hub height over the wind-up body nodes along the body's up at spawn""",
    """        public float travel0;                // m: hub height over the wind-up body nodes along the body's up at spawn
        public float3 kingpin;               // camber reference axis in model coordinates: the steering axis (lower to upper
                                             // ball joint) of a steered knuckle, up otherwise (D-051)
        public float kingpinPhi0;            // rad: model angle between the axle line and that axis, less the model camber""")])

patch("Core/SoftBodyWorld.cs", [(
    """                    ws.travel0 = hubM.y - bcM.y;
                    ws.side = hubM.x >= 0f ? 1f : -1f;""",
    """                    ws.travel0 = hubM.y - bcM.y;
                    ws.side = hubM.x >= 0f ? 1f : -1f;
                    // camber reference axis (D-051): steered knuckles measure the camber as the angle between the axle line
                    // and the steering axis, which steering does not change; phi0 makes it the plain camber at the model pose
                    float3 aM = math.normalizesafe(ModelPos(def, wd.axleOuter) - ModelPos(def, wd.axleInner), new float3(ws.side, 0f, 0f));
                    ws.kingpin = new float3(0f, 1f, 0f);
                    if (wd.steered != 0 && wd.kingpin != null && wd.kingpin.Length == 2)
                        ws.kingpin = math.normalizesafe(ModelPos(def, wd.kingpin[1]) - ModelPos(def, wd.kingpin[0]), ws.kingpin);
                    ws.kingpinPhi0 = math.acos(math.clamp(math.dot(aM, ws.kingpin), -1f, 1f)) + math.asin(math.clamp(aM.y, -1f, 1f));"""), (
    """            float3 bF = math.normalizesafe(sf / cf - sr / cr), bR = math.normalizesafe(sR / cR - sL / cL);
            float3 bU = math.normalizesafe(math.cross(bF, bR));
            if (math.lengthsq(bU) < 0.5f)
                return 0.0;
            double e = 0.0;""",
    """            float3 bF = math.normalizesafe(sf / cf - sr / cr), bR = math.normalizesafe(sR / cR - sL / cL);
            float3 bU = math.normalizesafe(math.cross(bF, bR));
            if (math.lengthsq(bU) < 0.5f)
                return 0.0;
            bR = math.cross(bU, bF);
            double e = 0.0;"""), (
    """                float toe = math.asin(math.clamp(math.dot(aOut, bF), -1f, 1f));
                float camber = -math.asin(math.clamp(math.dot(aOut, bU), -1f, 1f));
                double eC = camber - (ws.camberStatic + ws.camberGain * travel);""",
    """                float toe = math.asin(math.clamp(math.dot(aOut, bF), -1f, 1f));
                float3 kp = ws.kingpin.x * bR + ws.kingpin.y * bU + ws.kingpin.z * bF;
                float camber = math.acos(math.clamp(math.dot(aOut, kp), -1f, 1f)) - ws.kingpinPhi0;
                double eC = camber - (ws.camberStatic + ws.camberGain * travel);""")])

patch("Vehicle/VehicleControlJob.cs", [(
    """                // Alignment element (D-049): camber and toe of the axle line relative to the body frame, spring-dampers
                // towards static + gain x travel; toe-in about -side x up, camber (top out) about -side x forward. It acts on""",
    """                // Alignment element (D-049): camber and toe of the axle line relative to the body frame, spring-dampers
                // towards static + gain x travel; toe-in about -side x up, camber (top out) about -(axle x reference axis):
                // the reference axis is the steering axis of a steered knuckle (D-051: the camber is the angle between the
                // axle line and the kingpin, which steering leaves unchanged; no toe spring there, the toe is the rack's)
                // and up for the others (plain camber). It acts on"""), (
    """                    float toe = math.asin(math.clamp(math.dot(aOut, bF), -1f, 1f));
                    float camber = -math.asin(math.clamp(math.dot(aOut, bU), -1f, 1f));
                    float3 tAxis = -ws.side * bU, cAxis = -ws.side * bF;""",
    """                    float toe = math.asin(math.clamp(math.dot(aOut, bF), -1f, 1f));
                    float3 kp = ws.kingpin.x * bR + ws.kingpin.y * bU + ws.kingpin.z * bF;
                    float camber = math.acos(math.clamp(math.dot(aOut, kp), -1f, 1f)) - ws.kingpinPhi0;
                    float3 tAxis = -ws.side * bU, cAxis = -math.normalizesafe(math.cross(aOut, kp), ws.side * bF);""")])
print("patched")
