@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 启研 W0 Demo 启动中... 浏览器打开 http://127.0.0.1:8100/
uv run --no-project --with fastapi --with uvicorn --with pydantic python server/main.py
pause
