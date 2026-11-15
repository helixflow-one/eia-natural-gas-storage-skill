from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eia_storage.config import get_setting


class ConfigurationTests(unittest.TestCase):
    def test_environment_precedes_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("EIA_API_KEY=file-value\n", encoding="utf-8")
            with patch.dict(os.environ, {"EIA_API_KEY": "process-value"}):
                self.assertEqual(get_setting("EIA_API_KEY", env_file=env_file), "process-value")

    def test_dotenv_fallback_and_empty_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("EIA_API_KEY=file-value\nEMPTY=\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(get_setting("EIA_API_KEY", env_file=env_file), "file-value")
                self.assertEqual(get_setting("EMPTY", "fallback", env_file=env_file), "fallback")


if __name__ == "__main__":
    unittest.main()

