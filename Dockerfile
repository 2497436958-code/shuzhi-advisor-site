# 后端镜像：只跑 API，静态站由 GitHub Pages 承担。
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
ENV ADVISOR_HOST=0.0.0.0 ADVISOR_PORT=8000
EXPOSE 8000
CMD ["uvicorn", "advisor.web.api:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
