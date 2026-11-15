---
name: eia-natural-gas-storage
description: Retrieve and analyze the U.S. EIA Weekly Natural Gas Storage Report for current Lower 48 or regional stocks, historical weekly observations, transparent year-ago and five-year comparisons, release schedules, and freshness validation. Use for U.S. underground working-gas storage questions; not for natural-gas prices, forecasts, trading advice, or market-expectation surprise analysis.
metadata:
  short-description: Analyze official EIA weekly gas storage
---

# EIA Natural Gas Storage

Use the bundled Python commands from this skill directory. They return JSON to stdout, typed failures to stderr, and never return the API key.

## Choose the command

- Current stock, injection/withdrawal, regional snapshot, or latest official comparisons: `python scripts/fetch_latest.py --region <region> --format json`
- Historical weekly observations: `python scripts/fetch_history.py --region <region> --start YYYY-MM-DD --end YYYY-MM-DD --format json`
- Year-ago and five-year comparison: `python scripts/analyze.py --region <region> --reference-date latest --lookback-years 5 --format json`
- Comparison for a historical storage week: replace `latest` with `YYYY-MM-DD`. This requires `EIA_API_KEY`.
- Official standard schedule and holiday exceptions: `python scripts/schedule.py --format json`
- Source diagnostics: `python scripts/validate.py --source latest|history --format json`

Regions are `lower48`, `east`, `midwest`, `mountain`, `pacific`, `south_central`, `salt`, and `nonsalt`. Treat Lower 48 as EIA's contiguous-U.S. aggregate, not all 50 states.

## Source and reporting rules

Prefer the dedicated WNGSR JSON for the current release and API v2 for history. Never scrape the report HTML or replace missing values with estimates. Read [references/source_policy.md](references/source_policy.md) when selecting, reconciling, or diagnosing sources.

Always state the storage week, retrieval time, freshness status, region, units, warnings, and stable source URL. A positive net change is an injection; a negative one is a withdrawal. Keep `net_change_bcf` and `implied_flow_bcf` distinct. Storage levels are not prices.

For current releases, report EIA's published year-ago and five-year indicators. For historical comparisons, disclose the window, comparable-week inclusion rule, missing observations, and derived method. Read [references/data_dictionary.md](references/data_dictionary.md) for fields, region mappings, and interpretation.

Do not call a release bullish or bearish versus expectations without a separately sourced, time-aligned consensus forecast. Do not provide price forecasts or trading recommendations from storage data alone.

## Present the result

For a concise snapshot, lead with: report week, stocks in Bcf, net injection/withdrawal, year-ago difference, five-year difference, and freshness. Follow with a small regional table only when requested or useful. End with the stable official endpoint from `source_url` and surface every warning.

If a command returns a typed error, explain the limitation directly. For a missing API key, configure `EIA_API_KEY` in the process environment or a local ignored `.env`; never ask the user to paste a key into the answer or log it.

## Setup

Requires Python 3.11+ and `requests>=2.31,<3`. Install with `python -m pip install -r requirements.txt`. Copy `.env.example` to `.env` only for local development. Do not package or commit `.env`.

## Example requests

- “What is the latest Lower 48 natural gas storage level and how does it compare with last year?”
- “Show East, Midwest, Mountain, Pacific, and South Central storage for the latest week.”
- “Compare Lower 48 storage for 2024-11-08 with comparable weeks in the prior five years.”
- “Is the current WNGSR stale given this week's holiday schedule?”

