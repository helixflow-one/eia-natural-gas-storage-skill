from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.package_skill import build


class PackageTests(unittest.TestCase):
    def test_release_archive_excludes_secrets_and_caches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "skill.zip"
            result = build(output)
            self.assertFalse(result["contains_env"])
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
            self.assertTrue(any(name.endswith("/SKILL.md") for name in names))
            self.assertTrue(any(name.endswith("/.env.example") for name in names))
            self.assertFalse(any(name.endswith("/.env") for name in names))
            self.assertFalse(any("__pycache__" in name for name in names))


if __name__ == "__main__":
    unittest.main()
