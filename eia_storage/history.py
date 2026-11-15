"""Historical EIA API v2 acquisition, pagination, and normalization."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from .config import DEFAULT_PAGE_SIZE, HISTORY_API_URL, MAX_HISTORY_ROWS, MAX_PAGE_SIZE
from .errors import ConfigurationError, InputError, SchemaError
from .http import EIAHttpClient
from .normalize import parse_iso_date
from .regions import Region


def validate_date_range(start_date: str, end_date: str) -> tuple[date, date]:
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except (TypeError, ValueError) as exc:
        raise InputError("Dates must use YYYY-MM-DD format", start_date=start_date, end_date=end_date) from exc
    if start > end:
        raise InputError("start_date must be on or before end_date", start_date=start_date, end_date=end_date)
    return start, end


def _numeric(value: Any, *, period: str) -> int | float:
    if isinstance(value, bool) or value is None:
        raise SchemaError("Historical observation has no numeric value", period=period)
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SchemaError("Historical observation has an invalid value", period=period, value_type=type(value).__name__) from exc
    return int(number) if number.is_integer() else number


class HistoryClient:
    def __init__(self, api_key: str | None, *, http: EIAHttpClient | Any | None = None, page_size: int = DEFAULT_PAGE_SIZE) -> None:
        if not api_key or not api_key.strip():
            raise ConfigurationError("EIA_API_KEY is required for historical API queries")
        if page_size < 1 or page_size > MAX_PAGE_SIZE:
            raise InputError("page_size is outside the allowed range", minimum=1, maximum=MAX_PAGE_SIZE)
        self._api_key = api_key.strip()
        self.http = http or EIAHttpClient()
        self.page_size = page_size

    def fetch(
        self,
        region: Region,
        start_date: str,
        end_date: str,
        *,
        limit: int | None = None,
        retrieved_at: datetime | None = None,
    ) -> dict[str, Any]:
        start, end = validate_date_range(start_date, end_date)
        if limit is not None and (isinstance(limit, bool) or limit < 1 or limit > MAX_HISTORY_ROWS):
            raise InputError("limit is outside the allowed range", minimum=1, maximum=MAX_HISTORY_ROWS)

        target = limit or MAX_HISTORY_ROWS
        offset = 0
        pages = 0
        total_available: int | None = None
        raw_rows: list[dict[str, Any]] = []
        while len(raw_rows) < target:
            length = min(self.page_size, target - len(raw_rows))
            params: list[tuple[str, Any]] = [
                ("api_key", self._api_key),
                ("frequency", "weekly"),
                ("data[0]", "value"),
                ("facets[series][]", region.history_series_id),
                ("start", start.isoformat()),
                ("end", end.isoformat()),
                ("sort[0][column]", "period"),
                ("sort[0][direction]", "desc"),
                ("offset", offset),
                ("length", length),
            ]
            payload = self.http.get_json(HISTORY_API_URL, params=params)
            response = payload.get("response")
            if not isinstance(response, dict) or not isinstance(response.get("data"), list):
                raise SchemaError("Historical API response is missing response.data", observed_fields=sorted(payload))
            page = response["data"]
            try:
                reported_total = int(response.get("total", len(page)))
            except (TypeError, ValueError) as exc:
                raise SchemaError("Historical API response has invalid total") from exc
            total_available = reported_total if total_available is None else total_available
            if reported_total != total_available:
                raise SchemaError("Historical API total changed during pagination", first_total=total_available, observed_total=reported_total)
            pages += 1
            raw_rows.extend(page)
            offset += len(page)
            if not page or len(page) < length or offset >= reported_total:
                break

        retrieved = (retrieved_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        seen: set[str] = set()
        observations: list[dict[str, Any]] = []
        duplicate_periods: list[str] = []
        for index, row in enumerate(raw_rows):
            if not isinstance(row, dict):
                raise SchemaError("Historical API row is not an object", index=index)
            period = parse_iso_date(row.get("period"), f"response.data[{index}].period").isoformat()
            if not (start.isoformat() <= period <= end.isoformat()):
                raise SchemaError("Historical API returned a date outside the requested range", period=period)
            if period in seen:
                duplicate_periods.append(period)
                continue
            seen.add(period)
            source_series = row.get("series")
            if source_series is not None and source_series != region.history_series_id:
                raise SchemaError("Historical API returned an unexpected series", expected=region.history_series_id, observed=source_series)
            observations.append(
                {
                    "report_date": period,
                    "release_date": None,
                    "retrieved_at_utc": retrieved,
                    "region": region.canonical,
                    "region_display_name": region.display_name,
                    "series_id": region.history_series_id,
                    "stocks_bcf": _numeric(row.get("value"), period=period),
                    "net_change_bcf": None,
                    "implied_flow_bcf": None,
                    "year_ago_stocks_bcf": None,
                    "five_year_average_bcf": None,
                    "pct_change_yoy": None,
                    "pct_vs_five_year": None,
                    "revision_flags": {},
                    "source_url": HISTORY_API_URL,
                    "source_kind": "eia_api_v2",
                    "freshness_status": "unknown",
                    "units": {"name": "billion cubic feet", "symbol": row.get("units") or "Bcf"},
                }
            )
        observations.sort(key=lambda item: item["report_date"], reverse=True)
        warnings: list[str] = []
        if duplicate_periods:
            warnings.append(f"Removed {len(duplicate_periods)} duplicate observation(s) returned by the source")
        truncated = total_available is not None and len(observations) < total_available and len(raw_rows) >= target
        if truncated:
            warnings.append("Result was truncated by the requested or safety limit")
        return {
            "schema_version": "1.0",
            "command": "history",
            "region": region.canonical,
            "region_display_name": region.display_name,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "retrieved_at_utc": retrieved,
            "units": {"name": "billion cubic feet", "symbol": "Bcf"},
            "source_url": HISTORY_API_URL,
            "source_kind": "eia_api_v2",
            "freshness_status": "unknown",
            "observations": observations,
            "pagination": {
                "page_size": self.page_size,
                "pages_fetched": pages,
                "rows_received": len(raw_rows),
                "rows_returned": len(observations),
                "total_available": total_available,
                "truncated": truncated,
            },
            "warnings": warnings,
        }

