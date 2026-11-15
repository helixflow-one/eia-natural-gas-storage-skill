# EIA Natural Gas Storage Skill

A portable Agent Skill and Python CLI for the U.S. Energy Information Administration (EIA) Weekly Natural Gas Storage Report (WNGSR).

It retrieves current Lower 48 and regional storage values, queries historical weekly observations, calculates transparent comparisons, checks publication freshness, and returns source-attributed JSON. It does not provide price forecasts, trading recommendations, or market-expectation analysis.

## Features

- Latest Lower 48, East, Midwest, Mountain, Pacific, South Central, Salt, and Nonsalt storage
- Historical EIA API v2 queries with pagination and deduplication
- Official year-ago and five-year comparisons
- Net-change, implied-flow, revision, and reclassification preservation
- Holiday-aware release freshness checks
- Typed errors, bounded retries, provenance, units, timestamps, and warnings

See [SKILL.md](SKILL.md) for agent instructions and the [specification](EIA_Natural_Gas_Storage_Skill_Specification.md) for the full contract.

## Requirements

- Python 3.11+
- `requests>=2.31,<3`
- HTTPS access to `ir.eia.gov` and `api.eia.gov`
- A free `EIA_API_KEY` for historical queries

The latest report and release schedule do not require an API key.

## Install

This repository root is the skill directory: it contains `SKILL.md`, reusable Python modules, scripts, references, and tests. A compatible Agent Skills environment can copy or clone the repository into its skills directory and load `SKILL.md` as the entry point.

### Codex

Ask Codex:

```text
Use $skill-installer to install the skill from
https://github.com/helixflow-one/eia-natural-gas-storage-skill.
The skill is at repository path "."; install it as
"eia-natural-gas-storage".
```

Or run:

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo helixflow-one/eia-natural-gas-storage-skill `
  --path . `
  --name eia-natural-gas-storage
```

Add `--ref v1.0.0` to install a tagged version. The installer uses repository contents; it does not automatically install ZIP assets from GitHub Releases.

Install the dependency after copying or installing the skill:

```powershell
python -m pip install -r requirements.txt
```

## Configure

Register for an EIA API key at <https://www.eia.gov/opendata/register.php> and expose it as `EIA_API_KEY` to the process running the skill. For local development, copy `.env.example` to `.env`. Never commit or publish the real key.

Configuration precedence is process environment, local `.env`, then non-secret defaults.

Network policy should allow only the required EIA hosts where domain restrictions are supported. For Codex workspace-write mode:

```toml
[sandbox_workspace_write]
network_access = true

[features.network_proxy]
enabled = true
domains = { "ir.eia.gov" = "allow", "api.eia.gov" = "allow" }
```

Restart the host environment after changing credentials or network policy.

## Use

Example agent requests:

```text
Show the latest Lower 48 natural gas storage report.
Compare current storage with last year and the five-year average.
Show the latest storage figures for all supported regions.
Retrieve East-region history from 2021-01-01 through 2026-11-06.
Check whether the current WNGSR release is stale.
```

In Codex, prefix a request with `$eia-natural-gas-storage` for explicit invocation.

### CLI

```powershell
python scripts/fetch_latest.py --region lower48 --format json
python scripts/fetch_history.py --region east --start 2021-01-01 --end 2026-11-06 --format json
python scripts/analyze.py --region lower48 --reference-date latest --lookback-years 5 --format json
python scripts/schedule.py --format json
python scripts/validate.py --source latest --format json
python scripts/validate.py --source history --format json
```

Results go to stdout as JSON; typed errors go to stderr with stable exit codes. Secrets and signed redirect parameters are redacted.

## Test and package

```powershell
python -m unittest discover -s tests -v
python scripts/package_skill.py
```

The secret-scanned archive is created at `dist/eia-natural-gas-storage-skill.zip`. Keep `dist/` out of source control; attach the ZIP to a GitHub Release only for optional manual installation.

## Official sources

- Latest WNGSR JSON: <https://ir.eia.gov/ngs/wngsr.json>
- Historical EIA API v2: <https://api.eia.gov/v2/natural-gas/stor/wkly/data/>
- Release schedule: <https://ir.eia.gov/ngs/schedule.html>
- EIA API documentation: <https://www.eia.gov/opendata/documentation.php>

The skill performs read-only requests to EIA and retains stable public URLs as provenance.
