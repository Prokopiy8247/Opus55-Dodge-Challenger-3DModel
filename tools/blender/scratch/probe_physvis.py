import bpy, json

out = {}
for o in bpy.data.objects:
    if o.name.startswith("PH_"):
        out[o.name] = {"cols": [c.name for c in o.users_collection], "hide_render": o.hide_render,
                       "hide_viewport": o.hide_viewport, "hide_get": o.hide_get() if o.name in bpy.context.view_layer.objects else "not in layer",
                       "verts": len(o.data.vertices) if o.type == "MESH" else 0, "mods": [m.type for m in o.modifiers]}


def walk(lc, depth=0, acc=None):
    acc = acc if acc is not None else []
    acc.append(("  " * depth) + f"{lc.name} exclude={lc.exclude} hide={lc.hide_viewport}")
    for c in lc.children:
        walk(c, depth + 1, acc)
    return acc


out["layers"] = walk(bpy.context.view_layer.layer_collection)
print(json.dumps(out, indent=0)[:4000])
