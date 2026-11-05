import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient

from advisor.web.api import app


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["mode"], "online")
        self.assertEqual(data["indicators"], 15)
        self.assertEqual(data["scenarios"], 16)

    def test_criteria(self):
        response = self.client.get("/api/criteria")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["indicators"]), 15)
        self.assertEqual(len(data["scenarios"]), 16)

    def test_fixtures(self):
        response = self.client.get("/api/fixtures")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 6)

    def test_fixture(self):
        response = self.client.get("/api/fixtures/ap1_只买设备不联网.json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("profile", data)
        self.assertIn("result", data)

    def test_fixture_not_found(self):
        response = self.client.get("/api/fixtures/not_exists.json")
        self.assertEqual(response.status_code, 404)

    def test_scenario_evidence(self):
        response = self.client.get("/api/scenario_evidence")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["available"])

    def test_evaluate_precomputed_profile(self):
        payload = json.loads(
            (ROOT / "precomputed/ap1_只买设备不联网.json").read_text(encoding="utf-8")
        )
        response = self.client.post("/api/evaluate", json=payload["profile"])
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["evaluation"]["total_score"], 51.95)
        self.assertEqual(data["evaluation"]["level_name"], "规范级")
        self.assertEqual(data["meta"]["mode"], "realtime")
        # 推理层已上线：四段式都要有内容
        self.assertTrue(data["diagnosis"])
        self.assertTrue(data["pathway"])
        self.assertTrue(data["ranking"])
        self.assertTrue(data["do_not"])
        self.assertTrue(data["policy_notes"])
        self.assertEqual(data["do_not"][0]["pattern_id"], "AP1")

    def test_evaluate_response_matches_frontend_contract(self):
        """前端渲染器（app.js）读到的每个字段都必须存在。"""
        payload = json.loads(
            (ROOT / "precomputed/ap1_只买设备不联网.json").read_text(encoding="utf-8")
        )
        data = self.client.post("/api/evaluate", json=payload["profile"]).json()

        for key in (
            "profile",
            "evaluation",
            "level_judgement",
            "item_results",
            "scenario_results",
            "diagnosis",
            "pathway",
            "ranking",
            "do_not",
            "scenario_evidence",
            "policy_notes",
            "policy_notes_status",
            "roi_assumptions",
            "meta",
        ):
            self.assertIn(key, data)

        for key in ("total_score", "level_name", "rule_gaps", "scenario_levels_source"):
            self.assertIn(key, data["evaluation"])

        for row in data["level_judgement"]:
            for key in ("level", "name", "satisfied", "note"):
                self.assertIn(key, row)

        for entry in data["diagnosis"]:
            for key in (
                "bottleneck",
                "bottleneck_type",
                "evidence",
                "hit_items",
                "hit_scenarios",
                "max_score_gain",
                "basis_kind",
                "evidence_refs",
            ):
                self.assertIn(key, entry)

        for step in data["pathway"]:
            for key in (
                "step",
                "action",
                "target_scenario",
                "target_items",
                "cost_range",
                "depends_on",
                "expected",
                "acceptance",
                "evidence_refs",
            ):
                self.assertIn(key, step)
            self.assertEqual(len(step["cost_range"]), 2)
            for metric in step["expected"]:
                for key in ("indicator", "metric", "expect"):
                    self.assertIn(key, metric)

        for row in data["ranking"]:
            for key in (
                "rank",
                "name",
                "target_scenario",
                "cost_range",
                "benefit_range",
                "roi_low",
                "roi_high",
                "blocked_by",
                "evidence_refs",
            ):
                self.assertIn(key, row)

        for item in data["do_not"]:
            for key in ("pattern_id", "name", "basis", "evidence", "basis_kind", "evidence_refs"):
                self.assertIn(key, item)

        for row in data["scenario_results"]:
            for key in ("id", "name", "level", "judgment", "level_desc", "next_level"):
                self.assertIn(key, row)
            self.assertIn("quote", row["judgment"])

        for key in ("formula", "conservatism", "elasticity", "benefit_bases", "scale_factor"):
            self.assertIn(key, data["roi_assumptions"])

        for key in ("mode", "criteria_source", "scenario_source", "document", "generated_at"):
            self.assertIn(key, data["meta"])

    def test_knowledge_stats(self):
        response = self.client.get("/api/knowledge/stats")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(data["status"]["policy"], 30)
        self.assertGreaterEqual(data["status"]["cases"], 86)
        self.assertIn("sources", data)

    def test_evaluate_missing_answers(self):
        response = self.client.post("/api/evaluate", json={"answers": {}, "scenario_levels": {}})
        self.assertEqual(response.status_code, 422)

    def test_evaluate_invalid_answer(self):
        payload = json.loads(
            (ROOT / "precomputed/ap1_只买设备不联网.json").read_text(encoding="utf-8")
        )
        profile = payload["profile"]
        profile["answers"]["2"] = ["非法选项"]
        response = self.client.post("/api/evaluate", json=profile)
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
