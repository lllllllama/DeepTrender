# DeepTrender Docker 镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建数据目录
RUN mkdir -p data output/figures output/reports

# 暴露端口
EXPOSE 5000

# 环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 启动命令
CMD ["gunicorn", "--config", "gunicorn.conf.py", "src.web.app:create_app()"]
