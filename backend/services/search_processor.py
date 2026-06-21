from backend.services.search_buffer import InMemorySearchBuffer

def sanitize_query(phrase: str) -> str:
    """Converts a search query to lowercase, strips trailing spaces, and squashes multiple internal spaces."""
    phrase = phrase.lower().strip()
    return " ".join(phrase.split())

class SearchIngestionProcessor:
    """Ingests incoming search queries, normalizes their format, and queues them into the write buffer."""
    
    def __init__(self, buffer_service: InMemorySearchBuffer):
        self.buffer_service = buffer_service

    def process_and_record_search(self, raw_phrase: str) -> None:
        """Sanitizes the incoming query and pushes it to the buffered write queue."""
        clean_phrase = sanitize_query(raw_phrase)
        if clean_phrase:
            self.buffer_service.push_query(clean_phrase)
