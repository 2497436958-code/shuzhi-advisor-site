"""推理层测试：判据层复算、诊断一致、证据链强制。

验收口径（主控文档）：
- 判据层 100% 可复算；
- 每条结论可溯源（证据链非空）；
- 反模式判定与已发布预计算结果一致。
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from advisor.reasoning.knowledge import load_knowledge
from advisor.reasoning.pipeline import build_result
from advisor.scoring.engine import load_criteria

FIXTURES = [
    "ap0_无等级",
    "ap1_只买设备不联网",
    "ap2_只上系统不跑流程",
    "ap3_只做数据采集不做分析",
    "ap4_只追补贴不建能力",
    "baseline_二级规范级",
]


def load_fixture(name):
    return json.loads(
        (ROOT / "precomputed" / f"{name}.json").read_text(encoding="utf-8")
    )


class ReasoningParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.criteria = load_criteria(ROOT / "precomputed/criteria.json")
        cls.knowledge = load_knowledge()

    def build(self, name):
        fixture = load_fixture(name)
        return fixture, build_result(fixture["profile"], self.criteria, self.knowledge)

    def test_criteria_layer_is_reproducible(self):
        """判据层 100% 可复算：引擎结果与已发布预计算逐字段一致。"""
        for name in FIXTURES:
            with self.subTest(fixture=name):
                fixture, result = self.build(name)
                published = fixture["result"]["evaluation"]
                engine = result["evaluation"]
                for key, value in published.items():
                    self.assertEqual(engine[key], value, f"{name}.{key} 不一致")

    def test_antipattern_matches_published(self):
        for name in FIXTURES:
            with self.subTest(fixture=name):
                fixture, result = self.build(name)
                self.assertEqual(
                    [hit["pattern_id"] for hit in result["do_not"]],
                    [hit["pattern_id"] for hit in fixture["result"]["do_not"]],
                )

    def test_diagnosis_matches_published(self):
        for name in FIXTURES:
            with self.subTest(fixture=name):
                fixture, result = self.build(name)
                published = [
                    (
                        entry["bottleneck_type"],
                        entry["hit_items"],
                        entry["hit_scenarios"],
                        entry["max_score_gain"],
                    )
                    for entry in fixture["result"]["diagnosis"]
                ]
                engine = [
                    (
                        entry["bottleneck_type"],
                        entry["hit_items"],
                        entry["hit_scenarios"],
                        entry["max_score_gain"],
                    )
                    for entry in result["diagnosis"]
                ]
                self.assertEqual(engine, published)

    def test_roi_numbers_match_published(self):
        """共同改造项的 ROI 必须与已发布预计算完全一致。"""
        for name in FIXTURES:
            with self.subTest(fixture=name):
                fixture, result = self.build(name)
                published = {
                    row["name"]: (row["roi_low"], row["roi_high"])
                    for row in fixture["result"]["ranking"]
                }
                for row in result["ranking"]:
                    if row["name"] in published:
                        self.assertEqual(
                            (row["roi_low"], row["roi_high"]), published[row["name"]]
                        )

    def test_every_conclusion_has_evidence(self):
        for name in FIXTURES:
            with self.subTest(fixture=name):
                _, result = self.build(name)
                for section in ("diagnosis", "pathway", "ranking", "do_not"):
                    for entry in result[section]:
                        self.assertTrue(
                            entry.get("evidence_refs"),
                            f"{name}.{section} 存在没有证据链的结论",
                        )
                        for ref in entry["evidence_refs"]:
                            self.assertTrue(ref["quote"] or ref["title"])

    def test_scenario_quotes_come_from_official_text(self):
        _, result = self.build("ap1_只买设备不联网")
        for row in result["scenario_results"]:
            scenario = next(
                s for s in self.criteria["scenarios"] if s["id"] == row["id"]
            )
            self.assertEqual(row["judgment"]["quote"], scenario["levels"][str(row["level"])])


class KnowledgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.knowledge = load_knowledge()

    def test_four_knowledge_sources_loaded(self):
        status = self.knowledge.status()
        self.assertGreaterEqual(status["policy"], 30)
        self.assertGreaterEqual(status["cases"], 86)
        self.assertGreater(status["papers"], 0)
        self.assertGreater(status["patent_categories"], 0)

    def test_synthetic_cases_are_separated(self):
        status = self.knowledge.status()
        self.assertLessEqual(status["cases_synthetic"], status["cases"])

    def test_case_evidence_has_url(self):
        for case in self.knowledge.cases:
            self.assertTrue(case.get("id"))
            self.assertTrue((case.get("evidence") or {}).get("url"), case["id"])


if __name__ == "__main__":
    unittest.main()
