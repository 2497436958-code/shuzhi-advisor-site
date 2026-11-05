# 纯静态演示站

本目录由 `python3 tools/build_static_site.py` 生成，不依赖任何后端进程。

```bash
python3 -m http.server -d static_site 8080
# 浏览器打开 http://localhost:8080
```

页面加载 `/api/health` 失败会自动切到**离线模式**：读 `precomputed/` 里的
预计算结果，并在顶部明示「当前为预计算结果（非实时计算）」。

* `precomputed/`：6 份夹具的画像与预计算四段式结果
* `official/`：官方 PDF 原文，证据卡里的「打开原文」链接指向它

结果由冻结的判据层与计算层算出（见 `src/advisor/criteria/`、`src/advisor/scoring/`），
前端不做任何评分。


## 判据层复算

```bash
python3 scripts/verify_criteria.py
python3 -m unittest discover -s tests -v
python3 scripts/recompute_profile.py path/to/profile.json
```

详细说明见 `docs/criteria_recompute.md`。

## 开发环境

- Python：3.10 或以上；判据层只依赖标准库。
- Node.js：仅用于 `node --check app.js` 的前端语法检查。
- 本地预览：`python3 -m http.server 8081`。

### 常用验证

```bash
python3 scripts/verify_criteria.py
python3 -m unittest discover -s tests -v
node --check app.js
node scripts/check_frontend_pages.mjs
python3 scripts/check_contrast.py          # 配色对比度（WCAG AA）
python3 scripts/check_knowledge_schema.py  # 知识库 schema 与引用链
git diff --check
```

CI 会在 Python 3.10 / 3.11 / 3.12 下运行判据层校验和单元测试，并检查前端语法。

## 后端本地启动

```bash
python3 -m pip install -r requirements-dev.txt
python3 api/main.py
```

后端默认监听 `127.0.0.1:8000`，同时用于本地静态前端和 API 联调。

也可以直接使用：

```bash
uvicorn advisor.web.api:app --app-dir src --reload --port 8000
```

当前后端状态：

- `/api/evaluate` 已接入判据层与推理层：现场填写即可拿到四段式结果
  （诊断 → 路径 → 排序与不建议做 → 政策注记）；
- 反模式 AP1—AP4、诊断规则、选步与依赖顺序、ROI 区间与优先级全部由确定性代码算出，
  每条结论都带官方原文引文与出处链接；
- 四类知识库（政策 30 份 / 案例 259 条 / 论文 11 篇 + 3 条检索入口 / 专利 5 个大类口径）
  已入库，`GET /api/knowledge/stats` 可查数量与口径。

接口说明见 `docs/backend_api.md`，推理层口径见 `docs/reasoning_layer.md`，
知识库搬运记录见 `docs/knowledge_port.md`，路径参数反解记录见
`docs/pathway_params_provenance.md`。

## 知识库页面

站点底部的「知识库」区块给出政策 / 案例 / 论文 / 专利四类的数量、分类口径与检索入口：
关键词 + 分类下拉，每条都带原文链接。后端在线时支持检索，离线模式可浏览不检索。

```bash
python3 scripts/build_frontend_fixtures.py   # 重新生成前端冒烟测试用的接口样例
node scripts/check_frontend_pages.mjs        # 前端渲染冒烟测试（零依赖，无需浏览器）
```

冒烟测试用最小 DOM 桩把 app.js 的启动流程真跑一遍，覆盖知识库页、评测报告页、
方法页内容守卫，以及**四段式结果页**（真的提交一次评测，看摘要、诊断卡片、路径步骤、
排序表格有没有断）。

站点的「方法与口径」区块回答"结论是怎么来的"：判据出处与权重链乘、算分规则、
四级门槛与约束性场景要求、AP1—AP4 判据、路径与 ROI/优先级公式、知识库与评测口径、
局限与合规边界、可复算命令清单。

站点的「评测报告」区块展示四组对照、四组消融与六项指标的实测值与门槛判定，
数据来自 `data/evaluation/report.json`（在线时走 `GET /api/evaluation/report`）。
不达标与不可测的指标如实标注，真实层家数如实显示。

## 合成评测样本

`data/profiles/synthetic_60.json` 是 60 家合成评测样本（AP1—AP4 各 10 家、
正常对照 20 家），全部标 `synthetic`，真实企业 0 家。每条带"按构造应当命中什么"
与"引擎实测命中什么"两份记录，供评测指标直接使用。

```bash
python3 scripts/generate_synthetic_profiles.py          # 生成（固定种子，可复算）
python3 scripts/generate_synthetic_profiles.py --check   # 幂等自检
```

样本设计见 `docs/synthetic_samples.md`。

## 评测报告

```bash
python3 scripts/build_evaluation_report.py    # 跑 8 个组、算 6 项指标、出报告
```

输出 `data/evaluation/report.md`（人读）与 `data/evaluation/report.json`（接口用，
`GET /api/evaluation/report`）。报告覆盖**合成层 60 家**，真实层 0 家并如实标注。

当前结论（合成层）：

| 指标 | 实测 | 门槛 | 结论 |
|---|---|---|---|
| T041 诊断准确率 F1 | 100.0% | ≥80% | 达标 |
| T042 归因路径命中率 | 83.7% | ≥70% | 达标 |
| T043 排序一致性 Top-3 | 67.8% | ≥70% | **未达标**（已定位原因，见报告） |
| T044 反模式检出率 / 误报率 | 100.0% / 0.0% | ≥85% / ≤15% | 达标 |
| T045 ROI 测算偏差 | — | ≤20% | 不可测（需真实企业样本） |
| T046 跨行业泛化衰减 | 0.0% | ≤10pp | 达标 |

四组对照（纯 RAG / 纯规则 / RAG+计算器 / 完整闭环）与四组消融（去归因 /
去约束场景 / 去反模式 / 去判据锚定）都在报告里，各自关掉了什么写在
`src/advisor/evaluation/variants.py` 的文档字符串里。

## 推理层复算与一致性

```bash
python3 -m unittest discover -s tests -v   # 含判据层 100% 复算与诊断一致性测试
```

测试会校验：6 个样例的判据层结果与已发布预计算结果逐字段一致、
反模式命中一致、诊断条目一致、共同改造项的 ROI 数值完全一致、
以及每条结论都带非空证据链。
