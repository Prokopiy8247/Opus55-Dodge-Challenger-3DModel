"""Start the MCP for Blender socket server on 127.0.0.1:9876 after Blender has opened the file.

Usage (relaunch after a crash):
    W:\\Blender\\blender.exe "<project>\\3DDodgeChallenger_vNNN.blend" --python tools\\blender\\start_mcp_server.py
A watchdog timer waits until the add-on module is loaded and the port is free, then starts the
server (same class the add-on's sidebar button uses). Telemetry consent stays off.
"""
import os
import socket
import sys

import bpy

MODULE = "blender_mcp"
PORT = 9876
_state = {"tries": 0}


def _port_busy():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.2)
    try:
        return s.connect_ex(("127.0.0.1", PORT)) == 0
    finally:
        s.close()


def _watchdog():
    _state["tries"] += 1
    srv = getattr(bpy.types, "blendermcp_server", None)
    if srv is not None and getattr(srv, "running", False):
        print(f"[start_mcp_server] running on {PORT}")
        return None
    if _state["tries"] > 120:
        print("[start_mcp_server] giving up")
        return None
    mod = sys.modules.get(MODULE)
    if mod is None or not hasattr(mod, "BlenderMCPServer") or _port_busy():
        return 1.0
    try:
        addon = bpy.context.preferences.addons.get(MODULE)
        if addon is not None and hasattr(addon.preferences, "telemetry_consent"):
            addon.preferences.telemetry_consent = False
        srv = mod.BlenderMCPServer(port=PORT)
        bpy.types.blendermcp_server = srv
        srv.start()
        try:
            bpy.context.scene.blendermcp_server_running = srv.running
        except Exception:
            pass
        print(f"[start_mcp_server] started on {PORT}")
    except Exception as exc:
        print(f"[start_mcp_server] start failed: {exc}")
    return 1.0


os.environ["BLENDERMCP_NO_UPDATE_CHECK"] = "1"
bpy.app.timers.register(_watchdog, first_interval=2.0, persistent=True)
