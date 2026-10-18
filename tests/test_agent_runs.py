import io
import os
import runpy
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


CLI = runpy.run_path(Path(__file__).parents[1] / "astria", run_name="astria_test")


class AgentRunCommandTest(unittest.TestCase):
    def run_command(self, *argv):
        calls = []

        def request(_cfg, method, path, **options):
            calls.append((method, path, options))
            return {"id": 42, "status": {"state": "submitted"}}

        args = CLI["build_parser"]({}).parse_args(["agent", *argv])
        with patch.dict(CLI["execute_api_operation"].__globals__, {"request": request}), patch.dict(os.environ, {}, clear=True):
            with redirect_stdout(io.StringIO()):
                args.func(args, {})
        return calls[0]

    def test_start_posts_the_message_to_the_workspace(self):
        method, path, options = self.run_command("start", "/music-video a runway film", "--workspace", "7")
        self.assertEqual((method, path), ("POST", "/api/agent_runs"))
        self.assertEqual(dict(options["form"]), {"workspace_id": "7", "message": "/music-video a runway film"})
        self.assertEqual(options["workspace"], "7")

    def test_start_requires_a_workspace(self):
        with self.assertRaises(SystemExit):
            self.run_command("start", "/music-video")

    def test_reply_sends_answers_as_a_top_level_json_body(self):
        method, path, options = self.run_command("reply", "42", "--tool-call-id", "call-1",
                                                 "--answers", '{"Which location?": "Beach", "Looks?": ["A", "B"]}')
        self.assertEqual((method, path), ("POST", "/api/agent_runs/42/reply"))
        self.assertEqual(options["json_body"], {"tool_call_id": "call-1", "answers": {"Which location?": "Beach", "Looks?": ["A", "B"]}})
        self.assertTrue(options["no_workspace"])

    def test_get_and_cancel_address_the_run(self):
        self.assertEqual(self.run_command("get", "42")[:2], ("GET", "/api/agent_runs/42"))
        self.assertEqual(self.run_command("cancel", "42")[:2], ("POST", "/api/agent_runs/42/cancel"))


class AgentRunOperationTest(unittest.TestCase):
    def tools(self):
        return {tool["name"]: tool for tool in CLI["operation_catalog"]() if tool["name"].endswith("_agent_run")}

    def test_mcp_exposes_start_get_reply_and_cancel(self):
        tools = self.tools()
        self.assertEqual(set(tools), {"start_agent_run", "get_agent_run", "reply_agent_run", "cancel_agent_run"})
        self.assertEqual(tools["start_agent_run"]["inputSchema"]["required"], ["message", "workspace", "idempotency_key"])
        self.assertTrue(tools["get_agent_run"]["annotations"]["readOnlyHint"])
        self.assertIn("idempotency_key", tools["reply_agent_run"]["inputSchema"]["required"])
        self.assertTrue(tools["cancel_agent_run"]["annotations"]["destructiveHint"])

    def test_answers_accept_labels_or_label_arrays_only(self):
        schema = self.tools()["reply_agent_run"]["inputSchema"]["properties"]["answers"]
        validate = CLI["validate_argument"]
        self.assertTrue(validate(schema, {"Which location?": "Beach", "Looks?": ["A", "B"]}))
        self.assertFalse(validate(schema, {"Which location?": 3}))
        self.assertFalse(validate(schema, {"Looks?": []}))


if __name__ == "__main__":
    unittest.main()
