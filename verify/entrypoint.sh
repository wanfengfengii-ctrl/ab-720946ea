#!/bin/sh
# verify 服务入口：任一步骤失败立即以非零码退出。
set -eu

echo "== [1/3] 后端代码测试 (pytest) =="
python3 -m venv /opt/venv
. /opt/venv/bin/activate
pip install --quiet --no-cache-dir -r /srv/backend/requirements-dev.txt
cd /srv/backend
python -m pytest tests/ -q

echo "== [2/3] 前端构建检查 (tsc --noEmit + vite build) =="
cd /srv/frontend
npm ci --no-audit --no-fund
npm run build

echo "== [3/3] API 冒烟 (health / solve / 422 定位 / 前端页面) =="
python /srv/backend/scripts/smoke.py

echo "== VERIFY PASSED =="
