"""前端可访问性守门（T057）。

三件事：
1. 配色对比度达到 WCAG AA（脚本实算，不是人工看）；
2. 关键控件有可访问名称（aria-label / role / scope）；
3. 键盘可达的基本条件在（跳转链接、焦点样式、语义化标签）。
"""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ContrastTests(unittest.TestCase):
    def test_contrast_passes_wcag_aa(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_contrast.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class MarkupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.js = (ROOT / "app.js").read_text(encoding="utf-8")
        cls.css = (ROOT / "styles.css").read_text(encoding="utf-8")

    def test_skip_link_and_landmarks(self):
        self.assertIn('class="skip-link"', self.html)
        self.assertIn("<main id=\"main\">", self.html)
        self.assertIn('href="#main"', self.html)

    def test_focus_is_visible(self):
        self.assertIn(":focus-visible", self.css)

    def test_form_controls_have_accessible_names(self):
        self.assertIn('"aria-label": `采集项', self.js)
        self.assertIn('"aria-label": `场景', self.js)
        self.assertIn('"aria-label": meta.title + "检索"', self.js)

    def test_groups_are_marked_up(self):
        self.assertIn('role: "radiogroup"', self.js)
        self.assertIn('role: "group"', self.js)
        self.assertIn('scope: "col"', self.js)

    def test_live_regions(self):
        self.assertIn('role="status"', self.html)

    def test_mobile_breakpoint_covers_new_blocks(self):
        self.assertIn("@media (max-width: 720px)", self.css)
        self.assertIn(".navlink", self.css)

    def test_no_aria_labelledby_to_missing_ids(self):
        """aria-labelledby / aria-controls 指向的 id 必须真实存在。"""
        import re

        ids = set(re.findall(r'id="([^"]+)"', self.html))
        for attr in ("aria-labelledby", "aria-controls"):
            for value in re.findall(attr + r'="([^"]+)"', self.html + self.js):
                for token in value.split():
                    if token.startswith("#"):
                        token = token[1:]
                    self.assertIn(token, ids, f"{attr} 指向不存在的 id：{token}")


if __name__ == "__main__":
    unittest.main()
