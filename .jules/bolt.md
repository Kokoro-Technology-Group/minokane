## 2024-06-25 - Pydantic Serialization Overhead
**Learning:** Pydantic v2 `model_dump_json()` immediately passed into `json.loads()` is an anti-pattern that creates an unnecessary string serialization and deserialization cycle.
**Action:** Always use `model.model_dump(mode='json')` to directly extract a dictionary with JSON-compatible types (e.g., converting datetimes to strings) instead of roundtripping through a string format.
