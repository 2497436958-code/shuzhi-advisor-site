"""评测层：对照、消融、指标与报告。

对应主控文档 T039—T048。
分层原则：评测层只做"装配与度量"，不改判据层、不改推理层，
每个对照组/消融组只关掉一项能力，关掉什么写在 ``variants.py`` 的文档字符串里。
"""

from .metrics import compute_metrics
from .runner import run_evaluation, write_reports
from .variants import SYSTEMS, build_conclusion

__all__ = [
    "SYSTEMS",
    "build_conclusion",
    "compute_metrics",
    "run_evaluation",
    "write_reports",
]
