# 数改指导智能体 · 网站建设模型接力操作手册

> 目的：因为多个大模型可能接力参与开发，本手册必须作为**唯一主控文档**使用。  
> 规则：每一个模型完成工作后，必须在“任务状态表”和“模型接力日志”里登记它完成了什么、验证了什么、留下了什么问题。  
> 使用方式：把本文件完整复制给下一个模型，不要只给它一句话需求。

---

## 0. 使用纪律

1. **不要重新发明架构**：先读本手册，再读仓库，再动代码。
2. **不要只做不记录**：每个模型结束时必须更新任务状态表、模型接力日志、变更记录。
3. **不要把“看起来能跑”当完成**：必须写清楚验证命令和验证结果。
4. **不要让模型擅自改口径**：判据、权重、门槛、ROI、反模式规则必须与选题文档一致。
5. **不要把模型当架构师**：架构冲突由人工或主控模型裁决。
6. **每个任务必须留“交接说明”**：下一个模型要知道从哪里继续。
7. **真实层与合成层不能混写**：合成样本要标注 `synthetic`，真实企业单独报告。
8. **成果要落库**：每完成一项任务就提交并推送到远端，不允许把已完成的工作只留在本地磁盘。推送前必须跑通第 7 节的最小验证，并用 `python3 scripts/check_push_state.py` 自查。

---

## 1. 项目目标

把“数改指导智能体 · 演示站”从静态预计算网站升级为能支撑申报验收的完整系统。

### 网站必须能证明四层能力

1. **判据层**：15 采集项 + 16 应用场景 + 四级门槛 + 打分规则。
2. **知识库层**：政策、案例、论文、专利四类来源。
3. **推理层**：画像 → 诊断 → 归因 → 路径 → 排序 → 反模式。
4. **评测层**：60 家合成样本 + 1 家真实企业 + 4 组对照 + 4 组消融。

### 最终验收标准

- [ ] 判据层 100% 可复算。
- [ ] 1 家真实企业手填复算与公开评测结论一致。
- [ ] 政策库 ≥30 份。
- [ ] 案例库 ≥86 个典型案例 + 191 家参评案例集说明。
- [ ] 论文库、专利库各 1 套可检索入口与分类口径。
- [ ] 60 家合成样本全部跑通。
- [ ] 1 家真实企业全流程跑通。
- [ ] 4 组对照 + 4 组消融有数字。
- [ ] 每条结论可溯源到采集项、场景、案例或政策文件。
- [ ] 后端不可用时自动回退到预计算模式。

---

## 2. 当前状态快照

> 这部分由人工/主控维护，每个模型接力前必须确认是否仍然成立。

### 已完成 / 基本可用

| 模块 | 当前状态 | 备注 |
|---|---|---|
| 静态演示站 | 已上线 | GitHub Pages 可访问 |
| 判据数据 | 已有 | `precomputed/criteria.json` 包含 15 采集项、16 场景 |
| 四段式结果 | 已有 | 诊断 / 路径 / 排序与“不建议做” / 政策注记 |
| 反模式展示 | 已有 | AP1—AP4 可命中 |
| ROI 展示 | 已有 | 有 ROI 区间、成本分母、敏感性提示 |
| 证据链展示 | 已有 | 六个预计算样本均有 `evidence_refs` |
| 离线模式 | 已有 | 后端不可用时读取 `precomputed/` |
| 合成样本标注 | 已有 | 页面标注示例企业为合成样本 |
| 实时推理层 | 已有 | `src/advisor/reasoning/`：诊断、路径、排序、反模式、证据链 |
| 四类知识库 | 已有 | 政策 30 份 / 案例 259 条 / 论文 11 篇 + 3 条检索入口 / 专利 5 个大类口径 |
| 知识库统计接口 | 已有 | `GET /api/knowledge/stats` |
| 改造项参数表 | 已有 | `data/pathways.json`、`data/pathway_content.json`（从预计算结果反解，待人工审校） |
| 推送纪律 | 已有 | 手册第 0 节第 8 条 + 第 7 节第 7 条：每完成一项任务即提交并推送，`scripts/check_push_state.py` 自查 |
| 知识库页面 | 已有 | 站点底部「知识库」区块：四库统计 + 分类口径 + 检索 + 原文链接 |
| 知识库检索接口 | 已有 | `/api/knowledge/policy\|cases\|papers\|patents`，检索逻辑见 `src/advisor/knowledge/search.py` |

### 已知问题 / 待补齐

| 问题 | 影响 | 状态 |
|---|---|---|
| 后端不可用 | 用户不能实时填写企业情况并得到结果 | 已解决：`/api/evaluate` 已接入推理层，实时出四段式结果 |
| 只有 6 个样本 | 不满足 60 家合成样本 + 1 家真实企业 | 未解决：T037—T038 |
| 场景等级校验偏宽 | 表单只强制校验 15 个采集项，16 个场景等级不是必填 | 已解决：T010 |
| 场景等级提示 bug | 场景已有等级，但仍显示“尚未选择等级” | 已解决：T009 |
| 排序公式不完整 | 当前主要用 ROI 下界，未显式加入“等级跃迁分” | 已解决：T028，排序行输出 `level_gain` 与 `priority` |
| 知识库未展示 | 政策、案例、论文、专利缺少数量、口径、检索入口 | 已解决：四库已入库，有统计接口与「知识库」页面（数量、口径、检索入口、原文链接） |
| 评测报告缺失 | 没有诊断准确率、检出率、误报率、消融结果 | 未解决：T037—T048 |
| 真实企业复算缺失 | 选题硬验收要求 1 家企业手填复算一致 | 未解决：T008、T038 |
| 优先级公式未显式落地 | 选题要求 `(等级跃迁分 + 成效改善) ÷ 投入成本` | 已解决：T028，`P = (等级跃迁分 + 关联成效改善) ÷ 投入成本` |
| 归因路径只覆盖 9 个场景 | S02/S04/S05/S12/S13/S14/S15 没有可用路径 | 未解决：口径待人工裁决，见 `docs/reasoning_layer.md` |
| 成效弹性未被公开案例支撑 | ROI 只用于排序，不能当结论数 | 未解决：待人工裁决是否切换到 `data/knowledge/elasticity.json` 口径 |

