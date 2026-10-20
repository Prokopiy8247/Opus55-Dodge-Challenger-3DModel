"""Prints sections of sim/vehicle/<vehicle>/params.json (comments stripped).

Usage: tools/.venv/Scripts/python.exe tools/p3b/params_view.py [section ...] [--vehicle hellcat]
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def strip_comments(text):
    out, i, in_str = [], 0, False
    while i < len(text):
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < len(text):
                i += 1
                out.append(text[i])
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
            out.append(ch)
        elif ch == "/" and i + 1 < len(text) and text[i + 1] == "/":
            while i < len(text) and text[i] != "\n":
                i += 1
            out.append("\n")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def load(vehicle="hellcat"):
    return json.loads(strip_comments((ROOT / "sim/vehicle" / vehicle / "params.json").read_text(encoding="utf-8")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sections", nargs="*")
    ap.add_argument("--vehicle", default="hellcat")
    ns = ap.parse_args()
    p = load(ns.vehicle)
    if not ns.sections:
        print(list(p.keys()))
        return
    for s in ns.sections:
        if s == "materials":
            print("materials:", [m["name"] for m in p["materials"]])
            continue
        if ":" in s:
            sec, name = s.split(":", 1)
            print(json.dumps([m for m in p[sec] if m.get("name") == name], indent=1))
            continue
        print(s, json.dumps(p.get(s), indent=1))


if __name__ == "__main__":
    main()
