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
| POST | `/api/evaluate` | 接收企业画像，调用确定性打分器并返回评测结果 |
| GET | `/api/scenario_evidence` | 返回场景等级判定证据可用性 |

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

当前最小版返回：

```json
{
  "profile": {},
  "evaluation": {},
  "level_judgement": [],
  "diagnosis": [],
  "pathway": [],
  "ranking": [],
  "do_not": [],
  "policy_notes": [],
  "roi_assumptions": {},
  "meta": {
    "mode": "realtime",
    "engine": "advisor.scoring.engine",
    "reasoning_status": "pending"
  }
}
```

`reasoning_status = "pending"` 表示诊断、路径、排序和反模式尚未接入实时后端。  
不能把该状态删除或改成 `ready`，否则会让前端把未完成推理当成完整结果。

## 已知边界

- `/api/evaluate` 目前只保证判据层可实时复算；
- 四段式建议中的诊断、路径、ROI 排序和“不建议做”还未实时生成；
- 生产部署前应避免直接挂载整个仓库根目录；
- 后端部署需要同时部署前端，或配置 CORS。
