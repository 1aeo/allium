# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Allium is a Python static site generator that produces ~22k HTML pages of Tor relay analytics from the Onionoo API. No databases, Docker, or Node.js required.

### Development environment

- Python venv at `/workspace/venv`; activate with `source /workspace/venv/bin/activate`.
- Dev dependencies: `pip install -r config/requirements-dev.txt` (includes pytest, flake8, bandit, etc.).

### Running the application

- **Full generation** (~3 GB RAM, 2-5 min): `python3 allium/allium.py --progress --apis all`
- **Minimal/fast mode** (~1 GB RAM, <1 min): `python3 allium/allium.py --progress --apis details`
- **Serve output**: `cd www && python3 -m http.server 8000` then visit http://localhost:8000
- Output goes to `./www/` by default. Use `--out <path>` to override.

### Standard commands (see README.md and .cursorrules for details)

| Task | Command |
|------|---------|
| Lint (critical) | `flake8 . --select=E9,F63,F7,F82 --show-source --exclude=venv` |
| Unit tests | `pytest` (runs non-slow tests by default; see `pytest.ini`) |
| Coverage | `pytest --cov=allium --cov-report=html` |
| Security scan | `bandit -r . --exclude=venv` |
| Template lint | `djlint allium/templates/` |

### Gotchas

- Always pass `--exclude=venv` to `flake8` and `bandit` to avoid false positives from third-party packages.
- The `--apis details` mode skips uptime/bandwidth/AROI/collector data, so uptime stats will show 0%. This is expected and useful for fast iteration.
- `pytest.ini` already configures `--timeout=30` and `-m "not slow"`, so `pytest` alone is sufficient for unit tests.
- There are a small number of pre-existing test failures (4 as of writing) that are not caused by environment setup.
- Site generation requires internet access to fetch live data from `onionoo.torproject.org`. If the API is down, generation will fail with retry logic.
- The `www/` output directory is gitignored. Do not commit generated output.
