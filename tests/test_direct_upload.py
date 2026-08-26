import io
import runpy
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


CLI = runpy.run_path(Path(__file__).parents[1] / "astria", run_name="astria_test")


class DirectUploadTest(unittest.TestCase):
    def test_tune_create_direct_uploads_local_images_as_signed_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "look.jpg"
            image.write_bytes(b"image")
            captured = []

            def request(_cfg, method, path, **kwargs):
                captured.append((method, path, kwargs))
                return {"id": 7}

            args = SimpleNamespace(
                title="Look", name="dress", model_type="faceid", model="123",
                description=None, image_url=None, image=[str(image)], workspace=None,
            )
            with patch.dict(CLI["cmd_tunes_create"].__globals__, {
                "direct_upload": lambda _cfg, _path: "signed-blob",
                "request": request,
            }):
                with redirect_stdout(io.StringIO()):
                    CLI["cmd_tunes_create"](args, {})

        form = captured[0][2]["form"]
        self.assertIn(("tune[images][]", "signed-blob"), form)
        self.assertNotIn(f"@{image}", [value for _, value in form])

    def test_inspect_video_direct_uploads_a_local_file(self):
        args = SimpleNamespace(source="clip.mp4", tune_id=["12", "13"], workspace="9")
        captured = {}

        def request(_cfg, method, path, **kwargs):
            captured.update(method=method, path=path, **kwargs)
            return {"description": "00-05 - shot"}

        with patch.dict(CLI["cmd_inspect_video"].__globals__, {
            "direct_upload": lambda _cfg, _path: "signed-video",
            "request": request,
        }):
            output = io.StringIO()
            with redirect_stdout(output):
                CLI["cmd_inspect_video"](args, {})

        self.assertEqual(captured["path"], "/videos/inspect")
        self.assertEqual(captured["json_body"], {
            "blob_signed_id": "signed-video",
            "tune_ids": [12, 13],
        })
        self.assertEqual(captured["timeout"], 125)
        self.assertEqual(__import__("json").loads(output.getvalue())["description"], "00-05 - shot")

    def test_inspect_video_passes_an_https_url_without_uploading(self):
        args = SimpleNamespace(source="https://example.com/clip.mp4", tune_id=None, workspace=None)
        request = Mock(return_value={"description": "00-05 - shot"})
        upload = Mock()

        with patch.dict(CLI["cmd_inspect_video"].__globals__, {
            "direct_upload": upload,
            "request": request,
        }):
            with redirect_stdout(io.StringIO()):
                CLI["cmd_inspect_video"](args, {})

        upload.assert_not_called()
        self.assertEqual(request.call_args.kwargs["json_body"], {
            "file_url": "https://example.com/clip.mp4",
        })

    def test_parser_exposes_inspect_video_without_a_custom_prompt(self):
        args = CLI["build_parser"]().parse_args([
            "inspect-video", "clip.mp4", "--tune-id", "12",
        ])

        self.assertEqual(args.source, "clip.mp4")
        self.assertEqual(args.tune_id, ["12"])
        self.assertFalse(hasattr(args, "prompt"))


if __name__ == "__main__":
    unittest.main()
