#!/usr/bin/env python3
"""对比四种排序口径的实测表现（T043 口径裁决用）。

口径候选与含义见 `docs/decisions/T043_ranking.md`。
本脚本只做对比，不改变正式结论（正式口径是 `roi`）。

用法：python3 scripts/compare_ranking_policies.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from advisor.evaluation.runner import run_evaluation
from advisor.evaluation.variants import RANKING_POLICIES

LABELS = {
    "roi": "ROI 下界（现状）",
    "priority_p": "优先级 P 降序",
    "bottleneck_first": "先覆盖已诊断瓶颈",
    "unblock_first": "先解锁一级约束性场景",
}


def main() -> int:
    print(f"{'排序口径':<22}{'T043 Top-3':>12}{'稳定性':>10}{'路径命中':>10}{'诊断 F1':>10}")
    print("-" * 64)
    for policy in RANKING_POLICIES:
        report = run_evaluation(ranking_policy=policy)
        metrics = report["systems"]["control_full"]["metrics"]
        ranking = metrics["T043_ranking_top3"]
        stability = metrics["ranking_stability"]
        print(
            f"{LABELS[policy]:<22}"
            f"{ranking['top3_overlap'] * 100:>11.1f}%"
            f"{stability['flip_rate'] * 100:>9.1f}%"
            f"{metrics['T042_path_hit_rate']['hit_rate'] * 100:>9.1f}%"
            f"{metrics['T041_diagnosis_f1']['bottleneck_micro_f1'] * 100:>9.1f}%"
        )
    print()
    print("说明：T043 的参考顺序是代理定义，与 `unblock_first` 同源，"
          "该口径下 T043 接近 100% 属于循环论证，不能当作口径正确的证据。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
