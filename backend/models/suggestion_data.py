from dataclasses import dataclass

@dataclass
class TypeaheadSuggestion:
    """Represents a ranked autocomplete suggestion candidate."""
    suggestion_text: str
    ranking_score: float
