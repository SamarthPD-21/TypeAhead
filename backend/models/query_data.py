from dataclasses import dataclass

@dataclass
class SearchQueryRecord:
    """Represents a persisted search term record in the database."""
    phrase: str
    hits_count: int
    activity_score: float
    updated_at: int
