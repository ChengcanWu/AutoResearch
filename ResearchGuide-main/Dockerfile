# 启研：前端静态文件由 FastAPI 同源托管，一条命令起全站。
# 构建上下文必须是 ResearchGuide-main（控制台「Dockerfile 文件名」填 Dockerfile）。
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    QIYAN_DB=/data/qiyan.db \
    PYTHONPATH=/app/server

COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt

COPY . /app

RUN mkdir -p /data

EXPOSE 8100

CMD ["python", "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8100"]
