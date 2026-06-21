"""
AOL Typeahead Load Test
=======================
Simulates concurrent users making typeahead suggestions and searches
using a subset of the AOL query dataset, ramping up load progressively.

Usage:
    python backend/load_testing/stress_test.py
    python backend/load_testing/stress_test.py --rows 2000 --users 2000
"""
import sys
import time
import random
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import importlib

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient


# ─── Defaults ──────────────────────────────────────────────────────────────
DEFAULT_ROWS  = 1_000
DEFAULT_USERS = 1_000


def parse_args():
    p = argparse.ArgumentParser(description="Stress test the Typeahead API.")
    p.add_argument(
        "--rows", type=int, default=50_000,
        help="Number of dataset rows to process (default: 50,000). Use 0 for all."
    )
    p.add_argument(
        "--users", type=int, default=500,
        help="Max concurrent users to simulate (default: 500)."
    )
    p.add_argument(
        "--data", type=str, default="search_queries.csv",
        help="Path to synthetic CSV dataset file."
    )
    return p.parse_args()


# ─── Dataset ────────────────────────────────────────────────────────────────
def load_subset(max_rows: int, data_path_str: str) -> list[str]:
    data_path = Path(data_path_str) if Path(data_path_str).is_absolute() else ROOT / data_path_str
    if not data_path.exists():
        print(f"[ERROR] Dataset not found at {data_path}")
        return []

    queries = []
    import csv
    with open(data_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for row in reader:
            if len(queries) >= max_rows:
                break
            if len(row) > 0 and row[0].strip():
                queries.append(row[0].strip())

    return list(queries)  # deduplicate


# ─── Helpers ────────────────────────────────────────────────────────────────
def percentile(sorted_data: list[float], pct: float) -> float:
    if not sorted_data:
        return 0.0
    idx = int(len(sorted_data) * pct / 100)
    return sorted_data[min(idx, len(sorted_data) - 1)]


# ─── Simulation ─────────────────────────────────────────────────────────────
def run_wave(num_users: int, queries: list[str], client: TestClient) -> dict:
    """
    Simulates `num_users` concurrent users each doing 10 operations
    (30% POST /search, 70% GET /suggest with random prefix length).
    Returns a dict of metrics collected for this wave, including p50/p95.
    """
    suggest_latencies: list[float] = []
    lock = Lock()

    def user_session():
        local = []
        for _ in range(10):
            q = random.choice(queries)
            if random.random() < 0.3:
                client.post("/search", json={"query": q})
            else:
                prefix = q[:random.randint(1, len(q))]
                t0 = time.perf_counter()
                client.get("/suggest", params={"q": prefix})
                local.append((time.perf_counter() - t0) * 1000)
        with lock:
            suggest_latencies.extend(local)

    client.app.state.telemetry.wipe_statistics()
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=min(num_users, 200)) as ex:
        futures = [ex.submit(user_session) for _ in range(num_users)]
        for f in futures:
            f.result()

    elapsed = time.time() - t0
    m = client.get("/metrics").json()
    total_ops = num_users * 10

    # Compute ALL latency stats from the same client-side samples so
    # avg / p50 / p95 are directly comparable (same distribution).
    sorted_lats = sorted(suggest_latencies)
    avg = sum(sorted_lats) / len(sorted_lats) if sorted_lats else 0.0
    p50 = percentile(sorted_lats, 50)
    p95 = percentile(sorted_lats, 95)

    return {
        "users":     num_users,
        "ops":       total_ops,
        "elapsed":   elapsed,
        "hits":      m.get("cache_hits", 0),
        "misses":    m.get("cache_misses", 0),
        "hit_rate":  m.get("cache_hit_rate_pct", 0.0),
        "db":        m.get("db_queries", 0),
        "latency":   avg,   # client-side avg — same population as p50/p95
        "p50":       p50,
        "p95":       p95,
        "throughput": round(total_ops / elapsed, 1),
        "stale_checks": m.get("stale_checks", 0),
        "stale_hits":   m.get("stale_hits", 0),
        "stale_clears": m.get("stale_clears", 0),
        "flushes":      m.get("buffer_flushes", 0),
    }


# ─── Display ────────────────────────────────────────────────────────────────
def divider(char="─", width=96):
    print(char * width)


