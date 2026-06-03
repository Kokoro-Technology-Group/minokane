## 2024-05-24 - [Secure Token Comparison]
**Vulnerability:** Timing attack vulnerability when comparing sensitive tokens (like API keys) using standard equality operators (`==`, `!=`).
**Learning:** Python's standard string comparison compares character by character and returns `False` on the first mismatch. This allows an attacker to deduce the correct token by measuring the time it takes for the comparison to fail.
**Prevention:** Use `secrets.compare_digest()` for comparing sensitive strings. It performs a constant-time comparison, preventing timing attacks. Always check for `None` before passing variables to `compare_digest` to avoid exceptions.
