"""P0 step 2: report what the working file contains and save a "before" screenshot.

Read-only for scene data. The only side effect is one PNG of the whole Blender
window written by bpy.ops.screen.screenshot into docs\\video_assets\\P0\\.
Sent verbatim through the Blender MCP (safe mode: no os/open/exec/lambda).
"""
import bpy
import json

PROJECT_DIR = "W:\\YouTube\\3D Model Dodge Challenger\\"
SHOT = PROJECT_DIR + "docs\\video_assets\\P0\\2026-10-10_P0_blender_initial_scene.png"


def rounded(vec):
    return [round(v, 4) for v in vec]


scene = bpy.context.scene
units = scene.unit_settings
report = {
    "file": bpy.data.filepath,
    "dirty": bpy.data.is_dirty,
    "blender": bpy.app.version_string,
    "scenes": [s.name for s in bpy.data.scenes],
    "collections": [c.name for c in bpy.data.collections],
    "objects": [
        {
            "name": o.name,
            "type": o.type,
            "collections": [c.name for c in o.users_collection],
            "location": rounded(o.location),
            "dimensions": rounded(o.dimensions),
        }
        for o in bpy.data.objects
    ],
    "counts": {
        "meshes": len(bpy.data.meshes),
        "materials": len(bpy.data.materials),
        "images": len(bpy.data.images),
        "node_groups": len(bpy.data.node_groups),
        "actions": len(bpy.data.actions),
        "worlds": len(bpy.data.worlds),
        "cameras": len(bpy.data.cameras),
        "lights": len(bpy.data.lights),
    },
    "materials": [m.name for m in bpy.data.materials],
    "images": [i.name for i in bpy.data.images],
    "units": {
        "system": units.system,
        "scale_length": units.scale_length,
        "length_unit": units.length_unit,
        "mass_unit": units.mass_unit,
    },
    "render": {
        "engine": scene.render.engine,
        "fps": scene.render.fps,
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
    },
    "frame_range": [scene.frame_start, scene.frame_end],
    "world": scene.world.name if scene.world else None,
    "addons": sorted(bpy.context.preferences.addons.keys()),
}

shot = {"path": SHOT, "ok": False}
try:
    win = bpy.context.window_manager.windows[0]
    biggest = None
    for area in win.screen.areas:
        if biggest is None or area.width * area.height > biggest.width * biggest.height:
            biggest = area
    with bpy.context.temp_override(window=win, screen=win.screen, area=biggest):
        bpy.ops.screen.screenshot(filepath=SHOT, check_existing=False)
    shot["ok"] = True
except Exception as exc:
    shot["error"] = str(exc)
report["screenshot"] = shot
print(json.dumps(report))
