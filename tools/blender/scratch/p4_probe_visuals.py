"""P4 probe: Blender version, fracture add-ons, the visual collections (mesh / vertex / loop counts) and materials."""
import addon_utils
import bpy

print("blender", bpy.app.version_string)
print("file", bpy.data.filepath)
print("fracture addons", [m.__name__ for m in addon_utils.modules() if "fract" in m.__name__.lower()])
print("collections", [c.name for c in bpy.data.collections][:40])


def meshes(c):
    return [o for o in c.all_objects if o.type == "MESH"]


allm = []
for name in ("Car_Visual", "Car_Interior"):
    c = bpy.data.collections.get(name)
    if not c:
        continue
    ob = meshes(c)
    allm += ob
    dg = bpy.context.evaluated_depsgraph_get()
    tris = verts = loops = 0
    for o in ob:
        e = o.evaluated_get(dg)
        m = e.to_mesh()
        m.calc_loop_triangles()
        tris += len(m.loop_triangles)
        verts += len(m.vertices)
        loops += len(m.loops)
        e.to_mesh_clear()
    print(name, len(ob), "meshes; evaluated verts", verts, "loops", loops, "tris", tris)
mats = {}
for o in allm:
    for s in o.material_slots:
        if s.material:
            mats.setdefault(s.material.name, 0)
            mats[s.material.name] += 1
print(len(mats), "materials")
for k in sorted(mats):
    m = bpy.data.materials[k]
    bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if m.use_nodes else None
    tex = [n.image.name for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image] if m.use_nodes else []
    if bsdf:
        bc = bsdf.inputs["Base Color"].default_value
        print(f"  {k:34s} base ({bc[0]:.2f},{bc[1]:.2f},{bc[2]:.2f}) metal {bsdf.inputs['Metallic'].default_value:.2f} "
              f"rough {bsdf.inputs['Roughness'].default_value:.2f} alpha {bsdf.inputs['Alpha'].default_value:.2f} "
              f"trans {bsdf.inputs['Transmission Weight'].default_value if 'Transmission Weight' in bsdf.inputs else 0:.2f} "
              f"links {[l.to_socket.name for l in m.node_tree.links if l.to_node == bsdf]} tex {tex}")
    else:
        print("  ", k, "no principled")
mods = {}
for o in allm:
    for md in o.modifiers:
        mods[md.type] = mods.get(md.type, 0) + 1
print("modifiers", mods)
