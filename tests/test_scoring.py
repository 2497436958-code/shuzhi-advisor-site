import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from advisor.scoring.engine import evaluate_profile, item_score, load_criteria

ROOT = Path(__file__).resolve().parents[1]


class ScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.criteria = load_criteria(ROOT / "precomputed/criteria.json")

    def test_criteria_structure(self):
        self.assertEqual(len(self.criteria["indicators"]), 15)
        self.assertEqual(len(self.criteria["scenarios"]), 16)
        self.assertEqual(len(self.criteria["levels"]), 4)
        self.assertAlmostEqual(
            sum(item["chain_weight"] for item in self.criteria["indicators"]), 1.0
        )

    def test_three_option_single(self):
        indicator = next(item for item in self.criteria["indicators"] if item["id"] == 12)
        self.assertEqual(item_score(indicator, ["增加"]), 0.0)
        self.assertEqual(item_score(indicator, ["持平"]), 50.0)
        self.assertEqual(item_score(indicator, ["降低"]), 100.0)

    def test_five_option_single(self):
        indicator = next(item for item in self.criteria["indicators"] if item["id"] == 2)
        self.assertEqual(item_score(indicator, ["[0-10%]"]), 0.0)
        self.assertEqual(item_score(indicator, ["(10%,20%]"]), 25.0)
        self.assertEqual(item_score(indicator, ["(20%,40%]"]), 50.0)
        self.assertEqual(item_score(indicator, ["(40%,60%]"]), 75.0)
        self.assertEqual(item_score(indicator, ["(60%,100%]"]), 100.0)

    def test_multi_none_zero(self):
        indicator = next(item for item in self.criteria["indicators"] if item["id"] == 1)
        self.assertEqual(item_score(indicator, ["无"]), 0.0)

    def test_multi_partial(self):
        indicator = next(item for item in self.criteria["indicators"] if item["id"] == 1)
        self.assertEqual(
            item_score(indicator, [indicator["options"][1], indicator["options"][2]]),
            50.0,
        )

    def test_multi_none_cannot_combine(self):
        indicator = next(item for item in self.criteria["indicators"] if item["id"] == 1)
        with self.assertRaises(ValueError):
            item_score(indicator, ["无", indicator["options"][1]])

    def test_official_six_option_gap_disclosed(self):
        indicator = next(item for item in self.criteria["indicators"] if item["id"] == 8)
        self.assertTrue(indicator["official_rule_gap"])
        payload = json.loads(
            (ROOT / "precomputed/ap0_无等级.json").read_text(encoding="utf-8")
        )
        profile = payload["profile"]
        profile["answers"]["8"] = [indicator["options"][3]]
        result = evaluate_profile(profile, self.criteria)
        self.assertIn("采集项 8", result["rule_gaps"][0])
        self.assertIn("按等距线性兜底计分", result["rule_gaps"][0])

    def test_all_precomputed_fixtures(self):
        fixtures = json.loads((ROOT / "precomputed/fixtures.json").read_text(encoding="utf-8"))
        for fixture in fixtures["fixtures"]:
            with self.subTest(fixture=fixture["name"]):
                payload = json.loads(
                    (ROOT / "precomputed" / fixture["name"]).read_text(encoding="utf-8")
                )
                expected = payload["result"]["evaluation"]
                actual = evaluate_profile(payload["profile"], self.criteria)
                self.assertEqual(actual["total_score"], expected["total_score"])
                self.assertEqual(actual["level"], expected["level"])
                self.assertEqual(actual["level_name"], expected["level_name"])
                self.assertEqual(actual["dimension_scores"], expected["dimension_scores"])
                self.assertEqual(actual["unmet"], expected["unmet"])
                self.assertEqual(actual["rule_gaps"], expected["rule_gaps"])
                self.assertEqual(
                    actual["scenario_count_by_level"], expected["scenario_count_by_level"]
                )
                self.assertEqual(
                    actual["constraint_count_by_level"],
                    expected["constraint_count_by_level"],
                )


if __name__ == "__main__":
    unittest.main()