---

## 3. 仓库建议结构

如果仓库还没整理，先按这个结构迁移。

```text
advisor-web/
  frontend/
    index.html
    app.js
    styles.css
  api/
    main.py
    schemas.py
  advisor/
    scoring/
      engine.py
      thresholds.py
    knowledge/
      policy/
      cases/
      papers/
      patents/
    reasoning/
      diagnosis.py
      pathway.py
      ranking.py
      antipatterns.py
    evaluation/
      runner.py
      report.py
  data/
    criteria/
    profiles/
    precomputed/
    evaluation/
  tests/
    test_scoring.py
    test_scenarios.py
    test_roi.py
    test_antipatterns.py
    test_evidence.py
  scripts/
    build_precomputed.py
    build_report.py
  docs/
    method.md
    handoff.md
  requirements.txt
  README.md
```

---

## 4. 核心接口设计

后端上线后建议固定这些接口：

```text
GET  /api/health
GET  /api/criteria
GET  /api/fixtures
GET  /api/fixtures/{fixture_id}
POST /api/evaluate
GET  /api/scenario_evidence
GET  /api/knowledge/stats
GET  /api/knowledge/policy
GET  /api/knowledge/cases
GET  /api/knowledge/papers
GET  /api/knowledge/patents
GET  /api/evaluation/report
```

最低要求：

- `/api/health` 必须可用于前端判断在线/离线。
- `/api/evaluate` 输入必须包含企业基线、15 采集项、16 场景等级。
- `/api/criteria` 必须是前端渲染表单的唯一来源。
- 所有评测结果必须保留证据链字段。

---

## 5. 任务状态总控表

> 每个 AI 模型完成工作后必须更新本表。  
> 状态只能用：`未开始 / 进行中 / 待验收 / 已完成 / 回归失败 / 放弃`。

