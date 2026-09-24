"""API 集成测试（FastAPI TestClient）。"""

import copy

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def valid_payload():
    return {
        "fault_modes": ["F1", "F2", "F3"],
        "buses": [
            {"id": "B1", "channels": 1},
            {"id": "B2", "channels": 2},
        ],
        "sentinels": [
            {"id": "S1", "bus": "B1", "cost": 5, "readings": {"F1": 0, "F2": 0, "F3": 1}},
            {"id": "S2", "bus": "B2", "cost": 5, "readings": {"F1": 0, "F2": 1, "F3": 0}},
            {"id": "S3", "bus": "B2", "cost": 9, "readings": {"F1": 0, "F2": 1, "F3": 1}},
            {"id": "S4", "bus": "B2", "cost": 1, "readings": {"F1": 0, "F2": 0, "F3": 0}},
        ],
    }


def err_locs(resp):
    return [tuple(e["loc"]) for e in resp.json()["detail"]]


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_solve_ok():
    resp = client.post("/api/solve", json=valid_payload())
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert [s["id"] for s in data["selected"]] == ["S1", "S2"]
    assert data["total_cost"] == 10
    assert data["sentinel_count"] == 2
    assert data["stats"]["combinations_examined"] == 2 ** 4 - 1
    assert data["stats"]["feasible_combinations"] >= 1
    # 逐对证据：3 对故障模式，每对至少一个见证哨点
    assert len(data["evidence"]) == 3
    for item in data["evidence"]:
        assert len(item["pair"]) == 2
        assert item["witnesses"]
    usage = {u["bus"]: u for u in data["bus_usage"]}
    assert usage["B1"]["used"] == 1
    assert usage["B2"]["used"] == 1


def test_duplicate_fault_mode_rejected():
    payload = valid_payload()
    payload["fault_modes"][2] = "F1"
    resp = client.post("/api/solve", json=payload)
    assert resp.status_code == 422
    assert ("body", "fault_modes", 2) in err_locs(resp)


def test_duplicate_sentinel_id_rejected():
    payload = valid_payload()
    payload["sentinels"][3]["id"] = "S1"
    resp = client.post("/api/solve", json=payload)
    assert resp.status_code == 422
    assert ("body", "sentinels", 3, "id") in err_locs(resp)


def test_duplicate_bus_id_rejected():
    payload = valid_payload()
    payload["buses"].append({"id": "B1", "channels": 3})
    resp = client.post("/api/solve", json=payload)
    assert resp.status_code == 422
    assert ("body", "buses", 2, "id") in err_locs(resp)


def test_unknown_bus_rejected():
    payload = valid_payload()
    payload["sentinels"][1]["bus"] = "B9"
    resp = client.post("/api/solve", json=payload)
    assert resp.status_code == 422
    assert ("body", "sentinels", 1, "bus") in err_locs(resp)


def test_missing_reading_rejected():
    payload = valid_payload()
    del payload["sentinels"][0]["readings"]["F3"]
    resp = client.post("/api/solve", json=payload)
    assert resp.status_code == 422
    assert ("body", "sentinels", 0, "readings") in err_locs(resp)


def test_extra_reading_rejected():
    payload = valid_payload()
    payload["sentinels"][0]["readings"]["F9"] = 1
    resp = client.post("/api/solve", json=payload)
    assert resp.status_code == 422
    assert ("body", "sentinels", 0, "readings") in err_locs(resp)


def test_invalid_channels_rejected():
    for bad in (0, -1, 2.5, "x"):
        payload = valid_payload()
        payload["buses"][0]["channels"] = bad
        resp = client.post("/api/solve", json=payload)
        assert resp.status_code == 422, bad


def test_invalid_reading_value_rejected():
    payload = valid_payload()
    payload["sentinels"][0]["readings"]["F1"] = 2
    resp = client.post("/api/solve", json=payload)
    assert resp.status_code == 422


def test_negative_cost_rejected():
    payload = valid_payload()
    payload["sentinels"][0]["cost"] = -1
    resp = client.post("/api/solve", json=payload)
    assert resp.status_code == 422


def test_mode_and_sentinel_count_bounds():
    payload = valid_payload()
    payload["fault_modes"] = ["F1", "F2"]
    resp = client.post("/api/solve", json=payload)
    assert resp.status_code == 422

    payload = valid_payload()
    payload["fault_modes"] = [f"F{i}" for i in range(13)]
    resp = client.post("/api/solve", json=payload)
    assert resp.status_code == 422

    payload = valid_payload()
    payload["sentinels"] = payload["sentinels"][:3]
    resp = client.post("/api/solve", json=payload)
    assert resp.status_code == 422

    payload = valid_payload()
    extra = copy.deepcopy(payload["sentinels"][3])
    for i in range(5, 20):
        item = copy.deepcopy(extra)
        item["id"] = f"SX{i}"
        payload["sentinels"].append(item)
    assert len(payload["sentinels"]) == 19
    resp = client.post("/api/solve", json=payload)
    assert resp.status_code == 422


def test_infeasible_returns_no_solution():
    payload = valid_payload()
    # 让所有哨点下 F1 与 F2 读数一致 → 无法区分
    for s in payload["sentinels"]:
        s["readings"]["F2"] = s["readings"]["F1"]
    resp = client.post("/api/solve", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "infeasible"
    assert ["F1", "F2"] in data["blocking_pairs"]
    assert data["selected"] == []
