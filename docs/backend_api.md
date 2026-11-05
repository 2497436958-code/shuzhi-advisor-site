# 后端 API 说明

## 启动

```bash
python3 -m pip install -r requirements-dev.txt
python3 api/main.py
```

访问：

```text
http://127.0.0.1:8000/
```

## 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查，返回在线状态和判据层规模 |
| GET | `/api/criteria` | 返回 15 个采集项与 16 个应用场景的官方原文数据 |
| GET | `/api/fixtures` | 返回示例企业列表 |
| GET | `/api/fixtures/{fixture_id}` | 返回单个示例企业的画像和预计算结果 |
| POST | `/api/evaluate` | 接收企业画像，返回评测 + 四段式结论（诊断 / 路径 / 排序 / 不建议做 / 政策注记） |
| GET | `/api/scenario_evidence` | 返回场景等级判定证据可用性 |
| GET | `/api/knowledge/stats` | 返回政策 / 案例 / 论文 / 专利四库的数量与字段口径 |

## `/api/evaluate`

输入为画像 JSON，至少包含：

```json
{
  "name": "某精密件制造企业",
  "answers": {
    "1": ["无"],
    "2": ["[0-10%]"]
  },
  "scenario_levels": {
    "S01": 1,
    "S02": 1
  }
}
```

完整画像应包含 15 个采集项答案和 16 个场景等级。

### 返回结构

与站点已发布的预计算结果（`precomputed/*.json` 的 `result`）同构，前端同一套渲染代码
同时支持实时结果与离线预计算结果：

```json
{
  "profile": {},
  "evaluation": {},
  "level_judgement": [],
  "item_results": [],
  "scenario_results": [],
  "diagnosis": [],
  "pathway": [],
  "ranking": [],
  "do_not": [],
  "scenario_evidence": {},
  "policy_notes": [],
  "policy_notes_status": {},
  "roi_assumptions": {},
  "meta": {
    "mode": "realtime",
    "engine": "advisor.scoring.engine / advisor.reasoning",
    "knowledge": {}
  }
}
```

`diagnosis`、`pathway`、`ranking`、`do_not` 的每个条目都带 `evidence_refs`
（官方原文引文 + 出处链接）。推理层的口径见 `docs/reasoning_layer.md`。

## 已知边界

- ROI 的成效弹性沿用站点演示口径，**未被公开案例支撑**，只用于排序，不作为结论数；
- 投入与收益按营业收入等比折算，折算律待真实企业校准；
- 场景等级由用户自评，系统只做规则判定，不替企业判断等级；
- 生产部署前应避免直接挂载整个仓库根目录；
- 后端部署需要同时部署前端，或配置 CORS。
