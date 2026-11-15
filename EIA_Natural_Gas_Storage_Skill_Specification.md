# EIA Natural Gas Storage Skill Specification

**Version:** 1.0  
**Date:** 2026-11-14  
**Status:** Proposed for implementation

Purpose. Define a portable Agent Skill that retrieves and analyzes the U.S. Energy Information Administration Weekly Natural Gas Storage Report (WNGSR). This specification is intended for implementation, testing, and later portability across compatible AI environments.

Decision. Use the official WNGSR JSON publication for the latest release and EIA API v2 for historical series. The Skill will not scrape or parse the HTML report. An MCP server, background scheduler, and persistent database are outside the initial MVP.

# 1 Scope and success criteria

- MVP: retrieve the newest published Lower 48 and regional storage figures; query historical weekly series; compute transparent comparisons; produce structured, source-attributed results for AI analysis.

- Support East, Midwest, Mountain, Pacific, South Central, South Central Salt, South Central Nonsalt, and Lower 48 aggregate.

  **Terminology:** *Lower 48* means the 48 contiguous U.S. states, excluding Alaska and Hawaii. In this Skill, `lower48` identifies the EIA national aggregate for those states, displayed as **U.S. Lower 48 (Contiguous United States)**. It is not a sum of all 50 states.

- Return report date, release metadata, source URL, retrieval timestamp, data freshness, units, and warnings with every result.

- Out of scope for MVP: price forecasting, trading recommendations, consensus-surprise analysis, notifications, always-on monitoring, market-price datasets, production MCP hosting.

- Success: an agent can answer the latest-storage question and a multi-year historical comparison without fabricating data, while detecting a stale report.

# 2 Official sources and precedence

| **Source**       | **Endpoint**                                       | **Purpose / policy**                                               |
|------------------|----------------------------------------------------|--------------------------------------------------------------------|
| Latest JSON      | https://ir.eia.gov/ngs/wngsr.json                  | Primary current-release values; fixed public URL; follow redirects |
| Historical API   | https://api.eia.gov/v2/natural-gas/stor/wkly/data/ | Historical weekly series; API key and pagination                   |
| CSV backup       | https://ir.eia.gov/ngs/wngsr.csv                   | Optional structured fallback to JSON                               |
| Release schedule | https://ir.eia.gov/ngs/schedule.html               | Holiday exceptions and expected publication times                  |
| Historical XLS   | https://ir.eia.gov/ngs/ngshistory.xls              | Optional backfill / reconciliation                                 |

EIA states that WNGSR data may appear in API v2 within two hours after the publication; for near-release access its dedicated release server is preferred. The normal schedule is Thursday 10:30 a.m. America/New_York, with holiday exceptions. Do not hard-code Thursdays as an unconditional rule.

Use stable public URLs above. Do not persist or configure redirected, time-limited signed /secure/ URLs.

# 3 Skill package and runtime contract

Recommended package layout: SKILL.md, scripts/fetch_latest.py, scripts/fetch_history.py, scripts/normalize.py, scripts/analyze.py, references/data_dictionary.md, references/source_policy.md, tests/, requirements.txt, `.env.example`, and `.gitignore`. A local `.env` file may hold secrets and machine-specific overrides, but it must never be committed or packaged.

- SKILL.md specifies activation conditions, source-selection policy, execution commands, response templates, citations, and limits. Keep domain rules here, while parsing/calculation remains in reusable Python modules.

- Python 3.11+; requests/httpx; optional pandas for historical analysis. Pin dependency ranges. Avoid requiring pandas for a single current report.

- For cross-platform portability, provide a CLI returning JSON to stdout, errors to stderr, and stable exit codes; never rely on platform-specific paths or AI tool names.

- The execution environment must permit network requests to ir.eia.gov and api.eia.gov and secure configuration of EIA_API_KEY. If unavailable, report the limitation; do not substitute invented values.

## 3.1 Local configuration and secrets

- Support `EIA_API_KEY` from the process environment as the preferred source. For local development, also support a project-root `.env` file containing `EIA_API_KEY=<value>` when the process environment does not define it.

