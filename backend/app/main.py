"""FastAPI 入口：健康检查 + 哨点组合推荐 API。"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .schemas import MAX_MODES, MAX_SENTINELS, MIN_MODES, MIN_SENTINELS
from .solver import solve
from .validation import ValidationError, validate_payload

app = FastAPI(title="海上变流器绝缘诊断哨点组合推荐", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/limits")
def limits() -> dict[str, int]:
    return {
        "min_modes": MIN_MODES,
        "max_modes": MAX_MODES,
        "min_sentinels": MIN_SENTINELS,
        "max_sentinels": MAX_SENTINELS,
    }


@app.post("/api/solve")
async def solve_endpoint(request: Request) -> JSONResponse:
    try:
        payload: Any = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "errors": [{"loc": "body", "msg": "请求体不是合法 JSON"}],
            },
        )

    try:
        normalized = validate_payload(payload)
    except ValidationError as exc:
        return JSONResponse(
            status_code=422, content={"ok": False, "errors": exc.errors}
        )

    result = solve(normalized)
    return JSONResponse(content={"ok": True, "result": result})
