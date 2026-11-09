import runpy
import unittest
from argparse import Namespace
from pathlib import Path


CLI = runpy.run_path(Path(__file__).parents[1] / "astria", run_name="astria_test")


class ArchiveTest(unittest.TestCase):
    def tool(self, name):
        return next(tool for tool in CLI["operation_catalog"]() if tool["name"] == name)

    def test_schemas_take_an_id_and_an_unarchive_flag(self):
        for name in ("archive_prompt", "archive_reference"):
            schema = self.tool(name)["inputSchema"]
            self.assertEqual(schema["properties"]["unarchive"]["type"], "boolean")
            self.assertEqual(schema["required"], ["id", "idempotency_key"])

    def test_archiving_is_a_reversible_write(self):
        for name in ("archive_prompt", "archive_reference"):
            self.assertEqual(self.tool(name)["annotations"], {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True})

    def test_unarchive_selects_the_restore_route(self):
        for name, resource in (("archive_prompt", "prompts"), ("archive_reference", "tunes")):
            definition = CLI["API_OPERATIONS"][name]
            self.assertEqual(CLI["operation_path"](definition, {"id": 7, "unarchive": False}), f"/{resource}/7/archive")
            self.assertEqual(CLI["operation_path"](definition, {"id": 7, "unarchive": True}), f"/{resource}/7/unarchive")

    def test_references_can_be_listed_from_the_archive(self):
        self.assertEqual(self.tool("list_references")["inputSchema"]["properties"]["archived"]["type"], "boolean")
        self.assertIn(["archived", "archived", "truthy"], CLI["API_OPERATIONS"]["list_references"]["fields"])


if __name__ == "__main__":
    unittest.main()
