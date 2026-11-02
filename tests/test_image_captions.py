import io
import runpy
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch


CLI = runpy.run_path(Path(__file__).parents[1] / "astria", run_name="astria_test")
URLS = ["https://assets.example/front.jpg", "https://assets.example/back.jpg"]
CATALOG = {"default": "nano-banana-2", "models": {"nano-banana-2": {"tune_id": 123}}}


def create_reference(arguments):
    calls = []

    def transport(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return CATALOG if path == "/cli/models" else {"id": 7, "name": "shirt"}

    CLI["run_operation"]("create_reference", {"title": "Shirt", "name": "shirt",
                                              "idempotency_key": "k1", **arguments}, transport)
    return calls[-1]


class ImageCaptionOperationTest(unittest.TestCase):
    def test_mcp_schema_takes_one_caption_per_image_url(self):
        tool = next(tool for tool in CLI["operation_catalog"]() if tool["name"] == "create_reference")
        caption = tool["inputSchema"]["properties"]["image_caption"]
        self.assertEqual(caption["type"], "array")
        self.assertEqual(caption["items"], {"type": "string"})
        self.assertIn("image_url order", caption["description"])
        self.assertNotIn("--", caption["description"])
        self.assertNotIn("image_caption", tool["inputSchema"]["required"])

    def test_captions_are_sent_in_image_url_order(self):
        method, path, kwargs = create_reference({"image_url": URLS, "image_caption": ["front", "back detail"]})
        self.assertEqual((method, path), ("POST", "/tunes"))
        form = kwargs["form"]
        self.assertEqual([value for key, value in form if key == "tune[image_urls][]"], URLS)
        self.assertEqual([value for key, value in form if key == "tune[image_captions][]"], ["front", "back detail"])

    def test_mcp_reference_is_faceid_on_the_catalog_default_model(self):
        tool = next(tool for tool in CLI["operation_catalog"]() if tool["name"] == "create_reference")
        self.assertNotIn("model", tool["inputSchema"]["properties"])
        self.assertNotIn("model_type", tool["inputSchema"]["properties"])
        form = dict(create_reference({"image_url": URLS})[2]["form"])
        self.assertEqual(form["tune[model_type]"], "faceid")
        self.assertEqual(form["tune[base_tune_id]"], "123")

    def test_captions_are_optional(self):
        _method, _path, kwargs = create_reference({"image_url": URLS})
        self.assertNotIn("tune[image_captions][]", dict(kwargs["form"]))

    def test_rejects_a_caption_count_that_differs_from_the_images(self):
        for captions in (["front"], ["front", "back", "side"]):
            with self.assertRaisesRegex(CLI["AstriaError"], "one image_caption per image: 2 images"):
                create_reference({"image_url": URLS, "image_caption": captions})


class ImageCaptionCommandTest(unittest.TestCase):
    def run_create(self, *argv):
        args = CLI["build_parser"](models_record={}).parse_args(
            ["tunes", "create", "--title", "Shirt", "--name", "shirt", "--model", "123", *argv])
        captured = {}

        def request(_cfg, _method, _path, **kwargs):
            captured.update(kwargs)
            return {"id": 7}

        with patch.dict(CLI["cmd_tunes_create"].__globals__, {
            "direct_uploads": lambda _cfg, paths: [f"signed-{path}" for path in paths],
            "request": request,
        }), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            CLI["cmd_tunes_create"](args, {})
        return captured["form"]

    def test_repeatable_flag_maps_to_image_captions(self):
        form = self.run_create("--image-url", URLS[0], "--image-caption", "front",
                               "--image-url", URLS[1], "--image-caption", "back")
        self.assertEqual([value for key, value in form if key == "tune[image_captions][]"], ["front", "back"])

    def test_captions_follow_local_image_order(self):
        form = self.run_create("--image", "a.jpg", "--image", "b.jpg",
                               "--image-caption", "front", "--image-caption", "logo")
        self.assertEqual([value for key, value in form if key == "tune[images][]"], ["signed-a.jpg", "signed-b.jpg"])
        self.assertEqual([value for key, value in form if key == "tune[image_captions][]"], ["front", "logo"])

    def test_rejects_mismatched_count(self):
        with self.assertRaisesRegex(CLI["AstriaError"], "one image_caption per image: 2 images, 1 given"):
            self.run_create("--image-url", URLS[0], "--image-url", URLS[1], "--image-caption", "front")

    def test_rejects_captions_for_mixed_files_and_urls(self):
        with self.assertRaises(SystemExit):
            self.run_create("--image-url", URLS[0], "--image", "b.jpg",
                            "--image-caption", "front", "--image-caption", "back")


if __name__ == "__main__":
    unittest.main()
