"""Normalize and validate current WNGSR JSON."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from .config import LATEST_JSON_URL
from .errors import SchemaError
from .regions import Region

REQUIRED_TOP_LEVEL = {"release_name", "release_date", "current_week", "week_ago", "year_ago", "periodicity", "series"}


def parse_iso_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise SchemaError("Expected an ISO date string", field=field, received_type=type(value).__name__)
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SchemaError("Invalid ISO date", field=field, value=value) from exc


def parse_release_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise SchemaError("Invalid release_date type", received_type=type(value).__name__)
    for pattern in ("%Y-%b-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            pass
    raise SchemaError("Unrecognized release_date format", value=value)


def _number(value: Any, field: str, *, required: bool = False) -> int | float | None:
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaError("Expected a number", field=field, received_type=type(value).__name__)
    return value


def _flag(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    raise SchemaError("Invalid revision/reclassification flag", value=value)


def validate_latest_payload(payload: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_TOP_LEVEL - payload.keys())
    if missing:
        raise SchemaError("Latest WNGSR payload is missing required fields", missing_fields=missing, observed_fields=sorted(payload))
    if payload.get("periodicity") != "weekly":
        raise SchemaError("Unexpected WNGSR periodicity", periodicity=payload.get("periodicity"))
    if not isinstance(payload["series"], list):
        raise SchemaError("WNGSR series must be an array", received_type=type(payload["series"]).__name__)


def normalize_latest(
    payload: dict[str, Any],
    region: Region,
    *,
    retrieved_at: datetime | None = None,
    freshness: dict[str, Any] | None = None,
    source_url: str = LATEST_JSON_URL,
) -> dict[str, Any]:
    validate_latest_payload(payload)
    report_date = parse_iso_date(payload["current_week"], "current_week")
    week_ago = parse_iso_date(payload["week_ago"], "week_ago")
    year_ago = parse_iso_date(payload["year_ago"], "year_ago")

    matches = [item for item in payload["series"] if isinstance(item, dict) and item.get("series_id") == region.latest_series_id]
    if len(matches) != 1:
        raise SchemaError(
            "Expected exactly one series for region",
            region=region.canonical,
            series_id=region.latest_series_id,
            matches=len(matches),
        )
    series = matches[0]
    data = series.get("data")
    if not isinstance(data, list):
        raise SchemaError("Series data must be an array", series_id=region.latest_series_id)

    observations: dict[date, int | float] = {}
    observation_flags: dict[date, dict[str, bool | None]] = {}
    revision_flags = series.get("revision_flag", [])
    reclassification_flags = series.get("reclassification_flag", [])
    for index, item in enumerate(data):
        if not isinstance(item, list) or len(item) != 2:
            raise SchemaError("Observation must contain date and value", series_id=region.latest_series_id, index=index)
        observed_date = parse_iso_date(item[0], f"series.data[{index}].date")
        if observed_date in observations:
            raise SchemaError("Duplicate observation date", series_id=region.latest_series_id, report_date=observed_date.isoformat())
        observations[observed_date] = _number(item[1], f"series.data[{index}].value", required=True)  # type: ignore[assignment]
        observation_flags[observed_date] = {
            "revision": _flag(revision_flags[index]) if index < len(revision_flags) else None,
            "reclassification": _flag(reclassification_flags[index]) if index < len(reclassification_flags) else None,
        }

    if report_date not in observations:
        raise SchemaError("Current-week observation is missing", series_id=region.latest_series_id, report_date=report_date.isoformat())

    calculated = series.get("calculated", {})
    if not isinstance(calculated, dict):
        raise SchemaError("Series calculated field must be an object", series_id=region.latest_series_id)
    stocks = observations[report_date]
    prior_stocks = observations.get(week_ago)
    year_ago_stocks = observations.get(year_ago)
    net_change = _number(calculated.get("net_change"), "calculated.net_change")
    implied_flow = _number(calculated.get("implied_flow"), "calculated.implied_flow")
    five_year_average = _number(calculated.get("5yr-avg"), "calculated.5yr-avg")

    warnings: list[str] = []
    for label, value in (
        ("net_change_bcf", net_change),
        ("implied_flow_bcf", implied_flow),
        ("year_ago_stocks_bcf", year_ago_stocks),
        ("five_year_average_bcf", five_year_average),
    ):
        if value is None:
            warnings.append(f"{label} is unavailable in the source release")
    if prior_stocks is not None and net_change is not None and abs((stocks - prior_stocks) - net_change) > 1:
        warnings.append("Reported net change differs from the stock-level difference by more than 1 Bcf; revisions or reclassifications may apply")

    calc_flags: dict[str, dict[str, bool | None]] = {}
    for key in ("5yr-avg", "net_change", "implied_flow", "pct-change_yrago", "pct-chg_5yr-avg"):
        calc_flags[key] = {
            "revision": _flag(calculated.get(f"revision_flag_{key}")),
            "reclassification": _flag(calculated.get(f"reclassification_flag_{key}")),
        }

    retrieved = (retrieved_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    freshness_data = freshness or {
        "status": "unknown",
        "expected_report_date": None,
        "reason": "Official release schedule was not evaluated",
    }
    return {
        "schema_version": "1.0",
        "command": "latest",
        "report_date": report_date.isoformat(),
        "release_date": parse_release_date(payload.get("release_date")).isoformat() if payload.get("release_date") else None,
        "release_name": payload.get("release_name"),
        "retrieved_at_utc": retrieved.isoformat().replace("+00:00", "Z"),
        "region": region.canonical,
        "region_display_name": region.display_name,
        "series_id": region.latest_series_id,
        "stocks_bcf": stocks,
        "net_change_bcf": net_change,
        "implied_flow_bcf": implied_flow,
        "year_ago_stocks_bcf": year_ago_stocks,
        "five_year_average_bcf": five_year_average,
        "pct_change_yoy": _number(calculated.get("pct-change_yrago"), "calculated.pct-change_yrago"),
        "pct_vs_five_year": _number(calculated.get("pct-chg_5yr-avg"), "calculated.pct-chg_5yr-avg"),
        "units": {"name": series.get("units", "billion cubic feet"), "symbol": "Bcf"},
        "revision_flags": {
            "observations": {key.isoformat(): value for key, value in observation_flags.items()},
            "calculated": calc_flags,
            "original_values": {"observations": data, "calculated": calculated},
        },
        "source_url": source_url,
        "source_kind": "wngsr_json",
        "freshness_status": freshness_data.get("status", "unknown"),
        "freshness": freshness_data,
        "warnings": warnings,
    }

