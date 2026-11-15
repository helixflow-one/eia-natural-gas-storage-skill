"""Source-level diagnostics for latest and historical data."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from .config import LATEST_JSON_URL, SCHEDULE_URL, get_api_key
from .history import HistoryClient
from .http import EIAHttpClient
from .normalize import normalize_latest, parse_iso_date
from .regions import REGIONS
from .schedule import evaluate_freshness, parse_schedule_html


def validate_latest_source(*, http: Any | None = None, now: datetime | None = None) -> dict[str, Any]:
    client = http or EIAHttpClient()
    retrieved = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    payload = client.get_json(LATEST_JSON_URL)
    freshness = {"status": "unknown", "expected_report_date": None, "reason": "Official schedule was not evaluated"}
    warnings: list[str] = []
    try:
        schedule_response = client.get(SCHEDULE_URL)
        freshness = evaluate_freshness(
            parse_iso_date(payload.get("current_week"), "current_week"),
            parse_schedule_html(schedule_response.text),
            as_of=retrieved,
        )
    except Exception:
        warnings.append("Freshness is unknown because the official schedule could not be evaluated")
    results = {key: normalize_latest(payload, region, retrieved_at=retrieved, freshness=freshness) for key, region in REGIONS.items()}
    regions_sum = sum(results[key]["stocks_bcf"] for key in ("east", "midwest", "mountain", "pacific", "south_central"))
    lower48 = results["lower48"]["stocks_bcf"]
    components_sum = results["salt"]["stocks_bcf"] + results["nonsalt"]["stocks_bcf"]
    south_central = results["south_central"]["stocks_bcf"]
    checks = {
        "all_regions_present": len(results) == len(REGIONS),
        "same_report_date": len({item["report_date"] for item in results.values()}) == 1,
        "regional_total_within_rounding_tolerance": abs(regions_sum - lower48) <= 5,
        "south_central_components_within_rounding_tolerance": abs(components_sum - south_central) <= 2,
        "freshness_evaluated": results["lower48"]["freshness_status"] != "unknown",
        "freshness_current": results["lower48"]["freshness_status"] == "current",
    }
    return {
        "schema_version": "1.0",
        "command": "validate",
        "source": "latest",
        "valid": all(checks.values()),
        "checks": checks,
        "diagnostics": {"lower48_bcf": lower48, "regional_sum_bcf": regions_sum, "south_central_bcf": south_central, "salt_plus_nonsalt_bcf": components_sum},
        "report_date": results["lower48"]["report_date"],
        "retrieved_at_utc": results["lower48"]["retrieved_at_utc"],
        "source_url": results["lower48"]["source_url"],
        "freshness_status": results["lower48"]["freshness_status"],
        "warnings": sorted(set(warnings) | {warning for item in results.values() for warning in item["warnings"]}),
    }


def validate_history_source(*, http: Any | None = None, api_key: str | None = None) -> dict[str, Any]:
    end = date.today()
    start = end - timedelta(days=90)
    result = HistoryClient(api_key or get_api_key(), http=http).fetch(REGIONS["lower48"], start.isoformat(), end.isoformat())
    dates = [item["report_date"] for item in result["observations"]]
    checks = {
        "observations_present": bool(dates),
        "dates_descending": dates == sorted(dates, reverse=True),
        "no_duplicate_dates": len(dates) == len(set(dates)),
        "values_nonnegative": all(item["stocks_bcf"] >= 0 for item in result["observations"]),
        "not_truncated": not result["pagination"]["truncated"],
    }
    return {
        "schema_version": "1.0",
        "command": "validate",
        "source": "history",
        "valid": all(checks.values()),
        "checks": checks,
        "diagnostics": result["pagination"],
        "report_date": dates[0] if dates else None,
        "retrieved_at_utc": result["retrieved_at_utc"],
        "source_url": result["source_url"],
        "freshness_status": "unknown",
        "warnings": result["warnings"],
    }
