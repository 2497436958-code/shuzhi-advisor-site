#!/usr/bin/env python3
"""生成 60 家合成评测样本（真实层 0 家，合成层 60 家）。

样本构成（主控文档 T037）：
- AP1—AP4 各 10 家：分别按四条反模式判据构造，每家**只**命中目标反模式；
- 正常对照 20 家：按二级规范级企业构造，不命中任何反模式。

硬约束：
1. **合成层与真实层分开**：每条样本带 ``synthetic: true`` 与
   ``provenance: "合成样本（synthetic）…"``，真实企业不得混进来；
2. **模型不参与算分**：样本由规则构造，算分、定级、反模式命中全部由
   ``advisor.scoring.engine`` 与 ``advisor.reasoning.antipatterns`` 算出；
3. **可复算**：固定随机种子，重跑结果一致（``--check`` 做幂等自检）；
4. **自带 ground truth**：每条样本记录按构造应当命中的反模式、诊断类型、
   应当出现的改造路径与等级区间，供 T041—T046 的指标直接使用。

用法：
    python3 scripts/generate_synthetic_profiles.py          # 生成
    python3 scripts/generate_synthetic_profiles.py --check   # 幂等自检
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from advisor.reasoning.antipatterns import detect_antipatterns
from advisor.scoring.engine import evaluate_profile, load_criteria

OUTPUT = ROOT / "data" / "profiles" / "synthetic_60.json"
SEED = 20261105

CRITERIA = load_criteria(ROOT / "precomputed" / "criteria.json")
SCENARIOS = {scenario["id"]: scenario for scenario in CRITERIA["scenarios"]}
CONSTRAINT_SCENARIOS = [sid for sid, s in SCENARIOS.items() if s.get("constraint")]

# 官方选项原文（与 criteria.json 一致，构造样本时按原文给值）
OPT = {
    "网络建设": [
        "无",
        "企业车间建成工控网络，支持自动化控制应用",
        "企业建成应用系统网络，实现大规模设备、人员与信息系统互联，可支持大规模设备、人员与信息系统互联",
        "企业建设/租用5G工业网络，支撑系统互联和网络协同应用，满足AGV、工业互联网等规模化移动应用场景需求",
        "网络全面覆盖生产现场与环节，具备未来智能化新应用的扩展能力",
    ],
    "设备数字化": ["[0-10%]", "(10%,20%]", "(20%,40%]", "(40%,60%]", "(60%,100%]"],
    "设备联网": ["[0-10%]", "(10%,20%]", "(20%,40%]", "(40%,60%]", "(60%,100%]"],
    "信息系统": ["无", "单个业务环节", "多个业务环节（2个及以上）", "绝大部分业务环节（大于80%）", "全覆盖"],
    "网络安全": [
        "无",
        "建立了网络安全管理制度",
        "使用了网络安全产品及服务（如防火墙、网络分区、入侵检测、身份认证等）",
        "自行或委托专业评估机构实施网络安全风险评估",
        "建立网络边界安全访问控制能力，及网络关键节点入侵检测和恶意代码检测能力",
    ],
    "数据安全": [
        "无",
        "建立了数据安全管理制度",
        "使用了数据安全产品及服务（如数据加密、数据备份与恢复、数据脱敏、数据分级分类保护等）",
        "自行或委托专业评估机构实施数据风险评估",
        "建立数据台账（类型、用途、数量、数据源单位、使用单位等），定期开展数据安全保障能力核验",
    ],
    "规划实施": [
        "无",
        "已经主动了解数字化相关内容",
        "已经制定实施数字化的规划、计划及保障措施等",
        "已经着手开始进行单点或多点的数字化改造",
        "已经通过数字化手段实现业务模式、管理决策方式的改变并取得成效",
        "定期组织员工去数字化建设成效较好的同行业公司参观交流，增强数字化转型意识",
    ],
    "管理机制": [
        "无",
        "建立数字化转型实施工作流程",
        "建立信息系统建设及运营管理制度",
        "建立数据资源管理制度",
        "建立与数字化融合的科研、业务、产品等方面的创新激励制度",
    ],
    "人才建设": [
        "无",
        "配备专职/兼职的数字化人才",
        "设置专门的数字化岗位/部门",
        "定期对员工开展数字化方面培训",
        "有明确的数字化人才绩效及薪酬管理",
        "有明确的数字化人才梯度培育机制",
    ],
    "资金保障": ["[0-10%]", "(10%,20%]", "(20%,40%]", "(40%,60%]", "(60%,100%]"],
    "绿色低碳": ["增加", "持平", "降低"],
    "产品质量": ["降低", "持平", "增加"],
    "市场表现": ["降低", "持平", "增加"],
    "价值效益": ["增加", "持平", "降低"],
}

DATA_SCOPE = [
    "产品设计", "工艺设计", "营销管理", "售后服务", "计划排程", "生产管控",
    "质量管理", "设备管理", "安全生产", "能耗管理", "采购管理", "仓储物流",
    "财务管理", "人力资源",
]

INDUSTRIES = [
    "电子电器", "装备制造", "原材料", "纺织", "汽车零部件", "五金制品",
    "机械加工", "食品", "化工", "医疗器械",
]

SCALES = [
    ("小型", 1800, 35, 220, 900, 120),
    ("中型", 6000, 120, 200, 3600, 260),
    ("中型偏上", 12000, 260, 380, 7200, 420),
]


def solid_answers() -> dict[str, list[str]]:
    """二级规范级企业的基线答案。"""
    return {
        "1": [OPT["网络建设"][1], OPT["网络建设"][2]],
        "2": [OPT["设备数字化"][3]],
        "3": [OPT["设备联网"][3]],
        "4": ["产品设计", "工艺设计", "营销管理", "生产管控"],
        "5": [OPT["信息系统"][2]],
        "6": [OPT["网络安全"][1]],
        "7": [OPT["数据安全"][1]],
        "8": [OPT["规划实施"][3]],
        "9": [OPT["管理机制"][1], OPT["管理机制"][2]],
        "10": [OPT["人才建设"][1], OPT["人才建设"][3]],
        "11": [OPT["资金保障"][1]],
        "12": [OPT["绿色低碳"][2]],
        "13": [OPT["产品质量"][1]],
        "14": [OPT["市场表现"][1]],
        "15": [OPT["价值效益"][1]],
    }


def base_scenarios() -> dict[str, int]:
    """二级企业的场景等级：多数场景二级，少数一级留作改造空间。"""
    levels = {sid: 2 for sid in SCENARIOS}
    for sid in ("S08", "S09", "S10", "S11", "S12"):
        levels[sid] = 1
    return levels


def build_ap1(rng: random.Random, index: int) -> tuple[dict, dict, dict]:
    """AP1 只买设备不联网：设备买齐了但没联网。"""
    answers = solid_answers()
    answers["2"] = [OPT["设备数字化"][4]]
    answers["3"] = [OPT["设备联网"][0]]
    answers["4"] = ["产品设计", "工艺设计", "营销管理", "售后服务"]
    answers["1"] = [OPT["网络建设"][1]]
    scenarios = base_scenarios()
    scenarios["S08"] = 1
    expected = {
        "antipatterns": ["AP1"],
        "diagnosis_types": ["基础断层·设备侧"],
        "bottleneck_scenarios": ["S08"],
    }
    return answers, scenarios, expected


def build_ap2(rng: random.Random, index: int) -> tuple[dict, dict, dict]:
    """AP2 只上系统不跑流程：系统铺开了，流程没跑。"""
    answers = solid_answers()
    answers["5"] = [OPT["信息系统"][4]]
    answers["4"] = ["产品设计", "工艺设计", "营销管理", "售后服务", "计划排程"]
    scenarios = base_scenarios()
    for sid in ("S01", "S02", "S13", "S14", "S15"):
        scenarios[sid] = 2
    for sid in ("S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10", "S11", "S12", "S16"):
        scenarios[sid] = 1
    expected = {
        "antipatterns": ["AP2"],
        "diagnosis_types": ["流程空转·系统已上"],
        "bottleneck_scenarios": ["S06", "S07"],
    }
    return answers, scenarios, expected


def build_ap3(rng: random.Random, index: int) -> tuple[dict, dict, dict]:
    """AP3 只做数据采集不做分析：采集覆盖广，但没有分析与决策。"""
    answers = solid_answers()
    answers["4"] = [
        "产品设计", "工艺设计", "营销管理", "售后服务", "计划排程", "生产管控", "质量管理",
    ]
    scenarios = base_scenarios()
    scenarios["S16"] = 1
    expected = {
        "antipatterns": ["AP3"],
        "diagnosis_types": ["数据沉底·只采不析"],
        "bottleneck_scenarios": ["S16"],
    }
    return answers, scenarios, expected


def build_ap4(rng: random.Random, index: int) -> tuple[dict, dict, dict]:
    """AP4 只追补贴不建能力：投入占比高，能力没建起来。"""
    answers = solid_answers()
    # 追了补贴、买了点东西（建了工控网络、上了单个环节的系统），但能力没建起来
    answers["1"] = [OPT["网络建设"][1]]
    answers["2"] = [OPT["设备数字化"][0]]
    answers["3"] = [OPT["设备联网"][0]]
    answers["4"] = ["无"]
    # 补贴换来了系统，但流程没跑起来（单个业务环节 → 两个以上环节，仍未到全覆盖）
    answers["5"] = [OPT["信息系统"][2]]
    answers["6"] = ["无"]
    answers["7"] = ["无"]
    answers["8"] = [OPT["规划实施"][0]]
    answers["9"] = ["无"]
    answers["10"] = ["无"]
    answers["11"] = [OPT["资金保障"][3]]
    answers["12"] = [OPT["绿色低碳"][1]]
    answers["13"] = [OPT["产品质量"][1]]
    answers["14"] = [OPT["市场表现"][1]]
    answers["15"] = [OPT["价值效益"][0]]
    scenarios = base_scenarios()
    for sid in SCENARIOS:
        scenarios[sid] = 1
    scenarios["S13"] = 2
    expected = {
        "antipatterns": ["AP4"],
        "diagnosis_types": ["投入错配·重投入轻能力"],
        "bottleneck_scenarios": [],
    }
    return answers, scenarios, expected


def build_control(rng: random.Random, index: int) -> tuple[dict, dict, dict]:
    """正常对照：二级规范级企业，不命中任何反模式。"""
    answers = solid_answers()
    scenarios = base_scenarios()
    expected = {
        "antipatterns": [],
        "diagnosis_types": [],
        "bottleneck_scenarios": [],
    }
    return answers, scenarios, expected


ARCHETYPES = [
    ("AP1", build_ap1, 10, "只买设备不联网"),
    ("AP2", build_ap2, 10, "只上系统不跑流程"),
    ("AP3", build_ap3, 10, "只做数据采集不做分析"),
    ("AP4", build_ap4, 10, "只追补贴不建能力"),
    ("control", build_control, 20, "正常对照（二级规范级）"),
]

# 按构造应当得到的等级（与引擎实测一致才算自检通过）
EXPECTED_LEVELS = {
    "AP1": [2],
    "AP2": [1],
    "AP3": [2],
    "AP4": [1],
    "control": [2],
}


def vary(rng: random.Random, answers: dict[str, list[str]], archetype: str) -> None:
    """在不破坏判据与等级区间的前提下做变体差异。

    只在**同一得分档位**内替换选项：多选换选中的项但不改选中数量
    （多选得分只与数量有关），单选不换（单选每一档得分不同）。
    因此分数不变、命中不变，样本之间的差异只在"选了哪一项"。
    """
    swap: dict[str, list[list[str]]] = {
        "6": [[OPT["网络安全"][1]], [OPT["网络安全"][2]]],
        "7": [[OPT["数据安全"][1]], [OPT["数据安全"][2]]],
        "9": [[OPT["管理机制"][1], OPT["管理机制"][2]], [OPT["管理机制"][2], OPT["管理机制"][3]]],
        "10": [[OPT["人才建设"][1], OPT["人才建设"][3]], [OPT["人才建设"][1], OPT["人才建设"][4]]],
    }
    if archetype == "AP1":
        swap["1"] = [[OPT["网络建设"][1]], [OPT["网络建设"][2]]]
        swap["2"] = [[OPT["设备数字化"][4]]]
        swap["3"] = [[OPT["设备联网"][0]], [OPT["设备联网"][1]]]
    elif archetype == "AP2":
        swap["2"] = [[OPT["设备数字化"][3]], [OPT["设备数字化"][4]]]
        swap["3"] = [[OPT["设备联网"][3]], [OPT["设备联网"][4]]]
    elif archetype == "AP3":
        swap["2"] = [[OPT["设备数字化"][3]], [OPT["设备数字化"][4]]]
        swap["3"] = [[OPT["设备联网"][3]], [OPT["设备联网"][4]]]
    elif archetype == "AP4":
        for key in ("6", "7", "9", "10"):
            swap.pop(key, None)

    for key, choices in swap.items():
        if key in answers and choices:
            answers[key] = list(rng.choice(choices))


def wobble(rng: random.Random, answers: dict[str, list[str]], archetype: str) -> None:
    """在同一判据前提下拉开得分档次。

    - AP4：各项已接近最弱，只让成效项往好的方向走（总分已贴近一级门槛 20 分，
      往下走会掉出等级），保证仍在初始级；
    - 其余 archetype：规划实施与资金保障各换一档（都不影响四条反模式判据），
      让同一 archetype 内出现不同得分与等级组合。
    """
    if archetype == "AP4":
        # 成效项只允许持平或更好；总分贴近一级门槛（20 分），往下走会掉成无等级
        answers["12"] = [rng.choice([OPT["绿色低碳"][1], OPT["绿色低碳"][2]])]
        answers["15"] = [rng.choice([OPT["价值效益"][0], OPT["价值效益"][1]])]
        return
    answers["8"] = [rng.choice([OPT["规划实施"][2], OPT["规划实施"][3], OPT["规划实施"][4]])]
    answers["11"] = [rng.choice([OPT["资金保障"][1], OPT["资金保障"][2]])]


def sample_profile(rng: random.Random, archetype: str, builder, index: int) -> dict[str, Any]:
    answers, scenarios, expected = builder(rng, index)
    vary(rng, answers, archetype)
    wobble(rng, answers, archetype)
    scale_name, revenue, spend, headcount, cost, energy = SCALES[index % len(SCALES)]
    industry = INDUSTRIES[index % len(INDUSTRIES)]
    name = f"SYN-{archetype.upper()}-{index + 1:02d}"
    profile = {
        "name": name,
        "provenance": (
            "合成样本（synthetic）：由 scripts/generate_synthetic_profiles.py "
            "按判据规则构造，非真实企业数据，不得用于对外披露"
        ),
        "answers": answers,
        "scenario_levels": scenarios,
        "revenue_wan": revenue + rng.randrange(-200, 400, 50),
        "digital_spend_wan": spend + rng.randrange(-20, 40, 5),
        "energy_wan": energy + rng.randrange(-40, 80, 10),
        "headcount": headcount + rng.randrange(-20, 40, 5),
        "cost_wan": cost + rng.randrange(-200, 300, 50),
        "province": "",
    }
    return {
        "id": name,
        "label": expected.get("label", archetype),
        "archetype": archetype,
        "synthetic": True,
        "industry": industry,
        "scale": scale_name,
        "expected": expected,
        "profile": profile,
    }


def load_action_table() -> dict[str, Any]:
    """改造项 → 目标场景映射（来自 data/pathways.json）。"""
    path = ROOT / "data" / "pathways.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("actions") or {}


def expected_action_ids(scenarios: dict[str, int], action_table: dict[str, Any]) -> list[str]:
    """仍在一级的场景，对应的改造项应当出现在路径段里。

    这是按"路径表覆盖的场景"推出的 ground truth，与推理层的选步规则无关，
    可以直接用来算归因路径命中率（T042）。
    """
    by_scenario: dict[str, list[str]] = {}
    for action_id, action in action_table.items():
        for scenario_id in action.get("target_scenarios") or []:
            by_scenario.setdefault(scenario_id, []).append(action_id)
    expected: list[str] = []
    for scenario_id, level in sorted(scenarios.items()):
        if level > 1:
            continue
        for action_id in by_scenario.get(scenario_id, []):
            if action_id not in expected:
                expected.append(action_id)
    return expected


def evaluate_sample(sample: dict[str, Any]) -> dict[str, Any]:
    """用确定性引擎复核样本，拿到真实命中结果。"""
    profile = sample["profile"]
    evaluation = evaluate_profile(profile, CRITERIA)
    hits = detect_antipatterns(evaluation, CRITERIA)
    return {
        "total_score": evaluation["total_score"],
        "level": evaluation["level"],
        "level_name": evaluation["level_name"],
        "antipatterns": [hit.pattern_id for hit in hits],
    }


def build_dataset() -> dict[str, Any]:
    rng = random.Random(SEED)
    action_table = load_action_table()
    samples: list[dict[str, Any]] = []
    for archetype, builder, count, label in ARCHETYPES:
        for index in range(count):
            sample = sample_profile(rng, archetype, builder, index)
            sample["label"] = label
            sample["expected"]["action_ids"] = expected_action_ids(
                sample["profile"]["scenario_levels"], action_table
            )
            sample["actual"] = evaluate_sample(sample)
            samples.append(sample)
    return {
        "schema_version": "1.0",
        "generated_by": "scripts/generate_synthetic_profiles.py",
        "seed": SEED,
        "synthetic": True,
        "expected_levels": EXPECTED_LEVELS,
        "composition": {
            "total": 60,
            "AP1": 10,
            "AP2": 10,
            "AP3": 10,
            "AP4": 10,
            "control": 20,
        },
        "note": (
            "全部为合成样本（真实层 0 家）。按 AP1—AP4 各 10 家、正常对照 20 家构造，"
            "每条记录 expected（按构造应当命中的反模式与诊断）与 actual（引擎实测结果），"
            "供 T041—T046 的指标直接使用。"
        ),
        "samples": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 60 家合成评测样本")
    parser.add_argument("--check", action="store_true", help="只做幂等自检，不写文件")
    args = parser.parse_args()

    dataset = build_dataset()
    payload = json.dumps(dataset, ensure_ascii=False, indent=1) + "\n"

    problems: list[str] = []
    for sample in dataset["samples"]:
        expected = sample["expected"]["antipatterns"]
        actual = sample["actual"]["antipatterns"]
        if expected != actual:
            problems.append(
                f"{sample['id']}：期望命中 {expected or '无'}，实测 {actual or '无'}"
            )
        allowed = EXPECTED_LEVELS[sample["archetype"]]
        if sample["actual"]["level"] not in allowed:
            problems.append(
                f"{sample['id']}：期望等级 {allowed}，实测 {sample['actual']['level_name']}"
            )
    if problems:
        print("合成样本自检未通过：")
        for problem in problems:
            print("  ✗ " + problem)
        return 1

    if args.check:
        if not OUTPUT.exists():
            print(f"缺少 {OUTPUT.relative_to(ROOT)}，先运行生成脚本")
            return 1
        if OUTPUT.read_text(encoding="utf-8") != payload:
            print("幂等自检失败：重新生成的结果与仓库文件不一致")
            return 1
        print(f"幂等自检通过：{OUTPUT.relative_to(ROOT)} 与重新生成结果一致")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(payload, encoding="utf-8")
    print(f"写出 {OUTPUT.relative_to(ROOT)}")
    print(f"  样本 {len(dataset['samples'])} 家：" + "、".join(
        f"{name} {count} 家" for name, count in dataset["composition"].items() if name != "total"
    ))
    for archetype, _, count, _ in ARCHETYPES:
        subset = [s for s in dataset["samples"] if s["archetype"] == archetype]
        scores = [s["actual"]["total_score"] for s in subset]
        levels = sorted({s["actual"]["level_name"] for s in subset})
        hits = sorted({tuple(s["actual"]["antipatterns"]) or ("无",) for s in subset})
        print(
            f"  {archetype}: {count} 家，得分 {min(scores):.1f}—{max(scores):.1f}，"
            f"等级 {'/'.join(levels)}，命中 {'、'.join('/'.join(h) for h in hits)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
