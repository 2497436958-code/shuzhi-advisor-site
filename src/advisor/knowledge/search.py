"""知识库检索：政策、案例、论文、专利四个库的统一检索。

设计原则：

- **只读不改**：检索层不修改输入条目，返回的 ``items`` 是原样条目，
  不裁字段、不改内容、不重排（保持输入顺序，保证结果可复现）；
- **过滤与分页分离**：``total`` 是过滤后、分页前的命中总数，
  ``facets`` 也基于同一份过滤后集合计算（含本维度自身的过滤结果）；
- **检索口径可解释**：关键词命中哪些字段、精确过滤对应哪个字段，
  都在本文件里写明，避免调用方误解结果。

数值字段（如论文年份）统一转成字符串参与匹配，``None`` 视为空串，
不允许因为字段缺失导致检索报错。
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

# 数组字段拼接时的分隔符：用换行，避免跨条目边界产生虚假命中。
_JOIN_SEP = "\n"


def _as_text(value: Any) -> str:
    """把任意值转成可参与匹配的字符串；``None`` 视为空串。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _join(values: Any) -> str:
    """把数组字段拼成一段文本参与匹配。"""
    if not values:
        return ""
    if isinstance(values, (str, bytes)):
        return _as_text(values)
    if isinstance(values, dict):
        return _JOIN_SEP.join(_as_text(item) for item in values.values())
    if not isinstance(values, Iterable):
        return _as_text(values)
    return _JOIN_SEP.join(_as_text(item) for item in values)


def _hits(q: str, fields: Sequence[str]) -> bool:
    """大小写不敏感的子串匹配；``q`` 为空表示不过滤。"""
    needle = _as_text(q).strip().lower()
    if not needle:
        return True
    return any(needle in field.lower() for field in fields)


def _clamp_limit(limit: Any) -> int:
    """``limit`` 裁剪到 ``[1, MAX_LIMIT]``；非法值回落到默认值。"""
    try:
        value = int(limit)
    except (TypeError, ValueError):
        value = DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, value))


def _clamp_offset(offset: Any) -> int:
    """``offset`` 小于 0 视为 0；非法值视为 0。"""
    try:
        value = int(offset)
    except (TypeError, ValueError):
        return 0
    return max(0, value)


def _sorted_counts(counts: dict[str, int]) -> dict[str, int]:
    """计数排序：条数降序，同数按键名升序。"""
    return dict(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))


def _facet(items: Sequence[dict], field: str) -> dict[str, int]:
    """单维度计数分布：按条数降序，同数按键名升序。"""
    counts: dict[str, int] = {}
    for item in items:
        key = _as_text(item.get(field))
        counts[key] = counts.get(key, 0) + 1
    return _sorted_counts(counts)


def _paginate(
    items: Sequence[dict],
    limit: Any,
    offset: Any,
    facets: dict[str, dict[str, int]],
) -> dict[str, Any]:
    """统一分页与返回结构。``items`` 保持输入顺序。"""
    total = len(items)
    safe_limit = _clamp_limit(limit)
    safe_offset = _clamp_offset(offset)
    window = list(items[safe_offset : safe_offset + safe_limit])
    return {
        "total": total,
        "returned": len(window),
        "offset": safe_offset,
        "limit": safe_limit,
        "items": window,
        "facets": facets,
    }


