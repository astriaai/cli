import io
import runpy
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


CLI = runpy.run_path(Path(__file__).parents[1] / "astria", run_name="astria_test")
CATALOG = {
    "default": "nano-banana-2",
    "models": {"nano-banana-2": {"tune_id": 111}},
    "default_music_model": "mureka-v9.5",
    "music_models": {
        "mureka-v9.5": {"tune_id": 5922969, "default": True, "lyrics_length": {"min": 10, "max": 3000}},
        "minimax-music-3.0": {"tune_id": 5922836, "default": False, "lyrics_length": {"min": 1, "max": 3500}},
    },
}


class MusicCommandTest(unittest.TestCase):
    def submit(self, *argv):
        calls = []

        def request(_cfg, method, path, form=None, workspace=None, **_kwargs):
            calls.append((method, path, form))
            return {"id": 9, "tune_id": 5922969}

        args = CLI["build_parser"]({}).parse_args(["music", *argv])
        with patch.dict(CLI["execute_api_operation"].__globals__, {"request": request, "model_catalog": lambda _cfg: CATALOG}):
            with redirect_stdout(io.StringIO()):
                args.func(args, {})
        method, path, form = calls[0]
        self.assertEqual(method, "POST")
        return path, dict(form)

    def test_song_with_lyrics_uses_the_default_music_model(self):
        path, form = self.submit("upbeat synth-pop", "--lyrics", "[Verse]\nCity lights")
        self.assertEqual(path, "/tunes/5922969/prompts")
        self.assertEqual(form, {"prompt[text]": "upbeat synth-pop", "prompt[lyrics]": "[Verse]\nCity lights",
                                "prompt[num_images]": "1"})

    def test_model_name_resolves_against_music_models(self):
        path, _form = self.submit("folk", "--model", "minimax-music-3.0")
        self.assertEqual(path, "/tunes/5922836/prompts")

    def test_default_image_model_config_does_not_leak_into_songs(self):
        calls = []

        def request(_cfg, _method, path, **_kwargs):
            calls.append(path)
            return {"id": 9, "tune_id": 5922969}

        args = CLI["build_parser"]({}).parse_args(["music", "folk"])
        with patch.dict(CLI["execute_api_operation"].__globals__, {"request": request, "model_catalog": lambda _cfg: CATALOG}):
            with redirect_stdout(io.StringIO()):
                args.func(args, {"default_model": "nano-banana-2"})
        self.assertEqual(calls, ["/tunes/5922969/prompts"])

    def test_instrumental_is_sent_only_when_requested(self):
        self.assertEqual(self.submit("lo-fi beat", "--instrumental")[1]["prompt[instrumental]"], "true")
        self.assertNotIn("prompt[instrumental]", self.submit("lo-fi beat")[1])


class MusicOperationTest(unittest.TestCase):
    def test_mcp_tool_exposes_lyrics_and_instrumental(self):
        tool = next(tool for tool in CLI["operation_catalog"]() if tool["name"] == "generate_music")
        properties = tool["inputSchema"]["properties"]
        self.assertEqual(properties["lyrics"]["type"], "string")
        self.assertEqual(properties["instrumental"]["type"], "boolean")
        self.assertNotIn("wait", properties)
        self.assertEqual(tool["inputSchema"]["required"], ["text", "idempotency_key"])
        self.assertFalse(tool["annotations"]["readOnlyHint"])

    def test_run_operation_resolves_the_default_music_model(self):
        calls = []

        def transport(method, path, **kwargs):
            calls.append((method, path, kwargs))
            return CATALOG if path == "/cli/models" else [{"id": 9, "tune_id": 5922969}]

        result = CLI["run_operation"]("generate_music", {"text": "jingle", "instrumental": True,
                                                         "idempotency_key": "k1"}, transport)
        self.assertEqual(result, {"id": 9, "tune_id": 5922969})
        method, path, kwargs = calls[-1]
        self.assertEqual((method, path), ("POST", "/tunes/5922969/prompts"))
        self.assertEqual(dict(kwargs["form"]), {"prompt[text]": "jingle", "prompt[instrumental]": "true",
                                                "prompt[num_images]": "1"})

    def test_list_models_keeps_music_models(self):
        result = CLI["operation_result"](CLI["API_OPERATIONS"]["list_models"], CATALOG, {})
        self.assertEqual(result["default_music_model"], "mureka-v9.5")
        self.assertEqual(result["music_models"], CATALOG["music_models"])

    def test_cache_without_music_models_is_refetched(self):
        record = {"models": {"x": {}}, "base_url": CLI["base_url"]({}), "fetched_at": int(time.time())}
        self.assertTrue(CLI["models_cache_stale"](record, {}))
        self.assertFalse(CLI["models_cache_stale"](record | {"music_models": {}}, {}))


if __name__ == "__main__":
    unittest.main()
