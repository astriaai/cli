import io
import json
import runpy
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


CLI = runpy.run_path(Path(__file__).parents[1] / "astria", run_name="astria_test")


class VariateTest(unittest.TestCase):
    def args(self, **overrides):
        values = {
            "source": "source.mp4",
            "brief": "Replace the wardrobe",
            "tune_ids": ["88"],
            "references": ["dress.jpg", "woman=model.jpg"],
            "description": None,
            "description_file": None,
            "base_pack_id": 12,
            "order_id": 34,
            "workspace": "7",
            "wait": False,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_local_flow_batches_uploads_and_matches_mini_app_payload(self):
        upload = Mock(return_value=[
            {"signed_id": "signed-video", "public_url": "https://cdn.test/source.mp4"},
            {"signed_id": "signed-dress", "public_url": "https://cdn.test/dress.jpg"},
            {"signed_id": "signed-woman", "public_url": "https://cdn.test/model.jpg"},
        ])
        calls = []

        def request(_cfg, method, path, **kwargs):
            calls.append((method, path, kwargs))
            if path == "/videos/inspect":
                return {"description": "00-05 - A presenter walks toward camera."}
            if path == "/images/class_name":
                return {
                    "class_name": "dress",
                    "short_description": "red satin dress",
                    "caption": "front",
                    "first_name": "",
                }
            if path == "/tunes":
                form = dict(kwargs["form"])
                name = form["tune[name]"]
                return {"id": 201 if name == "dress" else 202, "name": name, "title": form["tune[title]"]}
            if path == "/assist/complete":
                return {"text": json.dumps({"video_prompt": "Keep <faceid:88:1> in the same performance."})}
            if path == "/prompts":
                return {"prompt": {"id": 901, "images": []}}
            raise AssertionError(path)

        with patch.dict(CLI["cmd_variate"].__globals__, {
            "direct_upload_records": upload,
            "model_catalog": lambda _cfg: {"video_models": {"seedance25_720p": {}}},
            "resolve_model": lambda _cfg, _name: "999",
            "request": request,
        }):
            output = io.StringIO()
            with redirect_stdout(output):
                CLI["cmd_variate"](self.args(), {})

        upload.assert_called_once_with({}, ["source.mp4", "dress.jpg", "model.jpg"])
        detected = next(call for call in calls if call[1] == "/images/class_name")
        self.assertEqual(detected[2]["form"], [("file_url", "https://cdn.test/dress.jpg")])

        tune_calls = [call for call in calls if call[1] == "/tunes"]
        self.assertEqual(len(tune_calls), 2)
        auto_form = tune_calls[0][2]["form"]
        named_form = tune_calls[1][2]["form"]
        self.assertIn(("tune[name]", "dress"), auto_form)
        self.assertIn(("tune[images][]", "signed-dress"), auto_form)
        self.assertIn(("tune[image_captions][]", "front"), auto_form)
        self.assertIn(("tune[name]", "woman"), named_form)
        self.assertIn(("tune[images][]", "signed-woman"), named_form)

        assist = next(call for call in calls if call[1] == "/assist/complete")
        assist_body = assist[2]["json_body"]
        self.assertEqual(assist_body["messages"][0]["content"], CLI["VARIATE_SYSTEM_MESSAGE"])
        self.assertIn("00-05 - A presenter walks toward camera.", assist_body["messages"][1]["content"])
        self.assertIn("<faceid:88:1>\n<faceid:201:1>\n<faceid:202:1>", assist_body["messages"][1]["content"])
        self.assertEqual(assist_body["response_schema"], CLI["VARIATE_PROMPT_SCHEMA"])

        create = next(call for call in calls if call[1] == "/prompts")
        self.assertEqual(create[2]["query"], [("view", "board")])
        prompt = create[2]["json_body"]["prompt"]
        self.assertEqual(prompt, {
            "text": "",
            "tune_id": 999,
            "video_model": "seedance25_720p",
            "video_prompt": (
                "Replace objects in the scene with <faceid:201:1> <faceid:202:1>. "
                "Keep <faceid:88:1> in the same performance."
            ),
            "video_audio": True,
            "input_video": "signed-video",
            "base_pack_id": 12,
            "order_id": 34,
        })
        self.assertNotIn("video_duration", prompt)
        self.assertNotIn("aspect_ratio", prompt)

        result = json.loads(output.getvalue())
        self.assertEqual([reference["id"] for reference in result["references"]], [88, 201, 202])
        self.assertEqual(result["prompt"]["id"], 901)

    def test_remote_source_and_description_skip_upload_and_inspection(self):
        upload = Mock(return_value=[])
        calls = []

        def request(_cfg, method, path, **kwargs):
            calls.append((method, path, kwargs))
            if path == "/assist/complete":
                return {"text": '{"video_prompt":"Use <faceid:55:1> for the replacement."}'}
            if path == "/prompts":
                return {"prompt": {"id": 902}}
            raise AssertionError(path)

        args = self.args(
            source="https://example.com/source.mp4?token=a=b",
            brief="",
            tune_ids=["55", "55"],
            references=[],
            description=" 00-03 - A product rotates. ",
            base_pack_id=None,
            order_id=None,
        )
        with patch.dict(CLI["cmd_variate"].__globals__, {
            "direct_upload_records": upload,
            "model_catalog": lambda _cfg: {"video_models": {"seedance25_720p": {}}},
            "resolve_model": lambda _cfg, _name: "999",
            "request": request,
        }):
            with redirect_stdout(io.StringIO()):
                CLI["cmd_variate"](args, {})

        upload.assert_called_once_with({}, [])
        self.assertNotIn("/videos/inspect", [call[1] for call in calls])
        prompt = next(call for call in calls if call[1] == "/prompts")[2]["json_body"]["prompt"]
        self.assertEqual(prompt["input_video_url"], "https://example.com/source.mp4?token=a=b")
        self.assertNotIn("input_video", prompt)

    def test_wait_returns_the_settled_prompt_inside_structured_output(self):
        poll = Mock(return_value={"id": 903, "images": [{"url": "https://cdn.test/video.mp4"}]})
        args = self.args(
            source="https://example.com/source.mp4",
            references=[],
            description="00-03 - A product rotates.",
            base_pack_id=None,
            order_id=None,
            wait=True,
        )

        def request(_cfg, _method, path, **_kwargs):
            if path == "/assist/complete":
                return {"text": '{"video_prompt":"Use <faceid:88:1> for the replacement."}'}
            if path == "/prompts":
                return {"prompt": {"id": 903}}
            raise AssertionError(path)

        with patch.dict(CLI["cmd_variate"].__globals__, {
            "direct_upload_records": lambda _cfg, _values: [],
            "model_catalog": lambda _cfg: {"video_models": {"seedance25_720p": {}}},
            "resolve_model": lambda _cfg, _name: "999",
            "request": request,
            "poll_prompt": poll,
        }):
            output = io.StringIO()
            with redirect_stdout(output):
                CLI["cmd_variate"](args, {})

        poll.assert_called_once_with({}, "999", 903, workspace="7")
        self.assertEqual(json.loads(output.getvalue())["prompt"]["images"][0]["url"], "https://cdn.test/video.mp4")

    def test_bare_url_with_query_equals_is_not_parsed_as_a_named_reference(self):
        specs = CLI["parse_variate_reference_specs"]([
            "https://example.com/look.jpg?signature=a=b",
            "dress=https://example.com/dress.jpg",
        ])

        self.assertEqual(specs, [
            {"name": None, "source": "https://example.com/look.jpg?signature=a=b"},
            {"name": "dress", "source": "https://example.com/dress.jpg"},
        ])


if __name__ == "__main__":
    unittest.main()