def search_policy(
    policy: list[dict],
    q: str = "",
    role: str = "",
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> dict:
    """政策库检索。

    关键词命中字段：``doc_no``、``title``、``issuer``、``role``、
    ``used_where``、``key_provisions``（数组拼成一段）。
    精确过滤：``role``（政策角色，空串不过滤，大小写敏感）。
    分面：``role``。
    """
    filtered: list[dict] = []
    for item in policy or []:
        if role and _as_text(item.get("role")) != role:
            continue
        fields = [
            _as_text(item.get("doc_no")),
            _as_text(item.get("title")),
            _as_text(item.get("issuer")),
            _as_text(item.get("role")),
            _as_text(item.get("used_where")),
            _join(item.get("key_provisions")),
        ]
        if not _hits(q, fields):
            continue
        filtered.append(item)
    return _paginate(filtered, limit, offset, {"role": _facet(filtered, "role")})


def search_cases(
    cases: list[dict],
    q: str = "",
    industry: str = "",
    source_type: str = "",
    scenario: str = "",
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> dict:
    """案例库检索。

    关键词命中字段：``title``、``symptom``、``industry``、``sector``、
    ``collection``、``source_type``、``actions[].action``。
    精确过滤：``industry``、``source_type``、``scenario``
    （命中 ``actions[].target_scenario``，任一动作命中即算命中）；
    三者均为空串时不过滤，大小写敏感。
    分面：``source_type``、``industry``。
    """
    filtered: list[dict] = []
    for item in cases or []:
        if industry and _as_text(item.get("industry")) != industry:
            continue
        if source_type and _as_text(item.get("source_type")) != source_type:
            continue
        actions = item.get("actions") or []
        if scenario and not any(
            _as_text(action.get("target_scenario")) == scenario for action in actions
        ):
            continue
        fields = [
            _as_text(item.get("title")),
            _as_text(item.get("symptom")),
            _as_text(item.get("industry")),
            _as_text(item.get("sector")),
            _as_text(item.get("collection")),
            _as_text(item.get("source_type")),
        ]
        fields.extend(_as_text(action.get("action")) for action in actions)
        if not _hits(q, fields):
            continue
        filtered.append(item)
    return _paginate(
        filtered,
        limit,
        offset,
        {
            "source_type": _facet(filtered, "source_type"),
            "industry": _facet(filtered, "industry"),
        },
    )


def search_papers(
    papers: list[dict],
    q: str = "",
    kind: str = "",
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> dict:
    """论文库检索。

    关键词命中字段：``title``、``authors``、``journal``、``doi``、
    ``claim``、``used_where``、``type``、``tier``。
    精确过滤：``kind``（对应 ``type``，空串不过滤，大小写敏感）。
    分面：``type``、``tier``。
    """
    filtered: list[dict] = []
    for item in papers or []:
        if kind and _as_text(item.get("type")) != kind:
            continue
        fields = [
            _as_text(item.get("title")),
            _as_text(item.get("authors")),
            _as_text(item.get("journal")),
            _as_text(item.get("doi")),
            _as_text(item.get("claim")),
            _as_text(item.get("used_where")),
            _as_text(item.get("type")),
            _as_text(item.get("tier")),
        ]
        if not _hits(q, fields):
            continue
        filtered.append(item)
    return _paginate(
        filtered,
        limit,
        offset,
        {
            "type": _facet(filtered, "type"),
            "tier": _facet(filtered, "tier"),
        },
    )


def search_patents(
    patents: dict,
    q: str = "",
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> dict:
    """专利库检索（按分类检索）。

    关键词命中字段：``category``、``keywords[]``、``ipc[]``、
    ``maps_to_scenarios[]``，以及 ``official_aggregate`` 里的
    ``ipc_class`` / ``ipc_class_desc``。
    精确过滤：本题无独立过滤参数（分类内部字段由关键词覆盖）。
    分面：``ipc_class``（取 ``official_aggregate.ipc_class``，缺失跳过该条）。
    """
    categories = list((patents or {}).get("categories") or [])
    filtered: list[dict] = []
    for item in categories:
        aggregate = item.get("official_aggregate") or {}
        fields = [
            _as_text(item.get("category")),
            _join(item.get("keywords")),
            _join(item.get("ipc")),
            _join(item.get("maps_to_scenarios")),
            _as_text(aggregate.get("ipc_class")),
            _as_text(aggregate.get("ipc_class_desc")),
        ]
        if not _hits(q, fields):
            continue
        filtered.append(item)

    counts: dict[str, int] = {}
    for item in filtered:
        aggregate = item.get("official_aggregate") or {}
        ipc_class = _as_text(aggregate.get("ipc_class"))
        if not ipc_class:
            continue
        counts[ipc_class] = counts.get(ipc_class, 0) + 1
    return _paginate(filtered, limit, offset, {"ipc_class": _sorted_counts(counts)})
