## 2024-06-18 - Avoid unnecessary json serialization
**Learning:** In Pydantic, serializing to a json string and parsing it back (`json.loads(model.model_dump_json())`) is much slower (~2.5x) than directly requesting json-compatible dict (`model.model_dump(mode='json')`).
**Action:** Always prefer `model.model_dump(mode='json')` when getting a dictionary out of Pydantic.
