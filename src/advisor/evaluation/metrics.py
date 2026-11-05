"""六项评测指标（T041—T046）。

每个指标写清**分子分母是什么**、**参考值从哪来**，避免出现"指标好看但没法复核"。
参考值一律来自**判据层与样本自身**，不来自被测系统的输出，避免自己给自己判卷。

T041 诊断准确率 F1 ≥0.80
    参考：样本按构造应当出现的瓶颈类型集合（反模式型 + 场景断层 + 等级缺口 + 基础缺口）。
    另给一个只看"瓶颈型"（反模式型与场景断层）的 F1——那部分才是有区分度的。
T042 归因路径命中率 ≥70%
    参考：样本里仍在一级的场景所对应的改造项（取自路径表的场景—改造项映射）。
    命中 = 这些改造项出现在系统给出的路径段里。
T043 排序一致性 Top-3 ≥70%
    参考：独立算出的"应先做顺序"——按能解锁的一级约束性场景数、再按可回收分数排序。
    一致性 = 系统 Top-3 与参考 Top-3 的重合率。
    注：主控文档没有定义参考顺序，这里用的是可解释的代理定义，已在报告里写明。
T044 反模式检出率 ≥85% / 误报率 ≤15%
    参考：样本按构造应当命中的反模式（每家至多一个）。
T045 ROI 测算偏差 ≤20%
    合成层没有真值，给两个可复核的数：实现一致性（独立复算与引擎结果的偏差）、
    弹性口径切换偏差（换成有公开案例支撑的弹性区间后 ROI 的变化）。
    **真实偏差需要 T038 的真实企业样本，本指标在真实层落地前不算完成。**
T046 跨行业泛化 ≤10 个百分点
    按行业分组算诊断 F1，最差行业与总体的差即衰减幅度。
"""

from __future__ import annotations

import json
import zlib
from pathlib import Path
from typing import Any

from ..scoring.engine import evaluate_profile

ROOT = Path(__file__).resolve().parents[3]

AP_DIAGNOSIS_TYPE = {
    "AP1": "基础断层·设备侧",
    "AP2": "流程空转·系统已上",
    "AP3": "数据沉底·只采不析",
    "AP4": "投入错配·重投入轻能力",
}
BOTTLENECK_TYPES = {"基础断层·设备侧", "流程空转·系统已上", "数据沉底·只采不析", "投入错配·重投入轻能力"}


def _expected_diagnosis_types(
    sample: dict[str, Any], criteria: dict[str, Any], evaluation: dict[str, Any]
) -> set[str]:
    """按构造应当出现的瓶颈类型（与推理层实现无关，只看判据与样本本身）。"""
    expected: set[str] = set()
    archetype = sample["archetype"]
    if archetype in AP_DIAGNOSIS_TYPE:
        expected.add(AP_DIAGNOSIS_TYPE[archetype])

    levels = sample["profile"]["scenario_levels"]
    constraint = [
        scenario["id"]
        for scenario in criteria["scenarios"]
        if scenario.get("constraint") and levels.get(scenario["id"], 1) <= 1
    ]
    if constraint:
        expected.add("场景断层·约束性场景未进阶")

    expected.add("等级缺口")

    dimension_weight = next(
        (
            item["primary_weight"]
            for item in criteria["indicators"]
            if item["primary"] == "数字化基础"
        ),
        0.5,
    )
    dimension_score = evaluation["dimension_scores"].get("数字化基础", 0.0)
    if dimension_score < dimension_weight * 100 / 2:
        expected.add("基础缺口·一级指标")
    return expected


def _f1(tp: int, fp: int, fn: int) -> float:
    if tp == 0:
        return 0.0
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    return 2 * precision * recall / (precision + recall)


