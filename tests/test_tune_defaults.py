import io
import runpy
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


CLI = runpy.run_path(Path(__file__).parents[1] / "astria", run_name="astria_test")


class TuneDefaultsTest(unittest.TestCase):
    def test_create_uses_live_catalog_default_model(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "object.jpg"
            image.write_bytes(b"image")
            args = CLI["build_parser"]().parse_args([
                "tunes",
                "create",
                "--title",
                "Object",
                "--name",
                "object",
                "--image",
                str(image),
            ])
            captured = {}

            def request(_cfg, _method, _path, **kwargs):
                captured.update(kwargs)
                return {"id": 7}

            with patch.dict(CLI["cmd_tunes_create"].__globals__, {
                "direct_uploads": lambda _cfg, _paths: ["signed-blob"],
                "model_catalog": lambda _cfg: {
                    "default": "nano-banana-2",
                    "models": {"nano-banana-2": {"tune_id": 4180298}},
                },
                "request": request,
            }):
                with redirect_stdout(io.StringIO()):
                    CLI["cmd_tunes_create"](args, {})

        self.assertIsNone(args.model)
        self.assertIn(("tune[model_type]", "faceid"), captured["form"])
        self.assertIn(("tune[base_tune_id]", "4180298"), captured["form"])


if __name__ == "__main__":
    unittest.main()
