from pydantic import BaseModel

class SearchQueryPayload(BaseModel):
    """Payload for submitting a new search term."""
    query: str

class SuggestionItemDTO(BaseModel):
    """Data transfer object for a single typeahead suggestion."""
    text: str
    score: float

class SuggestionResponseEnvelope(BaseModel):
    """Response wrapper containing the list of suggestions."""
    suggestions: list[SuggestionItemDTO]
