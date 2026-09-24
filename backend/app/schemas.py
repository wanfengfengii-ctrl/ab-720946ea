"""API 请求/响应模型。"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

IdStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=32),
]


class BusIn(BaseModel):
    id: IdStr
    channels: Annotated[int, Field(ge=1, description="该总线可用通道数，至少为 1")]


class SentinelIn(BaseModel):
    id: IdStr
    bus: IdStr
    cost: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    readings: dict[IdStr, Literal[0, 1]]


class SolveRequest(BaseModel):
    fault_modes: Annotated[list[IdStr], Field(min_length=3, max_length=12)]
    buses: Annotated[list[BusIn], Field(min_length=1, max_length=18)]
    sentinels: Annotated[list[SentinelIn], Field(min_length=4, max_length=18)]


class SelectedSentinel(BaseModel):
    id: str
    bus: str
    cost: float


class BusUsage(BaseModel):
    bus: str
    used: int
    capacity: int


class Witness(BaseModel):
    sentinel: str
    readings: list[int]  # 与 pair 中两个故障模式顺序对应的读数


class PairEvidence(BaseModel):
    pair: list[str]
    witnesses: list[Witness]


class SolveStats(BaseModel):
    combinations_examined: int
    feasible_combinations: int


class SolveResponse(BaseModel):
    status: Literal["ok", "infeasible"]
    message: str
    selected: list[SelectedSentinel]
    total_cost: float | None
    sentinel_count: int
    bus_usage: list[BusUsage]
    evidence: list[PairEvidence]
    blocking_pairs: list[list[str]]
    stats: SolveStats
