#!/usr/bin/env python3
"""知识库搬运校验脚本（只读）。

校验目标仓库 `data/knowledge/` 下的 8 个知识库 JSON，并把它们与
`precomputed/*.json` 里已经引用的 CASE-xxx / PATH-xxx 编号做交叉检查。

用法：
    python3 scripts/check_knowledge_port.py
    python3 scripts/check_knowledge_port.py --source-repo /path/to/shuzhi-advisor

退出码：0 = 无 ERROR；1 = 存在 ERROR（缺文件 / 非法 JSON / 编号对不上等）；
WARNING 不影响退出码。

只依赖标准库。本脚本不写入任何文件。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = REPO_ROOT / "data" / "knowledge"
PRECOMPUTED_DIR = REPO_ROOT / "precomputed"

# 8 个必须存在的知识库文件 -> 该文件里"条目"的取法
KNOWLEDGE_FILES = {
    "policy.json": "list",
    "cases.json": "list",
    "case_ids.json": "dict",
    "centers.json": "list",
    "elasticity.json": "list",
    "papers.json": "list",
    "patents.json": "dict",
    "patent_center_cross.json": "dict",
}

# 归因路径表：优先看目标仓库自带，其次看源仓库（只读）
REL_PATHS_PY = Path("src/advisor/knowledge/paths.py")
DEFAULT_SOURCE_REPO = Path(
    "/Users/xx/Documents/Codex/2026-11-05/fan-hu/work/shuzhi-advisor"
)

CASE_ID_RE = re.compile(r"CASE-\d{3}")
PATH_ID_RE = re.compile(r"PATH-\d{3}")
PATH_DEF_RE = re.compile(r'id="(PATH-\d{3})"')
CASE_REFS_RE = re.compile(r"case_refs=\(([^)]*)\)", re.S)

# 政策条目的必填字段
POLICY_REQUIRED = ("doc_no", "issuer", "publish_date", "url")
# 案例条目的必填字段（不含 root_cause —— 它在归因路径层，见下方说明）
CASE_REQUIRED = ("id", "source_type", "title", "evidence", "extracted")
# 案例的 actions 子项必填字段
ACTION_REQUIRED = ("action", "target_scenario")

errors: list[str] = []
warnings: list[str] = []
notes: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def note(msg: str) -> None:
    notes.append(msg)


def walk_strings(node):
    """递归产出 JSON 里的所有字符串。"""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from walk_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk_strings(v)


def count_entries(name: str, data) -> int:
    """按文件语义给出条目数。"""
    if name == "patents.json":
        cats = data.get("categories") or []
        return len(cats)
    if name == "patent_center_cross.json":
        rows = data.get("rows") or []
        return len(rows)
    if name == "case_ids.json":
        return len(data)
    return len(data)


# ---------------------------------------------------------------- 1. 加载知识库


def load_knowledge() -> dict:
    loaded = {}
    for name, kind in KNOWLEDGE_FILES.items():
        path = KNOWLEDGE_DIR / name
        if not path.exists():
            err(f"缺失文件：data/knowledge/{name}")
            continue
        if path.stat().st_size == 0:
            err(f"文件为空：data/knowledge/{name}")
            continue
        try:
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            err(f"非法 JSON：data/knowledge/{name} -> {exc}")
            continue
        except OSError as exc:
            err(f"读取失败：data/knowledge/{name} -> {exc}")
            continue
        if kind == "list" and not isinstance(data, list):
            err(f"结构不符：data/knowledge/{name} 期望顶层数组，实际 {type(data).__name__}")
            continue
        if kind == "dict" and not isinstance(data, dict):
            err(f"结构不符：data/knowledge/{name} 期望顶层对象，实际 {type(data).__name__}")
            continue
        loaded[name] = data
    return loaded


# ---------------------------------------------------------------- 2. 路径表解析


def parse_paths_py(path: Path):
    """用正则从 paths.py 里提取 PATH 编号与 case_refs（只读，不 import）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        warn(f"路径表不可读：{path} -> {exc}")
        return None
    ids = sorted(set(PATH_DEF_RE.findall(text)))
    refs = set()
    for group in CASE_REFS_RE.findall(text):
        refs.update(CASE_ID_RE.findall(group))
    return {"ids": ids, "case_refs": refs, "path": path}


