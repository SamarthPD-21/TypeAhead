from fastapi import APIRouter, Request
from backend.models.api_schemas import SearchQueryPayload

router = APIRouter()

@router.post("/search")
def receive_search_phrase(payload: SearchQueryPayload, request: Request) -> dict[str, str]:
    """Ingests a search term into the buffering pipeline, returning an immediate queued status."""
    request.app.state.search_processor.process_and_record_search(payload.query)
    return {"status": "queued"}
