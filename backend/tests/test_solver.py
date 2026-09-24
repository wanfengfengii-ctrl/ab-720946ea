"""求解器单元测试。"""

from app.solver import BusSpec, SentinelSpec, solve

MODES = ["F1", "F2", "F3"]


def sent(id, bus, cost, bits, modes=None):
    """bits: 按 modes（默认 F1,F2,F3）顺序的 0/1 读数。"""
    return SentinelSpec(id=id, bus=bus, cost=cost, readings=dict(zip(modes or MODES, bits)))


def test_lowest_cost_then_lexicographic():
    buses = [BusSpec("BX", 1), BusSpec("BY", 2)]
    sentinels = [
        sent("A", "BX", 5, [0, 0, 1]),  # 区分 (F1,F3) (F2,F3)
        sent("B", "BY", 5, [0, 1, 0]),  # 区分 (F1,F2) (F2,F3)
        sent("C", "BY", 5, [0, 1, 1]),  # 区分 (F1,F2) (F1,F3)
        sent("D", "BY", 0, [0, 0, 0]),  # 无区分能力
    ]
    out = solve(MODES, buses, sentinels)
    assert out.status == "ok"
    # {A,B} {A,C} {B,C} 费用与数量均相同，取编号序列字典序最小者
    assert [s["id"] for s in out.selected] == ["A", "B"]
    assert out.total_cost == 10
    assert out.sentinel_count == 2
    # 证据覆盖全部 3 对，且每对都有读数不同的见证哨点
    assert len(out.evidence) == 3
    for item in out.evidence:
        assert item["witnesses"], item["pair"]
        for w in item["witnesses"]:
            assert w["readings"][0] != w["readings"][1]


def test_lowest_cost_beats_fewer_sentinels():
    """费用优先于哨点数量：贵的 2 哨点组合不敌便宜的 3 哨点组合。"""
    buses = [BusSpec("BX", 4)]
    sentinels = [
        sent("S1", "BX", 1, [0, 0, 1]),  # p13 p23
        sent("S2", "BX", 1, [0, 1, 0]),  # p12 p23
        sent("S3", "BX", 1, [0, 1, 1]),  # p12 p13
        sent("S4", "BX", 2, [1, 0, 0]),  # p12 p13
    ]
    # {S1,S2}=2 即可全覆盖，费用最低
    out = solve(MODES, buses, sentinels)
    assert out.status == "ok"
    assert [s["id"] for s in out.selected] == ["S1", "S2"]
    assert out.total_cost == 2


def test_fewer_sentinels_preferred_when_cost_ties():
    buses = [BusSpec("BX", 4)]
    sentinels = [
        sent("S1", "BX", 0, [0, 0, 1]),  # p13 p23
        sent("S2", "BX", 8, [0, 1, 0]),  # p12 p23
        sent("S3", "BX", 0, [1, 1, 0]),  # p13 p23
        sent("S4", "BX", 8, [0, 1, 1]),  # p12 p13
    ]
    # 费用 8 的可行方案既有 2 哨点组合（如 {S1,S2}），也有 3 哨点组合
    # （如 {S1,S2,S3}）；数量最少者优先，同数量再按编号字典序。
    out = solve(MODES, buses, sentinels)
    assert out.status == "ok"
    assert out.total_cost == 8
    assert out.sentinel_count == 2
    assert [s["id"] for s in out.selected] == ["S1", "S2"]


def test_lexicographic_tie_break_on_ids():
    buses = [BusSpec("BX", 2), BusSpec("BY", 2)]
    sentinels = [
        sent("S2", "BX", 5, [0, 0, 1]),  # p13 p23
        sent("S1", "BY", 5, [0, 0, 1]),  # p13 p23（与 S2 等效）
        sent("S3", "BX", 5, [0, 1, 0]),  # p12 p23
        sent("S4", "BY", 9, [1, 1, 1]),
    ]
    # {S1,S3} 与 {S2,S3} 费用、数量相同，[S1,S3] 字典序更小
    out = solve(MODES, buses, sentinels)
    assert out.status == "ok"
    assert [s["id"] for s in out.selected] == ["S1", "S3"]


