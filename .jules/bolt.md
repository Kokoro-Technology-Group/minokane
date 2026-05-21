## 2024-05-21 - Pydantic JSON Serialization Overhead
**Learning:** Using `json.loads(model.model_dump_json())` creates an unnecessary string serialization and deserialization step, causing performance overhead when converting Pydantic models to JSON-compatible dictionaries for storage or responses.
**Action:** Always use `model.model_dump(mode='json')` to directly obtain a JSON-compatible dictionary without the intermediate string step.
