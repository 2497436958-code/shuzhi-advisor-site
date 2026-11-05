"""确定性评测指标打分器。

约定：
- 模型不参与算术；
- 多选选「无」得 0 分；
- 多选非「无」按 `选中数 × 100 ÷ (总选项数 - 1)` 计分；
- 单选按选项序号等距计分；
- 采集项 8 官方只给 6 个选项但未给分值，按等距线性兜底并在结果中披露。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .thresholds import LEVELS

DEFAULT_LEVEL = 1


def load_criteria(path: str | Path) -> dict[str, Any]:
    """加载并做结构校验。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_criteria(data)
    return data


def validate_criteria(data: dict[str, Any]) -> None:
    indicators = data.get("indicators")
    scenarios = data.get("scenarios")
    levels = data.get("levels")
    if not isinstance(indicators, list) or len(indicators) != 15:
        raise ValueError(f"采集项数量必须是 15，当前是 {len(indicators) if isinstance(indicators, list) else '缺失'}")
    if not isinstance(scenarios, list) or len(scenarios) != 16:
        raise ValueError(f"应用场景数量必须是 16，当前是 {len(scenarios) if isinstance(scenarios, list) else '缺失'}")
    if len({item["id"] for item in indicators}) != 15:
        raise ValueError("采集项 ID 必须唯一")
    if len({item["id"] for item in scenarios}) != 16:
        raise ValueError("场景 ID 必须唯一")
    if len(levels) != 4:
        raise ValueError("必须定义四个等级门槛")

    for item in indicators:
        if item["option_type"] not in {"单选", "多选"}:
            raise ValueError(f"采集项 {item['id']} 的题型非法：{item['option_type']}")
        if len(item["options"]) < 2:
            raise ValueError(f"采集项 {item['id']} 的选项数非法")
        if item["max_points"] <= 0:
            raise ValueError(f"采集项 {item['id']} 的满分非法")

    for scenario in scenarios:
        if set(scenario["levels"].keys()) != {"1", "2", "3", "4"}:
            raise ValueError(f"场景 {scenario['id']} 必须包含 1—4 级判定要求")

    weights = [item["chain_weight"] for item in indicators]
    if not abs(sum(weights) - 1.0) < 1e-9:
        raise ValueError(f"15 个采集项权重之和必须为 1.0，当前为 {sum(weights):.6f}")


def item_score(indicator: dict[str, Any], selected: list[str]) -> float:
    options = indicator["options"]
    option_type = indicator["option_type"]

    if option_type == "单选":
        if len(selected) != 1:
            raise ValueError(f"采集项 {indicator['id']} 是单选，答案数量为 {len(selected)}")
        if selected[0] not in options:
            raise ValueError(f"采集项 {indicator['id']} 选项非法：{selected[0]}")
        index = options.index(selected[0])
        return round(index * 100.0 / (len(options) - 1), 2)

    if not selected:
        raise ValueError(f"采集项 {indicator['id']} 是多选，必须至少选择一项")
    if "无" not in options:
        raise ValueError(f"采集项 {indicator['id']} 的多选选项缺少「无」")
    if selected.count("无") > 1:
        raise ValueError(f"采集项 {indicator['id']} 的「无」最多只能选择一次")
    if "无" in selected:
        if len(selected) != 1:
            raise ValueError(f"采集项 {indicator['id']} 选择「无」时不能与其他选项并存")
        return 0.0

    unknown = [value for value in selected if value not in options]
    if unknown:
        raise ValueError(f"采集项 {indicator['id']} 选项非法：{'、'.join(unknown)}")
    selected_count = len(selected)
    denominator = len(options) - 1
    return round(selected_count * 100.0 / denominator, 2)


def scenario_count_by_level(scenario_levels: dict[str, int]) -> dict[str, int]:
    """按“达到 N 级”统计，即等级值 >= N 的场景数量。"""
    counts = {"1": 0, "2": 0, "3": 0, "4": 0}
    for level in counts:
        counts[level] = sum(1 for value in scenario_levels.values() if value >= int(level))
    return counts


