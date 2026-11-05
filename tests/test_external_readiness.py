"""外部依赖项的"只差一个动作"物料测试。

T035（专利人工检索）、T052（后端部署）、T038（真实企业）都需要外部输入，
本轮把每项的物料备齐并用测试守住，避免材料被删或走形。
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PatentSearchWorklistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = json.loads((ROOT / "data" / "patent_search_tasks.json").read_text(encoding="utf-8"))

    def test_worklist_covers_every_category(self):
        categories = json.loads(
            (ROOT / "data" / "knowledge" / "patents.json").read_text(encoding="utf-8")
        )["categories"]
        self.assertEqual(len(self.tasks["tasks"]), len(categories))
        self.assertEqual(
            {task["id"] for task in self.tasks["tasks"]},
            {category["id"] for category in categories},
        )

    def test_each_task_has_runnable_queries_and_fields(self):
        for task in self.tasks["tasks"]:
            self.assertTrue(task["queries_to_run"], task["id"])
            self.assertTrue(task["search_entry"], task["id"])
            self.assertIn("applications_cn", task["fields_to_fill"], task["id"])
            self.assertIn("grants_cn", task["fields_to_fill"], task["id"])
            self.assertTrue(task["evidence_to_capture"], task["id"])
            self.assertTrue(task["counting_rule"], task["id"])

    def test_checker_reports_pending_without_failing(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_patent_search.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("待人工检索", result.stdout)


class DeploymentArtifactTests(unittest.TestCase):
    def test_render_blueprint(self):
        text = (ROOT / "render.yaml").read_text(encoding="utf-8")
        self.assertIn("healthCheckPath: /api/health", text)
        self.assertIn("ADVISOR_CORS_ORIGINS", text)
        self.assertIn("advisor.web.api:app", text)

    def test_dockerfile(self):
        text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("advisor.web.api:app", text)
        self.assertIn("requirements-dev.txt", text)
        self.assertIn("ADVISOR_HOST=0.0.0.0", text)

    def test_start_command_matches_app(self):
        import re

        text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        command = re.search(r"CMD \[(.*)\]", text).group(1)
        self.assertIn("--app-dir", command)
        self.assertIn("src", command)


class RealEnterpriseIntakeTests(unittest.TestCase):
    def test_template_is_marked_real_layer(self):
        template = json.loads((ROOT / "data" / "profiles" / "real_template.json").read_text(encoding="utf-8"))
        self.assertFalse(template["synthetic"])
        self.assertIn("published_conclusion", template)
        self.assertIn("profile", template)

    def test_template_is_empty_but_valid(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_real_recompute.py"),
             str(ROOT / "data" / "profiles" / "real_template.json")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("还没填完", result.stdout)

    def test_intake_doc_warns_about_public_repo(self):
        doc = (ROOT / "docs" / "real_enterprise_intake.md").read_text(encoding="utf-8")
        self.assertIn("不要提交进本仓库", doc)
        self.assertIn("公开评测结论", doc)
        self.assertIn("verify_real_recompute.py", doc)


class RankingDecisionTests(unittest.TestCase):
    def test_decision_memo_lists_candidates_and_numbers(self):
        memo = (ROOT / "docs" / "decisions" / "T043_ranking.md").read_text(encoding="utf-8")
        for candidate in ("ROI 下界", "优先级 P", "先覆盖已诊断瓶颈", "先解锁一级约束性场景"):
            self.assertIn(candidate, memo, candidate)
        self.assertIn("循环论证", memo)
        self.assertIn("需要人工裁决", memo)

    def test_policy_comparison_runs(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "compare_ranking_policies.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("T043 Top-3", result.stdout)


if __name__ == "__main__":
    unittest.main()
