"""改造路径：症状 → 根因 → 改造项，并给出分步顺序与验收口径。

数据来源：
- ``data/pathways.json``        改造项参数（投入区间、成效弹性、依赖），由
  ``scripts/extract_pathway_params.py`` 从预计算结果反解；
- ``data/pathway_content.json`` 改造项措辞（症状、根因、依据、置信度），由
  ``scripts/extract_pathway_content.py`` 反解。

选步规则（确定性，可复算）：
1. 弱场景 = 当前等级低于 2 级的场景；
2. 候选 = 目标场景命中弱场景的改造项；
3. 按优先级 P 排序取前 6 步；
4. 强制补齐前置依赖（依赖不满足的步骤标记受阻）；
5. 超出 6 步时，先剔除不影响他人的最低优先级候选。

依赖顺序（先底座后场景）与 ROI 排序（保守取下界）是两套口径，页面上分别展示。
"""

from __future__ import annotations

from typing import Any

from . import evidence as ev

MAX_STEPS = 6
TARGET_LEVEL = 2


def _score_text(value: float) -> str:
    """得分按整数展示（官方选项对应的是档位，不是小数）。"""
    return str(round(value))


def weak_scenarios(evaluation: dict[str, Any]) -> dict[str, int]:
    levels = evaluation.get("scenario_levels") or {}
    return {
        scenario_id: level
        for scenario_id, level in levels.items()
        if level < TARGET_LEVEL
    }


def _pick_scenario(
    action: dict[str, Any], weak: dict[str, int]
) -> str | None:
    """该改造项本次要推的场景：命中的弱场景里等级最低、编号最小者。"""
    hits = [
        (weak[scenario_id], scenario_id)
        for scenario_id in action.get("target_scenarios") or []
        if scenario_id in weak
    ]
    if not hits:
        return None
    hits.sort()
    return hits[0][1]


def _dependencies(
    action: dict[str, Any],
    content: dict[str, Any],
    path_to_actions: dict[str, list[str]],
) -> list[str]:
    """改造项级前置依赖：优先用观测到的依赖，其次用路径级依赖展开。"""
    deps = set(content.get("depends_on_actions", {}).get(action["action_id"]) or [])
    for path_id in action.get("depends_on_paths") or []:
        deps.update(path_to_actions.get(path_id, []))
    deps.discard(action["action_id"])
    return sorted(deps)


def select_actions(
    actions_table: dict[str, Any],
    content: dict[str, Any],
    evaluation: dict[str, Any],
    criteria: dict[str, Any],
    bases: dict[str, float],
) -> list[dict[str, Any]]:
    """选出本次要推进的改造项（已按依赖拓扑排序）。"""
    from .ranking import level_gain, priority_score

    items = {item["id"]: item for item in evaluation["item_results"]}
    weak = weak_scenarios(evaluation)

    path_to_actions: dict[str, list[str]] = {}
    for variant in (content.get("variants") or {}).values():
        path_id = variant.get("path_ref")
        if path_id:
            path_to_actions.setdefault(path_id, [])
            if variant["action_id"] not in path_to_actions[path_id]:
                path_to_actions[path_id].append(variant["action_id"])

    def make_candidate(action: dict[str, Any], scenario_id: str) -> dict[str, Any]:
        gain = level_gain(action, items)
        return {
            "action_id": action["action_id"],
            "action_name": action["action_name"],
            "target_scenario": scenario_id,
            "target_scenarios": list(action.get("target_scenarios") or []),
            "cost_range": list(action["cost_range"]),
            "elasticity": action.get("elasticity") or {},
            "target_items": _variant_items(content, action["action_id"], scenario_id),
            "path_ref": _variant_path(content, action["action_id"], scenario_id),
            "gain": gain,
            "priority": priority_score(action, bases, gain),
        }

    # 一个场景只提一个改造项：优先场景专属动作，底座动作只补没有专属动作的场景。
    specific = [
        action
        for action in actions_table.values()
        if len(action.get("target_scenarios") or []) == 1
    ]
    generic = [
        action
        for action in actions_table.values()
        if len(action.get("target_scenarios") or []) > 1
    ]

    candidates: list[dict[str, Any]] = []
    taken: set[str] = set()
    for action in specific:
        scenario_id = _pick_scenario(action, weak)
        if scenario_id is None or scenario_id in taken:
            continue
        taken.add(scenario_id)
        candidates.append(make_candidate(action, scenario_id))
    for action in generic:
        for scenario_id in sorted(
            action.get("target_scenarios") or [], key=lambda sid: (weak.get(sid, 9), sid)
        ):
            if scenario_id in weak and scenario_id not in taken:
                taken.add(scenario_id)
                candidates.append(make_candidate(action, scenario_id))
                break

    candidates.sort(key=lambda row: (-row["priority"], row["action_id"]))
    selected = candidates[:MAX_STEPS]
    selected_ids = {row["action_id"] for row in selected}

    # 补齐前置依赖
    by_id = {row["action_id"]: row for row in candidates}
    changed = True
    while changed:
        changed = False
        for row in list(selected):
            for dep in _dependencies(by_id.get(row["action_id"], row), content, path_to_actions):
                if dep in selected_ids:
                    continue
                dep_row = by_id.get(dep)
                if dep_row is None:
                    row.setdefault("blocked_by", []).append(dep)
                    continue
                selected.append(dep_row)
                selected_ids.add(dep)
                changed = True

    # 超出上限时先剔除不影响他人的最低优先级候选
    if len(selected) > MAX_STEPS:
        required = set()
        for row in selected:
            for dep in _dependencies(by_id.get(row["action_id"], row), content, path_to_actions):
                if dep in selected_ids:
                    required.add(dep)
        removable = [row for row in selected if row["action_id"] not in required]
        removable.sort(key=lambda row: (row["priority"], row["action_id"]))
        while len(selected) > MAX_STEPS and removable:
            victim = removable.pop(0)
            selected.remove(victim)
            selected_ids.discard(victim["action_id"])

    _annotate_blocked(selected, by_id, content, path_to_actions)
    _sort_by_dependency(selected, content, path_to_actions)
    return selected


