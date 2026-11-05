"""交付文档守门：口径、合规声明与演示脚本不能缺项。

文档最容易在赶工时被删掉或改漏，所以把必须出现的内容写成用例。
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DemoScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo = (ROOT / "docs/demo.md").read_text(encoding="utf-8")

    def test_demo_script_has_all_steps(self):
        for heading in ("第 1 步 · 定位", "第 2 步 · 问题", "第 3 步 · 输入",
                        "第 4 步 · 诊断", "第 5 步 · 路径与排序",
                        "第 6 步 · 不建议做", "第 7 步 · 评测", "第 8 步 · 边界"):
            self.assertIn(heading, self.demo, heading)

    def test_demo_numbers_match_published_samples(self):
        """演示脚本里的数字必须与样例一致，不能凭记忆写。"""
        for number in ("51.95", "规范级", "AP1", "(60%,100%]", "[0-10%]",
                       "S08", "67.8%", "0 家"):
            self.assertIn(number, self.demo, number)

    def test_demo_states_honest_limits(self):
        self.assertIn("不承诺补贴获批", self.demo)
        self.assertIn("不承接申报代理", self.demo)
        self.assertIn("未达标", self.demo)
        self.assertIn("不可测", self.demo)
        self.assertIn("真实层", self.demo)

    def test_demo_has_fallback(self):
        self.assertIn("兜底方案", self.demo)
        self.assertIn("预计算结果（非实时计算）", self.demo)


class DeploymentDocTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.deployment = (ROOT / "docs/deployment.md").read_text(encoding="utf-8")

    def test_env_vars_documented(self):
        for name in ("ADVISOR_HOST", "ADVISOR_PORT", "ADVISOR_CORS_ORIGINS"):
            self.assertIn(name, self.deployment, name)

    def test_warns_about_public_site(self):
        self.assertIn("公开", self.deployment)
        self.assertIn("不要提交进这个公开仓库", self.deployment)

    def test_cors_guidance_is_specific(self):
        self.assertIn("不同源不开放", self.deployment)
        self.assertIn("不要写", self.deployment)


class KnowledgeSourceDocTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = (ROOT / "docs/knowledge_sources.md").read_text(encoding="utf-8")

    def test_citation_dimensions_documented(self):
        for dimension in ("来源", "日期", "用途", "回查"):
            self.assertIn(dimension, self.doc, dimension)

    def test_known_gaps_are_registered(self):
        for gap in ("39 条没有来源发布日期", "3 条是检索入口", "5 个分类的小类数量未取到"):
            self.assertIn(gap, self.doc, gap)

    def test_schemas_exist(self):
        for name in ("policy", "case", "paper", "patent"):
            path = ROOT / "docs" / "schemas" / f"{name}.schema.json"
            self.assertTrue(path.exists(), path)
            import json as _json
            schema = _json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(schema.get("required"), name)


class FooterTests(unittest.TestCase):
    def test_footer_has_disclaimer(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("免责与边界", html)
        for statement in ("不承诺补贴获批", "不承接申报代理", "不替代企业自身的判断"):
            self.assertIn(statement, html, statement)


if __name__ == "__main__":
    unittest.main()
