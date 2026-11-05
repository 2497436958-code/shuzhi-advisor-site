"""证据链构造与强制规则。

规则（主控文档 T030）：**没有证据的结论不允许出现在结果里**。
所有诊断、路径、排序、不建议做条目都必须带 ``evidence_refs``；
由 ``ensure_evidence`` 兜底，缺证据直接抛错，不做静默丢弃。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

OFFICIAL_URL = "official/中小企业数字化水平评测指标（2024年版）.pdf"
OFFICIAL_DOC = "工信厅企业〔2024〕56 号"
INDICATOR_TABLE = f"{OFFICIAL_DOC} 附件（一）数字化基础、管理及成效评测表"
SCENARIO_TABLE = f"{OFFICIAL_DOC} 附件（二）数字化经营应用场景等级判定表"
LEVEL_RULE_DOC = f"{OFFICIAL_DOC} 附件（二）二、判定方法（得分与场景数须同时满足）"
WEIGHT_DOC = f"{OFFICIAL_DOC} 附件（一）权重体系（一级指标权重 50%）"
CRITERIA_NOTE = "非官方口径：评审可按此判据复核或质疑，改判据不动判据层"


class MissingEvidenceError(ValueError):
    """结论缺少证据链时抛出。"""


@dataclass(frozen=True)
class EvidenceRef:
    kind: str
    ref: str
    title: str
    quote: str
    doc: str
    url: str
    note: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "ref": self.ref,
            "title": self.title,
            "quote": self.quote,
            "doc": self.doc,
            "url": self.url,
            "note": self.note,
        }


def indicator_ref(criteria: dict[str, Any], item_id: int, item_result: dict[str, Any]) -> EvidenceRef:
    """采集项证据：官方选项原文逐字引用 + 该项得分与权重。"""
    indicator = next(i for i in criteria["indicators"] if i["id"] == item_id)
    selected = item_result["selected"]
    quote = f"{indicator['title']} → {'、'.join(selected)}"
    weight = item_result["chain_weight"]
    note = (
        f"官方选项原文，逐字引用；该采集项得分 {round(item_result['score'])}/100，"
        f"三级权重连乘 {weight:.4f}（占总分 {weight * 100:.1f}%）"
    )
    return EvidenceRef(
        kind="采集项",
        ref=f"采集项 {item_id}",
        title=f"{indicator['primary']}/{indicator['secondary']}/{indicator['item']}",
        quote=quote,
        doc=f"{INDICATOR_TABLE} 第 {item_id} 行",
        url=OFFICIAL_URL,
        note=note,
    )


def scenario_ref(criteria: dict[str, Any], scenario_id: str, level: int) -> EvidenceRef:
    """场景证据：该等级对应的官方判定原文。"""
    scenario = next(s for s in criteria["scenarios"] if s["id"] == scenario_id)
    quote = scenario["levels"].get(str(level), "")
    label = f"{scenario['name']}（{'约束性场景' if scenario.get('constraint') else '指导性场景'}）"
    return EvidenceRef(
        kind="场景",
        ref=f"场景 {scenario_id}",
        title=f"{scenario['primary']}/{label}",
        quote=quote,
        doc=SCENARIO_TABLE,
        url=OFFICIAL_URL,
        note=f"当前自评等级：{level}",
    )


def criteria_ref(pattern_id: str, name: str, basis: str) -> EvidenceRef:
    """反模式判据证据。判据是本项目构造的，必须标明不是官方口径。"""
    return EvidenceRef(
        kind="判据",
        ref=f"本项目构造的判据 {pattern_id}",
        title=name,
        quote=basis,
        doc=(
            f"{OFFICIAL_DOC} 附件（一）采集项 2/3/4/5/11 与附件（二）场景等级判定（拼合而成）"
        ),
        url=OFFICIAL_URL,
        note=CRITERIA_NOTE,
    )


def case_ref(case: dict[str, Any]) -> EvidenceRef:
    """案例证据：只引用案例库里的原文出处。"""
    evidence = case.get("evidence") or {}
    return EvidenceRef(
        kind="案例",
        ref=f"案例 {case['id']}",
        title=case.get("title", ""),
        quote=evidence.get("quoted", "") or case.get("symptom", ""),
        doc=evidence.get("doc", ""),
        url=evidence.get("url", ""),
        note="案例库条目原文出处，可逐条回查",
    )


def policy_ref(policy: dict[str, Any]) -> EvidenceRef:
    return EvidenceRef(
        kind="政策",
        ref=policy.get("doc_no") or policy.get("id", ""),
        title=policy.get("title", ""),
        quote="；".join(policy.get("key_provisions") or [])[:400],
        doc=f"{policy.get('issuer', '')} {policy.get('publish_date', '')}".strip(),
        url=policy.get("url", ""),
        note=f"用途：{policy.get('used_where', '')}",
    )


def level_ref() -> EvidenceRef:
    return EvidenceRef(
        kind="等级门槛",
        ref="等级判定",
        title="四级门槛判定要求",
        quote="得分与场景数须同时满足（≥20/40/60/80 分，且场景数与约束性场景数达标）",
        doc=LEVEL_RULE_DOC,
        url=OFFICIAL_URL,
        note="官方附件（二）二、判定方法",
    )


def weight_ref(dimension: str, weight_percent: float) -> EvidenceRef:
    return EvidenceRef(
        kind="权重体系",
        ref="一级指标权重",
        title=f"{dimension}（一级指标权重 {weight_percent:g}%）",
        quote=f"{dimension}在一级指标权重体系中占 {weight_percent:g}%",
        doc=WEIGHT_DOC,
        url=OFFICIAL_URL,
        note="官方附件（一）权重体系",
    )


def ensure_evidence(conclusion: str, refs: Iterable[EvidenceRef]) -> list[dict[str, str]]:
    """证据链闸门：没有证据的结论不允许输出。"""
    materialized = [ref.to_dict() for ref in refs]
    if not materialized:
        raise MissingEvidenceError(f"结论缺少证据链，不得输出：{conclusion}")
    return materialized
