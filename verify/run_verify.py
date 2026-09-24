"""verify 一次性服务入口：代码测试 → 构建检查 → API 冒烟。

全部步骤通过后以退出码 0 退出，任一步骤失败以退出码 1 退出。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

API_BASE = os.environ.get("API_BASE", "http://backend:8000").rstrip("/")
WEB_BASE = os.environ.get("WEB_BASE", "http://frontend:80").rstrip("/")
APP_DIR = os.environ.get("APP_DIR", "/app")
WEB_DIST = os.environ.get("WEB_DIST", "/web/dist")
WAIT_SECONDS = int(os.environ.get("VERIFY_WAIT_SECONDS", "90"))

FAILURES: list[str] = []


def step(title: str) -> None:
    print(f"\n{'=' * 64}\n[verify] {title}\n{'=' * 64}", flush=True)


def check(name: str, cond: bool, detail: str = "") -> bool:
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {name}" + (f" —— {detail}" if detail and not cond else ""), flush=True)
    if not cond:
        FAILURES.append(name)
    return cond


def run_backend_tests() -> None:
    step("第 1 步：后端代码测试（pytest）")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=APP_DIR,
        capture_output=True,
        text=True,
    )
    print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    check("后端单元/接口测试全部通过", proc.returncode == 0, f"pytest 退出码 {proc.returncode}")


def run_build_checks() -> None:
    step("第 2 步：构建检查")
    dist = Path(WEB_DIST)
    index = dist / "index.html"
    assets = list((dist / "assets").glob("*")) if (dist / "assets").is_dir() else []
    check("前端构建产物 index.html 存在", index.is_file())
    check("前端构建产物 assets 非空", len(assets) > 0)
    if index.is_file():
        html = index.read_text(encoding="utf-8")
        check("index.html 挂载点完整", 'id="root"' in html)
        check("index.html 引用了构建产物", "assets/" in html)
    # 后端应用可正常导入（依赖完整性检查）
    proc = subprocess.run(
        [sys.executable, "-c", "import app.main; print('import ok')"],
        cwd=APP_DIR,
        capture_output=True,
        text=True,
    )
    check("后端应用可正常导入", proc.returncode == 0, proc.stderr.strip())


def wait_for_services() -> bool:
    step("第 3 步：API 冒烟（等待服务就绪）")
    deadline = time.time() + WAIT_SECONDS
    while time.time() < deadline:
        try:
            r = httpx.get(f"{API_BASE}/api/health", timeout=3)
            if r.status_code == 200:
                print(f"  后端就绪：{API_BASE}/api/health -> 200", flush=True)
                return True
        except httpx.HTTPError:
            pass
        time.sleep(2)
    check("等待后端服务就绪", False, f"{WAIT_SECONDS}s 内未就绪")
    return False


def smoke_fixture() -> dict:
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


def run_api_smoke() -> None:
    if not wait_for_services():
        return
    try:
        # 1) 健康检查
        r = httpx.get(f"{API_BASE}/api/health", timeout=5)
        check("GET /api/health 返回 200", r.status_code == 200)

        # 2) 正常求解：期望最优组合 {S1, S2}，总费用 10
        r = httpx.post(f"{API_BASE}/api/solve", json=smoke_fixture(), timeout=30)
        ok = r.status_code == 200
        check("POST /api/solve 合法请求返回 200", ok, f"实际 {r.status_code}: {r.text[:200]}")
        if ok:
            data = r.json()
            check("求解状态为 ok", data.get("status") == "ok")
            check(
                "推荐组合为 [S1, S2]",
                [s["id"] for s in data.get("selected", [])] == ["S1", "S2"],
                f"实际 {data.get('selected')}",
            )
            check("总费用为 10", data.get("total_cost") == 10)
            evidence = data.get("evidence", [])
            check(
                "逐对证据覆盖全部 3 对且均有见证哨点",
                len(evidence) == 3 and all(e["witnesses"] for e in evidence),
            )
            check(
                "枚举组合数正确（2^4-1=15）",
                data.get("stats", {}).get("combinations_examined") == 15,
            )

        # 3) 非法输入：重复哨点编号 → 422 且带定位信息
        bad = smoke_fixture()
        bad["sentinels"][3]["id"] = "S1"
        r = httpx.post(f"{API_BASE}/api/solve", json=bad, timeout=10)
        locs = []
        if r.status_code == 422:
            locs = [e.get("loc", []) for e in r.json().get("detail", [])]
        check("重复编号返回 422", r.status_code == 422, f"实际 {r.status_code}")
        check(
            "422 响应带字段定位",
            ["body", "sentinels", 3, "id"] in locs,
            f"实际 locs={locs}",
        )

        # 4) 非法输入：未知总线 → 422
        bad = smoke_fixture()
        bad["sentinels"][0]["bus"] = "B9"
        r = httpx.post(f"{API_BASE}/api/solve", json=bad, timeout=10)
        check("未知总线返回 422", r.status_code == 422, f"实际 {r.status_code}")

        # 5) 非法输入：读数缺失 → 422
        bad = smoke_fixture()
        del bad["sentinels"][0]["readings"]["F3"]
        r = httpx.post(f"{API_BASE}/api/solve", json=bad, timeout=10)
        check("读数缺失返回 422", r.status_code == 422, f"实际 {r.status_code}")

        # 6) 非法输入：通道数为 0 → 422
        bad = smoke_fixture()
        bad["buses"][0]["channels"] = 0
        r = httpx.post(f"{API_BASE}/api/solve", json=bad, timeout=10)
        check("通道数不合法返回 422", r.status_code == 422, f"实际 {r.status_code}")

        # 7) 无法区分 → 明确返回无方案
        bad = smoke_fixture()
        for s in bad["sentinels"]:
            s["readings"]["F2"] = s["readings"]["F1"]
        r = httpx.post(f"{API_BASE}/api/solve", json=bad, timeout=10)
        infeasible = r.status_code == 200 and r.json().get("status") == "infeasible"
        check("无法区分时明确返回无方案", infeasible, f"实际 {r.status_code}: {r.text[:200]}")
        if infeasible:
            check(
                "无方案响应指出不可区分的故障对",
                ["F1", "F2"] in r.json().get("blocking_pairs", []),
            )

        # 8) 前端页面可访问
        try:
            r = httpx.get(f"{WEB_BASE}/", timeout=5, follow_redirects=True)
            check(
                "前端页面可访问",
                r.status_code == 200 and 'id="root"' in r.text,
                f"实际 {r.status_code}",
            )
        except httpx.HTTPError as exc:
            check("前端页面可访问", False, str(exc))
    except httpx.HTTPError as exc:
        check("API 冒烟过程中无网络异常", False, str(exc))


def main() -> int:
    print("[verify] 开始执行：代码测试 + 构建检查 + API 冒烟", flush=True)
    run_backend_tests()
    run_build_checks()
    run_api_smoke()

    step("汇总")
    if FAILURES:
        print(f"[verify] 失败 {len(FAILURES)} 项：", flush=True)
        for name in FAILURES:
            print(f"  - {name}", flush=True)
        print("[verify] 结果：FAIL（退出码 1）", flush=True)
        return 1
    print("[verify] 全部检查通过。结果：PASS（退出码 0）", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