def print_results(all_results: list[dict]):
    print()
    divider("═")
    print("  📊  LOAD TEST RESULTS")
    divider("═")

    header = (
        f"{'Users':>7}  {'Ops':>6}  {'Time':>6}  {'Hit%':>6}  "
        f"{'Hits':>6}  {'Misses':>7}  {'DB Reads':>9}  "
        f"{'Avg Lat':>9}  {'p50':>8}  {'p95':>8}  {'Ops/s':>8}"
    )
    print(f"\n  {header}")
    divider()

    for r in all_results:
        elapsed_str = f"{r['elapsed']:.2f}s"
        lat_str     = f"{r['latency']:.1f}ms"
        p50_str     = f"{r['p50']:.1f}ms"
        p95_str     = f"{r['p95']:.1f}ms"
        hit_pct_str = f"{r['hit_rate']:.1f}%"
        row = (
            f"{r['users']:>7}  "
            f"{r['ops']:>6}  "
            f"{elapsed_str:>6}  "
            f"{hit_pct_str:>6}  "
            f"{r['hits']:>6}  "
            f"{r['misses']:>7}  "
            f"{r['db']:>9}  "
            f"{lat_str:>9}  "
            f"{p50_str:>8}  "
            f"{p95_str:>8}  "
            f"{r['throughput']:>8}"
        )
        print(f"  {row}")

    divider()

    # summary section
    final = all_results[-1]
    best_avg = min(all_results, key=lambda x: x["latency"])
    worst_avg = max(all_results, key=lambda x: x["latency"])

    print()
    print("  SUMMARY")
    divider()
    print(f"  {'Peak Users':<30}  {final['users']:,}")
    print(f"  {'Total Ops (peak wave)':<30}  {final['ops']:,}")
    print(f"  {'Final Cache Hit Rate':<30}  {final['hit_rate']:.1f}%")
    print(f"  {'Best Avg Latency':<30}  {best_avg['latency']:.1f}ms  (@ {best_avg['users']:,} users)")
    print(f"  {'Worst Avg Latency':<30}  {worst_avg['latency']:.1f}ms  (@ {worst_avg['users']:,} users)")
    print(f"  {'p50 @ Peak Load':<30}  {final['p50']:.1f}ms")
    print(f"  {'p95 @ Peak Load':<30}  {final['p95']:.1f}ms")
    print(f"  {'Peak Throughput':<30}  {max(r['throughput'] for r in all_results):,.0f} ops/s")
    divider()

    # Stale-prefix & batch-write stats (cumulative across all waves)
    total_stale_checks = sum(r["stale_checks"] for r in all_results)
    total_stale_hits   = sum(r["stale_hits"]   for r in all_results)
    total_stale_clears = sum(r["stale_clears"] for r in all_results)
    total_flushes      = sum(r["flushes"]      for r in all_results)

    print()
    print("  STALE-PREFIX & BATCH-WRITE STATS (cumulative)")
    divider()
    print(f"  {'Stale Checks':<30}  {total_stale_checks:,}")
    print(f"  {'Stale Hits':<30}  {total_stale_hits:,}")
    print(f"  {'Stale Clears':<30}  {total_stale_clears:,}")
    print(f"  {'Buffer Flushes':<30}  {total_flushes:,}")
    divider("═")
    print()


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    args = parse_args()

    print()
    divider("═")
    print("  🚀  TYPEAHEAD LOAD TEST (REFACTORED)")
    divider("═")
    print(f"  Dataset rows   : {args.rows:,}")
    print(f"  Max users      : {args.users:,}")
    print(f"  Ramp schedule  : 10 → 50 → 100 → 500 → {args.users}")
    divider()

    print(f"\n[1/3] Loading dataset (up to {args.rows:,} rows)...")
    queries = load_subset(args.rows, args.data)
    if not queries:
        return
    print(f"      Loaded {len(queries):,} unique queries.")

    print("[2/3] Starting FastAPI app...")
    import backend.app as app_module
    importlib.reload(app_module)

    with TestClient(app_module.app) as client:
        print("[3/3] Pre-warming backend with dataset queries...")
        for q in queries:
            client.post("/search", json={"query": q})
        app_module.app.state.trigger_sync()
        print("      Pre-warm complete.\n")

        # Build ramp schedule, de-dup and sort
        milestones = sorted(set([10, 50, 100, 500, args.users]))

        all_results = []
        for milestone in milestones:
            print(f"  ▶  Simulating {milestone:,} users...", end="", flush=True)
            result = run_wave(milestone, queries, client)
            all_results.append(result)
            print(f"  done  ({result['elapsed']:.2f}s)")

        print_results(all_results)


if __name__ == "__main__":
    main()
