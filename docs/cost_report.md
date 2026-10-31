# Cost report (brief section 18)

Data: the Claude Code transcripts of this project (8 files: main sessions and sub-agents) from 2026-10-10T16:05:05Z to 2026-10-15T22:45:49Z, read by `tools/cost/make_cost_report.py`; raw rows per phase in `docs/cost_log.csv`, totals in `docs/cost/usage_total.json`. All money figures are an **API-equivalent estimate** at the official Anthropic API list prices - not the user's actual subscription billing.

## Summary table

| Metric | Value |
|---|---|
| Calendar time from the first message to the end | 126.7 h (5.3 days) |
| Active agent time (pauses > 10 min not counted) | 50.9 h |
| Model | Claude Opus 5.5 (`claude-opus-5-5`): main session and sub-agents |
| Input tokens (uncached) | 3 705 771 |
| Output tokens | 7 926 549 |
| Cache writes (5 min / 1 h) | 52 043 242 / 5 443 174 |
| Cache reads | 2 151 185 863 |
| Cost at API prices (equivalent) | **$907.35** (main session $881.71, sub-agents $25.64) |
| Phases completed | 12 (P0, P0.5, P1, P1b, P2, P3, P3b, P4, P4b, P5, P6, P7) |
| Lines of code (in git) | 61 525 in 380 files |
| Unity batch runs / player runs / Blender calls | 264 / 86 / 239 (agent tool calls) |

## 1. Time

- **Wall-clock** from the first transcript record to the last: **126.7 h** (5.3 days). It includes the nights and the breaks between sessions (the autonomy mode ran without waiting for the user, but sessions ended and resumed).
- **Active agent time: 50.9 h.** Rule: the sum of the gaps between consecutive transcript records, leaving out every gap longer than 10 minutes. Long background jobs (Unity builds, crash series, test suites) that ran more than 10 minutes without a record therefore count as idle; the time they took is in the job counts below.

| Phase | Wall-clock h | Active h | Messages | Tool calls | Unity batch | Player runs | Blender calls | Sub-agents |
|---|---|---|---|---|---|---|---|---|
| P0 | 1.6 | 1.6 | 103 | 171 | 7 | 1 | 5 | 1 |
| P0.5 | 3.3 | 2.8 | 87 | 145 | 6 | 6 | 8 | 0 |
| P1 | 10.9 | 10.2 | 573 | 833 | 0 | 0 | 150 | 1 |
| P1b | 2.0 | 2.0 | 123 | 233 | 0 | 0 | 31 | 0 |
| P2 | 8.6 | 2.7 | 142 | 233 | 0 | 0 | 18 | 0 |
| P3 | 25.0 | 7.7 | 611 | 689 | 42 | 1 | 9 | 0 |
| P3b | 8.7 | 8.6 | 669 | 776 | 104 | 0 | 6 | 0 |
| P4 | 38.7 | 7.4 | 790 | 885 | 75 | 26 | 12 | 1 |
| P4b | 2.5 | 2.3 | 277 | 284 | 19 | 8 | 0 | 0 |
| P5 | 0.7 | 0.7 | 59 | 67 | 6 | 7 | 0 | 0 |
| P6 | 21.6 | 3.3 | 580 | 570 | 2 | 19 | 0 | 0 |
| P7 | 3.0 | 1.6 | 250 | 269 | 3 | 18 | 0 | 0 |

Phase wall-clock is first to last record inside the phase (the gaps between phases are not in any row). The job columns count the agent's tool calls that started such jobs (a call may run a whole series, e.g. one `run_all_p6.ps1` call ran 33 scenario runs).

## 2. Tokens

| Model (context) | Messages | Input | Output | Cache write 5 min | Cache write 1 h | Cache read |
|---|---|---|---|---|---|---|
| claude-opus-5-5 (main) | 4 130 | 3 574 927 | 7 623 260 | 49 162 349 | 5 443 174 | 2 127 962 163 |
| claude-opus-5-5 (subagent) | 134 | 130 844 | 303 289 | 2 880 893 | 0 | 23 223 700 |
| **total** | 4 264 | 3 705 771 | 7 926 549 | 52 043 242 | 5 443 174 | 2 151 185 863 |

Per phase (all models):

