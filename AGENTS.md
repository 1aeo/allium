# Allium Development Guide

See `.cursorrules` for project overview, output comparison workflow, and code conventions.

## Cursor Cloud specific instructions

### Services

| Service | How to run | Notes |
|---------|-----------|-------|
| Static site generator | `source venv/bin/activate && python3 allium/allium.py --progress` | Fetches live data from Tor APIs; use `--apis details` for faster/lower-memory runs (~400 MB vs ~2.4 GB) |
| Local preview server | `cd www && python3 -m http.server 8000` | Output lands in `./www` relative to where `allium.py` was invoked |

### Lint / Test / Build

Standard commands documented in README and `pytest.ini`:

- **Lint:** `flake8 . --select=E9,F63,F7,F82 --show-source --exclude=venv`
- **Tests:** `pytest --cov=allium` (801 unit/integration tests; slow/system tests excluded by default via `-m "not slow"`)
- **Generate site:** `python3 allium/allium.py --apis details --progress` (minimal mode, good for CI/dev)

### Non-obvious caveats

- The venv must be activated (`source venv/bin/activate`) before running any command; the project does not use a global install.
- `python3.12-venv` system package is required to create the venv on Ubuntu 24.04 (not installed by default).
- The `--apis details` flag is recommended for cloud agent runs to keep memory under ~600 MB and runtime under 1 minute; `--apis all` needs ~3 GB RAM and 2-5 minutes.
- Site output directory defaults to `./www` relative to CWD, not relative to `allium/`. When running from repo root, output is at `/workspace/www/`.
- The 2 pre-existing flake8 F821 errors are in test `__main__` blocks (`tests/integration/test_api_timeout.py`, `tests/integration/test_authorities.py`) — they do not affect test runs.
