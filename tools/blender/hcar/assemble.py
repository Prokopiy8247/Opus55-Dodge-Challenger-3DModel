"""Final organisation of the exterior: names, left/right parts, collections, origins, UVs.

    finalize()  takes the objects built by body.preview_* / details / mechanics in Car_Visual_WIP,
                renames DBG_* -> CH_*, splits mirrored pairs into *_L / *_R (x < 0 = car's left),
                moves everything into the collection Car_Visual (wheel assemblies under
                Car_Visual/Wheels), sets every origin to its own bounding-box centre, adds a
                Smart-UV unwrap, and deletes the preview helpers (strip, greenhouse, old caps).
    build_car() runs the whole pipeline from the shape tables to the finished collection.
"""
import bmesh
import bpy
from mathutils import Vector

from .blend_util import collection, remove_object

SPLIT = ("CH_Door", "CH_Fender", "CH_Quarter", "CH_Rocker", "CH_Flare_front", "CH_Flare_rear", "CH_Glass_Door",
         "CH_Glass_Quarter", "CH_Pillars", "CH_Headlamp_Housing", "CH_Headlamp_Reflector", "CH_Headlamp_Halo",
         "CH_Headlamp_Lens", "CH_Mirror_Housing", "CH_Mirror_Glass", "CH_Mirror_Stalk", "CH_SideSill",
         "CH_Marker_Front", "CH_Marker_Rear", "CH_Door_Handle", "CH_Exhaust_Tips", "CH_Grille_Duct",
         "CH_Hood_Extractor", "CH_Hood_Extractor_Vent", "CH_Badge_Hellcat", "CH_WheelLiners")
DROP = ("DBG_Strip", "DBG_Greenhouse", "DBG_hood", "DBG_deck")
RENAME = {"CH_CH_Fascia": "CH_Bumper_F", "CH_Fascia": "CH_Bumper_F", "CH_CH_RearBumper": "CH_Bumper_R",
          "CH_RearBumper": "CH_Bumper_R"}
# panel thickness (brief 5.3: thin panels 1-2 mm): name prefix -> (thickness m, material class)
THICK = (("CH_Glass", 0.0045), ("CH_Bumper", 0.003), ("CH_Flare", 0.003), ("CH_Door", 0.0015),
         ("CH_Fender", 0.0015), ("CH_Quarter", 0.0015), ("CH_Rocker", 0.0015), ("CH_Hood", 0.0015),
         ("CH_DeckLid", 0.0015), ("CH_Roof", 0.0015), ("CH_Pillars", 0.0015), ("CH_Spoiler", 0.0),
         ("CH_PlateRecess", 0.0015), ("CH_Valance", 0.003),
         ("CH_FloorPan", 0.0015), ("CH_WheelLiners", 0.002), ("CH_Hood_Scoop", 0.0015), ("CH_Cowl", 0.002))


def add_thickness(objs):
    """Solidify modifiers (inwards, rim fill, high-quality normals) so every panel is a closed thin
    shell; exported with the modifier applied. Even thickness stays off: at the folded flange
    corners it divides by a near-zero cosine and throws vertices metres away (G-Model audit)."""
    n = 0
    for o in objs:
        if o.type != "MESH":
            continue
        th = next((t for p, t in THICK if o.name.startswith(p)), None)
        if not th:
            continue
        mod = o.modifiers.get("CH_Thickness") or o.modifiers.new("CH_Thickness", "SOLIDIFY")
        mod.solidify_mode = "EXTRUDE"
        mod.thickness = th
        mod.offset = -1.0
        mod.use_rim = True
        mod.use_even_offset = False
        if hasattr(mod, "use_quality_normals"):
            mod.use_quality_normals = True
        n += 1
    return n


def unmirror_wheels(objs):
    """The left wheel hubs were mirrored with scale x = -1 (and their meshes flipped to compensate).
    Bake the mirror into the meshes instead, so every object has a positive-determinant transform
    (clean FBX export, no winding surprises in Unity)."""
    from mathutils import Matrix
    mirror = Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0))
    n = 0
    for hub in [o for o in objs if o.type == "EMPTY" and o.name.startswith("CH_Wheel_") and o.scale.x < 0]:
        for ch in hub.children:
            if ch.type == "MESH":
                ch.data.transform(mirror)
                ch.data.flip_normals()      # keeps the rendered front side (mirroring reversed the winding)
        hub.scale.x = 1.0
        n += 1
    return n