def _variant_items(content: dict[str, Any], action_id: str, scenario_id: str) -> list[int]:
    variants = content.get("variants") or {}
    exact = variants.get(f"{action_id}|{scenario_id}")
    if exact:
        return list(exact.get("target_items") or [])
    for variant in variants.values():
        if variant.get("action_id") == action_id:
            return list(variant.get("target_items") or [])
    return []


def _variant_path(content: dict[str, Any], action_id: str, scenario_id: str) -> str | None:
    variants = content.get("variants") or {}
    exact = variants.get(f"{action_id}|{scenario_id}")
    if exact:
        return exact.get("path_ref")
    for variant in variants.values():
        if variant.get("action_id") == action_id:
            return variant.get("path_ref")
    return None


def _annotate_blocked(
    selected: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    content: dict[str, Any],
    path_to_actions: dict[str, list[str]],
) -> None:
    selected_ids = {row["action_id"] for row in selected}
    for row in selected:
        blocked = []
        for dep in _dependencies(by_id.get(row["action_id"], row), content, path_to_actions):
            if dep not in selected_ids:
                blocked.append(dep)
        row["blocked_by"] = sorted(blocked)


def _sort_by_dependency(
    selected: list[dict[str, Any]],
    content: dict[str, Any],
    path_to_actions: dict[str, list[str]],
) -> None:
    by_id = {row["action_id"]: row for row in selected}

    def depth(row: dict[str, Any], seen: frozenset[str] = frozenset()) -> int:
        if row["action_id"] in seen:
            return 0
        best = 0
        for dep in _dependencies(by_id.get(row["action_id"], row), content, path_to_actions):
            dep_row = by_id.get(dep)
            if dep_row is not None:
                best = max(best, 1 + depth(dep_row, seen | {row["action_id"]}))
        return best

    selected.sort(key=lambda row: (depth(row), -row["priority"], row["action_id"]))


def _expected(
    action: dict[str, Any], bases: dict[str, float]
) -> list[dict[str, Any]]:
    """预期成效：按成效采集项 12—15 给出区间与是否被公开案例支撑。"""
    expected = []
    for indicator, elasticity in sorted(
        (action.get("elasticity") or {}).items(), key=lambda pair: int(pair[0])
    ):
        base = bases.get(str(indicator), 0.0)
        low = base * elasticity["low"]
        high = base * elasticity["high"]
        text = (
            f"改善 {elasticity['low'] * 100:.1f}%—{elasticity['high'] * 100:.1f}%"
            f"（收益基数约 {base:.1f} 万元/年，预期年化收益 {low:.1f}—{high:.1f} 万元）"
        )
        if not elasticity.get("supported", False):
            text += "；该弹性未被公开案例支撑，只用于排序，不作为结论数"
        expected.append(
            {
                "indicator": int(indicator),
                "metric": elasticity.get("metric", ""),
                "expect": text,
                "supported": bool(elasticity.get("supported", False)),
            }
        )
    return expected


