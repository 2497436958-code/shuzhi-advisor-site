# 静态演示站（评委点开就看的那一版）

纯静态：无后端、无构建、无第三方依赖。`index.html` + `assets/` + `data/` 直接丢进任何
静态托管（nginx 子路径、OSS/COS、GitHub Pages）就能跑。

```
index.html            页面骨架（含 16 场景雷达、章节动效挂点）
assets/styles.css     基础组件与设计令牌（含深色模式）
assets/redesign.css   改版视觉层
assets/typography.css 思源宋体/黑体 + Times 字体系统
assets/motion-hero.css / hero-editorial.css   首屏排版与入场
assets/cinematic-scene.css / .js              首屏 Canvas 工厂场景
assets/chapter-film.css / .js                 章节背景影像
assets/continuity.css / .js                   章节滚动衔接与左侧章节索引
assets/spectacle.css / .js                    16 场景雷达与滚动进度
assets/scenario-gallery.css / scenario-atlas.js  场景配图切换与光箱
assets/engine.js      判据引擎：计分、定级、场景缺口（可直接 require，用于回归测试）
assets/app.js         渲染与交互
assets/img/           首屏、章节与 16 场景配图（AI 生成示意图，非实拍）
assets/fonts/         本地 WOFF2 中文字体（含 SIL OFL 许可文本）
data/criteria.json    官方判据（15 采集项 + 16 场景 + 四级门槛）
data/fixtures.json    6 个示例企业的元信息
data/samples/*.json   6 个示例企业的完整预计算结果（诊断 / 路径 / 排序 / 政策）
data/policy-notes.json  与结论直接相关的政策注解
official/             官方 PDF 原文（证据卡"打开原文"指向它）
单文件版/             打包好的单文件 HTML，双击即可离线演示
```

改版资源一共 9 个 CSS、6 个 JS，加载顺序在 `index.html` 里固定：先
`styles.css → redesign → 动效层`，脚本在 `engine.js`、`app.js` 之后加载动效层。
新增样式层请接在 `hero-editorial.css` 之后，它是最外层覆盖，便于回退。

## 本地预览

```bash
python -m http.server 8000 --directory static_site
# 打开 http://127.0.0.1:8000
```

直接双击 `index.html` 不行：`file://` 会被同源策略拦住，读不到 `data/*.json`。
要双击看，用 `单文件版/数改指导智能体-演示.html`。

## 数据从哪来（别再手工导出）

```bash
python tools/sync_site_data.py            # 从后端重导 data/
python tools/sync_site_data.py --check    # 只比对：与后端不一致就返回 1
node static_site/test-regression.mjs      # 浏览器引擎 vs 后端，6 份样本逐项比对
node static_site/build-single.mjs         # 重新打包单文件版
python tools/build_site_manifest.py       # 写入确定性发布清单（提交 build-manifest.json）
python tools/build_site_manifest.py --check # 校验清单、全部 HTML 本地 src/href 与问答索引
```

判据、结果、政策库或静态资源任一改动后，重新生成发布清单再提交。`data/` 是**导出快照**，
不是手写文件；`meta.generated_at` 故意写成固定说明文字，避免每次导出都产生无意义 diff。

## 两条数据通路

| 通路 | 数据来源 | 投入产出 |
|---|---|---|
| 示例企业 | `data/samples/*.json`（后端预计算） | 完整，含 ROI 区间与排序 |
| 自定义画像 | `assets/engine.js` 浏览器内实算 | 不出金额，改出场景缺口优先级表 |

自定义画像不给金额是**故意的**：金额依赖后端的成本区间与成效弹性系数，前端没有这份库，
编一个数出来会毁掉"可回查"这个立身之本。页面对应位置已写明。

## 引擎与后端的对齐

`engine.js` 是从 6 份样本反推并全量验证的：

- 单选：`score = 选项索引 / (选项数 - 1) × 100`
- 多选：`score = 选中数 / 有效选项数 × 100`，「无」不计入分母，单选「无」得 0
- 单项：`points = max_points × score / 100`
- 总分：未取整 points 求和后 `round2`，采用 half-even（对齐 Python `round`，用 `toFixed` 会差 0.01）
- 定级：得分、达标场景数、其中约束性场景数**三项同时满足**
- 场景缺失：按规则基线兜底为 1 级（对齐后端 `rule_baseline`）

`node static_site/test-regression.mjs` 当前：**6/6 通过，二级校验 6/6 通过**。

## 部署

见 `docs/` 与工作区里的《公网部署方案》。最短路径：nginx 里给这个目录一个 location，
配 `auth_basic` 给评委账号密码；后端挂了也不影响，页面自动走预计算数据并在顶部标注。

### 发布验收

正式静态站的发布物是整个 `static_site/`，其中包含 `ask.html`、`assets/agent/` 与
`data/agent/` 四个问答索引；不能只上传首页或旧版根目录资源。发布前运行：

```bash
bash tools/deploy.sh check
```

发布后，用同一工作树的清单逐项比对远端字节内容：

```bash
python tools/check_site_integrity.py https://example.com/site/
```

该命令会读取本地 `build-manifest.json`，校验远端清单及每个文件的 SHA-256；404、网络错误
或任一文件不一致都会失败。清单不含时间戳；本地默认 `git_commit` 为稳定的 `development`，避免
一次提交仅因 HEAD 改变而使已跟踪清单失效。正式发布可设置 `BUILD_SHA` 写入实际发布提交。

完整的生产发布、回滚、GitHub Environment 审批和必需 Secrets 清单见
[`deploy/README.md`](../deploy/README.md)。上线验收建议使用
`tools/check_live_site.py`：它会核对 `build-manifest.json`、四个 HTML 页面、问答资源及
浏览器层的标题/核心 DOM/console 错误；没有浏览器默认失败，只有明确传 `--http-only` 才跳过。
