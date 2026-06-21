import hashlib

class ConsistentHashRing:
    """Consistently maps keys to a cluster of nodes using virtual nodes and binary search routing."""
    
    def __init__(self, physical_nodes: list[str], virtual_nodes_count: int = 100):
        self.virtual_nodes_count = virtual_nodes_count
        self.ring: list[tuple[int, str]] = []
        for node in physical_nodes:
            self.add_node_to_ring(node)

    def _hash(self, val_str: str) -> int:
        """Computes a 256-bit hash integer using SHA-256 for balanced distribution."""
        hashed = hashlib.sha256(val_str.encode("utf-8")).hexdigest()
        return int(hashed, 16)

    def add_node_to_ring(self, node_id: str) -> None:
        """Populates virtual nodes for the given physical node on the ring."""
        for index in range(self.virtual_nodes_count):
            virtual_key = f"vnode:{node_id}:{index}"
            position = self._hash(virtual_key)
            self.ring.append((position, node_id))
        self.ring.sort()

    def remove_node_from_ring(self, node_id: str) -> None:
        """Removes all virtual nodes associated with a physical node from the ring."""
        self.ring = [item for item in self.ring if item[1] != node_id]

    def route_key(self, target_key: str) -> str:
        """Finds the appropriate physical node for a given prefix/key."""
        if not self.ring:
            raise ValueError("Consistent Hash Ring contains no nodes.")

        key_pos = self._hash(target_key)
        
        # Binary search lookup
        low, high = 0, len(self.ring) - 1
        while low <= high:
            mid = (low + high) // 2
            if self.ring[mid][0] < key_pos:
                low = mid + 1
            else:
                high = mid - 1
                
        if low == len(self.ring):
            return self.ring[0][1]
            
        return self.ring[low][1]

    def get_ring_topology(self) -> list[tuple[int, str]]:
        """Returns the current state of the consistent hash ring."""
        return self.ring
