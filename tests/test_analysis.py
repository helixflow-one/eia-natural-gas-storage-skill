from __future__ import annotations

import unittest

from eia_storage.analysis import compare_history, compare_latest
from eia_storage.regions import REGIONS


class FakeHistory:
    def fetch(self, region, start, end):
        rows = [
            ("2026-11-06", 3862), ("2025-11-06", 3954), ("2024-11-06", 3900),
            ("2023-11-06", 3800), ("2022-11-06", 3700), ("2021-11-06", 3600),
        ]
        return {
            "observations": [{"report_date": day, "stocks_bcf": value} for day, value in rows],
            "warnings": [], "source_url": "https://api.eia.gov/v2/natural-gas/stor/wkly/data/",
            "source_kind": "eia_api_v2", "retrieved_at_utc": "2026-11-13T16:00:00Z",
        }


class AnalysisTests(unittest.TestCase):
    def test_latest_uses_official_comparisons(self) -> None:
        def latest(region):
            return {
                "report_date": "2026-11-06", "stocks_bcf": 3862, "year_ago_stocks_bcf": 3954,
                "five_year_average_bcf": 3787, "units": {"name": "billion cubic feet", "symbol": "Bcf"},
                "source_url": "https://ir.eia.gov/ngs/wngsr.json", "source_kind": "wngsr_json",
                "retrieved_at_utc": "2026-11-13T16:00:00Z", "freshness_status": "current",
                "freshness": {"status": "current"}, "warnings": [],
            }
        result = compare_latest(REGIONS["lower48"], latest_fetcher=latest)
        self.assertEqual(result["comparisons"]["year_ago"]["difference_bcf"], -92)
        self.assertEqual(result["comparisons"]["five_year"]["percent_difference"], 2.0)
        self.assertIn("EIA-published", result["comparisons"]["five_year"]["method"])

    def test_history_discloses_window_and_inclusion(self) -> None:
        result = compare_history(REGIONS["lower48"], "2026-11-06", 5, FakeHistory())
        self.assertEqual(result["comparisons"]["year_ago"]["reference_bcf"], 3954)
        self.assertEqual(len(result["comparisons"]["five_year"]["observations"]), 5)
        self.assertEqual(result["window"]["missing_weeks"], 0)


if __name__ == "__main__":
    unittest.main()

