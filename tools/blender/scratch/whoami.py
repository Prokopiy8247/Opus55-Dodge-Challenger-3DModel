import bpy
print({"file": bpy.data.filepath, "objects": len(bpy.data.objects), "version": bpy.app.version_string})
