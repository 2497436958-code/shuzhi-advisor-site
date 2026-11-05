"""评测执行器：跑 8 个组、算 6 项指标、出报告。

输出：
- ``data/evaluation/report.json``（机器可读，页面与接口都从它出）
- ``data/evaluation/report.md``（人可读，含真实层/合成层分列）
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..reasoning.knowledge import load_knowledge
from ..scoring.engine import load_criteria
from .metrics import compute_metrics
from .variants import (
    ABLATION_SYSTEMS,
    CONTROL_SYSTEMS,
    SYSTEM_LABELS,
    build_conclusion,
)

ROOT = Path(__file__).resolve().parents[3]
SAMPLES_PATH = ROOT / "data" / "profiles" / "synthetic_60.json"
EVALUATION_DIR = ROOT / "data" / "evaluation"

# 每项指标的口径说明（人读报告与前端页面共用这一份）
METRIC_INFO = {
    "T041_diagnosis_f1": {
        "label": "诊断准确率 F1",
        "basis": "只看有区分度的瓶颈型（反模式型 + 场景断层），参考值是样本按构造应当出现的瓶颈类型",
    },
    "T042_path_hit_rate": {
        "label": "归因路径命中率",
        "basis": "仍在一级的场景所对应的改造项，有多少出现在系统的路径段里",
    },
    "T043_ranking_top3": {
        "label": "排序一致性 Top-3",
        "basis": "系统 Top-3 与独立算出的应先做顺序（先解锁一级约束性场景多者先做）的重合率",
    },
    "T044_antipattern_detection": {
        "label": "反模式检出率",
        "basis": "样本按构造应当命中的反模式，有多少被检出",
    },
    "T044_antipattern_false_positive": {
        "label": "反模式误报率",
        "basis": "检出的反模式里，有多少是样本没有的",
    },
    "T045_roi_deviation": {
        "label": "ROI 测算偏差",
        "basis": "相对真值的偏差；合成层无真值，只给实现一致性与弹性口径切换偏差",
    },
    "T046_generalization": {
        "label": "跨行业泛化衰减",
        "basis": "按行业分组的诊断 F1，最差行业相对总体的差",
    },
}

# 报告里必须写明的已知边界
REPORT_NOTES = [
    "本报告只覆盖合成层：合成样本能证明规则实现没有系统性偏差，不能证明业务结论正确。",
    "T043 的参考顺序是代理定义（先解锁一级约束性场景多者先做，再按可回收分数），"
    "主控文档未定义参考顺序，换一个定义数字会变；要拿到有意义的数需要人工标注顺序。",
    "路径表只覆盖 9 个场景，S02/S04/S05/S12—S15 无法用样本验证。",
    "真实层 0 家：本报告不含任何真实企业的评测结论，不得用合成层数字替代。",
    "当前 ROI 用的成效弹性是演示口径，没有公开案例支撑，只用于排序。",
]

# 主控文档给出的验收门槛
THRESHOLDS = {
    "T041_diagnosis_f1": {"metric": "diagnosis_f1", "op": ">=", "value": 0.80},
    "T042_path_hit_rate": {"metric": "hit_rate", "op": ">=", "value": 0.70},
    "T043_ranking_top3": {"metric": "top3_overlap", "op": ">=", "value": 0.70},
    "T044_antipattern_detection": {"metric": "detection_rate", "op": ">=", "value": 0.85},
    "T044_antipattern_false_positive": {"metric": "false_positive_rate", "op": "<=", "value": 0.15},
    "T045_roi_deviation": {"metric": "true_deviation", "op": "<=", "value": 0.20},
    "T046_generalization": {"metric": "degradation", "op": "<=", "value": 0.10},
}


def _metric_value(metrics: dict[str, Any], task: str) -> float | None:
    if task == "T041_diagnosis_f1":
        return metrics["T041_diagnosis_f1"]["bottleneck_micro_f1"]
    if task == "T042_path_hit_rate":
        return metrics["T042_path_hit_rate"]["hit_rate"]
    if task == "T043_ranking_top3":
        return metrics["T043_ranking_top3"]["top3_overlap"]
    if task == "T044_antipattern_detection":
        return metrics["T044_antipattern"]["detection_rate"]
    if task == "T044_antipattern_false_positive":
        return metrics["T044_antipattern"]["false_positive_rate"]
    if task == "T045_roi_deviation":
        return metrics["T045_roi_deviation"]["true_deviation"]
    if task == "T046_generalization":
        return metrics["T046_generalization"]["degradation"]
    return None


def run_evaluation(ranking_policy: str = "roi") -> dict[str, Any]:
    """跑完 8 个组，产出报告数据。

    ``ranking_policy`` 默认 ``roi``（现状口径）；其余取值只用于 T043 的口径对比。
    """
    dataset = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
    samples = dataset["samples"]
    criteria = load_criteria(ROOT / "precomputed" / "criteria.json")
    knowledge = load_knowledge()

    conclusions_by_system: dict[str, list[dict[str, Any]]] = {}
    for system in CONTROL_SYSTEMS + ABLATION_SYSTEMS:
        conclusions_by_system[system] = [
            build_conclusion(
                system, sample["profile"], criteria, knowledge, ranking_policy=ranking_policy
            )
            for sample in samples
        ]

    metrics = compute_metrics(samples, conclusions_by_system, criteria, knowledge)

    verdicts: dict[str, Any] = {}
    for task, rule in THRESHOLDS.items():
        value = _metric_value(metrics["control_full"], task)
        if value is None:
            verdicts[task] = {"value": None, "status": "不可测", "threshold": f"{rule['op']} {rule['value']}"}
            continue
        passed = value >= rule["value"] if rule["op"] == ">=" else value <= rule["value"]
        verdicts[task] = {
            "value": value,
            "status": "达标" if passed else "未达标",
            "threshold": f"{rule['op']} {rule['value']}",
        }

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ranking_policy": ranking_policy,
        "layers": {
            "synthetic": {
                "count": len(samples),
                "source": "data/profiles/synthetic_60.json",
                "composition": dataset["composition"],
                "note": "全部为合成样本（真实层 0 家）",
            },
            "real": {
                "count": 0,
                "source": None,
                "note": "真实企业样本未提供（T038），本报告不含真实层结论",
            },
        },
        "systems": {
            system: {
                "label": SYSTEM_LABELS[system],
                "kind": "control" if system in CONTROL_SYSTEMS else "ablation",
                "capabilities": conclusions_by_system[system][0]["capabilities"],
                "metrics": metrics[system],
            }
            for system in CONTROL_SYSTEMS + ABLATION_SYSTEMS
        },
        "thresholds": THRESHOLDS,
        "metric_info": METRIC_INFO,
        "verdicts": verdicts,
        "notes": REPORT_NOTES,
        "capability_labels": {
            "scoring": "算分定级",
            "knowledge": "知识库",
            "diagnosis": "诊断",
            "pathway": "归因路径",
            "ranking": "ROI 排序",
            "antipattern": "反模式",
            "constraint": "约束性场景要求",
            "anchor": "判据锚定",
        },
    }


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    add = lines.append

    add("# 评测报告")
    add("")
    add(f"生成时间：{report['generated_at']}")
    add("")
    add("> 本报告只覆盖**合成层**。真实企业样本尚未提供（T038），真实层结论为空，")
    add("> 不能用合成层的数字替代真实层。")
    add("")

    layers = report["layers"]
    add("## 一、样本层")
    add("")
    add("| 层 | 家数 | 来源 | 说明 |")
    add("|---|---|---|---|")
    for key, label in (("synthetic", "合成层"), ("real", "真实层")):
        layer = layers[key]
        add(f"| {label} | {layer['count']} | {layer['source'] or '—'} | {layer['note']} |")
    add("")
    composition = layers["synthetic"]["composition"]
    add("合成层构成：" + "、".join(
        f"{name} {count} 家" for name, count in composition.items() if name != "total"
    ) + "。")
    add("")

    add("## 二、四组对照")
    add("")
    add("| 组 | 算分定级 | 知识库 | 诊断 | 归因路径 | ROI 排序 | 反模式 | 证据链 |")
    add("|---|---|---|---|---|---|---|---|")
    for system in CONTROL_SYSTEMS:
        caps = report["systems"][system]["capabilities"]
        mark = lambda key: "✓" if caps[key] else "—"
        add(
            f"| {report['systems'][system]['label']} | {mark('scoring')} | {mark('knowledge')} | "
            f"{mark('diagnosis')} | {mark('pathway')} | {mark('ranking')} | "
            f"{mark('antipattern')} | {mark('anchor')} |"
        )
    add("")

    add("## 三、四组消融")
    add("")
    add("| 组 | 关掉了什么 | 诊断 F1 | 路径命中 | Top-3 一致 | 检出率 | 误报率 | 等级一致 | 证据链完整 |")
    add("|---|---|---|---|---|---|---|---|---|")
    dropped = {
        "ablation_no_attribution": "归因路径与排序",
        "ablation_no_constraint": "约束性场景数要求",
        "ablation_no_antipattern": "AP1—AP4 检测",
        "ablation_no_anchor": "结论与采集项/场景的锚定",
    }
    for system in ABLATION_SYSTEMS:
        metrics = report["systems"][system]["metrics"]
        add(
            f"| {report['systems'][system]['label']} | {dropped[system]} | "
            f"{_pct(metrics['T041_diagnosis_f1']['bottleneck_micro_f1'])} | "
            f"{_pct(metrics['T042_path_hit_rate']['hit_rate'])} | "
            f"{_pct(metrics['T043_ranking_top3']['top3_overlap'])} | "
            f"{_pct(metrics['T044_antipattern']['detection_rate'])} | "
            f"{_pct(metrics['T044_antipattern']['false_positive_rate'])} | "
            f"{_pct(metrics['level_agreement']['agreement'])} | "
            f"{_pct(metrics['evidence_quality']['evidence_complete_rate'])} |"
        )
    add("")

    add("## 四、完整闭环的六项指标")
    add("")
    add("| 指标 | 口径 | 实测 | 门槛 | 结论 |")
    add("|---|---|---|---|---|")
    metric_text = {
        task: f"{info['label']}（{info['basis']}）" for task, info in METRIC_INFO.items()
    }
    for task, rule in THRESHOLDS.items():
        verdict = report["verdicts"][task]
        add(
            f"| {task} | {metric_text[task]} | {_pct(verdict['value'])} | "
            f"{verdict['threshold']} | {verdict['status']} |"
        )
    add("")

    full = report["systems"]["control_full"]["metrics"]
    add("补充说明：")
    add("")
    add(f"- 诊断 F1：全类型微平均 {_pct(full['T041_diagnosis_f1']['micro_f1'])}、"
        f"宏平均 {_pct(full['T041_diagnosis_f1']['macro_f1'])}；"
        f"只看瓶颈型（反模式型 + 场景断层）为 {_pct(full['T041_diagnosis_f1']['bottleneck_micro_f1'])}。")
    roi = full["T045_roi_deviation"]
    add(f"- ROI：独立复算与引擎结果的最大相对偏差 {_pct(roi['implementation_max_gap'])}（实现一致性，"
        f"残差来自展示取整）；换成有公开案例支撑的弹性区间后，相对偏差中位数 "
        f"{_pct(roi['elasticity_switch_median_gap'])}、最大 {_pct(roi['elasticity_switch_max_gap'])}"
        f"（{roi['elasticity_switch_samples']} 个改造项可切换）——"
        f"**当前排序对弹性口径高度敏感**，这是口径层面的风险，不是实现错误；"
        f"相对真值的偏差仍不可测，需真实企业样本。")
    ranking = full["T043_ranking_top3"]
    stability = full["ranking_stability"]
    add(f"- 排序一致性：整体 {_pct(ranking['top3_overlap'])}（门槛 70%，**未达标**）。定位："
        f"期望动作 ≤4 个的样本 Top-3 完全一致；一级场景多（期望动作 8—9 个）的样本只有约 33%。"
        f"原因是排序按 ROI 下界走，会把高 ROI 但与已诊断瓶颈无关的改造项排进 Top-3"
        f"（例如 AP2 样本把「营销订单与生产协同」排在「质量数据闭环」之前）。"
        f"这属口径问题不是实现错误：是否在排序里加「先覆盖已诊断瓶颈」的约束，需人工裁决。")
    add(f"- 排序稳定性：每个改造项的成本与收益各自独立抖动 ±20%（{stability.get('trials', 20)} 轮，"
        f"系数由 crc32 推出、可复算）时，Top-3 换人比例 {_pct(stability['flip_rate'])}"
        f"（{stability['samples']} 个样本）。")
    generalization = full["T046_generalization"]
    add(f"- 跨行业：最差行业 {generalization['worst_industry']}（F1 "
        f"{_pct(generalization['worst_industry_f1'])}），相对总体衰减 "
        f"{_pct(generalization['degradation'])}。")
    add("")

    add("## 五、已知边界")
    add("")
    for note in REPORT_NOTES:
        add(f"- {note}")
    add("")
    return "\n".join(lines) + "\n"


def write_reports(report: dict[str, Any] | None = None) -> tuple[Path, Path]:
    report = report or run_evaluation()
    EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
    json_path = EVALUATION_DIR / "report.json"
    md_path = EVALUATION_DIR / "report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path
