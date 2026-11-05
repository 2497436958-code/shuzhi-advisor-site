#!/usr/bin/env python3
"""检查工作区与远端同步状态。

配合手册第 7 节第 7 条使用：每完成一项任务就推送，不允许把已完成的工作
只留在本地磁盘。

用法：
    python3 scripts/check_push_state.py            # 检查当前分支
    python3 scripts/check_push_state.py --all      # 检查所有本地分支

退出码 0 表示已推送且工作区干净；1 表示有未推送提交或有未提交改动。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.strip()


def status_lines() -> list[str]:
    output = git("status", "--porcelain")
    return [line for line in output.split("\n") if line.strip()]


def unpushed(branch: str) -> int:
    upstream = git("rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}")
    if not upstream:
        return -1
    count = git("rev-list", "--count", f"{upstream}..{branch}")
    return int(count) if count.isdigit() else -1


def main() -> int:
    check_all = "--all" in sys.argv
    current = git("rev-parse", "--abbrev-ref", "HEAD")
    branches = (
        [line.split(" ")[0] for line in git("branch", "--format=%(refname:short)").split("\n") if line]
        if check_all
        else [current]
    )

    problems = 0
    for branch in branches:
        count = unpushed(branch)
        if count == -1:
            print(f"  {branch}: 没有上游分支，需要第一次推送")
            problems += 1
        elif count:
            print(f"  {branch}: 有 {count} 个未推送提交")
            problems += 1
        else:
            print(f"  {branch}: 已与远端同步")

    dirty = status_lines()
    if dirty:
        problems += 1
        print(f"  工作区有 {len(dirty)} 处未提交改动：")
        for line in dirty[:10]:
            print(f"    {line}")
    else:
        print("  工作区干净")

    if problems:
        print("\n未通过：先把成果提交并推送，再结束本轮任务。")
        return 1
    print("\n通过：工作区干净，成果已在远端。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
