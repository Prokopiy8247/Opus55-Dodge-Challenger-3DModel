"""Hellcat soft-body sandbox: Blender-side authoring package (car model, physics skeleton, export).

Imported through tools/blender/blender_bridge.py `call hcar.<module>:<function>`; every call
re-imports the package, so edits are picked up without restarting Blender.

Frames: Blender authoring frame is metric, Z up, car forward = +Y, +X = car right.
The exported simulation frame is Unity's: x right, y up, z forward (u = (bx, bz, by)).
"""

PROJECT_ROOT = "W:/YouTube/3D Model Dodge Challenger"
