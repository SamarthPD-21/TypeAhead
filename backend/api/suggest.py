from fastapi import APIRouter, Query, Request
import time

from backend.models.api_schemas import SuggestionResponseEnvelope, SuggestionItemDTO

router = APIRouter()

@router.get("/suggest", response_model=SuggestionResponseEnvelope)
def fetch_typeahead_suggestions(request: Request, q: str = Query(..., min_length=1)) -> SuggestionResponseEnvelope:
    """Retrieves autocomplete suggestions, measuring query latency and reporting via telemetry."""
    start_time = time.perf_counter()
    suggestions = request.app.state.typeahead_engine.get_suggestions(q)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    
    if hasattr(request.app.state, 'telemetry') and request.app.state.telemetry:
        request.app.state.telemetry.record_duration(elapsed_ms)
        
    return SuggestionResponseEnvelope(
        suggestions=[
            SuggestionItemDTO(text=item.suggestion_text, score=item.ranking_score)
            for item in suggestions
        ]
    )

@router.get("/trending", response_model=SuggestionResponseEnvelope)
def fetch_trending_searches(request: Request, limit: int = Query(5, ge=1)) -> SuggestionResponseEnvelope:
    """Retrieves the globally trending search items ranked by the engine."""
    suggestions = request.app.state.typeahead_engine.get_trending(limit=limit)
    return SuggestionResponseEnvelope(
        suggestions=[
            SuggestionItemDTO(text=item.suggestion_text, score=item.ranking_score)
            for item in suggestions
        ]
    )

@router.get("/metrics")
def retrieve_system_metrics(request: Request) -> dict:
    """Aggregates telemetry counters and Redis database sizes for the dashboard metrics interface."""
    report = {}
    if hasattr(request.app.state, 'telemetry') and request.app.state.telemetry:
        report = request.app.state.telemetry.generate_report()
        
    redis_metrics = {}
    if hasattr(request.app.state, 'typeahead_engine') and request.app.state.typeahead_engine:
        clients = request.app.state.typeahead_engine.redis_clients
        for node_id, client in clients.items():
            try:
                redis_metrics[node_id] = client.connection.dbsize()
            except Exception:
                redis_metrics[node_id] = "error"
                
    report["redis_nodes"] = redis_metrics
    return report

@router.get("/cache/debug")
def inspect_cache_routing(request: Request, prefix: str) -> dict:
    """Debug route returning consistent hashing routing results and node occupancy status."""
    engine = request.app.state.typeahead_engine
    target_node = engine.hash_ring.route_key(prefix)
    client = engine.redis_clients[target_node]
    exists = client.check_exists(prefix)
    return {
        "prefix": prefix,
        "node": target_node,
        "cache_hit": exists
    }
