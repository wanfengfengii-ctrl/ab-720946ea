# syntax=docker/dockerfile:1
# verify 一次性服务镜像：后端代码测试 + 前端构建检查 + 对运行中服务做 API 冒烟。
FROM node:22-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY backend ./backend
COPY frontend ./frontend
COPY verify/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV BACKEND_URL=http://backend:8000 \
    WEB_URL=http://web \
    PIP_BREAK_SYSTEM_PACKAGES=1

ENTRYPOINT ["/entrypoint.sh"]
