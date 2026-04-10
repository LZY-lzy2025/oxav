# 使用官方 Playwright 镜像
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 将代码和频道文件一起复制进容器
COPY main.py .
COPY channels.txt .

# Render 推荐通过环境变量 PORT 来指定端口，我们默认给 8000
ENV PORT=8000
EXPOSE 8000

# 启动命令
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
