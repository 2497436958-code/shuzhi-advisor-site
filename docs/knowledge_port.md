# 知识库搬运记录（data/knowledge → 网站仓库）

> 本文件是 `data/knowledge/` 下 8 个知识库 JSON 从**源仓库**搬进**网站仓库**的搬运凭据与校验结论。
> 搬运时间：2026-11-05（Asia/Shanghai）。
> 校验脚本：`scripts/check_knowledge_port.py`（只读，不写任何文件）。

---

## 1. 来源

| 项 | 值 |
|---|---|
| 源仓库 | `https://github.com/2497436958-code/shuzhi-advisor.git` |
| 源仓库本地路径 | `/Users/xx/Documents/Codex/2026-11-05/fan-hu/work/shuzhi-advisor` |
| 源仓库分支 | `feature/knowledge-p2` |
| 源仓库 commit | `5917baae0c0b36de78ca3de8575264379574cbbc` |
| 源仓库 commit 时间 | 2026-11-05 01:11:36 +0800 |
| 源目录 | `data/knowledge/`（只读，本次未对源仓库做任何修改） |

目标仓库：

| 项 | 值 |
|---|---|
| 目标仓库 | `https://github.com/2497436958-code/shuzhi-advisor-site.git` |
| 目标仓库本地路径 | `/Users/xx/Documents/Codex/2026-11-05/https-2497436958-code-github-io-shuzhi/work/shuzhi-advisor-site` |
| 目标仓库分支 | `fix/scene-level-hint` |
| 目标仓库 commit（搬运前 HEAD） | `447187bf1dec71a49ed388981644fbde6b533a6a` |

搬运方式：`cp -p` 原样复制，未做任何内容改写、重排或重新序列化。
两侧 sha256 逐文件比对一致（见下表），确认是字节级相同的原样搬运。

---

## 2. 搬运文件清单

目标目录：`/Users/xx/Documents/Codex/2026-11-05/https-2497436958-code-github-io-shuzhi/work/shuzhi-advisor-site/data/knowledge/`

| 文件 | 绝对路径 | 字节数 | sha256 | 条目数 |
|---|---|---|---|---|
| policy.json | `.../shuzhi-advisor-site/data/knowledge/policy.json` | 27,368 | `9e847d173180ae8277f6e7ded69326ccf678d00fd7a58571f85b2260344d11d6` | 30 |
| cases.json | `.../shuzhi-advisor-site/data/knowledge/cases.json` | 730,299 | `85687706922695815d4f2baab7acead118729bba3004836efc95653e893cafab` | 259 |
| case_ids.json | `.../shuzhi-advisor-site/data/knowledge/case_ids.json` | 50,023 | `9159c1ed1691b8d097d681bf6e18440cc586bdb8d8d05d05ba2d32a2a0ba4745` | 258 |
| centers.json | `.../shuzhi-advisor-site/data/knowledge/centers.json` | 46,747 | `7e9938ffcaa84e0f2be21384993dbc26188fed6d0c28a61b8bdfa25007f0ab46` | 87 |
| elasticity.json | `.../shuzhi-advisor-site/data/knowledge/elasticity.json` | 1,926 | `f16d02b44ac421c1011c04c942213937c5579a0cf768996223241488f5eb150a` | 4 |
| papers.json | `.../shuzhi-advisor-site/data/knowledge/papers.json` | 9,992 | `81b21987fb7234f1504a8c3779deaa13b1b89331aaba7011eb33ee5b49a085ab` | 14 |
| patents.json | `.../shuzhi-advisor-site/data/knowledge/patents.json` | 9,399 | `d441b1899e45f40a65871f1cbc67fbe65bcf91c12fdb5aea8ad2c924994ec6cd` | 5（`categories`） |
| patent_center_cross.json | `.../shuzhi-advisor-site/data/knowledge/patent_center_cross.json` | 4,969 | `563f8f90776eb4227edfe2398dc860a694c61e14b9f837248f88ac0da6fd22f8` | 5（`rows`） |