- Configuration precedence is: explicit process environment, then local `.env`, then documented non-secret defaults. An empty value is treated as unconfigured.

- Commit `.env.example` with placeholder names only. Add `.env`, `.env.*`, and other local secret files to `.gitignore`, while explicitly allowing `.env.example`.

- Never place a real key in the specification, examples, fixtures, source code, logs, command output, exception text, or release package. Do not return the key in JSON output. Redact key-like query parameters from diagnostics.

- Keep portable, non-secret constants such as endpoint URLs, timeout bounds, retry counts, and default page sizes in a dedicated configuration module. Environment variables and `.env` are reserved for secrets or machine-specific overrides.

# 4 Public commands and behavior

| **Command / function** | **Inputs**                                                                     | **Result**                                                                      |
|------------------------|--------------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| latest                 | region=lower48\|east\|midwest\|mountain\|pacific\|south_central\|salt\|nonsalt | Normalized current report, data freshness and warnings                          |
| history                | region, start_date, end_date; optional limit                                   | Weekly observations with pagination metadata                                    |
| compare                | region, reference_date or latest, lookback_years                               | Year-ago and five-year comparisons with methods and provenance                  |
| schedule               | optional date range                                                            | Expected publication dates where supported, otherwise link to official schedule |
| validate               | source=latest\|history                                                         | Schema, arithmetic, date and freshness diagnostics                              |

Example CLI interface: python scripts/fetch_latest.py --region lower48 --format json; python scripts/fetch_history.py --region east --start 2021-01-01 --end 2026-11-06 --format json.

# 5 Normalized data model

| **Field**                         | **Type**         | **Definition / rule**                                                            |
|-----------------------------------|------------------|----------------------------------------------------------------------------------|
| report_date                       | ISO date         | Underlying storage week ending date, from current_week or historical period      |
| release_date                      | ISO date or null | Publication date; do not infer exact hour from midnight-valued JSON release_date |
| retrieved_at_utc                  | ISO datetime     | Actual fetch timestamp                                                           |
| region                            | enum             | Canonical region name; preserve original series_id                               |
| stocks_bcf                        | number           | Working gas inventory in billion cubic feet                                      |
| net_change_bcf                    | number or null   | Official reported net change; not always equal to implied_flow                   |
| implied_flow_bcf                  | number or null   | Separate EIA measure; never conflate with net change                             |
| year_ago_stocks_bcf               | number or null   | Comparable prior-year reported stock                                             |
| five_year_average_bcf             | number or null   | Official benchmark for the current report                                        |
| pct_change_yoy / pct_vs_five_year | number or null   | Use EIA published calculated values for latest report                            |
| revision_flags                    | object           | Preserve revisions/reclassification flags and original values                    |
| source_url / source_kind          | string           | Provenance for each observation                                                  |
| freshness_status                  | enum             | current, stale, unknown; calculated against schedule and report date             |

JSON schema facts observed: release_name, release_date, current_week, week_ago, year_ago, 5yr_avg, periodicity, series\[\].series_id, series\[\].name, series\[\].calculated, series\[\].data. The national series_id is png.nw2_epg0_swo_r48_bcf.w. Confirm every region mapping against source before locking the dictionary.

# 6 Acquisition and validation algorithm

- Fetch latest JSON over HTTPS with a bounded timeout, redirect support, content-type/JSON check, and 2–3 retries with exponential backoff on transient failures; avoid aggressive polling.

- Validate required top-level fields and series entries; map region by series_id rather than display-name substring; read observation dates explicitly, not by positional assumption.

- Compare current_week with the expected latest period determined from the official schedule, while allowing holiday changes and temporary delays. Distinguish unavailable from stale.

- Preserve source-provided net_change and implied_flow independently. Check arithmetic only within rounding tolerance; regional totals may differ due to independent rounding.

- For historical queries, request EIA API v2 /data with frequency, data\[\], facets, start/end, explicit sorting, and pagination. Confirm the route’s metadata and configured API key at implementation time.

- If latest JSON fails, optionally attempt the structured CSV file; label the degraded source in the response. Do not scrape HTML as a fallback.

