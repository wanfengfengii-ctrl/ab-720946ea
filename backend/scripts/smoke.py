"""一次性冒烟脚本：由 Compose 的 verify 服务执行。

覆盖：健康检查、求解 API 正常路径、无方案路径、422 定位错误路径，以及前端页面可达性。
任何断言失败即以非零退出码结束。
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BACKEND = os.environ.get("BACKEND_URL", "http://backend:8000")
WEB = os.environ.get("WEB_URL", "http://web")


def _request(method: str, url: str, payload: dict | None = None) -> tuple[int, dict | str]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            ctype = resp.headers.get("Content-Type", "")
            return resp.status, (json.loads(body) if "application/json" in ctype else body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, body


def main() -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}{(' — ' + detail) if detail and not ok else ''}")
        if not ok:
            failures.append(name)

    # 1. 健康检查
    status, body = _request("GET", f"{BACKEND}/api/health")
    check("backend health 200", status == 200 and isinstance(body, dict) and body.get("status") == "ok")

    # 2. limits
    status, body = _request("GET", f"{BACKEND}/api/limits")
    check("limits endpoint", status == 200 and body.get("min_modes") == 3)

    # 3. 正常求解：3 模式 4 哨点，S1+S2 即可全区分（同费 S3 更贵场景）
    good = {
        "modes": ["M1", "M2", "M3"],
        "buses": [{"id": "B1", "channels": 4}],
        "sentinels": [
            {"id": "S1", "cost": 1, "bus": "B1", "readings": {"M1": 0, "M2": 1, "M3": 0}},
            {"id": "S2", "cost": 1, "bus": "B1", "readings": {"M1": 0, "M2": 0, "M3": 1}},
            {"id": "S3", "cost": 5, "bus": "B1", "readings": {"M1": 0, "M2": 1, "M3": 1}},
            {"id": "S4", "cost": 0, "bus": "B1", "readings": {"M1": 1, "M2": 1, "M3": 1}},
        ],
    }
    status, body = _request("POST", f"{BACKEND}/api/solve", good)
    ok = (
        status == 200
        and isinstance(body, dict)
        and body.get("ok") is True
        and body["result"].get("feasible") is True
        and body["result"].get("selection") == ["S1", "S2"]
        and len(body["result"].get("evidence", [])) == 3
    )
    check("solve feasible case", ok, f"status={status} body={body}")

    # 4. 无方案：M1/M2 读数恒相同
    impossible = {
        "modes": ["M1", "M2", "M3"],
        "buses": [{"id": "B1", "channels": 4}],
        "sentinels": [
            {"id": "S1", "cost": 1, "bus": "B1", "readings": {"M1": 0, "M2": 0, "M3": 1}},
            {"id": "S2", "cost": 1, "bus": "B1", "readings": {"M1": 0, "M2": 0, "M3": 1}},
            {"id": "S3", "cost": 1, "bus": "B1", "readings": {"M1": 1, "M2": 1, "M3": 0}},
            {"id": "S4", "cost": 1, "bus": "B1", "readings": {"M1": 1, "M2": 1, "M3": 0}},
        ],
    }
    status, body = _request("POST", f"{BACKEND}/api/solve", impossible)
    ok = (
        status == 200
        and body["ok"] is True
        and body["result"].get("feasible") is False
        and any(
            p["mode_a"] == "M1" and p["mode_b"] == "M2"
            for p in body["result"].get("indistinguishable_pairs", [])
        )
    )
    check("solve infeasible case", ok, f"status={status} body={body}")

    # 5. 校验错误带定位：缺读数 + 未知总线 + 非法通道
    bad = {
        "modes": ["M1", "M2", "M3"],
        "buses": [{"id": "B1", "channels": -1}],
        "sentinels": [
            {"id": "S1", "cost": 1, "bus": "BX",
             "readings": {"M1": 0, "M2": 1}},  # 缺 M3
            {"id": "S2", "cost": 1, "bus": "B1", "readings": {"M1": 0, "M2": 0, "M3": 1}},
            {"id": "S3", "cost": 1, "bus": "B1", "readings": {"M1": 0, "M2": 1, "M3": 1}},
            {"id": "S4", "cost": 1, "bus": "B1", "readings": {"M1": 1, "M2": 1, "M3": 1}},
        ],
    }
    status, body = _request("POST", f"{BACKEND}/api/solve", bad)
    locs = {e["loc"] for e in body.get("errors", [])} if isinstance(body, dict) else set()
    ok = (
        status == 422
        and {"buses[0].channels", "sentinels[0].bus", "sentinels[0].readings.M3"} <= locs
    )
    check("validation errors located", ok, f"status={status} locs={sorted(locs)}")

    # 6. 前端页面可达
    status, body = _request("GET", f"{WEB}/")
    check("web index served", status == 200 and isinstance(body, str) and 'id="root"' in body)

    print()
    if failures:
        print(f"SMOKE FAILED: {len(failures)} check(s): {failures}")
        return 1
    print("SMOKE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