| Phase | Input | Output | Cache write 5 min | Cache write 1 h | Cache read | API-equivalent USD |
|---|---|---|---|---|---|---|
| P0 | 212 | 348 635 | 4 677 065 | 0 | 23 769 468 | $35.11 |
| P0.5 | 2 381 | 298 745 | 3 061 313 | 0 | 46 849 029 | $30.66 |
| P1 | 9 680 | 1 213 650 | 13 173 422 | 0 | 257 709 515 | $141.72 |
| P1b | 246 | 331 799 | 1 528 768 | 0 | 61 381 259 | $26.56 |
| P2 | 286 | 356 636 | 5 992 366 | 0 | 57 257 056 | $48.55 |
| P3 | 7 683 | 1 477 402 | 8 754 787 | 0 | 267 420 505 | $126.84 |
| P3b | 2 121 195 | 1 445 053 | 12 829 286 | 0 | 330 916 106 | $167.72 |
| P4 | 1 561 658 | 1 066 255 | 2 026 235 | 1 646 429 | 437 684 519 | $138.41 |
| P4b | 568 | 384 035 | 0 | 689 388 | 139 338 859 | $41.07 |
| P5 | 118 | 153 988 | 0 | 206 042 | 46 520 047 | $14.03 |
| P6 | 1 240 | 584 656 | 0 | 2 397 484 | 309 628 521 | $92.80 |
| P7 | 504 | 265 695 | 0 | 503 831 | 172 710 979 | $43.89 |
| **total** | 3 705 771 | 7 926 549 | 52 043 242 | 5 443 174 | 2 151 185 863 | **$907.35** |

## 3. Money (API-equivalent)

Prices: official Anthropic API price list, https://platform.claude.com/docs/en/about-claude/pricing, read on 2026-10-15, Claude Opus 5.5 in USD per million tokens:

| Base input | 5-minute cache write | 1-hour cache write | Cache hit / refresh | Output |
|---|---|---|---|---|
| $4.00 | $5.00 | $8.00 | $0.20 | $20.00 |

The full 1M-token context window is billed at standard prices for this model (no long-context surcharge); the sessions used global routing (no `inference_geo`, so no 1.1x data-residency multiplier), standard speed (no fast mode) and no Batch API, so no other modifier applies.

Formula: cost = (input x 4.00 + cache write 5 min x 5.00 + cache write 1 h x 8.00 + cache read x 0.20 + output x 20.00) / 1,000,000.

- **claude-opus-5-5 (main):** (3 574 927 x 4.00 + 49 162 349 x 5.00 + 5 443 174 x 8.00 + 2 127 962 163 x 0.20 + 7 623 260 x 20.00) / 1e6 = **$881.71**
- **claude-opus-5-5 (subagent):** (130 844 x 4.00 + 2 880 893 x 5.00 + 0 x 8.00 + 23 223 700 x 0.20 + 303 289 x 20.00) / 1e6 = **$25.64**

**Total: $907.35.** By token type: cache reads $430.24 (47 %), 1-hour cache writes $43.55 (5 %), 5-minute cache writes $260.22 (29 %), output $158.53 (17 %), uncached input $14.82 (2 %). Without prompt caching the same input would have cost about $9,008.

## 4. Uncertainty

- **Exact:** the token counts. They are the `usage` fields the API returned for every assistant message, summed after de-duplicating streamed records by message id. The prices are the published list prices.
- **Estimated:** the active time (the 10-minute gap rule) and the phase boundaries (each phase ends at its `docs/cost_log.csv` timestamp). The job counts are tool calls, not individual runs.
- **Exact as well:** the cache writes' time to live. Every record splits its writes into 5-minute and 1-hour ones (`usage.cache_creation`); the early sessions wrote 5-minute entries, the later ones 1-hour entries.
- **Missing:**
  - transcripts deleted or kept outside this project's Claude Code folder (none known);
  - costs outside the model: the Unity licence, electricity, the user's subscription.
- **Not the bill:** the user's actual charges depend on their Claude subscription, not on these list prices.

## 5. Context

- Phases completed: P0, P0.5, P1, P1b, P2, P3, P3b, P4, P4b, P5, P6, P7, each with its quality gate (`docs/gates/`) and report (`docs/P*_report.md`).
- Files tracked in git: 2 820 (LFS for binaries).
- Code written (tracked files, lines including comments):
  - Unity C# (solver, game, editor tools): 26 257 lines in 96 files
  - Unity shaders: 205 lines in 4 files
  - Blender Python (hcar package, scripts): 12 511 lines in 61 files
  - Python tools (gates, analysis, skeleton design, cost): 22 068 lines in 208 files
  - PowerShell scripts: 484 lines in 11 files
- Tool calls of the agent: 5 155; Unity batch runs started 264, player runs 86, Blender bridge / background calls 239, sub-agents 3.
- Decisions logged: 104 (`docs/decisions.md`).

