"""Final cost report (brief section 18): docs/cost_report.md from the Claude Code transcripts of this project.

Reads every transcript (main sessions and sub-agents, de-duplicated by message id as in collect_usage.py) and splits the
records into the phases of docs/cost_log.csv (each row's timestamp ends its phase; P0 starts at the first record). Per
phase and in total: wall-clock time, active time (gaps longer than --idle-gap minutes between consecutive records are
idle), tokens by type and model - cache writes split by their time to live (5 minutes / 1 hour, from usage.cache_creation)
- and the API-equivalent cost at the official price list (PRICES below, with its source and date). Also counts the tool
calls that ran the long jobs: Unity batch runs, player runs, Blender calls, sub-agents, and the code written.

Usage: tools/.venv/Scripts/python.exe tools/cost/make_cost_report.py [--until ISO] [--idle-gap 10]
Output: docs/cost_report.md, docs/cost/usage_total.json
"""
import argparse
import csv
import json
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from collect_usage import PROJECT_DIR, iter_records, parse_ts

ROOT = Path(__file__).resolve().parents[2]

# Official Anthropic API prices, USD per million tokens (https://platform.claude.com/docs/en/about-claude/pricing, read
# 2026-10-15): Claude Opus 5.5 - base input $4, 5-minute cache writes $5, 1-hour cache writes $8, cache hits and refreshes
# $0.20, output $20; the full 1M context at standard prices (no long-context surcharge); global routing (no inference_geo,
# no 1.1x); standard speed (no fast mode); no Batch API use.
PRICES = {
    "claude-opus-5-5": {"input": 4.00, "cache_write_5m": 5.00, "cache_write_1h": 8.00, "cache_read": 0.20, "output": 20.00},
}
PRICE_SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing"
PRICE_DATE = "2026-10-15"
TOKEN_KEYS = ("input", "output", "cache_write_5m", "cache_write_1h", "cache_read")


def load_phases():
    rows = list(csv.DictReader(open(ROOT / "docs/cost_log.csv", encoding="utf-8")))
    return [(r["phase"], parse_ts(r["timestamp_utc"])) for r in rows]


def scan(until, idle_gap_min):
    messages = {}   # message id -> (ts, model, source, usage)
    stamps = []
    tools = []      # (ts, name, text)
    files = sorted(PROJECT_DIR.rglob("*.jsonl"))
    for path in files:
        source = "subagent" if "subagents" in path.parts else "main"
        for rec in iter_records(path):
            ts = parse_ts(rec.get("timestamp"))
            if ts is None or (until and ts > until):
                continue
            stamps.append(ts)
            msg = rec.get("message") or {}
            if rec.get("type") != "assistant":
                continue
            usage = msg.get("usage")
            mid = msg.get("id") or rec.get("uuid")
            if usage:
                messages[mid] = (ts, msg.get("model", "unknown"), source, usage)
            content = msg.get("content")
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        inp = b.get("input") or {}
                        text = " ".join(str(v) for v in inp.values() if isinstance(v, str))
                        tools.append((ts, mid, b.get("id"), b.get("name", ""), text))
    stamps.sort()
    # tool calls are repeated in streamed records: keep one per tool_use id
    seen, uniq = set(), []
    for t in tools:
        if t[2] in seen:
            continue
        seen.add(t[2])
        uniq.append(t)
    return files, messages, stamps, uniq


def tokens(u):
    cc = u.get("cache_creation") or {}
    w1h = int(cc.get("ephemeral_1h_input_tokens") or 0)
    w5m = int(cc.get("ephemeral_5m_input_tokens") or 0)
    total_w = int(u.get("cache_creation_input_tokens") or 0)
    if w1h + w5m < total_w:   # records without the split: count the rest as 5-minute writes (the cheaper, conservative)
        w5m += total_w - w1h - w5m
    return {"input": int(u.get("input_tokens") or 0), "output": int(u.get("output_tokens") or 0),
            "cache_write_5m": w5m, "cache_write_1h": w1h, "cache_read": int(u.get("cache_read_input_tokens") or 0)}


