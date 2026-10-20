"""One-off (P5): teleport hold releases only before tall obstacles ahead (lanes may hold through), props spawn 12 mm above
the surface, the map check logs broken beams by material."""
from pathlib import Path

A = Path(__file__).resolve().parents[2] / "Unity/HellcatSandbox/Assets"


def patch(rel, pairs):
    p = A / rel
    s = p.read_text(encoding="utf-8")
    for o, n in pairs:
        assert s.count(o) == 1, (rel, o[:70])
        s = s.replace(o, n)
    p.write_text(s, encoding="utf-8")


patch("Game/World/SpawnPoint.cs", [(
    """        [Tooltip("Default teleport speed (km/h)")]
        public float defaultKmh = 50f;""",
    """        [Tooltip("Default teleport speed (km/h)")]
        public float defaultKmh = 50f;
        [Tooltip("The teleport speed hold keeps going through drivable obstacles (ramps, ledges, debris) until the run-up time is over")]
        public bool holdThrough;""")])

patch("Game/Input/ApproachHoldSource.cs", [
    ("""    /// go just before the barrier, so it meets the obstacle at V. The hold also ends when the driver touches a pedal, the
    /// steering or the handbrake, or after the run-up time.""",
     """    /// go just before the barrier, so it meets the obstacle at V. Obstacles are static solids taller than 0.3 m ahead of the
    /// car (not the grass slabs, curbs or bumps it drives over); a lane can hold through them (ramps, ledges). The hold also
    /// ends when the driver touches a pedal, the steering or the handbrake, or after the run-up time."""),
    ("""        DriverRobot robot;
        CarProbe probe;""",
     """        DriverRobot robot;
        CarProbe probe;
        bool releaseNear = true;
        const float ObstacleHeight = 0.3f;"""),
    ("""        public void Begin(Vector3 origin, Vector3 dir, float speed, float length)
        {""",
     """        public void Begin(Vector3 origin, Vector3 dir, float speed, float length, bool releaseNearObstacles = true)
        {
            releaseNear = releaseNearObstacles;"""),
    ("""            if (MinObstacleDistance(w, b) < releaseDistance)""",
     """            if (releaseNear && ObstacleAhead(w, b, f) < releaseDistance)"""),
    ("""        /// <summary>Nearest distance of the car's nodes to any static primitive except planes (the ground).</summary>
        static float MinObstacleDistance(SoftBodyWorld w, SoftBodyWorld.Body b)
        {
            float best = float.MaxValue;
            float3 c = w.pos[b.nodeStart];
            for (int p = 0; p < w.prims.Length; p++)
            {
                var prim = w.prims[p];
                if (prim.type == PrimType.Plane)
                    continue;
                if (math.any(c < prim.aabbMin - 12f) || math.any(c > prim.aabbMax + 12f))
                    continue;
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                    best = math.min(best, StaticSdf.Distance(prim, w.planes, w.pos[i], out _));
            }
            return best;
        }""",
     """        /// <summary>Nearest distance of the car's front-half nodes to a static solid ahead of it that stands taller than
        /// 0.3 m (planes, ground slabs, curbs and bumps are driven over).</summary>
        static float ObstacleAhead(SoftBodyWorld w, SoftBodyWorld.Body b, in CarFrame f)
        {
            float best = float.MaxValue;
            float3 c = (float3)f.com, fwd = (float3)f.forward;
            for (int p = 0; p < w.prims.Length; p++)
            {
                var prim = w.prims[p];
                if (prim.type == PrimType.Plane || prim.aabbMax.y < ObstacleHeight)
                    continue;
                float3 nearest = math.clamp(c, prim.aabbMin, prim.aabbMax);
                if (math.dot(nearest - c, fwd) <= 0f || math.distance(nearest, c) > 15f)
                    continue;
                for (int i = b.nodeStart; i < b.nodeStart + b.nodeCount; i++)
                    if (math.dot(w.pos[i] - c, fwd) > 0f)
                        best = math.min(best, StaticSdf.Distance(prim, w.planes, w.pos[i], out _));
            }
            return best;
        }"""),
])

patch("Game/Core/GameControls.cs", [(
    """                approach.Begin(sp.transform.position, fwd, kmh / 3.6f, sp.approachDistance > 0f ? sp.approachDistance : 80f);""",
    """                approach.Begin(sp.transform.position, fwd, kmh / 3.6f, sp.approachDistance > 0f ? sp.approachDistance : 80f, !sp.holdThrough);""")])

