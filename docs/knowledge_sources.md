# 来源与出处规范

主控文档要求：**每条引用有来源、日期、用途**。这一页写清四个库各自的引用链字段、
怎么回查、以及目前如实登记的缺口。

校验方式：

```bash
python3 scripts/check_knowledge_schema.py   # schema 校验 + 引用链核对
python3 scripts/check_knowledge_port.py     # 编号交叉检查与去重
```

`check_knowledge_schema.py` 有 ERROR 就返回非 0；WARNING 只报告不失败——
**缺口如实登记，不掩盖，也不假装齐全**。

## 四个库的引用链

| 库 | 来源 | 日期 | 用途 | 回查方式 |
|---|---|---|---|---|
| 政策（30 份） | 文号 `doc_no` + 发布方 `issuer` | `publish_date`（发布日期） | `role`（作用）+ `used_where`（用在哪） | `url` 打开原文；`verified` 记录核验方式与时间 |
| 案例（259 条） | `evidence.doc`（原文文档名）+ `evidence.url` | `extracted.at`（抽取日期）；来源年份在 `collection` 里 | `collection`（来源集）+ `source_type` | `evidence.url` 打开原文；`evidence.quoted` 是原文摘录 |
| 论文（14 条） | `journal` / `tier` | `year`（文献年份） | `used_where`（用在哪） | `url` / `doi` |
| 专利（5 类） | `official_aggregate.ipc_class`（IPC 大类）+ `meta.search_entry` | `official_aggregate.year`（统计年份） | `maps_to_scenarios`（映射到哪些场景）+ `meta.purpose` | 按 `meta.counting_rule` 在官方检索系统自查 |

## schema 文件

| 文件 | 约束 |
|---|---|
| `docs/schemas/policy.schema.json` | 必填：id、文号、标题、发布方、发布日期、链接、作用、用途、核验记录 |
| `docs/schemas/case.schema.json` | 必填：id、标题、来源类型、来源集、原文出处、抽取记录；集合级条目没有症状描述，由校验器按「有条目动作则必须有症状」另行把关 |
| `docs/schemas/paper.schema.json` | 必填：id、类型、标题、作者、出处、链接、结论、用途、文献层级 |
| `docs/schemas/patent.schema.json` | 必填：id、类别名、关键词、IPC 号、映射场景、检索状态、官方大类口径 |

## 已如实登记的缺口

校验器每次运行都会把下面三条报成 WARNING——这是**现状登记**，不是待办清单：

1. **案例库 39 条没有来源发布日期**（优秀场景 30 条 + 地方实践 9 条）：
   来源集名里不含年份，只有抽取日期。能定位到原文，但没有"这份材料是哪年发的"。
2. **论文库 3 条是检索入口**（CNKI / 万方 / NCPSSD 的检索式）：
   它们不是文献，本来就没有年份与 DOI。**统计文献数时必须按 `type` 过滤**，
   否则会把 3 条检索式算进文献。
3. **专利库 5 个分类的小类数量未取到**（CNIPA 无公开 API）：
   页面与接口只出官方 IPC 大类口径，并标"待人工检索"，
   **不用大类数量冒充小类数量**。`meta.manual_protocol` 记了人工检索的做法。

## 两条硬规矩

1. **不伪造**：补不齐的字段就留空并登记，不填"看起来像真的"的值。
   专利小类数宁可空着，也不拿大类口径充数。
2. **真实层与合成层不混写**：案例库的 `extracted.synthetic` 全部为 false（公开案例）；
   评测样本全部为 true（合成样本）。两层的报告分开出，不互相替代。
