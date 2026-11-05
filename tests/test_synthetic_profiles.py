"""合成样本集测试（T037）。

要守住的四条线：
1. 数量与构成：AP1—AP4 各 10 家、正常对照 20 家，共 60 家；
2. 合成层与真实层不混写：全部标 synthetic，真实企业 0 家；
3. 构造意图与引擎实测一致：每家只命中该命中的反模式，等级落在预期区间；
4. 可复算：同一份画像重算，结果一致；仓库里的样本文件与重新生成一致。
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from advisor.reasoning.antipatterns import detect_antipatterns
from advisor.scoring.engine import evaluate_profile, load_criteria

DATASET = ROOT / "data" / "profiles" / "synthetic_60.json"
GENERATOR = ROOT / "scripts" / "generate_synthetic_profiles.py"


class SyntheticProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = json.loads(DATASET.read_text(encoding="utf-8"))
        cls.criteria = load_criteria(ROOT / "precomputed" / "criteria.json")
        cls.samples = cls.dataset["samples"]

    def test_composition(self):
        self.assertEqual(len(self.samples), 60)
        counts = {}
        for sample in self.samples:
            counts[sample["archetype"]] = counts.get(sample["archetype"], 0) + 1
        self.assertEqual(
            counts,
            {"AP1": 10, "AP2": 10, "AP3": 10, "AP4": 10, "control": 20},
        )

    def test_all_samples_are_synthetic(self):
        self.assertTrue(self.dataset["synthetic"])
        for sample in self.samples:
            self.assertTrue(sample["synthetic"], sample["id"])
            self.assertIn("合成样本", sample["profile"]["provenance"], sample["id"])

    def test_no_real_enterprise_in_dataset(self):
        """真实层与合成层不混写：本数据集里不允许出现真实企业。"""
        for sample in self.samples:
            self.assertIn("synthetic", sample["profile"]["provenance"])
            self.assertNotIn("真实", sample["profile"]["provenance"].replace("非真实企业数据", ""))

    def test_answers_are_complete_and_valid(self):
        indicators = {item["id"]: item for item in self.criteria["indicators"]}
        for sample in self.samples:
            answers = sample["profile"]["answers"]
            self.assertEqual(len(answers), 15, sample["id"])
            for item_id, indicator in indicators.items():
                selected = answers[str(item_id)]
                self.assertTrue(selected, f"{sample['id']} 采集项 {item_id} 未作答")
                for option in selected:
                    self.assertIn(option, indicator["options"], f"{sample['id']} 采集项 {item_id}")
            self.assertEqual(len(sample["profile"]["scenario_levels"]), 16, sample["id"])

    def test_engine_matches_construction(self):
        """每家样本只命中该命中的反模式，且等级落在预期区间。"""
        expected_levels = self.dataset["expected_levels"]
        for sample in self.samples:
            evaluation = evaluate_profile(sample["profile"], self.criteria)
            hits = [hit.pattern_id for hit in detect_antipatterns(evaluation, self.criteria)]
            self.assertEqual(
                hits,
                sample["expected"]["antipatterns"],
                f"{sample['id']} 反模式命中与构造意图不一致",
            )
            self.assertIn(
                evaluation["level"],
                expected_levels[sample["archetype"]],
                f"{sample['id']} 等级 {evaluation['level_name']} 不在预期区间",
            )

    def test_evaluation_is_reproducible(self):
        for sample in self.samples[:10]:
            first = evaluate_profile(sample["profile"], self.criteria)
            second = evaluate_profile(sample["profile"], self.criteria)
            self.assertEqual(first["total_score"], second["total_score"], sample["id"])
            self.assertEqual(
                first["total_score"], sample["actual"]["total_score"], sample["id"]
            )

    def test_expected_actions_cover_level_one_scenarios(self):
        """ground truth 里的改造项，必须来自仍在一级的场景。"""
        action_table = json.loads(
            (ROOT / "data" / "pathways.json").read_text(encoding="utf-8")
        )["actions"]
        by_scenario = {}
        for action_id, action in action_table.items():
            for scenario_id in action.get("target_scenarios") or []:
                by_scenario.setdefault(scenario_id, []).append(action_id)
        for sample in self.samples:
            levels = sample["profile"]["scenario_levels"]
            for action_id in sample["expected"]["action_ids"]:
                scenarios = action_table[action_id].get("target_scenarios") or []
                self.assertTrue(
                    any(levels.get(sid, 9) <= 1 for sid in scenarios),
                    f"{sample['id']} 的期望改造项 {action_id} 没有对应的一级场景",
                )

    def test_generator_is_idempotent(self):
        result = subprocess.run(
            [sys.executable, str(GENERATOR), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
