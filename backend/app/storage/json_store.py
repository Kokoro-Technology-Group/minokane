import asyncio
import json
from pathlib import Path

from app.models.schemas import ForecastSession

_lock = asyncio.Lock()


class JSONStore:
    def __init__(self, file_path: str) -> None:
        self.path = Path(file_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}")

    async def save_session(self, session: ForecastSession) -> None:
        async with _lock:
            data = json.loads(self.path.read_text())
            # Use model_dump(mode="json") instead of json.loads(session.model_dump_json())
            # to avoid an unnecessary serialization/deserialization cycle and improve perf by ~2x
            data[session.id] = session.model_dump(mode="json")
            self.path.write_text(json.dumps(data, indent=2))

    async def get_session(self, session_id: str) -> ForecastSession | None:
        async with _lock:
            data = json.loads(self.path.read_text())
        raw = data.get(session_id)
        if raw is None:
            return None
        return ForecastSession.model_validate(raw)
