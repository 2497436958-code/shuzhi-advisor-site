"""投入产出模型与排序。

口径（主控文档第 8 节）：

    ROI = 预期可量化成效收益 ÷ 投入成本
    分子 = 采集项 12—15 对应的预期改善收益
    分母 = 直接投入 + 年运维 + 内部工时折价

排序取 **下界**（最小收益 ÷ 最大成本），并给出区间；
优先级 ``P = (等级跃迁分 + 关联成效改善) ÷ 投入成本``，
其中等级跃迁分是该改造项相关采集项的可回收分数。

规模折算：投入区间与收益基数都按营业收入等比折算（基准见
``data/pathways.json`` 的 ``source.revenue_reference_wan``），
ROI 是比值，不随规模变化。**该折算律尚未用真实企业校准，待人工确认。**
"""

from __future__ import annotations

from typing import Any

REFERENCE_REVENUE_WAN = 6000.0


def scale_factor(profile: dict[str, Any]) -> float:
    """按营业收入折算的比例；没有填营业额时按 1.0 处理。"""
    revenue = profile.get("revenue_wan")
    if not revenue or revenue <= 0:
        return 1.0
    return float(revenue) / REFERENCE_REVENUE_WAN


def benefit_bases(
    reference_bases: dict[str, float], scale: float
) -> dict[str, float]:
    """按规模折算后的收益基数（万元/年）。"""
    return {key: value * scale for key, value in reference_bases.items()}


def level_gain(action: dict[str, Any], items: dict[int, dict[str, Any]]) -> float:
    """等级跃迁分：该改造项相关采集项当前可回收的分数（占总分）。"""
    total = 0.0
    for item_id in action.get("target_items") or []:
        item = items.get(item_id)
        if item is None:
            continue
        total += item["chain_weight"] * (100.0 - item["score"])
    return round(total, 2)


def benefit_range(
    action: dict[str, Any], bases: dict[str, float]
) -> tuple[float, float]:
    """预期年化收益区间（万元/年）。"""
    low = 0.0
    high = 0.0
    for indicator, elasticity in (action.get("elasticity") or {}).items():
        base = bases.get(str(indicator))
        if base is None:
            continue
        low += base * elasticity["low"]
        high += base * elasticity["high"]
    return low, high


def roi_range(
    action: dict[str, Any], bases: dict[str, float]
) -> tuple[float, float, float, float]:
    """ROI 区间。下界用最小收益配最大成本，上界反之。"""
    low, high = benefit_range(action, bases)
    cost_low, cost_high = action["cost_range"]
    if cost_high <= 0:
        raise ValueError(f"改造项 {action['action_id']} 的成本区间非法")
    return low, high, low / cost_high, high / cost_low


def priority_score(
    action: dict[str, Any], bases: dict[str, float], gain: float
) -> float:
    """优先级 P = (等级跃迁分 + 关联成效改善) ÷ 投入成本。

    两个分子项单位不同（分 / 万元），按主控文档给定公式直接计算，
    只用于同一依赖层内的排序，不作为业务结论数。
    """
    low, _ = benefit_range(action, bases)
    cost_high = action["cost_range"][1]
    return round((gain + low) / cost_high, 4) if cost_high else 0.0


def build_ranking(
    profile: dict[str, Any],
    evaluation: dict[str, Any],
    criteria: dict[str, Any],
    actions: list[dict[str, Any]],
    reference_bases: dict[str, float],
    content: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """产出排序段（按 ROI 下界排序）与 ROI 口径说明。"""
    from . import evidence as ev

    items = {item["id"]: item for item in evaluation["item_results"]}
    scale = scale_factor(profile)
    bases = benefit_bases(reference_bases, scale)

    rows: list[dict[str, Any]] = []
    for action in actions:
        low, high, roi_low, roi_high = roi_range(action, bases)
        gain = level_gain(action, items)
        scenario_id = action["target_scenario"]
        refs = []
        for item_id in action.get("target_items") or []:
            item = items.get(item_id)
            if item is not None:
                refs.append(ev.indicator_ref(criteria, item_id, item))
        scenario = next(
            (s for s in criteria["scenarios"] if s["id"] == scenario_id), None
        )
        if scenario is not None:
            level = (evaluation.get("scenario_levels") or {}).get(scenario_id, 1)
            refs.append(ev.scenario_ref(criteria, scenario_id, level))
        rows.append(
            {
                "name": action["action_name"],
                "action_id": action["action_id"],
                "target_scenario": scenario_id,
                "cost_range": [round(action["cost_range"][0] * scale, 2), round(action["cost_range"][1] * scale, 2)],
                "benefit_range": [round(low, 1), round(high, 1)],
                "roi_low": round(roi_low, 4),
                "roi_high": round(roi_high, 4),
                "blocked_by": list(action.get("blocked_by") or []),
                "level_gain": gain,
                "priority": priority_score(action, bases, gain),
                "evidence_refs": ev.ensure_evidence(action["action_name"], refs),
            }
        )

    rows.sort(key=lambda row: (-row["roi_low"], -row["priority"], row["action_id"]))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index

    assumptions = {
        "formula": "ROI = 预期可量化成效收益 ÷ 投入成本（分子取成效采集项 12—15，分母取投入 + 年运维 + 内部工时折价）",
        "conservatism": "排序取 ROI 下界（最小收益 ÷ 最大成本）",
        "elasticity": "成效弹性为演示估算区间，无公开案例支撑，只用于排序，不作为结论数",
        "benefit_bases": {key: round(value, 1) for key, value in bases.items()},
        "scale_factor": round(scale, 4),
        "flip_rate": None,
        "scale_note": (
            f"投入区间与收益基数按营业收入折算（基准 {REFERENCE_REVENUE_WAN:g} 万元营收，"
            "折算律待真实企业校准）；ROI 为比值，不随规模变化。"
        ),
        "priority_formula": "P = (等级跃迁分 + 关联成效改善) ÷ 投入成本",
    }
    return rows, assumptions
