#!/usr/bin/env python3
"""检查站点配色对比度（WCAG 2.1 AA）。

颜色取自 `styles.css` 的 CSS 变量（浅色与深色两套），按下面对组合算对比度：
正文与辅助文字按 4.5:1，大字/图标/边框按 3:1。

用法：python3 scripts/check_contrast.py
退出码 0 表示全部达标。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "styles.css"

# (前景变量, 背景变量, 最低对比度, 说明)
PAIRS = [
    ("--ink", "--bg", 4.5, "正文 / 页面底色"),
    ("--ink", "--bg-2", 4.5, "正文 / 次级底色"),
    ("--ink-2", "--bg", 4.5, "次级正文 / 页面底色"),
    ("--ink-2", "--bg-2", 4.5, "次级正文 / 次级底色"),
    ("--muted", "--bg", 4.5, "辅助文字 / 页面底色"),
    ("--muted", "--bg-2", 4.5, "辅助文字 / 次级底色"),
    ("--accent", "--bg", 4.5, "强调文字 / 页面底色"),
    ("--accent", "--accent-weak", 4.5, "强调标签 / 标签底色"),
    ("--good", "--good-weak", 4.5, "达标标签 / 标签底色"),
    ("--warn", "--warn-weak", 4.5, "警示标签 / 标签底色"),
    ("--bad", "--bad-weak", 4.5, "否定标签 / 标签底色"),
    ("--line-input", "--bg", 3.0, "输入控件边框 / 页面底色"),
    ("--line-input", "--bg-2", 3.0, "输入控件边框 / 次级底色"),
]


def parse_tokens(css: str) -> dict[str, dict[str, str]]:
    """取出 :root 与深色偏好两套变量。"""
    tokens: dict[str, dict[str, str]] = {}
    for block in re.finditer(r"(:root)\s*\{(.*?)\}", css, re.S):
        name = "light"
        body = block.group(2)
        if "@media" in css[: block.start()].rsplit("}", 1)[-1]:
            name = "dark"
        for key, value in re.findall(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})", body):
            tokens.setdefault(name, {})[key] = value
    # 深色块在 media 查询里，单独再取一次
    dark_block = re.search(r"@media \(prefers-color-scheme: dark\)\s*\{\s*:root\s*\{(.*?)\}", css, re.S)
    if dark_block:
        for key, value in re.findall(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})", dark_block.group(1)):
            tokens.setdefault("dark", {})[key] = value
    return tokens


def luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    r, g, b = (int(value[i: i + 2], 16) / 255 for i in (0, 2, 4))
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def ratio(foreground: str, background: str) -> float:
    a, b = luminance(foreground), luminance(background)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def main() -> int:
    css = CSS.read_text(encoding="utf-8")
    tokens = parse_tokens(css)
    if "light" not in tokens or "dark" not in tokens:
        print("未能从 styles.css 解析出两套配色")
        return 1

    failures = 0
    for scheme in ("light", "dark"):
        palette = tokens[scheme]
        print(f"== {scheme} ==")
        for fg, bg, minimum, label in PAIRS:
            if fg not in palette or bg not in palette:
                print(f"  ? {label}: 变量缺失（{fg} / {bg}）")
                failures += 1
                continue
            value = ratio(palette[fg], palette[bg])
            mark = "✓" if value >= minimum else "✗"
            if value < minimum:
                failures += 1
            print(f"  {mark} {label:24s} {value:5.2f}:1（要求 ≥{minimum}）")
    print()
    if failures:
        print(f"未通过：{failures} 处对比度不足")
        return 1
    print("通过：所有配色组合达到 WCAG AA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