def fix_orientation(objs, n_dirs=96, res=100):
    """Outward normals for every part built without custom normals (details, wheels, mechanics):
    1. per connected island, make the winding consistent (bmesh recalc; closed islands come out
       facing outwards);
    2. open islands: flip when rays from outside the car hit more back faces than front faces;
    returns {object: islands flipped in step 2}."""
    import numpy as np
    from .gate_model import ray_hits
    cand = [o for o in objs if o.type == "MESH" and not o.data.has_custom_normals and len(o.data.polygons)]
    islands = {}
    for o in cand:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.faces.ensure_lookup_table()
        seen = set()
        isl = []
        for f0 in bm.faces:
            if f0.index in seen:
                continue
            stack, comp = [f0], []
            seen.add(f0.index)
            while stack:
                f = stack.pop()
                comp.append(f)
                for e in f.edges:
                    for g in e.link_faces:
                        if g.index not in seen:
                            seen.add(g.index)
                            stack.append(g)
            closed = all(len(e.link_faces) == 2 for f in comp for e in f.edges)
            bmesh.ops.recalc_face_normals(bm, faces=comp)
            isl.append(([f.index for f in comp], closed))
        bm.to_mesh(o.data)
        bm.free()
        o.data.update()
        islands[o.name] = isl
    # step 2: visibility votes (the whole car occludes)
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    allm = [o for o in objs if o.type == "MESH"]
    hits, _ = ray_hits(allm, dg, n_dirs, res)
    flipped = {}
    for o in cand:
        f, b = hits.get(o.name, (None, None))
        if f is None:
            continue
        rev = []
        for idx, closed in islands[o.name]:
            idx = np.asarray(idx)
            idx = idx[idx < len(f)]
            if closed or not len(idx):
                continue
            fr, bk = int(f[idx].sum()), int(b[idx].sum())
            if bk > fr and bk >= 3:
                rev.append(idx)
        if rev:
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bm.faces.ensure_lookup_table()
            bmesh.ops.reverse_faces(bm, faces=[bm.faces[int(i)] for r in rev for i in r])
            bm.to_mesh(o.data)
            bm.free()
            o.data.update()
            flipped[o.name] = len(rev)
    return flipped


def two_sided_open_shells(objs, threshold=0.01, n_dirs=128, res=110):
    """Parts that still show back faces from outside (open cups and tubes: mirror housings,
    exhaust tips, lamp housings) get a thin shell so both sides render with culling on."""
    from .gate_model import visibility
    allm = [o for o in objs if o.type == "MESH"]
    vis = visibility(allm, None, n_dirs, res)["per_object"]
    added = []
    for o in allm:
        v = vis.get(o.name)
        if v is None or v["hits"] < 10 or v["back_frac"] <= threshold or o.modifiers.get("CH_Thickness"):
            continue
        mod = o.modifiers.new("CH_Thickness", "SOLIDIFY")
        mod.solidify_mode = "EXTRUDE"
        mod.thickness = 0.0008
        mod.offset = -1.0
        mod.use_rim = True
        mod.use_even_offset = False
        added.append(o.name)
    return added


def _drop_loose(obj):
    """Delete vertices used by no face (flange ring vertices whose faces were pruned): they would
    land in both halves of a left/right split and in the FBX. Returns the number removed."""
    import numpy as np
    me = obj.data
    used = np.zeros(len(me.vertices), bool)
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    used[lv] = True
    if used.all():
        return 0
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    loose = [bm.verts[int(i)] for i in np.nonzero(~used)[0]]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(me)
    bm.free()
    me.update()
    return len(loose)


def _split_lr(obj):
    """Separate the faces with centre x < 0 into a new object *_L; the original becomes *_R."""
    base = obj.name
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    left = [f for f in bm.faces if f.calc_center_median().x < 0]
    if not left or len(left) == len(bm.faces):
        bm.free()
        return [obj]
    me_l = me.copy()
    bm_l = bmesh.new()
    bm_l.from_mesh(me_l)
    bmesh.ops.delete(bm_l, geom=[f for f in bm_l.faces if f.calc_center_median().x >= 0], context="FACES")
    bm_l.to_mesh(me_l)
    bm_l.free()
    bmesh.ops.delete(bm, geom=left, context="FACES")
    bm.to_mesh(me)
    bm.free()
    obj_l = bpy.data.objects.new(base + "_L", me_l)
    for c in obj.users_collection:
        c.objects.link(obj_l)
    obj_l.matrix_world = obj.matrix_world.copy()
    obj.name = base + "_R"
    me.name = obj.name
    me_l.name = obj_l.name
    return [obj_l, obj]


def _origin_to_bbox(obj):
    if obj.type != "MESH" or not len(obj.data.vertices):
        return
    co = [obj.matrix_world @ v.co for v in obj.data.vertices]
    lo = Vector((min(c.x for c in co), min(c.y for c in co), min(c.z for c in co)))
    hi = Vector((max(c.x for c in co), max(c.y for c in co), max(c.z for c in co)))
    centre = (lo + hi) / 2
    local = obj.matrix_world.inverted() @ centre
    obj.data.transform(__import__("mathutils").Matrix.Translation(-local))
    obj.matrix_world.translation = obj.matrix_world @ local


