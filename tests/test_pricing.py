import io
import runpy
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


CLI = runpy.run_path(Path(__file__).parents[1] / "astria", run_name="astria_test")


class PricingOutputTest(unittest.TestCase):
    def capture(self, function_name, args, response):
        with patch.dict(CLI[function_name].__globals__, {"request": lambda *a, **kw: response}):
            output = io.StringIO()
            with redirect_stdout(output):
                CLI[function_name](args, {})
        return output.getvalue()

    def test_prompt_list_keeps_cost_millicents(self):
        args = SimpleNamespace(
            text=None,
            pack_id="88",
            base_pack_id=None,
            tune_id=None,
            user_id=None,
            orig_prompt_id=None,
            order_id=None,
            expand=[],
            liked=False,
            today=False,
            is_video=False,
            is_api=False,
            limit=None,
            offset=None,
            workspace=None,
        )

        output = self.capture("cmd_prompts_list", args, [{"id": 7, "num_images": 4, "cost_mc": 12_500}])

        self.assertIn('"cost_mc": 12500', output)

    def test_pack_get_keeps_aggregate_and_per_prompt_prices(self):
        args = SimpleNamespace(slug="spring-lookbook", workspace=None)
        response = {
            "template_prompts": [
                {"id": 7, "cost_mc": 12_500},
                {"id": 8, "cost_mc": 25_000},
            ],
            "costs": {"woman": {"cost_mc": 537_500, "num_images": 12}},
        }

        output = self.capture("cmd_packs_get", args, response)

        self.assertIn('"cost_mc": 12500', output)
        self.assertIn('"cost_mc": 25000', output)
        self.assertIn('"cost_mc": 537500', output)

    def test_pack_list_keeps_cost_pricing(self):
        args = SimpleNamespace(limit=None, offset=None, workspace=None)
        response = [{
            "id": 88,
            "title": "Spring Lookbook",
            "slug": "spring-lookbook",
            "costs": {"woman": {"cost_mc": 537_500, "num_images": 12}},
        }]

        output = self.capture("cmd_packs_list", args, response)

        self.assertIn('"cost_mc": 537500', output)


if __name__ == "__main__":
    unittest.main()
