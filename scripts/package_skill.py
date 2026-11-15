"""Build a portable skill archive while refusing to include local secrets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eia_storage.config import get_api_key

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = (
    "SKILL.md", "agents", "eia_storage", "references", "scripts", "tests",
    "requirements.txt", "pyproject.toml", ".env.example",
)
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".git", "dist"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def included_files() -> list[Path]:
    files: list[Path] = []
    for name in INCLUDE:
        candidate = ROOT / name
        if candidate.is_file():
            files.append(candidate)
        elif candidate.is_dir():
            files.extend(path for path in candidate.rglob("*") if path.is_file())
    return sorted(
        path for path in files
        if not (set(path.relative_to(ROOT).parts) & EXCLUDED_PARTS)
        and path.suffix not in EXCLUDED_SUFFIXES
        and path.name != ".env"
    )


def build(output: Path) -> dict[str, object]:
    files = included_files()
    live_key = get_api_key()
    for path in files:
        content = path.read_bytes()
        if live_key and live_key.encode("utf-8") in content:
            raise RuntimeError(f"Refusing to package a live API key found in {path.relative_to(ROOT)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, Path("eia-natural-gas-storage") / path.relative_to(ROOT))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return {"archive": str(output), "files": len(files), "sha256": digest, "contains_env": False}


if __name__ == "__main__":
    destination = ROOT / "dist" / "eia-natural-gas-storage-skill.zip"
    try:
        print(json.dumps(build(destination), indent=2))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": {"code": "package_failed", "message": str(exc)}}), file=sys.stderr)
        raise SystemExit(1)

