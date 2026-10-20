"""P4: export of the visual car for Unity (brief 7: one FBX per part group, parts.json, materials and textures).

Every CH_* mesh of Car_Visual and Car_Interior goes into the FBX of the physics part that lists it in the skeleton
(hskel.VISUALS, written to geometry.json "parts"); visuals listed by several parts (knuckles, arms, springs, half
shafts) go into "running_gear" and keep the list of parts whose nodes they may bind to; the interior (except the door
cards) goes into "interior" and binds to the body. Meshes are exported with their modifiers applied (Solidify) and the
object transforms baked, in metres; the Unity editor import (Tools/Hellcat/Import Car) checks that the imported
vertices land in the skeleton's frame (u = (x, z, y)) and computes the node bindings there.

parts.json: {"frame": "...", "fbx": [{"file", "group", "objects": [{"name", "bind": [parts], "materials": [...],
"vertices", "triangles", "bbox_min": [x, y, z], "bbox_max": [x, y, z]}]}]} (Unity frame); materials.json: base colour, metallic, roughness, alpha,
emission, textures per material (Principled BSDF, linear colours); textures copied next to the FBX files.
"""
import json
import os
import shutil

import bpy

from . import blend_util as bu

PROJECT_ROOT = bu.PROJECT_ROOT if hasattr(bu, "PROJECT_ROOT") else os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GEOMETRY = os.path.join(PROJECT_ROOT, "sim", "vehicle", "hellcat", "geometry.json")
OUT = os.path.join(PROJECT_ROOT, "Unity", "HellcatSandbox", "Assets", "Game", "Vehicles", "Hellcat", "Export")
SHARED = "running_gear"
INTERIOR = "interior"


def visual_objects():
    objs = {}
    for cname in ("Car_Visual", "Car_Interior"):
        c = bpy.data.collections.get(cname)
        if c is None:
            raise RuntimeError(f"collection {cname} missing")
        for o in c.all_objects:
            if o.type == "MESH" and o.name.startswith("CH_"):
                objs[o.name] = (o, cname)
    return objs


def grouping(objs):
    """object name -> (fbx group, bind parts)."""
    g = json.load(open(GEOMETRY, encoding="utf-8"))
    listed = {}
    for p in g["parts"]:
        for v in p.get("visuals") or []:
            listed.setdefault(v, []).append(p["name"])
    out = {}
    for name, (o, cname) in objs.items():
        parts = listed.get(name)
        if parts:
            parts = list(dict.fromkeys(parts))
            out[name] = (parts[0] if len(parts) == 1 else SHARED, parts)
        elif cname == "Car_Interior":
            out[name] = (INTERIOR, ["body"])
        else:
            out[name] = ("body", ["body"])
    return out


def unity_bbox(o):
    dg = bpy.context.evaluated_depsgraph_get()
    e = o.evaluated_get(dg)
    m = e.to_mesh()
    mw = o.matrix_world
    lo, hi = [1e9] * 3, [-1e9] * 3
    for v in m.vertices:
        w = mw @ v.co
        u = (w.x, w.z, w.y)
        lo = [min(a, b) for a, b in zip(lo, u)]
        hi = [max(a, b) for a, b in zip(hi, u)]
    nv, nt = len(m.vertices), sum(len(p.vertices) - 2 for p in m.polygons)
    e.to_mesh_clear()
    return [lo, hi], nv, nt