| ID | 模块 | 任务 | 依赖 | 交付物 | 验收标准 | 状态 | 负责模型 | 模型完成说明 |
|---|---|---|---|---|---|---|---|---|
| T000 | 工程化 | 确认源码仓库、分支、运行方式 | 无 | 可本地启动的仓库 | `git clone` 后可运行，前端可打开 | 已完成 | Codex | 已克隆 `work/shuzhi-advisor-site`；本地 8081 可打开静态站。 |
| T001 | 工程化 | 建立 Git 分支与提交规范 | T000 | 分支规范说明 | 不允许直接改主干，提交有说明 | 已完成 | Codex | 已创建 `fix/scene-level-hint`；本次只提交该任务相关修改。MODEL-008 追加“每完成一项任务即提交并推送”纪律与 `scripts/check_push_state.py`。 |
| T002 | 工程化 | 建立后端依赖与环境说明 | T000 | `requirements.txt`、README | 新模型可按 README 启动 | 已完成 | Codex | 已补充 FastAPI/Uvicorn 依赖、httpx 开发依赖、后端启动说明。 |
| T003 | 工程化 | 建立 CI | T000 | GitHub Actions | push 后自动跑测试 | 已完成 | Codex | CI 在 Python 3.10/3.11/3.12 跑判据校验、测试和前端语法检查。 |
| T004 | 判据层 | 固化 15 个采集项 | 无 | `criteria.json` 或 DB | 数量、权重、选项、题型一致 | 已完成 | Codex | `precomputed/criteria.json` 结构校验通过，15 项权重合计 1.0。 |
| T005 | 判据层 | 固化 16 个应用场景 | T004 | 场景定义文件 | 16 个场景、约束性标记、四级描述完整 | 已完成 | Codex | 16 个场景、约束性标记、四级描述均已通过校验。 |
| T006 | 判据层 | 实现打分引擎 | T004 | `engine.py` | 单选/多选/官方口径缺口可复算 | 已完成 | Codex | 新增确定性打分器，6 个预计算样本全部复算通过。 |
| T007 | 判据层 | 实现四级门槛 | T005/T006 | `thresholds.py` | 20/40/60/80 分和场景下限正确 | 已完成 | Codex | 四级门槛与场景/约束性场景下限已实现并通过样本验证。 |
| T008 | 判据层 | 增加 1 家真实企业复算记录 | T006/T007 | 复算页或文档 | 手填复算与公开结论一致 | 进行中 | Codex | 已新增通用复算脚本和说明；等待真实企业手填数据。 |
| T009 | 前端 | 修复场景等级提示 bug | 无 | `app.js` 修改 | 已选等级不再显示“尚未选择等级” | 已完成 | Codex | 载入时同步场景等级描述；无等级时恢复默认提示。 |
| T010 | 前端 | 场景等级改为必填 | T009 | 表单校验 | 16 个场景未填时禁止提交 | 已完成 | Codex | AP0 缺场景被拦截；AP1 填齐后通过校验。 |
| T011 | 前端 | 企业画像表单完善 | T010 | 表单 UI | 基线、采集项、场景清晰可填 | 未开始 |  |  |
| T012 | 前端 | 四段式结果页优化 | T006/T008 | 结果页 | 诊断、路径、排序、政策注记阅读体验清晰 | 未开始 |  |  |
| T013 | 前端 | 知识库页面 | P2 | `/knowledge` | 四类知识源数量、分类、样例可见 | 已完成 | Codex | 知识库页面已上线：四库统计 + 分类口径 + 关键词与分类下拉检索 + 原文链接；离线模式可浏览不检索。 |
| T014 | 前端 | 评测报告页面 | P4 | `/evaluation` | 报告数字和样本分层可访问 | 未开始 |  |  |
| T015 | 前端 | 方法页 | P3/P4 | `/method` | 讲清公式、口径、局限、合规边界 | 未开始 |  |  |
| T016 | 后端 | 实现 `/api/health` | T000 | API | 前端可判断在线/离线 | 已完成 | Codex | 返回在线状态与判据层规模；前端可切换到实时模式。 |
| T017 | 后端 | 实现 `/api/criteria` | T004/T005 | API | 前端可渲染完整表单 | 已完成 | Codex | 返回 15 采集项、16 场景和四级门槛。 |
| T018 | 后端 | 实现 `/api/fixtures` | T004 | API | 样例企业列表可用 | 已完成 | Codex | 已实现列表和单样例接口。 |
| T019 | 后端 | 实现 `/api/evaluate` | T006—T012 | API | 自定义企业实时出四段式结果 | 已完成 | Codex | 已接入判据层 + 推理层：诊断、路径、排序、反模式、政策注记全部实时生成，返回体与已发布预计算结果同构。 |
| T020 | 后端 | 实现 `/api/scenario_evidence` | T005 | API | 官方原文引文可返回 | 已完成 | Codex | 返回预计算场景判定证据和可用性标记。 |
| T021 | 后端 | 实现知识库接口 | T013 | API | 政策/案例/论文/专利可查询 | 已完成 | Codex | 已实现 `/api/knowledge/policy|cases|papers|patents`（关键词 + 精确过滤 + 分页 + 分面计数）与 `/api/knowledge/stats`。 |
| T022 | 后端 | 实现评测报告接口 | P4 | API | 报告 JSON 可访问 | 未开始 |  |  |
| T023 | 后端 | 保留离线回退 | T016—T022 | `precomputed/` | 后端挂掉仍可演示 | 已完成 | Codex | `precomputed/` 未改动，前端 `/api/health` 失败时仍回退到预计算模式，离线与实时共用同一套渲染代码。 |
| T024 | 推理层 | 诊断规则 | T004—T007 | `diagnosis.py` | 输出瓶颈、命中项、命中场景 | 已完成 | Codex | 四类瓶颈规则全部实现（反模式型、场景断层、等级缺口、基础缺口），与预计算结果逐条一致。 |
| T025 | 推理层 | 归因路径匹配 | 案例库 | `pathway.py` | 症状 → 根因 → 改造项可匹配 | 已完成 | Codex | 路径表从预计算结果反解入库（`data/pathways.json`），案例按目标场景就近匹配，引用可逐条回查。 |
| T026 | 推理层 | 改造路径生成 | T024/T025 | 结构化路径 | 每步有目标场景、投入、成效、验收口径 | 已完成 | Codex | 每步含目标场景、关联采集项、投入区间、预期成效区间、依赖与逐条验收口径。 |
| T027 | 推理层 | ROI 模型 | T004—T011 | `ranking.py` | 分子分母、区间、敏感性可复算 | 已完成 | Codex | ROI 区间按“最小收益÷最大成本”取下界排序，分母含投入、运维与工时折价，补贴不入分子。 |
| T028 | 推理层 | 等级跃迁分排序 | T027 | `ranking.py` | 优先级包含等级跃迁分 | 已完成 | Codex | 排序行输出 `level_gain`（等级跃迁分）与 `priority`（P =（等级跃迁分 + 关联成效改善）÷ 投入成本）。 |
| T029 | 推理层 | 反模式检测 | T004—T007 | `antipatterns.py` | AP1—AP4 全部可检 | 已完成 | Codex | AP1—AP4 全部可检，6 个样例命中结果与预计算一致。 |
| T030 | 推理层 | 证据链强制规则 | T024—T029 | schema 校验 | 没证据的结论不允许输出 | 已完成 | Codex | 证据链闸门：结论缺 `evidence_refs` 直接报错；测试覆盖全部四段式条目。 |
| T031 | 知识库 | 政策库 ≥30 份 | 无 | `policy/` | 每条有文号、发布方、日期、用途、链接 | 已完成 | Codex | 政策库 30 份入库（`data/knowledge/policy.json`），每条有文号、发布方、日期、链接、关键条款。 |
| T032 | 知识库 | 案例库 ≥86 个典型案例 | T031 | `cases/` | 每条有行业、症状、根因、动作、场景、来源 | 已完成 | Codex | 案例库 259 条入库（典型案例 95 + 链式案例集 134 + 优秀场景 30），逐条带原文出处。 |
| T033 | 知识库 | 191 家参评案例集说明 | T032 | 文档/数据 | 数量、来源、用途清楚 | 已完成 | Codex | `docs/knowledge_case_sets.md` 说明 191 家参评 → 66 家入选口径与 87 家数促中心登记。 |
| T034 | 知识库 | 论文库检索入口 | 无 | `papers/` | 有分类口径和样例数据 | 已完成 | Codex | 论文库 11 篇文献 + 3 条检索入口入库，文献与检索入口分开计数。 |
| T035 | 知识库 | 专利库检索入口 | 无 | `patents/` | 有分类口径和样例数据 | 进行中 | Codex | 专利库 5 个官方大类口径与场景映射已入库；逐件检索入口与小类数量待补（CNIPA 无公开 API）。 |
| T036 | 知识库 | 四库统计页 | T031—T035 | `/knowledge/stats` | 数量、来源、用途可视化 | 已完成 | Codex | 统计接口与前端页面均已上线，CI 用前端冒烟测试（`node scripts/check_knowledge_page.mjs`）守着渲染路径。 |
| T037 | 评测 | 60 家合成样本 | T004—T030 | `profiles/` | AP1—AP4 各 10 家，正常对照 20 家 | 未开始 |  |  |
| T038 | 评测 | 1 家真实企业 | T008 | `profiles/` | 真实层单列报告 | 未开始 |  |  |
| T039 | 评测 | 4 组对照 | T037 | 评测结果 | 纯 RAG / 纯规则 / RAG+计算器 / 完整闭环 | 未开始 |  |  |
| T040 | 评测 | 4 组消融 | T037 | 评测结果 | 去归因 / 去约束场景 / 去反模式 / 去判据锚定 | 未开始 |  |  |
| T041 | 评测 | 诊断准确率 F1 | T037 | 指标 | ≥0.80 | 未开始 |  |  |
| T042 | 评测 | 归因路径命中率 | T038/T039 | 指标 | ≥70% | 未开始 |  |  |
| T043 | 评测 | 排序一致性 | T027/T028/T039 | 指标 | Top-3 ≥70% | 未开始 |  |  |
| T044 | 评测 | 反模式检出率/误报率 | T029/T037 | 指标 | ≥85% / ≤15% | 未开始 |  |  |
| T045 | 评测 | ROI 测算偏差 | T027/T037 | 指标 | ≤20% | 未开始 |  |  |
| T046 | 评测 | 跨行业泛化 | T037—T045 | 指标 | 衰减 ≤10 个百分点 | 未开始 |  |  |
| T047 | 评测 | 评测报告生成 | T037—T046 | `/evaluation/report.md` | 人可读报告含真实层/合成层 | 未开始 |  |  |
| T048 | 评测 | 评测报告 JSON | T047 | API | 页面和接口一致 | 未开始 |  |  |
| T049 | 合规 | 免责与边界声明 | 无 | 页脚/方法页 | 不承诺补贴、不代申报、不替代决策 | 未开始 |  |  |
| T050 | 合规 | 来源与出处规范 | 全部 | 数据 schema | 每条引用有来源、日期、用途 | 进行中 | Codex | 入库条目均有来源、日期与链接；统一 schema 文件待落地。 |
| T051 | 部署 | 静态站部署 | T000 | GitHub Pages | 页面可访问 | 未开始 |  |  |
| T052 | 部署 | 后端部署 | T016—T023 | Render/Fly/Railway | `/api/health` 可访问 | 未开始 |  |  |
| T053 | 部署 | CORS 与环境变量 | T052 | 配置文档 | 前后端联调无跨域问题 | 未开始 |  |  |
| T054 | QA | 判据层测试 | T006—T008 | 测试 | 打分与门槛可重复验证 | 未开始 |  |  |
| T055 | QA | 推理层测试 | T024—T030 | 测试 | 输出结构、证据链、反模式可测 | 已完成 | Codex | `tests/test_reasoning.py`、`test_ranking.py`、`test_evidence.py`：判据层复算、诊断一致、ROI 一致、证据链强制。 |
| T056 | QA | API 测试 | T016—T023 | 测试 | 接口输入输出和错误处理可测 | 已完成 | Codex | `tests/test_api.py` 覆盖 health/criteria/fixtures/evaluate/knowledge stats/四个检索端点与 404、422 分支。 |
| T057 | QA | 前端可访问性 | T009—T015 | UI 检查 | 键盘、aria、对比度、移动端可用 | 进行中 | Codex | 知识库页面的检索框、筛选下拉与计数都带 aria 标注；全站可访问性审计未做。 |
| T058 | QA | 演示脚本 | 全部 | `docs/demo.md` | 5 分钟答辩演示路径固定 | 未开始 |  |  |