def constraint_count_by_level(
    scenarios: list[dict[str, Any]], scenario_levels: dict[str, int]
) -> dict[str, int]:
    """按“达到 N 级的约束性场景”统计。"""
    counts = {"1": 0, "2": 0, "3": 0, "4": 0}
    for scenario in scenarios:
        if not scenario.get("constraint"):
            continue
        level = scenario_levels.get(scenario["id"], DEFAULT_LEVEL)
        for threshold in counts:
            if level >= int(threshold):
                counts[threshold] += 1
    return counts


def evaluate_profile(profile: dict[str, Any], criteria: dict[str, Any]) -> dict[str, Any]:
    answers = profile.get("answers", {})
    item_results: list[dict[str, Any]] = []
    dimension_points: dict[str, float] = {}

    for indicator in criteria["indicators"]:
        selected = answers.get(str(indicator["id"]))
        if not isinstance(selected, list):
            raise ValueError(f"采集项 {indicator['id']} 未作答")
        score = item_score(indicator, selected)
        raw_points = indicator["chain_weight"] * score
        points = round(raw_points, 2)
        dimension_points[indicator["primary"]] = (
            dimension_points.get(indicator["primary"], 0.0) + raw_points
        )
        item_results.append(
            {
                "id": indicator["id"],
                "title": indicator["title"],
                "item": indicator["item"],
                "primary": indicator["primary"],
                "secondary": indicator["secondary"],
                "option_type": indicator["option_type"],
                "selected": selected,
                "score": score,
                "points": points,
                "max_points": indicator["max_points"],
                "chain_weight": indicator["chain_weight"],
                "rule_gap": indicator.get("official_rule_gap", False),
            }
        )

    dimension_scores = {
        name: round(value, 2) for name, value in dimension_points.items()
    }
    raw_total = sum(dimension_points.values())
    total_score = round(raw_total, 2)
    display_total = round(raw_total, 1)

    raw_scenario_levels = profile.get("scenario_levels", {})
    scenario_levels = (
        {key: int(value) for key, value in raw_scenario_levels.items()}
        if raw_scenario_levels
        else {scenario["id"]: DEFAULT_LEVEL for scenario in criteria["scenarios"]}
    )
    scenario_levels_source = "submitted" if raw_scenario_levels else "rule_baseline"

    scenario_counts = scenario_count_by_level(scenario_levels)
    constraint_counts = constraint_count_by_level(criteria["scenarios"], scenario_levels)

    highest_level = None
    unmet: list[str] = []
    for threshold in LEVELS:
        level = threshold["level"]
        reasons: list[str] = []
        if total_score < threshold["min_score"]:
            reasons.append(f"评测得分 {display_total:.1f} < {threshold['min_score']:.0f} 分")
        if scenario_counts[str(level)] < threshold["min_scenarios"]:
            reasons.append(
                f"达到 {level} 级的应用场景 {scenario_counts[str(level)]} 个 < {threshold['min_scenarios']} 个"
            )
        if constraint_counts[str(level)] < threshold["min_constraint_scenarios"]:
            reasons.append(
                f"其中约束性场景 {constraint_counts[str(level)]} 个 < {threshold['min_constraint_scenarios']} 个"
            )
        if reasons:
            unmet.append(
                f"{level} 级（{threshold['name']}）：{'；'.join(reasons)}"
            )
        else:
            highest_level = threshold

    rule_gaps = [
        f"采集项 {item['id']}（{item['item']}）为 {len(item['options'])} 选项单选，官方评分逻辑未覆盖，按等距线性兜底计分"
        for item in criteria["indicators"]
        if item.get("official_rule_gap")
    ]

    return {
        "total_score": total_score,
        "level": highest_level["level"] if highest_level else None,
        "level_name": highest_level["name"] if highest_level else "无等级",
        "dimension_scores": dimension_scores,
        "unmet": unmet,
        "rule_gaps": rule_gaps,
        "scenario_levels_source": scenario_levels_source,
        "scenario_count_by_level": scenario_counts,
        "constraint_count_by_level": constraint_counts,
        "item_results": item_results,
        "scenario_levels": scenario_levels,
    }
