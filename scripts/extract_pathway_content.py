#!/usr/bin/env python3
"""从预计算结果反解"归因步骤"的措辞内容。

`scripts/extract_pathway_params.py` 还原的是数值口径（投入区间、成效弹性、依赖）。
本脚本还原的是同一条链上的**措辞**：改造动作、症状、根因、依据、置信度、
关联采集项，并把每个改造项与它的前置依赖（改造项级）落到一张表里。

输出：`data/pathway_content.json`
结构：{"variants": {"<action_id>|<场景>": {...}}, "conflicts": [...]}

口径说明：
- 改造项主键取 `data/pathways.json` 的 `actions` 表（该表已验证 6 个样例间参数一致）；
- 预计算步骤与改造项的关联键是（投入区间, 目标场景），在 9 个改造项上唯一；
- 同一 (改造项, 场景) 在不同样例里若措辞或关联采集项不一致，记入 conflicts，
  取出现次数最多的版本，并显式保留冲突记录，不做静默合并。
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PRECOMPUTED = ROOT / "precomputed"
PATHWAYS = ROOT / "data" / "pathways.json"
OUTPUT = ROOT / "data" / "pathway_content.json"


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _action_index(actions: dict[str, Any]) -> dict[tuple[tuple[float, float], str], str]:
    """(投入区间, 目标场景) → 改造项 id。9 个改造项上唯一。"""
    index: dict[tuple[tuple[float, float], str], str] = {}
    for action_id, action in actions.items():
        cost = tuple(float(value) for value in action["cost_range"])
        for scenario in action.get("target_scenarios") or []:
            key = (cost, scenario)
            if key in index:
                raise SystemExit(f"(投入区间, 场景) 关联键不唯一：{key} -> {index[key]} / {action_id}")
            index[key] = action_id
    return index


def _step_signature(step: dict[str, Any]) -> tuple:
    return (
        step.get("action"),
        step.get("symptom"),
        step.get("root_cause"),
        tuple(step.get("target_items") or ()),
    )


def main() -> int:
    pathways = _load_json(PATHWAYS)
    if not pathways:
        print("缺少 data/pathways.json，请先运行 scripts/extract_pathway_params.py")
        return 1
    index = _action_index(pathways["actions"])

    variants: dict[str, dict[str, Any]] = {}
    conflicts: list[dict[str, Any]] = []
    depends: dict[str, Counter] = {}
    observed: Counter = Counter()
    unmatched: list[dict[str, Any]] = []

    for sample in sorted(PRECOMPUTED.glob("*.json")):
        if sample.name in {"criteria.json", "fixtures.json", "scenario_judgments.json"}:
            continue
        result = _load_json(sample).get("result") or {}
        steps = result.get("pathway") or []
        step_action: dict[int, str] = {}
        for step in steps:
            cost = tuple(float(value) for value in step.get("cost_range") or ())
            key = (cost, step.get("target_scenario"))
            action_id = index.get(key)
            if action_id is None:
                unmatched.append({"sample": sample.name, "path_ref": step.get("path_ref"), "key": str(key)})
                continue
            step_action[step["step"]] = action_id
            observed[(action_id, step.get("target_scenario"))] += 1
            variant_key = f"{action_id}|{step.get('target_scenario')}"
            entry = variants.setdefault(
                variant_key,
                {
                    "action_id": action_id,
                    "target_scenario": step.get("target_scenario"),
                    "path_ref": step.get("path_ref"),
                    "action": step.get("action"),
                    "symptom": step.get("symptom"),
                    "root_cause": step.get("root_cause"),
                    "basis": step.get("basis"),
                    "confidence": step.get("confidence"),
                    "target_items": list(step.get("target_items") or []),
                    "cost_basis": step.get("cost_basis"),
                    "seen_signatures": {},
                    "observed_in": [],
                },
            )
            signature = _step_signature(step)
            entry["seen_signatures"][json.dumps(signature, ensure_ascii=False)] = (
                entry["seen_signatures"].get(json.dumps(signature, ensure_ascii=False), 0) + 1
            )
            if sample.name not in entry["observed_in"]:
                entry["observed_in"].append(sample.name)
        for step in steps:
            action_id = step_action.get(step["step"])
            if action_id is None:
                continue
            for dep_step in step.get("depends_on") or []:
                dep_action = step_action.get(dep_step)
                if dep_action:
                    depends.setdefault(action_id, Counter())[dep_action] += 1

    for variant_key, entry in variants.items():
        signatures = entry.pop("seen_signatures")
        if len(signatures) > 1:
            best = max(signatures.items(), key=lambda pair: (pair[1], pair[0]))[0]
            chosen = json.loads(best)
            conflicts.append(
                {
                    "kind": "same_variant_multiple_wordings",
                    "variant": variant_key,
                    "observed_variants": len(signatures),
                    "chosen": {"action": chosen[0], "symptom": chosen[1], "target_items": chosen[3]},
                }
            )
            entry["action"], entry["symptom"], entry["root_cause"], entry["target_items"] = (
                chosen[0],
                chosen[1],
                chosen[2],
                list(chosen[3]),
            )
        entry["observed_in"].sort()

    payload = {
        "source": {
            "method": "从 precomputed 预计算样例的 pathway 步骤反解措辞内容",
            "samples": sorted(
                sample.name
                for sample in PRECOMPUTED.glob("*.json")
                if sample.name not in {"criteria.json", "fixtures.json", "scenario_judgments.json"}
            ),
            "join_key": "(投入区间, 目标场景) → 改造项 id",
            "note": "措辞内容来自站点已发布的预计算结果，未新增生成；口径待人工审校。",
        },
        "variants": variants,
        "depends_on_actions": {key: [dep for dep, _ in counter.most_common()] for key, counter in depends.items()},
        "conflicts": conflicts,
        "unmatched_steps": unmatched,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"写出 {OUTPUT.relative_to(ROOT)}")
    print(f"  步骤变体：{len(variants)}")
    print(f"  改造项：{len({entry['action_id'] for entry in variants.values()})}")
    print(f"  冲突：{len(conflicts)}")
    print(f"  未匹配步骤：{len(unmatched)}")
    for entry in sorted(variants.values(), key=lambda item: (item["action_id"], item["target_scenario"])):
        print(
            f"    {entry['action_id']:8s} {entry['target_scenario']}  "
            f"items={entry['target_items']}  {entry['action'][:34]}"
        )
    if unmatched:
        print("  未匹配明细：")
        for item in unmatched:
            print(f"    {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
