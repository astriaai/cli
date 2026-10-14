import io
import runpy
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


CLI = runpy.run_path(Path(__file__).parents[1] / "astria", run_name="astria_test")
FAMILIES = {
    "seedance25": {"title": "Seedance 2.5", "resolutions": ["480p", "720p", "1080p"], "default_resolution": "720p",
                   "generates_audio": True},
    "kling30_pro": {"title": "Kling 3.0 Pro", "resolutions": [], "default_resolution": None, "generates_audio": True},
}


class VideoResolutionTest(unittest.TestCase):
    def submitted_form(self, **overrides):
        args = SimpleNamespace(
            model="123", references=[], text=None, num_images="1", seed=None, aspect_ratio="16:9",
            resolution=None, input_image=None, mask_image=None, pack_id=None, base_pack_id=None,
            video_model="seedance25", video_resolution="1080p", video_prompt="slow dolly-in", duration="5",
            image_references=None, first_frame=None, last_frame=None, input_video=None, audio_reference=None,
            generate_audio=None, workspace=None, wait=False,
        )
        vars(args).update(overrides)
        captured = {}

        def request(_cfg, _method, _path, form, workspace):
            captured["form"] = form
            return {"id": 9}

        with patch.dict(CLI["_generate"].__globals__, {"request": request}):
            with redirect_stdout(io.StringIO()):
                CLI["_generate"](args, {}, video=True)
        return dict(captured["form"])

    def test_sends_family_and_resolution(self):
        form = self.submitted_form()
        self.assertEqual(form["prompt[video_model]"], "seedance25")
        self.assertEqual(form["prompt[video_resolution]"], "1080p")

    def test_video_parser_accepts_seed_and_sends_it(self):
        # a 480p draft and its 1080p final share one seed; `astria video` must accept --seed (1.20.1 refused it)
        parser = CLI["build_parser"]({}) if "build_parser" in CLI else None
        if parser is not None:
            ns = parser.parse_args(["video", "--video-model", "seedance25", "--video-prompt", "x", "--seed", "42"])
            self.assertEqual(ns.seed, "42")
        self.assertEqual(self.submitted_form(seed="42")["prompt[seed]"], "42")

    def test_omits_resolution_for_the_family_default(self):
        self.assertNotIn("prompt[video_resolution]", self.submitted_form(video_resolution=None))

    def test_help_lists_families_and_their_resolutions(self):
        record = {"video_model_families": FAMILIES}
        self.assertIn("seedance25, kling30_pro", CLI["video_model_help"](record))
        self.assertIn("seedance25: 480p/720p/1080p", CLI["video_resolution_help"](record))
        self.assertNotIn("kling30_pro:", CLI["video_resolution_help"](record))

    def test_mcp_tool_accepts_video_resolution(self):
        tool = next(tool for tool in CLI["operation_catalog"]() if tool["name"] == "generate_video")
        self.assertEqual(tool["inputSchema"]["properties"]["video_resolution"]["type"], "string")
        self.assertIn("video_resolution", CLI["operation_contract"]()["operations"]["generate_video"]["defaults"])


if __name__ == "__main__":
    unittest.main()