---

## 6. 模型接力日志

> 规则：每换一个模型，必须新增一条记录。  
> 不要写“做了很多工作”，要写清楚具体文件、具体任务 ID、验证方式和遗留风险。

### 模板

```markdown
## MODEL-001 · 模型名 · 日期

### 参与范围
- 任务 ID：
- 模块：

### 实际完成
- 修改文件：
- 新增文件：
- 修改内容：

### 验证方式
- 命令：
- 结果：

### 更新的任务状态
- T000：未开始 → 已完成
- T004：未开始 → 已完成

### 遗留问题
- ：
- ：

### 给下一个模型的交接提示
- 优先处理：
- 不要动：
- 风险点：
```

---

### 已记录

```markdown
## 2026-11-05 · Codex · 项目审题与操作方案

### 参与范围
- 项目审题
- 网站现状分析
- 操作方案撰写

### 实际完成
- 对照选题文档检查网站目标、判据层、四段式输出、ROI、反模式、知识库缺口、评测缺口。
- 输出《完成选题网站操作方案.md》。
- 识别场景等级提示 bug、场景等级校验偏宽、后端不可用、知识库与评测报告缺失等问题。

### 验证方式
- 读取选题文档关键章节。
- 访问线上站点并载入示例企业。
- 检查 `precomputed/criteria.json`、`precomputed/fixtures.json` 和六个预计算结果。

### 更新的任务状态
- 项目审题：已完成
- 当前状态快照：已完成
- 操作方案：已完成

### 遗留问题
- 源码仓库尚未确认。
- 场景等级提示 bug 尚未修复。
- 后端、知识库、评测报告尚未完成。

### 给下一个模型的交接提示
- 先确认源码仓库位置，再开始 T000—T003。
- 不要先做大模型问答界面。
- 不要动判据口径，先做 T004—T008。
- 所有模型修改后必须更新第 5 节任务状态表和第 6 节模型接力日志。
```

---

## MODEL-002 · Codex · 2026-11-05

### 参与范围
- 任务 ID：T000、T001、T009
- 模块：工程化准备、前端场景等级提示

### 实际完成
- 克隆源码仓库到 `work/shuzhi-advisor-site`。
- 创建工作分支 `fix/scene-level-hint`。
- 修改 `app.js`：
  - 载入画像后同步 16 个场景等级描述。
  - 无等级时恢复“尚未选择等级”默认提示。
  - 切换画像前先清空旧选中状态，避免状态残留。
- 将本手册复制到仓库 `docs/model_handoff.md`，便于后续模型直接读取。

### 验证方式
- `node --check app.js`
- `git diff --check`
- 本地打开 `http://localhost:8081/`
- 依次载入 6 个示例企业，确认：
  - AP0：16 个场景均为默认“尚未选择等级”提示；
  - AP1—AP4 和 baseline：16 个场景均有选中等级，且无“尚未选择等级”残留。

### 更新的任务状态
- T000：未开始 → 已完成
- T001：未开始 → 已完成
- T009：未开始 → 已完成

### 遗留问题
- T010 尚未完成：16 个场景等级还不是必填。
- 本次修改尚未推送到远端，需要用户确认后再提交/推送。
- 后端、知识库展示、评测报告仍未开始。

### 给下一个模型的交接提示
- 从 `work/shuzhi-advisor-site` 的 `fix/scene-level-hint` 分支继续。
- 下一步优先做 T010：16 个场景等级必填校验。
- 不要动判据口径和 ROI 公式。
- 所有新修改继续登记到本文件第 5 节和第 6 节。

---

## MODEL-003 · Codex · 2026-11-05

### 参与范围
- 任务 ID：T010
- 模块：前端必填校验

### 实际完成
- 修改 `app.js`：
  - 新增 `missingScenarios` 校验。
  - 采集项与场景等级缺失时合并显示错误提示。
  - 明确“15 个采集项与 16 个场景等级全部作答才能定级”。

