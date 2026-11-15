from __future__ import annotations

import copy
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from eia_storage.errors import InputError, SchemaError
from eia_storage.normalize import normalize_latest
from eia_storage.regions import REGIONS, resolve_region


FIXTURE = Path(__file__).parent / "fixtures" / "wngsr_2026_11_13.json"


class NormalizeLatestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_regression_lower48(self) -> None:
        result = normalize_latest(
            self.payload,
            REGIONS["lower48"],
            retrieved_at=datetime(2026, 11, 13, 16, tzinfo=timezone.utc),
        )
        self.assertEqual(result["report_date"], "2026-11-06")
        self.assertEqual(result["stocks_bcf"], 3862)
        self.assertEqual(result["net_change_bcf"], 61)
        self.assertEqual(result["five_year_average_bcf"], 3787)
        self.assertEqual(result["source_url"], "https://ir.eia.gov/ngs/wngsr.json")
        self.assertEqual(result["freshness_status"], "unknown")

    def test_all_canonical_regions_map_by_exact_series_id(self) -> None:
        for key, region in REGIONS.items():
            with self.subTest(region=key):
                result = normalize_latest(self.payload, region)
                self.assertEqual(result["region"], key)
                self.assertEqual(result["series_id"], region.latest_series_id)
                self.assertGreater(result["stocks_bcf"], 0)

    def test_revision_and_reclassification_flags_preserved(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["series"][0]["revision_flag"][0] = "true"
        payload["series"][0]["calculated"]["revision_flag_net_change"] = "true"
        result = normalize_latest(payload, REGIONS["lower48"])
        self.assertTrue(result["revision_flags"]["observations"]["2026-11-06"]["revision"])
        self.assertTrue(result["revision_flags"]["calculated"]["net_change"]["revision"])

    def test_observations_are_selected_by_date_not_position(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["series"][0]["data"].reverse()
        payload["series"][0]["revision_flag"].reverse()
        payload["series"][0]["reclassification_flag"].reverse()
        result = normalize_latest(payload, REGIONS["lower48"])
        self.assertEqual(result["stocks_bcf"], 3862)
        self.assertEqual(result["year_ago_stocks_bcf"], 3954)

    def test_missing_required_field_fails_with_observed_names(self) -> None:
        payload = copy.deepcopy(self.payload)
        del payload["current_week"]
        with self.assertRaises(SchemaError) as caught:
            normalize_latest(payload, REGIONS["lower48"])
        self.assertIn("current_week", caught.exception.details["missing_fields"])
        self.assertNotIn("current_week", caught.exception.details["observed_fields"])

    def test_invalid_region_is_typed_input_error(self) -> None:
        with self.assertRaises(InputError):
            resolve_region("not-a-region")

    def test_rounding_discrepancy_is_warning_not_rewrite(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["series"][0]["calculated"]["net_change"] = 50
        result = normalize_latest(payload, REGIONS["lower48"])
        self.assertEqual(result["net_change_bcf"], 50)
        self.assertTrue(any("differs" in warning for warning in result["warnings"]))


if __name__ == "__main__":
    unittest.main()