### 条目数口径

- `policy.json` / `cases.json` / `centers.json` / `elasticity.json` / `papers.json`：顶层数组长度。
- `case_ids.json`：顶层对象键数（`source_id → {id, title}`），258 条，对应 `cases.json` 259 条中除 `CASE-901`（链式案例集集合级条目）外的全部案例。
- `patents.json`：按 `categories` 计数（5 个专利类别）；其 `meta.collection_status` 为"未执行自动取数"。
- `patent_center_cross.json`：按 `rows` 计数（5 个类别 × 数促中心行业覆盖）。

---

## 3. 校验脚本

### 用法

```bash
cd /Users/xx/Documents/Codex/2026-11-05/https-2497436958-code-github-io-shuzhi/work/shuzhi-advisor-site
python3 scripts/check_knowledge_port.py
# 归因路径表不在目标仓库时，显式指定源仓库（只读）
python3 scripts/check_knowledge_port.py --source-repo /Users/xx/Documents/Codex/2026-11-05/fan-hu/work/shuzhi-advisor
```

退出码：`0` = 无 ERROR；`1` = 存在 ERROR。WARNING 不影响退出码。
输出末尾附 `===JSON===` 机器可读结论块（status / 各库条目数 / 引用编号集合 / 全部问题清单）。

### 实际输出（关键部分）

```
[1] 文件存在性与 JSON 合法性
  OK   data/knowledge/policy.json  27368 bytes, 30 条
  OK   data/knowledge/cases.json  730299 bytes, 259 条
  OK   data/knowledge/case_ids.json  50023 bytes, 258 条
  OK   data/knowledge/centers.json  46747 bytes, 87 条
  OK   data/knowledge/elasticity.json  1926 bytes, 4 条
  OK   data/knowledge/papers.json  9992 bytes, 14 条
  OK   data/knowledge/patents.json  9399 bytes, 5 条
  OK   data/knowledge/patent_center_cross.json  4969 bytes, 5 条

[3] 真实层 / 合成层分层统计（按 extracted.synthetic）
  真实条目（synthetic != true）：259
  合成条目（synthetic == true）：0
    source_type:优秀场景             30
    source_type:典型案例             95
    source_type:链式案例集            134

[4] 与 precomputed/*.json 的编号交叉检查
  precomputed 引用到的 CASE 编号：4 个
    OK   CASE-013  <- ap1_只买设备不联网.json
    OK   CASE-021  <- ap2_只上系统不跑流程.json
    OK   CASE-129  <- ap4_只追补贴不建能力.json
    OK   CASE-184  <- ap3_只做数据采集不做分析.json
  precomputed 引用到的 PATH 编号：9 个
    路径表来源：.../shuzhi-advisor/src/advisor/knowledge/paths.py（32 条路径）
    OK   PATH-001 / PATH-003 / PATH-006 / PATH-007 / PATH-008
    OK   PATH-009 / PATH-010 / PATH-011 / PATH-014
  路径表 case_refs 覆盖：50 个 CASE 编号（全部命中）

[5] 发现的不一致
  （无 ERROR）
  WARNING 1. 259/259 条案例没有 root_cause 字段……
  WARNING 2. 1 条案例没有 actions：['CASE-901']……
  WARNING 3-8. 论文 PAPER-012/013/014（检索入口）没有 year / doi……

===JSON===
{ "status": "PASS", "cases": {"total": 259, "unique_ids": 259, "real": 259, "synthetic": 0},
  "precomputed_case_refs": ["CASE-013","CASE-021","CASE-129","CASE-184"],
  "precomputed_path_refs": ["PATH-001","PATH-003","PATH-006","PATH-007","PATH-008","PATH-009","PATH-010","PATH-011","PATH-014"],
  "path_table_size": 32, "errors": [], "warnings": [8 条], "notes": [5 条] }
```

