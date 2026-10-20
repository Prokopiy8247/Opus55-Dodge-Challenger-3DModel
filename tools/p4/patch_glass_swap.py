"""One-off (P4): pre-fractured glass. The importer binds every CH_Glass_*_Shards vertex rigidly to the node in its second
UV map (hcar.glass_shards); the car view hides the shards and swaps them in for the intact pane once one of the pane's
glass beams has broken."""
from pathlib import Path


def edit(path, pairs):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    for o, n in pairs:
        assert s.count(o) == 1, (path, o[:80])
        s = s.replace(o, n)
    p.write_text(s, encoding="utf-8")


edit("Unity/HellcatSandbox/Assets/Editor/Car/CarImporter.cs", [
    ('''                    var candidates = Candidates(def, obj, partNodes);
                    var ms = Bind(def, world, candidates, bind, toWorld, out double reach);''',
     '''                    var candidates = Candidates(def, obj, partNodes);
                    var ms = objName.EndsWith("_Shards")
                        ? BindShards(def, mesh, world, candidates, bind, toWorld, out double reach)
                        : Bind(def, world, candidates, bind, toWorld, out reach);'''),
    ('''        /// <summary>Linear blend skinning at the bind pose (bones at the model pose) against the vertices in the skeleton frame.</summary>''',
     '''        /// <summary>Pre-fractured glass (hcar.glass_shards): every vertex rigidly on the node its shard was cut around, whose
        /// index (vehicle definition) the second UV map carries; the shards keep their pane's shape while its nodes hold
        /// together and fly with them once the glass beams break.</summary>
        static CarSkinData.MeshSkin BindShards(VehicleDef def, Mesh mesh, Vector3[] world, int[] cand, Matrix4x4[] bind, Matrix4x4 toWorld,
            out double reach)
        {
            var uv = new List<Vector2>();
            mesh.GetUVs(1, uv);
            if (uv.Count != world.Length)
                throw new InvalidDataException($"{mesh.name}: no ShardNode UV map (second UV channel)");
            var allowed = new HashSet<int>(cand);
            var boneOf = new Dictionary<int, int>();
            var bones = new List<int>();
            var bpv = new byte[world.Length];
            var weights = new BoneWeight1[world.Length];
            reach = 0;
            for (int v = 0; v < world.Length; v++)
            {
                int node = Mathf.RoundToInt(uv[v].x);
                if (!allowed.Contains(node))
                    throw new InvalidDataException($"{mesh.name}: vertex {v} names node {node}, not a node of its pane");
                if (!boneOf.TryGetValue(node, out int bi)) { bi = bones.Count; boneOf[node] = bi; bones.Add(node); }
                bpv[v] = 1;
                weights[v] = new BoneWeight1 { boneIndex = bi, weight = 1f };
                reach = Math.Max(reach, (P(def, node) - world[v]).magnitude);
            }
            var bp = bones.Select(n => bind[n].inverse * toWorld).ToArray();
            return new CarSkinData.MeshSkin
            {
                vertexCount = world.Length, boneNodes = bones.ToArray(), bindposes = bp, bonesPerVertex = bpv, weights = weights,
            };
        }

        /// <summary>Linear blend skinning at the bind pose (bones at the model pose) against the vertices in the skeleton frame.</summary>'''),
])

edit("Unity/HellcatSandbox/Assets/Game/Views/SoftBodyCarView.cs", [
    ('''        TransformAccessArray access;
        NativeArray<int3> frames;   // world node indices: origin, axis a, axis b
        bool ready;''',
     '''        TransformAccessArray access;
        NativeArray<int3> frames;   // world node indices: origin, axis a, axis b
        bool ready;

        // pre-fractured glass (brief 7): per pane the intact renderer, its shards and the pane's own glass beams
        sealed class Pane
        {
            public string name;
            public Renderer intact, shards;
            public int[] beams;      // global beam indices of the pane's glass / glass_side beams
            public bool broken;
        }
        readonly List<Pane> panes = new List<Pane>();

        /// <summary>Panes shattered so far (shards shown).</summary>
        public int BrokenPanes { get; private set; }'''),
    ('''            frames = new NativeArray<int3>(nodeBones.Length, Allocator.Persistent);
            for (int i = 0; i < nodeBones.Length; i++)
                frames[i] = new int3(start + i, start + frameAxes[i].x, start + frameAxes[i].y);
            ready = true;
            UpdateBones();''',
     '''            frames = new NativeArray<int3>(nodeBones.Length, Allocator.Persistent);
            for (int i = 0; i < nodeBones.Length; i++)
                frames[i] = new int3(start + i, start + frameAxes[i].x, start + frameAxes[i].y);
            SetupGlass();
            ready = true;
            UpdateBones();'''),
    ('''        public void UpdateBones()
        {
            new BoneJob { pos = runner.World.pos, frames = frames }.Schedule(access).Complete();
        }''',
     '''        public void UpdateBones()
        {
            new BoneJob { pos = runner.World.pos, frames = frames }.Schedule(access).Complete();
            CheckGlass();
        }

        void SetupGlass()
        {
            var byName = new Dictionary<string, Renderer>();
            foreach (var r in GetComponentsInChildren<SkinnedMeshRenderer>(true))
                byName[r.name] = r;
            var w = runner.World;
            var b = w.bodies[runner.VehicleBody];
            var def = b.def;
            foreach (var part in def.parts ?? new Hellcat.Sim.Data.PartDef[0])
            {
                if (part.visuals == null) continue;
                foreach (var vis in part.visuals)
                {
                    if (!vis.EndsWith("_Shards") || !byName.TryGetValue(vis, out var shards)) continue;
                    string paneName = vis.Substring(0, vis.Length - "_Shards".Length);
                    if (!byName.TryGetValue(paneName, out var intact)) continue;
                    var inPart = new HashSet<int>(part.nodes);
                    var beams = new List<int>();
                    for (int k = 0; k < b.beamCount; k++)
                    {
                        var bd = def.beams[k];
                        if ((bd.mat == "glass" || bd.mat == "glass_side") && inPart.Contains(bd.a) && inPart.Contains(bd.b))
                            beams.Add(b.beamStart + k);
                    }
                    shards.enabled = false;
                    panes.Add(new Pane { name = paneName, intact = intact, shards = shards, beams = beams.ToArray() });
                }
            }
        }

        /// <summary>A pane shatters (its shards replace it) as soon as one of its glass beams has broken.</summary>
        void CheckGlass()
        {
            var broken = runner.World.broken;
            foreach (var p in panes)
            {
                if (p.broken) continue;
                foreach (int j in p.beams)
                    if (broken[j] != 0)
                    {
                        p.broken = true;
                        p.intact.enabled = false;
                        p.shards.enabled = true;
                        BrokenPanes++;
                        break;
                    }
            }
        }'''),
])
print("patched")
