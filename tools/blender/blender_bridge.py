"""Direct client for the MCP for Blender add-on socket (the Blender side of the MCP link).

The Mirasim session that runs this project no longer lists an MCP server for port 9876
(only other projects' Blender instances), so this script speaks the add-on's own JSON
socket protocol - the same commands the mcp-for-blender server sends - to the project
Blender on 127.0.0.1:9876. See docs/decisions.md (D-001).

Usage (run from the project root):
  python -I tools/blender/blender_bridge.py ping
  python -I tools/blender/blender_bridge.py cmd get_addon_info
  python -I tools/blender/blender_bridge.py cmd get_viewport_screenshot "{\"filepath\": \"W:/x.png\", \"max_size\": 1200}"
  python -I tools/blender/blender_bridge.py exec tools/blender/some_script.py --args "{\"key\": 1}"
  python -I tools/blender/blender_bridge.py call hcar.build_body:main --args "{\"lod\": 0}"

`exec` sends a script file verbatim (with `ARGS` predefined). `call` imports a module from
tools/blender (fresh import every time, so edits are picked up) and prints the JSON result
of `function(**ARGS)`. Before connecting, the bridge reports any other process holding a
connection to the port (`--strict` refuses to run in that case).
"""
import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

HOST = "127.0.0.1"
DEFAULT_PORT = 9876
TOOLS_BLENDER = Path(__file__).resolve().parent


def foreign_clients(port):
    """PIDs of processes with an established TCP connection to HOST:port (Windows netstat)."""
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, timeout=15).stdout
    except Exception as exc:  # netstat missing or slow: do not block the call
        return {"error": str(exc)}
    pids = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[3] == "ESTABLISHED" and parts[2] == f"{HOST}:{port}":
            pids.add(int(parts[4]))
    pids.discard(os.getpid())
    return sorted(pids)


def send(command, port=DEFAULT_PORT, timeout=180.0):
    """Send one command dict and return the decoded response dict."""
    with socket.create_connection((HOST, port), timeout=10.0) as sock:
        sock.sendall(json.dumps(command).encode("utf-8"))
        sock.settimeout(timeout)
        buf = b""
        deadline = time.monotonic() + timeout
        while True:
            chunk = sock.recv(1 << 20)
            if not chunk:
                break
            buf += chunk
            try:
                return json.loads(buf.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                if time.monotonic() > deadline:
                    raise TimeoutError("incomplete response from Blender")
                continue
    raise ConnectionError(f"connection closed after {len(buf)} bytes without a complete response")


def call_code(module_func, args):
    module, _, func = module_func.partition(":")
    func = func or "main"
    return (
        "import sys, importlib, json\n"
        f"_root = {str(TOOLS_BLENDER)!r}\n"
        "if _root not in sys.path:\n"
        "    sys.path.insert(0, _root)\n"
        f"_pkg = {module.split('.')[0]!r}\n"
        "for _m in [m for m in list(sys.modules) if m == _pkg or m.startswith(_pkg + '.')]:\n"
        "    del sys.modules[_m]\n"
        f"_mod = importlib.import_module({module!r})\n"
        f"_res = getattr(_mod, {func!r})(**json.loads({json.dumps(args)!r}))\n"
        "print('@@RESULT@@' + json.dumps(_res, default=str))\n"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["ping", "cmd", "exec", "call"])
    ap.add_argument("target", nargs="?", help="command type, script path, or module:function")
    ap.add_argument("params", nargs="?", default="{}", help="JSON params for cmd")
    ap.add_argument("--args", default="{}", help="JSON object passed as ARGS / keyword arguments")
    ap.add_argument("--args-file", help="read the JSON arguments from a file (avoids shell quoting issues)")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--strict", action="store_true", help="refuse when another process is connected")
    ns = ap.parse_args()
    if ns.args_file:
        ns.args = Path(ns.args_file).read_text(encoding="utf-8-sig")
    json.loads(ns.args)  # fail early on malformed arguments

    others = foreign_clients(ns.port)
    if others:
        print(json.dumps({"warning": "other clients connected to the Blender port", "pids": others}), file=sys.stderr)
        if ns.strict:
            return 3

    if ns.mode == "ping":
        command = {"type": "ping", "params": {}}
    elif ns.mode == "cmd":
        command = {"type": ns.target, "params": json.loads(ns.params)}
    elif ns.mode == "exec":
        code = Path(ns.target).read_text(encoding="utf-8-sig")  # PowerShell writes a BOM
        code = f"import json as _json\nARGS = _json.loads({ns.args!r})\n" + code
        command = {"type": "execute_code", "params": {"code": code}}
    else:
        command = {"type": "execute_code", "params": {"code": call_code(ns.target, json.loads(ns.args))}}

    t0 = time.perf_counter()
    try:
        resp = send(command, ns.port, ns.timeout)
    except Exception as exc:
        print(json.dumps({"bridge_error": type(exc).__name__, "message": str(exc)}))
        return 2
    elapsed = time.perf_counter() - t0

    if resp.get("status") != "success":
        message = resp.get("message", resp)
        try:
            detail = json.loads(message)
            print(detail.get("traceback", message))
        except (TypeError, ValueError):
            print(message)
        return 1
    result = resp.get("result")
    if ns.mode in ("exec", "call") and isinstance(result, dict) and "result" in result:
        text = result["result"]
        if ns.mode == "call":
            m = re.search(r"@@RESULT@@(.*)$", text, re.S)
            prefix = text[: m.start()] if m else text
            if prefix.strip():
                print(prefix.rstrip())
            print(m.group(1).strip() if m else "null")
        else:
            print(text.rstrip())
    else:
        print(json.dumps(result, indent=1, default=str))
    print(f"[bridge] {ns.mode} {ns.target or ''} ok in {elapsed:.2f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
