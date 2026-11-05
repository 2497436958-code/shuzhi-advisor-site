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

## 推理层复算与一致性

```bash
python3 -m unittest discover -s tests -v   # 含判据层 100% 复算与诊断一致性测试
```

测试会校验：6 个样例的判据层结果与已发布预计算结果逐字段一致、
反模式命中一致、诊断条目一致、共同改造项的 ROI 数值完全一致、
以及每条结论都带非空证据链。
