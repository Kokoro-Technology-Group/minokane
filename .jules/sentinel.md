## 2024-05-24 - [API Key Timing Attack]
**Vulnerability:** API key string comparison using `==` allows timing attacks.
**Learning:** Found API key authentication using standard string equality checking which exposes timing information to attackers, potentially enabling them to discover valid keys.
**Prevention:** Always use `secrets.compare_digest` for cryptographic comparisons of secrets like tokens, keys or passwords.