def _item_improvement(
    indicator: dict[str, Any], item: dict[str, Any]
) -> str | None:
    """下一档的提升方案（可复算：按官方选项顺序往后一档）。"""
    options = indicator["options"]
    selected = list(item["selected"])
    if indicator["option_type"] == "单选":
        index = options.index(selected[0])
        if index + 1 >= len(options):
            return None
        current_score = index * 100.0 / (len(options) - 1)
        next_score = (index + 1) * 100.0 / (len(options) - 1)
        return (
            f"采集项 {indicator['id']}「{indicator['item']}」由「{selected[0]}」"
            f"提升到「{options[index + 1]}」（该项得分 {_score_text(current_score)} → "
            f"{_score_text(next_score)}）"
        )

    chosen = [option for option in selected if option != "无"]
    denominator = len(options) - 1
    if len(chosen) + 1 > denominator:
        return None
    current_score = len(chosen) * 100.0 / denominator
    next_score = (len(chosen) + 1) * 100.0 / denominator
    return (
        f"采集项 {indicator['id']}「{indicator['item']}」由「{'、'.join(chosen)}」"
        f"提升到「在当前 {len(chosen)} 项基础上再补 1 项（合计 {len(chosen) + 1} 项）」"
        f"（该项得分 {_score_text(current_score)} → {_score_text(next_score)}）"
    )


def _acceptance(
    criteria: dict[str, Any],
    scenario_id: str,
    target_items: list[int],
    items: dict[int, dict[str, Any]],
) -> str:
    scenario = next(s for s in criteria["scenarios"] if s["id"] == scenario_id)
    level = min(TARGET_LEVEL, 4)
    description = scenario["levels"].get(str(level), "").rstrip("。")
    text = (
        f"场景 {scenario_id}「{scenario['name']}」达到 {level} 级，"
        f"按附件（二）判定要求逐条核对：{description}。"
    )
    for item_id in target_items:
        item = items.get(item_id)
        if item is None:
            continue
        indicator = next(i for i in criteria["indicators"] if i["id"] == item_id)
        improvement = _item_improvement(indicator, item)
        if improvement:
            text += improvement + "；"
    return text.rstrip("；")


def build_pathway(
    profile: dict[str, Any],
    evaluation: dict[str, Any],
    criteria: dict[str, Any],
    actions_table: dict[str, Any],
    content: dict[str, Any],
    bases: dict[str, float],
    knowledge: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """产出路径段（分步顺序）与被选中的改造项。"""
    items = {item["id"]: item for item in evaluation["item_results"]}
    selected = select_actions(actions_table, content, evaluation, criteria, bases)
    variants = content.get("variants") or {}
    levels = evaluation.get("scenario_levels") or {}

    steps: list[dict[str, Any]] = []
    for index, row in enumerate(selected, start=1):
        scenario_id = row["target_scenario"]
        variant = variants.get(f"{row['action_id']}|{scenario_id}")
        action_table_entry = actions_table.get(row["action_id"], {})
        scenario = next(s for s in criteria["scenarios"] if s["id"] == scenario_id)

        if variant is not None:
            action_text = variant["action"]
            symptom = variant.get("symptom")
            root_cause = variant.get("root_cause")
            basis = variant.get("basis")
            confidence = variant.get("confidence")
            path_ref = variant.get("path_ref")
        else:
            action_text = f"{row['action_name']}（目标场景 {scenario_id}「{scenario['name']}」）"
            symptom = None
            root_cause = None
            basis = None
            confidence = None
            path_ref = row.get("path_ref")

        refs = []
        for item_id in row.get("target_items") or []:
            item = items.get(item_id)
            if item is not None:
                refs.append(ev.indicator_ref(criteria, item_id, item))
        refs.append(ev.scenario_ref(criteria, scenario_id, levels.get(scenario_id, 1)))
        cases = knowledge.cases_for_scenario(scenario_id)
        if cases:
            refs.append(ev.case_ref(cases[0]))

        step = {
            "step": index,
            "action": action_text,
            "target_scenario": scenario_id,
            "path_ref": path_ref,
            "symptom": symptom,
            "root_cause": root_cause,
            "basis": basis,
            "confidence": confidence,
            "target_items": list(row.get("target_items") or []),
            "cost_range": [
                round(action_table_entry.get("cost_range", [0, 0])[0], 1),
                round(action_table_entry.get("cost_range", [0, 0])[1], 1),
            ],
            "cost_estimated": True,
            "cost_basis": "万元/年，估算区间（含直接投入 + 年运维 + 内部工时折价）；按营收规模折算",
            "expected": _expected(action_table_entry, bases),
            "acceptance": _acceptance(
                criteria, scenario_id, list(row.get("target_items") or []), items
            ),
            "depends_on": [],
            "evidence_refs": ev.ensure_evidence(action_text, refs),
        }
        steps.append(step)

    step_number = {row["action_id"]: step["step"] for step, row in zip(steps, selected)}
    for step, row in zip(steps, selected):
        deps = []
        for dep in row.get("blocked_by") or []:
            deps.append(dep)
        step["depends_on"] = sorted(
            step_number[dep] for dep in deps if dep in step_number
        )
    return steps, selected