def material_record(m):
    rec = {"name": m.name, "baseColor": [1, 1, 1, 1], "metallic": 0.0, "roughness": 0.5, "alpha": 1.0,
           "emission": [0, 0, 0], "emissionStrength": 0.0, "textures": {}}
    if not m.use_nodes:
        rec["baseColor"] = list(m.diffuse_color)
        return rec
    bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        return rec
    rec["baseColor"] = list(bsdf.inputs["Base Color"].default_value)
    rec["metallic"] = float(bsdf.inputs["Metallic"].default_value)
    rec["roughness"] = float(bsdf.inputs["Roughness"].default_value)
    rec["alpha"] = float(bsdf.inputs["Alpha"].default_value)
    if "Emission Color" in bsdf.inputs:
        rec["emission"] = list(bsdf.inputs["Emission Color"].default_value)[:3]
        rec["emissionStrength"] = float(bsdf.inputs["Emission Strength"].default_value)
    for link in m.node_tree.links:
        if link.to_node != bsdf:
            continue
        src = link.from_node
        # follow through simple colour nodes to the image
        seen = 0
        while src.type != "TEX_IMAGE" and seen < 4:
            ins = [l.from_node for l in m.node_tree.links if l.to_node == src]
            if not ins:
                break
            src = ins[0]
            seen += 1
        if src.type == "TEX_IMAGE" and src.image:
            rec["textures"][link.to_socket.name] = os.path.basename(bpy.path.abspath(src.image.filepath)) or src.image.name
    return rec


def export_group(path, objects):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH"}, use_mesh_modifiers=True,
                             mesh_smooth_type="OFF", use_tspace=True, add_leaf_bones=False, bake_anim=False,
                             path_mode="STRIP", embed_textures=False, axis_forward="Z", axis_up="Y",
                             apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL", bake_space_transform=True,
                             global_scale=1.0, use_custom_props=False)


def export_all(out_dir=OUT, only=None):
    os.makedirs(out_dir, exist_ok=True)
    objs = visual_objects()
    grp = grouping(objs)
    groups = {}
    for name, (fbx, parts) in sorted(grp.items()):
        groups.setdefault(fbx, []).append(name)
    # remember and restore visibility / selection
    vis = {n: (o.hide_get(), o.hide_viewport) for n, (o, _) in objs.items()}
    hidden_cols = []
    lc = bpy.context.view_layer.layer_collection
    stack = list(lc.children)
    while stack:
        c = stack.pop()
        if c.name in ("Car_Visual", "Car_Interior") and c.exclude:
            c.exclude = False
            hidden_cols.append(c)
        stack.extend(c.children)
    record = {"frame": "Unity: x right, y up, z forward (Blender x, z, y); metres; transforms and modifiers applied",
              "fbx": []}
    mats = {}
    try:
        for fbx, names in sorted(groups.items()):
            if only and fbx not in only:
                continue
            obs = [objs[n][0] for n in names]
            path = os.path.join(out_dir, f"{fbx}.fbx")
            export_group(path, obs)
            entry = {"file": f"{fbx}.fbx", "group": fbx, "objects": []}
            for o in obs:
                bb, nv, nt = unity_bbox(o)
                ms = [s.material.name for s in o.material_slots if s.material]
                for s in o.material_slots:
                    if s.material and s.material.name not in mats:
                        mats[s.material.name] = material_record(s.material)
                entry["objects"].append({"name": o.name, "bind": grp[o.name][1], "materials": ms, "vertices": nv,
                                         "triangles": nt, "bbox_min": bb[0], "bbox_max": bb[1]})
            record["fbx"].append(entry)
    finally:
        for n, (h, hv) in vis.items():
            objs[n][0].hide_set(h)
        for c in hidden_cols:
            c.exclude = True
        bpy.ops.object.select_all(action="DESELECT")
    # textures
    tex_dir = os.path.join(out_dir, "Textures")
    os.makedirs(tex_dir, exist_ok=True)
    copied = []
    for img in bpy.data.images:
        src = bpy.path.abspath(img.filepath) if img.filepath else ""
        if src and os.path.exists(src) and any(os.path.basename(src) in m["textures"].values() for m in mats.values()):
            dst = os.path.join(tex_dir, os.path.basename(src))
            shutil.copyfile(src, dst)
            copied.append(os.path.basename(src))
    with open(os.path.join(out_dir, "parts.json"), "w", encoding="utf-8") as f:
        json.dump(record, f, indent=1)
    with open(os.path.join(out_dir, "materials.json"), "w", encoding="utf-8") as f:
        json.dump({"materials": [mats[k] for k in sorted(mats)]}, f, indent=1)
    return {"fbx": [e["file"] for e in record["fbx"]], "objects": sum(len(e["objects"]) for e in record["fbx"]),
            "materials": len(mats), "textures": copied, "out": out_dir}
