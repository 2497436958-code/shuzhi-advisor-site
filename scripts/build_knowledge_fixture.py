#!/usr/bin/env python3
"""生成前端冒烟测试用的接口样例。

前端渲染逻辑没有浏览器也要能验证，所以把知识库检索接口的真实响应
截一小份存成 `scripts/fixtures/knowledge_api.json`，
由 `node scripts/check_knowledge_page.mjs` 用作 fetch 桩。

用法：python3 scripts/build_knowledge_fixture.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from advisor.web.api import (
    get_knowledge_cases,
    get_knowledge_papers,
    get_knowledge_patents,
    get_knowledge_policy,
    get_knowledge_stats,
)

OUTPUT = ROOT / "scripts" / "fixtures" / "knowledge_api.json"


def main() -> int:
    payload = {
        "stats": get_knowledge_stats(),
        "policy": get_knowledge_policy(q="验收", limit=3),
        "cases": get_knowledge_cases(q="联网", limit=3),
        "papers": get_knowledge_papers(kind="方法", limit=3),
        "patents": get_knowledge_patents(q="", limit=3),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"写出 {OUTPUT.relative_to(ROOT)}")
    for key in ("policy", "cases", "papers", "patents"):
        print(f"  {key}: total={payload[key]['total']} items={len(payload[key]['items'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
