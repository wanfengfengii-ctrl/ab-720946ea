"""FastAPI 应用入口。"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .schemas import SolveRequest, SolveResponse
from .solver import BusSpec, SentinelSpec, solve
from .validation import collect_business_errors

app = FastAPI(
    title="海上变流器诊断哨点组合推荐",
    description=(
        "在总线通道约束下，从候选诊断哨点中枚举全部组合，"
        "选出可区分全部故障模式两两组合的最优哨点组合。"
    ),
    version="1.0.0",
)

# 前端经 nginx 同源代理访问；此处放开 CORS 便于本地开发（vite dev server）。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/solve", response_model=SolveResponse)
def solve_endpoint(payload: SolveRequest) -> SolveResponse:
    errors = collect_business_errors(payload)
    if errors:
        # 与 FastAPI 默认校验错误保持相同的 {detail: [{loc, msg, type}]} 结构。
        raise HTTPException(status_code=422, detail=errors)

    outcome = solve(
        mode_ids=payload.fault_modes,
        buses=[BusSpec(id=b.id, channels=b.channels) for b in payload.buses],
        sentinels=[
            SentinelSpec(id=s.id, bus=s.bus, cost=s.cost, readings=s.readings)
            for s in payload.sentinels
        ],
    )

    return SolveResponse(
        status=outcome.status,
        message=outcome.message,
        selected=outcome.selected,
        total_cost=outcome.total_cost,
        sentinel_count=outcome.sentinel_count,
        bus_usage=outcome.bus_usage,
        evidence=outcome.evidence,
        blocking_pairs=outcome.blocking_pairs,
        stats={
            "combinations_examined": outcome.combinations_examined,
            "feasible_combinations": outcome.feasible_combinations,
        },
    )
