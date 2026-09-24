# 海上变流器诊断哨点组合推荐

海上变流器出现绝缘告警后，维护工程师需要从已标定的诊断哨点中选出一组
**可同时区分全部候选故障模式**的检测组合。本系统在后端完整枚举所有合法
哨点组合，按统一规则给出最优方案与逐对区分证据，避免逐项挑选低成本哨点
后仍留下无法判别的故障对。

## 功能

- 页面录入 3–12 个故障模式、4–18 个哨点、1–18 条读出总线；
- 每个哨点在各故障模式下的二元读数（0/1）、费用、所属总线；每条总线的可用通道数；
- 提交后经真实业务 API（`POST /api/solve`）求解并展示：
  - 推荐哨点组合（总费用、哨点数、总线通道占用）；
  - 逐对区分证据（每对故障模式由哪些选中哨点给出不同读数）；
  - 无法区分时明确返回「无可行方案」及不可区分的故障对；
- 每个选中哨点占用所属总线一个通道，任一总线被选哨点数不得超过其通道数；
- 服务端完整比较所有合法组合（`2^n - 1` 个子集逐一判定），依次按
  **总费用最低 → 哨点数最少 → 编号升序序列字典序最小** 取最优；
- 重复编号、未知总线、读数缺失/多余、通道数不合法等输入错误均以 422
  响应定位到具体字段，页面同步高亮；
- 页面任意输入变更后立即撤下旧结论。

## 目录结构

```
├── docker-compose.yml      # backend / frontend / verify 三个服务
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── main.py         # 路由与应用入口
│   │   ├── schemas.py      # 请求/响应模型（Pydantic）
│   │   ├── validation.py   # 跨字段业务校验（重复编号、未知总线、读数缺失…）
│   │   └── solver.py       # 全组合枚举求解器
│   ├── tests/              # pytest 单元与接口测试
│   └── Dockerfile
├── frontend/               # React + Vite 前端（nginx 托管并反代 /api）
│   ├── src/
│   ├── nginx.conf
│   └── Dockerfile
└── verify/                 # 一次性校验服务（代码测试 + 构建检查 + API 冒烟）
    ├── Dockerfile
    └── run_verify.py
```

## 快速开始

```bash
docker compose up --build
```

- 前端页面：http://localhost:8080 （`WEB_PORT` 可改）
- 后端 API 文档（Swagger UI）：http://localhost:8000/docs （`API_PORT` 可改）

### 宿主机端口配置

通过环境变量覆盖默认端口：

```bash
WEB_PORT=9000 API_PORT=9001 docker compose up --build
```

| 变量       | 默认 | 说明                 |
| ---------- | ---- | -------------------- |
| `WEB_PORT` | 8080 | 前端页面宿主机端口   |
| `API_PORT` | 8000 | 后端 API 宿主机端口  |

### 健康检查

- `backend`：`GET /api/health`，Compose 中以 `urllib` 探测；
- `frontend`：nginx `/healthz`，Compose 中以 `wget` 探测；
- `frontend` 与 `verify` 均通过 `depends_on: service_healthy` 等待依赖就绪。

## 一次性校验服务 verify

`verify` 服务依次完成：**后端代码测试（pytest）→ 构建检查（前端构建产物、
后端可导入）→ API 冒烟（健康检查、正例求解、各类 422 定位、无方案场景、
前端页面可达）**，随后自行退出并以退出码报告结果（0 通过 / 非 0 失败）。

```bash
docker compose up --build --exit-code-from verify verify
echo $?   # 0 表示全部通过
```

说明：前端构建检查在 verify 镜像构建阶段强制执行（`npm run build` 失败则
镜像构建失败，`docker compose up --build` 以非零退出码结束）；容器运行
时再执行 pytest 与 API 冒烟，结果同样体现在退出码上。

## API 说明

### `POST /api/solve`

请求体：

```json
{
  "fault_modes": ["F1", "F2", "F3"],
  "buses": [{"id": "B1", "channels": 1}, {"id": "B2", "channels": 2}],
  "sentinels": [
    {"id": "S1", "bus": "B1", "cost": 5, "readings": {"F1": 0, "F2": 0, "F3": 1}},
    {"id": "S2", "bus": "B2", "cost": 5, "readings": {"F1": 0, "F2": 1, "F3": 0}},
    {"id": "S3", "bus": "B2", "cost": 9, "readings": {"F1": 0, "F2": 1, "F3": 1}},
    {"id": "S4", "bus": "B2", "cost": 1, "readings": {"F1": 0, "F2": 0, "F3": 0}}
  ]
}
```

约束：故障模式 3–12 个、哨点 4–18 个、总线 1–18 条；编号 1–32 字符且各自
不可重复；读数必须为 0/1 且恰好覆盖全部故障模式；通道数为 ≥1 的整数；
费用为 ≥0 的数值（内部按小数点后 6 位量化比较，避免浮点误差）。

成功响应（`status: "ok"`）：

```json
{
  "status": "ok",
  "selected": [{"id": "S1", "bus": "B1", "cost": 5}, {"id": "S2", "bus": "B2", "cost": 5}],
  "total_cost": 10,
  "sentinel_count": 2,
  "bus_usage": [{"bus": "B1", "used": 1, "capacity": 1}, {"bus": "B2", "used": 1, "capacity": 2}],
  "evidence": [
    {"pair": ["F1", "F2"], "witnesses": [{"sentinel": "S2", "readings": [0, 1]}]},
    {"pair": ["F1", "F3"], "witnesses": [{"sentinel": "S1", "readings": [0, 1]}]},
    {"pair": ["F2", "F3"], "witnesses": [{"sentinel": "S1", "readings": [0, 1]}, {"sentinel": "S2", "readings": [1, 0]}]}
  ],
  "blocking_pairs": [],
  "stats": {"combinations_examined": 15, "feasible_combinations": 6}
}
```

无可行方案响应（`status: "infeasible"`）：`blocking_pairs` 列出即使选中
全部哨点也无法区分的故障对；若全集可区分但通道约束导致无解，
`blocking_pairs` 为空且 `message` 说明原因。

输入非法时返回 422，`detail` 中每项含 `loc`（字段定位，如
`["body", "sentinels", 3, "id"]`）与 `msg`（中文错误说明），页面据此
高亮对应输入。

### `GET /api/health`

返回 `{"status": "ok"}`，用于健康检查。

## 求解规则

设哨点集合为 `S`，故障模式两两组合共 `C(m,2)` 对。哨点子集 `T` 可行
当且仅当：

1. 对任意两个不同故障模式，`T` 中至少一个哨点给出不同读数；
2. 对每条总线，`T` 中属于该总线的哨点数不超过其通道数。

服务端枚举全部 `2^|S| - 1` 个非空子集逐一判定（响应中
`stats.combinations_examined` 可见），在所有可行子集中依次按：

1. 总费用最低；
2. 哨点数量最少；
3. 按哨点编号升序排列后的编号序列字典序最小（编号按字符串序比较）；

取最优者返回，并给出每一对故障模式的全部见证哨点作为区分证据。

## 本地开发

```bash
# 后端（http://localhost:8000）
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload
.venv/bin/pytest -q            # 运行测试

# 前端（http://localhost:5173，/api 自动代理到 8000）
cd frontend
npm ci
npm run dev
npm run build                  # 构建检查
```
