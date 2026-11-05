"""四类投入无效模式（反模式）检测。

判据出处：工信厅企业〔2024〕56 号 附件（一）采集项 2/3/4/5/11，
附件（二）应用场景等级判定。四条判据与主控文档第 8 节一致，模型不得改写。

- AP1 只买设备不联网：采集项 2 达到 (40%,60%] 或以上，且采集项 3 落在 (10%,20%] 或以下。
- AP2 只上系统不跑流程：采集项 5 覆盖绝大部分业务环节或全覆盖，且生产管控或质量管理仍在一级。
- AP3 只做数据采集不做分析：采集项 4 覆盖环节数不少于 6，且决策支持场景仍在一级。
- AP4 只追补贴不建能力：采集项 11 达到 (20%,40%] 或以上，且总分不够二级（<40 分）。

每条判据只给"命中/不命中"两态，可解释、可复核。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

BAND_0_10 = "[0-10%]"
BAND_10_20 = "(10%,20%]"
BAND_20_40 = "(20%,40%]"
BAND_40_60 = "(40%,60%]"
BAND_60_100 = "(60%,100%]"

HIGH_SPEND_BANDS = (BAND_20_40, BAND_40_60, BAND_60_100)
HIGH_DEVICE_BANDS = (BAND_40_60, BAND_60_100)
LOW_NETWORK_BANDS = (BAND_0_10, BAND_10_20)
FULL_COVERAGE = ("绝大部分业务环节（大于80%）", "全覆盖")

BASIS_KIND = "本项目构造的判据（拼自官方采集项与附件（二）场景判定），非官方口径"

AP_BASIS = {
    "AP1": "采集项 2 设备数字化率 ≥(40%,60%] 且 采集项 3 设备联网率 ≤(10%,20%]",
    "AP2": "采集项 5 覆盖绝大部分业务环节或全覆盖，但生产管控／质量管理场景仍为一级",
    "AP3": "采集项 4 自动采集覆盖环节数 ≥6，但决策支持场景仍为一级",
    "AP4": "采集项 11 数字化投入占营业额 ≥(20%,40%]，但总分 <40 分（够不到二级规范级）",
}

AP_NAME = {
    "AP1": "只买设备不联网",
    "AP2": "只上系统不跑流程",
    "AP3": "只做数据采集不做分析",
    "AP4": "只追补贴不建能力",
}


@dataclass(frozen=True)
class AntipatternHit:
    pattern_id: str
    name: str
    basis: str
    evidence: str
    hit_items: tuple[int, ...]
    hit_scenarios: tuple[str, ...]
    basis_kind: str = BASIS_KIND

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "basis": self.basis,
            "evidence": self.evidence,
            "hit_items": list(self.hit_items),
            "hit_scenarios": list(self.hit_scenarios),
            "basis_kind": self.basis_kind,
        }


def _selected(evaluation: dict[str, Any], item_id: int) -> list[str]:
    for item in evaluation["item_results"]:
        if item["id"] == item_id:
            return list(item["selected"])
    raise KeyError(f"评测结果里没有采集项 {item_id}")


def _scenario_id(criteria: dict[str, Any], name: str) -> str:
    for scenario in criteria["scenarios"]:
        if scenario["name"] == name:
            return scenario["id"]
    raise KeyError(f"官方 16 个场景中找不到 {name!r}")


def detect_antipatterns(
    evaluation: dict[str, Any], criteria: dict[str, Any]
) -> list[AntipatternHit]:
    """在评测结果上跑四条反模式判据。"""
    hits: list[AntipatternHit] = []
    levels = evaluation.get("scenario_levels") or {}
    selected = {item["id"]: list(item["selected"]) for item in evaluation["item_results"]}

    # AP1 只买设备不联网
    digital = selected[2][0]
    networked = selected[3][0]
    if digital in HIGH_DEVICE_BANDS and networked in LOW_NETWORK_BANDS:
        hits.append(
            AntipatternHit(
                pattern_id="AP1",
                name=AP_NAME["AP1"],
                basis=AP_BASIS["AP1"],
                evidence=f"设备数字化率 {digital}，设备联网率 {networked}",
                hit_items=(2, 3),
                hit_scenarios=(_scenario_id(criteria, "设备管理"),),
            )
        )

    # AP2 只上系统不跑流程
    coverage = selected[5][0]
    if coverage in FULL_COVERAGE:
        weak = [
            name
            for name in ("生产管控", "质量管理")
            if levels.get(_scenario_id(criteria, name), 1) <= 1
        ]
        if weak:
            hits.append(
                AntipatternHit(
                    pattern_id="AP2",
                    name=AP_NAME["AP2"],
                    basis=AP_BASIS["AP2"],
                    evidence=f"覆盖 {coverage}；{'、'.join(weak)} 场景仍在一级",
                    hit_items=(5,),
                    hit_scenarios=tuple(_scenario_id(criteria, name) for name in weak),
                )
            )

    # AP3 只做数据采集不做分析
    collected = [option for option in selected[4] if option != "无"]
    if len(collected) >= 6 and levels.get(_scenario_id(criteria, "决策支持"), 1) <= 1:
        hits.append(
            AntipatternHit(
                pattern_id="AP3",
                name=AP_NAME["AP3"],
                basis=AP_BASIS["AP3"],
                evidence=f"已覆盖 {len(collected)} 个环节；决策支持场景仍在一级",
                hit_items=(4,),
                hit_scenarios=(_scenario_id(criteria, "决策支持"),),
            )
        )

    # AP4 只追补贴不建能力
    spend = selected[11][0]
    if spend in HIGH_SPEND_BANDS and evaluation["total_score"] < 40:
        hits.append(
            AntipatternHit(
                pattern_id="AP4",
                name=AP_NAME["AP4"],
                basis=AP_BASIS["AP4"],
                evidence=f"投入占比 {spend}；总分 {evaluation['total_score']:.1f}（够不到二级规范级）",
                hit_items=(11,),
                hit_scenarios=(),
            )
        )

    return hits
