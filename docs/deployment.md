# 部署说明：静态站、后端与环境变量

本项目是"静态站 + 可选后端"两段式：

| 段 | 是什么 | 部署在哪 | 现状 |
|---|---|---|---|
| 静态站 | 判据原文、预计算结果、四类知识库、评测报告、方法与口径页 | GitHub Pages（从 `main` 分支构建） | 已上线，CI 自动构建 |
| 后端 | 实时评测与检索接口（FastAPI） | Render / Fly / Railway / 自己的机器 | 未部署（本地 `python3 api/main.py` 可跑） |

**后端不可用时静态站照常工作**：前端检测 `/api/health` 失败会切离线模式，
读 `precomputed/` 里的预计算结果，并在页面顶部明示"当前为预计算结果（非实时计算）"。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `ADVISOR_HOST` | `127.0.0.1` | 后端监听地址 |
| `ADVISOR_PORT` | `8000` | 后端监听端口 |
| `ADVISOR_CORS_ORIGINS` | 空 | 允许跨域访问的前端来源，逗号分隔。**默认空 = 不同源不开放** |

```bash
ADVISOR_HOST=0.0.0.0 ADVISOR_PORT=8080 python3 api/main.py
```

## 跨域（CORS）

前后端**同源**部署时不需要 CORS，默认就不开（少一个攻击面）。

前后端**分开**部署（例如 Pages 静态站 + Render 后端）时，必须显式允许来源：

```bash
ADVISOR_CORS_ORIGINS="https://2497436958-code.github.io" python3 api/main.py
```

只允许 `GET` 与 `POST`，只允许 `Accept` 与 `Content-Type` 请求头，不带凭据。
**不要写 `*`**：来源写具体域名，误配成通配等于把接口开到公网任意站点都能调。

## 静态目录白名单

后端不再把整个仓库根目录挂出去，只公开站点真正需要的路径：

| 路径 | 内容 |
|---|---|
| `/`、`/index.html`、`/app.js`、`/styles.css` | 页面本体 |
| `/precomputed/` | 6 份预计算样例与判据原文数据 |
| `/data/` | 知识库、合成样本、评测报告 |
| `/official/` | 官方 PDF 原文 |

源码、脚本、测试、`.git` 与 `README` 一律 404（工程结构与数据加工逻辑不该公开）。

## 后端部署

### Render

仓库根目录放 `render.yaml`：

```yaml
services:
  - type: web
    name: advisor-api
    env: python
    plan: free
    buildCommand: pip install -r requirements-dev.txt
    startCommand: uvicorn advisor.web.api:app --app-dir src --host 0.0.0.0 --port $PORT
    healthCheckPath: /api/health
    envVars:
      - key: ADVISOR_CORS_ORIGINS
        sync: false
```

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
ENV ADVISOR_HOST=0.0.0.0 ADVISOR_PORT=8000
CMD ["uvicorn", "advisor.web.api:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
```

### 无论哪种方式

- 健康检查打 `GET /api/health`，返回 `status=ok` 与判据层规模；
- 跨域来源用环境变量配，别改代码；
- 后端与静态站版本要对齐（前端契约变了就要同步部署后端）。

## 安全注意

- **本演示站是公开的**：GitHub Pages 上的 `data/` 目录对所有人可见。
  真实企业画像（任务 T038）**不要提交进这个公开仓库**，也不要传到公开的后端实例；
  需要演示真实层时，用本地环境或私有部署。
- 后端没有用户体系与鉴权，任何人调接口都会消耗推理资源；放到公网时建议加限流。
- 后端不落盘用户提交的画像（只在内存里算完就返回），但反向代理的访问日志仍可能记录请求体。
- 知识库里的政策与案例链接指向外部原文，页面只做跳转，不代理抓取。
