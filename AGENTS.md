# Allium

## Cursor Cloud specific instructions

Allium is a Python CLI tool that generates ~22k static HTML pages of Tor relay analytics. There are no databases, Docker containers, or background services — just Python + Jinja2.

### Project layout

- `allium/allium.py` — main entry point
- `allium/templates/` — Jinja2 templates
- `tests/` — pytest test suite (745+ unit tests)
- `config/requirements-dev.txt` — dev dependencies (includes production deps)
- `compare_outputs.py` — before/after HTML comparison tool

### Running the dev environment

All commands assume the virtualenv at `/workspace/venv` is activated (`source venv/bin/activate`).

| Task | Command |
|------|---------|
| Generate site (minimal, ~400 MB RAM) | `python3 allium/allium.py --apis details --progress` |
| Generate site (full, ~3 GB RAM) | `python3 allium/allium.py --apis all --progress` |
| Serve generated site | `cd www && python3 -m http.server 8000` |
| Run tests | `pytest` |
| Lint (critical errors only) | `flake8 . --select=E9,F63,F7,F82 --exclude=venv` |
| Security scan | `bandit -r . --exclude=venv` |

### Non-obvious caveats

- The default output directory is `./www` (relative to CWD), not `allium/www/`. Run `allium.py` from the repo root.
- `python3.12-venv` system package is required to create the virtualenv; the update script installs it automatically.
- `--apis details` fetches only the Onionoo Details API (~400 MB) and is much faster/lighter than `--apis all` (~2.4 GB). Use `details` for quick dev iterations.
- pytest is configured with `--timeout=30` and `-m "not slow"` by default (see `pytest.ini`). Slow/integration/system tests are excluded from default runs.
- Two pre-existing flake8 F821 warnings exist in `tests/integration/` files — these are not regressions.
- See `.cursorrules` for the output comparison workflow (before/after HTML diffing for template or data processing changes).
