from backend.services.consistent_hash_ring import ConsistentHashRing
from backend.storage.redis_client import RedisCacheClient

class StalePrefixTracker:
    """Manages cache invalidation using a set of stale prefixes mapped across Redis cache nodes."""
    
    SET_NAME = "stale_prefixes:set"

    def __init__(self, hash_ring: ConsistentHashRing, redis_clients: dict[str, RedisCacheClient]):
        self.hash_ring = hash_ring
        self.redis_clients = redis_clients

    def _resolve_client(self, prefix: str) -> RedisCacheClient:
        """Determines which Redis client is responsible for a prefix."""
        node = self.hash_ring.route_key(prefix)
        return self.redis_clients[node]

    def mark_prefix_stale(self, prefix: str) -> None:
        """Adds a prefix to the stale tracking set on its mapped Redis node."""
        client = self._resolve_client(prefix)
        client.add_to_set(self.SET_NAME, prefix)

    def verify_if_stale(self, prefix: str) -> bool:
        """Returns True if the prefix is marked stale and needs database re-scoring."""
        client = self._resolve_client(prefix)
        return client.is_set_member(self.SET_NAME, prefix)

    def remove_stale_flag(self, prefix: str) -> None:
        """Clears the stale flag for a prefix after a cache re-fetch."""
        client = self._resolve_client(prefix)
        client.remove_from_set(self.SET_NAME, prefix)

    def mark_all_subprefixes_stale(self, query_phrase: str) -> None:
        """Marks all sequential subprefixes of a query as stale (e.g., 'i', 'ip', 'iph' for 'iphone')."""
        for char_len in range(1, len(query_phrase) + 1):
            self.mark_prefix_stale(query_phrase[:char_len])

    def mark_batch_queries_stale(self, query_phrases: list[str]) -> None:
        """Pipelined batch operation to flag all subprefixes of a list of search queries as stale."""
        # Initialize pipelines for each active cache node
        pipelines = {
            node_id: client.obtain_pipeline()
            for node_id, client in self.redis_clients.items()
        }

        for phrase in query_phrases:
            for char_len in range(1, len(phrase) + 1):
                sub_prefix = phrase[:char_len]
                target_node = self.hash_ring.route_key(sub_prefix)
                # Queue the sadd command in the appropriate node's pipeline
                pipelines[target_node].sadd(self.SET_NAME, sub_prefix)

        # Execute all pipelines in batch
        for pipe in pipelines.values():
            pipe.execute()
