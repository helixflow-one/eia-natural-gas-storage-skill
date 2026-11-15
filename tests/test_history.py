from __future__ import annotations

import unittest
from datetime import datetime, timezone

from eia_storage.errors import ConfigurationError, InputError, RetrievalError, SchemaError
from eia_storage.history import HistoryClient, validate_date_range
from eia_storage.regions import REGIONS


class FakeHttp:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def get_json(self, url, *, params=None):
        self.calls.append((url, params))
        item = self.pages.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def page(rows, total):
    return {"response": {"total": total, "data": rows}}


class HistoryTests(unittest.TestCase):
    def test_multi_page_pagination_sorting_and_parameters(self) -> None:
        fake = FakeHttp([
            page([
                {"period": "2026-01-02", "value": "3200", "series": "NW2_EPG0_SWO_R48_BCF", "units": "BCF"},
                {"period": "2026-01-16", "value": "3100", "series": "NW2_EPG0_SWO_R48_BCF", "units": "BCF"},
            ], 3),
            page([
                {"period": "2026-01-09", "value": "3150", "series": "NW2_EPG0_SWO_R48_BCF", "units": "BCF"},
            ], 3),
        ])
        result = HistoryClient("test-key", http=fake, page_size=2).fetch(
            REGIONS["lower48"], "2026-01-01", "2026-01-31",
            retrieved_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        self.assertEqual([row["report_date"] for row in result["observations"]], ["2026-01-16", "2026-01-09", "2026-01-02"])
        self.assertEqual(result["pagination"]["pages_fetched"], 2)
        second_params = dict(fake.calls[1][1])
        self.assertEqual(second_params["offset"], 2)
        self.assertEqual(second_params["facets[series][]"], "NW2_EPG0_SWO_R48_BCF")
        self.assertEqual(second_params["sort[0][direction]"], "desc")

    def test_duplicate_observation_is_removed_explicitly(self) -> None:
        rows = [
            {"period": "2026-01-09", "value": 10, "series": "NW2_EPG0_SWO_R31_BCF"},
            {"period": "2026-01-09", "value": 10, "series": "NW2_EPG0_SWO_R31_BCF"},
        ]
        result = HistoryClient("key", http=FakeHttp([page(rows, 2)]), page_size=10).fetch(REGIONS["east"], "2026-01-09", "2026-01-09")
        self.assertEqual(len(result["observations"]), 1)
        self.assertIn("duplicate", result["warnings"][0])

    def test_limit_truncation(self) -> None:
        rows = [
            {"period": "2026-01-16", "value": 10, "series": "NW2_EPG0_SWO_R31_BCF"},
            {"period": "2026-01-09", "value": 11, "series": "NW2_EPG0_SWO_R31_BCF"},
        ]
        result = HistoryClient("key", http=FakeHttp([page(rows, 10)]), page_size=5).fetch(REGIONS["east"], "2026-01-01", "2026-02-01", limit=2)
        self.assertTrue(result["pagination"]["truncated"])

    def test_date_boundaries_and_invalid_ranges(self) -> None:
        self.assertEqual(validate_date_range("2026-01-01", "2026-01-01")[0].isoformat(), "2026-01-01")
        with self.assertRaises(InputError):
            validate_date_range("2026-02-01", "2026-01-01")
        with self.assertRaises(InputError):
            validate_date_range("01/01/2026", "2026-01-02")

    def test_missing_key_and_invalid_key_failure_are_explicit(self) -> None:
        with self.assertRaises(ConfigurationError):
            HistoryClient(None)
        denied = RetrievalError("EIA rejected the request", status=403, url="https://api.eia.gov/redacted")
        with self.assertRaises(RetrievalError):
            HistoryClient("invalid", http=FakeHttp([denied])).fetch(REGIONS["lower48"], "2026-01-01", "2026-01-31")

    def test_wrong_series_and_out_of_range_are_rejected(self) -> None:
        wrong = page([{"period": "2026-01-09", "value": 1, "series": "WRONG"}], 1)
        with self.assertRaises(SchemaError):
            HistoryClient("key", http=FakeHttp([wrong])).fetch(REGIONS["east"], "2026-01-01", "2026-01-31")
        outside = page([{"period": "2025-12-26", "value": 1, "series": "NW2_EPG0_SWO_R31_BCF"}], 1)
        with self.assertRaises(SchemaError):
            HistoryClient("key", http=FakeHttp([outside])).fetch(REGIONS["east"], "2026-01-01", "2026-01-31")


if __name__ == "__main__":
    unittest.main()
