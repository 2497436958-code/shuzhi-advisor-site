#!/usr/bin/env python3
"""本地开发后端入口。

用法：
    python3 api/main.py
    # 或
    uvicorn advisor.web.api:app --reload --app-dir src

环境变量（见 docs/deployment.md）：
    ADVISOR_HOST          监听地址，默认 127.0.0.1
    ADVISOR_PORT          监听端口，默认 8000
    ADVISOR_CORS_ORIGINS  允许跨域的前端来源，逗号分隔；默认空 = 不同源不开放
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import uvicorn  # noqa: E402

from advisor.web.api import app  # noqa: E402

if __name__ == "__main__":
    host = os.environ.get("ADVISOR_HOST", "127.0.0.1")
    port = int(os.environ.get("ADVISOR_PORT", "8000"))
    print(f"数改指导智能体后端：http://{host}:{port}/（Ctrl+C 退出）")
    uvicorn.run(app, host=host, port=port)
