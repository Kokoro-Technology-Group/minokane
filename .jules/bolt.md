## 2025-02-28 - [Pydantic Serialization Optimization]
**Learning:** Found unnecessary string serialization and immediate deserialization pattern using `json.loads(session.model_dump_json())` in `json_store.py`. This introduces significant overhead, especially since Pydantic provides a native mechanism to accomplish exactly this.
**Action:** Replaced with `session.model_dump(mode="json")` to directly obtain a dictionary with JSON-compatible types, saving memory and CPU cycles while preserving the identical dictionary structure.
