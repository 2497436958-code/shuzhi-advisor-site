#!/usr/bin/env python3
"""检查专利人工检索工作单的完成情况（T035）。

- 未回填：列出待办分类与该跑的检索式；
- 已回填：校验数值类型、小类不超过官方 IPC 大类口径（上限参照）、
  且回填了检索日与检索人。

用法：python3 scripts/check_patent_search.py
退出码 0 表示要么全部完成，要么全部处于"待人工检索"且已如实标注。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATENTS = ROOT / "data" / "knowledge" / "patents.json"
TASKS = ROOT / "data" / "patent_search_tasks.json"


def main() -> int:
    patents = json.loads(PATENTS.read_text(encoding="utf-8"))
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))
    meta = patents.get("meta") or {}
    categories = {item["id"]: item for item in patents.get("categories", [])}

    pending = []
    filled = []
    errors = []
    for task in tasks["tasks"]:
        category = categories.get(task["id"], {})
        applications = category.get("applications_cn")
        grants = category.get("grants_cn")
        if applications is None and grants is None:
            pending.append(task)
            continue
        if not isinstance(applications, int) or not isinstance(grants, int):
            errors.append(f"{task['id']}: 回填的数量必须是整数")
            continue
        if applications < grants:
            errors.append(f"{task['id']}: 授权量 {grants} 大于申请量 {applications}")
        reference = task["official_aggregate_reference"]
        if applications > (reference.get("applications_cn") or 0):
            errors.append(
                f"{task['id']}: 小类申请量 {applications} 超过官方大类口径 "
                f"{reference.get('applications_cn')}，请核对检索式"
            )
        if category.get("status") != "已人工检索":
            errors.append(f"{task['id']}: 已回填数量但 status 不是「已人工检索」")
        if not meta.get("collected_at"):
            errors.append(f"{task['id']}: meta.collected_at（检索日）未填")
        if not meta.get("collected_by"):
            errors.append(f"{task['id']}: meta.collected_by（检索人）未填")
        filled.append(task)

    print(f"专利检索工作单：{len(tasks['tasks'])} 个分类，已回填 {len(filled)}，待人工检索 {len(pending)}")
    if pending:
        print("\n待办（每条都写清了该跑的检索式与要填的字段）：")
        for task in pending:
            queries = "；".join(item["value"] for item in task["queries_to_run"])
            print(f"  {task['id']} {task['category']}")
            print(f"    IPC {task['ipc_class']}（{task['ipc_class_desc']}）  检索式：{queries}")
            print(f"    窗口：{task['search_window']}  入口：{task['search_entry']}")
    if filled:
        print("\n已回填：")
        for task in filled:
            category = categories[task["id"]]
            print(
                f"  {task['id']} 申请 {category['applications_cn']} / 授权 {category['grants_cn']}"
                f"（官方大类 {task['official_aggregate_reference']['ipc_class']} "
                f"申请 {task['official_aggregate_reference']['applications_cn']}）"
            )
    if errors:
        print("\n错误：")
        for message in errors:
            print("  ✗ " + message)
        return 1
    print("\n通过。" + ("仍有待人工检索的分类，已如实标注。" if pending else "全部分类已完成检索并回填。"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
