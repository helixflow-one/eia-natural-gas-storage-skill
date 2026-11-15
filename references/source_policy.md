# Source policy

## Precedence

1. Current release: `https://ir.eia.gov/ngs/wngsr.json`.
2. Historical weekly series: `https://api.eia.gov/v2/natural-gas/stor/wkly/data/` with `EIA_API_KEY`.
3. Release timing and holiday exceptions: `https://ir.eia.gov/ngs/schedule.html`.
4. Structured CSV and historical XLS are reserved fallbacks or reconciliation sources; the MVP does not scrape report HTML.

Follow redirects while retaining the stable public URL as provenance. Never persist or cite a signed `/secure/` redirect URL.

## Current versus historical data

Near publication, prefer WNGSR JSON because API v2 may lag. When combining sources, identify observations by region and report date, prefer WNGSR for the newest release, and surface discrepancies rather than averaging or overwriting them.

The normal release is Thursday at 10:30 a.m. America/New_York, but holiday exceptions are authoritative. Freshness evaluation uses elapsed scheduled releases and the expected prior Friday storage week. If schedule retrieval fails, report freshness as `unknown`, not current.

## Retrieval and failure policy

Use bounded timeouts, at most two retries with exponential backoff for transient HTTP failures, explicit API pagination, and a maximum of 50,000 history rows per command. Treat 401/403 as API-key configuration failures. Treat schema drift as a validation failure and report observed field names without returning unverified figures.

Return partial/missing source values as null with warnings, never zero. Do not invent release times, data points, or consensus estimates.

## Secrets

Prefer process `EIA_API_KEY`, then a local `.env`. Redact API keys and signed redirect parameters from diagnostics. Never log, cite, package, or commit a real key.

