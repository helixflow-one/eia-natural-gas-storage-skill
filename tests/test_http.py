from __future__ import annotations

import unittest
from unittest.mock import patch

import requests

from eia_storage.errors import RetrievalError, SchemaError
from eia_storage.http import EIAHttpClient, redact_url


def response(status=200, body='{}', content_type='application/json'):
    item = requests.Response()
    item.status_code = status
    item._content = body.encode("utf-8")
    item.headers["Content-Type"] = content_type
    item.url = "https://example.test/result"
    return item


class FakeSession:
    def __init__(self, items):
        self.items = list(items)
        self.calls = []
        self.headers = {}

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class HttpTests(unittest.TestCase):
    def test_redirect_support_is_explicit(self) -> None:
        fake = FakeSession([response()])
        EIAHttpClient(session=fake).get("https://example.test")
        self.assertTrue(fake.calls[0][1]["allow_redirects"])

    def test_timeout_retries_are_bounded(self) -> None:
        fake = FakeSession([requests.Timeout(), requests.Timeout(), requests.Timeout()])
        with patch("eia_storage.http.time.sleep"):
            with self.assertRaises(RetrievalError) as caught:
                EIAHttpClient(session=fake, retries=2).get("https://example.test")
        self.assertEqual(len(fake.calls), 3)
        self.assertEqual(caught.exception.details["reason"], "Timeout")

    def test_transient_status_retries_then_succeeds(self) -> None:
        fake = FakeSession([response(503), response(200)])
        with patch("eia_storage.http.time.sleep"):
            result = EIAHttpClient(session=fake, retries=2).get_json("https://example.test")
        self.assertEqual(result, {})
        self.assertEqual(len(fake.calls), 2)

    def test_non_transient_http_error_is_immediate(self) -> None:
        fake = FakeSession([response(404)])
        with self.assertRaises(RetrievalError) as caught:
            EIAHttpClient(session=fake, retries=2).get("https://example.test")
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(caught.exception.details["status"], 404)

    def test_content_type_and_malformed_json_are_validated(self) -> None:
        with self.assertRaises(SchemaError):
            EIAHttpClient(session=FakeSession([response(body="hello", content_type="text/plain")])).get_json("https://example.test")
        with self.assertRaises(SchemaError):
            EIAHttpClient(session=FakeSession([response(body="{bad")])).get_json("https://example.test")

    def test_utf8_bom_json_is_accepted(self) -> None:
        result = EIAHttpClient(session=FakeSession([response(body="\ufeff{\"release_name\": \"WNGSR\"}")])).get_json("https://example.test")
        self.assertEqual(result["release_name"], "WNGSR")

    def test_secret_query_parameters_are_redacted(self) -> None:
        safe = redact_url("https://example.test/data?api_key=secret&start=2026-01-01&Signature=signed&Key-Pair-Id=pair")
        self.assertNotIn("secret", safe)
        self.assertNotIn("signed", safe)
        self.assertNotIn("pair", safe)
        self.assertIn("start=2026-01-01", safe)


if __name__ == "__main__":
    unittest.main()