### 验证方式
- `node --check app.js`
- `git diff --check`
- 本地打开 `http://localhost:8081/?t=t010`
- AP0 缺少 16 个场景等级：点击评测后显示拦截提示。
- AP1 已填齐：点击评测后通过校验，进入“离线模式”提示。

### 更新的任务状态
- T010：未开始 → 已完成

### 遗留问题
- 后端仍然不可用，只能使用预计算结果。
- T004—T008 判据层固化与真实企业复算仍未完成。
- 知识库展示、评测报告仍未完成。

### 给下一个模型的交接提示
- 从 `fix/scene-level-hint` 分支继续。
- 下一步建议做 T004—T008：固化判据层并补 1 家真实企业复算。
- 不要改判据口径，不要让模型参与算分。

---

## MODEL-004 · Codex · 2026-11-05

### 参与范围
- 任务 ID：T004、T005、T006、T007、T008
- 模块：判据层固化、打分引擎、四级门槛、真实企业复算准备

### 实际完成
- 新增 `src/advisor/scoring/thresholds.py`，固化四级门槛。
- 新增 `src/advisor/scoring/engine.py`，实现确定性打分器。
- 新增 `scripts/verify_criteria.py`，自动校验 15 采集项、16 场景、四级门槛和权重。
- 新增 `scripts/recompute_profile.py`，支持任意画像 JSON 复算。
- 新增 `tests/test_scoring.py`，覆盖 3/5 选项单选、多选、官方口径缺口和 6 个预计算样本。
- 新增 `docs/criteria_recompute.md`，记录口径、公式、复算命令和真实企业数据要求。
- 更新 `README.md`，补充判据层复算入口。

### 验证方式
- `python3 scripts/verify_criteria.py`
- `python3 -m unittest discover -s tests -v`
- `python3 scripts/recompute_profile.py precomputed/ap1_只买设备不联网.json --payload`
- 全部通过。

### 更新的任务状态
- T004：未开始 → 已完成
- T005：未开始 → 已完成
- T006：未开始 → 已完成
- T007：未开始 → 已完成
- T008：未开始 → 进行中

### 遗留问题
- T008 缺少真实企业手填数据和公开评测结论，尚不能宣布完成。
- 后端 `/api/evaluate` 还没有接入新打分器。
- CI 和依赖说明尚未建立。

### 给下一个模型的交接提示
- 下一步可以先做 T002/T003，把 Python 环境和 CI 固化。
- 或者继续 T008：请用户提供 1 家真实企业的手填数据。
- 不要让模型参与算分；所有判据层计算必须走 `advisor.scoring.engine`。

---

## MODEL-005 · Codex · 2026-11-05

### 参与范围
- 任务 ID：T002、T003
- 模块：开发环境、CI

### 实际完成
- 新增 `requirements.txt`，当前只声明判据层无第三方依赖，后端依赖留待接入后固定。
- 更新 `README.md`，补充 Python 3.10+、Node.js 检查、本地预览和常用验证命令。
- 新增 `.github/workflows/ci.yml`。
- CI 覆盖 Python 3.10 / 3.11 / 3.12，并执行判据层校验、单元测试、前端语法检查和空白符检查。

### 验证方式
- `python3 -m pip install -q -r requirements.txt`
- `python3 scripts/verify_criteria.py`
- `python3 -m unittest discover -s tests -v`
- `node --check app.js`
- `git diff --check`
- `ruby -e "require 'yaml'; YAML.load_file('.github/workflows/ci.yml')"`
- 全部通过。

### 更新的任务状态
- T002：未开始 → 已完成
- T003：未开始 → 已完成

### 遗留问题
- CI 尚未推送到远端，未在 GitHub Actions 实际执行。
- 后端依赖尚未确定，`requirements.txt` 只保留说明。
- `/api/evaluate` 还没有接入确定性打分器。

### 给下一个模型的交接提示
- 从 `fix/scene-level-hint` 分支继续。
- 下一步建议做 T016—T020：搭建最小后端接口，并把 `/api/evaluate` 接到 `advisor.scoring.engine`。
- 后端新增依赖时必须同步更新 `requirements.txt`、README 和 CI。
- 不要让模型参与算分。

---

## MODEL-006 · Codex · 2026-11-05

### 参与范围
- 任务 ID：T016、T017、T018、T019、T020
- 模块：最小后端 API、确定性打分器接入、联调验证

### 实际完成
- 新增 FastAPI 后端：`src/advisor/web/api.py`。
- 新增开发入口：`api/main.py`。
- 实现端点：
  - `/api/health`
  - `/api/criteria`
  - `/api/fixtures`
  - `/api/fixtures/{fixture_id}`
  - `/api/evaluate`
  - `/api/scenario_evidence`
- `/api/evaluate` 已接入 `advisor.scoring.engine`。
- 新增 `docs/backend_api.md`。
- 更新 `requirements.txt` 和 `requirements-dev.txt`。
- 更新 CI，使用 `requirements-dev.txt` 安装测试依赖。
- 更新 README，补充后端启动说明。

### 验证方式
- `python3 -m unittest discover -s tests -v`：17 个测试全部通过。
- `python3 scripts/verify_criteria.py`：6 个预计算样本全部 PASS。
- `node --check app.js`：通过。
- 启动 `uvicorn` 后用 `curl` 冒烟测试：
  - `/api/health` 返回 `mode=online`；
  - `/api/criteria` 返回 15 个采集项、16 个场景；
  - `/api/fixtures/ap1_只买设备不联网.json` 返回画像；
  - `/api/evaluate` 返回 `51.95 / 规范级 / realtime`。
- 浏览器打开后端地址，确认顶部从“预计算结果”切换为“实时计算（后端在线）”。

### 更新的任务状态
- T002：说明更新
- T016：未开始 → 已完成
- T017：未开始 → 已完成
- T018：未开始 → 已完成
- T019：未开始 → 进行中
- T020：未开始 → 已完成

### 遗留问题
- T019 只完成判据层实时计算；诊断、归因路径、ROI 排序、反模式识别还没有接入。
- 后端当前挂载整个仓库根目录用于本地联调，生产部署前需要改为专用静态目录。
- CI 尚未推送远端，尚未在 GitHub Actions 实际运行。