def locate_paths_table(source_repo: Path | None):
    local = REPO_ROOT / REL_PATHS_PY
    if local.exists():
        return parse_paths_py(local)
    if source_repo is not None:
        cand = source_repo / REL_PATHS_PY
        if cand.exists():
            return parse_paths_py(cand)
    warn(
        "找不到归因路径表（src/advisor/knowledge/paths.py）："
        "目标仓库没有，源仓库路径也不可用；PATH-xxx 交叉检查已跳过"
    )
    return None


# ---------------------------------------------------------------- 3. 各类检查


def check_cases(cases):
    """返回 (case_ids:set, synthetic_counter)。"""
    ids = []
    dup = Counter()
    synthetic = Counter()
    missing_root_cause = []
    missing_actions = []
    for entry in cases:
        cid = entry.get("id")
        if not isinstance(cid, str) or not CASE_ID_RE.fullmatch(cid):
            err(f"案例 id 不合法：{cid!r}（应形如 CASE-001）")
        else:
            ids.append(cid)
            dup[cid] += 1

        for field in CASE_REQUIRED:
            if field not in entry or entry[field] in (None, "", [], {}):
                err(f"案例 {cid} 缺少必填字段 {field}")

        if not entry.get("source_type"):
            err(f"案例 {cid} 缺少 source_type")
        else:
            src_type = entry["source_type"]
            synth = bool((entry.get("extracted") or {}).get("synthetic", False))
            synthetic["synthetic" if synth else "real"] += 1
            synthetic[f"source_type:{src_type}"] += 1

        if "root_cause" not in entry:
            missing_root_cause.append(cid)

        actions = entry.get("actions")
        if not actions:
            missing_actions.append(cid)
        else:
            for i, act in enumerate(actions):
                for field in ACTION_REQUIRED:
                    if not act.get(field):
                        err(f"案例 {cid} actions[{i}] 缺少 {field}")
                ts = act.get("target_scenario")
                if ts and not re.fullmatch(r"S\d{2}", str(ts)):
                    err(f"案例 {cid} actions[{i}] target_scenario 非法：{ts!r}")
                for item in act.get("target_items") or []:
                    if not isinstance(item, int) or not (1 <= item <= 15):
                        err(f"案例 {cid} actions[{i}] target_items 越界：{item!r}")

        ev = entry.get("evidence") or {}
        if not ev.get("url"):
            err(f"案例 {cid} 缺少 evidence.url")

        ext = entry.get("extracted") or {}
        if "synthetic" not in ext:
            err(f"案例 {cid} 缺少 extracted.synthetic 标记")
        if not ext.get("by") or not ext.get("at"):
            err(f"案例 {cid} 的 extracted 缺少 by/at")

    for cid, n in sorted(dup.items()):
        if n > 1:
            err(f"案例 id 重复：{cid} 出现 {n} 次")

    if missing_root_cause:
        warn(
            f"{len(missing_root_cause)}/{len(cases)} 条案例没有 root_cause 字段"
            f"（如 {missing_root_cause[0]}）——按源仓库设计，根因写在归因路径层"
            "（paths.py），案例层只留症状与动作；若下游要求案例层自带 root_cause 需回源仓库补齐"
        )
    if missing_actions:
        warn(
            f"{len(missing_actions)} 条案例没有 actions：{missing_actions}——"
            "集合级条目（如 CASE-901 链式案例集）本就无单条动作"
        )
    return set(ids), synthetic


def check_policy(policies):
    for entry in policies:
        pid = entry.get("id", "<无 id>")
        for field in POLICY_REQUIRED:
            if not entry.get(field):
                err(f"政策 {pid} 缺少必填字段 {field}")
        if not entry.get("title"):
            err(f"政策 {pid} 缺少 title")
        if not entry.get("key_provisions"):
            warn(f"政策 {pid} 没有 key_provisions（原文摘录）")


