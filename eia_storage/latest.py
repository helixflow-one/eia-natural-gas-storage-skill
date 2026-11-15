"""Current WNGSR acquisition service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .config import LATEST_JSON_URL, SCHEDULE_URL
from .errors import SkillError
from .http import EIAHttpClient
from .normalize import normalize_latest, parse_iso_date
from .regions import Region
from .schedule import evaluate_freshness, parse_schedule_html


def fetch_latest(region: Region, *, http: EIAHttpClient | Any | None = None, now: datetime | None = None) -> dict[str, Any]:
    client = http or EIAHttpClient()
    retrieved = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    payload = client.get_json(LATEST_JSON_URL)
    freshness: dict[str, Any]
    schedule_warning: str | None = None
    try:
        schedule_response = client.get(SCHEDULE_URL)
        exceptions = parse_schedule_html(schedule_response.text)
        freshness = evaluate_freshness(parse_iso_date(payload.get("current_week"), "current_week"), exceptions, as_of=retrieved)
    except SkillError as exc:
        freshness = {"status": "unknown", "expected_report_date": None, "reason": "Official schedule could not be evaluated"}
        schedule_warning = f"Freshness is unknown because schedule retrieval failed ({exc.code})"
    result = normalize_latest(payload, region, retrieved_at=retrieved, freshness=freshness)
    if schedule_warning:
        result["warnings"].append(schedule_warning)
    return result