def test_channel_capacity_forces_alternative():
    modes = ["F1", "F2", "F3", "F4"]
    buses = [BusSpec("BX", 1), BusSpec("BY", 2)]
    sentinels = [
        sent("S1", "BX", 1, [0, 0, 1, 1], modes),  # 掩码 e={13,14,23,24}
        sent("S2", "BY", 5, [0, 1, 1, 1], modes),  # 掩码 a={12,13,14}
        sent("S3", "BY", 5, [1, 1, 1, 0], modes),  # 掩码 d={14,24,34}
        sent("S4", "BX", 1, [0, 1, 0, 1], modes),  # 掩码 f={12,14,23,34}
    ]
    # e∪f 即可全覆盖且费用仅 2，但 S1、S4 同在 BX（1 通道）→ 不可行；
    # 最优可行为 {S1,S2,S3}（与 {S2,S3,S4} 同费用同数量，字典序更小）。
    out = solve(modes, buses, sentinels)
    assert out.status == "ok"
    assert [s["id"] for s in out.selected] == ["S1", "S2", "S3"]
    assert out.total_cost == 11
    usage = {u["bus"]: u for u in out.bus_usage}
    assert usage["BX"]["used"] == 1 and usage["BX"]["capacity"] == 1
    assert usage["BY"]["used"] == 2 and usage["BY"]["capacity"] == 2


def test_infeasible_indistinguishable_pair():
    buses = [BusSpec("BX", 4)]
    sentinels = [
        sent("S1", "BX", 1, [0, 0, 1]),
        sent("S2", "BX", 1, [1, 1, 0]),
        sent("S3", "BX", 1, [0, 0, 0]),
        sent("S4", "BX", 1, [1, 1, 1]),
    ]
    # F1 与 F2 在所有哨点下读数相同 → 永远不可区分
    out = solve(MODES, buses, sentinels)
    assert out.status == "infeasible"
    assert ["F1", "F2"] in out.blocking_pairs
    assert out.feasible_combinations == 0


def test_infeasible_due_to_channels_only():
    buses = [BusSpec("BX", 1), BusSpec("BY", 2)]
    sentinels = [
        sent("S1", "BX", 1, [0, 1, 1]),  # p12 p13
        sent("S2", "BX", 1, [1, 1, 0]),  # p13 p23（必须搭配 S1 才能全覆盖）
        sent("S3", "BY", 1, [0, 0, 0]),
        sent("S4", "BY", 1, [1, 1, 1]),
    ]
    # 全集可覆盖所有故障对，但唯一全覆盖组合 {S1,S2} 超出 BX 通道数
    out = solve(MODES, buses, sentinels)
    assert out.status == "infeasible"
    assert out.blocking_pairs == []
    assert "通道" in out.message


def test_exhaustive_combination_count():
    buses = [BusSpec("BX", 4)]
    sentinels = [
        sent("S1", "BX", 1, [0, 0, 1]),
        sent("S2", "BX", 1, [0, 1, 0]),
        sent("S3", "BX", 1, [0, 1, 1]),
        sent("S4", "BX", 1, [1, 0, 0]),
    ]
    out = solve(MODES, buses, sentinels)
    assert out.combinations_examined == 2 ** 4 - 1
    assert out.feasible_combinations >= 1


def test_decimal_costs_compared_exactly():
    """0.1+0.2 之类的费用不得因浮点误差影响比较与展示。"""
    modes = ["F1", "F2", "F3", "F4"]
    buses = [BusSpec("BX", 4)]
    sentinels = [
        sent("S1", "BX", 0.1, [0, 0, 1, 1], modes),   # 划分 {F1,F2}|{F3,F4}
        sent("S2", "BX", 0.2, [0, 1, 0, 1], modes),   # 划分 {F1,F3}|{F2,F4}
        sent("S3", "BX", 0.4, [0, 1, 1, 0], modes),   # 划分 {F1,F4}|{F2,F3}
        sent("S4", "BX", 0.01, [0, 1, 1, 1], modes),  # 仅 3 对，无法单独补全
    ]
    # 三种 2|2 划分两两组合均可全覆盖；{S1,S2} 真实费用 0.3 最低。
    out = solve(modes, buses, sentinels)
    assert out.status == "ok"
    assert [s["id"] for s in out.selected] == ["S1", "S2"]
    assert out.total_cost == 0.3  # 精确等于 0.3，而非 0.30000000000000004