def check_papers(papers):
    """论文库条目校验。

    `type == "检索入口"` 的条目是检索式登记（未取得全文），按源仓库口径
    不要求 doi/year，改判为 WARNING；其余条目缺 doi/year 判 ERROR。
    """
    for entry in papers:
        pid = entry.get("id", "<无 id>")
        is_entry_point = entry.get("type") == "检索入口"
        for field in ("title", "url", "claim"):
            if not entry.get(field):
                err(f"论文 {pid} 缺少必填字段 {field}")
        for field in ("year", "doi"):
            if entry.get(field) in (None, "", "—"):
                if is_entry_point:
                    warn(f"论文 {pid}（检索入口）没有 {field}——按源仓库口径如实登记检索式，不伪造文献")
                else:
                    err(f"论文 {pid} 缺少必填字段 {field}")


def check_patents(patents):
    cats = patents.get("categories") or []
    if not cats:
        err("专利库 categories 为空")
    for cat in cats:
        cid = cat.get("id", "<无 id>")
        if not cat.get("category"):
            err(f"专利类别 {cid} 缺少 category")
        if not cat.get("keywords"):
            err(f"专利类别 {cid} 缺少 keywords")
        for sc in cat.get("maps_to_scenarios") or []:
            if not re.fullmatch(r"S\d{2}", str(sc)):
                err(f"专利类别 {cid} maps_to_scenarios 非法：{sc!r}")
        if cat.get("applications_cn") is None or cat.get("grants_cn") is None:
            note(f"专利类别 {cid} 未取数（applications_cn/grants_cn 为 null，按源仓库口径标注待人工检索）")


def check_centers(centers):
    for entry in centers:
        cid = entry.get("id", "<无 id>")
        if not entry.get("name"):
            err(f"中心 {cid} 缺少 name")
        src = entry.get("source") or {}
        if not src.get("page_url"):
            err(f"中心 {cid} 缺少 source.page_url")


def check_elasticity(elasticity, case_ids):
    for entry in elasticity:
        item = entry.get("item")
        for field in ("metric", "low", "high", "n_cases", "supported", "basis"):
            if field not in entry:
                err(f"弹性条目 item={item} 缺少字段 {field}")
        for ref in entry.get("case_refs") or []:
            if ref not in case_ids:
                err(f"弹性条目 item={item} 引用了案例库中不存在的 {ref}")


def check_case_ids(case_ids_map, case_ids):
    """case_ids.json: source_id -> {id, title}，其中 id 必须能在 cases.json 里查到。"""
    for source_id, meta in case_ids_map.items():
        if not isinstance(meta, dict) or "id" not in meta:
            err(f"case_ids.json 条目 {source_id} 结构异常（应为 {{id,title}}）")
            continue
        if meta["id"] not in case_ids:
            err(f"case_ids.json 的 {source_id} 指向案例库中不存在的 {meta['id']}")


# ---------------------------------------------------------------- 4. 交叉检查


def collect_precomputed_refs():
    """从 precomputed/*.json 里收集引用到的 CASE-xxx / PATH-xxx。"""
    case_refs = {}   # ref -> set(filename)
    path_refs = {}
    if not PRECOMPUTED_DIR.is_dir():
        err(f"预计算目录不存在：{PRECOMPUTED_DIR}")
        return case_refs, path_refs
    for path in sorted(PRECOMPUTED_DIR.glob("*.json")):
        try:
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            err(f"预计算文件不可读：{path.name} -> {exc}")
            continue
        for s in walk_strings(data):
            for ref in set(CASE_ID_RE.findall(s)):
                case_refs.setdefault(ref, set()).add(path.name)
            for ref in set(PATH_ID_RE.findall(s)):
                path_refs.setdefault(ref, set()).add(path.name)
    return case_refs, path_refs


