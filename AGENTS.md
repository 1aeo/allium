# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Allium is a Python static site generator for Tor relay analytics. It fetches data from Tor Project APIs (Onionoo, CollecTor, AROI Validator), processes relay records, and generates ~21,000+ static HTML pages. There is no database, no Docker, and no long-running backend service.

### Development environment

- **Python 3.8+** with a virtualenv at `venv/`
- Production dep: `Jinja2` only (`config/requirements.txt`)
- Dev deps: pytest, flake8, bandit, safety, djlint, memory-profiler (`config/requirements-dev.txt`)
- Activate with: `source venv/bin/activate`
- `python3.12-venv` system package is required (not installed by default on Ubuntu 24.04)

### Commands reference

| Task | Command |
|------|---------|
| Run tests | `pytest` (runs 665+ unit/integration tests; slow/system tests excluded by default via `-m "not slow"` in `pytest.ini`) |
| Lint (Python) | `flake8 allium/ tests/` (no `.flake8` config exists; always scope to project dirs to avoid linting `venv/`) |
| Security scan | `bandit -r allium/` |
| Template lint | `djlint allium/templates/` |
| Generate site (minimal) | `python3 allium/allium.py --apis details --progress` (~400MB RAM, ~1 min) |
| Generate site (full) | `python3 allium/allium.py --progress` (~3GB RAM, ~2-5 min) |
| Serve output | `cd www && python3 -m http.server 8000` (output defaults to `./www/` from repo root) |

### Non-obvious caveats

- **flake8 scope**: There is no `.flake8` or `setup.cfg` config file. Always run `flake8 allium/ tests/` rather than `flake8 .` to avoid linting the virtualenv and getting thousands of false positives.
- **Output directory**: The site generator writes to `./www/` relative to `cwd`, not inside `allium/www/`. Run from the repo root.
- **Memory**: Full generation (`--apis all`) requires ~3GB RAM. Use `--apis details` for a lighter run (~400MB).
- **Network**: Site generation fetches live data from `onionoo.torproject.org`. If the API is down, cached data in `allium/data/cache/` is used as fallback.
- **pytest coverage**: `pytest.ini` enables `--cov-report=term-missing --cov-report=xml` by default. The `--cov` flag requires a target; without it, coverage runs on the whole directory. Tests use `pythonpath = .` so imports resolve from repo root.
- **conftest.py path setup**: `tests/conftest.py` handles a tricky import situation where `allium/allium.py` (the script) conflicts with `allium/` (the package). It pre-loads the package into `sys.modules` before tests run.
