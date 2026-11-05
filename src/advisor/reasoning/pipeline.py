"""推理流水线：画像 → 评测 → 诊断 → 路径 → 排序 → 不建议做 → 政策注记。

输出结构与站点已发布的预计算结果（``precomputed/*.json`` 的 ``result``）
保持一致，前端同一套渲染代码同时支持实时结果与离线预计算结果。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..scoring.engine import evaluate_profile
from .antipatterns import detect_antipatterns
from .diagnosis import build_diagnosis
from .knowledge import Knowledge, load_knowledge
from .pathway import build_pathway
from .ranking import benefit_bases, build_ranking, scale_factor

ENGINE_NAME = "advisor.scoring.engine / advisor.reasoning"


def _unmet_reasons(evaluation: dict[str, Any]) -> dict[int, list[str]]:
    """从引擎输出的 unmet 列表里取出每个等级未达标的原因（不重复实现门槛判定）。"""
    reasons: dict[int, list[str]] = {}
    for line in evaluation.get("unmet") or []:
        head, _, tail = line.partition("：")
        level_text = head.split(" ")[0]
        if not level_text.isdigit():
            continue
        reasons[int(level_text)] = [part for part in tail.split("；") if part]
    return reasons


def _level_judgement(evaluation: dict[str, Any], criteria: dict[str, Any]) -> list[dict[str, Any]]:
    reasons = _unmet_reasons(evaluation)
    achieved = evaluation.get("level")
    rows = []
    for threshold in criteria["levels"]:
        satisfied = achieved is not None and threshold["level"] <= achieved
        rows.append(
            {
                "level": threshold["level"],
                "name": threshold["name"],
                "min_score": threshold["min_score"],
                "min_scenarios": threshold["min_scenarios"],
                "min_constraint_scenarios": threshold["min_constraint_scenarios"],
                "satisfied": satisfied,
                "note": "得分与场景数均达标"
                if satisfied
                else "；".join(reasons.get(threshold["level"], ["未达标"])),
            }
        )
    return rows


def _scenario_results(
    evaluation: dict[str, Any], criteria: dict[str, Any], submitted: bool
) -> list[dict[str, Any]]:
    levels = evaluation.get("scenario_levels") or {}
    rows = []
    for scenario in criteria["scenarios"]:
        level = levels.get(scenario["id"], 1)
        next_level = level + 1 if level < 4 else None
        rows.append(
            {
                "id": scenario["id"],
                "name": scenario["name"],
                "primary": scenario["primary"],
                "constraint": bool(scenario.get("constraint")),
                "level": level,
                "judgment": {
                    "scenario_id": scenario["id"],
                    "level": level,
                    "quote": scenario["levels"].get(str(level), ""),
                    "reason": "企业自评等级（用户提交）"
                    if submitted
                    else "未提交场景等级，按确定性规则基线取一级（未调用模型）",
                    "citation_ok": True,
                    "used_fallback": not submitted,
                    "source": "submitted" if submitted else "rule_baseline",
                },
                "level_desc": scenario["levels"].get(str(level), ""),
                "next_level": next_level,
                "next_level_desc": scenario["levels"].get(str(next_level), "") if next_level else "",
            }
        )
    return rows


def _policy_notes(knowledge: Knowledge) -> list[dict[str, Any]]:
    """政策注记段：只列与本次结论直接相关的文件。"""
    notes = []
    for policy in knowledge.policy:
        used_where = policy.get("used_where", "")
        if "政策注记段" not in used_where and policy.get("role") != "判据底座":
            continue
        notes.append(
            {
                "doc": f"{policy.get('doc_no', '')}｜{policy.get('title', '')}",
                "url": policy.get("url", ""),
                "window": f"{policy.get('publish_date', '')} 发布".strip(),
                "role": policy.get("role", ""),
                "used_where": used_where,
                "issuer": policy.get("issuer", ""),
                "key_provisions": list(policy.get("key_provisions") or []),
            }
        )
    return notes


def build_result(
    profile: dict[str, Any],
    criteria: dict[str, Any],
    knowledge: Knowledge | None = None,
) -> dict[str, Any]:
    """把一份画像算成完整四段式结果。"""
    knowledge = knowledge or load_knowledge()
    evaluation = evaluate_profile(profile, criteria)

    hits = detect_antipatterns(evaluation, criteria)
    diagnosis = build_diagnosis(evaluation, criteria, hits, knowledge)

    content = knowledge.content
    actions_table = knowledge.pathways.get("actions") or {}
    reference_bases = knowledge.benefit_bases
    scale = scale_factor(profile)
    bases = benefit_bases(reference_bases, scale)

    steps, selected = build_pathway(
        profile, evaluation, criteria, actions_table, content, bases, knowledge
    )
    ranking, assumptions = build_ranking(
        profile, evaluation, criteria, selected, reference_bases, content
    )

    submitted = bool(profile.get("scenario_levels"))
    scenario_results = _scenario_results(evaluation, criteria, submitted)
    notes = _policy_notes(knowledge)

    return {
        "profile": {
            "name": profile.get("name", "未命名企业"),
            "provenance": profile.get("provenance", "用户现场填写"),
        },
        "evaluation": evaluation,
        "level_judgement": _level_judgement(evaluation, criteria),
        "item_results": evaluation["item_results"],
        "scenario_results": scenario_results,
        "diagnosis": diagnosis,
        "pathway": steps,
        "ranking": ranking,
        "do_not": [
            {
                **hit.to_dict(),
                "case_ref": diagnosis[index].get("case_ref"),
                "evidence_refs": diagnosis[index]["evidence_refs"],
            }
            for index, hit in enumerate(hits)
        ],
        "scenario_evidence": {
            "available": True,
            "model_judgments_available": False,
            "rule_baseline_available": True,
            "source": criteria.get("source", {}).get("scenarios", ""),
            "levels_source": "submitted" if submitted else "rule_baseline",
            "items": [
                {
                    "scenario_id": row["id"],
                    "level": row["level"],
                    "quote": row["judgment"]["quote"],
                    "source": row["judgment"]["source"],
                    "citation_ok": row["judgment"]["citation_ok"],
                }
                for row in scenario_results
            ],
            "note": "场景等级引文直接取自官方附件（二）转写文本，未调用模型。",
        },
        "policy_notes": notes,
        "policy_notes_status": {
            "status": "已接入" if notes else "待接入",
            "reason": "政策库（data/knowledge/policy.json）已就绪"
            if notes
            else "政策库尚未就绪，本段留空位。",
            "planned": "只列与本次结论直接相关的文件（判据基准、画像口径、资金、验收、监管、地方口径）",
        },
        "roi_assumptions": assumptions,
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mode": "realtime",
            "criteria_source": criteria.get("source", {}).get("indicators", ""),
            "scenario_source": criteria.get("source", {}).get("scenarios", ""),
            "document": criteria.get("source", {}).get("document", ""),
            "engine": ENGINE_NAME,
            "knowledge": knowledge.status(),
        },
    }
