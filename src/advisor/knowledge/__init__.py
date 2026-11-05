"""知识库检索层：政策、案例、论文、专利四个库的检索接口。

与 ``advisor.reasoning`` 的分工：推理层负责"规则匹配 + 证据组织"，
本层只负责"按用户输入检索知识条目"，不产生任何结论。

四个检索函数返回同一种结构::

    {
        "total": int,     # 过滤后、分页前的命中总数
        "returned": int,  # 本次实际返回条数
        "offset": int,
        "limit": int,
        "items": [...],   # 原样条目，不裁字段、不改内容
        "facets": {...},  # 分面计数，基于过滤后的集合
    }
"""

from .search import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    search_cases,
    search_papers,
    search_patents,
    search_policy,
)

__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "search_cases",
    "search_papers",
    "search_patents",
    "search_policy",
]
