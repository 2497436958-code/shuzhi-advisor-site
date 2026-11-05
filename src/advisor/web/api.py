"""FastAPI 后端。

暴露判据层 + 推理层：现场填写的画像可以实时拿到四段式结果
（诊断 → 路径 → 排序与不建议做 → 政策注记）。

后端不可用时前端自动回退到 ``precomputed/`` 的预计算结果（见 ``app.js``）。

算分、定级、ROI 全部由确定性代码完成，模型不参与计算。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from advisor.knowledge.search import (
    search_cases,
    search_papers,
    search_patents,
    search_policy,
)
from advisor.reasoning.knowledge import load_knowledge
from advisor.reasoning.pipeline import build_result
from advisor.scoring.engine import evaluate_profile, load_criteria

ROOT = Path(__file__).resolve().parents[3]
CRITERIA_PATH = ROOT / "precomputed/criteria.json"
FIXTURES_PATH = ROOT / "precomputed/fixtures.json"
SCENARIO_EVIDENCE_PATH = ROOT / "precomputed/scenario_judgments.json"


class EvaluationProfile(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = "未命名企业"
    provenance: str = "用户现场填写"
    answers: dict[str, list[str]] = Field(default_factory=dict)
    scenario_levels: dict[str, int] = Field(default_factory=dict)
    revenue_wan: float | None = None
    digital_spend_wan: float | None = None
    energy_wan: float | None = None
    headcount: float | None = None
    cost_wan: float | None = None
    province: str = ""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"数据文件不存在：{path.name}") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"数据文件解析失败：{path.name}") from exc


criteria = load_criteria(CRITERIA_PATH)
fixtures_payload = _read_json(FIXTURES_PATH)
scenario_evidence = _read_json(SCENARIO_EVIDENCE_PATH)
knowledge = load_knowledge()


def cors_origins() -> list[str]:
    """允许跨域访问的前端来源。

    默认空（不同源不开放）：前后端同源部署时不需要 CORS。
    前后端分开部署时，用环境变量 ``ADVISOR_CORS_ORIGINS`` 指定，
    多个来源用逗号分隔，例如 ``https://example.github.io``。
    """
    raw = os.environ.get("ADVISOR_CORS_ORIGINS", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


class PublicStatic(StaticFiles):
    """只公开站��需要的静态文件。

    仓库根目录里还有源码、脚本、测试与 ``.git``，整个挂出去等于把
    工程结构和数据加工逻辑一并公开，所以这里用白名单限制可访问路径。
    """

    ALLOWED_FILES = {"index.html", "app.js", "styles.css"}
    ALLOWED_DIRS = {"precomputed", "data", "official"}

    async def get_response(self, path: str, scope: Any):
        relative = path.lstrip("/")
        head = relative.split("/", 1)[0]
        # 根路径在 Starlette 里会变成 "."，两种写法都放行（交给 StaticFiles 找 index.html）
        if relative in self.ALLOWED_FILES or head in self.ALLOWED_DIRS or relative in ("", "."):
            return await super().get_response(path, scope)
        raise HTTPException(status_code=404, detail="Not Found")


def create_app(cors: list[str] | None = None) -> FastAPI:
    """建应用。``cors`` 为空表示不同源不开放。"""
    application = FastAPI(
        title="数改指导智能体",
        version="0.2.0",
        description="面向中小企业数字化改造的确定性评测与决策支持接口。",
    )
    origins = cors if cors is not None else cors_origins()
    if origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Accept", "Content-Type"],
        )
    return application


app = create_app()


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "mode": "online",
        "criteria_loaded": True,
        "indicators": len(criteria["indicators"]),
        "scenarios": len(criteria["scenarios"]),
        "reasoning": "ready",
        "knowledge": knowledge.status(),
    }


@app.get("/api/criteria")
def get_criteria() -> dict[str, Any]:
    return criteria


@app.get("/api/fixtures")
def get_fixtures() -> dict[str, Any]:
    return fixtures_payload


@app.get("/api/fixtures/{fixture_id}")
def get_fixture(fixture_id: str) -> dict[str, Any]:
    fixtures = fixtures_payload.get("fixtures", [])
    fixture = next(
        (item for item in fixtures if item.get("name") == fixture_id),
        None,
    )
    if fixture is None:
        raise HTTPException(status_code=404, detail=f"未找到示例企业：{fixture_id}")
    return _read_json(ROOT / "precomputed" / fixture_id)


@app.post("/api/evaluate")
def evaluate(request: EvaluationProfile) -> dict[str, Any]:
    profile = request.model_dump()
    if not profile["answers"]:
        raise HTTPException(status_code=422, detail="缺少 15 个采集项答案")
    if not profile["scenario_levels"]:
        raise HTTPException(status_code=422, detail="缺少 16 个场景等级")

    try:
        return build_result(profile, criteria, knowledge)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/scenario_evidence")
def get_scenario_evidence() -> dict[str, Any]:
    return {
        "available": bool(scenario_evidence),
        "judgments": scenario_evidence,
    }


@app.get("/api/knowledge/policy")
def get_knowledge_policy(
    q: str = "", role: str = "", limit: int = 50, offset: int = 0
) -> dict[str, Any]:
    """政策库检索：按关键词与用途（role）过滤。"""
    return search_policy(knowledge.policy, q=q, role=role, limit=limit, offset=offset)


@app.get("/api/knowledge/cases")
def get_knowledge_cases(
    q: str = "",
    industry: str = "",
    source_type: str = "",
    scenario: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """案例库检索：按关键词、行业、来源类型与目标场景过滤。"""
    return search_cases(
        knowledge.cases,
        q=q,
        industry=industry,
        source_type=source_type,
        scenario=scenario,
        limit=limit,
        offset=offset,
    )


@app.get("/api/knowledge/papers")
def get_knowledge_papers(
    q: str = "", kind: str = "", limit: int = 50, offset: int = 0
) -> dict[str, Any]:
    """论文库检索：按关键词与类型（方法／成效证据／检索入口）过滤。"""
    return search_papers(knowledge.papers, q=q, kind=kind, limit=limit, offset=offset)


@app.get("/api/knowledge/patents")
def get_knowledge_patents(q: str = "", limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """专利库检索：按关键词过滤官方大类口径，附带检索入口与计数规则。"""
    result = search_patents(knowledge.patents, q=q, limit=limit, offset=offset)
    result["meta"] = knowledge.patents.get("meta", {})
    result["supply_side"] = knowledge.patents.get("supply_side_cross_reference", {})
    return result


@app.get("/api/evaluation/report")
def get_evaluation_report() -> dict[str, Any]:
    """评测报告（合成层）。真实层为空时如实返回 count=0。"""
    path = ROOT / "data" / "evaluation" / "report.json"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="评测报告尚未生成，请先运行 scripts/build_evaluation_report.py",
        )
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/knowledge/stats")
def get_knowledge_stats() -> dict[str, Any]:
    """四类知识库的数量与口径。"""
    status = knowledge.status()
    return {
        "status": status,
        "sources": {
            "policy": {
                "count": len(knowledge.policy),
                "file": "data/knowledge/policy.json",
                "fields": "文号、发布方、发布日期、链接、关键条款、用途",
            },
            "cases": {
                "count": len(knowledge.cases),
                "synthetic": status["cases_synthetic"],
                "file": "data/knowledge/cases.json",
                "fields": "行业、症状、改造动作、目标场景、原文出处",
            },
            "papers": {
                "count": status["papers"],
                "entries": status["paper_entries"],
                "file": "data/knowledge/papers.json",
                "fields": "文献条目与检索入口分开计数",
            },
            "patents": {
                "count": status["patent_categories"],
                "file": "data/knowledge/patents.json",
                "fields": "官方大类口径与应用场景映射",
            },
            "elasticity": {
                "count": status["elasticity_items"],
                "file": "data/knowledge/elasticity.json",
                "fields": "成效采集项 12—15 的弹性区间与是否被公开案例支撑",
            },
            "paths": {
                "count": status["paths"],
                "variants": status["path_variants"],
                "file": "data/pathways.json / data/pathway_content.json",
                "fields": "改造项投入区间、成效弹性、前置依赖",
            },
        },
        "filters": {
            "policy_roles": sorted({policy.get("role", "") for policy in knowledge.policy if policy.get("role")}),
            "case_industries": sorted({case.get("industry", "") for case in knowledge.cases if case.get("industry")}),
            "case_source_types": sorted({case.get("source_type", "") for case in knowledge.cases if case.get("source_type")}),
            "paper_types": sorted({paper.get("type", "") for paper in knowledge.papers if paper.get("type")}),
        },
        "note": "知识库条目均为公开来源，逐条带原文出处；数字仅用于排序，不作为结论数。",
    }


# 该挂载放在 API 路由之后，用于本地联调静态前端；只公开白名单里的路径。
app.mount("/", PublicStatic(directory=ROOT, html=True), name="static")