def _box_uv(obj, scale=1.0):
    """Box-projection UVs in world metres (dominant normal axis per face): seamless enough for
    paint flakes, trim grain and decals; needs no operator context."""
    import numpy as np
    me = obj.data
    npoly = len(me.polygons)
    if not npoly:
        return False
    # mesh API only (a bmesh round trip could drop the custom split normals)
    nrm = np.empty(npoly * 3, np.float32)
    me.polygons.foreach_get("normal", nrm)
    nrm = nrm.reshape(-1, 3)
    ls = np.empty(npoly, np.int32)
    lt = np.empty(npoly, np.int32)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    vi = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", vi)
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    M = np.array(obj.matrix_world)
    co = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    poly_of_loop = np.repeat(np.arange(npoly), lt)
    ax = np.abs(nrm).argmax(axis=1)[poly_of_loop]
    pick = np.array([(1, 2), (0, 2), (0, 1)])[ax]
    c = co[vi]
    uv = np.stack([c[np.arange(len(c)), pick[:, 0]], c[np.arange(len(c)), pick[:, 1]]], axis=1) * scale
    layer = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    layer.data.foreach_set("uv", uv.astype(np.float32).ravel())
    return True


def _smart_uv(objs):
    """UVs for every mesh (box projection, see _box_uv)."""
    return sum(1 for o in objs if o.type == "MESH" and _box_uv(o))


def finalize(uv=True):
    wip = bpy.data.collections.get("Car_Visual_WIP")
    if wip is None:
        raise RuntimeError("build the WIP objects first")
    vis = collection("Car_Visual")
    wheels_col = collection("Wheels", parent=vis)
    for name in DROP:
        remove_object(name)
    result = {"renamed": 0, "split": 0}
    for obj in list(wip.all_objects):
        if obj.name.startswith("DBG_"):
            new = obj.name[4:]
            if not new.startswith("CH_"):
                new = "CH_" + new
            remove_object(new)
            obj.name = new
            if obj.data is not None:
                obj.data.name = new
            result["renamed"] += 1
    for obj in list(wip.all_objects):
        if obj.name in RENAME:
            new = RENAME[obj.name]
            remove_object(new)
            obj.name = new
            obj.data.name = new
    result["loose_vertices_removed"] = sum(_drop_loose(o) for o in wip.all_objects if o.type == "MESH")
    for obj in list(wip.all_objects):
        if obj.type == "MESH" and obj.name in SPLIT:
            parts = _split_lr(obj)
            result["split"] += len(parts) > 1
    # move into the final collections
    for obj in list(wip.all_objects):
        target = wheels_col if obj.name.startswith("CH_Wheel_") else vis
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        target.objects.link(obj)
    if not wip.all_objects:
        bpy.data.collections.remove(wip)
    result["unmirrored_hubs"] = unmirror_wheels(list(vis.all_objects))
    result["orientation_flipped"] = fix_orientation(list(vis.all_objects))
    # origins (wheel parts keep their hub parent frame)
    for obj in vis.all_objects:
        if obj.type == "MESH" and obj.parent is None:
            _origin_to_bbox(obj)
    if uv:
        result["uv_objects"] = _smart_uv([o for o in vis.all_objects if o.type == "MESH"])
    result["thickness"] = add_thickness(list(vis.all_objects))
    result["two_sided"] = two_sided_open_shells(list(vis.all_objects))
    result["objects"] = len(vis.all_objects)
    return result


def clear_car():
    """Delete the finished exterior (Car_Visual and its child collections) and orphan data."""
    n = 0
    for cname in ("Car_Visual", "Car_Visual_WIP"):
        col = bpy.data.collections.get(cname)
        if col is None:
            continue
        for obj in list(col.all_objects):
            bpy.data.objects.remove(obj, do_unlink=True)
            n += 1
    for me in [m for m in bpy.data.meshes if m.users == 0]:
        bpy.data.meshes.remove(me)
    return n


def build_car():
    """Whole exterior from the tables: preview builders, details, mechanics, then finalize()."""
    from . import body, details, mechanics  # noqa: F401
    from .body_panels import bumper_panels
    out = {"cleared": clear_car()}
    out["all"] = body.preview_all()
    out["flares_wheels"] = body.preview_flares_wheels()
    out["panels"] = body.preview_panels()
    m = body.model()
    out["details"] = details.build_all(m, bumper_panels(m))
    out["mechanics"] = mechanics.build_all()
    out["finalize"] = finalize()
    return out
