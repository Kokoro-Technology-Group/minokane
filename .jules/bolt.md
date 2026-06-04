## 2024-06-04 - [Pydantic JSON Serialization]
**Learning:** `json.loads(model.model_dump_json())` creates an unnecessary string intermediate that gets parsed back into a dictionary, which is slow.
**Action:** Use `model.model_dump(mode='json')` to retrieve a JSON-compatible dictionary directly without string serialization overhead.
