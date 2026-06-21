from backend.models.suggestion_data import TypeaheadSuggestion
from backend.services.decay_ranker import DecayScoringRanker
from backend.storage.sql_repository import SQLiteDatabaseStorage
from backend.services.consistent_hash_ring import ConsistentHashRing
from backend.storage.redis_client import RedisCacheClient
from backend.services.stale_prefix_tracker import StalePrefixTracker
from backend.services.telemetry_collector import TelemetryCollector

def clean_prefix(prefix: str) -> str:
    """Normalizes prefix string to avoid casing and whitespace differences."""
    prefix = prefix.lower().strip()
    return " ".join(prefix.split())

class TypeaheadEngine:
    """Core suggestion processing engine coordinating cache routing, invalidation checks, and DB fallbacks."""

    def __init__(
        self,
        ranker: DecayScoringRanker,
        repo: SQLiteDatabaseStorage,
        hash_ring: ConsistentHashRing,
        redis_clients: dict[str, RedisCacheClient],
        stale_tracker: StalePrefixTracker,
        telemetry: TelemetryCollector = None
    ):
        self.ranker = ranker
        self.repository = repo
        self.hash_ring = hash_ring
        self.redis_clients = redis_clients
        self.stale_tracker = stale_tracker
        self.telemetry = telemetry

    def get_suggestions(self, prefix: str) -> list[TypeaheadSuggestion]:
        """Retrieves autocomplete suggestions, handling consistent hash routing, cache hits/misses, and stale data re-indexing."""
        normalized_prefix = clean_prefix(prefix)
        if not normalized_prefix:
            return []

        # Consistent hashing routing to Redis shard
        target_node = self.hash_ring.route_key(normalized_prefix)
        cache_client = self.redis_clients[target_node]
        
        # Read from cache
        suggestions = cache_client.retrieve_suggestions(normalized_prefix)

        # Check stale/dirty indicators if cached hit
        is_stale = False
        if suggestions is not None:
            if self.telemetry:
                self.telemetry.record_stale_check()
            is_stale = self.stale_tracker.verify_if_stale(normalized_prefix)
            if is_stale and self.telemetry:
                self.telemetry.record_stale_hit()

        # Cache Miss or Stale Cache Entry triggers DB read and ranking
        if suggestions is None or is_stale:
            if self.telemetry:
                self.telemetry.record_miss()
                self.telemetry.record_database_access()
                
            db_candidates = self.repository.query_by_prefix(normalized_prefix)
            suggestions = self.ranker.evaluate_and_rank(db_candidates)
            
            # Store in cache
            cache_client.store_suggestions(normalized_prefix, suggestions)
            
            # Reset stale indicator
            self.stale_tracker.remove_stale_flag(normalized_prefix)
            if is_stale and self.telemetry:
                self.telemetry.record_stale_clear()
                
            return suggestions
        else:
            if self.telemetry:
                self.telemetry.record_hit()
            return suggestions

    def get_trending(self, limit: int = 5) -> list[TypeaheadSuggestion]:
        """Fetches and ranks the globally trending search items."""
        trending_records = self.repository.fetch_trending_terms()
        return self.ranker.evaluate_and_rank(trending_records, limit=limit)