- For merged current and historical data, deduplicate by region, report_date, and source/version; prefer WNGSR release for the latest observation and expose discrepancies rather than silently blending.

# 7 Analysis and reporting rules

- For latest snapshots, favor official calculated indicators; for history-derived statistics, disclose window, inclusion rules, handling of missing weeks, and units.

- A positive net change represents net injection; negative represents net withdrawal. Explain that storage levels are not natural gas prices.

- Do not classify a release as bullish or bearish versus market expectations without a separately sourced consensus forecast and time alignment.

- Every answer about “latest” states the report week and retrieval freshness. Cite source endpoints and acknowledge sampling uncertainty or revisions when relevant.

- Skill can format concise summary, regional table, or historical trend analysis. It must not invent unavailable release times or data points.

# 8 Errors, security, and portability

| **Condition**                   | **Required behavior**                                                       |
|---------------------------------|-----------------------------------------------------------------------------|
| Timeout, 429, 5xx               | Bounded retry; retain provenance; return typed retrieval error after limit  |
| 401/403 API key problem         | Explain environment or local `.env` configuration; do not log the secret    |
| JSON schema drift               | Fail schema validation; save diagnostic field names, not unverified figures |
| Report date older than expected | Return data with stale flag and expected/current dates                      |
| API history not yet updated     | Do not overwrite newer release-server observation                           |
| Partial/missing regional data   | Return partial result explicitly, not zeros                                 |
| Client lacks Python/network     | Explain runtime limitation and provide setup instruction                    |

Respect official access policies. Avoid hard-coded keys or signed redirects, redact secrets from logs and URLs, cap requests, and validate user-supplied date/region parameters. Keep the package read-only to EIA. Packaging and release validation must fail if a real `.env` file or API key is included.

# 9 Testing and acceptance criteria

- Fixture test against the 2026-11-13 WNGSR release: week 2026-11-06, Lower 48 stocks 3862 Bcf, net change +61 Bcf, five-year average 3787 Bcf. Treat this as a regression fixture, not an assertion about future current data.

- Test all canonical regions, revision flags, missing field, invalid date, invalid API key, HTTP redirect, timeout, stale release and rounding discrepancy. Test configuration precedence, missing/empty key handling, `.env` fallback, and secret redaction without committing a live credential to fixtures.

- Historical tests include multi-page pagination, descending dates, no duplicate observations, boundary dates and source reconciliation.

- Acceptance: latest and history commands return schema-valid JSON; source dates/units included; no fabricated data; failures explicit; documented setup succeeds in at least one Python runtime.

- Cross-platform acceptance is separately assessed for each target AI environment: skill discovery, script execution, network access, dependency availability, and credential handling.

# 10 Milestones and open decisions

| **Phase**   | **Deliverable / exit gate**                                                    |
|-------------|--------------------------------------------------------------------------------|
| M1          | JSON parser + normalized schema + fixture tests                                |
| M2          | Historical API client + key handling + pagination tests                        |
| M3          | SKILL.md + analysis and source-selection rules + sample prompts                |
| M4          | End-to-end QA, portability checks, documentation and release package           |
| Optional M5 | Persistent publication snapshots, revision audit, scheduler and/or MCP wrapper |

Decisions before implementation: (1) exact target AI environments; (2) whether an EIA API key will be provided; (3) whether to persist weekly source snapshots for revision auditing; (4) desired language and report output format; (5) whether release-day polling is needed. Default MVP: no always-on scheduler and no database.

# 11 Primary references

EIA current report: https://ir.eia.gov/ngs/ngs.html

EIA JSON data: https://ir.eia.gov/ngs/wngsr.json

EIA automated retrieval HTTPS notice: https://ir.eia.gov/ngs/notice.html

EIA 2013 report file format notice: https://ir.eia.gov/ngs/notice_12_11_2013.html

EIA API technical documentation: https://www.eia.gov/opendata/documentation.php

EIA API FAQs and release lag: https://www.eia.gov/opendata/faqs.php

EIA holiday release schedule: https://ir.eia.gov/ngs/schedule.html