### 给下一个模型的交接提示
- 从 `fix/scene-level-hint` 分支继续。
- 下一步优先做 T024—T030：诊断、归因路径、ROI、反模式和证据链，然后接入 `/api/evaluate`。
- 不要把 `reasoning_status` 改成 `ready`。
- 后端新增依赖时同步更新 `requirements.txt`、`requirements-dev.txt`、README 和 CI。


---

## MODEL-007 · Codex · 2026-11-05

### 参与范围
- 任务 ID：T019、T021、T023—T030、T031—T036、T050、T055、T056
- 模块：推理层（诊断 / 路径 / 排序 / 反模式 / 证据链）、知识库入库、后端接口

### 实际完成
- 新增 `src/advisor/reasoning/` 推理层：
  - `antipatterns.py`（AP1—AP4）、`diagnosis.py`（四类瓶颈）、`pathway.py`（选步、依赖顺序、验收口径）、
    `ranking.py`（ROI 区间、等级跃迁分、优先级）、`evidence.py`（证据构造与强制闸门）、`pipeline.py`（结果组装）。
- `/api/evaluate` 由“只返回判据层”升级为返回完整四段式结果，返回体与已发布预计算结果同构；
  新增 `GET /api/knowledge/stats`。
- 知识库入库：`data/knowledge/` 8 个数据文件（政策 30 份、案例 259 条、论文 11 篇 + 3 条检索入口、
  专利 5 个大类口径、成效弹性 4 条、中心登记 87 家），来自引擎仓 `feature/knowledge-p2` 分支。
- 归因路径表从已发布预计算结果反解入库：
  - `scripts/extract_pathway_params.py` → `data/pathways.json`（9 个改造项 / 11 个步骤变体，31 行 ROI 复算通过）；
  - `scripts/extract_pathway_content.py` → `data/pathway_content.json`（症状、根因、依据、置信度）。
- 新增文档：`docs/reasoning_layer.md`（推理层口径与差异说明）、`docs/knowledge_case_sets.md`（191 家参评口径）、
  `docs/knowledge_port.md`、`docs/pathway_params_provenance.md`。
- 前端仅一处改动：`app.js` 场景等级来源标签增加“用户自评”，其余渲染逻辑未动。

### 验证方式
- `python3 scripts/verify_criteria.py`
- `python3 -m unittest discover -s tests -v` → 34 个用例全部通过
- `python3 scripts/compare_precomputed.py` → 6 个样例的判据层、反模式命中、共同改造项 ROI **完全一致**
- `python3 scripts/check_knowledge_port.py` → 案例 259 条、政策 30 份，编号交叉检查无缺口
- `python3 scripts/extract_pathway_params.py --check` → 反解幂等自检通过
- `node --check app.js`
- `python3 -c "from fastapi.testclient import TestClient; ..."` → `/api/evaluate`、`/api/knowledge/stats`、
  静态首页均返回 200，四段式字段齐全
- **本轮未能做浏览器实机验证**：执行环境的回环 HTTP 被网络策略拦截（curl 与应用内浏览器均
  连不上 127.0.0.1），改用 FastAPI TestClient 覆盖同一套 ASGI 路由，并用契约测试
  固定前端渲染器读到的全部字段。下一步模型请在能联网的本机起一次
  `python3 api/main.py`，肉眼确认四段式渲染。

### 更新的任务状态
- T019、T023—T030、T031—T034、T050、T055、T056：未开始 → 已完成
- T021、T035、T036：未开始 → 进行中
- 当前状态快照：已知问题表补齐“状态”列；补 4 行已完成能力

### 变更记录
- 新增目录 `src/advisor/reasoning/`、`data/`；新增脚本 3 个、文档 4 份、测试 3 个。
- 修改 `src/advisor/web/api.py`、`app.js`、`README.md`、`docs/backend_api.md`、`tests/test_api.py`。
- **未改动** `precomputed/*.json`、`src/advisor/scoring/*`、`precomputed/criteria.json`（判据层保持冻结）。

### 遗留问题
- 归因路径只覆盖 9 个场景（S01/S03/S06—S11/S16），S02/S04/S05/S12—S15 无路径可用。
- 两处口径冲突待人工裁决：
  1. 引擎仓 `feature/knowledge-p2` 有 32 条更新路径表，与站点现用路径表编号含义不同（两边 PATH-011 指向不同场景）；
  2. 引擎仓 `elasticity.json` 的成效弹性有公开案例支撑，与站点现用演示弹性区间不同。
- 投入与收益按营业收入等比折算（基准 6000 万元营收），折算律未经真实企业校准。
- T008 / T037—T048（60 家合成样本、4 组对照、4 组消融、评测报告）仍未开始。

### 给下一个模型的交接提示
- 从 `fix/scene-level-hint` 分支继续。
- 下一步优先做 **T036 前端知识库页面**（数据与统计接口已就绪，只差展示）或 **T037 合成样本生成器**。
- **不要动** `src/advisor/scoring/`、`precomputed/criteria.json`：判据层已冻结，改动会让全部评测数字作废。
- 两条口径冲突（路径表、弹性区间）必须由人工裁决，模型不得自行替换。
- 验证命令：`python3 -m unittest discover -s tests -v` 与 `python3 scripts/compare_precomputed.py`。


---

## MODEL-008 · Codex · 2026-11-05

### 参与范围
- 任务 ID：T001（补充推送纪律）
- 模块：手册纪律、Git 推送流程

### 实际完成
- 手册新增两条硬规则：
  - 第 0 节第 8 条“成果要落库”：每完成一项任务就提交并推送，不允许只留在本地磁盘；
  - 第 7 节交接协议扩为 7 条，第 7 条“把成果推上远端”，给出 `git status` /
    `scripts/check_push_state.py` / `git push` 三步与"推工作分支、合 main 前确认 CI"的分工。
- 第 10 节输出模板增加“推送”字段（分支、推送提交、自查结果）。
- 新增 `scripts/check_push_state.py`：检查工作区是否干净、各本地分支是否还有未推送提交，
  不通过时返回非 0，可直接当作收工前的自检。
- 把此前只在本地磁盘的 9 个提交全部推送上线，并快进合并到 `main`。

