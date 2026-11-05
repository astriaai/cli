import contextlib
import io
import runpy
import unittest
from pathlib import Path
from unittest import mock


CLI = Path(__file__).parents[1] / "astria"


class TemplateTextTest(unittest.TestCase):
    def test_prints_the_text_as_written_and_sends_the_filter(self):
        core = runpy.run_path(str(CLI), run_name="astria_shared")
        args = core["build_parser"]().parse_args(["packs", "text", "hat", "--class", "tank top", "--limit", "10"])
        calls = []

        def transport(_cfg, method, path, **options):
            calls.append((method, path, options["query"]))
            return "# Hat\n\nכובע\n"

        stdout = io.StringIO()
        with mock.patch.dict(args.func.__globals__, {"request": transport}), contextlib.redirect_stdout(stdout):
            args.func(args, {})

        self.assertEqual(stdout.getvalue(), "# Hat\n\nכובע\n")
        self.assertEqual(calls, [("GET", "/p/hat.txt", [("class", "tank top"), ("limit", "10")])])


if __name__ == "__main__":
    unittest.main()
