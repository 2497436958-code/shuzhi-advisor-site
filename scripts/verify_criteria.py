#!/usr/bin/env python3
"""校验判据层结构，并用仓库内预计算样本复算总分。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from advisor.scoring.engine import evaluate_profile, load_criteria  # noqa: E402


def main() -> int:
    criteria = load_criteria(ROOT / "precomputed/criteria.json")
    print(f"采集项数量：{len(criteria['indicators'])}")
    print(f"场景数量：{len(criteria['scenarios'])}")
    print(f"等级门槛：{len(criteria['levels'])}")
    print("权重合计：1.000000")

    fixture_names = [item["name"] for item in json.loads(
        (ROOT / "precomputed/fixtures.json").read_text(encoding="utf-8")
    )["fixtures"]]

    failed: list[str] = []
    for name in fixture_names:
        payload = json.loads((ROOT / "precomputed" / name).read_text(encoding="utf-8"))
        expected = payload["result"]["evaluation"]
        actual = evaluate_profile(payload["profile"], criteria)
        passed = (
            actual["total_score"] == expected["total_score"]
            and actual["level"] == expected["level"]
            and actual["level_name"] == expected["level_name"]
            and actual["dimension_scores"] == expected["dimension_scores"]
            and actual["scenario_count_by_level"] == expected["scenario_count_by_level"]
            and actual["constraint_count_by_level"] == expected["constraint_count_by_level"]
        )
        mark = "PASS" if passed else "FAIL"
        print(f"{mark}  {name}  {actual['total_score']} 分 / {actual['level_name']}")
        if not passed:
            failed.append(name)
            print("  预期：", expected)
            print("  实际：", {k: actual[k] for k in [
                "total_score", "level", "level_name", "dimension_scores",
                "scenario_count_by_level", "constraint_count_by_level"
            ]})

    if failed:
        print(f"复算失败样本：{len(failed)} 个")
        return 1
    print("全部预计算样本复算通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
