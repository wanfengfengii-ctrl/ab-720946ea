"""求解器与校验的单元测试 + API 冒烟。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.solver import solve
from app.validation import ValidationError, validate_payload

client = TestClient(app)


# --------------------------------------------------------------------------- #
# 辅助构造
# --------------------------------------------------------------------------- #
def make_payload(modes, rows, buses=None):
    """rows: list of (sid, cost, bus, {mode: bit})"""
    if buses is None:
        bus_names = sorted({r[2] for r in rows})
        buses = [{"id": b, "channels": len(rows)} for b in bus_names]
    return {
        "modes": list(modes),
        "buses": buses,
        "sentinels": [
            {"id": sid, "cost": cost, "bus": bus, "readings": dict(reads)}
            for sid, cost, bus, reads in rows
        ],
    }


# --------------------------------------------------------------------------- #
# 求解规则
# --------------------------------------------------------------------------- #
def test_cheapest_total_cost_wins():
    # M1,M2,M3；S1 区分 (M1,M2)，S2 区分 (M2,M3)，S3 区分 (M1,M3)
    payload = make_payload(
        ["M1", "M2", "M3"],
        [
            ("S1", 1, "B1", {"M1": 0, "M2": 1, "M3": 0}),
            ("S2", 1, "B1", {"M1": 0, "M2": 0, "M3": 1}),
            ("S3", 10, "B1", {"M1": 0, "M2": 1, "M3": 1}),
        ],
    )
    # 数量要求 4-18，补一个不提供区分能力的廉价哨点
    payload["sentinels"].append(
        {"id": "S4", "cost": 0.1, "bus": "B1",
         "readings": {"M1": 0, "M2": 0, "M3": 0}}
    )
    res = solve(validate_payload(payload))
    assert res["feasible"] is True
    assert res["selection"] == ["S1", "S2"]
    assert res["total_cost"] == 2.0
    assert len(res["evidence"]) == 3


def test_fewer_sentinels_breaks_cost_tie():
    # 4 个模式：S1+S2（费用 2+3=5，2 个哨点）给出 00/01/10/11 全区分；
    # S3+S4+S5 为“点隔离”列，费用 1+1+3=5（3 个哨点，任意两个都留下一对碰撞），
    # 同费但哨点更多
    payload = make_payload(
        ["M1", "M2", "M3", "M4"],
        [
            ("S1", 2, "B1", {"M1": 0, "M2": 0, "M3": 1, "M4": 1}),
            ("S2", 3, "B1", {"M1": 0, "M2": 1, "M3": 0, "M4": 1}),
            ("S3", 1, "B1", {"M1": 1, "M2": 0, "M3": 0, "M4": 0}),
            ("S4", 1, "B1", {"M1": 0, "M2": 1, "M3": 0, "M4": 0}),
            ("S5", 3, "B1", {"M1": 0, "M2": 0, "M3": 1, "M4": 0}),
        ],
        buses=[{"id": "B1", "channels": 5}],
    )
    res = solve(validate_payload(payload))
    assert res["selection"] == ["S1", "S2"]
    assert res["sentinel_count"] == 2
    assert res["total_cost"] == 5.0


def test_lexicographic_id_sequence_breaks_tie():
    # 两个等费用等数量方案：{S1,S3} 与 {S2,S4}，取字典序小者
    payload = make_payload(
        ["M1", "M2", "M3"],
        [
            ("S1", 1, "B1", {"M1": 0, "M2": 1, "M3": 0}),
            ("S2", 1, "B1", {"M1": 0, "M2": 1, "M3": 0}),
            ("S3", 1, "B1", {"M1": 0, "M2": 0, "M3": 1}),
            ("S4", 1, "B1", {"M1": 0, "M2": 0, "M3": 1}),
        ],
    )
    res = solve(validate_payload(payload))
    assert res["selection"] == ["S1", "S3"]


def test_bus_channel_capacity_enforced():
    # 两个必需哨点都在 B1，但 B1 只有 1 个通道 → 无方案
    payload = make_payload(
        ["M1", "M2", "M3"],
        [
            ("S1", 1, "B1", {"M1": 0, "M2": 1, "M3": 0}),
            ("S2", 1, "B1", {"M1": 0, "M2": 0, "M3": 1}),
            ("S3", 1, "B2", {"M1": 0, "M2": 0, "M3": 0}),
            ("S4", 1, "B2", {"M1": 0, "M2": 0, "M3": 0}),
        ],
        buses=[{"id": "B1", "channels": 1}, {"id": "B2", "channels": 2}],
    )
    res = solve(validate_payload(payload))
    assert res["feasible"] is False
    assert "通道" in res["reason"]
    assert res["indistinguishable_pairs"] == []


def test_structurally_indistinguishable_pair_reported():
    payload = make_payload(
        ["M1", "M2", "M3"],
        [
            ("S1", 1, "B1", {"M1": 0, "M2": 0, "M3": 1}),
            ("S2", 1, "B1", {"M1": 0, "M2": 0, "M3": 1}),
            ("S3", 1, "B1", {"M1": 1, "M2": 1, "M3": 0}),
            ("S4", 1, "B1", {"M1": 1, "M2": 1, "M3": 0}),
        ],
    )
    res = solve(validate_payload(payload))
    assert res["feasible"] is False
    pairs = {(p["mode_a"], p["mode_b"]) for p in res["indistinguishable_pairs"]}
    assert pairs == {("M1", "M2")}


def test_capacity_zero_bus_means_no_selection_from_it():
    payload = make_payload(
        ["M1", "M2", "M3"],
        [
            ("S1", 1, "B1", {"M1": 0, "M2": 1, "M3": 0}),
            ("S2", 1, "B2", {"M1": 0, "M2": 0, "M3": 1}),
            ("S3", 1, "B1", {"M1": 0, "M2": 0, "M3": 0}),
            ("S4", 1, "B1", {"M1": 0, "M2": 0, "M3": 0}),
        ],
        buses=[{"id": "B1", "channels": 1}, {"id": "B2", "channels": 1}],
    )
    res = solve(validate_payload(payload))
    assert res["feasible"] is True
    assert set(res["selection"]) == {"S1", "S2"}
    usage = {u["bus"]: u for u in res["bus_usage"]}
    assert usage["B1"]["used"] <= usage["B1"]["capacity"]
    assert usage["B2"]["used"] <= usage["B2"]["capacity"]


def test_all_combinations_compared_when_unconstrained():
    payload = make_payload(
        ["M1", "M2", "M3"],
        [
            ("S1", 1, "B1", {"M1": 0, "M2": 1, "M3": 0}),
            ("S2", 1, "B1", {"M1": 0, "M2": 0, "M3": 1}),
            ("S3", 1, "B1", {"M1": 0, "M2": 1, "M3": 1}),
            ("S4", 1, "B1", {"M1": 0, "M2": 0, "M3": 0}),
        ],
        buses=[{"id": "B1", "channels": 4}],
    )
    res = solve(validate_payload(payload))
    assert res["total_combinations"] == 16
    assert res["combinations_evaluated"] == 16


def test_max_size_problem_completes():
    modes = [f"M{i:02d}" for i in range(12)]
    rows = []
    # 用模式序号的二进制位作为读数，保证模式列两两不同
    for k in range(18):
        reads = {m: (i >> k) & 1 for i, m in enumerate(modes)}
        rows.append((f"S{k+1:02d}", 1.0, "B1", reads))
    payload = make_payload(
        modes, rows, buses=[{"id": "B1", "channels": 18}]
    )
    res = solve(validate_payload(payload))
    assert res["total_combinations"] == 2**18
    assert res["feasible"] is True
    assert len(res["evidence"]) == 66  # C(12,2)


# --------------------------------------------------------------------------- #
# 校验与定位
# --------------------------------------------------------------------------- #
def _valid_payload():
    return make_payload(
        ["M1", "M2", "M3"],
        [
            ("S1", 1, "B1", {"M1": 0, "M2": 1, "M3": 0}),
            ("S2", 1, "B1", {"M1": 0, "M2": 0, "M3": 1}),
            ("S3", 1, "B1", {"M1": 0, "M2": 1, "M3": 1}),
            ("S4", 1, "B1", {"M1": 1, "M2": 0, "M3": 1}),
        ],
        buses=[{"id": "B1", "channels": 4}],
    )


def _locs(errors):
    return {e["loc"] for e in errors}


def test_duplicate_ids_located():
    p = _valid_payload()
    p["sentinels"][2]["id"] = "S1"
    p["modes"].append("M3")
    with pytest.raises(ValidationError) as exc:
        validate_payload(p)
    locs = _locs(exc.value.errors)
    assert "sentinels[2].id" in locs
    assert "modes[3]" in locs


def test_unknown_bus_located():
    p = _valid_payload()
    p["sentinels"][0]["bus"] = "BX"
    with pytest.raises(ValidationError) as exc:
        validate_payload(p)
    assert "sentinels[0].bus" in _locs(exc.value.errors)


def test_missing_reading_located():
    p = _valid_payload()
    del p["sentinels"][1]["readings"]["M2"]
    with pytest.raises(ValidationError) as exc:
        validate_payload(p)
    assert "sentinels[1].readings.M2" in _locs(exc.value.errors)


def test_invalid_reading_value_located():
    p = _valid_payload()
    p["sentinels"][0]["readings"]["M1"] = 2
    with pytest.raises(ValidationError) as exc:
        validate_payload(p)
    assert "sentinels[0].readings.M1" in _locs(exc.value.errors)


def test_invalid_channel_located():
    p = _valid_payload()
    p["buses"][0]["channels"] = -1
    with pytest.raises(ValidationError) as exc:
        validate_payload(p)
    assert "buses[0].channels" in _locs(exc.value.errors)


def test_bad_count_ranges():
    p = _valid_payload()
    p["modes"] = ["M1", "M2"]
    with pytest.raises(ValidationError) as exc:
        validate_payload(p)
    assert "modes" in _locs(exc.value.errors)

    p = _valid_payload()
    p["sentinels"] = p["sentinels"][:3]
    with pytest.raises(ValidationError) as exc:
        validate_payload(p)
    assert "sentinels" in _locs(exc.value.errors)


def test_negative_cost_located():
    p = _valid_payload()
    p["sentinels"][0]["cost"] = -0.5
    with pytest.raises(ValidationError) as exc:
        validate_payload(p)
    assert "sentinels[0].cost" in _locs(exc.value.errors)


# --------------------------------------------------------------------------- #
# API 冒烟
# --------------------------------------------------------------------------- #
def test_health_endpoint():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_solve_api_success():
    r = client.post("/api/solve", json=_valid_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["result"]["feasible"] is True
    assert body["result"]["selection"]


def test_solve_api_validation_error_shape():
    r = client.post("/api/solve", json={"modes": [], "sentinels": [], "buses": []})
    assert r.status_code == 422
    body = r.json()
    assert body["ok"] is False
    assert all("loc" in e and "msg" in e for e in body["errors"])


def test_solve_api_no_solution():
    p = make_payload(
        ["M1", "M2", "M3"],
        [
            ("S1", 1, "B1", {"M1": 0, "M2": 0, "M3": 1}),
            ("S2", 1, "B1", {"M1": 0, "M2": 0, "M3": 1}),
            ("S3", 1, "B1", {"M1": 1, "M2": 1, "M3": 0}),
            ("S4", 1, "B1", {"M1": 1, "M2": 1, "M3": 0}),
        ],
        buses=[{"id": "B1", "channels": 4}],
    )
    r = client.post("/api/solve", json=p)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["result"]["feasible"] is False
    assert body["result"]["indistinguishable_pairs"]
