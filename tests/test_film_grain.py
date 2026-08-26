import io
import runpy
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


CLI = runpy.run_path(Path(__file__).parents[1] / "astria", run_name="astria_test")


class FilmGrainTest(unittest.TestCase):
    def args(self, film_grain):
        return SimpleNamespace(
            model="123",
            references=[],
            text="cinematic portrait",
            num_images="1",
            seed=None,
            film_grain=film_grain,
            aspect_ratio="3:4",
            resolution=None,
            input_image=None,
            mask_image=None,
            pack_id=None,
            base_pack_id=None,
            workspace=None,
            wait=False,
        )

    def submitted_form(self, film_grain):
        captured = {}

        def request(_cfg, _method, _path, form, workspace):
            captured["form"] = form
            return {"id": 9}

        with patch.dict(CLI["_generate"].__globals__, {"request": request}):
            with redirect_stdout(io.StringIO()):
                CLI["_generate"](self.args(film_grain), {}, video=False)
        return dict(captured["form"])

    def test_parser_accepts_canonical_and_prompt_style_spellings(self):
        parser = CLI["build_parser"]()

        canonical = parser.parse_args([
            "generate", "--text", "portrait", "--film-grain",
        ])
        prompt_style = parser.parse_args([
            "generate", "--text", "portrait", "--film_grain",
        ])

        self.assertTrue(canonical.film_grain)
        self.assertTrue(prompt_style.film_grain)

    def test_parser_accepts_explicit_disable(self):
        args = CLI["build_parser"]().parse_args([
            "generate", "--text", "portrait", "--no-film-grain",
        ])

        self.assertFalse(args.film_grain)

    def test_submits_enabled_film_grain_separately_from_text(self):
        form = self.submitted_form(True)

        self.assertEqual(form["prompt[text]"], "cinematic portrait")
        self.assertEqual(form["prompt[film_grain]"], "true")

    def test_submits_disabled_film_grain_separately_from_text(self):
        form = self.submitted_form(False)

        self.assertEqual(form["prompt[text]"], "cinematic portrait")
        self.assertEqual(form["prompt[film_grain]"], "false")

    def test_omits_film_grain_when_unspecified(self):
        form = self.submitted_form(None)

        self.assertNotIn("prompt[film_grain]", form)


if __name__ == "__main__":
    unittest.main()
