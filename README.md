# 海上变流器绝缘诊断 · 哨点组合推荐

维护工程师在海上变流器出现绝缘告警后，需要从已标定的诊断哨点中选出一组检测组合，
使其能够**同时区分全部候选故障模式**。本项目提供 React + FastAPI 全栈应用：

- 页面录入 3–12 个故障模式、4–18 个哨点、各模式在每个哨点下的二元读数（0/1）、
  哨点费用、所属读出总线及总线可用通道数；
- 提交后由真实业务 API 完成求解，返回推荐组合与**逐对区分证据**；
- 每个选中哨点占用所属总线一个通道（通道容量为硬约束）；
- 任意两个不同故障模式必须至少被一个选中哨点给出不同读数；
- 输入问题（重复编号、未知总线、读数缺失、通道数非法等）逐条**定位反馈**；
- 无法区分时明确返回无方案及不可区分故障对。

## 求解规则

服务对所有**合法组合**（满足每条总线通道容量的哨点子集）做完整比较，依次取：

1. **总费用最低**；
2. **哨点数最少**；
3. 选中哨点按编号升序排列后，**编号序列字典序最小**。

规模上限（12 模式 × 18 哨点，子集数 2^18 = 262 144）下全量枚举为亚秒级。

## 目录结构

```
backend/            FastAPI 服务
  app/
    main.py         API 入口：/api/health、/api/limits、/api/solve
    validation.py   手工收集式校验，所有错误带 loc 定位
    solver.py       合法组合 DFS 全枚举 + 三级择优 + 逐对证据
  tests/            pytest（求解规则、容量约束、错误定位、API 冒烟）
  scripts/smoke.py  纯标准库 API 冒烟脚本（容器与本地通用）
  Dockerfile
frontend/           React + TypeScript + Vite
  src/App.tsx       矩阵录入、错误高亮、输入变更撤下旧结论、结果展示
  Dockerfile        多阶段构建，nginx 托管静态资源并代理 /api
verify/             一次性校验服务（pytest + 前端构建 + API 冒烟）
docker-compose.yml  backend / web / verify 三服务编排
```

## 快速开始

```bash
# 可选：配置宿主机端口
cp .env.example .env   # BACKEND_PORT / WEB_PORT

docker compose up --build
# 打开 http://localhost:8080 （即 WEB_PORT）
```

- 前端页面：`http://localhost:<WEB_PORT>`
- 后端 API：`http://localhost:<BACKEND_PORT>`
- 健康检查：`GET /api/health`（backend 与 web 均在 Compose 中配置了 healthcheck）

## API

`POST /api/solve`

请求：

```json
{
  "modes": ["M1", "M2", "M3"],
  "buses": [{"id": "B1", "channels": 4}],
  "sentinels": [
    {"id": "S1", "cost": 1, "bus": "B1",
     "readings": {"M1": 0, "M2": 1, "M3": 0}}
  ]
}
```

成功（有方案）返回 `selection`、`total_cost`、`sentinel_count`、`evidence`
（每个故障模式对的见证哨点与两端读数）、`bus_usage` 及枚举统计；
无方案返回 `feasible: false`、原因及 `indistinguishable_pairs`；
输入非法返回 HTTP 422，`errors` 中每项含 `loc`（如
`sentinels[2].readings.M3`、`buses[0].channels`、`sentinels[0].bus`）与 `msg`。

## 校验与 verify 一次性服务

Compose 提供名为 `verify` 的 profile 服务，它会：

1. 在 Python venv 中运行后端 `pytest`；
2. 执行前端 `tsc --noEmit` 类型检查与 `vite build` 构建检查；
3. 对已健康运行的 backend / web 执行 API 冒烟（健康检查、正常求解、无方案、422 定位、页面可达）；

随后自行退出，**以退出码报告结果**（0 通过，非 0 失败）：

```bash
docker compose --profile verify run --rm verify
echo $?
```

## 前端行为约定

- 任何输入变更（编号、费用、总线、通道数、读数、增删行）都会立即撤下上一次的结论与报错，
  并作废旧的在途响应，避免展示与当前输入不符的推荐；
- 读数格只接受 0/1，留空提交时由服务端定位为“读数缺失”并高亮对应单元格。
