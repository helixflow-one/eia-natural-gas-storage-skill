"""Bounded, read-only HTTP client with redacted diagnostics."""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from .config import DEFAULT_RETRIES, DEFAULT_TIMEOUT_SECONDS
from .errors import RetrievalError, SchemaError

TRANSIENT_STATUS = {408, 425, 429, 500, 502, 503, 504}
SECRET_QUERY_KEYS = {"api_key", "apikey", "key", "signature", "policy", "key-pair-id"}


def redact_url(url: str) -> str:
    parts = urlsplit(url)
    safe_query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        safe_query.append((key, "[REDACTED]" if key.lower() in SECRET_QUERY_KEYS else value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(safe_query, doseq=True), ""))


class EIAHttpClient:
    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        retries: int = DEFAULT_RETRIES,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", "eia-natural-gas-storage-skill/1.0")

    def get(self, url: str, *, params: dict[str, Any] | list[tuple[str, Any]] | None = None) -> requests.Response:
        safe_url = redact_url(url)
        last_reason = "unknown"
        for attempt in range(self.retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout, allow_redirects=True)
                if response.status_code in TRANSIENT_STATUS and attempt < self.retries:
                    retry_after = response.headers.get("Retry-After")
                    delay = min(float(retry_after), 8.0) if retry_after and retry_after.isdigit() else 0.5 * (2**attempt)
                    time.sleep(delay)
                    continue
                if response.status_code in {401, 403}:
                    raise RetrievalError(
                        "EIA rejected the request; verify EIA_API_KEY configuration",
                        status=response.status_code,
                        url=safe_url,
                    )
                response.raise_for_status()
                return response
            except RetrievalError:
                raise
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                raise RetrievalError("EIA returned a non-success HTTP status", url=safe_url, status=status) from exc
            except requests.RequestException as exc:
                last_reason = type(exc).__name__
                if attempt < self.retries:
                    time.sleep(0.5 * (2**attempt))
                    continue
        raise RetrievalError("EIA request failed after bounded retries", url=safe_url, reason=last_reason)

    def get_json(self, url: str, *, params: dict[str, Any] | list[tuple[str, Any]] | None = None) -> dict[str, Any]:
        response = self.get(url, params=params)
        content_type = response.headers.get("Content-Type", "").lower()
        if "json" not in content_type and not response.text.lstrip("\ufeff \t\r\n").startswith(("{", "[")):
            raise SchemaError("EIA response is not JSON", content_type=content_type or None, url=redact_url(url))
        try:
            payload = json.loads(response.content.decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise SchemaError("EIA returned malformed JSON", url=redact_url(url)) from exc
        if not isinstance(payload, dict):
            raise SchemaError("Expected a JSON object", received_type=type(payload).__name__)
        return payload

