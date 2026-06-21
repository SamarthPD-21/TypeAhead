"""
End-to-End Typeahead System Test
=================================
Validates the complete system against 3 core behavioural paths:

  Path 1 — Cache Miss then Hit
  Path 2 — Stale-Prefix Invalidation after a batch write
  Path 3 — Trending ranking order

Usage:
    python backend/load_testing/e2e_comprehensive_test.py
"""
import sys
import time
import os
import tempfile
import redis
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient


# ─── Display helpers ────────────────────────────────────────────────────────
def divider(char="─", width=70):
    print(char * width)

def status(label: str, passed: bool):
    icon = "✅" if passed else "❌"
    print(f"    {icon}  {label}")

def section(title: str):
    print()
    divider("─")
    print(f"  {title}")
    divider("─")


# ─── Individual paths ────────────────────────────────────────────────────────
def path_cache_miss_then_hit(client, metrics, r) -> dict:
    """Populate DB, flush cache, then verify miss → hit flow."""
    section("PATH 1 — Cache Miss then Hit")

    client.post("/search", json={"query": "iphone"})
    client.app.state.trigger_sync()
    r.flushdb()
    metrics.wipe_statistics()

    t0 = time.perf_counter()
    res1 = client.get("/suggest", params={"q": "iphone"})
    miss_lat = (time.perf_counter() - t0) * 1000
    m = metrics.generate_report()

    hit1_ok    = res1.status_code == 200
    miss_ok    = m["cache_misses"] == 1
    db_ok      = m["db_queries"]   == 1
    no_hit_ok  = m["cache_hits"]   == 0

    t0 = time.perf_counter()
    res2 = client.get("/suggest", params={"q": "iphone"})
    hit_lat = (time.perf_counter() - t0) * 1000
    m = metrics.generate_report()

    hit2_ok   = res2.status_code == 200
    hit_ok    = m["cache_hits"]   == 1

    status("First request  → cache miss  → DB lookup",   miss_ok and no_hit_ok and db_ok)
    status("Second request → cache hit   (no DB query)", hit_ok)
    print(f"\n    Miss latency : {miss_lat:.1f}ms")
    print(f"    Hit latency  : {hit_lat:.1f}ms")
    print(f"    Speedup      : {miss_lat/max(hit_lat,0.01):.1f}×")

    passed = all([hit1_ok, miss_ok, db_ok, no_hit_ok, hit2_ok, hit_ok])
    return {"path": "Cache Miss → Hit", "passed": passed, "miss_ms": miss_lat, "hit_ms": hit_lat}


def path_stale_invalidation(client, metrics, r) -> dict:
    """After a new query is flushed, stale cache entries must be invalidated."""
    section("PATH 2 — Stale-Prefix Invalidation")

    client.post("/search", json={"query": "iphone charger"})
    client.app.state.trigger_sync()

    stale_tracker = client.app.state.typeahead_engine.stale_tracker
    prefix_stale  = stale_tracker.verify_if_stale("iphone")
    status("Prefix 'iphone' marked stale after batch flush", prefix_stale)

    metrics.wipe_statistics()
    res = client.get("/suggest", params={"q": "iphone"})
    cleared = not stale_tracker.verify_if_stale("iphone")
    m       = metrics.generate_report()

    recomputed_ok = m["cache_misses"] == 1 and m["db_queries"] == 1
    status("Stale read triggers DB recompute",          recomputed_ok)
    status("Stale flag cleared after recompute",         cleared)

    res2 = client.get("/suggest", params={"q": "iphone"})
    m2   = metrics.generate_report()
    hit_after_ok = m2["cache_hits"] == 1
    status("Subsequent read served from fresh cache",   hit_after_ok)

    # Verify 'iphone charger' appears in refreshed suggestions
    texts   = [s["text"] for s in res.json()["suggestions"]]
    charger_ok = any("iphone charger" in t for t in texts)
    status("'iphone charger' visible in updated results", charger_ok)

    passed = all([prefix_stale, recomputed_ok, cleared, hit_after_ok, charger_ok])
    return {"path": "Stale-Prefix Invalidation", "passed": passed}


def path_trending(client, metrics) -> dict:
    """Insert queries at different frequencies; verify trending order."""
    section("PATH 3 — Trending Ranking")

    for _ in range(100): client.post("/search", json={"query": "iphone"})
    for _ in range(50):  client.post("/search", json={"query": "youtube"})
    for _ in range(20):  client.post("/search", json={"query": "chatgpt"})
    client.app.state.trigger_sync()

    res   = client.get("/trending", params={"limit": 5})
    suggs = res.json()["suggestions"]
    texts = [s["text"] for s in suggs]

    print(f"\n    Trending order returned: {texts[:5]}")

    p1 = texts[0] == "iphone"
    p2 = texts[1] == "youtube" if len(texts) > 1 else False
    p3 = texts[2] == "chatgpt" if len(texts) > 2 else False

    status("Rank 1 → 'iphone'  (100 searches)", p1)
    status("Rank 2 → 'youtube' (50 searches)",  p2)
    status("Rank 3 → 'chatgpt' (20 searches)",  p3)

    passed = all([p1, p2, p3])
    return {"path": "Trending Ranking", "passed": passed}


# ─── Summary table ────────────────────────────────────────────────────────
def print_summary(results: list[dict]):
    print()
    divider("═")
    print("  📋  E2E TEST SUMMARY")
    divider("═")
    all_passed = True
    for r in results:
        icon = "✅ PASS" if r["passed"] else "❌ FAIL"
        print(f"  {icon}  {r['path']}")
        if not r["passed"]:
            all_passed = False
    divider()
    if all_passed:
        print("  🎉  All paths passed — system is behaving correctly!")
    else:
        print("  ⚠️   Some paths failed — review output above.")
    divider("═")
    print()


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    print()
    divider("═")
    print("  🧪  END-TO-END TYPEAHEAD SYSTEM TEST (REFACTORED)")
    divider("═")

    with tempfile.TemporaryDirectory() as tmp_dir:
        os.environ["TYPEAHEAD_DB_PATH"] = str(Path(tmp_dir) / "test_e2e.db")

        r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
        try:
            r.ping()
        except Exception:
            print("\n  [ERROR] Cannot reach Redis on localhost:6379.")
            print("          Run: docker compose up -d\n")
            return
        r.flushdb()

        import backend.app as app_module
        importlib.reload(app_module)

        with TestClient(app_module.app) as client:
            metrics = app_module.app.state.telemetry

            results = [
                path_cache_miss_then_hit(client, metrics, r),
                path_stale_invalidation(client, metrics, r),
                path_trending(client, metrics),
            ]

        print_summary(results)


if __name__ == "__main__":
    main()
