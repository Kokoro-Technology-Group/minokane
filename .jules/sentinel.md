## 2026-05-13 - Removed Hardcoded API Key
**Vulnerability:** A hardcoded API key ('minokane-dev-key') was present as a default value in the backend configuration ('backend/app/config.py') and frontend ('frontend/src/scripts/api.ts').
**Learning:** This is a critical security vulnerability that could guarantee access for anyone who finds the source code or uses default configurations. Hardcoded secrets are easily discoverable and bypass environmental configuration.
**Prevention:** Rely strictly on environment variables for API authentication keys and validate them. Ensure the backend authentication logic fails securely (e.g., returning 403 Forbidden) if the API key is not configured or is an empty string.
