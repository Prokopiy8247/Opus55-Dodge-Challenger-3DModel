"""Pre-fractured glass (brief 7): for every pane a shard mesh that Unity swaps in once the pane's glass beams break.

The pane's evaluated mesh (thickness applied) is split along a Voronoi diagram whose seeds are the pane's physics nodes
plus a few jittered seeds per node (smaller pieces): every triangle goes to the seed nearest to its centroid, the faces
of different seeds are torn apart (split edges) and every shard is shrunk by a millimetre or two towards its centre, so
the cracks show. A second UV map "ShardNode" carries in u the index of the shard's node in geometry.json: the Unity
importer binds every shard rigidly to that one node, so the shards stay in place while the pane holds together (a
cracked windscreen) and fly with their nodes, at their velocities, once the glass beams have broken.

Objects: CH_Glass_*_Shards in Car_Visual/Glass_Shards (exported with their pane, hskel.VISUALS); deterministic (seeded).
Usage (Blender): hcar.glass_shards:build()
"""
import json
import math
import os
import random

import bmesh
import bpy
from mathutils import Vector, kdtree

from . import PROJECT_ROOT
from . import blend_util as bu

GEOMETRY = os.path.join(PROJECT_ROOT, "sim", "vehicle", "hellcat", "geometry.json")
PANES = [  # skeleton part, pane object, extra seeds per node, shrink (m)
    ("glass_windshield", "CH_Glass_Windshield", 2, 0.0012),
    ("glass_rear", "CH_Glass_Rear", 2, 0.0012),
    ("glass_side_FL", "CH_Glass_Door_L", 3, 0.0015),
    ("glass_side_FR", "CH_Glass_Door_R", 3, 0.0015),
    ("glass_quarter_L", "CH_Glass_Quarter_L", 3, 0.0015),
    ("glass_quarter_R", "CH_Glass_Quarter_R", 3, 0.0015),
]


def shard_name(pane):
    return pane + "_Shards"


def _pane_nodes(geo, part):
    """(node index, Blender-frame position) of the part's nodes (geometry.json is in the Unity frame u = (x, z, y))."""
    out = []
    for i, n in enumerate(geo["nodes"]):
        if n["part"] == part:
            x, y, z = n["p"]
            out.append((i, Vector((x, z, y))))
    return out


def _build_one(geo, part, pane_name, extra, shrink, rng, parent):
    src = bpy.data.objects.get(pane_name)
    if src is None:
        raise RuntimeError(f"{pane_name} missing")
    nodes = _pane_nodes(geo, part)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = src.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    ev.to_mesh_clear()
    bm.transform(src.matrix_world)
    bm.faces.ensure_lookup_table()
    # node spacing: jitter radius of the extra seeds
    tree_n = kdtree.KDTree(len(nodes))
    for k, (_, p) in enumerate(nodes):
        tree_n.insert(p, k)
    tree_n.balance()
    spacing = []
    for _, p in nodes:
        found = tree_n.find_n(p, 2)
        spacing.append(found[1][2] if len(found) > 1 else 0.05)
    # seeds: the nodes on the pane surface (nearest face centroid) plus jittered ones
    centroids = [f.calc_center_median() for f in bm.faces]
    tree_f = kdtree.KDTree(len(centroids))
    for k, c in enumerate(centroids):
        tree_f.insert(c, k)
    tree_f.balance()
    seeds = []                                                  # (position, node index)
    for k, (ni, p) in enumerate(nodes):
        _, fk, _ = tree_f.find(p)
        base = centroids[fk]
        seeds.append((base, ni))
        for _ in range(extra):
            r = 0.45 * spacing[k]
            a = rng.uniform(0.0, 2.0 * math.pi)
            off = Vector((math.cos(a), math.sin(a), rng.uniform(-1.0, 1.0))) * r * rng.uniform(0.3, 1.0)
            _, fk2, _ = tree_f.find(base + off)
            seeds.append((centroids[fk2], ni))
    tree_s = kdtree.KDTree(len(seeds))
    for k, (p, _) in enumerate(seeds):
        tree_s.insert(p, k)
    tree_s.balance()
    owner = [tree_s.find(c)[1] for c in centroids]
    # tear the faces of different seeds apart
    cut = [e for e in bm.edges if len(e.link_faces) == 2 and owner[e.link_faces[0].index] != owner[e.link_faces[1].index]]
    bmesh.ops.split_edges(bm, edges=cut)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    # per shard: centre, shrink, node index into the ShardNode UV map
    vshard = {}
    for f in bm.faces:
        for v in f.verts:
            vshard[v.index] = owner[f.index]
    sums = {}
    for v in bm.verts:
        s = vshard.get(v.index)
        if s is None:
            continue
        acc = sums.setdefault(s, [Vector(), 0])
        acc[0] += v.co
        acc[1] += 1
    for v in bm.verts:
        s = vshard.get(v.index)
        if s is None:
            continue
        c = sums[s][0] / sums[s][1]
        d = c - v.co
        if d.length > 1e-6:
            v.co += d.normalized() * min(shrink, 0.5 * d.length)
    if not bm.loops.layers.uv:
        bm.loops.layers.uv.new("UVMap")              # ShardNode must be the second map (Unity uv2)
    uv_node = bm.loops.layers.uv.new("ShardNode")
    for f in bm.faces:
        ni = seeds[owner[f.index]][1]
        for loop in f.loops:
            loop[uv_node].uv = (float(ni), 0.0)
    name = shard_name(pane_name)
    bu.remove_object(name)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    for mat in src.data.materials:
        obj.data.materials.append(mat)
    parent.objects.link(obj)
    obj.hide_render = True
    obj.hide_set(True)
    return {"pane": pane_name, "nodes": len(nodes), "seeds": len(seeds), "shards": len(set(owner)),
            "vertices": len(mesh.vertices), "faces": len(mesh.polygons)}


def build(rng_seed=7):
    geo = json.load(open(GEOMETRY, encoding="utf-8"))
    vis = bpy.data.collections.get("Car_Visual")
    if vis is None:
        raise RuntimeError("collection Car_Visual missing")
    col = bu.collection("Glass_Shards", parent=vis)
    rng = random.Random(rng_seed)
    out = []
    for part, pane, extra, shrink in PANES:
        out.append(_build_one(geo, part, pane, extra, shrink, rng, col))
    return out
