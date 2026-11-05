"""诊断：把评测结果翻译成"卡在哪一步"。

四类瓶颈（与主控文档第 8 节的判据一致，全部可复算）：

1. 反模式型瓶颈：命中 AP1—AP4 时，瓶颈直接指向判据命中的采集项与场景。
2. 场景断层：约束性场景还停在一级，直接卡等级门槛。
3. 等级缺口：距下一个等级还差哪几条硬指标（得分 / 场景数 / 约束性场景数）。
4. 基础缺口·一级指标：数字化基础维度得分不足一半的采集项。

规则里不出现模型生成的解释文本；每条结论的措辞、命中项、得分口径
都由 ``advisor.scoring.engine`` 的结果算出来，模型不参与算分。
"""

from __future__ import annotations

from typing import Any

from .antipatterns import AntipatternHit
from . import evidence as ev

AP_BOTTLENECK = {
    "AP1": ("设备已购入但未联网，数据流在设备侧断掉", "基础断层·设备侧"),
    "AP2": ("信息系统铺开但关键业务流程没有真正跑通", "流程空转·系统已上"),
    "AP3": ("数据沉底·只采不析", "数据沉底·只采不析"),
    "AP4": ("投入错配·重投入轻能力", "投入错配·重投入轻能力"),
}

SCENE_GAP_TYPE = "场景断层·约束性场景未进阶"
LEVEL_GAP_TYPE = "等级缺口"
BASE_GAP_TYPE = "基础缺口·一级指标"

FOUNDATION_DIMENSION = "数字化基础"
FOUNDATION_SCORE_FLOOR = 50.0

MAX_ITEM_REFS = 5
MAX_SCENARIO_REFS = 4
MAX_GAP_ITEMS = 3