def _diagnosis_metrics(
    samples: list[dict[str, Any]],
    conclusions: list[dict[str, Any]],
    criteria: dict[str, Any],
) -> dict[str, Any]:
    tp = fp = fn = 0
    btp = bfp = bfn = 0
    per_sample: list[float] = []
    for sample, conclusion in zip(samples, conclusions):
        evaluation = evaluate_profile(sample["profile"], criteria)
        expected = _expected_diagnosis_types(sample, criteria, evaluation)
        predicted = {entry["bottleneck_type"] for entry in conclusion["diagnosis"]}
        hit = expected & predicted
        tp += len(hit)
        fp += len(predicted - expected)
        fn += len(expected - predicted)
        per_sample.append(_f1(len(hit), len(predicted - expected), len(expected - predicted)))

        expected_b = expected & BOTTLENECK_TYPES
        predicted_b = predicted & BOTTLENECK_TYPES
        hit_b = expected_b & predicted_b
        btp += len(hit_b)
        bfp += len(predicted_b - expected_b)
        bfn += len(expected_b - predicted_b)

    return {
        "micro_f1": round(_f1(tp, fp, fn), 4),
        "macro_f1": round(sum(per_sample) / len(per_sample), 4) if per_sample else 0.0,
        "bottleneck_micro_f1": round(_f1(btp, bfp, bfn), 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def _path_metrics(
    samples: list[dict[str, Any]], conclusions: list[dict[str, Any]]
) -> dict[str, Any]:
    covered = 0
    hit_total = 0
    expected_total = 0
    per_sample: list[float] = []
    for sample, conclusion in zip(samples, conclusions):
        expected = set(sample["expected"]["action_ids"])
        produced = {step["action_id"] for step in conclusion["pathway"]}
        if not expected:
            continue
        covered += 1
        hit = len(expected & produced)
        hit_total += hit
        expected_total += len(expected)
        per_sample.append(hit / len(expected))
    return {
        "hit_rate": round(hit_total / expected_total, 4) if expected_total else 0.0,
        "mean_sample_rate": round(sum(per_sample) / len(per_sample), 4) if per_sample else 0.0,
        "covered_samples": covered,
        "expected_actions": expected_total,
        "hit_actions": hit_total,
    }


def _reference_top3(
    sample: dict[str, Any], action_table: dict[str, Any], evaluation: dict[str, Any]
) -> list[str]:
    """独立算出的"应先做顺序"：先解锁的一级约束性场景多者先做，再看可回收分数。"""
    levels = sample["profile"]["scenario_levels"]
    constraint = {
        scenario["id"]
        for scenario in criteria_scenarios(sample)
        if scenario.get("constraint")
    }
    items = {item["id"]: item for item in evaluation["item_results"]}
    scored: list[tuple[float, str]] = []
    for action_id in sample["expected"]["action_ids"]:
        action = action_table.get(action_id, {})
        scenarios = action.get("target_scenarios") or []
        unblock = sum(
            1
            for scenario_id in scenarios
            if levels.get(scenario_id, 9) <= 1 and scenario_id in constraint
        )
        recover = 0.0
        for item_id in action.get("target_items") or []:
            item = items.get(item_id)
            if item is not None:
                recover += item["chain_weight"] * (100.0 - item["score"])
        scored.append((-(unblock * 10 + recover), action_id))
    scored.sort()
    return [action_id for _, action_id in scored[:3]]


def criteria_scenarios(sample: dict[str, Any]) -> list[dict[str, Any]]:
    return sample["_criteria"]["scenarios"]


def _ranking_metrics(
    samples: list[dict[str, Any]],
    conclusions: list[dict[str, Any]],
    criteria: dict[str, Any],
    action_table: dict[str, Any],
) -> dict[str, Any]:
    overlaps: list[float] = []
    by_archetype: dict[str, list[float]] = {}
    by_expected_count: dict[str, list[float]] = {}
    for sample, conclusion in zip(samples, conclusions):
        evaluation = evaluate_profile(sample["profile"], criteria)
        reference = _reference_top3(sample, action_table, evaluation)
        produced = [row["action_id"] for row in conclusion["ranking"][:3]]
        if not reference:
            continue
        overlap = len(set(reference) & set(produced)) / len(reference)
        overlaps.append(overlap)
        by_archetype.setdefault(sample["archetype"], []).append(overlap)
        key = str(len(sample["expected"]["action_ids"]))
        by_expected_count.setdefault(key, []).append(overlap)
    return {
        "top3_overlap": round(sum(overlaps) / len(overlaps), 4) if overlaps else 0.0,
        "samples": len(overlaps),
        "by_archetype": {
            key: round(sum(values) / len(values), 4) for key, values in sorted(by_archetype.items())
        },
        "by_expected_action_count": {
            key: {
                "samples": len(values),
                "overlap": round(sum(values) / len(values), 4),
            }
            for key, values in sorted(by_expected_count.items(), key=lambda pair: int(pair[0]))
        },
    }


TRIALS = 20


def _jitter(action_id: str, trial: int, kind: str) -> float:
    """确定性的 ±20% 抖动系数（同一 id、同一轮次永远得到同一个数）。"""
    seed = zlib.crc32(f"{action_id}|{trial}|{kind}".encode("utf-8"))
    return 0.8 + 0.4 * (seed % 1000) / 1000


def _ranking_stability(
    samples: list[dict[str, Any]],
    conclusions: list[dict[str, Any]],
    knowledge: Any,
) -> dict[str, Any]:
    """排序稳定性：成本与收益各扰动 ±20% 时，Top-3 有多少次换人。

    这是"同一个企业换个参数假设，排序会不会翻"的稳定性，
    与 T043 的"与参考顺序是否一致"是两件事，两个都报。
    """
    actions = knowledge.pathways.get("actions") or {}
    bases = knowledge.benefit_bases
    flips = 0
    total = 0
    for sample, conclusion in zip(samples, conclusions):
        produced = [row["action_id"] for row in conclusion["ranking"][:3]]
        if len(produced) < 3:
            continue
        total += 1
        # 每个改造项各自独立抖动 ±20%（统一扰动不改变相对顺序，测不出稳定性）；
        # 抖动系数用 crc32 从 id 与轮次推出，保证可复算。
        for trial in range(TRIALS):
            perturbed = []
            for row in conclusion["ranking"]:
                action = actions.get(row["action_id"])
                if action is None:
                    continue
                benefit = sum(
                    bases.get(str(indicator), 0.0) * elasticity["low"] * _jitter(row["action_id"], trial, "b")
                    for indicator, elasticity in (action.get("elasticity") or {}).items()
                )
                cost = action["cost_range"][1] * _jitter(row["action_id"], trial, "c")
                perturbed.append((-(benefit / cost), row["action_id"]))
            perturbed.sort()
            if [action_id for _, action_id in perturbed[:3]] != produced:
                flips += 1
    return {
        "flip_rate": round(flips / (total * TRIALS), 4) if total else 0.0,
        "samples": total,
        "trials": TRIALS,
        "note": f"每个改造项的成本与收益各自独立抖动 ±20%（{TRIALS} 轮，系数由 crc32 推出），Top-3 换人比例",
    }


def _antipattern_metrics(
    samples: list[dict[str, Any]], conclusions: list[dict[str, Any]]
) -> dict[str, Any]:
    tp = fn = fp = 0
    predicted_positive = 0
    for sample, conclusion in zip(samples, conclusions):
        expected = set(sample["expected"]["antipatterns"])
        predicted = set(conclusion["antipatterns"])
        predicted_positive += len(predicted)
        for pattern in expected:
            if pattern in predicted:
                tp += 1
            else:
                fn += 1
        fp += len(predicted - expected)
    detection = tp / (tp + fn) if (tp + fn) else 0.0
    false_positive = fp / predicted_positive if predicted_positive else 0.0
    return {
        "detection_rate": round(detection, 4),
        "false_positive_rate": round(false_positive, 4),
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "predicted_positive": predicted_positive,
    }


def _level_metrics(
    samples: list[dict[str, Any]],
    conclusions: list[dict[str, Any]],
    criteria: dict[str, Any],
) -> dict[str, Any]:
    """等级判定与官方口径（含约束性场景要求）的一致率。

    参考值就是官方四级门槛的判定结果，因此这一项衡量的是
    "去掉某条要求后，结论会不会偏离官方口径"，不是准确率宣称。
    """
    same = 0
    for sample, conclusion in zip(samples, conclusions):
        official = evaluate_profile(sample["profile"], criteria)
        if conclusion["level"] == official["level"]:
            same += 1
    return {
        "agreement": round(same / len(samples), 4) if samples else 0.0,
        "samples": len(samples),
    }


def _evidence_metrics(conclusions: list[dict[str, Any]]) -> dict[str, Any]:
    """证据链完整率与命中项准确率。

    - 证据链完整率：每条诊断结论都挂了官方原文引文与出处；
    - 命中项准确率：诊断点名的采集项，确实是得分不足一半的弱项。
    """
    total = 0
    with_refs = 0
    hit_items = 0
    hit_items_weak = 0
    for conclusion in conclusions:
        for entry in conclusion["diagnosis"]:
            total += 1
            if entry["evidence_refs"]:
                with_refs += 1
            for item_id in entry["hit_items"]:
                hit_items += 1
                if item_id in entry.get("_weak_items", []):
                    hit_items_weak += 1
    return {
        "evidence_complete_rate": round(with_refs / total, 4) if total else 0.0,
        "hit_item_precision": round(hit_items_weak / hit_items, 4) if hit_items else 0.0,
        "conclusions": total,
    }


def _roi_metrics(
    samples: list[dict[str, Any]],
    conclusions: list[dict[str, Any]],
    knowledge: Any,
) -> dict[str, Any]:
    """ROI 测算偏差：实现一致性 + 弹性口径切换偏差（真实偏差需真实企业样本）。"""
    elasticity_path = ROOT / "data" / "knowledge" / "elasticity.json"
    case_backed = {}
    if elasticity_path.exists():
        for row in json.loads(elasticity_path.read_text(encoding="utf-8")):
            if row.get("low") is None or row.get("high") is None:
                continue
            case_backed[str(row["item"])] = row

    bases = knowledge.benefit_bases
    max_impl_gap = 0.0
    switch_gaps: list[float] = []
    switch_examples: list[dict[str, Any]] = []
    switched = 0
    for sample, conclusion in zip(samples, conclusions):
        actions = knowledge.pathways.get("actions") or {}
        for row in conclusion["ranking"]:
            action = actions.get(row["action_id"])
            if action is None:
                continue
            engine_low = row["roi_low"]
            # 独立复算：最小收益 ÷ 最大成本
            benefit = sum(
                bases.get(str(indicator), 0.0) * elasticity["low"]
                for indicator, elasticity in (action.get("elasticity") or {}).items()
            )
            recomputed = benefit / action["cost_range"][1]
            if engine_low:
                max_impl_gap = max(max_impl_gap, abs(recomputed - engine_low) / engine_low)

            # 换成有公开案例支撑的弹性区间再看偏差
            if case_backed:
                switch_low = 0.0
                used = False
                for indicator in (action.get("elasticity") or {}):
                    reference = case_backed.get(str(indicator))
                    if reference is None:
                        switch_low = 0.0
                        used = False
                        break
                    switch_low += bases.get(str(indicator), 0.0) * reference["low"]
                    used = True
                if used:
                    switched += 1
                    # ROI 是比值：参考规模下的收益 ÷ 参考规模下的成本，与引擎口径一致
                    switch_roi = switch_low / action["cost_range"][1]
                    if engine_low:
                        gap = abs(switch_roi - engine_low) / engine_low
                        switch_gaps.append(gap)
                        switch_examples.append(
                            {
                                "action_id": row["action_id"],
                                "engine_roi_low": round(engine_low, 4),
                                "case_backed_roi_low": round(switch_roi, 4),
                            }
                        )

    switch_gaps.sort()
    median = switch_gaps[len(switch_gaps) // 2] if switch_gaps else 0.0
    examples = sorted(switch_examples, key=lambda row: -row["engine_roi_low"])[:3]
    return {
        "implementation_max_gap": round(max_impl_gap, 6),
        "elasticity_switch_median_gap": round(median, 4),
        "elasticity_switch_max_gap": round(switch_gaps[-1], 4) if switch_gaps else 0.0,
        "elasticity_switch_samples": switched,
        "elasticity_switch_examples": examples,
        "true_deviation": None,
        "true_deviation_note": "合成样本没有真值，真实 ROI 偏差需 T038 真实企业样本",
    }


def _generalization_metrics(
    samples: list[dict[str, Any]],
    conclusions: list[dict[str, Any]],
    criteria: dict[str, Any],
) -> dict[str, Any]:
    """跨行业泛化：按行业分组算诊断 F1，最差行业相对总体的衰减。"""
    overall = _diagnosis_metrics(samples, conclusions, criteria)
    by_industry: dict[str, list[int]] = {}
    for index, sample in enumerate(samples):
        by_industry.setdefault(sample["industry"], []).append(index)
    per_industry = {}
    worst = None
    for industry, indexes in sorted(by_industry.items()):
        subset_samples = [samples[i] for i in indexes]
        subset_conclusions = [conclusions[i] for i in indexes]
        metrics = _diagnosis_metrics(subset_samples, subset_conclusions, criteria)
        per_industry[industry] = {
            "samples": len(indexes),
            "micro_f1": metrics["micro_f1"],
            "bottleneck_micro_f1": metrics["bottleneck_micro_f1"],
        }
        score = metrics["bottleneck_micro_f1"]
        if worst is None or score < worst[1]:
            worst = (industry, score)
    degradation = round(overall["bottleneck_micro_f1"] - worst[1], 4) if worst else 0.0
    return {
        "overall_bottleneck_f1": overall["bottleneck_micro_f1"],
        "worst_industry": worst[0] if worst else None,
        "worst_industry_f1": worst[1] if worst else 0.0,
        "degradation": degradation,
        "by_industry": per_industry,
    }


def compute_metrics(
    samples: list[dict[str, Any]],
    conclusions_by_system: dict[str, list[dict[str, Any]]],
    criteria: dict[str, Any],
    knowledge: Any,
) -> dict[str, Any]:
    """算全套指标。``conclusions_by_system`` 是"系统 → 每个样本一条结论"。"""
    action_table = knowledge.pathways.get("actions") or {}
    prepared = []
    for sample in samples:
        item = dict(sample)
        item["_criteria"] = criteria
        prepared.append(item)

    results: dict[str, Any] = {}
    for system, conclusions in conclusions_by_system.items():
        results[system] = {
            "T041_diagnosis_f1": _diagnosis_metrics(prepared, conclusions, criteria),
            "T042_path_hit_rate": _path_metrics(samples, conclusions),
            "T043_ranking_top3": _ranking_metrics(prepared, conclusions, criteria, action_table),
            "T044_antipattern": _antipattern_metrics(samples, conclusions),
            "T045_roi_deviation": _roi_metrics(samples, conclusions, knowledge),
            "T046_generalization": _generalization_metrics(prepared, conclusions, criteria),
            "level_agreement": _level_metrics(samples, conclusions, criteria),
            "evidence_quality": _evidence_metrics(conclusions),
            "ranking_stability": _ranking_stability(samples, conclusions, knowledge),
        }
    return results
