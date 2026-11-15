from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

from eia_storage.schedule import evaluate_freshness, parse_schedule_html, previous_friday


HTML = """
<table>
<tr><th>Alternate release date</th><th>Release day</th><th>Release time</th><th>Holiday</th></tr>
<tr><td>November 13, 2026</td><td>Friday</td><td>10:30 a.m.</td><td>Veterans Day</td></tr>
<tr><td>November 25, 2026</td><td>Wednesday</td><td>12:00 p.m.</td><td>Thanksgiving Day</td></tr>
</table>
"""


class ScheduleTests(unittest.TestCase):
    def test_parses_holiday_exceptions(self) -> None:
        rows = parse_schedule_html(HTML)
        self.assertEqual(rows[0]["release_date"], "2026-11-13")
        self.assertEqual(rows[0]["release_time_eastern"], "10:30")
        self.assertEqual(rows[1]["holiday"], "Thanksgiving Day")

    def test_holiday_release_drives_expected_period(self) -> None:
        rows = parse_schedule_html(HTML)
        result = evaluate_freshness(
            date(2026, 11, 6), rows,
            as_of=datetime(2026, 11, 13, 17, tzinfo=timezone.utc),
        )
        self.assertEqual(result["status"], "current")
        self.assertEqual(result["expected_report_date"], "2026-11-06")
        self.assertIn("holiday exception", result["schedule_basis"])

    def test_stale_release_is_detected(self) -> None:
        result = evaluate_freshness(
            date(2026, 10, 30), parse_schedule_html(HTML),
            as_of=datetime(2026, 11, 13, 17, tzinfo=timezone.utc),
        )
        self.assertEqual(result["status"], "stale")

    def test_previous_friday_is_strict_for_friday_release(self) -> None:
        self.assertEqual(previous_friday(date(2026, 11, 13)), date(2026, 11, 6))
        self.assertEqual(previous_friday(date(2026, 11, 12)), date(2026, 11, 6))

    def test_replaced_thursday_is_not_treated_as_a_release(self) -> None:
        rows = parse_schedule_html(HTML)
        result = evaluate_freshness(
            date(2026, 10, 30), rows,
            as_of=datetime(2026, 11, 12, 17, tzinfo=timezone.utc),
        )
        self.assertEqual(result["status"], "current")
        self.assertEqual(result["expected_report_date"], "2026-10-30")



if __name__ == "__main__":
    unittest.main()

