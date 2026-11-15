"""Official release-schedule parsing and freshness evaluation."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from html.parser import HTMLParser
from typing import Any
from zoneinfo import ZoneInfo

from .config import SCHEDULE_URL
from .errors import InputError, SchemaError
from .http import EIAHttpClient

EASTERN = ZoneInfo("America/New_York")
STANDARD_RELEASE_TIME = time(10, 30)


class _ScheduleTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_cell = False
        self.cell_parts: list[str] = []
        self.row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"td", "th"}:
            self.in_cell = True
            self.cell_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.in_cell:
            self.row.append(" ".join("".join(self.cell_parts).split()))
            self.in_cell = False
        elif tag == "tr":
            if self.row:
                self.rows.append(self.row)
            self.row = []


def _parse_time(value: str) -> time:
    clean = value.lower().replace("eastern", "").strip().replace(".", "")
    for pattern in ("%I:%M %p", "%I %p"):
        try:
            return datetime.strptime(clean, pattern).time()
        except ValueError:
            pass
    raise SchemaError("Unrecognized schedule time", value=value)


def parse_schedule_html(html: str) -> list[dict[str, str]]:
    parser = _ScheduleTableParser()
    parser.feed(html)
    releases: list[dict[str, str]] = []
    for row in parser.rows:
        if len(row) < 4 or row[0].lower().startswith("alternate release"):
            continue
        raw_date = row[0].split(" - ", 1)[0].strip()
        try:
            release_date = datetime.strptime(raw_date, "%B %d, %Y").date()
            release_time = _parse_time(row[2])
        except (ValueError, SchemaError):
            continue
        releases.append(
            {
                "release_date": release_date.isoformat(),
                "release_day": row[1],
                "release_time_eastern": release_time.strftime("%H:%M"),
                "holiday": row[3],
            }
        )
    releases.sort(key=lambda item: item["release_date"])
    return releases


def previous_friday(release_date: date) -> date:
    days = (release_date.weekday() - 4) % 7
    return release_date - timedelta(days=7 if days == 0 else days)


def evaluate_freshness(
    report_date: date,
    alternate_releases: list[dict[str, str]],
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise InputError("as_of must include a timezone")
    eastern_now = now.astimezone(EASTERN)
    alternate_by_date = {date.fromisoformat(item["release_date"]): item for item in alternate_releases}
    suppressed_thursdays: set[date] = set()
    for alternate_date in alternate_by_date:
        if alternate_date.weekday() == 0:  # Monday exception replaces the preceding Thursday.
            suppressed_thursdays.add(alternate_date - timedelta(days=4))
        elif alternate_date.weekday() == 2:  # Wednesday exception replaces the following Thursday.
            suppressed_thursdays.add(alternate_date + timedelta(days=1))
        elif alternate_date.weekday() == 4:  # Friday exception replaces the preceding Thursday.
            suppressed_thursdays.add(alternate_date - timedelta(days=1))

    candidates: list[tuple[datetime, str]] = []
    cursor = eastern_now.date() - timedelta(days=28)
    through = eastern_now.date() + timedelta(days=1)
    while cursor <= through:
        if cursor.weekday() == 3 and cursor not in suppressed_thursdays:
            release_at = datetime.combine(cursor, STANDARD_RELEASE_TIME, EASTERN)
            candidates.append((release_at, "standard Thursday schedule"))
        cursor += timedelta(days=1)
    for release_date, item in alternate_by_date.items():
        hh, mm = (int(part) for part in item["release_time_eastern"].split(":"))
        candidates.append((datetime.combine(release_date, time(hh, mm), EASTERN), f"holiday exception: {item['holiday']}"))

    eligible = [candidate for candidate in candidates if candidate[0] <= eastern_now]
    if not eligible:
        return {"status": "unknown", "expected_report_date": None, "reason": "No elapsed release could be determined"}
    expected_release_at, basis = max(eligible, key=lambda item: item[0])
    expected_report = previous_friday(expected_release_at.date())
    status = "stale" if report_date < expected_report else "current"
    return {
        "status": status,
        "expected_report_date": expected_report.isoformat(),
        "observed_report_date": report_date.isoformat(),
        "expected_release_at": expected_release_at.isoformat(),
        "evaluated_at": eastern_now.isoformat(),
        "schedule_basis": basis,
        "schedule_url": SCHEDULE_URL,
    }


def fetch_schedule(
    *,
    http: EIAHttpClient | Any | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    if (start_date is None) != (end_date is None):
        raise InputError("start_date and end_date must be supplied together")
    start: date | None = None
    end: date | None = None
    if start_date and end_date:
        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
        except ValueError as exc:
            raise InputError("Schedule dates must use YYYY-MM-DD format") from exc
        if start > end:
            raise InputError("start_date must be on or before end_date")
    client = http or EIAHttpClient()
    response = client.get(SCHEDULE_URL)
    exceptions = parse_schedule_html(response.text)
    if start and end:
        exceptions = [item for item in exceptions if start.isoformat() <= item["release_date"] <= end.isoformat()]
    return {
        "schema_version": "1.0",
        "command": "schedule",
        "standard_schedule": {"day": "Thursday", "time": "10:30", "timezone": "America/New_York"},
        "alternate_releases": exceptions,
        "source_url": SCHEDULE_URL,
        "source_kind": "eia_release_schedule",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "warnings": [] if exceptions else ["No alternate releases were present in the requested range; consult the source URL for updates"],
    }

