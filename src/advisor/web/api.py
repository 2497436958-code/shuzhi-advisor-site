"""最小 FastAPI 后端。

当前只把确定性判据层暴露为 API；诊断、归因路径、ROI 排序和反模式识别
仍按任务拆分推进，不把未完成的推理层伪装成实时计算结果。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

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

app = FastAPI(
    title="数改指导智能体",
    version="0.1.0",
    description="面向中小企业数字化改造的确定性评测与决策支持接口。",
)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "mode": "online",
        "criteria_loaded": True,
        "indicators": len(criteria["indicators"]),
        "scenarios": len(criteria["scenarios"]),
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
        evaluation = evaluate_profile(profile, criteria)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "profile": profile,
        "evaluation": evaluation,
        "level_judgement": [],
        "diagnosis": [],
        "pathway": [],
        "ranking": [],
        "do_not": [],
        "policy_notes": [],
        "policy_notes_status": "minimal_api",
        "roi_assumptions": {},
        "meta": {
            "mode": "realtime",
            "document": criteria.get("source", {}).get("document", ""),
            "engine": "advisor.scoring.engine",
            "reasoning_status": "pending",
        },
    }


@app.get("/api/scenario_evidence")
def get_scenario_evidence() -> dict[str, Any]:
    return {
        "available": bool(scenario_evidence),
        "judgments": scenario_evidence,
    }


# 该挂载放在 API 路由之后，用于本地联调静态前端。
app.mount("/", StaticFiles(directory=ROOT, html=True), name="static")
