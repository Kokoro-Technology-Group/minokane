## 2025-02-18 - [API Key Timing Attack]
**Vulnerability:** API key comparison in `backend/app/routes/questions.py` used `!=`, which is vulnerable to timing attacks.
**Learning:** Python's standard string comparison operators leak timing information, allowing attackers to guess keys character-by-character.
**Prevention:** Use `secrets.compare_digest` for constant-time comparison of sensitive tokens.
