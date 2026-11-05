"""投入产出与优先级计算测试。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from advisor.reasoning.ranking import (
    benefit_range,
    level_gain,
    priority_score,
    roi_range,
    scale_factor,
)


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.action = {
            "action_id": "P-NET",
            "action_name": "设备入网与数据采集打通",
            "cost_range": [30.0, 90.0],
            "elasticity": {
                "13": {"metric": "月均产品合格率", "low": 0.01, "high": 0.03, "supported": True},
                "12": {"metric": "每百元营业收入中综合能源消费量", "low": 0.01, "high": 0.025, "supported": True},
            },
        }
        self.bases = {"12": 90.0, "13": 72.0, "14": 6000.0, "15": 3600.0}
        self.items = {
            1: {"id": 1, "score": 50.0, "chain_weight": 0.08},
            3: {"id": 3, "score": 0.0, "chain_weight": 0.06},
            4: {"id": 4, "score": 35.71, "chain_weight": 0.10},
        }

    def test_benefit_range(self):
        low, high = benefit_range(self.action, self.bases)
        self.assertAlmostEqual(low, 72.0 * 0.01 + 90.0 * 0.01, places=6)
        self.assertAlmostEqual(high, 72.0 * 0.03 + 90.0 * 0.025, places=6)

    def test_roi_uses_conservative_bounds(self):
        low, high, roi_low, roi_high = roi_range(self.action, self.bases)
        self.assertAlmostEqual(roi_low, low / 90.0, places=9)
        self.assertAlmostEqual(roi_high, high / 30.0, places=9)

    def test_level_gain(self):
        action = dict(self.action, target_items=[3, 4])
        gain = level_gain(action, self.items)
        self.assertAlmostEqual(gain, 0.06 * 100 + 0.10 * (100 - 35.71), places=2)

    def test_priority_formula(self):
        action = dict(self.action, target_items=[3])
        gain = level_gain(action, self.items)
        expected = (gain + 72.0 * 0.01 + 90.0 * 0.01) / 90.0
        self.assertAlmostEqual(priority_score(action, self.bases, gain), expected, places=4)

    def test_scale_factor(self):
        self.assertEqual(scale_factor({"revenue_wan": 6000}), 1.0)
        self.assertEqual(scale_factor({"revenue_wan": 12000}), 2.0)
        self.assertEqual(scale_factor({}), 1.0)


if __name__ == "__main__":
    unittest.main()
