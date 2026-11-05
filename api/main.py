#!/usr/bin/env python3
"""本地开发后端入口。

用法：
    python3 api/main.py
    # 或
    uvicorn advisor.web.api:app --reload --app-dir src
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import uvicorn  # noqa: E402

from advisor.web.api import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
