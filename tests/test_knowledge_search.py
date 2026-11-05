import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from advisor.knowledge import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    search_cases,
    search_papers,
    search_patents,
    search_policy,
)

ROOT = Path(__file__).resolve().parents[1]

KNOWLEDGE_DIR = ROOT / "data" / "knowledge"


def _load(name):
    return json.loads((KNOWLEDGE_DIR / name).read_text(encoding="utf-8"))


class KnowledgeSearchTests(unittest.TestCase):
    """四个知识库检索函数的契约测试。

    断言用的数字全部来自仓库真实数据（``data/knowledge/*.json``），
    不使用外部网络，也不修改仓库数据文件。
    """

    @classmethod
    def setUpClass(cls):
        cls.policy = _load("policy.json")
        cls.cases = _load("cases.json")
        cls.papers = _load("papers.json")
        cls.patents = _load("patents.json")

    # ---------- 关键词命中 ----------

    def test_policy_keyword_hit(self):
        """政策搜"验收"命中 2 条（命中 title / key_provisions）。"""
        result = search_policy(self.policy, q="验收")
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["returned"], 2)
        self.assertEqual(len(result["items"]), 2)
        for item in result["items"]:
            self.assertIn("验收", item["title"] + "".join(item["key_provisions"]))

    def test_cases_keyword_hit(self):
        """案例搜"联网"命中 88 条（命中 symptom / actions[].action）。"""
        result = search_cases(self.cases, q="联网")
        self.assertEqual(result["total"], 88)
        # 默认 limit=50，因此只返回 50 条，total 仍是过滤后的全量命中数。
        self.assertEqual(result["returned"], DEFAULT_LIMIT)
        self.assertEqual(len(result["items"]), DEFAULT_LIMIT)

        # 放开 limit 后应能取回全部 88 条。
        result = search_cases(self.cases, q="联网", limit=MAX_LIMIT)
        self.assertEqual(result["returned"], 88)
        self.assertEqual(len(result["items"]), 88)

    def test_papers_keyword_hit(self):
        """论文搜"maturity"命中 2 条（命中 title / claim）。"""
        result = search_papers(self.papers, q="maturity")
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["returned"], 2)

    def test_patents_keyword_hit(self):
        """专利搜 IPC 号命中 1 条（命中 ipc[]）。"""
        result = search_patents(self.patents, q="G05B19/418")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["id"], "PATENT-CAT-01")

    def test_patents_keyword_hit_by_category_name(self):
        """专利搜中文类别名命中 1 条（命中 category）。"""
        result = search_patents(self.patents, q="工业软件")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["id"], "PATENT-CAT-01")

    # ---------- 精确过滤 ----------

    def test_policy_role_filter(self):
        result = search_policy(self.policy, role="资金与验收口径")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["role"], "资金与验收口径")

    def test_cases_industry_filter(self):
        result = search_cases(self.cases, industry="电子电器")
        self.assertEqual(result["total"], 44)
        for item in result["items"]:
            self.assertEqual(item["industry"], "电子电器")

    def test_cases_source_type_filter(self):
        result = search_cases(self.cases, source_type="优秀场景")
        self.assertEqual(result["total"], 30)
        for item in result["items"]:
            self.assertEqual(item["source_type"], "优秀场景")

    def test_cases_scenario_filter(self):
        """场景过滤命中 actions[].target_scenario，任一动作命中即算命中。"""
        result = search_cases(self.cases, scenario="S07")
        self.assertEqual(result["total"], 98)
        for item in result["items"]:
            scenarios = [a.get("target_scenario") for a in item["actions"]]
            self.assertIn("S07", scenarios)

    def test_papers_kind_filter(self):
        result = search_papers(self.papers, kind="检索入口")
        self.assertEqual(result["total"], 3)
        for item in result["items"]:
            self.assertEqual(item["type"], "检索入口")

    def test_empty_filter_string_means_no_filter(self):
        """空字符串表示不过滤，不等价于"匹配空值"。"""
        self.assertEqual(search_policy(self.policy, role="")["total"], len(self.policy))
        self.assertEqual(search_cases(self.cases, industry="")["total"], len(self.cases))
        self.assertEqual(
            search_cases(self.cases, source_type="")["total"], len(self.cases)
        )
        self.assertEqual(search_cases(self.cases, scenario="")["total"], len(self.cases))
        self.assertEqual(search_papers(self.papers, kind="")["total"], len(self.papers))

    def test_combined_keyword_and_filter(self):
        """关键词与精确过滤叠加，两者同时生效。"""
        result = search_cases(self.cases, q="联网", industry="电子电器")
        self.assertEqual(result["total"], 8)
        for item in result["items"]:
            self.assertEqual(item["industry"], "电子电器")

        result = search_cases(self.cases, q="联网", scenario="S07")
        self.assertEqual(result["total"], 31)

        result = search_policy(self.policy, q="验收", role="资金与验收口径")
        self.assertEqual(result["total"], 1)

        result = search_papers(self.papers, q="maturity", kind="方法")
        self.assertEqual(result["total"], 2)

    def test_filters_are_case_sensitive(self):
        """精确过滤大小写敏感（用带 ASCII 的合成条目验证）。"""
        tmp_cases = [{"id": "TMP-CS", "title": "临时", "source_type": "TypicalCase"}]
        self.assertEqual(search_cases(tmp_cases, source_type="TypicalCase")["total"], 1)
        self.assertEqual(search_cases(tmp_cases, source_type="typicalcase")["total"], 0)
        self.assertEqual(search_cases(tmp_cases, source_type="TYPICALCASE")["total"], 0)

        tmp_papers = [{"id": "TMP-CS-P", "type": "Method", "title": "临时"}]
        self.assertEqual(search_papers(tmp_papers, kind="Method")["total"], 1)
        self.assertEqual(search_papers(tmp_papers, kind="method")["total"], 0)

        tmp_policy = [{"id": "TMP-CS-PO", "role": "Picking", "title": "临时"}]
        self.assertEqual(search_policy(tmp_policy, role="Picking")["total"], 1)
        self.assertEqual(search_policy(tmp_policy, role="picking")["total"], 0)

    # ---------- 分页 ----------

    def test_pagination_consistency(self):
        result = search_cases(self.cases, limit=10, offset=0)
        self.assertEqual(result["total"], 259)
        self.assertEqual(result["returned"], 10)
        self.assertEqual(result["offset"], 0)
        self.assertEqual(result["limit"], 10)
        self.assertEqual(len(result["items"]), 10)

        result = search_cases(self.cases, limit=10, offset=10)
        self.assertEqual(result["total"], 259)
        self.assertEqual(result["returned"], 10)
        self.assertEqual(result["offset"], 10)
        self.assertEqual(len(result["items"]), 10)

    def test_pagination_keeps_input_order(self):
        """分页保持输入顺序，不重新排序，保证结果可复现。"""
        result = search_cases(self.cases, limit=20, offset=0)
        ids = [item["id"] for item in result["items"]]
        self.assertEqual(ids, [case["id"] for case in self.cases[:20]])

        result = search_cases(self.cases, limit=5, offset=3)
        ids = [item["id"] for item in result["items"]]
        self.assertEqual(ids, [case["id"] for case in self.cases[3:8]])

    def test_offset_beyond_range_returns_empty(self):
        result = search_cases(self.cases, limit=10, offset=100000)
        self.assertEqual(result["total"], 259)
        self.assertEqual(result["returned"], 0)
        self.assertEqual(result["items"], [])
        self.assertEqual(result["offset"], 100000)

    def test_offset_negative_treated_as_zero(self):
        result = search_cases(self.cases, limit=3, offset=-5)
        self.assertEqual(result["offset"], 0)
        self.assertEqual(result["returned"], 3)

    def test_limit_clamped_to_max(self):
        """传 9999 会被裁到 MAX_LIMIT。"""
        result = search_cases(self.cases, limit=9999)
        self.assertEqual(result["limit"], MAX_LIMIT)
        self.assertEqual(result["returned"], MAX_LIMIT)

        result = search_policy(self.policy, limit=9999)
        self.assertEqual(result["limit"], MAX_LIMIT)
        self.assertEqual(result["returned"], len(self.policy))

    def test_limit_clamped_to_min(self):
        """limit 小于 1 时裁到 1。"""
        for bad in (0, -10):
            with self.subTest(limit=bad):
                result = search_cases(self.cases, limit=bad)
                self.assertEqual(result["limit"], 1)
                self.assertEqual(result["returned"], 1)

    def test_default_limit(self):
        result = search_cases(self.cases)
        self.assertEqual(result["limit"], DEFAULT_LIMIT)

    # ---------- 分面 ----------

    def test_facets_counts_match_hits(self):
        """分面计数与实际命中一致（各维度计数之和等于命中总数）。"""
        result = search_cases(self.cases)
        self.assertEqual(sum(result["facets"]["source_type"].values()), result["total"])
        self.assertEqual(sum(result["facets"]["industry"].values()), result["total"])

        result = search_policy(self.policy)
        self.assertEqual(sum(result["facets"]["role"].values()), result["total"])

        result = search_papers(self.papers)
        self.assertEqual(sum(result["facets"]["type"].values()), result["total"])
        self.assertEqual(sum(result["facets"]["tier"].values()), result["total"])

    def test_facets_based_on_filtered_set(self):
        """分面基于过滤后的集合（含本维度自身的过滤结果）。"""
        result = search_cases(self.cases, industry="电子电器")
        self.assertEqual(result["facets"]["industry"], {"电子电器": 44})
        self.assertEqual(
            result["facets"]["source_type"],
            {"典型案例": 24, "链式案例集": 18, "优秀场景": 2},
        )

        result = search_papers(self.papers, kind="检索入口")
        self.assertEqual(result["facets"]["type"], {"检索入口": 3})
        self.assertEqual(result["facets"]["tier"], {"检索入口": 3})

    def test_facets_sorted_by_count_desc_then_key_asc(self):
        """排序规则：条数降序，同数按键名升序。"""
        result = search_cases(self.cases, source_type="优秀场景")
        industry = result["facets"]["industry"]
        self.assertEqual(
            list(industry.items()),
            [
                ("跨行业", 15),
                ("纺织", 6),
                ("汽车", 3),
                ("电子电器", 2),
                ("装备制造", 2),
                ("建材", 1),
                ("轻工", 1),
            ],
        )
        counts = list(industry.values())
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_patents_facets_use_ipc_class(self):
        result = search_patents(self.patents)
        self.assertEqual(result["total"], 5)
        self.assertEqual(
            result["facets"]["ipc_class"],
            {"B25": 1, "B65": 1, "G01": 1, "G05": 1, "H04": 1},
        )

    def test_facets_empty_on_empty_result(self):
        result = search_cases(self.cases, q="绝对不存在的词zzzz")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["items"], [])
        self.assertEqual(result["facets"]["source_type"], {})
        self.assertEqual(result["facets"]["industry"], {})

    # ---------- 空结果与大小写 ----------

    def test_empty_result_no_error(self):
        """空结果不报错，各库结构一致。"""
        for result in (
            search_policy(self.policy, q="绝对不存在的词zzzz"),
            search_cases(self.cases, q="绝对不存在的词zzzz"),
            search_papers(self.papers, q="绝对不存在的词zzzz"),
            search_patents(self.patents, q="绝对不存在的词zzzz"),
        ):
            with self.subTest(total=result["total"]):
                self.assertEqual(result["total"], 0)
                self.assertEqual(result["returned"], 0)
                self.assertEqual(result["items"], [])
                self.assertIsInstance(result["facets"], dict)

    def test_case_insensitive_keyword(self):
        """关键词大小写不敏感。"""
        lower = search_papers(self.papers, q="maturity")
        for variant in ("MATURITY", "MaTuRiTy", "  maturity  "):
            with self.subTest(q=variant):
                result = search_papers(self.papers, q=variant)
                self.assertEqual(result["total"], lower["total"])
                self.assertEqual(
                    [i["id"] for i in result["items"]],
                    [i["id"] for i in lower["items"]],
                )

        self.assertEqual(
            search_papers(self.papers, q="DIGITAL ENGINEERING")["total"],
            search_papers(self.papers, q="digital engineering")["total"],
        )

    def test_empty_query_returns_everything(self):
        self.assertEqual(search_policy(self.policy, q="")["total"], len(self.policy))
        self.assertEqual(search_cases(self.cases, q="")["total"], len(self.cases))
        self.assertEqual(search_papers(self.papers, q="")["total"], len(self.papers))
        self.assertEqual(search_patents(self.patents, q="")["total"], 5)

    # ---------- 返回结构与原样条目 ----------

    def test_response_shape(self):
        """四个函数返回同一形状。"""
        for result in (
            search_policy(self.policy, q="验收"),
            search_cases(self.cases, q="联网"),
            search_papers(self.papers, q="maturity"),
            search_patents(self.patents, q="G05B19/418"),
        ):
            with self.subTest(total=result["total"]):
                self.assertEqual(
                    set(result.keys()),
                    {"total", "returned", "offset", "limit", "items", "facets"},
                )
                self.assertIsInstance(result["total"], int)
                self.assertIsInstance(result["returned"], int)
                self.assertEqual(result["returned"], len(result["items"]))
                self.assertLessEqual(result["returned"], result["limit"])

    def test_items_are_returned_verbatim(self):
        """items 是原样条目，不裁字段、不改内容。"""
        result = search_cases(self.cases, q="联网", limit=3)
        by_id = {case["id"]: case for case in self.cases}
        for item in result["items"]:
            self.assertEqual(item, by_id[item["id"]])

    def test_facets_are_computed_before_pagination(self):
        """分面基于过滤后全量，不受分页影响。"""
        full = search_cases(self.cases, industry="电子电器")
        page = search_cases(self.cases, industry="电子电器", limit=1, offset=0)
        self.assertEqual(page["facets"], full["facets"])
        self.assertEqual(page["total"], full["total"])

    # ---------- 边界条目（合成，不污染仓库数据） ----------

    def test_synthetic_boundary_entries(self):
        """合成临时条目做边界测试：空 title、None 字段、空 actions 均不报错。"""
        tmp_cases = [
            {
                "id": "TMP-EMPTY",
                "title": "",
                "symptom": None,
                "industry": None,
                "sector": None,
                "collection": None,
                "source_type": None,
                "actions": [],
            },
            {
                "id": "TMP-NONE-ACTION",
                "title": "临时条目",
                "symptom": None,
                "industry": None,
                "sector": None,
                "collection": None,
                "source_type": None,
                "actions": [{"action": None, "target_scenario": None, "estimated": False}],
            },
            {
                "id": "TMP-SCENARIO",
                "title": "临时条目",
                "industry": "测试行业",
                "source_type": "测试类型",
                "actions": [{"action": "临时动作", "target_scenario": "S07"}],
            },
        ]

        # 不抛异常，空字段按空串处理。
        result = search_cases(tmp_cases, q="")
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["returned"], 3)

        # 空字段条目不命中任何非空关键词。
        result = search_cases(tmp_cases, q="临时")
        self.assertEqual(result["total"], 2)
        self.assertNotIn("TMP-EMPTY", [item["id"] for item in result["items"]])

        # 场景过滤遇到 target_scenario=None 不报错，且 None 不等于 "S07"。
        result = search_cases(tmp_cases, scenario="S07")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["id"], "TMP-SCENARIO")

        # 分面遇到 None 字段按空串计数，不抛异常。
        result = search_cases(tmp_cases, industry="测试行业")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["facets"]["industry"], {"测试行业": 1})

    def test_synthetic_papers_and_patents_boundary(self):
        """论文的 None 字段、专利缺 official_aggregate 都不报错。"""
        tmp_papers = [
            {
                "id": "TMP-PAPER",
                "type": None,
                "doi": None,
                "title": "",
                "authors": None,
                "year": None,
                "journal": None,
                "tier": None,
                "claim": None,
                "used_where": None,
            }
        ]
        result = search_papers(tmp_papers, q="")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["facets"]["type"], {"": 1})
        self.assertEqual(result["facets"]["tier"], {"": 1})

        tmp_patents = {
            "categories": [
                {"id": "TMP-CAT", "category": "临时分类", "keywords": [], "ipc": []},
                {
                    "id": "TMP-CAT-2",
                    "category": "有口径分类",
                    "keywords": [],
                    "ipc": [],
                    "official_aggregate": {"ipc_class": "G05"},
                },
            ]
        }
        result = search_patents(tmp_patents, q="")
        self.assertEqual(result["total"], 2)
        # 缺 official_aggregate 的条目不进 ipc_class 分面，但仍在 items 里。
        self.assertEqual(result["facets"]["ipc_class"], {"G05": 1})
        self.assertEqual(len(result["items"]), 2)


if __name__ == "__main__":
    unittest.main()
