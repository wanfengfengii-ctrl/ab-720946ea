"""跨字段业务校验：重复编号、未知总线、读数缺失/多余等。

Pydantic 负责结构与取值范围校验；本模块在其通过后执行，返回带定位
信息的错误列表（loc 与 FastAPI 默认 422 响应的 loc 结构一致）。
"""

from __future__ import annotations

from .schemas import SolveRequest


def _err(loc: list, msg: str) -> dict:
    return {"loc": ["body", *loc], "msg": msg, "type": "value_error"}


def collect_business_errors(payload: SolveRequest) -> list[dict]:
    errors: list[dict] = []

    # 1. 故障模式编号重复
    seen: dict[str, int] = {}
    for i, mode in enumerate(payload.fault_modes):
        if mode in seen:
            errors.append(
                _err(["fault_modes", i], f"故障模式编号 '{mode}' 与第 {seen[mode] + 1} 项重复")
            )
        else:
            seen[mode] = i

    # 2. 总线编号重复
    seen = {}
    for i, bus in enumerate(payload.buses):
        if bus.id in seen:
            errors.append(_err(["buses", i, "id"], f"总线编号 '{bus.id}' 与第 {seen[bus.id] + 1} 项重复"))
        else:
            seen[bus.id] = i

    # 3. 哨点编号重复
    seen = {}
    for i, s in enumerate(payload.sentinels):
        if s.id in seen:
            errors.append(_err(["sentinels", i, "id"], f"哨点编号 '{s.id}' 与第 {seen[s.id] + 1} 项重复"))
        else:
            seen[s.id] = i

    bus_ids = {b.id for b in payload.buses}
    mode_ids = payload.fault_modes
    mode_set = set(mode_ids)

    for i, s in enumerate(payload.sentinels):
        # 4. 引用未知总线
        if s.bus not in bus_ids:
            errors.append(
                _err(["sentinels", i, "bus"], f"哨点 '{s.id}' 引用了未定义的总线 '{s.bus}'")
            )
        # 5. 读数缺失或多余
        keys = set(s.readings.keys())
        missing = [m for m in mode_ids if m not in keys]
        extra = [k for k in s.readings.keys() if k not in mode_set]
        if missing:
            errors.append(
                _err(
                    ["sentinels", i, "readings"],
                    f"哨点 '{s.id}' 缺少故障模式 {missing} 的读数",
                )
            )
        if extra:
            errors.append(
                _err(
                    ["sentinels", i, "readings"],
                    f"哨点 '{s.id}' 包含未定义故障模式 {extra} 的读数",
                )
            )

    return errors
