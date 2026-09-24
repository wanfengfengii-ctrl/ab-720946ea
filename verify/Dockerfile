# verify 一次性服务：代码测试 + 构建检查 + API 冒烟，完成后自行退出并以退出码报告结果。

# 阶段 1：后端测试环境（依赖 + 源码 + 测试）
FROM python:3.12-slim AS backend-env
WORKDIR /app
COPY backend/requirements.txt backend/requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY backend/ ./

# 阶段 2：前端构建检查（构建失败则 verify 镜像构建失败，从而以非零退出码报告）
FROM node:20-alpine AS frontend-build
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# 阶段 3：verify 运行时
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1

# 后端依赖、源码与测试（pytest 在容器内执行，结果直接体现在退出码上）
COPY --from=backend-env /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=backend-env /app /app
# 前端构建产物（阶段 2 已完成构建检查，此处校验产物完整性）
COPY --from=frontend-build /web/dist /web/dist

COPY verify/run_verify.py /verify/run_verify.py

ENV API_BASE=http://backend:8000 \
    WEB_BASE=http://frontend:80 \
    VERIFY_WAIT_SECONDS=90

WORKDIR /app
CMD ["python", "/verify/run_verify.py"]
