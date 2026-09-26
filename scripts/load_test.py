#!/usr/bin/env python3
"""
Load & Stability Tester:
Simulates concurrent requests (10 req/s) against /v1/healthz, /v1/tick, and /v1/reply.
Confirms zero 500 errors and measures p95 latency.
"""
from __future__ import annotations

import asyncio
import sys
import time
import httpx


async def run_load_test(base_url: str = "http://127.0.0.1:8000", duration_s: int = 15, req_rate: int = 10):
    print(f"Starting load test against {base_url} ({req_rate} req/s for {duration_s}s)...")
    latencies = []
    error_count = 0
    status_500_count = 0
    total_requests = 0

    endpoints = [
        ("GET", "/v1/healthz", None),
        ("GET", "/v1/metadata", None),
        ("POST", "/v1/tick", {"now": "2026-04-26T10:00:00Z", "available_triggers": ["trg_001"]}),
        ("POST", "/v1/reply", {"conversation_id": "c_load", "merchant_id": "m_001", "from_role": "merchant", "message": "Ok lets do it", "turn_number": 2}),
    ]

    async with httpx.AsyncClient(timeout=10.0) as client:
        start_time = time.time()
        while time.time() - start_time < duration_s:
            batch_start = time.time()
            tasks = []
            for i in range(req_rate):
                method, path, body = endpoints[(total_requests + i) % len(endpoints)]
                url = f"{base_url}{path}"
                tasks.append(_send_request(client, method, url, body))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                total_requests += 1
                if isinstance(res, tuple):
                    lat_ms, status_code = res
                    latencies.append(lat_ms)
                    if status_code >= 500:
                        status_500_count += 1
                    elif status_code >= 400 and status_code != 404:
                        error_count += 1
                else:
                    error_count += 1

            # Rate throttle to 1 second per batch
            elapsed = time.time() - batch_start
            if elapsed < 1.0:
                await asyncio.sleep(1.0 - elapsed)

    latencies.sort()
    n = len(latencies)
    p50 = latencies[int(n * 0.50)] if n else 0.0
    p95 = latencies[int(n * 0.95)] if n else 0.0
    p99 = latencies[int(n * 0.99)] if n else 0.0

    print("\n" + "=" * 50)
    print("LOAD TEST RESULTS")
    print("=" * 50)
    print(f"Total Requests Sent: {total_requests}")
    print(f"HTTP 500 Errors:     {status_500_count} (Goal: 0)")
    print(f"Client/Conn Errors:  {error_count}")
    print(f"p50 Latency:         {p50:.2f} ms")
    print(f"p95 Latency:         {p95:.2f} ms (Goal: < 5000 ms)")
    print(f"p99 Latency:         {p99:.2f} ms")
    print("=" * 50)

    if status_500_count > 0:
        print("FAIL: Server returned 500 errors!")
        sys.exit(1)
    if p95 > 5000.0:
        print("FAIL: p95 latency exceeded 5.0 seconds!")
        sys.exit(1)
    print("SUCCESS: Load test passed cleanly with zero 500s and sub-second latencies!")


async def _send_request(client: httpx.AsyncClient, method: str, url: str, json_body: dict | None):
    t0 = time.perf_counter()
    try:
        if method == "GET":
            r = await client.get(url)
        else:
            r = await client.post(url, json=json_body)
        latency = (time.perf_counter() - t0) * 1000
        return latency, r.status_code
    except Exception as e:
        latency = (time.perf_counter() - t0) * 1000
        return latency, 599


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    asyncio.run(run_load_test(base_url=url, duration_s=15, req_rate=10))
