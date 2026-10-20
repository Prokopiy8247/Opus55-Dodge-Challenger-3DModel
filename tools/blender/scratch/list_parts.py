"""Parts of Car_Visual: name, material(s), evaluated triangles, thickness modifier."""
import bpy
import json

dg = bpy.context.evaluated_depsgraph_get()
rows = []
for o in sorted(bpy.data.collections["Car_Visual"].all_objects, key=lambda o: o.name):
    if o.type != "MESH":
        rows.append([o.name, o.type, "", 0, ""])
        continue
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    me.calc_loop_triangles()
    tris = len(me.loop_triangles)
    oe.to_mesh_clear()
    mats = ",".join(s.material.name for s in o.material_slots if s.material)
    sol = next((f"{m.thickness * 1000:.1f}mm" for m in o.modifiers if m.type == "SOLIDIFY"), "")
    rows.append([o.name, "MESH", mats, tris, sol])
mats = sorted({m for r in rows for m in r[2].split(",") if m})
print(json.dumps({"rows": rows, "materials": mats}))
