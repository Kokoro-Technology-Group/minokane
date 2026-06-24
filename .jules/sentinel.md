## 2024-05-18 - [HIGH] Fix timing attack vulnerability in API key validation
**Vulnerability:** Timing attack vulnerability in API key validation (`verify_api_key`) due to the use of standard equality operators (`!=`).
**Learning:** Python's standard string comparison operators check characters one by one and stop at the first mismatch. This can allow attackers to guess secrets by measuring the time it takes for the comparison to fail.
**Prevention:** Always use `secrets.compare_digest` for comparing sensitive strings like API keys, passwords, or tokens. Remember to handle `None` values when using `compare_digest` to prevent `TypeError`.
