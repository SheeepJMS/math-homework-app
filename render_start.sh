#!/bin/bash
# Render 启动脚本：先执行迁移再启动应用
# 若 upgrade 失败（如生产库已有作业表但无 alembic 记录），则 stamp 后重试
set -e
echo ">>> Running migrations..."
if ! flask db upgrade; then
  echo ">>> Initial upgrade failed, stamping to b4fefe386c31 and retrying..."
  flask db stamp b4fefe386c31
  flask db upgrade
fi
echo ">>> Migrations OK, starting app..."
exec python app.py
