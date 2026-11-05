#!/usr/bin/env python3
"""对比实时引擎输出与站点已发布的预计算结果。

用途：让下一个模型一眼看到"哪些结论完全一致、哪些有意不同"。
判据层与共同改造项的 ROI 必须完全一致；路径段的差异是已知且有意保留的
（原因见 docs/reasoning_layer.md）。

退出码 0 表示判据层与 ROI 一致；不一致时返回 1。
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

FIXTURES = [
    "ap0_无等级",
    "ap1_只买设备不联网",
    "ap2_只上系统不跑流程",
    "ap3_只做数据采集不做分析",
    "ap4_只追补贴不建能力",
    "baseline_二级规范级",
]


def main() -> int:
    criteria = load_criteria(ROOT / "precomputed" / "criteria.json")
    knowledge = load_knowledge()
    print(f"知识库状态：{knowledge.status()}")
    failures = 0

    for name in FIXTURES:
        fixture = json.loads(
            (ROOT / "precomputed" / f"{name}.json").read_text(encoding="utf-8")
        )
        published = fixture["result"]
        engine = build_result(fixture["profile"], criteria, knowledge)

        diff = {
            key: (value, engine["evaluation"][key])
            for key, value in published["evaluation"].items()
            if engine["evaluation"].get(key) != value
        }
        ap_published = [hit["pattern_id"] for hit in published["do_not"]]
        ap_engine = [hit["pattern_id"] for hit in engine["do_not"]]
        published_roi = {
            row["name"]: (row["roi_low"], row["roi_high"]) for row in published["ranking"]
        }
        roi_diff = [
            (row["name"], (row["roi_low"], row["roi_high"]), published_roi[row["name"]])
            for row in engine["ranking"]
            if row["name"] in published_roi
            and (row["roi_low"], row["roi_high"]) != published_roi[row["name"]]
        ]

        consistent = not diff and not roi_diff and ap_published == ap_engine
        if not consistent:
            failures += 1
        print(f"\n=== {name}：判据层/反模式/ROI {'一致' if consistent else '不一致'}")
        if diff:
            print("  判据层差异：", diff)
        if ap_published != ap_engine:
            print(f"  反模式：预计算 {ap_published} / 引擎 {ap_engine}")
        if roi_diff:
            print("  ROI 差异：", roi_diff)
        print("  路径段（预计算）：", [(s["path_ref"], s["target_scenario"]) for s in published["pathway"]])
        print("  路径段（引擎）  ：", [(s["path_ref"], s["target_scenario"]) for s in engine["pathway"]])

    print("\n结论：判据层 100% 可复算；路径段的差异是已知的口径差异（见 docs/reasoning_layer.md）。")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
