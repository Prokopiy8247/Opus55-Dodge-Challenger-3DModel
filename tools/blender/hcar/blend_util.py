"""Small Blender helpers: collections, mesh objects, materials, versioned saving."""
import os
import re

import bpy

from . import PROJECT_ROOT

ORIGINAL = os.path.normcase(os.path.normpath(os.path.join(PROJECT_ROOT, "3DDodgeChallenger.blend")))


def collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
    parent = parent or bpy.context.scene.collection
    if col.name not in [c.name for c in parent.children]:
        # unlink from other parents first so the hierarchy stays clean
        for other in bpy.data.collections:
            if col.name in [c.name for c in other.children] and other != parent:
                other.children.unlink(col)
        if col.name in [c.name for c in bpy.context.scene.collection.children] and parent != bpy.context.scene.collection:
            bpy.context.scene.collection.children.unlink(col)
        parent.children.link(col)
    return col


def remove_object(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        return
    data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if data is not None and getattr(data, "users", 1) == 0:
        if isinstance(data, bpy.types.Mesh):
            bpy.data.meshes.remove(data)
        elif isinstance(data, bpy.types.Curve):
            bpy.data.curves.remove(data)


def mesh_object(name, verts, edges=(), faces=(), col=None, replace=True):
    if replace:
        remove_object(name)
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [tuple(e) for e in edges], [tuple(f) for f in faces])
    me.validate(clean_customdata=False)
    me.update()
    obj = bpy.data.objects.new(name, me)
    (col or bpy.context.scene.collection).objects.link(obj)
    return obj


def material(name, color, metallic=0.0, roughness=0.5, emission=None, alpha=1.0, emission_strength=1.0):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*color[:3], 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission is not None:
        bsdf.inputs["Emission Color"].default_value = (*emission[:3], 1.0)
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
    mat.diffuse_color = (*color[:3], alpha)
    return mat


def next_version_path():
    folder = PROJECT_ROOT
    best = 0
    for f in os.listdir(folder):
        m = re.fullmatch(r"3DDodgeChallenger_v(\d{3})\.blend", f)
        if m:
            best = max(best, int(m.group(1)))
    return os.path.join(folder, f"3DDodgeChallenger_v{best + 1:03d}.blend")


def save_version(note=""):
    """Saves the open file as the next 3DDodgeChallenger_vNNN.blend (never the original)."""
    path = next_version_path()
    if os.path.normcase(os.path.normpath(path)) == ORIGINAL:
        raise RuntimeError("refusing to overwrite the original file")
    bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False, copy=False)
    return {"saved": path, "note": note}


def save_current():
    """Saves the current working file in place (only when it is a vNNN file, never the original)."""
    path = bpy.data.filepath
    if not path or os.path.normcase(os.path.normpath(path)) == ORIGINAL or not re.search(r"_v\d{3}\.blend$", path):
        return save_version("auto")
    bpy.ops.wm.save_mainfile(filepath=path)
    return {"saved": path}