def cost(model, t):
    p = PRICES.get(model)
    if p is None:
        return 0.0
    return sum(t[k] * p[k] for k in TOKEN_KEYS) / 1e6


def active_hours(stamps, gap_min):
    h = 0.0
    for a, b in zip(stamps, stamps[1:]):
        g = (b - a).total_seconds()
        if g <= gap_min * 60:
            h += g / 3600
    return h


def count_lines():
    groups = {
        "Unity C# (solver, game, editor tools)": ["Unity/HellcatSandbox/Assets/Sim/**/*.cs", "Unity/HellcatSandbox/Assets/Game/**/*.cs",
                                                  "Unity/HellcatSandbox/Assets/Editor/**/*.cs"],
        "Unity shaders": ["Unity/HellcatSandbox/Assets/**/*.shader", "Unity/HellcatSandbox/Assets/**/*.hlsl",
                          "Unity/HellcatSandbox/Assets/**/*.compute"],
        "Blender Python (hcar package, scripts)": ["tools/blender/**/*.py"],
        "Python tools (gates, analysis, skeleton design, cost)": ["tools/*.py", "tools/cost/*.py", "tools/p*/**/*.py", "tools/skeleton/**/*.py",
                                                                  "tools/ref/**/*.py", "tools/textures/**/*.py", "tools/unity/**/*.py"],
        "PowerShell scripts": ["tools/**/*.ps1"],
    }
    tracked = set(subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines())
    out = {}
    for name, pats in groups.items():
        files = set()
        for pat in pats:
            for f in ROOT.glob(pat):
                rel = f.relative_to(ROOT).as_posix()
                if f.is_file() and rel in tracked and "/.venv/" not in rel and "/Library/" not in rel:
                    files.add(f)
        lines = sum(len(f.read_text(encoding="utf-8", errors="replace").splitlines()) for f in files)
        out[name] = (len(files), lines)
    return out, len(tracked)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--until")
    ap.add_argument("--idle-gap", type=float, default=10.0)
    ns = ap.parse_args()
    until = parse_ts(ns.until) if ns.until else None
    phases = load_phases()
    files, messages, stamps, tools = scan(until, ns.idle_gap)
    first, last = stamps[0], stamps[-1]

    def phase_of(ts):
        for name, end in phases:
            if ts <= end:
                return name
        return "after"

    # per phase and model
    per = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for ts, model, source, u in messages.values():
        if model == "<synthetic>":
            continue
        t = tokens(u)
        key = f"{model} ({source})"
        d = per[phase_of(ts)][key]
        d["messages"] += 1
        for k in TOKEN_KEYS:
            d[k] += t[k]
    phase_stamps = defaultdict(list)
    for ts in stamps:
        phase_stamps[phase_of(ts)].append(ts)
    order = [p for p, _ in phases] + (["after"] if per.get("after") else [])

    tool_counts = defaultdict(lambda: defaultdict(int))
    for ts, mid, tid, name, text in tools:
        ph = phase_of(ts)
        if name in ("Bash", "PowerShell"):
            if "run_unity_batch" in text:
                tool_counts[ph]["unity_batch_calls"] += 1
            if re.search(r"run_player\.ps1|run_scenarios\.ps1|run_all_p6\.ps1|run_p7\.ps1|run_suites\.ps1|Builds[\\/][^ '\"]*\.exe", text):
                tool_counts[ph]["player_run_calls"] += 1
            if re.search(r"blender_bridge\.py|bcall\.ps1|blender_bg\.py|export_all\.py", text):
                tool_counts[ph]["blender_calls"] += 1
        elif "blender" in name.lower():
            tool_counts[ph]["blender_calls"] += 1
        if name in ("Agent", "Task"):
            tool_counts[ph]["subagents"] += 1
        tool_counts[ph]["tool_calls"] += 1

    lines, tracked = count_lines()

    # totals
    tot = defaultdict(lambda: defaultdict(int))
    for ph in order:
        for key, d in per[ph].items():
            for k, v in d.items():
                tot[key][k] += v
    total_cost = sum(cost(k.split(" ")[0], v) for k, v in tot.items())
    wall_h = (last - first).total_seconds() / 3600
    act_h = active_hours(stamps, ns.idle_gap)

    data = {"first": first.isoformat(), "last": last.isoformat(), "wall_clock_h": wall_h, "active_h": act_h, "idle_gap_min": ns.idle_gap,
            "transcripts": [str(f) for f in files], "prices": PRICES, "price_source": PRICE_SOURCE, "price_date": PRICE_DATE,
            "per_model": {k: dict(v) for k, v in tot.items()}, "cost_usd": total_cost,
            "phases": {ph: {"wall_h": ((phase_stamps[ph][-1] - phase_stamps[ph][0]).total_seconds() / 3600) if phase_stamps[ph] else 0.0,
                            "active_h": active_hours(phase_stamps[ph], ns.idle_gap),
                            "per_model": {k: dict(v) for k, v in per[ph].items()},
                            "cost_usd": sum(cost(k.split(" ")[0], v) for k, v in per[ph].items()),
                            "tools": dict(tool_counts[ph])} for ph in order},
            "code": {k: {"files": v[0], "lines": v[1]} for k, v in lines.items()}, "tracked_files": tracked}
    (ROOT / "docs/cost").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs/cost/usage_total.json").write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
    write_md(data, order)
    print(f"total ${total_cost:,.2f}; wall {wall_h:.1f} h, active {act_h:.1f} h -> docs/cost_report.md")


