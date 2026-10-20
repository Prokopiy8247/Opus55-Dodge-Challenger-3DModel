"""P0 step 1: save the open original file as 3DDodgeChallenger_v001.blend.

The original 3DDodgeChallenger.blend must never be overwritten. This script is
idempotent: when the session already points at v001 it only reports, and it
refuses to act when any other file is open.

Sent verbatim through the Blender MCP (execute_blender_code). The server runs in
safe mode (no os/open/exec), so the caller checks on disk that the v001 target
does not exist yet before sending this script.
"""
import bpy
import json

PROJECT_DIR = "W:\\YouTube\\3D Model Dodge Challenger\\"
ORIGINAL = PROJECT_DIR + "3DDodgeChallenger.blend"
TARGET = PROJECT_DIR + "3DDodgeChallenger_v001.blend"


def norm(p):
    return p.replace("/", "\\").lower()


status = {
    "blender": bpy.app.version_string,
    "file_before": bpy.data.filepath,
    "dirty_before": bpy.data.is_dirty,
}
if norm(bpy.data.filepath) == norm(TARGET):
    status["action"] = "already_on_v001"
elif norm(bpy.data.filepath) == norm(ORIGINAL):
    bpy.ops.wm.save_as_mainfile(filepath=TARGET, check_existing=False, copy=False)
    status["action"] = "saved_as_v001"
else:
    status["action"] = "refused_unexpected_file"
status["file_after"] = bpy.data.filepath
status["dirty_after"] = bpy.data.is_dirty
print(json.dumps(status))
