import json
import redis
from backend.models.suggestion_data import TypeaheadSuggestion

class RedisCacheClient:
    """Wrapper for Redis operations, supporting consistent hashing caching and cache invalidation."""
    
    def __init__(self, host: str, port: int, db: int):
        self.connection = redis.Redis(host=host, port=port, db=db, decode_responses=True)

    def retrieve_suggestions(self, prefix: str) -> list[TypeaheadSuggestion] | None:
        """Fetches cached suggestions for a prefix, reconstructing TypeaheadSuggestion objects."""
        cached_val = self.connection.get(prefix)
        if cached_val is None:
            return None
        
        try:
            records = json.loads(cached_val)
            return [
                TypeaheadSuggestion(suggestion_text=item["t"], ranking_score=item["s"])
                for item in records
            ]
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def store_suggestions(self, prefix: str, suggestions: list[TypeaheadSuggestion], ttl_seconds: int = 300) -> None:
        """Saves a list of suggestions in Redis, serialized as compact JSON keys."""
        compact_representation = [
            {"t": item.suggestion_text, "s": item.ranking_score}
            for item in suggestions
        ]
        self.connection.set(prefix, json.dumps(compact_representation), ex=ttl_seconds)

    def evict_key(self, prefix: str) -> None:
        """Deletes a key from the Redis cache."""
        self.connection.delete(prefix)

    def check_exists(self, prefix: str) -> bool:
        """Returns True if the cache key exists."""
        return bool(self.connection.exists(prefix))

    def add_to_set(self, set_name: str, value: str) -> None:
        """Adds a value to a Redis set."""
        self.connection.sadd(set_name, value)

    def is_set_member(self, set_name: str, value: str) -> bool:
        """Checks if a value is present in a Redis set."""
        return bool(self.connection.sismember(set_name, value))

    def remove_from_set(self, set_name: str, value: str) -> None:
        """Removes a value from a Redis set."""
        self.connection.srem(set_name, value)

    def obtain_pipeline(self) -> redis.client.Pipeline:
        """Returns a pipeline object to run multiple Redis commands atomically."""
        return self.connection.pipeline()
