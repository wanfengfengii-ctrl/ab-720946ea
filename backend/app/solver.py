"""诊断哨点组合求解器。

通过深度优先枚举完整比较所有 *合法组合*（满足每条总线通道容量的哨点子集），
并依次按以下准则取最优：

1. 总费用最低；
2. 哨点数最少；
3. 选中哨点按编号升序排列后的编号序列字典序最小。

区分判据：任意两个不同故障模式，至少被一个选中哨点给出不同读数。
"""

from __future__ import annotations

from dataclasses import dataclass

from .validation import NormalizedInput

COST_EPS = 1e-9


@dataclass
class Pair:
    index: int
    a: str
    b: str


def _build_pairs(mode_ids: list[str]) -> list[Pair]:
    pairs: list[Pair] = []
    idx = 0
    for i in range(len(mode_ids)):
        for j in range(i + 1, len(mode_ids)):
            pairs.append(Pair(idx, mode_ids[i], mode_ids[j]))
            idx += 1
    return pairs


def _sentinel_signature(readings: dict[str, int], pairs: list[Pair]) -> int:
    """该哨点能区分的故障对位图：第 p 位置 1 表示两端读数不同。"""
    sig = 0
    for p in pairs:
        if readings[p.a] != readings[p.b]:
            sig |= 1 << p.index
    return sig


def solve(data: NormalizedInput) -> dict:
    modes = data.modes
    sentinels = data.sentinels  # 输入顺序即哨点编号提交顺序，固定枚举次序
    pairs = _build_pairs(modes)
    full_cover = (1 << len(pairs)) - 1

    sigs = [_sentinel_signature(s.readings, pairs) for s in sentinels]
    bus_ids = [s.bus for s in sentinels]
    bus_capacity = {bid: b.channels for bid, b in data.buses.items()}

    # 即便选上全部哨点也无法区分的故障对：结构性不可区分
    union_all = 0
    for sig in sigs:
        union_all |= sig
    impossible_pairs = [
        {"mode_a": p.a, "mode_b": p.b}
        for p in pairs
        if not ((union_all >> p.index) & 1)
    ]

    best_mask = -1
    best_cost = 0.0
    best_count = 0
    evaluated = 0

    # 各总线当前已占用通道；DFS 保证任何被访问节点都是合法组合
    bus_used: dict[str, int] = {bid: 0 for bid in bus_capacity}

    def consider(mask: int, cover: int, cost: float, count: int) -> None:
        nonlocal best_mask, best_cost, best_count
        if cover != full_cover:
            return
        if best_mask == -1:
            best_mask, best_cost, best_count = mask, cost, count
            return
        if cost < best_cost - COST_EPS:
            better = True
        elif cost > best_cost + COST_EPS:
            better = False
        elif count != best_count:
            better = count < best_count
        else:
            better = _sorted_ids(mask) < _sorted_ids(best_mask)
        if better:
            best_mask, best_cost, best_count = mask, cost, count

    def _sorted_ids(mask: int) -> list[str]:
        return sorted(
            sentinels[k].id for k in range(len(sentinels)) if (mask >> k) & 1
        )

    def dfs(i: int, mask: int, cover: int, cost: float, count: int) -> None:
        nonlocal evaluated, best_mask
        if i == len(sentinels):
            evaluated += 1
            consider(mask, cover, cost, count)
            return

        # 不选第 i 个哨点
        dfs(i + 1, mask, cover, cost, count)

        # 选第 i 个哨点（受总线通道容量约束）
        bid = bus_ids[i]
        if bus_used[bid] < bus_capacity[bid]:
            bus_used[bid] += 1
            dfs(
                i + 1,
                mask | (1 << i),
                cover | sigs[i],
                cost + sentinels[i].cost,
                count + 1,
            )
            bus_used[bid] -= 1

    dfs(0, 0, 0, 0.0, 0)

    total_combinations = 1 << len(sentinels)

    if best_mask == -1:
        return {
            "feasible": False,
            "reason": (
                "存在任何哨点都无法区分的故障模式对"
                if impossible_pairs
                else "受总线可用通道数限制，不存在可区分全部故障模式的合法组合"
            ),
            "indistinguishable_pairs": impossible_pairs,
            "combinations_evaluated": evaluated,
            "total_combinations": total_combinations,
        }

    selected_idx = [
        k for k in range(len(sentinels)) if (best_mask >> k) & 1
    ]
    selected_ids = sorted(sentinels[k].id for k in selected_idx)
    id_order = {s.id: k for k, s in enumerate(sentinels)}

    # 逐对区分证据：取输入顺序最靠前的选中见证哨点（确定性输出）
    evidence: list[dict] = []
    for p in pairs:
        witness = None
        for k in selected_idx:
            if (sigs[k] >> p.index) & 1:
                witness = sentinels[k]
                break
        assert witness is not None  # cover == full_cover 保证存在
        evidence.append(
            {
                "mode_a": p.a,
                "mode_b": p.b,
                "witness": witness.id,
                "reading_a": witness.readings[p.a],
                "reading_b": witness.readings[p.b],
            }
        )

    usage: dict[str, list[str]] = {}
    for k in selected_idx:
        usage.setdefault(sentinels[k].bus, []).append(sentinels[k].id)
    bus_usage_out = [
        {
            "bus": bid,
            "selected": sorted(ids),
            "used": len(ids),
            "capacity": bus_capacity[bid],
        }
        for bid, ids in sorted(usage.items())
    ]

    return {
        "feasible": True,
        "selection": selected_ids,
        "selection_order": [id_order[sid] for sid in selected_ids],
        "total_cost": round(best_cost, 10),
        "sentinel_count": best_count,
        "evidence": evidence,
        "bus_usage": bus_usage_out,
        "combinations_evaluated": evaluated,
        "total_combinations": total_combinations,
    }
