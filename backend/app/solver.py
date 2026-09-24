"""诊断哨点组合求解器。

从候选哨点中枚举全部合法组合，找出能够区分所有故障模式两两组合的最优方案。
优化顺序（依次）：
  1. 总费用最低
  2. 哨点数量最少
  3. 按哨点编号升序排列后的编号序列字典序最小

约束：每个被选中的哨点占用其所属总线的一个通道，任一总线上被选中的
哨点数量不得超过该总线的可用通道数。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 费用内部按 1e-6 精度量化为整数计算，避免浮点累计误差影响方案比较。
COST_SCALE = 1_000_000


@dataclass(frozen=True)
class BusSpec:
    id: str
    channels: int


@dataclass(frozen=True)
class SentinelSpec:
    id: str
    bus: str
    cost: float
    readings: dict[str, int]  # 故障模式编号 -> 0/1


@dataclass
class SolveOutcome:
    status: str  # "ok" | "infeasible"
    message: str
    selected: list[dict] = field(default_factory=list)       # 选中的哨点（按编号升序）
    total_cost: float | None = None
    sentinel_count: int = 0
    bus_usage: list[dict] = field(default_factory=list)      # 每条总线的通道占用
    evidence: list[dict] = field(default_factory=list)       # 逐对区分证据
    blocking_pairs: list[list[str]] = field(default_factory=list)  # 全集也无法区分的故障对
    combinations_examined: int = 0
    feasible_combinations: int = 0


def _iter_bits(mask: int):
    while mask:
        lsb = mask & -mask
        yield lsb.bit_length() - 1
        mask ^= lsb


def solve(mode_ids: list[str], buses: list[BusSpec], sentinels: list[SentinelSpec]) -> SolveOutcome:
    """完整枚举所有非空哨点子集，返回最优可行方案或无可行方案的结论。"""
    m = len(mode_ids)
    n = len(sentinels)

    # 故障模式两两组合，每个组合对应判别掩码中的一个比特位。
    pairs: list[tuple[int, int]] = [(i, j) for i in range(m) for j in range(i + 1, m)]
    full_mask = (1 << len(pairs)) - 1

    # 每个哨点的判别掩码：读数不同的故障对置位。
    disc_masks: list[int] = []
    for s in sentinels:
        mask = 0
        bit = 1
        r = s.readings
        for i, j in pairs:
            if r[mode_ids[i]] != r[mode_ids[j]]:
                mask |= bit
            bit <<= 1
        disc_masks.append(mask)

    bus_capacity = {b.id: b.channels for b in buses}
    sentinel_bus = [s.bus for s in sentinels]
    cost_units = [round(s.cost * COST_SCALE) for s in sentinels]

    size = 1 << n
    # 子集 DP：cover/total_cost/count 均按“去掉最低位”的递推计算。
    cover = [0] * size
    total_units = [0] * size
    count = [0] * size

    best_key: tuple[int, int, tuple[str, ...]] | None = None
    best_subset = 0
    feasible = 0

    for subset in range(1, size):
        lsb = subset & -subset
        idx = lsb.bit_length() - 1
        prev = subset ^ lsb

        cov = cover[prev] | disc_masks[idx]
        units = total_units[prev] + cost_units[idx]
        cnt = count[prev] + 1
        cover[subset] = cov
        total_units[subset] = units
        count[subset] = cnt

        if cov != full_mask:
            continue

        # 通道约束：每条总线上被选中的哨点数不得超过其通道数。
        usage: dict[str, int] = {}
        ok = True
        for idx2 in _iter_bits(subset):
            bus = sentinel_bus[idx2]
            used = usage.get(bus, 0) + 1
            if used > bus_capacity[bus]:
                ok = False
                break
            usage[bus] = used
        if not ok:
            continue

        feasible += 1
        ids = tuple(sorted(sentinels[t].id for t in _iter_bits(subset)))
        key = (units, cnt, ids)
        if best_key is None or key < best_key:
            best_key = key
            best_subset = subset

    examined = size - 1

    if best_key is None:
        # 无法给出方案：区分是“全集也覆盖不了某些故障对”还是“通道限制”导致。
        all_mask = 0
        for mask in disc_masks:
            all_mask |= mask
        blocking = [
            [mode_ids[i], mode_ids[j]]
            for k, (i, j) in enumerate(pairs)
            if not (all_mask >> k) & 1
        ]
        if blocking:
            message = "无可行方案：即使选中全部哨点，仍无法区分部分故障模式对。"
        else:
            message = "无可行方案：存在可完全区分的哨点组合，但总线通道数限制下没有任何组合可行。"
        return SolveOutcome(
            status="infeasible",
            message=message,
            blocking_pairs=blocking,
            combinations_examined=examined,
            feasible_combinations=0,
        )

    selected_idx = sorted(_iter_bits(best_subset), key=lambda t: sentinels[t].id)
    selected = [
        {"id": sentinels[t].id, "bus": sentinels[t].bus, "cost": sentinels[t].cost}
        for t in selected_idx
    ]

    used_by_bus: dict[str, int] = {}
    for t in selected_idx:
        used_by_bus[sentinels[t].bus] = used_by_bus.get(sentinels[t].bus, 0) + 1
    bus_usage = [
        {"bus": b.id, "used": used_by_bus.get(b.id, 0), "capacity": b.channels}
        for b in sorted(buses, key=lambda b: b.id)
    ]

    # 逐对区分证据：每一对故障模式，列出选中哨点中所有读数不同的见证哨点。
    evidence = []
    for i, j in pairs:
        witnesses = []
        for t in selected_idx:
            s = sentinels[t]
            ri, rj = s.readings[mode_ids[i]], s.readings[mode_ids[j]]
            if ri != rj:
                witnesses.append({"sentinel": s.id, "readings": [ri, rj]})
        evidence.append({"pair": [mode_ids[i], mode_ids[j]], "witnesses": witnesses})

    total_cost = best_key[0] / COST_SCALE
    return SolveOutcome(
        status="ok",
        message="已找到最优哨点组合。",
        selected=selected,
        total_cost=total_cost,
        sentinel_count=len(selected_idx),
        bus_usage=bus_usage,
        evidence=evidence,
        blocking_pairs=[],
        combinations_examined=examined,
        feasible_combinations=feasible,
    )
