from __future__ import annotations

import contextlib
import io
import json
import unittest

from eia_storage.cli import main


class CliTests(unittest.TestCase):
    def test_success_is_json_on_stdout(self) -> None:
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main("fetch_latest", ["--region", "east"], dispatcher=lambda command, args: {"command": command, "region": args.region})
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["region"], "east")
        self.assertEqual(err.getvalue(), "")

    def test_input_error_is_json_on_stderr_with_stable_exit(self) -> None:
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main("fetch_history", ["--region", "east"])
        self.assertEqual(code, 2)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(json.loads(err.getvalue())["error"]["code"], "invalid_input")


if __name__ == "__main__":
    unittest.main()
