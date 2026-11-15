from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from eia_storage.latest import fetch_latest
from eia_storage.regions import REGIONS
from eia_storage.validation import validate_latest_source


FIXTURE = Path(__file__).parent / "fixtures" / "wngsr_2026_11_13.json"
SCHEDULE = """
<table><tr><th>Alternate release date</th><th>Release day</th><th>Release time</th><th>Holiday</th></tr>
<tr><td>November 13, 2026</td><td>Friday</td><td>10:30 a.m.</td><td>Veterans Day</td></tr></table>
"""


class TextResponse:
    text = SCHEDULE


class FixtureHttp:
    def __init__(self):
        self.json_calls = 0
        self.text_calls = 0
        self.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def get_json(self, url, *, params=None):
        self.json_calls += 1
        return self.payload

    def get(self, url, *, params=None):
        self.text_calls += 1
        return TextResponse()


class IntegrationTests(unittest.TestCase):
    def test_latest_service_combines_source_schedule_and_normalization(self) -> None:
        http = FixtureHttp()
        result = fetch_latest(REGIONS["lower48"], http=http, now=datetime(2026, 11, 13, 17, tzinfo=timezone.utc))
        self.assertEqual(result["stocks_bcf"], 3862)
        self.assertEqual(result["freshness_status"], "current")
        self.assertEqual(http.json_calls, 1)
        self.assertEqual(http.text_calls, 1)

    def test_latest_validation_fetches_each_source_once(self) -> None:
        http = FixtureHttp()
        result = validate_latest_source(http=http, now=datetime(2026, 11, 13, 17, tzinfo=timezone.utc))
        self.assertTrue(result["valid"])
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(http.json_calls, 1)
        self.assertEqual(http.text_calls, 1)
        self.assertEqual(result["diagnostics"]["regional_sum_bcf"], 3862)
        self.assertEqual(result["diagnostics"]["salt_plus_nonsalt_bcf"], 1236)


if __name__ == "__main__":
    unittest.main()
