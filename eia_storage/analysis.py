"""Transparent official and history-derived storage comparisons."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import Any, Callable

from .errors import InputError, SchemaError
from .history import HistoryClient
from .latest import fetch_latest
from .regions import Region


def _difference(current: int | float, reference: int | float | None) -> dict[str, float | int | None]:
    if reference is None:
        return {"reference_bcf": None, "difference_bcf": None, "percent_difference": None}
    pct = None if reference == 0 else round((current - reference) / reference * 100, 1)
    return {"reference_bcf": reference, "difference_bcf": current - reference, "percent_difference": pct}


def _years_before(value: date, years: int) -> date:
    year = value.year - years
    return value.replace(year=year, day=min(value.day, monthrange(year, value.month)[1]))


def compare_latest(region: Region, *, latest_fetcher: Callable[..., dict[str, Any]] = fetch_latest) -> dict[str, Any]:
    latest = latest_fetcher(region)
    stocks = latest["stocks_bcf"]
    year = _difference(stocks, latest["year_ago_stocks_bcf"])
    five = _difference(stocks, latest["five_year_average_bcf"])
    return {
        "schema_version": "1.0",
        "command": "compare",
        "reference_date": latest["report_date"],
        "region": region.canonical,
        "region_display_name": region.display_name,
        "stocks_bcf": stocks,
        "comparisons": {
            "year_ago": {**year, "method": "EIA-published comparable prior-year stock for the current WNGSR"},
            "five_year": {**five, "method": "EIA-published five-year average for the current WNGSR"},
        },
        "units": latest["units"],
        "source_url": latest["source_url"],
        "source_kind": latest["source_kind"],
        "retrieved_at_utc": latest["retrieved_at_utc"],
        "freshness_status": latest["freshness_status"],
        "freshness": latest["freshness"],
        "warnings": latest["warnings"],
    }


def compare_history(
    region: Region,
    reference_date: str,
    lookback_years: int,
    history_client: HistoryClient,
) -> dict[str, Any]:
    if lookback_years < 5 or lookback_years > 20:
        raise InputError("lookback_years must be between 5 and 20")
    try:
        reference = date.fromisoformat(reference_date)
    except ValueError as exc:
        raise InputError("reference_date must use YYYY-MM-DD format") from exc
    start = _years_before(reference, lookback_years) - timedelta(days=7)
    result = history_client.fetch(region, start.isoformat(), reference.isoformat())
    by_date = {date.fromisoformat(row["report_date"]): row for row in result["observations"]}
    if reference not in by_date:
        raise SchemaError("No historical observation exists on reference_date", reference_date=reference.isoformat())
    current = by_date[reference]["stocks_bcf"]

    selected: list[dict[str, Any]] = []
    for years in range(1, lookback_years + 1):
        target = _years_before(reference, years)
        candidates = [(abs((candidate - target).days), candidate, row) for candidate, row in by_date.items() if abs((candidate - target).days) <= 3]
        if candidates:
            _, observed, row = min(candidates, key=lambda item: (item[0], item[1]))
            selected.append({"year_offset": years, "target_date": target.isoformat(), "report_date": observed.isoformat(), "stocks_bcf": row["stocks_bcf"]})
    year_row = next((item for item in selected if item["year_offset"] == 1), None)
    five_rows = [item for item in selected if item["year_offset"] <= 5]
    five_average = round(sum(item["stocks_bcf"] for item in five_rows) / len(five_rows), 1) if len(five_rows) == 5 else None
    warnings = list(result["warnings"])
    if year_row is None:
        warnings.append("No comparable observation was found within 3 days of the prior-year calendar date")
    if five_average is None:
        warnings.append(f"Five-year average is unavailable because only {len(five_rows)} of 5 comparable weeks were found")
    return {
        "schema_version": "1.0",
        "command": "compare",
        "reference_date": reference.isoformat(),
        "region": region.canonical,
        "region_display_name": region.display_name,
        "stocks_bcf": current,
        "comparisons": {
            "year_ago": {**_difference(current, year_row["stocks_bcf"] if year_row else None), "method": "Closest weekly observation within ±3 days of the prior-year calendar date", "observation": year_row},
            "five_year": {**_difference(current, five_average), "method": "Mean of one closest weekly observation within ±3 days in each of the prior five years", "observations": five_rows, "required_observations": 5},
        },
        "window": {"start_date": start.isoformat(), "end_date": reference.isoformat(), "lookback_years": lookback_years, "missing_weeks": 5 - len(five_rows)},
        "units": {"name": "billion cubic feet", "symbol": "Bcf"},
        "source_url": result["source_url"],
        "source_kind": result["source_kind"],
        "retrieved_at_utc": result["retrieved_at_utc"],
        "freshness_status": "unknown",
        "warnings": warnings,
    }

