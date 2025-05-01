FROM python:3.9-slim

# 安装SQLite工具
RUN apt-get update && apt-get install -y sqlite3

# 创建工作目录
WORKDIR /app

# 创建备份目录
RUN mkdir -p /backups

# 复制备份脚本
COPY backup.py .

CMD ["python", "backup.py"] 