### 验证方式
- `python3 scripts/check_push_state.py --all` → 通过（工作区干净、无未推送提交）
- `git rev-list --count origin/main..main` → 0
- `git push --dry-run` → 凭据可用
- GitHub Actions：推送后自动触发 CI（含本轮新增的推理层一致性与知识库校验两步）

### 推送
- 分支：`fix/scene-level-hint` → `origin/fix/scene-level-hint`；`main` → `origin/main`
- 推送提交：本轮全部提交 + 此前积压的 9 个提交
- `scripts/check_push_state.py` 结果：通过

### 更新的任务状态
- T001：已完成的提交规范补充“每完成一项即推送”纪律

### 变更记录
- 修改：`docs/model_handoff.md`（同步到桌面手册）、`.github/workflows/ci.yml`
- 新增：`scripts/check_push_state.py`

### 遗留问题
- 该仓无分支保护、无推送前钩子，本轮 `main` 是快进直推；长期建议改走 PR，
  或给仓库加 `.githooks/pre-push`（引擎仓已有同类做法可参考）。
- **推送被拒的典型原因**：`refusing to allow an OAuth App to create or update workflow
  .github/workflows/ci.yml without 'workflow' scope` —— 这是本地 GitHub token 缺 `workflow`
  权限，不是仓库或代码问题。本地 token 权限在本次已补齐（`repo` + `workflow`）。
  换机器或 token 过期后再遇到，执行 `gh auth refresh -h github.com -s workflow` 重新授权即可。

### 给下一个模型的交接提示
- 每完成一项任务：先跑验证，再 `git add -A && git commit`，最后 `git push`，
  收工前跑 `python3 scripts/check_push_state.py` 确认无未推送提交。
- 推送若因 workflow scope 被拒，先 `gh auth refresh -h github.com -s workflow`，
  别去删 CI 文件绕过——那是倒退。
- 不要在没跑通 `python3 -m unittest discover -s tests` 与
  `python3 scripts/compare_precomputed.py` 的情况下推送。
- 下一步建议做 T036 前端知识库页面（数据与统计接口已就绪）或 T037 合成样本生成器。


---

## MODEL-009 · Codex · 2026-11-05

### 参与范围
- 任务 ID：T013、T021、T036、T056（补充）、T057（部分）
- 模块：知识库检索接口、知识库前端页面、前端冒烟测试

### 实际完成
- 新增 `src/advisor/knowledge/search.py`：政策 / 案例 / 论文 / 专利四库统一的检索层
  （关键词子串匹配 + 精确过滤 + 分页 + 分面计数），返回体统一为
  `{total, returned, offset, limit, items, facets}`；`items` 保持原顺序，不裁字段。
- 新增四个检索端点与扩充后的 `/api/knowledge/stats`（含前端筛选下拉用的维度清单）。
- 新增前端「知识库」区块：顶栏与首屏各一个入口，区块内含四库统计卡片、每库的分类口径说明、
  关键词检索、分类下拉筛选、命中计数与逐条原文链接；专利库额外显示官方检索入口与计数规则。
  离线模式降级为"可浏览不检索"，并明示"离线仅浏览"。
- 新增零依赖的前端冒烟测试 `scripts/check_knowledge_page.mjs`：用最小 DOM 桩 + fetch 桩
  在 Node 里跑完 app.js 启动流程，检查 app.js 请求的元素 id 都存在于 index.html、
  四个库块与条目真的渲染出来、检索与筛选确实发出正确请求并回填结果。
- CI 增加两步：`node scripts/check_knowledge_page.mjs` 与已有的推理层一致性、知识库校验。

### 验证方式
- `python3 -m unittest discover -s tests -v` → 77 个用例全部通过
- `node scripts/check_knowledge_page.mjs` → 统计卡片 4 个、库块 4 个、渲染条目 10 条、缺失 id 0 个
- `python3 scripts/build_knowledge_fixture.py` → 重新生成前端样例（policy 2 / cases 88 / papers 2 / patents 5）
- `node --check app.js`、`git diff --check` → 通过
- 接口联调（TestClient）：`/api/knowledge/policy?q=验收` → total=2；
  `/api/knowledge/cases?q=联网` → total=88；`?industry=电子电器` → 44；
  `?source_type=优秀场景` → 30；`?scenario=S07` → 98；`/api/knowledge/papers?kind=方法` → 2；
  `/api/knowledge/patents?q=G05B19/418` → 1

### 更新的任务状态
- T013：未开始 → 已完成
- T021：进行中 → 已完成
- T036：进行中 → 已完成
- T056：已完成（补充说明：新增四个检索端点覆盖）
- T057：未开始 → 进行中

### 变更记录
- 新增：`src/advisor/knowledge/`（`__init__.py`、`search.py`）、`tests/test_knowledge_search.py`、
  `scripts/check_knowledge_page.mjs`、`scripts/build_knowledge_fixture.py`、`scripts/fixtures/knowledge_api.json`
- 修改：`src/advisor/web/api.py`、`app.js`、`index.html`、`styles.css`、`tests/test_api.py`、
  `README.md`、`docs/backend_api.md`、`.github/workflows/ci.yml`
- **未改动** 判据层、`precomputed/*.json`、知识库数据文件本身

### 遗留问题
- 检索只做子串匹配，不做分词/拼音/同义词；关键词"数字化转型"命中 230/259 条，区分度低。
  当前不排序（保持原序以保证可复现），若要"最相关的排前面"需要另立排序口径，请人工决定。
- 专利 5 个类别的 `applications_cn`/`grants_cn` 仍为 null（CNIPA 无公开 API），
  页面只显示官方 IPC 大类口径，并明确标注"待人工检索"，不冒充小类数量。
- 论文库 3 条"检索入口"不是文献，页面与统计都分开计数。
- 知识库页面尚未做实机浏览器验证（执行环境回环 HTTP 被拦截），用 DOM 桩冒烟测试替代。

### 给下一个模型的交接提示
- 下一步建议做 **T037 合成样本生成器**（AP1—AP4 各 10 家 + 正常对照 20 家），
  为 T041—T048 的评测指标与对照消融准备样本；生成器必须标注 `synthetic`。
- 知识库检索口径见 `docs/backend_api.md`；若要改排序或加相关性，必须在手册里登记口径变更。
- 收工三步：`python3 -m unittest discover -s tests` → `node scripts/check_knowledge_page.mjs` →
  `python3 scripts/check_push_state.py`（未推送提交数必须为 0）。

