import os
import subprocess
import sys
import unittest
from pathlib import Path


CLI = Path(__file__).parents[1] / "astria"


class MetaCommandsTest(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            capture_output=True,
            text=True,
            env={**os.environ, "ASTRIA_NO_AUTO_UPGRADE": "1"},
        )

    def test_top_level_help_forms_match(self):
        short = self.run_cli("-h")
        long = self.run_cli("--help")
        command = self.run_cli("help")

        self.assertEqual(short.returncode, 0)
        self.assertEqual(long.returncode, 0)
        self.assertEqual(command.returncode, 0)
        self.assertEqual(short.stdout, long.stdout)
        self.assertEqual(command.stdout, long.stdout)

    def test_help_command_accepts_nested_command_path(self):
        command = self.run_cli("help", "tunes", "create")
        flag = self.run_cli("tunes", "create", "--help")

        self.assertEqual(command.returncode, 0)
        self.assertEqual(command.stdout, flag.stdout)
        self.assertIn("usage: astria tunes create", command.stdout)

    def test_version_forms_match(self):
        short = self.run_cli("-v")
        long = self.run_cli("--version")
        command = self.run_cli("version")

        self.assertEqual(short.returncode, 0)
        self.assertEqual(long.returncode, 0)
        self.assertEqual(command.returncode, 0)
        self.assertEqual(short.stdout, "astria 1.19.0\n")
        self.assertEqual(short.stdout, long.stdout)
        self.assertEqual(command.stdout, long.stdout)

    def test_help_alias_works_after_profile_option(self):
        command = self.run_cli("--profile", "localhost", "help", "variate")

        self.assertEqual(command.returncode, 0)
        self.assertIn("usage: astria variate", command.stdout)

    def test_handoff_is_discoverable_from_help(self):
        top_level = self.run_cli("--help")
        handoff = self.run_cli("agent", "handoff", "--help")

        self.assertIn("agent               Astria embedded agent", top_level.stdout)
        self.assertIn("usage: astria agent handoff", handoff.stdout)
        self.assertIn("--skill DIR", handoff.stdout)


if __name__ == "__main__":
    unittest.main()
