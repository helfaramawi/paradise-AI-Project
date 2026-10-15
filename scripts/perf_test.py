"""Lightweight performance test: what-if simulation latency and concurrent throughput.

Usage: python scripts/perf_test.py [base_url]   (default http://localhost:8080)
"""
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/") + "/api/v1"


def main() -> None:
    tok = httpx.post(f"{BASE}/auth/login", json={"email": "analyst@futuremirror.demo", "password": "FutureMirror!2026"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}

    def sim(i: int, iterations: int = 1000) -> float:
        t0 = time.perf_counter()
        r = httpx.post(f"{BASE}/simulation/run", headers=h, timeout=60,
                       json={"iterations": iterations, "controls": {"cost_reduction_target_pct": 10 + i % 15}})
        r.raise_for_status()
        return (time.perf_counter() - t0) * 1000

    seq = [sim(i) for i in range(10)]
    print(f"what-if (1000 iter, sensitivity + DES), sequential n=10: p50 {statistics.median(seq):.0f} ms, max {max(seq):.0f} ms")
    big = sim(0, 10000)
    print(f"what-if 10000 iterations: {big:.0f} ms")
    t0 = time.perf_counter()
    with ThreadPoolExecutor(8) as ex:
        lat = list(ex.map(sim, range(24)))
    wall = time.perf_counter() - t0
    print(f"concurrent 8 workers x 24 requests: wall {wall:.1f}s, throughput {24 / wall:.1f} req/s, p95 {sorted(lat)[int(0.95 * len(lat)) - 1]:.0f} ms")
    d = httpx.post(f"{BASE}/decisions", headers=h, json={"title": "perf", "question": "Reduce costs by 10% in 6 months"}).json()
    t0 = time.perf_counter()
    run = httpx.post(f"{BASE}/decisions/{d['id']}/runs", headers=h, json={"pacing_ms": 0}).json()
    while True:
        r = httpx.get(f"{BASE}/runs/{run['run_id']}", headers=h).json()
        if r["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.2)
    print(f"full multi-agent pipeline (no pacing): status {r['status']}, compute {r['compute_ms']:.0f} ms, wall {(time.perf_counter() - t0):.1f}s, events {len(r['events'])}")


if __name__ == "__main__":
    main()
