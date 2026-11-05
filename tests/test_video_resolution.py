import io
import json
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


class ReferenceMediaTest(unittest.TestCase):
    def video_args(self, *argv):
        parser = CLI["operation_parser"](("video",))
        return parser.parse_args(["--video-prompt", "x", *argv])

    def test_repeated_flags_keep_order_and_old_flag_still_works(self):
        args = self.video_args("--video-reference", "https://a/1.mp4", "--input-video", "https://a/2.mp4",
                               "--audio-reference", "https://a/1.mp3", "--audio-reference", "https://a/2.mp3")
        self.assertEqual(args.video_references, ["https://a/1.mp4", "https://a/2.mp4"])
        self.assertEqual(args.audio_references, ["https://a/1.mp3", "https://a/2.mp3"])

    def test_catalog_shows_only_the_arrays(self):
        tool = next(item for item in CLI["operation_catalog"]() if item["name"] == "generate_video")
        properties = tool["inputSchema"]["properties"]
        self.assertEqual(properties["video_references"]["type"], "array")
        self.assertEqual(properties["audio_references"]["type"], "array")
        self.assertIn("@Video1", properties["video_references"]["description"])
        self.assertNotIn("input_video", properties)
        self.assertNotIn("audio_reference", properties)
        music = next(item for item in CLI["operation_catalog"]() if item["name"] == "generate_music")
        self.assertIn("audio_reference", music["inputSchema"]["properties"])

    def test_form_mixes_files_and_urls_in_one_ordered_array(self):
        definition = CLI["API_OPERATIONS"]["generate_video"]
        field = next(spec for spec in definition["fields"] if spec[1] == "video_references")
        self.assertEqual(field, ["prompt[video_references][]", "video_references", "media_array", "prompt[video_references][]"])


class VideoResolutionTest(unittest.TestCase):
    def submitted_form(self, **overrides):
        args = SimpleNamespace(
            model="123", references=[], text=None, num_images="1", seed=None, aspect_ratio="16:9",
            resolution=None, input_image=None, mask_image=None, pack_id=None, base_pack_id=None,
            video_model="seedance25", video_resolution="1080p", video_prompt="slow dolly-in", duration="5",
            image_references=None, first_frame=None, last_frame=None, video_references=None, audio_references=None,
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

    def test_leaves_aspect_ratio_and_image_count_to_the_server(self):
        # Video models differ in supported ratios (Kling 4.0 has no 3:4) and video prompts take one first frame.
        parser = CLI["build_parser"]({})
        ns = parser.parse_args(["video", "--video-prompt", "x"])
        self.assertIsNone(ns.aspect_ratio)
        self.assertIsNone(ns.num_images)
        form = self.submitted_form(aspect_ratio=None, num_images=None)
        self.assertNotIn("prompt[aspect_ratio]", form)
        self.assertNotIn("prompt[num_images]", form)
        contract = CLI["operation_contract"]()["operations"]["generate_video"]
        self.assertIsNone(contract["defaults"]["aspect_ratio"])
        self.assertNotIn("image_count", contract)

    def test_omits_resolution_for_the_family_default(self):
        self.assertNotIn("prompt[video_resolution]", self.submitted_form(video_resolution=None))

    def test_help_lists_families_and_their_resolutions(self):
        record = {"video_model_families": FAMILIES}
        self.assertIn("seedance25, kling30_pro", CLI["video_model_help"](record))
        self.assertIn("seedance25: 480p/720p/1080p", CLI["video_resolution_help"](record))
        self.assertNotIn("kling30_pro:", CLI["video_resolution_help"](record))

    def test_omitted_video_model_uses_the_catalog_family_default(self):
        catalog = {"default_video_model_family": "seedance25"}
        with patch.dict(CLI["apply_catalog_defaults"].__globals__, {"model_catalog": lambda _cfg: catalog}):
            form = self.submitted_form(video_model=None, video_resolution=None)
        self.assertEqual(form["prompt[video_model]"], "seedance25")
        self.assertNotIn("prompt[video_resolution]", form)

    def test_mcp_video_model_is_optional_and_null_for_defaults(self):
        tool = next(tool for tool in CLI["operation_catalog"]() if tool["name"] == "generate_video")
        self.assertEqual(tool["inputSchema"]["required"], ["video_prompt", "idempotency_key"])
        video_model = tool["inputSchema"]["properties"]["video_model"]
        self.assertEqual(video_model["anyOf"], [{"type": "string"}, {"type": "null"}])
        self.assertIn("submit null for Astria defaults", video_model["description"])
        self.assertIn("video_model=null", tool["description"])
        self.assertNotIn("astria models", json.dumps(CLI["operation_catalog"]()))

    def test_mcp_tool_accepts_video_resolution(self):
        tool = next(tool for tool in CLI["operation_catalog"]() if tool["name"] == "generate_video")
        self.assertEqual(tool["inputSchema"]["properties"]["video_resolution"]["anyOf"], [{"type": "string"}, {"type": "null"}])
        self.assertIn("video_resolution", CLI["operation_contract"]()["operations"]["generate_video"]["defaults"])


if __name__ == "__main__":
    unittest.main()
