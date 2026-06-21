import threading

class TelemetryCollector:
    """Thread-safe collector for system telemetry metrics, query performance, and cache hit rates."""
    
    def __init__(self):
        self._mutex = threading.Lock()
        self.hits_count = 0
        self.misses_count = 0
        self.sql_queries_count = 0
        self.accumulated_latency_ms = 0.0
        self.total_requests = 0
        self.stale_verifications = 0
        self.stale_detections = 0
        self.stale_resolutions = 0
        self.flush_runs = 0

    def record_hit(self) -> None:
        """Increments the cache hit counter."""
        with self._mutex:
            self.hits_count += 1

    def record_miss(self) -> None:
        """Increments the cache miss counter."""
        with self._mutex:
            self.misses_count += 1

    def record_database_access(self) -> None:
        """Increments the database query counter."""
        with self._mutex:
            self.sql_queries_count += 1

    def record_duration(self, latency_ms: float) -> None:
        """Aggregates processing duration and total request count."""
        with self._mutex:
            self.accumulated_latency_ms += latency_ms
            self.total_requests += 1

    def record_stale_check(self) -> None:
        """Tracks how many times a stale cache prefix check was performed."""
        with self._mutex:
            self.stale_verifications += 1

    def record_stale_hit(self) -> None:
        """Tracks how many times a stale cache prefix was detected on read."""
        with self._mutex:
            self.stale_detections += 1

    def record_stale_clear(self) -> None:
        """Tracks how many times a stale flag was cleared after re-calculating suggestions."""
        with self._mutex:
            self.stale_resolutions += 1

    def record_flush_sync(self) -> None:
        """Tracks the execution of a background buffer flushing operation."""
        with self._mutex:
            self.flush_runs += 1

    def generate_report(self) -> dict:
        """Calculates hit rates and latency metrics, returning a dashboard-friendly summary."""
        with self._mutex:
            total_cache_access = self.hits_count + self.misses_count
            hit_ratio = (self.hits_count / total_cache_access * 100) if total_cache_access > 0 else 0.0
            average_ms = (self.accumulated_latency_ms / self.total_requests) if self.total_requests > 0 else 0.0

            return {
                "cache_hits": self.hits_count,
                "cache_misses": self.misses_count,
                "cache_hit_rate_pct": hit_ratio,
                "db_queries": self.sql_queries_count,
                "average_latency_ms": average_ms,
                "request_count": self.total_requests,
                "stale_checks": self.stale_verifications,
                "stale_hits": self.stale_detections,
                "stale_clears": self.stale_resolutions,
                "buffer_flushes": self.flush_runs
            }

    def wipe_statistics(self) -> None:
        """Resets all metrics counters back to zero."""
        with self._mutex:
            self.hits_count = 0
            self.misses_count = 0
            self.sql_queries_count = 0
            self.accumulated_latency_ms = 0.0
            self.total_requests = 0
            self.stale_verifications = 0
            self.stale_detections = 0
            self.stale_resolutions = 0
            self.flush_runs = 0
