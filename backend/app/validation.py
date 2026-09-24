"""请求体校验：重复编号、未知总线、读数缺失、通道数非法等问题精确定位。

校验成功后产出 :class:`NormalizedInput`，供求解器直接使用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schemas import MAX_MODES, MAX_SENTINELS, MIN_MODES, MIN_SENTINELS


class ValidationError(Exception):
    """收集式校验错误，errors 为定位字典列表。"""

    def __init__(self, errors: list[dict[str, str]]):
        self.errors = errors
        super().__init__(f"{len(errors)} validation error(s)")


@dataclass(frozen=True)
class Sentinel:
    id: str
    cost: float
    bus: str
    readings: dict[str, int]  # mode_id -> 0/1


@dataclass(frozen=True)
class Bus:
    id: str
    channels: int


@dataclass(frozen=True)
class NormalizedInput:
    modes: list[str]
    sentinels: list[Sentinel]
    buses: dict[str, Bus] = field(default_factory=dict)


def _is_str(v: Any) -> bool:
    return isinstance(v, str)


def _parse_int(v: Any) -> int | None:
    """接受 int 与数字字符串；布尔、浮点一律拒绝。"""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return None


def _parse_cost(v: Any) -> tuple[float | None, bool]:
    """返回 (值, 是否为有限数)。无法解析时值为 None。"""
    if isinstance(v, bool):
        return None, False
    if isinstance(v, (int, float)):
        f = float(v)
        return (f, f == f and f not in (float("inf"), float("-inf")))
    if isinstance(v, str):
        s = v.strip()
        if s:
            try:
                f = float(s)
            except ValueError:
                return None, False
            return (f, f == f and f not in (float("inf"), float("-inf")))
    return None, False


def validate_payload(payload: Any) -> NormalizedInput:
    errors: list[dict[str, str]] = []

    if not isinstance(payload, dict):
        raise ValidationError(
            [{"loc": "body", "msg": "请求体必须是 JSON 对象"}]
        )

    # ---- 顶层字段存在性与类型 ---------------------------------------------
    raw_modes = payload.get("modes")
    raw_sentinels = payload.get("sentinels")
    raw_buses = payload.get("buses")

    if not isinstance(raw_modes, list):
        errors.append({"loc": "modes", "msg": "故障模式列表缺失或不是数组"})
        raw_modes = []
    if not isinstance(raw_sentinels, list):
        errors.append({"loc": "sentinels", "msg": "哨点列表缺失或不是数组"})
        raw_sentinels = []
    if not isinstance(raw_buses, list):
        errors.append({"loc": "buses", "msg": "总线列表缺失或不是数组"})
        raw_buses = []

    # ---- 故障模式 -----------------------------------------------------------
    mode_ids: list[str] = []
    seen_modes: set[str] = set()
    for i, m in enumerate(raw_modes):
        loc = f"modes[{i}]"
        if not _is_str(m):
            errors.append({"loc": loc, "msg": "故障模式编号必须是字符串"})
            continue
        mid = m.strip()
        if not mid:
            errors.append({"loc": loc, "msg": "故障模式编号不能为空"})
            continue
        if mid in seen_modes:
            errors.append({"loc": loc, "msg": f"故障模式编号重复: {mid}"})
            continue
        seen_modes.add(mid)
        mode_ids.append(mid)

    if not any(e["loc"] == "modes" for e in errors):
        if not (MIN_MODES <= len(mode_ids) <= MAX_MODES):
            errors.append(
                {
                    "loc": "modes",
                    "msg": f"故障模式数量须为 {MIN_MODES}-{MAX_MODES} 个，当前 {len(mode_ids)} 个",
                }
            )

    # ---- 读出总线 -----------------------------------------------------------
    buses: dict[str, Bus] = {}
    seen_bus_ids: set[str] = set()
    for i, b in enumerate(raw_buses):
        loc = f"buses[{i}]"
        if not isinstance(b, dict):
            errors.append({"loc": loc, "msg": "总线项必须是对象"})
            continue
        bid = b.get("id")
        if not _is_str(bid) or not bid.strip():
            errors.append({"loc": f"{loc}.id", "msg": "总线编号缺失或为空"})
            bid = None
        else:
            bid = bid.strip()
            if bid in seen_bus_ids:
                errors.append({"loc": f"{loc}.id", "msg": f"总线编号重复: {bid}"})
            else:
                seen_bus_ids.add(bid)

        ch = _parse_int(b.get("channels"))
        if ch is None or ch < 0:
            errors.append(
                {"loc": f"{loc}.channels", "msg": "可用通道数必须是非负整数"}
            )
            ch = -1
        if bid is not None and bid not in buses:
            buses[bid] = Bus(id=bid, channels=max(ch, 0))

    # ---- 哨点 ---------------------------------------------------------------
    sentinels: list[Sentinel] = []
    seen_sentinel_ids: set[str] = set()
    for i, s in enumerate(raw_sentinels):
        loc = f"sentinels[{i}]"
        if not isinstance(s, dict):
            errors.append({"loc": loc, "msg": "哨点项必须是对象"})
            continue

        sid = s.get("id")
        if not _is_str(sid) or not sid.strip():
            errors.append({"loc": f"{loc}.id", "msg": "哨点编号缺失或为空"})
            sid = None
        else:
            sid = sid.strip()
            if sid in seen_sentinel_ids:
                errors.append({"loc": f"{loc}.id", "msg": f"哨点编号重复: {sid}"})
            else:
                seen_sentinel_ids.add(sid)

        cost, finite = _parse_cost(s.get("cost"))
        if cost is None:
            errors.append({"loc": f"{loc}.cost", "msg": "哨点费用必须是数字"})
        elif not finite or cost < 0:
            errors.append(
                {"loc": f"{loc}.cost", "msg": "哨点费用必须是非负有限数"}
            )

        bus = s.get("bus")
        if not _is_str(bus) or not bus.strip():
            errors.append({"loc": f"{loc}.bus", "msg": "哨点所属总线编号缺失或为空"})
            bus_ref = None
        else:
            bus_ref = bus.strip()
            if bus_ref not in buses:
                errors.append(
                    {
                        "loc": f"{loc}.bus",
                        "msg": f"哨点引用了未知总线: {bus_ref}",
                    }
                )

        # 读数矩阵：以 modes 为基准逐格校验
        readings: dict[str, int] = {}
        raw_readings = s.get("readings")
        if not isinstance(raw_readings, dict):
            errors.append({"loc": f"{loc}.readings", "msg": "读数必须是以故障模式为键的对象"})
            raw_readings = {}

        for mid in mode_ids:
            if mid not in raw_readings or raw_readings[mid] is None:
                errors.append(
                    {
                        "loc": f"{loc}.readings.{mid}",
                        "msg": f"哨点 {sid or loc} 对故障模式 {mid} 的二元读数缺失",
                    }
                )
                continue
            bit = _parse_int(raw_readings[mid])
            if bit not in (0, 1):
                errors.append(
                    {
                        "loc": f"{loc}.readings.{mid}",
                        "msg": "二元读数只能是 0 或 1",
                    }
                )
                continue
            readings[mid] = bit

        # 读数中引用了未定义的故障模式
        if isinstance(raw_readings, dict):
            for k in raw_readings:
                if k not in seen_modes:
                    errors.append(
                        {
                            "loc": f"{loc}.readings.{k}",
                            "msg": f"读数引用了未定义的故障模式: {k}",
                        }
                    )

        if sid is not None:
            sentinels.append(
                Sentinel(
                    id=sid,
                    cost=cost if cost is not None and finite and cost >= 0 else 0.0,
                    bus=bus_ref or "",
                    readings=dict(readings),
                )
            )

    # 存在结构性错误时不再叠加数量错误；否则按去重后的有效编号数判定
    if not any(e["loc"] == "sentinels" for e in errors):
        valid_count = len(seen_sentinel_ids)
        if not (MIN_SENTINELS <= valid_count <= MAX_SENTINELS):
            errors.append(
                {
                    "loc": "sentinels",
                    "msg": f"哨点数量须为 {MIN_SENTINELS}-{MAX_SENTINELS} 个，当前 {valid_count} 个",
                }
            )

    # ---- 总线通道容量的硬约束预检（属于业务非法输入，需定位到总线）-----------
    # 通道数小于 0 已在上面处理；这里检查“即便选中全部哨点也无解”的容量矛盾不算非法，
    # 容量是约束而非输入错误，交给求解器。但零通道总线上挂了哨点不构成非法（可不选）。

    if errors:
        raise ValidationError(errors)

    return NormalizedInput(modes=mode_ids, sentinels=sentinels, buses=buses)