**结论：`status: PASS`，退出码 0，ERROR 0 条。**
交叉检查中 `precomputed` 引用的 4 个 CASE 编号与 9 个 PATH 编号**全部命中**，没有对不上的编号。

### 脚本检查项

1. 8 个文件存在、非空、合法 JSON、顶层结构符合预期（list/dict）。
2. 各库条目数统计并打印。
3. 与 `precomputed/*.json` 交叉检查：递归扫描所有字符串值，提取 `CASE-\d{3}` / `PATH-\d{3}`，逐个比对案例库与归因路径表（路径表用正则从 `paths.py` 只读提取，不 import 源仓库代码）。
4. 反向检查：`paths.py` 里 50 个 `case_refs` 编号是否都能在 `cases.json` 查到。
5. 案例条目：id 唯一且形如 `CASE-\d{3}`、`source_type`、`title`、`evidence.url`、`extracted.by/at/synthetic`、`actions[].action/target_scenario`（场景号 `S\d{2}`）、`target_items` 在 1—15 内。
6. 政策条目：`doc_no` / `issuer` / `publish_date` / `url` / `title` 齐全，`key_provisions` 缺失降级为 WARNING。
7. 论文条目：`title` / `url` / `claim` 必填；`doi` / `year` 对 `type == "检索入口"` 的条目降级为 WARNING。
8. 专利类别：类别名、`keywords`、`maps_to_scenarios` 合法；未取数标注为 NOTE。
9. 中心条目：`name` / `source.page_url`。
10. 弹性条目：字段齐全，`case_refs` 指向的案例必须存在。
11. `case_ids.json` 每个条目的 `id` 必须能在 `cases.json` 查到。
12. **真实层 / 合成层分开统计**：按 `extracted.synthetic` 分为真实/合成两组计数，并按 `source_type` 细分，便于确认两层没有混写。

### 负向测试

在临时副本（`/tmp` 下，不触碰真实仓库）注入故障，脚本均能捕获并以退出码 1 结束：

| 注入的故障 | 脚本输出 | 退出码 |
|---|---|---|
| `precomputed` 引用不存在的 `CASE-999` | `ERROR 1. precomputed 引用了案例库中不存在的 CASE-999（出现于 ap1_只买设备不联网.json）` | 1 |
| 删除 `papers.json` | `ERROR 1. 缺失文件：data/knowledge/papers.json` | 1 |
| `papers.json` 写成非法 JSON | `ERROR 1. 非法 JSON：data/knowledge/papers.json -> Expecting property name enclosed in double quotes` | 1 |
| 清空 `evidence.url` | `ERROR 2. 案例 CASE-001 缺少 evidence.url` | 1 |
| 复制一条案例造成 id 重复 | `ERROR 4. 案例 id 重复：CASE-001 出现 2 次` | 1 |
| `target_scenario` 写成 `X9` | `ERROR 3. 案例 CASE-003 actions[0] target_scenario 非法：'X9'` | 1 |

---

## 4. 已知缺口

以下均为**源仓库既有状态**，原样搬运后依然存在，**不是搬运过程引入的**。本次不修改源数据，只如实记录。

1. **案例层没有 `root_cause`（259/259 全缺）。**
   源仓库的设计是"路径是判断、案例是证据"：`paths.py` 的 `Path.root_cause` 承载根因，`cases.json` 只留 `symptom` 与 `actions`（见 `src/advisor/knowledge/paths.py` 头部说明）。`docs/schemas/case.schema.json` 也把 `root_cause` 列为可选而非必填。
   影响：实时推理层若只读 `cases.json` 无法拿到根因，必须同时接入路径表。**这是本次搬运遗留的最大结构性缺口——路径表目前仍在源仓库，本次没有搬进目标仓库。**

