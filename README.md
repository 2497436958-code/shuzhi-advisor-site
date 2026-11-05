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
