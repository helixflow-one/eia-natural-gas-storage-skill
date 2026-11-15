"""Configuration constants and local secret loading."""

from __future__ import annotations

import os
from pathlib import Path

LATEST_JSON_URL = "https://ir.eia.gov/ngs/wngsr.json"
LATEST_CSV_URL = "https://ir.eia.gov/ngs/wngsr.csv"
HISTORY_API_URL = "https://api.eia.gov/v2/natural-gas/stor/wkly/data/"
SCHEDULE_URL = "https://ir.eia.gov/ngs/schedule.html"
HISTORY_XLS_URL = "https://ir.eia.gov/ngs/ngshistory.xls"

DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_RETRIES = 2
DEFAULT_PAGE_SIZE = 500
MAX_PAGE_SIZE = 5_000
MAX_HISTORY_ROWS = 50_000


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a conservative KEY=VALUE file without mutating os.environ."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"Invalid .env entry on line {line_number}")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not key.replace("_", "").isalnum() or not key[0].isalpha():
            raise ValueError(f"Invalid .env key on line {line_number}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def get_setting(name: str, default: str | None = None, env_file: Path | None = None) -> str | None:
    """Return process environment first, then project .env, then default."""
    process_value = os.environ.get(name)
    if process_value is not None and process_value.strip():
        return process_value.strip()
    local_values = _parse_env_file(env_file or project_root() / ".env")
    local_value = local_values.get(name)
    if local_value is not None and local_value.strip():
        return local_value.strip()
    return default


def get_api_key() -> str | None:
    return get_setting("EIA_API_KEY")

