"""四组对照与四组消融。

每组只关掉一项能力，关掉什么写在 ``capabilities`` 里，报告直接引用。

对照（主控文档 T039）

============  =====================================================
组名          具备什么 / 不具备什么
============  =====================================================
纯 RAG        只检索知识库并给出片段，不算分、不定级、不诊断、不出路径
纯规则        只用官方判据层：算分、定级、四类瓶颈诊断、反模式；
              不碰知识库，因此没有案例出处、没有归因路径、没有排序
RAG+计算器   判据层 + 知识库检索（案例出处可回查），但不做闭环推理：
              没有归因路径、没有投入产出排序
完整闭环      全部能力：判据层 + 知识库 + 诊断 + 归因路径 + ROI 排序 + 证据链
============  =====================================================

消融（主控文档 T040）

============  =====================================================
组名          关掉了什么
============  =====================================================
去归因        关掉归因路径与排序（诊断仍在，所以诊断指标不变、路径指标归零）
去约束场景    等级判定不再要求约束性场景数（官方附件（二）的"约束性场景"约束被拿掉）
去反模式      不做 AP1—AP4 检测（诊断里的反模式条目与"不建议做"清单随之消失）
去判据锚定    结论不再挂到官方采集项与场景上（去掉命中项、命中场景与证据链）
============  =====================================================
"""

from __future__ import annotations

from typing import Any

from ..reasoning.antipatterns import detect_antipatterns
from ..reasoning.diagnosis import build_diagnosis
from ..reasoning.pathway import build_pathway
from ..reasoning.ranking import benefit_bases, build_ranking, scale_factor
from ..scoring.engine import evaluate_profile

CONTROL_SYSTEMS = ["control_rag", "control_rules", "control_rag_calculator", "control_full"]
ABLATION_SYSTEMS = [
    "ablation_no_attribution",
    "ablation_no_constraint",
    "ablation_no_antipattern",
    "ablation_no_anchor",
]
SYSTEMS = CONTROL_SYSTEMS + ABLATION_SYSTEMS

CAPABILITIES = {
    "control_rag": {"scoring": False, "knowledge": True, "diagnosis": False, "pathway": False, "ranking": False, "antipattern": False, "constraint": False, "anchor": False},
    "control_rules": {"scoring": True, "knowledge": False, "diagnosis": True, "pathway": False, "ranking": False, "antipattern": True, "constraint": True, "anchor": True},
    "control_rag_calculator": {"scoring": True, "knowledge": True, "diagnosis": True, "pathway": False, "ranking": False, "antipattern": True, "constraint": True, "anchor": True},
    "control_full": {"scoring": True, "knowledge": True, "diagnosis": True, "pathway": True, "ranking": True, "antipattern": True, "constraint": True, "anchor": True},
    "ablation_no_attribution": {"scoring": True, "knowledge": True, "diagnosis": True, "pathway": False, "ranking": False, "antipattern": True, "constraint": True, "anchor": True},
    "ablation_no_constraint": {"scoring": True, "knowledge": True, "diagnosis": True, "pathway": True, "ranking": True, "antipattern": True, "constraint": False, "anchor": True},
    "ablation_no_antipattern": {"scoring": True, "knowledge": True, "diagnosis": True, "pathway": True, "ranking": True, "antipattern": False, "constraint": True, "anchor": True},
    "ablation_no_anchor": {"scoring": True, "knowledge": True, "diagnosis": True, "pathway": True, "ranking": True, "antipattern": True, "constraint": True, "anchor": False},
}

SYSTEM_LABELS = {
    "control_rag": "纯 RAG（只检索）",
    "control_rules": "纯规则（只用判据层）",
    "control_rag_calculator": "RAG + 计算器",
    "control_full": "完整闭环",
    "ablation_no_attribution": "消融·去归因",
    "ablation_no_constraint": "消融·去约束场景",
    "ablation_no_antipattern": "消融·去反模式",
    "ablation_no_anchor": "消融·去判据锚定",
}


def _levels_without_constraint_scenarios(criteria: dict[str, Any]) -> list[dict[str, Any]]:
    """去掉"约束性场景数"这一条要求，其余门槛完全不动。"""
    return [
        dict(level, min_constraint_scenarios=0) for level in criteria["levels"]
    ]


def _retrieval_query(profile: dict[str, Any], criteria: dict[str, Any]) -> list[str]:
    """纯 RAG 基线的检索式：企业选中的官方选项文字 + 仍在一级的场景名。"""
    terms: list[str] = []
    indicators = {item["id"]: item for item in criteria["indicators"]}
    for item_id, selected in profile.get("answers", {}).items():
        indicator = indicators.get(int(item_id))
        if indicator is None:
            continue
        for option in selected:
            if option in ("无", "持平", "降低", "增加"):
                continue
            terms.append(option)
    levels = profile.get("scenario_levels") or {}
    for scenario in criteria["scenarios"]:
        if levels.get(scenario["id"], 1) <= 1:
            terms.append(scenario["name"])
    return terms


