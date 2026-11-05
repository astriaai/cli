import runpy
import unittest
from pathlib import Path


CLI = runpy.run_path(Path(__file__).parents[1] / "astria", run_name="astria_test")


class EnhanceVideoTest(unittest.TestCase):
    def tool(self):
        return next(tool for tool in CLI["operation_catalog"]() if tool["name"] == "enhance_video")

    def test_schema_offers_the_upscale_and_fps_options(self):
        schema = self.tool()["inputSchema"]

        self.assertEqual(schema["properties"]["video_upscale_model"]["enum"], ["seedvr2"])
        self.assertEqual(schema["properties"]["video_upscale_target_resolution"]["enum"], ["720p", "1080p", "2k", "4k"])
        self.assertEqual(schema["properties"]["video_fps_model"]["enum"], ["video_fps_increaser"])
        self.assertEqual(schema["required"], ["id", "idempotency_key"])

    def test_it_is_a_paid_write_that_replaces_nothing(self):
        self.assertEqual(self.tool()["annotations"], {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True})

    def test_it_requires_an_enhancement(self):
        self.assertEqual(CLI["API_OPERATIONS"]["enhance_video"]["requires_any"], ["video_upscale_model", "video_fps_model"])


if __name__ == "__main__":
    unittest.main()
