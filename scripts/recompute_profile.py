#!/usr/bin/env python3
"""复算任意画像 JSON 的评测得分与等级。

用法：
    python3 scripts/recompute_profile.py path/to/profile.json
    python3 scripts/recompute_profile.py precomputed/ap1_只买设备不联网.json --payload
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from advisor.scoring.engine import evaluate_profile, load_criteria  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", type=Path, help="画像 JSON 或预计算 payload JSON")
    parser.add_argument("--payload", action="store_true", help="输入为 precomputed payload，自动取 profile 字段")
    parser.add_argument("--criteria", type=Path, default=ROOT / "precomputed/criteria.json")
    args = parser.parse_args()

    data = json.loads(args.profile.read_text(encoding="utf-8"))
    profile = data["profile"] if args.payload else data
    criteria = load_criteria(args.criteria)
    result = evaluate_profile(profile, criteria)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
