"""四类知识库与归因路径表的加载。

数据来源与口径：

- ``data/knowledge/policy.json``     政策库（30 份，含文号、发布方、日期、链接、关键条款）
- ``data/knowledge/cases.json``      案例库（259 条公开案例，逐条带原文出处）
- ``data/knowledge/papers.json``     论文库（文献 + 检索入口）
- ``data/knowledge/patents.json``    专利库（官方大类口径）
- ``data/knowledge/elasticity.json`` 成效弹性区间（采集项 12—15）
- ``data/pathways.json``             改造项参数（从 ``precomputed/*.json`` 反解，
  口径与还原方法见 ``docs/pathway_params_provenance.md``）
- ``data/pathway_content.json``       改造项措辞（症状、根因、依据、置信度），
  由 ``scripts/extract_pathway_content.py`` 反解

搬运与校验记录见 ``docs/knowledge_port.md``。

设计约束：文件缺失时返回空集合，由上层显式披露降级状态，
**不允许因为文件缺失就编造证据**。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"
PATHWAYS_PATH = DATA_DIR / "pathways.json"
PATHWAY_CONTENT_PATH = DATA_DIR / "pathway_content.json"


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


@dataclass(frozen=True)
class Knowledge:
    """一次运行内加载好的知识库快照。"""

    pathways: dict[str, Any]
    pathway_content: dict[str, Any]
    policy: list[dict[str, Any]]
    cases: list[dict[str, Any]]
    papers: list[dict[str, Any]]
    patents: dict[str, Any]
    elasticity: list[dict[str, Any]]

    @property
    def path_table(self) -> dict[str, Any]:
        return self.pathways.get("paths") or {}

    @property
    def benefit_bases(self) -> dict[str, float]:
        return self.pathways.get("benefit_bases") or {}

    @property
    def content(self) -> dict[str, Any]:
        """改造项措辞内容。"""
        return self.pathway_content

    def case_by_id(self) -> dict[str, dict[str, Any]]:
        return {case["id"]: case for case in self.cases if case.get("id")}

    def cases_for_scenario(self, scenario_id: str) -> list[dict[str, Any]]:
        """取目标场景命中的案例（确定性：按案例 id 升序）。"""
        matched = []
        for case in self.cases:
            for action in case.get("actions") or []:
                if action.get("target_scenario") == scenario_id:
                    matched.append(case)
                    break
        return sorted(matched, key=lambda case: case.get("id", ""))

    def papers_literature(self) -> list[dict[str, Any]]:
        """文献条目（检索入口不算文献）。"""
        return [paper for paper in self.papers if paper.get("type") != "检索入口"]

    def status(self) -> dict[str, Any]:
        return {
            "paths": len(self.path_table),
            "path_variants": len(self.pathway_content.get("variants") or {}),
            "policy": len(self.policy),
            "cases": len(self.cases),
            "cases_synthetic": sum(
                1 for case in self.cases if (case.get("extracted") or {}).get("synthetic")
            ),
            "papers": len(self.papers_literature()),
            "paper_entries": len(self.papers),
            "patent_categories": len(self.patents.get("categories") or []),
            "elasticity_items": len(self.elasticity),
        }


def load_knowledge() -> Knowledge:
    return Knowledge(
        pathways=_read_json(PATHWAYS_PATH, {}),
        pathway_content=_read_json(PATHWAY_CONTENT_PATH, {}),
        policy=_read_json(KNOWLEDGE_DIR / "policy.json", []),
        cases=_read_json(KNOWLEDGE_DIR / "cases.json", []),
        papers=_read_json(KNOWLEDGE_DIR / "papers.json", []),
        patents=_read_json(KNOWLEDGE_DIR / "patents.json", {}),
        elasticity=_read_json(KNOWLEDGE_DIR / "elasticity.json", []),
    )
