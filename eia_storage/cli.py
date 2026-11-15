"""Cross-platform JSON command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

from .analysis import compare_history, compare_latest
from .config import get_api_key
from .errors import InputError, SkillError
from .history import HistoryClient
from .latest import fetch_latest
from .regions import REGIONS, resolve_region
from .schedule import fetch_schedule
from .validation import validate_history_source, validate_latest_source


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InputError(message)


def _parser(command: str) -> JsonArgumentParser:
    parser = JsonArgumentParser(prog=f"python scripts/{command}.py")
    parser.add_argument("--format", default="json", choices=["json"], help="Output format (JSON only in MVP)")
    if command == "fetch_latest":
        parser.add_argument("--region", default="lower48", choices=sorted(REGIONS))
    elif command == "fetch_history":
        parser.add_argument("--region", required=True, choices=sorted(REGIONS))
        parser.add_argument("--start", required=True, dest="start_date")
        parser.add_argument("--end", required=True, dest="end_date")
        parser.add_argument("--limit", type=int)
    elif command == "analyze":
        parser.add_argument("--region", default="lower48", choices=sorted(REGIONS))
        parser.add_argument("--reference-date", default="latest", help="YYYY-MM-DD or latest")
        parser.add_argument("--lookback-years", type=int, default=5)
    elif command == "schedule":
        parser.add_argument("--start", dest="start_date")
        parser.add_argument("--end", dest="end_date")
    elif command == "validate":
        parser.add_argument("--source", required=True, choices=["latest", "history"])
    else:
        raise ValueError(f"Unsupported command: {command}")
    return parser


def dispatch(command: str, args: argparse.Namespace) -> dict[str, Any]:
    if command == "fetch_latest":
        return fetch_latest(resolve_region(args.region))
    if command == "fetch_history":
        return HistoryClient(get_api_key()).fetch(resolve_region(args.region), args.start_date, args.end_date, limit=args.limit)
    if command == "analyze":
        region = resolve_region(args.region)
        if args.reference_date == "latest":
            return compare_latest(region)
        return compare_history(region, args.reference_date, args.lookback_years, HistoryClient(get_api_key()))
    if command == "schedule":
        return fetch_schedule(start_date=args.start_date, end_date=args.end_date)
    if command == "validate":
        return validate_latest_source() if args.source == "latest" else validate_history_source()
    raise ValueError(f"Unsupported command: {command}")


def main(command: str, argv: list[str] | None = None, *, dispatcher: Callable[[str, argparse.Namespace], dict[str, Any]] = dispatch) -> int:
    try:
        args = _parser(command).parse_args(argv)
        result = dispatcher(command, args)
        print(json.dumps(result, indent=2, sort_keys=False, allow_nan=False))
        return 0
    except SkillError as exc:
        print(json.dumps(exc.as_dict(), indent=2, sort_keys=False), file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        safe = {"ok": False, "error": {"code": "internal_error", "message": "Unexpected local runtime failure", "details": {"exception_type": type(exc).__name__}}}
        print(json.dumps(safe, indent=2), file=sys.stderr)
        return 1

