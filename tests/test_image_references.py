import io
import runpy
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


CLI = runpy.run_path(Path(__file__).parents[1] / "astria", run_name="astria_test")


class ImageReferencesTest(unittest.TestCase):
    def args(self, image_references):
        return SimpleNamespace(
            model="123",
            references=[],
            text=None,
            num_images="1",
            seed=None,
            aspect_ratio="16:9",
            resolution=None,
            input_image=None,
            mask_image=None,
            pack_id=None,
            base_pack_id=None,
            video_model="seedance2_fast_720p",
            video_prompt="transition through these looks in order",
            duration="5",
            image_references=image_references,
            first_frame=None,
            last_frame=None,
            input_video=None,
            audio_reference=None,
            generate_audio=None,
            workspace=None,
            wait=False,
        )

    def submitted_form(self, args):
        captured = {}

        def request(_cfg, _method, _path, form, workspace):
            captured["form"] = form
            return {"id": 9}

        with patch.dict(CLI["_generate"].__globals__, {"request": request}):
            with redirect_stdout(io.StringIO()):
                CLI["_generate"](args, {}, video=True)
        return captured["form"]

    def test_preserves_url_reference_order(self):
        form = self.submitted_form(self.args([
            "https://example.com/look-1.jpg",
            "https://example.com/look-2.jpg",
        ]))

        references = [value for key, value in form if key == "prompt[image_reference_urls][]"]

        self.assertEqual(references, [
            "https://example.com/look-1.jpg",
            "https://example.com/look-2.jpg",
        ])

    def test_preserves_local_file_reference_order(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "look-1.jpg"
            second = Path(directory) / "look-2.jpg"
            first.touch()
            second.touch()

            form = self.submitted_form(self.args([str(first), str(second)]))

        references = [value for key, value in form if key == "prompt[image_references][]"]

        self.assertEqual(references, [f"@{first}", f"@{second}"])

    def test_rejects_mixed_url_and_local_file_references(self):
        with tempfile.TemporaryDirectory() as directory:
            local_file = Path(directory) / "look.jpg"
            local_file.touch()

            with self.assertRaises(SystemExit):
                self.submitted_form(self.args([
                    str(local_file),
                    "https://example.com/look-2.jpg",
                ]))


if __name__ == "__main__":
    unittest.main()