def _items(evaluation: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {item["id"]: item for item in evaluation["item_results"]}


def _gain(item: dict[str, Any]) -> float:
    """该项可回收的分数（占总分多少分）。"""
    return item["chain_weight"] * (100.0 - item["score"])


def _round_gain(value: float) -> float:
    return round(value, 2)


def _constraint_scenarios_at_level_one(
    evaluation: dict[str, Any], criteria: dict[str, Any]
) -> list[dict[str, Any]]:
    levels = evaluation.get("scenario_levels") or {}
    return [
        scenario
        for scenario in criteria["scenarios"]
        if scenario.get("constraint") and levels.get(scenario["id"], 1) <= 1
    ]


def _level_gap(
    evaluation: dict[str, Any], criteria: dict[str, Any]
) -> tuple[dict[str, Any] | None, list[str]]:
    """下一个够不到的等级及其未达标原因。

    原因直接取自引擎算出的 ``unmet``（门槛判定只在 ``advisor.scoring.engine``
    里实现一次，这里不重复算）。
    """
    achieved = evaluation.get("level")
    reasons: dict[int, list[str]] = {}
    for line in evaluation.get("unmet") or []:
        head, _, tail = line.partition("：")
        level_text = head.split(" ")[0]
        if level_text.isdigit():
            reasons[int(level_text)] = [part for part in tail.split("；") if part]

    for threshold in criteria["levels"]:
        if achieved is not None and threshold["level"] <= achieved:
            continue
        if threshold["level"] in reasons:
            return threshold, reasons[threshold["level"]]
    return None, []


# 反模式 → 案例库中的支撑案例。按场景就近匹配，取案例库中最先命中的真实条目。
def _match_cases(
    hits: list[AntipatternHit], knowledge: Any
) -> dict[str, dict[str, Any]]:
    matched: dict[str, dict[str, Any]] = {}
    for hit in hits:
        for scenario_id in hit.hit_scenarios:
            candidates = knowledge.cases_for_scenario(scenario_id)
            if candidates:
                matched[hit.pattern_id] = candidates[0]
                break
    return matched


def build_diagnosis(
    evaluation: dict[str, Any],
    criteria: dict[str, Any],
    hits: list[AntipatternHit],
    knowledge: Any,
) -> list[dict[str, Any]]:
    """产出诊断条目（顺序：反模式 → 场景断层 → 等级缺口 → 基础缺口）。"""
    items = _items(evaluation)
    entries: list[dict[str, Any]] = []

    matched_cases = _match_cases(hits, knowledge)
    for hit in hits:
        bottleneck, bottleneck_type = AP_BOTTLENECK[hit.pattern_id]
        levels = evaluation.get("scenario_levels") or {}
        refs: list[ev.EvidenceRef] = [
            ev.criteria_ref(hit.pattern_id, hit.name, hit.basis)
        ]
        for item_id in hit.hit_items:
            refs.append(ev.indicator_ref(criteria, item_id, items[item_id]))
        for scenario_id in hit.hit_scenarios:
            refs.append(ev.scenario_ref(criteria, scenario_id, levels.get(scenario_id, 1)))
        case = matched_cases.get(hit.pattern_id)
        if case is not None:
            refs.append(ev.case_ref(case))
        entries.append(
            {
                "bottleneck": bottleneck,
                "bottleneck_type": bottleneck_type,
                "hit_items": list(hit.hit_items),
                "hit_scenarios": list(hit.hit_scenarios),
                "evidence": f"{hit.evidence}。判据：{hit.basis}",
                "basis_kind": hit.basis_kind,
                "max_score_gain": _round_gain(
                    sum(_gain(items[item_id]) for item_id in hit.hit_items)
                ),
                "case_ref": case["id"] if case is not None else None,
                "evidence_refs": ev.ensure_evidence(bottleneck, refs),
            }
        )

    # 场景断层：约束性场景还停在一级
    stuck = _constraint_scenarios_at_level_one(evaluation, criteria)
    if stuck:
        levels = evaluation.get("scenario_levels") or {}
        detail = "；".join(
            f"{scenario['id']}「{scenario['name']}」当前 {levels.get(scenario['id'], 1)}"
            for scenario in stuck
        )
        bottleneck = f"{len(stuck)} 个约束性场景还停在一级，等级门槛上不去"
        evidence = (
            f"{detail}。约束性场景（官方标 *）是引导深度改造的重点场景，"
            "二级判定要求见附件（二）；场景层不直接计分，但直接卡等级门槛。"
        )
        refs = [
            ev.scenario_ref(criteria, scenario["id"], levels.get(scenario["id"], 1))
            for scenario in stuck[:MAX_SCENARIO_REFS]
        ]
        entries.append(
            {
                "bottleneck": bottleneck,
                "bottleneck_type": SCENE_GAP_TYPE,
                "hit_items": [],
                "hit_scenarios": [scenario["id"] for scenario in stuck],
                "evidence": evidence,
                "basis_kind": "官方附件（二）场景等级判定要求",
                "max_score_gain": 0.0,
                "case_ref": None,
                "evidence_refs": ev.ensure_evidence(bottleneck, refs),
            }
        )

    # 等级缺口：下一个够不到的等级
    threshold, reasons = _level_gap(evaluation, criteria)
    if threshold is not None:
        if evaluation.get("level") is None:
            bottleneck = "总分与场景数够不到最低一级（无等级）"
        else:
            bottleneck = f"距 {threshold['level']} 级（{threshold['name']}）还差门槛"
        ranked = sorted(items.values(), key=lambda item: (-_gain(item), item["id"]))
        gap_items = ranked[:MAX_GAP_ITEMS]
        refs = [ev.level_ref()]
        refs += [
            ev.indicator_ref(criteria, item["id"], item) for item in gap_items
        ]
        entries.append(
            {
                "bottleneck": bottleneck,
                "bottleneck_type": LEVEL_GAP_TYPE,
                "hit_items": [item["id"] for item in gap_items],
                "hit_scenarios": [],
                "evidence": "；".join(reasons),
                "basis_kind": "官方附件（二）二、判定方法（得分与场景数须同时满足）",
                "max_score_gain": _round_gain(sum(_gain(item) for item in gap_items)),
                "case_ref": None,
                "evidence_refs": ev.ensure_evidence(bottleneck, refs),
            }
        )

    # 基础缺口：数字化基础维度里得分不足一半的采集项
    dimension_weight = next(
        (
            indicator["primary_weight"]
            for indicator in criteria["indicators"]
            if indicator["primary"] == FOUNDATION_DIMENSION
        ),
        0.5,
    )
    dimension_score = evaluation["dimension_scores"].get(FOUNDATION_DIMENSION, 0.0)
    weak_items = [
        item
        for item in items.values()
        if item["primary"] == FOUNDATION_DIMENSION and item["score"] < FOUNDATION_SCORE_FLOOR
    ]
    # 维度整体低于该维度权重的一半才算"基础缺口"；个别采集项偏低不单独开一条诊断
    if weak_items and dimension_score < dimension_weight * 100 / 2:
        weak_items.sort(key=lambda item: item["id"])
        detail = "、".join(
            f"采集项 {item['id']}「{item['item']}」{round(item['score'])} 分"
            for item in weak_items
        )
        bottleneck = "数字化基础维度偏低，设备与数据底座还没打牢"
        evidence = (
            f"{FOUNDATION_DIMENSION}得分 {dimension_score:.2f} / "
            f"{dimension_weight * 100:g}（一级指标权重 {dimension_weight * 100:g}%）；"
            f"其中 {detail}"
        )
        refs = [
            ev.weight_ref(FOUNDATION_DIMENSION, dimension_weight * 100),
            *[
                ev.indicator_ref(criteria, item["id"], item)
                for item in weak_items[:MAX_ITEM_REFS]
            ],
        ]
        entries.append(
            {
                "bottleneck": bottleneck,
                "bottleneck_type": BASE_GAP_TYPE,
                "hit_items": [item["id"] for item in weak_items],
                "hit_scenarios": [],
                "evidence": evidence,
                "basis_kind": "官方附件（一）权重体系（一级指标权重 50%）",
                "max_score_gain": _round_gain(sum(_gain(item) for item in weak_items)),
                "case_ref": None,
                "evidence_refs": ev.ensure_evidence(bottleneck, refs),
            }
        )

    return entries

