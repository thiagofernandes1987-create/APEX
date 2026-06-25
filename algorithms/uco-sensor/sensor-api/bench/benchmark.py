"""
Sprint U — Benchmark harness (v3.5.0)
======================================
Measures req/s + p50/p95/p99 latency against a running uco-sensor.

Two modes
---------
- ``--mode serial`` (default): single connection, sequential.  Good
  for measuring per-request latency baseline.
- ``--mode parallel --workers N``: N concurrent threads, each hitting
  the server.  Approximates real throughput (still limited by GIL on
  the synchronous ``http.server``; ASGI/uvicorn shines here).

Usage
-----
::

    python -m bench.benchmark --url http://localhost:8765/health \\
                              --n 100 --mode parallel --workers 16

The script is intentionally pure-stdlib (``urllib`` only) so it can run
in any sandbox without ``pip install``.
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple


def _one_request(url: str, timeout: float = 10.0) -> Tuple[bool, float, int]:
    t0 = time.perf_counter()
    status = 0
    ok = False
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            status = resp.status
            resp.read()
            ok = 200 <= status < 400
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception:
        status = 0
    return ok, time.perf_counter() - t0, status


def run_serial(url: str, n: int) -> List[Tuple[bool, float, int]]:
    return [_one_request(url) for _ in range(n)]


def run_parallel(url: str, n: int, workers: int) -> List[Tuple[bool, float, int]]:
    out: List[Tuple[bool, float, int]] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_one_request, url) for _ in range(n)]
        for f in as_completed(futures):
            out.append(f.result())
    return out


def _percentile(xs: List[float], p: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    k = int(round((p / 100.0) * (len(xs) - 1)))
    return xs[k]


def summarise(results: List[Tuple[bool, float, int]], wallclock_s: float) -> dict:
    latencies = [t for _, t, _ in results]
    successes = [t for ok, t, _ in results if ok]
    n = len(results)
    ok = len(successes)
    return {
        "n":          n,
        "successes":  ok,
        "errors":     n - ok,
        "wall_s":     round(wallclock_s, 3),
        "throughput": round(n / wallclock_s, 2) if wallclock_s > 0 else 0.0,
        "p50_ms":     round(_percentile(latencies, 50) * 1000, 2),
        "p95_ms":     round(_percentile(latencies, 95) * 1000, 2),
        "p99_ms":     round(_percentile(latencies, 99) * 1000, 2),
        "mean_ms":    round(statistics.fmean(latencies) * 1000, 2) if latencies else 0,
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="uco-sensor benchmark harness")
    parser.add_argument("--url", required=True, help="Full URL to hit")
    parser.add_argument("--n", type=int, default=100, help="Total requests")
    parser.add_argument("--mode", choices=["serial", "parallel"], default="serial")
    parser.add_argument("--workers", type=int, default=4,
                        help="Concurrent threads (parallel mode only)")
    args = parser.parse_args(argv)

    print(f"Benchmark: {args.url}  n={args.n}  mode={args.mode}"
          + (f"  workers={args.workers}" if args.mode == "parallel" else ""))

    t0 = time.perf_counter()
    if args.mode == "serial":
        results = run_serial(args.url, args.n)
    else:
        results = run_parallel(args.url, args.n, args.workers)
    wall = time.perf_counter() - t0

    summary = summarise(results, wall)
    print()
    print(f"  total:      {summary['n']}  ({summary['successes']} ok, {summary['errors']} err)")
    print(f"  wallclock:  {summary['wall_s']}s")
    print(f"  throughput: {summary['throughput']} req/s")
    print(f"  latency:    p50 {summary['p50_ms']}ms  "
          f"p95 {summary['p95_ms']}ms  p99 {summary['p99_ms']}ms  "
          f"mean {summary['mean_ms']}ms")
    return 0 if summary["errors"] == 0 else 1


if __name__ == "__main__":   # pragma: no cover
    sys.exit(main())
