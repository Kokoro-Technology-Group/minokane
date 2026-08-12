import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from app.models.schemas import ForecastSession

_lock = asyncio.Lock()

# Name of the pointer file (written next to the sessions data file) that records
# the single most-recently-saved session. Lets the frontend resume the last
# session token-first without scanning the whole store.
POINTER_FILENAME = "last_session.json"


class JSONStore:
    def __init__(self, file_path: str) -> None:
        self.path = Path(file_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}")
        # Most-recent-session pointer, e.g. backend/data/last_session.json.
        self.pointer_path = self.path.parent / POINTER_FILENAME

    async def save_session(self, session: ForecastSession) -> None:
        async with _lock:
            data = json.loads(self.path.read_text())
            data[session.id] = json.loads(session.model_dump_json())
            self.path.write_text(json.dumps(data, indent=2))
            # Record this as the most recent session (token + timestamp).
            self.pointer_path.write_text(
                json.dumps(
                    {
                        "latest_session_id": session.id,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                    indent=2,
                )
            )

    async def get_session(self, session_id: str) -> ForecastSession | None:
        async with _lock:
            data = json.loads(self.path.read_text())
        raw = data.get(session_id)
        if raw is None:
            return None
        return ForecastSession.model_validate(raw)

    async def get_latest_session(self) -> ForecastSession | None:
        """Return the most recently saved session, or None if the store is empty.

        Reads the pointer file first; if it is missing or stale (points at a
        session no longer present), falls back to the newest by `created_at` so
        stores written before pointers existed still resolve.
        """
        async with _lock:
            data = json.loads(self.path.read_text())
            latest_id: str | None = None
            if self.pointer_path.exists():
                try:
                    latest_id = json.loads(self.pointer_path.read_text()).get("latest_session_id")
                except (json.JSONDecodeError, OSError):
                    latest_id = None

        raw = data.get(latest_id) if latest_id else None
        if raw is None and data:
            # Fallback: newest by created_at (ISO-8601 strings sort chronologically).
            _, raw = max(data.items(), key=lambda kv: kv[1].get("created_at", ""))
        if raw is None:
            return None
        return ForecastSession.model_validate(raw)
