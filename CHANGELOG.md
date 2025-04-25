# Changelog

## [0.2.0] - 2025-04-24

### Changed

- BREAKING: The server now uses `HOST` and `PORT` environment variables for SSE/web mode (Uvicorn/FastMCP). `SERVER_HOST` and `SERVER_PORT` are now legacy and only used for stdio/AI mode.

- Updated `.env.example`, `README.md`, and all config and CLI reporting to clarify the correct variables for each mode.

- Improved onboarding and documentation for correct server configuration.

- Fixed all server startup and CLI commands to be fully compatible with FastMCP 2.x+ (no more event loop or transport errors).