patch("Game/World/PropField.cs", [
    ("""                bodies[i] = world.AddBody($"{s.kind}_{i}", def, prm, transform.TransformPoint(s.position), rot, float3.zero, false);""",
     """                // 12 mm above the surface: a node inside the 10 mm contact zone at spawn would be kicked off it
                bodies[i] = world.AddBody($"{s.kind}_{i}", def, prm, transform.TransformPoint(s.position + new Vector3(0f, SpawnGap, 0f)), rot, float3.zero, false);"""),
    ("""        int[] bodies = Array.Empty<int>();""",
     """        int[] bodies = Array.Empty<int>();
        /// <summary>Spawn height above the surface below (m); stacked props add it per layer.</summary>
        public const float SpawnGap = 0.012f;"""),
])

patch("Editor/Build/TestMapBuilder.cs", [
    ("""                    field.props.Add(new PropField.Spot { kind = PropFactory.Kind.Box, position = new Vector3(fx - 0.93f + 0.62f * c, 0.5f, -3.5f - 0.62f * r), yawDeg = 4f * c });""",
     """                    field.props.Add(new PropField.Spot { kind = PropFactory.Kind.Box, position = new Vector3(fx - 0.93f + 0.62f * c, PropFactory.BoxSize + PropField.SpawnGap, -3.5f - 0.62f * r), yawDeg = 4f * c });"""),
    ("""        static void Lane(string id, int order, Vector3 spawn, float headingDeg, float faceZ, float kmh, string label)
        {""",
     """        static void Lane(string id, int order, Vector3 spawn, float headingDeg, float faceZ, float kmh, string label, bool holdThrough = false)
        {"""),
    ("""            SpawnAt(label, order, spawn, headingDeg, run, kmh);
            lanes.Add(""",
     """            SpawnAt(label, order, spawn, headingDeg, run, kmh).GetComponent<SpawnPoint>().holdThrough = holdThrough;
            lanes.Add("""),
    ("""            Lane("O8", 8, new Vector3(fx, 0f, spawnZ), 180f, 25.3f, 15f, "O8 DEBRIS FIELD");""",
     """            Lane("O8", 8, new Vector3(fx, 0f, spawnZ), 180f, 25.3f, 15f, "O8 DEBRIS FIELD", holdThrough: true);"""),
    ("""            Lane("O9", 9, new Vector3(-40f, 0f, spawnZ), 180f, 25f, 40f, "O9 LEDGE 3 m");""",
     """            Lane("O9", 9, new Vector3(-40f, 0f, spawnZ), 180f, 25f, 40f, "O9 LEDGE 3 m", holdThrough: true);"""),
    ("""            Lane("O9b", 10, new Vector3(-14f, 0f, spawnZ), 180f, 26f, 40f, "O9 BANK 30 deg (steer right)");""",
     """            Lane("O9b", 10, new Vector3(-14f, 0f, spawnZ), 180f, 26f, 40f, "O9 BANK 30 deg (steer right)", holdThrough: true);"""),
])

patch("Game/Scenario/MapCheck.cs", [
    ("""            yield return new WaitForEndOfFrame();
            FrameCapture.Save(cameras.GetComponent<Camera>(), Path.Combine(outDir, $"run_{id}_{kmh:F0}kmh.png"), 1600, 900);""",
     """            var brokenBy = new SortedDictionary<string, int>();
            for (int k = 0; k < b.beamCount; k++)
                if (w.broken[b.beamStart + k] != 0)
                {
                    string mat = b.def.beams[k].mat;
                    brokenBy[mat] = brokenBy.TryGetValue(mat, out int c) ? c + 1 : 1;
                }
            string brokenText = string.Join(", ", brokenBy.Select(kv => $"{kv.Key} {kv.Value}"));
            yield return new WaitForEndOfFrame();
            FrameCapture.Save(cameras.GetComponent<Camera>(), Path.Combine(outDir, $"run_{id}_{kmh:F0}kmh.png"), 1600, 900);"""),
    ("""                     $"\\"props_moved\\": {math.max(0, moved - moved0)}}}");""",
     """                     $"\\"props_moved\\": {math.max(0, moved - moved0)}, \\"broken_by_material\\": \\"{brokenText}\\"}}");"""),
])
print("patched")
