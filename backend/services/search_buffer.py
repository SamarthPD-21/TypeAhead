from threading import Lock

class InMemorySearchBuffer:
    """Thread-safe in-memory buffer to aggregate incoming search query counts before batch flushing."""
    
    def __init__(self):
        self._accumulator: dict[str, int] = {}
        self._mutex = Lock()

    def push_query(self, phrase: str) -> None:
        """Increments the frequency count for a search phrase in the buffer."""
        with self._mutex:
            self._accumulator[phrase] = self._accumulator.get(phrase, 0) + 1

    def drain_buffer(self) -> dict[str, int]:
        """Atomically copies the accumulated buffer contents and clears the active buffer."""
        with self._mutex:
            snapshot = self._accumulator.copy()
            self._accumulator.clear()
            return snapshot

    def clear_all(self) -> None:
        """Discards all accumulated items in the buffer."""
        with self._mutex:
            self._accumulator.clear()

    def get_pending_count(self) -> int:
        """Returns the number of unique queries currently buffered."""
        with self._mutex:
            return len(self._accumulator)