def _retrieve(profile: dict[str, Any], criteria: dict[str, Any], knowledge: Any, top_k: int = 5) -> list[dict[str, Any]]:
    """纯 RAG：按检索式命中案例条目，按命中词数排序。"""
    terms = _retrieval_query(profile, criteria)
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for case in knowledge.cases:
        haystack = " ".join(
            [
                case.get("title", ""),
                case.get("symptom", ""),
                " ".join(action.get("action", "") for action in case.get("actions") or []),
                case.get("collection", ""),
            ]
        )
        hits = sum(1 for term in terms if term and term in haystack)
        if hits:
            scored.append((hits, case.get("id", ""), case))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [
        {
            "id": case["id"],
            "title": case.get("title", ""),
            "hits": hits,
            "url": (case.get("evidence") or {}).get("url", ""),
        }
        for hits, _, case in scored[:top_k]
    ]


def build_conclusion(
    system: str,
    profile: dict[str, Any],
    criteria: dict[str, Any],
    knowledge: Any,
) -> dict[str, Any]:
    """跑一组（对照或消融），返回结构化结论。"""
    if system not in SYSTEMS:
        raise ValueError(f"未知的评测组：{system}")
    caps = CAPABILITIES[system]

    conclusion: dict[str, Any] = {
        "system": system,
        "label": SYSTEM_LABELS[system],
        "capabilities": caps,
        "total_score": None,
        "level": None,
        "level_name": None,
        "diagnosis": [],
        "antipatterns": [],
        "pathway": [],
        "ranking": [],
        "evidence_refs": 0,
        "retrieved": [],
    }

    if not caps["scoring"]:
        # 纯 RAG：只有检索，没有算分与结构化结论
        conclusion["retrieved"] = _retrieve(profile, criteria, knowledge)
        return conclusion

    effective_criteria = criteria
    effective_levels = (
        _levels_without_constraint_scenarios(criteria)
        if not caps["constraint"]
        else None
    )
    evaluation = evaluate_profile(profile, effective_criteria, levels=effective_levels)
    conclusion["total_score"] = evaluation["total_score"]
    conclusion["level"] = evaluation["level"]
    conclusion["level_name"] = evaluation["level_name"]

    hits = detect_antipatterns(evaluation, effective_criteria) if caps["antipattern"] else []
    conclusion["antipatterns"] = [hit.pattern_id for hit in hits]

    if caps["diagnosis"]:
        diagnosis = build_diagnosis(evaluation, effective_criteria, hits, knowledge)
        weak_items = {
            item["id"] for item in evaluation["item_results"] if item["score"] < 50
        }
        conclusion["diagnosis"] = [
            {
                "bottleneck_type": entry["bottleneck_type"],
                "hit_items": list(entry["hit_items"]),
                "hit_scenarios": list(entry["hit_scenarios"]),
                "evidence_refs": len(entry["evidence_refs"]),
                "_weak_items": sorted(weak_items),
            }
            for entry in diagnosis
        ]

    if caps["pathway"]:
        scale = scale_factor(profile)
        bases = benefit_bases(knowledge.benefit_bases, scale)
        steps, selected = build_pathway(
            profile,
            evaluation,
            effective_criteria,
            knowledge.pathways.get("actions") or {},
            knowledge.content,
            bases,
            knowledge,
        )
        conclusion["pathway"] = [
            {
                "step": step["step"],
                "action_id": action["action_id"],
                "target_scenario": step["target_scenario"],
                "path_ref": step["path_ref"],
                "cost_range": step["cost_range"],
            }
            for step, action in zip(steps, selected)
        ]
        rows, assumptions = build_ranking(
            profile,
            evaluation,
            effective_criteria,
            selected,
            knowledge.benefit_bases,
            knowledge.content,
        )
        conclusion["ranking"] = [
            {
                "rank": row["rank"],
                "action_id": row["action_id"],
                "name": row["name"],
                "target_scenario": row["target_scenario"],
                "roi_low": row["roi_low"],
                "roi_high": row["roi_high"],
                "level_gain": row["level_gain"],
            }
            for row in rows
        ]
        conclusion["roi_assumptions"] = assumptions

    if caps["knowledge"]:
        conclusion["retrieved"] = _retrieve(profile, criteria, knowledge)

    if not caps["anchor"]:
        # 去判据锚定：结论不再挂到官方采集项与场景上，证据链一并去掉
        for entry in conclusion["diagnosis"]:
            entry["hit_items"] = []
            entry["hit_scenarios"] = []
            entry["evidence_refs"] = 0
        for step in conclusion["pathway"]:
            step["target_scenario"] = ""
        for row in conclusion["ranking"]:
            row["target_scenario"] = ""

    conclusion["evidence_refs"] = sum(
        entry["evidence_refs"] for entry in conclusion["diagnosis"]
    )
    return conclusion