def fm(n):
    return f"{n:,.0f}".replace(",", " ")


def write_md(d, order):
    p = d["prices"]["claude-opus-5-5"]
    tot = d["per_model"]
    allk = defaultdict(int)
    for v in tot.values():
        for k in TOKEN_KEYS + ("messages",):
            allk[k] += v.get(k, 0)
    sub = {k: v for k, v in tot.items() if "(subagent)" in k}
    main = {k: v for k, v in tot.items() if "(main)" in k}
    c_main = sum(cost(k.split(" ")[0], v) for k, v in main.items())
    c_sub = sum(cost(k.split(" ")[0], v) for k, v in sub.items())
    tools_tot = defaultdict(int)
    for ph in order:
        for k, v in d["phases"][ph]["tools"].items():
            tools_tot[k] += v
    md = []
    md += ["# Cost report (brief section 18)", "",
           f"Data: the Claude Code transcripts of this project ({len(d['transcripts'])} files: main sessions and sub-agents) from "
           f"{d['first'][:19]}Z to {d['last'][:19]}Z, read by `tools/cost/make_cost_report.py`; raw rows per phase in "
           "`docs/cost_log.csv`, totals in `docs/cost/usage_total.json`. All money figures are an **API-equivalent estimate** at "
           "the official Anthropic API list prices - not the user's actual subscription billing.", ""]

    def k_(x):
        return x.get

    md += ["## Итоговая таблица (summary, Russian)", "",
           "| Показатель | Значение |", "|---|---|",
           f"| Календарное время от первого сообщения до финала | {d['wall_clock_h']:.1f} ч ({d['wall_clock_h'] / 24:.1f} сут) |",
           f"| Активное время агента (паузы > {d['idle_gap_min']:.0f} мин не считаются) | {d['active_h']:.1f} ч |",
           f"| Модель | Claude Opus 5.5 (`claude-opus-5-5`): основная сессия и суб-агенты |",
           f"| Входные токены (без кэша) | {fm(allk['input'])} |",
           f"| Выходные токены | {fm(allk['output'])} |",
           f"| Запись в кэш (5 мин / 1 ч) | {fm(allk['cache_write_5m'])} / {fm(allk['cache_write_1h'])} |",
           f"| Чтение из кэша | {fm(allk['cache_read'])} |",
           f"| Стоимость по ценам API (эквивалент) | **${d['cost_usd']:,.2f}** (основная сессия ${c_main:,.2f}, суб-агенты ${c_sub:,.2f}) |",
           f"| Фаз выполнено | {len([o for o in order if o != 'after'])} (P0, P0.5, P1, P1b, P2, P3, P3b, P4, P4b, P5, P6, P7) |",
           f"| Строк кода (в git) | {fm(sum(v['lines'] for v in d['code'].values()))} в {fm(sum(v['files'] for v in d['code'].values()))} файлах |",
           f"| Запусков Unity в batch-режиме / плеера / вызовов Blender | {tools_tot['unity_batch_calls']} / {tools_tot['player_run_calls']} / {tools_tot['blender_calls']} (вызовы инструментов агента) |",
           ""]

    md += ["## 1. Time", "",
           f"- **Wall-clock** from the first transcript record to the last: **{d['wall_clock_h']:.1f} h** ({d['wall_clock_h'] / 24:.1f} days). It "
           "includes the nights and the breaks between sessions (the autonomy mode ran without waiting for the user, but sessions "
           "ended and resumed).",
           f"- **Active agent time: {d['active_h']:.1f} h.** Rule: the sum of the gaps between consecutive transcript records, leaving "
           f"out every gap longer than {d['idle_gap_min']:.0f} minutes. Long background jobs (Unity builds, crash series, test suites) "
           "that ran more than 10 minutes without a record therefore count as idle; the time they took is in the job counts below.",
           "", "| Phase | Wall-clock h | Active h | Messages | Tool calls | Unity batch | Player runs | Blender calls | Sub-agents |",
           "|---|---|---|---|---|---|---|---|---|"]
    for ph in order:
        x = d["phases"][ph]
        msgs = sum(v.get("messages", 0) for v in x["per_model"].values())
        t = x["tools"]
        md.append(f"| {ph} | {x['wall_h']:.1f} | {x['active_h']:.1f} | {msgs} | {t.get('tool_calls', 0)} | {t.get('unity_batch_calls', 0)} | "
                  f"{t.get('player_run_calls', 0)} | {t.get('blender_calls', 0)} | {t.get('subagents', 0)} |")
    md += ["", "Phase wall-clock is first to last record inside the phase (the gaps between phases are not in any row). The job "
           "columns count the agent's tool calls that started such jobs (a call may run a whole series, e.g. one `run_all_p6.ps1` "
           "call ran 33 scenario runs).", ""]

    md += ["## 2. Tokens", "", "| Model (context) | Messages | Input | Output | Cache write 5 min | Cache write 1 h | Cache read |",
           "|---|---|---|---|---|---|---|"]
    for k, v in sorted(tot.items()):
        md.append(f"| {k} | {fm(v.get('messages', 0))} | {fm(v['input'])} | {fm(v['output'])} | {fm(v['cache_write_5m'])} | {fm(v['cache_write_1h'])} | {fm(v['cache_read'])} |")
    md.append(f"| **total** | {fm(allk['messages'])} | {fm(allk['input'])} | {fm(allk['output'])} | {fm(allk['cache_write_5m'])} | {fm(allk['cache_write_1h'])} | {fm(allk['cache_read'])} |")
    md += ["", "Per phase (all models):", "", "| Phase | Input | Output | Cache write 5 min | Cache write 1 h | Cache read | API-equivalent USD |",
           "|---|---|---|---|---|---|---|"]
    for ph in order:
        x = d["phases"][ph]
        s = defaultdict(int)
        for v in x["per_model"].values():
            for k in TOKEN_KEYS:
                s[k] += v.get(k, 0)
        md.append(f"| {ph} | {fm(s['input'])} | {fm(s['output'])} | {fm(s['cache_write_5m'])} | {fm(s['cache_write_1h'])} | {fm(s['cache_read'])} | ${x['cost_usd']:,.2f} |")
    md += [f"| **total** | {fm(allk['input'])} | {fm(allk['output'])} | {fm(allk['cache_write_5m'])} | {fm(allk['cache_write_1h'])} | "
           f"{fm(allk['cache_read'])} | **${d['cost_usd']:,.2f}** |", ""]

    md += ["## 3. Money (API-equivalent)", "",
           f"Prices: official Anthropic API price list, {PRICE_SOURCE}, read on {PRICE_DATE}, Claude Opus 5.5 in USD per million tokens:",
           "", "| Base input | 5-minute cache write | 1-hour cache write | Cache hit / refresh | Output |", "|---|---|---|---|---|",
           f"| ${p['input']:.2f} | ${p['cache_write_5m']:.2f} | ${p['cache_write_1h']:.2f} | ${p['cache_read']:.2f} | ${p['output']:.2f} |", "",
           "The full 1M-token context window is billed at standard prices for this model (no long-context surcharge); the sessions "
           "used global routing (no `inference_geo`, so no 1.1x data-residency multiplier), standard speed (no fast mode) and no "
           "Batch API, so no other modifier applies.", "",
           "Formula: cost = (input x 4.00 + cache write 5 min x 5.00 + cache write 1 h x 8.00 + cache read x 0.20 + output x 20.00) / 1,000,000.",
           ""]
    for k, v in sorted(tot.items()):
        terms = [(v['input'], p['input']), (v['cache_write_5m'], p['cache_write_5m']), (v['cache_write_1h'], p['cache_write_1h']),
                 (v['cache_read'], p['cache_read']), (v['output'], p['output'])]
        parts = " + ".join(f"{fm(n)} x {pr:.2f}" for n, pr in terms)
        md.append(f"- **{k}:** ({parts}) / 1e6 = **${cost(k.split(' ')[0], v):,.2f}**")
    share = {kk: sum(tot[k][kk] for k in tot) * p[kk] / 1e6 for kk in TOKEN_KEYS}
    md += ["", f"**Total: ${d['cost_usd']:,.2f}.** By token type: " + ", ".join(
        f"{n} ${share[k]:,.2f} ({100 * share[k] / max(d['cost_usd'], 1e-9):.0f} %)" for k, n in
        (("cache_read", "cache reads"), ("cache_write_1h", "1-hour cache writes"), ("cache_write_5m", "5-minute cache writes"),
         ("output", "output"), ("input", "uncached input"))) + ". Without prompt caching the same input would have cost about "
        f"${(sum(tot[k]['cache_read'] + tot[k]['cache_write_5m'] + tot[k]['cache_write_1h'] + tot[k]['input'] for k in tot) * p['input'] / 1e6 + share['output']):,.0f}.",
        ""]

    md += ["## 4. Uncertainty", "",
           "- **Exact:** the token counts. They are the `usage` fields the API returned for every assistant message, summed after "
           "de-duplicating streamed records by message id. The prices are the published list prices.",
           "- **Estimated:** the active time (the 10-minute gap rule) and the phase boundaries (each phase ends at its `docs/cost_log.csv` "
           "timestamp). The job counts are tool calls, not individual runs.",
           "- **Exact as well:** the cache writes' time to live. Every record splits its writes into 5-minute and 1-hour ones "
           "(`usage.cache_creation`); the early sessions wrote 5-minute entries, the later ones 1-hour entries.",
           "- **Missing:**",
           "  - transcripts deleted or kept outside this project's Claude Code folder (none known);",
           "  - costs outside the model: the Unity licence, electricity, the user's subscription.",
           "- **Not the bill:** the user's actual charges depend on their Claude subscription, not on these list prices.", ""]

    md += ["## 5. Context", "", f"- Phases completed: P0, P0.5, P1, P1b, P2, P3, P3b, P4, P4b, P5, P6, P7, each with its quality gate "
           "(`docs/gates/`) and report (`docs/P*_report.md`).",
           f"- Files tracked in git: {fm(d['tracked_files'])} (LFS for binaries).", "- Code written (tracked files, lines including comments):"]
    for k, v in d["code"].items():
        md.append(f"  - {k}: {fm(v['lines'])} lines in {v['files']} files")
    md += [f"- Tool calls of the agent: {fm(tools_tot['tool_calls'])}; Unity batch runs started {tools_tot['unity_batch_calls']}, player runs "
           f"{tools_tot['player_run_calls']}, Blender bridge / background calls {tools_tot['blender_calls']}, sub-agents {tools_tot['subagents']}.",
           "- Decisions logged: " + str(len(re.findall(r"^\| D-\d+", (ROOT / "docs/decisions.md").read_text(encoding="utf-8"), re.M))) +
           " (`docs/decisions.md`).", ""]
    (ROOT / "docs/cost_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
