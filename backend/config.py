from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("TYPEAHEAD_DB_PATH", BASE_DIR / "typeahead.db"))
FLUSH_INTERVAL_SECONDS = float(os.environ.get("TYPEAHEAD_FLUSH_INTERVAL_SECONDS", "10"))
SUGGESTION_LIMIT = int(os.environ.get("TYPEAHEAD_SUGGESTION_LIMIT", "5"))
