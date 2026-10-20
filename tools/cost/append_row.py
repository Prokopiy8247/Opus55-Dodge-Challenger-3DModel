"""Append one phase row to docs/cost_log.csv from a collect_usage.py JSON.

Usage: tools/.venv/Scripts/python.exe tools/cost/append_row.py <usage.json> <phase> <timestamp_utc> <subagents> <note>
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    usage_path, phase, stamp, subagents, note = sys.argv[1:6]
    u = json.loads(Path(usage_path).read_text(encoding="utf-8"))
    pm = u["per_model"]
    tot = {k: sum(v[k] for v in pm.values()) for k in ("input_tokens", "output_tokens", "cache_write_tokens",
                                                       "cache_read_tokens")}
    row = [stamp, phase, f"{u['wall_clock_h']:.3f}", f"{u['active_h_est']:.3f}", tot["input_tokens"],
           tot["output_tokens"], tot["cache_write_tokens"], tot["cache_read_tokens"], subagents, note]
    with open(ROOT / "docs" / "cost_log.csv", "a", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerow(row)
    print(row)


if __name__ == "__main__":
    main()
