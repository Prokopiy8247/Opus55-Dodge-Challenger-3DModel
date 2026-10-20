"""Sum token usage and timing from the Claude Code transcripts of this project.

Reads every *.jsonl transcript under the project's Claude Code folder (main sessions and
sub-agents), de-duplicates streamed records by message id (last record wins), and reports
per-model totals, wall-clock span and an estimate of active time (gaps longer than
--idle-gap minutes between consecutive records are treated as idle).

Usage:
  tools/.venv/Scripts/python.exe tools/cost/collect_usage.py [--since ISO] [--until ISO] [--json out.json]
"""
import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path.home() / ".claude" / "projects" / "W--YouTube-3D-Model-Dodge-Challenger"


def parse_ts(text):
    if not text:
        return None
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def iter_records(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def collect(since=None, until=None, idle_gap_min=10.0):
    messages = {}  # message id -> (timestamp, model, usage, source)
    stamps = []
    files = sorted(PROJECT_DIR.rglob("*.jsonl"))
    for path in files:
        source = "subagent" if "subagents" in path.parts else "main"
        for rec in iter_records(path):
            ts = parse_ts(rec.get("timestamp"))
            if ts is None:
                continue
            if since and ts < since:
                continue
            if until and ts > until:
                continue
            stamps.append(ts)
            msg = rec.get("message") or {}
            usage = msg.get("usage")
            if rec.get("type") != "assistant" or not usage:
                continue
            mid = msg.get("id") or rec.get("uuid")
            messages[mid] = (ts, msg.get("model", "unknown"), usage, source)

    totals = defaultdict(lambda: defaultdict(int))
    for ts, model, usage, source in messages.values():
        key = f"{model} ({source})"
        t = totals[key]
        t["messages"] += 1
        t["input_tokens"] += int(usage.get("input_tokens") or 0)
        t["output_tokens"] += int(usage.get("output_tokens") or 0)
        t["cache_write_tokens"] += int(usage.get("cache_creation_input_tokens") or 0)
        t["cache_read_tokens"] += int(usage.get("cache_read_input_tokens") or 0)

    stamps.sort()
    wall_h = active_h = 0.0
    if stamps:
        wall_h = (stamps[-1] - stamps[0]).total_seconds() / 3600
        for a, b in zip(stamps, stamps[1:]):
            gap = (b - a).total_seconds()
            if gap <= idle_gap_min * 60:
                active_h += gap / 3600
    return {
        "files": [str(p) for p in files],
        "first": stamps[0].isoformat() if stamps else None,
        "last": stamps[-1].isoformat() if stamps else None,
        "wall_clock_h": round(wall_h, 3),
        "active_h_est": round(active_h, 3),
        "idle_gap_rule_min": idle_gap_min,
        "per_model": {k: dict(v) for k, v in totals.items()},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--idle-gap", type=float, default=10.0)
    ap.add_argument("--json")
    ns = ap.parse_args()
    since = parse_ts(ns.since) if ns.since else None
    until = parse_ts(ns.until) if ns.until else None
    if since and since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    if until and until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    result = collect(since, until, ns.idle_gap)
    text = json.dumps(result, indent=2)
    if ns.json:
        Path(ns.json).parent.mkdir(parents=True, exist_ok=True)
        Path(ns.json).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
