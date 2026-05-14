## 2024-05-14 - Pydantic model serialization overhead
**Learning:** `json.loads(model.model_dump_json())` is a common anti-pattern that creates an unnecessary serialization string just to parse it back into a dict.
**Action:** Use `model.model_dump(mode="json")` to directly generate a dictionary containing JSON-compatible native types (handling dates, datetimes, UUIDs, etc) without string serialization. It is roughly 2x faster.
