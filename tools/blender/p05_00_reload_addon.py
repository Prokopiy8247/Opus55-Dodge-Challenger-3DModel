"""Re-enable the MCP for Blender add-on after its file was replaced (1.7 -> verified 1.8).

Sent through blender_bridge.py `exec`. The reload cannot run inside the command that
asks for it (disabling the add-on stops the socket server that is answering), so this
script only schedules a one-shot timer and returns. The timer:
  1. disables the add-on and drops the cached module,
  2. enables it again from disk (the new file),
  3. forces telemetry consent off before the server starts,
  4. keeps a watchdog timer running until a server is listening on the port again,
  5. saves the user preferences so consent stays off.
The online update check of the add-on is suppressed (BLENDERMCP_NO_UPDATE_CHECK) because
the add-on is updated only from the verified local file.
"""
import bpy
import json
import os
import sys
import socket
import addon_utils

MODULE = "blender_mcp"
PORT = 9876
LOG = []


def _log(msg):
    LOG.append(msg)
    print("[reload_addon] " + msg)


def _port_busy():
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.settimeout(0.2)
    try:
        return probe.connect_ex(("127.0.0.1", PORT)) == 0
    finally:
        probe.close()


_state = {"tries": 0}


def _watchdog():
    _state["tries"] += 1
    server = getattr(bpy.types, "blendermcp_server", None)
    running = bool(server is not None and server.running)
    if running:
        _log(f"server running on {getattr(server, 'port', '?')} after {_state['tries']} checks")
        try:
            bpy.ops.wm.save_userpref()
            _log("user preferences saved")
        except Exception as exc:
            _log(f"save_userpref failed: {exc}")
        return None
    if _state["tries"] > 60:
        _log("giving up: server did not start")
        return None
    if not _port_busy():
        mod = sys.modules.get(MODULE)
        if mod is not None and hasattr(mod, "BlenderMCPServer"):
            try:
                srv = mod.BlenderMCPServer(port=PORT)
                bpy.types.blendermcp_server = srv
                srv.start()
                bpy.context.scene.blendermcp_server_running = srv.running
                _log("server started by watchdog")
            except Exception as exc:
                _log(f"watchdog start failed: {exc}")
    return 1.0


def _reload():
    os.environ["BLENDERMCP_NO_UPDATE_CHECK"] = "1"
    try:
        addon_utils.disable(MODULE, default_set=True)
        _log("disabled old add-on")
    except Exception as exc:
        _log(f"disable failed: {exc}")
    sys.modules.pop(MODULE, None)
    try:
        addon_utils.modules_refresh()
    except Exception:
        pass
    mod = addon_utils.enable(MODULE, default_set=True, persistent=True)
    _log(f"enabled: {getattr(mod, 'bl_info', {}).get('version')} protocol {getattr(mod, 'ADDON_PROTOCOL_VERSION', None)}")
    addon = bpy.context.preferences.addons.get(MODULE)
    if addon is not None:
        addon.preferences.telemetry_consent = False
        _log("telemetry consent set to False")
    bpy.app.timers.register(_watchdog, first_interval=1.0)
    return None


bpy.app.timers.register(_reload, first_interval=1.5)
print(json.dumps({"scheduled": True, "module": MODULE, "port": PORT}))
