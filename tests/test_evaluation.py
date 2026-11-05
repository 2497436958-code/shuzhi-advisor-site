"""评测层测试（T039—T048）。

要守住的线：
1. 八个组都在，能力开关与"关掉了什么"一致；
2. 六项指标按主控文档的门槛判定，达标与未达标都如实写；
3. 四组消融各自真的把对应能力打掉（不是换个说法）；
4. 报告文件与重新跑出来的一致；
5. 真实层为 0 家，报告里不得出现真实企业的结论。
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from advisor.evaluation.runner import run_evaluation
from advisor.evaluation.variants import ABLATION_SYSTEMS, CONTROL_SYSTEMS, SYSTEMS

REPORT_JSON = ROOT / "data" / "evaluation" / "report.json"
REPORT_MD = ROOT / "data" / "evaluation" / "report.md"
BUILDER = ROOT / "scripts" / "build_evaluation_report.py"


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_evaluation()

    def test_eight_systems(self):
        self.assertEqual(len(SYSTEMS), 8)
        self.assertEqual(len(CONTROL_SYSTEMS), 4)
        self.assertEqual(len(ABLATION_SYSTEMS), 4)
        for system in SYSTEMS:
            self.assertIn(system, self.report["systems"])

    def test_thresholds_match_manual(self):
        thresholds = self.report["thresholds"]
        self.assertEqual(thresholds["T041_diagnosis_f1"]["value"], 0.80)
        self.assertEqual(thresholds["T042_path_hit_rate"]["value"], 0.70)
        self.assertEqual(thresholds["T043_ranking_top3"]["value"], 0.70)
        self.assertEqual(thresholds["T044_antipattern_detection"]["value"], 0.85)
        self.assertEqual(thresholds["T044_antipattern_false_positive"]["value"], 0.15)
        self.assertEqual(thresholds["T045_roi_deviation"]["value"], 0.20)
        self.assertEqual(thresholds["T046_generalization"]["value"], 0.10)

    def test_verdicts_are_consistent_with_values(self):
        for task, verdict in self.report["verdicts"].items():
            rule = self.report["thresholds"][task]
            if verdict["value"] is None:
                self.assertEqual(verdict["status"], "不可测", task)
                continue
            passed = (
                verdict["value"] >= rule["value"]
                if rule["op"] == ">="
                else verdict["value"] <= rule["value"]
            )
            self.assertEqual(verdict["status"], "达标" if passed else "未达标", task)

    def test_ablations_actually_remove_capability(self):
        systems = self.report["systems"]
        full = systems["control_full"]["metrics"]

        no_attribution = systems["ablation_no_attribution"]["metrics"]
        self.assertEqual(no_attribution["T042_path_hit_rate"]["hit_rate"], 0.0)
        self.assertEqual(no_attribution["T043_ranking_top3"]["top3_overlap"], 0.0)
        # 诊断能力没被关掉
        self.assertEqual(
            no_attribution["T041_diagnosis_f1"]["bottleneck_micro_f1"],
            full["T041_diagnosis_f1"]["bottleneck_micro_f1"],
        )

        no_antipattern = systems["ablation_no_antipattern"]["metrics"]
        self.assertEqual(no_antipattern["T044_antipattern"]["detection_rate"], 0.0)
        self.assertEqual(no_antipattern["T041_diagnosis_f1"]["bottleneck_micro_f1"], 0.0)

        no_anchor = systems["ablation_no_anchor"]["metrics"]
        self.assertEqual(no_anchor["evidence_quality"]["evidence_complete_rate"], 0.0)
        self.assertEqual(no_anchor["evidence_quality"]["hit_item_precision"], 0.0)

        no_constraint = systems["ablation_no_constraint"]["metrics"]
        self.assertLess(
            no_constraint["level_agreement"]["agreement"],
            full["level_agreement"]["agreement"],
            "去掉约束性场景要求后，等级判定应当发生变化",
        )

    def test_pure_rag_produces_no_structured_conclusion(self):
        rag = self.report["systems"]["control_rag"]["metrics"]
        self.assertEqual(rag["T041_diagnosis_f1"]["bottleneck_micro_f1"], 0.0)
        self.assertEqual(rag["T042_path_hit_rate"]["hit_rate"], 0.0)
        self.assertEqual(rag["level_agreement"]["agreement"], 0.0)

    def test_roi_implementation_is_consistent(self):
        roi = self.report["systems"]["control_full"]["metrics"]["T045_roi_deviation"]
        self.assertLess(roi["implementation_max_gap"], 0.01)
        self.assertIsNone(roi["true_deviation"])

    def test_layers_are_separated(self):
        layers = self.report["layers"]
        self.assertEqual(layers["synthetic"]["count"], 60)
        self.assertEqual(layers["real"]["count"], 0)
        self.assertIn("真实层", REPORT_MD.read_text(encoding="utf-8"))

    def test_report_files_are_up_to_date(self):
        result = subprocess.run(
            [sys.executable, str(BUILDER)], cwd=ROOT, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        fresh = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
        self.assertEqual(fresh["verdicts"], self.report["verdicts"])
        # 除生成时间外，报告内容必须完全一致
        without_time = lambda payload: {
            key: value for key, value in payload.items() if key != "generated_at"
        }
        self.assertEqual(without_time(fresh), without_time(self.report))


if __name__ == "__main__":
    unittest.main()