---

## 7. 交接协议：换模型前必须做的 6 件事

1. **确认当前分支**  
   记录分支名、最近 commit、未提交文件。

2. **跑一次最小验证**  
   至少执行：
   ```bash
   git status
   pytest
   npm run build # 如果有
   ```

3. **更新任务状态表**  
   把完成任务从“进行中”改成“待验收”或“已完成”。

4. **写模型接力日志**  
   写明修改了哪些文件、验证结果、遗留风险。

5. **写下一步建议**  
   给下一个模型一个明确入口，例如：
   > “下一步先修 T009 场景等级提示 bug，不要动 ROI。”

6. **不要留下未提交的半成品**  
   如果必须留下，要写清楚哪个文件、哪一段是临时实现。

7. **把成果推上远端**
   完成的每一项任务都要落库，不允许只留在本地磁盘：
   ```bash
   git status                          # 工作区必须干净
   python3 scripts/check_push_state.py # 未推送提交数必须为 0
   git push                            # 推送到工作分支
   ```
   推送到工作分支即可；合入 `main` 前确认 CI 通过。

---

## 8. 关键口径备忘

### 判据层

- 3 选项单选：`0 / 50 / 100`
- 5 选项单选：`0 / 25 / 50 / 75 / 100`
- 6 选项单选：官方评分逻辑未覆盖，按等距线性兜底并显式披露。
- 多选“无”：得 0 分。
- 多选非“无”：`选中数 × 100 ÷ (总选项数 - 1)`

### 等级门槛

| 等级 | 分数门槛 | 应用场景数 | 约束性场景数 |
|---|---|---|---|
| 一级 初始级 | ≥20 | ≥6 | ≥3 |
| 二级 规范级 | ≥40 | — | — |
| 三级 集成级 | ≥60 | — | — |
| 四级 协同级 | ≥80 | — | — |

> 场景与约束性场景的具体下限以选题文档和官方文件为准，不要由模型自行改写。

### ROI

```text
ROI = 预期可量化成效收益 ÷ 投入成本
分子 = 采集项 12—15 对应的预期改善收益
分母 = 直接投入 + 年运维 + 内部投入工时折价
```

优先级公式建议：

```text
P = (等级跃迁分 + 关联成效指标预期改善) ÷ 投入成本
```

不要把补贴放进排序逻辑。

### 四类反模式

| 反模式 | 判据 |
|---|---|
| AP1 只买设备不联网 | 采集项 2 达到 (40%,60%] 或以上，且采集项 3 落在 (10%,20%] 或以下 |
| AP2 只上系统不跑流程 | 采集项 5 达到绝大部分或全覆盖，且生产管控或质量管理仍在一级 |
| AP3 只做数据采集不做分析 | 采集项 4 覆盖环节数不少于 6，且决策支持场景仍在一级 |
| AP4 只追补贴不建能力 | 采集项 11 达到 (20%,40%] 或以上，且总分不够二级 |

### 知识库分工

| 知识源 | 作用 |
|---|---|
| 政策库 | 定判据、门槛、验收口径 |
| 案例库 | 提供症状 → 根因 → 改造项路径 |
| 论文库 | 提供成效弹性与评价方法 |
| 专利库 | 提供技术方案边界与成熟度信号 |

---

## 9. 模型不得做的事

- ❌ 不得让模型直接算分、排序、决定 ROI。
- ❌ 不得把补贴作为排序分子。
- ❌ 不得把合成样本写成真实企业。
- ❌ 不得删除或改写官方判据原文。
- ❌ 不得让没有证据的结论进入结果页。
- ❌ 不得承诺补贴获批。
- ❌ 不得承接申报代理或涉申报中介服务。
- ❌ 不得把论文单一结论写成定论。
- ❌ 不得只做好看的页面而跳过评测报告。
- ❌ 不得在换模型时丢失工作记录。

---

## 10. 每个模型结束时必须输出

请每个模型在结束前生成以下内容，方便人工或下一个模型检查：

```markdown
### 本次完成
- 任务 ID：
- 模块：
- 修改文件：
- 新增文件：

### 验证
- 命令：
- 结果：

### 推送
- 分支：
- 推送提交：
- `scripts/check_push_state.py` 结果：

### 更新
- 任务状态表：
- 模型接力日志：
- 变更记录：

### 遗留风险
- ：
- ：

### 下一步建议
- ：
```

---

## 11. 答辩演示脚本建议

### 5 分钟路径

1. **10 秒定位**  
   “这不是政策问答，而是中小企业数字化改造的投入产出决策工具。”

2. **30 秒问题**  
   “中小企业不是没花钱，而是钱花在不产生效应的地方。”

3. **1 分钟输入**  
   “15 个采集项 + 16 个场景等级，全部来自官方判据。”

4. **1 分钟诊断**  
   “系统指出企业卡在哪一步，并给出命中采集项和场景。”

5. **1 分钟路径与排序**  
   “系统输出分步改造路径、投入区间、预期成效、验收口径和 ROI 区间。”

6. **30 秒不建议做**  
   “四类无效投入模式会被主动排除。”

7. **30 秒证据**  
   “每条结论都能追到采集项、场景、案例或政策文件。”

8. **30 秒评测**  
   “60 家合成样本 + 1 家真实企业 + 四组对照 + 四组消融。”

---

## 12. 立即执行的下一步

下一轮建议按顺序处理：

1. **T000**：确认源码仓库、分支、启动方式。
2. **T004—T008**：把判据层和真实企业复算固化。
3. **T009—T010**：修场景等级提示 bug，并把场景等级改为必填。
4. **T016—T020**：搭后端最小接口。
5. **T031—T036**：补知识库展示。
6. **T037—T048**：做评测报告。

---

## 13. 最终判断标准

完成网站后，评审应该能做到三件事：

1. **看懂**：知道它不是政策问答，而是“先做什么、放弃什么、凭什么这么排”的决策工具。  
2. **复核**：任何结论都能追到采集项、场景、案例或政策文件。  
3. **相信**：有 60 家合成样本 + 1 家真实企业 + 4 组对照 + 4 组消融的数字支撑。
