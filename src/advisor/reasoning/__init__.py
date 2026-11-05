"""推理层：诊断、归因路径、投入产出排序、反模式与证据链。

分层原则（与主控文档一致）：
- 算分、定级由 ``advisor.scoring.engine`` 负责，本层不重复实现；
- 本层只做"规则匹配 + 证据组织"，不做自由文本生成；
- 每条结论必须带证据链，缺证据不允许输出（见 ``evidence.ensure_evidence``）。
"""

from .antipatterns import AntipatternHit, detect_antipatterns
from .diagnosis import build_diagnosis
from .knowledge import Knowledge, load_knowledge
from .pathway import build_pathway
from .pipeline import build_result
from .ranking import build_ranking

__all__ = [
    "AntipatternHit",
    "Knowledge",
    "build_diagnosis",
    "build_pathway",
    "build_ranking",
    "detect_antipatterns",
    "load_knowledge",
    "build_result",
]
