#!/usr/bin/env python3
"""校验四类知识库的 schema 与引用链完整性（T050）。

两件事分开：
1. **schema 校验**：每条条目按 `docs/schemas/*.json` 校验必填字段与类型；
2. **引用链校验**：主控文档要求「每条引用有来源、日期、用途」，逐库核对这三个维度。

ERROR 会让脚本返回非 0；WARNING 只报告不失败（缺口如实登记，不掩盖也不假装齐全）。
只读，不修改任何数据文件。

用法：python3 scripts/check_knowledge_schema.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "data" / "knowledge"
SCHEMAS = ROOT / "docs" / "schemas"

TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def validate(value: Any, schema: dict[str, Any], path: str) -> list[str]:
    """极简 JSON Schema 校验：够用即可，不引第三方依赖。"""
    errors: list[str] = []
    expected = schema.get("type")
    if expected:
        allowed = expected if isinstance(expected, list) else [expected]
        ok = False
        for name in allowed:
            python_type = TYPE_MAP.get(name)
            if python_type is None:
                ok = True
                break
            if name == "integer" and isinstance(value, bool):
                continue
            if name == "number" and isinstance(value, bool):
                continue
            if isinstance(value, python_type):
                ok = True
                break
        if not ok:
            errors.append(f"{path}: 类型应为 {expected}，实际 {type(value).__name__}")
            return errors

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: 取值应为 {schema['enum']} 之一，实际 {value!r}")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: 长度不足 {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: 不匹配 {schema['pattern']}")

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value or value[key] in (None, ""):
                errors.append(f"{path}: 缺少必填字段 {key}")
        for key, sub in (schema.get("properties") or {}).items():
            if key in value and value[key] is not None:
                errors.extend(validate(value[key], sub, f"{path}.{key}"))

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: 至少需要 {schema['minItems']} 项")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                errors.extend(validate(item, item_schema, f"{path}[{index}]"))

    return errors


def check_citations(library: str, rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """每条引用必须有来源、日期、用途。缺哪维就报哪维。"""
    errors: list[str] = []
    warnings: list[str] = []

    if library == "policy":
        for row in rows:
            missing = [
                name
                for name in ("doc_no", "issuer", "publish_date", "url", "used_where")
                if not row.get(name)
            ]
            if missing:
                errors.append(f"{row.get('id')}: 引用缺 {'、'.join(missing)}")
    elif library == "cases":
        no_source_date = []
        for row in rows:
            if row.get("actions") and not row.get("symptom"):
                errors.append(f"{row.get('id')}: 有改造动作但缺症状描述")
            evidence = row.get("evidence") or {}
            extracted = row.get("extracted") or {}
            if not evidence.get("url") or not evidence.get("doc"):
                errors.append(f"{row.get('id')}: 引用缺原文出处")
            if not extracted.get("at"):
                errors.append(f"{row.get('id')}: 引用缺日期")
            if not row.get("collection"):
                errors.append(f"{row.get('id')}: 引用缺用途（collection）")
            if not re.search(r"(19|20)\d{2}", row.get("collection", "")):
                no_source_date.append(row.get("id"))
        if no_source_date:
            warnings.append(
                f"案例库有 {len(no_source_date)} 条的来源集名不含年份（优秀场景与地方实践），"
                "只有抽取日期没有来源发布日期：" + "、".join(no_source_date[:8]) + " …"
            )
    elif library == "papers":
        for row in rows:
            if not row.get("url"):
                errors.append(f"{row.get('id')}: 引用缺链接")
            if not row.get("used_where"):
                errors.append(f"{row.get('id')}: 引用缺用途")
            if row.get("type") != "检索入口" and not row.get("year"):
                errors.append(f"{row.get('id')}: 文献缺年份")
        entries = [row for row in rows if row.get("type") == "检索入口"]
        if entries:
            warnings.append(
                f"论文库有 {len(entries)} 条是检索入口（无年份与 DOI 属正常），"
                "统计文献数时须按 type 过滤"
            )
    elif library == "patents":
        meta = rows[0] if rows else {}
        if not meta.get("search_entry"):
            errors.append("专利库缺官方检索入口")
        pending = [row for row in rows[1:] if row.get("status") != "已取数"]
        if pending:
            warnings.append(
                f"专利库有 {len(pending)} 个分类的小类数量未取到"
                "（CNIPA 无公开 API），页面与接口只出官方 IPC 大类口径："
                + "、".join(row.get("id", "") for row in pending)
            )
    return errors, warnings


def main() -> int:
    libraries = [
        ("policy", "policy.json", "policy.schema.json"),
        ("cases", "cases.json", "case.schema.json"),
        ("papers", "papers.json", "paper.schema.json"),
    ]
    total_errors = 0
    total_warnings = 0

    for library, data_file, schema_file in libraries:
        rows = json.loads((KNOWLEDGE / data_file).read_text(encoding="utf-8"))
        schema = json.loads((SCHEMAS / schema_file).read_text(encoding="utf-8"))
        errors: list[str] = []
        for row in rows:
            errors.extend(validate(row, schema, row.get("id", "?")))
        cite_errors, cite_warnings = check_citations(library, rows)
        errors.extend(cite_errors)
        print(f"{library}: {len(rows)} 条，schema 错误 {len(errors)}，引用链警告 {len(cite_warnings)}")
        for message in errors[:10]:
            print("  ✗ " + message)
        for message in cite_warnings:
            print("  ! " + message)
        total_errors += len(errors)
        total_warnings += len(cite_warnings)

    patents = json.loads((KNOWLEDGE / "patents.json").read_text(encoding="utf-8"))
    schema = json.loads((SCHEMAS / "patent.schema.json").read_text(encoding="utf-8"))
    errors = []
    for row in patents.get("categories", []):
        errors.extend(validate(row, schema, row.get("id", "?")))
    cite_errors, cite_warnings = check_citations("patents", [patents.get("meta", {})] + patents.get("categories", []))
    errors.extend(cite_errors)
    print(f"patents: {len(patents.get('categories', []))} 个分类，schema 错误 {len(errors)}，引用链警告 {len(cite_warnings)}")
    for message in errors[:10]:
        print("  ✗ " + message)
    for message in cite_warnings:
        print("  ! " + message)
    total_errors += len(errors)
    total_warnings += len(cite_warnings)

    print()
    if total_errors:
        print(f"未通过：{total_errors} 处 schema 错误，{total_warnings} 处引用链警告")
        return 1
    print(f"通过：schema 无错误；{total_warnings} 处引用链缺口已如实登记（见 docs/knowledge_sources.md）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
