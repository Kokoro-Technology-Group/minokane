
## 2024-05-24 - [Timing Attack in API Key Validation]
**Vulnerability:** The API key validation in `backend/app/routes/questions.py` was using standard equality `!=` operators which are vulnerable to timing attacks.
**Learning:** Python's standard equality operators check string characters one-by-one and exit early, letting attackers guess a secret key by measuring the response time of requests with different incorrect keys.
**Prevention:** Always use `secrets.compare_digest` when comparing sensitive strings like tokens or API keys to ensure a constant-time comparison.