# ---------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description="校验知识库搬运结果（只读）")
    parser.add_argument(
        "--source-repo",
        type=Path,
        default=DEFAULT_SOURCE_REPO,
        help="源仓库路径，用于读取归因路径表 paths.py（只读）",
    )
    args = parser.parse_args()

    print("=" * 72)
    print("知识库搬运校验")
    print(f"目标仓库：{REPO_ROOT}")
    print("=" * 72)

    knowledge = load_knowledge()
    counts = {}
    for name in KNOWLEDGE_FILES:
        if name in knowledge:
            counts[name] = count_entries(name, knowledge[name])

    print("\n[1] 文件存在性与 JSON 合法性")
    for name in KNOWLEDGE_FILES:
        if name in knowledge:
            size = (KNOWLEDGE_DIR / name).stat().st_size
            print(f"  OK   data/knowledge/{name}  {size} bytes, {counts[name]} 条")
        else:
            print(f"  FAIL data/knowledge/{name}  缺失或不可解析")

    print("\n[2] 各库条目数")
    for name, n in counts.items():
        print(f"  {name:<26} {n}")

    cases = knowledge.get("cases.json") or []
    case_ids = set()
    synthetic = Counter()
    if cases:
        case_ids, synthetic = check_cases(cases)
    if "policy.json" in knowledge:
        check_policy(knowledge["policy.json"])
    if "papers.json" in knowledge:
        check_papers(knowledge["papers.json"])
    if "patents.json" in knowledge:
        check_patents(knowledge["patents.json"])
    if "centers.json" in knowledge:
        check_centers(knowledge["centers.json"])
    if "elasticity.json" in knowledge:
        check_elasticity(knowledge["elasticity.json"], case_ids)
    if "case_ids.json" in knowledge:
        check_case_ids(knowledge["case_ids.json"], case_ids)

    print("\n[3] 真实层 / 合成层分层统计（按 extracted.synthetic）")
    print(f"  真实条目（synthetic != true）：{synthetic.get('real', 0)}")
    print(f"  合成条目（synthetic == true）：{synthetic.get('synthetic', 0)}")
    for key in sorted(k for k in synthetic if k.startswith("source_type:")):
        print(f"    {key:<28} {synthetic[key]}")

    print("\n[4] 与 precomputed/*.json 的编号交叉检查")
    case_refs, path_refs = collect_precomputed_refs()
    paths_table = locate_paths_table(args.source_repo)

    print(f"  precomputed 引用到的 CASE 编号：{len(case_refs)} 个")
    for ref in sorted(case_refs):
        mark = "OK  " if ref in case_ids else "FAIL"
        where = ",".join(sorted(case_refs[ref]))
        if mark == "FAIL":
            err(f"precomputed 引用了案例库中不存在的 {ref}（出现于 {where}）")
        print(f"    {mark} {ref}  <- {where}")

    print(f"  precomputed 引用到的 PATH 编号：{len(path_refs)} 个")
    known_paths = set(paths_table["ids"]) if paths_table else set()
    if paths_table:
        print(f"    路径表来源：{paths_table['path']}（{len(known_paths)} 条路径）")
    for ref in sorted(path_refs):
        where = ",".join(sorted(path_refs[ref]))
        if paths_table is None:
            print(f"    SKIP {ref}  <- {where}")
            continue
        if ref not in known_paths:
            err(f"precomputed 引用了路径表中不存在的 {ref}（出现于 {where}）")
            print(f"    FAIL {ref}  <- {where}")
        else:
            print(f"    OK   {ref}  <- {where}")

    if paths_table:
        print(f"\n  路径表 case_refs 覆盖：{len(paths_table['case_refs'])} 个 CASE 编号")
        for ref in sorted(paths_table["case_refs"]):
            if ref not in case_ids:
                err(f"路径表引用了案例库中不存在的 {ref}")
                print(f"    FAIL {ref}")

    print("\n[5] 发现的不一致")
    if errors:
        for i, msg in enumerate(errors, 1):
            print(f"  ERROR   {i}. {msg}")
    else:
        print("  （无 ERROR）")
    if warnings:
        for i, msg in enumerate(warnings, 1):
            print(f"  WARNING {i}. {msg}")
    else:
        print("  （无 WARNING）")
    if notes:
        print("\n[6] 备注（不判错）")
        for i, msg in enumerate(notes, 1):
            print(f"  NOTE {i}. {msg}")

    summary = {
        "status": "FAIL" if errors else "PASS",
        "files": {
            name: {"present": name in knowledge, "entries": counts.get(name)}
            for name in KNOWLEDGE_FILES
        },
        "cases": {
            "total": len(cases),
            "unique_ids": len(case_ids),
            "real": synthetic.get("real", 0),
            "synthetic": synthetic.get("synthetic", 0),
        },
        "precomputed_case_refs": sorted(case_refs),
        "precomputed_path_refs": sorted(path_refs),
        "path_table_size": len(known_paths) if paths_table else None,
        "errors": errors,
        "warnings": warnings,
        "notes": notes,
    }
    print("\n===JSON===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
