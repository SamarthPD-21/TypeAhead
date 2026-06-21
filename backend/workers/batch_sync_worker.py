import math
import time
from backend.storage.sql_repository import SQLiteDatabaseStorage
from backend.services.search_buffer import InMemorySearchBuffer
from backend.services.decay_ranker import DecayScoringRanker
from backend.services.stale_prefix_tracker import StalePrefixTracker
from backend.services.telemetry_collector import TelemetryCollector

def execute_buffer_flush(
    repo: SQLiteDatabaseStorage,
    buffer: InMemorySearchBuffer,
    ranker: DecayScoringRanker,
    stale_tracker: StalePrefixTracker,
    telemetry: TelemetryCollector = None,
    disable_stale_tracking: bool = False
) -> None:
    """Drains the in-memory query buffer and flushes the aggregated counts to the SQLite repository in a single transaction."""
    snapshot = buffer.drain_buffer()
    if not snapshot:
        return

    current_timestamp = int(time.time())
    query_phrases = list(snapshot.keys())

    # Bulk fetch existing metrics from database to avoid N+1 queries
    existing_records = repo.fetch_scores_for_batch(query_phrases)

    upsert_rows = []
    for phrase, current_count in snapshot.items():
        if phrase in existing_records:
            old_score, old_timestamp = existing_records[phrase]
            # Calculate elapsed time in hours
            elapsed_hours = (current_timestamp - old_timestamp) / 3600.0
            # Decay the historical score using the ranker's decay rate parameter
            decayed_score = old_score / math.exp(ranker.decay_rate * elapsed_hours)
            new_score = decayed_score + current_count
        else:
            new_score = float(current_count)
            
        upsert_rows.append((phrase, current_count, new_score, current_timestamp))

    # Perform batch upsert in WAL mode
    repo.upsert_records_batch(upsert_rows)

    # Invalidate cached prefixes associated with these queries
    if not disable_stale_tracking:
        stale_tracker.mark_batch_queries_stale(query_phrases)

    # Record telemetry flush operation
    if telemetry:
        telemetry.record_flush_sync()
