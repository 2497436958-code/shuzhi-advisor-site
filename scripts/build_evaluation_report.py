#!/usr/bin/env python3
"""跑评测并生成报告（T039—T048）。

用法：python3 scripts/build_evaluation_report.py
输出：data/evaluation/report.json、data/evaluation/report.md
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from advisor.evaluation.runner import run_evaluation, write_reports


def main() -> int:
    report = run_evaluation()
    json_path, md_path = write_reports(report)
    print(f"写出 {json_path.relative_to(ROOT)}")
    print(f"写出 {md_path.relative_to(ROOT)}")
    print()
    for task, verdict in report["verdicts"].items():
        value = "—" if verdict["value"] is None else f"{verdict['value'] * 100:.1f}%"
        print(f"  {task}: {value}（门槛 {verdict['threshold']}）→ {verdict['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
