"""证据链强制规则：没有证据的结论不允许输出。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from advisor.reasoning.evidence import (
    EvidenceRef,
    MissingEvidenceError,
    ensure_evidence,
)


class EvidenceTests(unittest.TestCase):
    def test_missing_evidence_raises(self):
        with self.assertRaises(MissingEvidenceError):
            ensure_evidence("测试结论", [])

    def test_evidence_is_serialized(self):
        ref = EvidenceRef(
            kind="采集项",
            ref="采集项 3",
            title="数字化基础/设备系统/设备联网",
            quote="企业的生产设备联网率 → [0-10%]",
            doc="工信厅企业〔2024〕56 号 附件（一）",
            url="official/中小企业数字化水平评测指标（2024年版）.pdf",
            note="官方选项原文",
        )
        materialized = ensure_evidence("测试结论", [ref])
        self.assertEqual(len(materialized), 1)
        self.assertEqual(materialized[0]["kind"], "采集项")
        self.assertTrue(materialized[0]["quote"])


if __name__ == "__main__":
    unittest.main()
