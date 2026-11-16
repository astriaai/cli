import runpy
import unittest
from pathlib import Path


CLI = runpy.run_path(Path(__file__).parents[1] / "astria", run_name="astria_test")


class DetectRegionsTest(unittest.TestCase):
    def tool(self):
        return next(tool for tool in CLI["operation_catalog"]() if tool["name"] == "detect_reference_regions")

    def test_schema_takes_the_reference_and_image(self):
        schema = self.tool()["inputSchema"]
        self.assertEqual(schema["required"], ["id", "blob_id", "idempotency_key"])
        self.assertEqual(set(schema["properties"]), {"workspace", "id", "blob_id", "idempotency_key"})

    def test_detection_is_a_non_destructive_write(self):
        self.assertEqual(self.tool()["annotations"], {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True})

    def test_posts_to_the_image_detect_route(self):
        definition = CLI["API_OPERATIONS"]["detect_reference_regions"]
        self.assertEqual(definition["method"], "POST")
        self.assertEqual(CLI["operation_path"](definition, {"id": 7, "blob_id": 15}), "/tunes/7/images/15/lynx_autotag")


if __name__ == "__main__":
    unittest.main()
