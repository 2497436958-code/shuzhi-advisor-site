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
        self.assertEqual(data["meta"]["reasoning_status"], "pending")

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
