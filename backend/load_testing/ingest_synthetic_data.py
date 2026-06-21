import sys
import time
import os
import argparse
import csv
from pathlib import Path
import importlib

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import redis

def parse_args():
    p = argparse.ArgumentParser(description="Fast ingest synthetic query data via buffer service.")
    p.add_argument(
        "--rows", type=int, default=0,
        help="Number of rows to ingest (default: 0 = all rows)."
    )
    p.add_argument(
        "--data", type=str, default="search_queries.csv",
        help="Path to synthetic CSV dataset."
    )
    return p.parse_args()


def main():
    args = parse_args()
    data_path = Path(args.data) if Path(args.data).is_absolute() else ROOT / args.data
    db_path = ROOT / "synthetic_test.db"

    if not data_path.exists():
        print(f"[ERROR] Dataset not found at {data_path}")
        return

    # ── Redis health check ────────────────────────────────────────────────────
    os.environ["TYPEAHEAD_DB_PATH"] = str(db_path)

    r = redis.Redis(host="localhost", port=6379, db=0)
    try:
        r.ping()
        print("[INFO] Redis connected. Flushing DB 0...")
        r.flushdb()
        r2 = redis.Redis(host="localhost", port=6380, db=0)
        r2.flushdb()
        r3 = redis.Redis(host="localhost", port=6381, db=0)
        r3.flushdb()
    except Exception as e:
        print(f"[ERROR] Cannot connect to Redis: {e}")
        return

    if db_path.exists():
        os.remove(db_path)

    # ── Import app ────────────────────────────────────────────────────────────
    import backend.app as app_module
    importlib.reload(app_module)

    # ── Load and inject queries ───────────────────────────────────────────────
    max_rows = args.rows if args.rows > 0 else float("inf")
    buffer_service = app_module.app.state.buffer_service

    print(f"[INFO] Fast ingesting dataset directly into buffer...")
    t0 = time.time()
    
    count = 0
    with open(data_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None) # skip header
        for row in reader:
            if count >= max_rows:
                break
            if len(row) == 2:
                query = row[0].strip()
                freq = int(row[1])
                # Direct injection into buffer
                with buffer_service.lock:
                    if query in buffer_service.buffer:
                        buffer_service.buffer[query] += freq
                    else:
                        buffer_service.buffer[query] = freq
                count += 1

    t1 = time.time()
    print(f"[OK] Injected {count:,} unique queries with exact frequencies in {t1 - t0:.2f}s")

    # ── Flush batch to SQLite ─────────────────────────────────────────────
    print("[INFO] Flushing in-memory buffer to SQLite + Redis...")
    t2 = time.time()
    # Force a flush of everything we just buffered without dirtying cache
    app_module.app.state.flush_pending_updates(disable_dirty_tracking=True)
    t3 = time.time()
    print(f"[OK]  Flush done in {t3 - t2:.1f}s")

    # ── Quick sanity check ────────────────────────────────────────────────
    with app_module.app.state.repository._get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) FROM search_terms").fetchone()
    final_rows = row[0] if row else 0
    
    print(f"\n[SUMMARY]")
    print(f"  Rows in SQLite DB : {final_rows:,}")
    print(f"\nRun stress_test.py with --data {data_path.name} to test system performance.")


if __name__ == "__main__":
    main()
