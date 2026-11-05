#!/usr/bin/env python3
"""真实企业手填复算与公开评测结论比对（T008 / T038）。

用法：
    python3 scripts/verify_real_recompute.py data/profiles/real_001.json

比对内容：
- 等级：必须完全一致（这是硬验收"手填复算与公开评测结论一致"）；
- 总分：公开结论有分数时按 0.5 分容差比对，没有就只比等级；
- 场景数与约束性场景数：作为参考列出，便于解释不一致的原因。

退出码：0 一致；1 不一致；2 文件未填写完整。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from advisor.reasoning.knowledge import load_knowledge
from advisor.reasoning.pipeline import build_result
from advisor.scoring.engine import load_criteria

SCORE_TOLERANCE = 0.5


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"找不到 {path}")
        return 2
    record = json.loads(path.read_text(encoding="utf-8"))
    profile = record.get("profile") or {}
    published = record.get("published_conclusion") or {}

    answers = profile.get("answers") or {}
    levels = profile.get("scenario_levels") or {}
    missing = []
    if len(answers) < 15:
        missing.append(f"采集项答案 {len(answers)}/15")
    if len(levels) < 16:
        missing.append(f"场景等级 {len(levels)}/16")
    if published.get("level") is None:
        missing.append("公开评测结论的等级")
    if missing:
        print("这份真实企业记录还没填完：" + "、".join(missing))
        print("填写说明见 docs/real_enterprise_intake.md")
        return 2

    criteria = load_criteria(ROOT / "precomputed" / "criteria.json")
    result = build_result(profile, criteria, load_knowledge())
    evaluation = result["evaluation"]

    print(f"记录：{record.get('id', path.name)}｜{record.get('name', '')}")
    source = record.get("source") or {}
    if source.get("public_conclusion_url"):
        print(f"公开评测结论出处：{source['public_conclusion_url']}")
    print()
    print(f"{'项目':<12}{'公开结论':>14}{'手填复算':>14}{'一致':>8}")
    print("-" * 50)

    same_level = evaluation["level"] == published["level"]
    print(
        f"{'等级':<12}{str(published.get('level_name') or published['level']):>14}"
        f"{evaluation['level_name']:>14}{'✓' if same_level else '✗':>8}"
    )
    same_score = None
    if published.get("total_score") is not None:
        same_score = abs(evaluation["total_score"] - published["total_score"]) <= SCORE_TOLERANCE
        print(
            f"{'总分':<12}{published['total_score']:>14.2f}{evaluation['total_score']:>14.2f}"
            f"{'✓' if same_score else '✗':>8}"
        )
    print(
        f"{'达到2级场景':<12}{'-':>14}"
        f"{str(evaluation['scenario_count_by_level'].get('2')) + ' 个':>14}{'':>8}"
    )
    print(
        f"{'其中约束性':<12}{'-':>14}"
        f"{str(evaluation['constraint_count_by_level'].get('2')) + ' 个':>14}{'':>8}"
    )
    print()
    if evaluation["unmet"]:
        print("复算未达标的门槛：")
        for line in evaluation["unmet"]:
            print("  · " + line)
    if same_level and (same_score is None or same_score):
        print("结论：手填复算与公开评测结论一致 ✓（可写入评测报告的真实层）")
        return 0
    print("结论：与公开评测结论不一致，需要说明差异原因（等级不同不能直接采用）。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