2. **`CASE-901` 没有 `actions`。**
   它是"中小企业链式数字化转型典型案例集（2023 年）"的集合级条目，只登记 191 家参评 / 66 家入选口径，本身没有单条动作。`case_ids.json` 也不含它（258 = 259 − 1）。

3. **专利库统计未取数（5 个类别全部 `applications_cn` / `grants_cn` = null）。**
   `patents.json` 的 `meta.collection_status` 为"未执行自动取数"：CNIPA 检索系统需登录且无公开 API，项目未取得批量统计授权，只登记了检索式与口径。
   `patent_center_cross.json` 的 `meta` 也标注 `centers_total: 87` 但注明"名单附件未逐条核对，故不写入计数"。
   影响：实时推理层无法输出专利供给侧的**数量**结论，只能输出"有可对接主体 / 供给不确定"这类定性判断。

4. **论文库有 3 条是"检索入口"而非文献（`PAPER-012/013/014`）。**
   分别登记 CNKI、万方、国家哲学社会科学文献中心的检索式，`doi` / `year` 均为 null，状态为"未取得全文"。论文库实际文献条目为 11 条（`PAPER-001`—`PAPER-011`）。

5. **政策库 30 条达标，但 `key_provisions` 的原文可检索性未在本次校验中复核。**
   校验脚本只检查字段非空；`docs/对接说明.md` WP1.1 的验收口径要求"摘录能在 PDF/网页里搜到"，这需要联网复核，属源仓库的责任范围，本次未做。

6. **目标仓库自身不消费这些数据。**
   `src/advisor/web/api.py` 目前没有任何 `data/knowledge` 引用，实时推理层尚未接上。本次只完成数据落地与校验，接线由后续任务负责（本次任务明确禁止修改 `src/**`、`api/**`）。

7. **归因路径表（`paths.py`，32 条）未搬入目标仓库。**
   本次硬约束只允许动 `data/knowledge/**`、`scripts/check_knowledge_port.py`、`docs/knowledge_port.md`，路径表是源仓库的 Python 常量模块，落在 `src/advisor/knowledge/` 下，不在允许范围内。校验脚本因此从源仓库只读解析；一旦源仓库不可用，脚本会自动跳过 PATH 交叉检查并给出 WARNING（不会误报通过）。

---

## 5. 遗留风险

| 风险 | 影响 | 建议 |
|---|---|---|
| 路径表未落地目标仓库 | 实时推理层拿不到 `root_cause` 与 `action` 列表；`precomputed` 里的 `PATH-xxx` 无法在本仓库内自证 | 单独一轮把 `paths.py`（或等价的 JSON 化路径表）搬进 `src/advisor/knowledge/`，并让 API 侧同时加载路径表与案例库 |
| 校验脚本的路径表依赖源仓库绝对路径 | 源仓库不可用时 PATH 交叉检查自动跳过（降级为 WARNING），存在"静默少查一项"的风险 | 路径表搬入后改为本仓库内自解析；脚本已内置该优先级（先查本仓库 `src/advisor/knowledge/paths.py`，再回落到源仓库） |
| 专利库数量字段为 null | 实时结论无法给专利供给侧量化区间 | 需要人工检索 CNIPA 后回填 `applications_cn` / `grants_cn`；在此之前推理层应显式说明"供给数量未知"，不得用 `official_aggregate` 的大类口径冒充小类口径 |
| `CASE-901` 缺 `actions`、`case_ids.json` 不含它 | 下游若按 `case_ids.json` 反查会漏掉集合级条目 | 后端加载时以 `cases.json` 为准，`case_ids.json` 只作 `source_id` 索引 |
| 论文库 3 条为检索入口 | 若下游按"论文库条目数"统计可用文献，会把 3 条检索式算成文献 | 推理层引用论文时按 `type` 过滤，只用 `type != "检索入口"` 的条目出结论 |
| 未 commit | 本次改动尚未纳入版本控制 | 任务约定不 commit；如需入库，由负责人决定提交时机与 commit message |
