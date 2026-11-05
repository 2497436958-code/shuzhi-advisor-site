#!/usr/bin/env python3
"""从 precomputed 预计算样例反解路径参数表，输出 data/pathways.json。

用法：
    python3 scripts/extract_pathway_params.py          # 生成 / 刷新 data/pathways.json
    python3 scripts/extract_pathway_params.py --check  # 只比对已有文件，不写盘（幂等自检）

背景：
    预计算样例由一个已丢失的生成脚本产出，该脚本内含一张「路径级参数表」：
    每个路径的投入区间（cost_range）、每个路径 × 成效采集项的成效弹性区间（elasticity）。
    后端实时推理层需要这张表，本脚本从 6 个样例的 pathway / ranking 里机械还原。

还原口径（已对 6 个样例全部 31 条 ranking 行验算通过）：
    benefit_low  = Σ(采集项收益基数 base × elasticity.low)
    benefit_high = Σ(采集项收益基数 base × elasticity.high)
    roi_low      = benefit_low  ÷ cost_range[1]（最小收益 ÷ 最大成本，取悲观下界）
    roi_high     = benefit_high ÷ cost_range[0]
    展示取整：benefit_range 保留 1 位小数；roi 保留 4 位小数；
              roi 用「未取整」的收益值计算（取整后收益再算会得到不同的 roi，见 docs/pathway_params_provenance.md）。

弹性百分比从 pathway[].expected[].expect 文案解析，形如「改善 0.5%—2.0%」；
文案里还带「收益基数约 X 万元/年，预期年化收益 A—B 万元」，一并用于交叉验算。
supported=false 的条目（文案带「该弹性未被公开案例支撑」）原样保留标记。

约束：
    只读 precomputed/*.json；只写 data/pathways.json；只用标准库；
    输出不含时间戳，重复执行字节一致（幂等）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRECOMPUTED = ROOT / "precomputed"
OUTPUT = ROOT / "data" / "pathways.json"

# precomputed/ 下不是「样例结果」的辅助数据文件
NON_SAMPLE_FILES = {"criteria.json", "fixtures.json", "scenario_judgments.json"}

BENEFIT_DECIMALS = 1
ROI_DECIMALS = 4
TOL = 1e-6
UNSUPPORTED_MARKER = "该弹性未被公开案例支撑"

# 「改善 0.5%—2.0%」：允许 — – - ~ ～ 至 作分隔符
PCT_RE = re.compile(
    r"改善\s*(?P<low>[0-9]+(?:\.[0-9]+)?)\s*%\s*[—–\-~～至]\s*(?P<high>[0-9]+(?:\.[0-9]+)?)\s*%"
)
# 「（收益基数约 6000.0 万元/年，预期年化收益 30.0—120.0 万元）」
DETAIL_RE = re.compile(
    r"收益基数约\s*(?P<base>[0-9]+(?:\.[0-9]+)?)\s*万元/年，"
    r"预期年化收益\s*(?P<bl>[0-9]+(?:\.[0-9]+)?)\s*[—–\-~～至]\s*(?P<bh>[0-9]+(?:\.[0-9]+)?)\s*万元"
)


class ExtractError(RuntimeError):
    """还原口径与样例数据不符时抛出。"""


# --------------------------------------------------------------------------- 读取


def load_sample_names() -> list[str]:
    """样例文件清单，以 precomputed/fixtures.json 的登记顺序为准。"""
    fixtures = PRECOMPUTED / "fixtures.json"
    if fixtures.exists():
        names = [
            item["name"]
            for item in json.loads(fixtures.read_text(encoding="utf-8"))["fixtures"]
        ]
    else:
        names = sorted(p.name for p in PRECOMPUTED.glob("*.json"))
    names = [n for n in names if n not in NON_SAMPLE_FILES and (PRECOMPUTED / n).exists()]
    if not names:
        raise ExtractError("precomputed/ 下没有找到样例结果文件")
    return names


def expected_signature(expected: list[dict]) -> tuple:
    """expected 列表的稳定指纹，用于 pathway 步骤与 ranking 行的关联。"""
    return tuple(
        (item["indicator"], item["metric"], item["expect"], bool(item["supported"]))
        for item in expected
    )


# --------------------------------------------------------------------------- 解析


def parse_elasticity(expected: list[dict], bases: dict[str, float], where: str) -> dict[str, dict]:
    """从 expect 文案解析弹性区间，并做三重交叉验算（百分比 / 基数 / 年化收益）。"""
    parsed: dict[str, dict] = {}
    for item in expected:
        indicator = str(item["indicator"])
        text = item["expect"]
        if indicator not in bases:
            raise ExtractError(f"{where}：采集项 {indicator} 不在收益基数表内")

        match = PCT_RE.search(text)
        if not match:
            raise ExtractError(f"{where}：无法从文案解析弹性区间：{text}")
        low = float(match.group("low")) / 100.0
        high = float(match.group("high")) / 100.0
        if not 0 <= low <= high:
            raise ExtractError(f"{where}：弹性区间不合法：{text}")

        # supported 标记：字段与文案标记必须一致
        supported = bool(item["supported"])
        if supported == (UNSUPPORTED_MARKER in text):
            raise ExtractError(f"{where}：supported 标记与文案不一致：{text}")

        base = bases[indicator]
        detail = DETAIL_RE.search(text)
        if detail:
            if abs(float(detail.group("base")) - base) > TOL:
                raise ExtractError(f"{where}：文案收益基数 {detail.group('base')} 与基数表 {base} 不符")
            for raw, pct, key in (
                (detail.group("bl"), low, "bl"),
                (detail.group("bh"), high, "bh"),
            ):
                if abs(round(base * pct, BENEFIT_DECIMALS) - float(raw)) > 0.05 + TOL:
                    raise ExtractError(
                        f"{where}：文案年化收益 {raw} 与 base×elasticity={base * pct} 不符"
                    )

        parsed[indicator] = {
            "metric": item["metric"],
            "low": low,
            "high": high,
            "supported": supported,
        }
    return parsed


def recompute(cost_range: list[float], elasticity: dict[str, dict], bases: dict[str, float]) -> dict:
    """按还原口径复算收益区间与 ROI。"""
    low = sum(bases[k] * v["low"] for k, v in elasticity.items())
    high = sum(bases[k] * v["high"] for k, v in elasticity.items())
    return {
        "benefit_exact": [low, high],
        "benefit_range": [round(low, BENEFIT_DECIMALS), round(high, BENEFIT_DECIMALS)],
        "roi": [
            round(low / cost_range[1], ROI_DECIMALS),
            round(high / cost_range[0], ROI_DECIMALS),
        ],
    }


def check_close(actual: float, expected: float, where: str) -> None:
    if abs(actual - expected) > TOL:
        raise ExtractError(f"{where}：复算值 {actual} 与样例值 {expected} 不一致")


def collect_observations(payload: dict, name: str) -> tuple[list[dict], dict[str, float], dict, float]:
    """把一个样例拆成「步骤观测」列表，并返回该样例的收益基数表与 scale_factor。"""
    result = payload["result"]
    assumptions = result["roi_assumptions"]
    raw_bases = {str(k): v for k, v in assumptions["benefit_bases"].items()}
    bases = {key: float(value) for key, value in raw_bases.items()}
    scale_factor = float(assumptions["scale_factor"])

    steps = result["pathway"]
    rows = result["ranking"]

    # pathway 步骤 ↔ ranking 行：用（目标场景, 投入区间, 成效条目）唯一关联
    row_index: dict[tuple, list[dict]] = {}
    for row in rows:
        key = (
            row["target_scenario"],
            tuple(row["cost_range"]),
            expected_signature(row["expected"]),
        )
        row_index.setdefault(key, []).append(row)

    observations: list[dict] = []
    for position, step in enumerate(steps):
        where = f"{name} / 第 {step['step']} 步 {step['path_ref']}"
        if step["step"] != position + 1:
            raise ExtractError(f"{where}：step 序号与 pathway 位置不一致，depends_on 无法映射")

        key = (
            step["target_scenario"],
            tuple(step["cost_range"]),
            expected_signature(step["expected"]),
        )
        matched = row_index.get(key, [])
        if len(matched) != 1:
            raise ExtractError(f"{where}：无法唯一关联 ranking 行（命中 {len(matched)} 条）")
        row = matched[0]

        elasticity = parse_elasticity(step["expected"], bases, where)
        cost_range = [float(step["cost_range"][0]), float(step["cost_range"][1])]
        computed = recompute(cost_range, elasticity, bases)

        # 交叉验算：解析出的弹性必须精确复算出样例里的 benefit_range / roi_low / roi_high
        check_close(computed["benefit_range"][0], row["benefit_range"][0], where + " benefit_low")
        check_close(computed["benefit_range"][1], row["benefit_range"][1], where + " benefit_high")
        check_close(computed["roi"][0], row["roi_low"], where + " roi_low")
        check_close(computed["roi"][1], row["roi_high"], where + " roi_high")

        # 步骤依赖：depends_on 存的是步骤序号（1 起），映射回被依赖步骤的 PATH id
        depends_on_paths: list[str] = []
        for dep in step.get("depends_on") or []:
            if not 1 <= dep <= len(steps):
                raise ExtractError(f"{where}：depends_on 步骤序号 {dep} 越界")
            if dep == step["step"]:
                raise ExtractError(f"{where}：步骤依赖自身")
            dep_path = steps[dep - 1]["path_ref"]
            if dep_path not in depends_on_paths:
                depends_on_paths.append(dep_path)

        observations.append(
            {
                "sample": name,
                "path_id": step["path_ref"],
                "target_scenario": step["target_scenario"],
                "action_id": row["action_id"],
                "action_name": row["name"],
                "cost_range": cost_range,
                "depends_on_paths": depends_on_paths,
                "elasticity": elasticity,
                "benefit_range": computed["benefit_range"],
                "roi": computed["roi"],
            }
        )
    return observations, bases, raw_bases, scale_factor


# --------------------------------------------------------------------------- 汇总


def variant_key(observation: dict) -> tuple:
    return (
        observation["action_id"],
        tuple(observation["cost_range"]),
        tuple(sorted(observation["elasticity"].items())),
        tuple(observation["depends_on_paths"]),
    )


def build_step(entry: dict, samples: list[str]) -> dict:
    """把同一 (PATH, 改造项) 的多次观测合并成一个参数条目。"""
    elasticity = {
        key: {
            "metric": value["metric"],
            "low": value["low"],
            "high": value["high"],
            "supported": value["supported"],
        }
        for key, value in sorted(entry["elasticity"].items())
    }
    return {
        "action_id": entry["action_id"],
        "action_name": entry["action_name"],
        "target_scenario": entry["target_scenario"],
        "cost_range": list(entry["cost_range"]),
        "depends_on_paths": list(entry["depends_on_paths"]),
        "elasticity": elasticity,
        "benefit_range": list(entry["benefit_range"]),
        "roi": {"low": entry["roi"][0], "high": entry["roi"][1]},
        "observed_in": sorted(samples),
    }


def aggregate(observations: list[dict]) -> tuple[dict, dict, list[dict], dict]:
    """汇总成 paths / actions 两张表，并产出冲突清单。"""
    # 1) 按 (PATH, action) 归并观测，检查同一参数条目在 6 个样例间是否一致
    variants: dict[tuple[str, str], dict] = {}
    for observation in observations:
        key = (observation["path_id"], observation["action_id"])
        entry = variants.setdefault(
            key,
            {
                "path_id": observation["path_id"],
                "action_id": observation["action_id"],
                "action_name": observation["action_name"],
                "target_scenario": observation["target_scenario"],
                "cost_range": list(observation["cost_range"]),
                "depends_on_paths": list(observation["depends_on_paths"]),
                "elasticity": {k: dict(v) for k, v in observation["elasticity"].items()},
                "benefit_range": list(observation["benefit_range"]),
                "roi": list(observation["roi"]),
                "samples": [],
            },
        )
        # 同一 (PATH, action) 在不同样例里的参数必须完全一致
        for field in ("action_name", "target_scenario", "cost_range", "depends_on_paths", "elasticity"):
            if entry[field] != observation[field]:
                raise ExtractError(
                    f"{observation['sample']}：{observation['path_id']} / {observation['action_id']} "
                    f"的 {field} 与其他样例不一致：{entry[field]} vs {observation[field]}"
                )
        if observation["sample"] not in entry["samples"]:
            entry["samples"].append(observation["sample"])

    # 2) 同一 PATH 下的多个参数条目（多步骤路径）
    by_path: dict[str, list[dict]] = {}
    for entry in variants.values():
        by_path.setdefault(entry["path_id"], []).append(entry)

    # 3) action 级参数表：action 是真正稳定的参数主键（9 个改造项，跨样例完全一致）
    by_action: dict[str, list[dict]] = {}
    for entry in variants.values():
        by_action.setdefault(entry["action_id"], []).append(entry)

    action_scenarios = {
        action_id: sorted({e["target_scenario"] for e in entries})
        for action_id, entries in by_action.items()
    }

    paths: dict[str, dict] = {}
    conflicts: list[dict] = []
    for path_id in sorted(by_path):
        entries = sorted(by_path[path_id], key=lambda e: e["action_id"])
        steps = [build_step(e, e["samples"]) for e in entries]

        # 主步骤选取规则：优先取「专属于本路径场景」且跨样例场景固定的改造项；
        # 没有这种条目时退化为「观测样例最多」，最后按 action_id 字典序。
        def rank(entry: dict) -> tuple:
            scenario_specific = len(action_scenarios[entry["action_id"]]) == 1
            matches_path = action_scenarios[entry["action_id"]] == [entry["target_scenario"]]
            return (
                0 if scenario_specific and matches_path else 1,
                -len(entry["samples"]),
                entry["action_id"],
            )

        primary = min(entries, key=rank)
        path = {
            "id": path_id,
            "target_scenario": primary["target_scenario"],
            "action_id": primary["action_id"],
            "action_name": primary["action_name"],
            "cost_range": list(primary["cost_range"]),
            "depends_on_paths": list(primary["depends_on_paths"]),
            "elasticity": {
                key: {
                    "metric": value["metric"],
                    "low": value["low"],
                    "high": value["high"],
                    "supported": value["supported"],
                }
                for key, value in sorted(primary["elasticity"].items())
            },
            "benefit_range": list(primary["benefit_range"]),
            "roi": {"low": primary["roi"][0], "high": primary["roi"][1]},
            "observed_in": sorted({s for e in entries for s in e["samples"]}),
            "step_count": len(entries),
            "steps": steps,
        }
        if len(entries) > 1:
            path["multi_step"] = True
            conflicts.append(
                {
                    "kind": "same_path_id_multiple_parameter_sets",
                    "path_id": path_id,
                    "target_scenario": primary["target_scenario"],
                    "step_count": len(entries),
                    "action_ids": [e["action_id"] for e in entries],
                    "detail": (
                        f"{path_id} 在不同样例下解析出 {len(entries)} 组不同参数，"
                        "说明 path_ref 是一条路径的编号、不是参数表主键；"
                        "参数主键是改造项（action_id），详见同文件 actions 表。"
                    ),
                }
            )
        paths[path_id] = path

    actions: dict[str, dict] = {}
    for action_id in sorted(by_action):
        entries = by_action[action_id]
        first = entries[0]
        for entry in entries:
            for field in ("action_name", "cost_range", "depends_on_paths", "elasticity"):
                if entry[field] != first[field]:
                    raise ExtractError(
                        f"改造项 {action_id} 的 {field} 在不同路径间不一致，参数表无法还原"
                    )
        samples = sorted({s for e in entries for s in e["samples"]})
        actions[action_id] = {
            "action_id": action_id,
            "action_name": first["action_name"],
            "cost_range": list(first["cost_range"]),
            "depends_on_paths": list(first["depends_on_paths"]),
            "elasticity": {
                key: {
                    "metric": value["metric"],
                    "low": value["low"],
                    "high": value["high"],
                    "supported": value["supported"],
                }
                for key, value in sorted(first["elasticity"].items())
            },
            "benefit_range": list(first["benefit_range"]),
            "roi": {"low": first["roi"][0], "high": first["roi"][1]},
            "target_scenarios": action_scenarios[action_id],
            "scenario_specific": len(action_scenarios[action_id]) == 1,
            "path_ids": sorted({e["path_id"] for e in entries}),
            "observed_in": samples,
        }

    consistency = {
        "samples": len({o["sample"] for o in observations}),
        "path_ids": len(paths),
        "path_ids_single_parameter_set": sum(1 for p in paths.values() if p["step_count"] == 1),
        "path_ids_multi_parameter_set": sum(1 for p in paths.values() if p["step_count"] > 1),
        "actions": len(actions),
        "ranking_rows_checked": len(observations),
        "benefit_bases_consistent": True,
        "scale_factor_consistent": True,
        "note": (
            "同一 action_id 在 6 个样例间参数完全一致；"
            "同一 path_id 下存在多组参数的情况见 conflicts。"
        ),
    }
    return paths, actions, conflicts, consistency


# --------------------------------------------------------------------------- 输出


def build_payload(
    sample_names: list[str],
    paths: dict,
    actions: dict,
    conflicts: list[dict],
    consistency: dict,
    bases: dict[str, float],
    raw_bases: dict,
    scale_factor: float,
) -> dict:
    return {
        "schema_version": "1.0",
        "status": "从预计算结果反解的口径，待人工审校",
        "source": {
            "method": "从 precomputed 预计算样例的 pathway / ranking 机械反解",
            "samples": list(sample_names),
            "sample_count": len(sample_names),
            "revenue_reference_wan": 6000,
            "note": (
                "6 个样例的 profile.revenue_wan 均为 6000，"
                "cost_basis 提到的「按营收规模折算」在样例内不可观测；"
                "本表 cost_range 为 6000 万元营收基准值。"
            ),
        },
        "benefit_bases": {key: raw_bases[key] for key in sorted(raw_bases)},
        "scale_factor": scale_factor,
        "rounding": {
            "benefit_range_decimals": BENEFIT_DECIMALS,
            "roi_decimals": ROI_DECIMALS,
            "note": "roi 用未取整的收益值计算；benefit_range 为未取整收益取整后的展示值。",
        },
        "formula": {
            "benefit_range": "Σ(benefit_bases[采集项] × elasticity[采集项].low / .high)",
            "roi_low": "benefit_low ÷ cost_range[1]",
            "roi_high": "benefit_high ÷ cost_range[0]",
        },
        "paths": paths,
        "actions": actions,
        "conflicts": conflicts,
        "consistency": consistency,
    }


def render(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="反解路径参数表 -> data/pathways.json")
    parser.add_argument("--check", action="store_true", help="只比对已有文件，不写盘")
    args = parser.parse_args()

    try:
        sample_names = load_sample_names()
        observations: list[dict] = []
        bases: dict[str, float] = {}
        raw_bases: dict = {}
        scale_factor: float | None = None

        for name in sample_names:
            payload = json.loads((PRECOMPUTED / name).read_text(encoding="utf-8"))
            rows, sample_bases, sample_raw_bases, sample_scale = collect_observations(payload, name)
            observations.extend(rows)
            if bases:
                if sample_bases != bases or sample_scale != scale_factor:
                    raise ExtractError(f"{name}：收益基数表 / scale_factor 与其他样例不一致")
            else:
                bases = sample_bases
                raw_bases = sample_raw_bases
                scale_factor = sample_scale

        paths, actions, conflicts, consistency = aggregate(observations)
        payload = build_payload(
            sample_names, paths, actions, conflicts, consistency, bases, raw_bases, scale_factor or 1.0
        )
        text = render(payload)
    except (ExtractError, KeyError, ValueError) as error:
        print(f"还原失败：{error}", file=sys.stderr)
        return 1

    if args.check:
        if not OUTPUT.exists():
            print(f"缺少 {OUTPUT}，请先运行本脚本生成。", file=sys.stderr)
            return 1
        current = OUTPUT.read_text(encoding="utf-8")
        if current != text:
            print("幂等自检失败：data/pathways.json 与重新反解的结果不一致。", file=sys.stderr)
            return 1
        print(f"幂等自检通过：{OUTPUT.relative_to(ROOT)} 与重新反解结果字节一致。")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8")

    print(f"样例：{len(sample_names)} 个 → {', '.join(sample_names)}")
    print(f"已还原路径：{len(paths)} 个 PATH / {sum(p['step_count'] for p in paths.values())} 个路径步骤")
    print(f"已还原改造项：{len(actions)} 个（action 级参数表，跨样例完全一致）")
    print(f"复算通过：{consistency['ranking_rows_checked']} 条 ranking 行（benefit_range / roi_low / roi_high）")
    indicators = sorted({k for a in actions.values() for k in a["elasticity"]})
    print(f"覆盖成效采集项：{', '.join(indicators)}")
    if conflicts:
        print(f"检出冲突 {len(conflicts)} 处（同一 path_id 下多组参数）：")
        for conflict in conflicts:
            print(f"  - {conflict['path_id']}：{'、'.join(conflict['action_ids'])}")
    print(f"已写出：{OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
