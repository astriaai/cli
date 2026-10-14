import runpy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


CLI = runpy.run_path(Path(__file__).parents[1] / "astria", run_name="astria_test")


def run_request(method, **kwargs):
    calls = []

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout=b'{"id": 1}\n201', stderr=b"")

    with patch.dict(CLI["request"].__globals__, {"api_key": lambda _cfg: "key", "base_url": lambda _cfg: "https://api.example"}):
        with patch.object(CLI["subprocess"], "run", fake_run):
            CLI["request"]({}, method, "/tunes/1/prompts", no_workspace=True, **kwargs)
    return calls[0]


def header(argv, name):
    values = [argv[i + 1] for i, arg in enumerate(argv[:-1]) if arg == "-H" and argv[i + 1].startswith(f"{name}: ")]
    return values[0].split(": ", 1)[1] if values else None


class IdempotencyTest(unittest.TestCase):
    def test_post_carries_an_idempotency_key_so_curl_retries_are_safe(self):
        argv = run_request("POST", form=[("prompt[text]", "a")])
        self.assertIn("--retry", argv)
        self.assertRegex(header(argv, "Idempotency-Key"), r"^astria-cli-[0-9a-f]{32}$")

    def test_each_post_gets_its_own_key(self):
        first = header(run_request("POST"), "Idempotency-Key")
        second = header(run_request("POST"), "Idempotency-Key")
        self.assertNotEqual(first, second)

    def test_explicit_key_is_sent_verbatim(self):
        self.assertEqual(header(run_request("POST", idempotency_key="job-42"), "Idempotency-Key"), "job-42")

    def test_get_sends_no_key(self):
        self.assertIsNone(header(run_request("GET"), "Idempotency-Key"))


if __name__ == "__main__":
    unittest.main()
