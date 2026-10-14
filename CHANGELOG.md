# Changelog

## Unreleased

- Renamed the project to Escólio (command `escolio`, wrapper `./es` / `es.ps1`, package `escolio`, app initials "ES").
- Kept compatibility with the old free-plaud names: `FREE_PLAUD_*` variables (env and `.env`, `ESCOLIO_*` wins), `free_plaud.sqlite3` when `escolio.sqlite3` is missing, `free_plaud_chunks` collection when `escolio_chunks` is missing, `free-plaud:*` localStorage keys migrated on read, and `FREE_PLAUD_ANSWER_API_KEY` migrated to `ESCOLIO_ANSWER_API_KEY` when saving.
- Added structured `PDF_PARSE_FAILED` handling for corrupted PDF ingestion.
- Added corpus status detection for embedding model mismatch between indexed vectors and current settings.
- Added validation to reject invalid chunk overlap settings before indexing.
- Fixed corpus reset to fail loudly on Chroma delete errors and preserve SQLite when vector reset fails.
- Sanitized provider failure limitations to avoid leaking raw remote error payloads.

## 1.0.0 - 2026-05-24

- Added machine-readable policy/state contract.
- Added deterministic repo bootstrap for LICENSE, FUNDING, Dependabot, and README scaffold.
- Added Docker image gate with Docker Image Doctor integration and static fallback.
- Added PR snapshot and CI diagnosis scripts for `babysit-pr`.
- Added CommonJS-compatible scripts with no `type=module` requirement.
- Added v1 smoke tests and release readiness checks.
