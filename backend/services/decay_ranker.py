import math
import time
from backend.models.query_data import SearchQueryRecord
from backend.models.suggestion_data import TypeaheadSuggestion

class DecayScoringRanker:
    """Ranks suggestions by blending historical search popularity with time-decayed recency scores."""
    
    def __init__(self, decay_rate: float = 0.03, weight_popularity: float = 0.4, weight_recency: float = 0.6):
        self.decay_rate = decay_rate
        self.weight_popularity = weight_popularity
        self.weight_recency = weight_recency

    def calculate_decayed_recency(self, initial_recency: float, last_updated_epoch: int) -> float:
        """Applies an exponential time-decay formula to a recency score based on elapsed hours."""
        elapsed_seconds = int(time.time()) - last_updated_epoch
        elapsed_hours = elapsed_seconds / 3600.0
        return initial_recency / math.exp(self.decay_rate * elapsed_hours)

    def calculate_unified_score(self, record: SearchQueryRecord) -> float:
        """Calculates a combined popularity-recency score for a database query record."""
        decayed_recent = self.calculate_decayed_recency(record.activity_score, record.updated_at)
        
        # Logarithmic dampening prevents extremely high frequency terms from dominating completely
        popularity_part = math.log(record.hits_count + 1)
        recency_part = math.log(decayed_recent + 1)
        
        return (self.weight_popularity * popularity_part) + (self.weight_recency * recency_part)

    def evaluate_and_rank(self, candidates: list[SearchQueryRecord], limit: int = 5) -> list[TypeaheadSuggestion]:
        """Calculates unified scores for a list of candidate records, sorts them, and returns top results."""
        scored_candidates = []
        for record in candidates:
            score = self.calculate_unified_score(record)
            scored_candidates.append((score, record))

        # Sort descending by score, ascending by phrase as a secondary alphabetical tie-breaker
        scored_candidates.sort(key=lambda item: (-item[0], item[1].phrase))

        return [
            TypeaheadSuggestion(suggestion_text=record.phrase, ranking_score=score)
            for score, record in scored_candidates[:limit]
        ]
