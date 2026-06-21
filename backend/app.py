from contextlib import asynccontextmanager
from pathlib import Path
from threading import Event, Thread

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.api.search import router as search_router
from backend.api.suggest import router as suggest_router
from backend.config import BASE_DIR, DB_PATH, FLUSH_INTERVAL_SECONDS
from backend.services.search_buffer import InMemorySearchBuffer
from backend.services.decay_ranker import DecayScoringRanker
from backend.services.search_processor import SearchIngestionProcessor
from backend.services.typeahead_engine import TypeaheadEngine
from backend.storage.sql_repository import SQLiteDatabaseStorage
from backend.storage.redis_client import RedisCacheClient
from backend.services.stale_prefix_tracker import StalePrefixTracker
from backend.services.telemetry_collector import TelemetryCollector
from backend.workers.batch_sync_worker import execute_buffer_flush
from backend.services.consistent_hash_ring import ConsistentHashRing

def create_application() -> FastAPI:
    """Builds and configures the FastAPI application, initializing storage and background workers."""
    # Storage layers
    database = SQLiteDatabaseStorage(str(DB_PATH))
    database.initialize_tables()

    # Shared services
    search_buffer = InMemorySearchBuffer()
    ranker = DecayScoringRanker()
    search_processor = SearchIngestionProcessor(search_buffer)
    
    # Cache layer
    hash_ring = ConsistentHashRing(["redis1", "redis2", "redis3"])
    redis_clients = {
        "redis1": RedisCacheClient(host='localhost', port=6379, db=0),
        "redis2": RedisCacheClient(host='localhost', port=6380, db=0),
        "redis3": RedisCacheClient(host='localhost', port=6381, db=0)
    }
    
    stale_tracker = StalePrefixTracker(hash_ring, redis_clients)
    telemetry = TelemetryCollector()
    
    typeahead_engine = TypeaheadEngine(
        ranker=ranker,
        repo=database,
        hash_ring=hash_ring,
        redis_clients=redis_clients,
        stale_tracker=stale_tracker,
        telemetry=telemetry
    )
    
    stop_signal = Event()

    def run_flush_sync(disable_stale_tracking: bool = False) -> None:
        """Triggers a manual flush of the write buffer into SQLite."""
        execute_buffer_flush(
            repo=database,
            buffer=search_buffer,
            ranker=ranker,
            stale_tracker=stale_tracker,
            telemetry=telemetry,
            disable_stale_tracking=disable_stale_tracking
        )

    def background_flush_loop() -> None:
        """Worker thread loop executing periodic buffer flushing."""
        while not stop_signal.wait(FLUSH_INTERVAL_SECONDS):
            run_flush_sync()

    @asynccontextmanager
    async def app_lifespan(application: FastAPI):
        # Startup: Launch background daemon thread
        worker_thread = Thread(target=background_flush_loop, daemon=True)
        worker_thread.start()
        application.state.flush_worker = worker_thread
        try:
            yield
        finally:
            # Shutdown: Stop worker thread and wait for completion
            stop_signal.set()
            worker_thread.join(timeout=2.0)

    # Instantiate app
    app = FastAPI(
        title="Premium Typeahead API Engine",
        description="Low-latency consistent hash ring autocomplete system.",
        lifespan=app_lifespan
    )
    
    # Enable CORS for file:/// protocol access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Store state attributes for routers and testing
    app.state.database = database
    app.state.search_buffer = search_buffer
    app.state.ranker = ranker
    app.state.search_processor = search_processor
    app.state.typeahead_engine = typeahead_engine
    app.state.telemetry = telemetry
    app.state.trigger_sync = run_flush_sync
    
    # Include routers
    app.include_router(search_router)
    app.include_router(suggest_router)

    # Serve static frontend assets
    frontend_dir = BASE_DIR.parent / "frontend"
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    @app.get("/")
    async def root_endpoint():
        """Serves the index landing page of the search frontend client."""
        return FileResponse(str(frontend_dir / "index.html"))

    @app.get("/styles.css")
    async def serve_stylesheet():
        """Serves the stylesheet relatively."""
        return FileResponse(str(frontend_dir / "styles.css"))

    @app.get("/app.js")
    async def serve_javascript():
        """Serves the script relatively."""
        return FileResponse(str(frontend_dir / "app.js"))

    return app

app = create_application()
