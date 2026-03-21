# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Allium is a Python static site generator that produces ~22k HTML pages of Tor relay analytics from the Onionoo API. No Docker, Node.js, or databases are needed — only Python 3.8+ and Jinja2.

### Virtual environment

All commands should be run inside the venv at `/workspace/venv`. Activate with:

```bash
source /workspace/venv/bin/activate
```

### Key commands

| Task | Command |
|------|---------|
| Install deps | `pip install -r config/requirements-dev.txt` |
| Run tests | `pytest` |
| Lint (CI-level) | `flake8 . --select=E9,F63,F7,F82 --show-source --exclude=venv` |
| Full lint | `flake8 . --max-complexity=10 --max-line-length=127 --exclude=venv` |
| Generate site (lightweight, ~400MB RAM) | `python3 allium/allium.py --progress --apis details` |
| Generate site (full, ~3GB RAM) | `python3 allium/allium.py --progress --apis all` |
| Serve site | `cd www && python3 -m http.server 8000` |

### Caveats

- `flake8` must be run with `--exclude=venv` to avoid false positives from installed packages.
- The default `pytest` run excludes tests marked `slow` (see `pytest.ini`). To run all tests: `pytest -m ""`.
- Site generation requires network access to `onionoo.torproject.org`. Use `--apis details` for faster, lower-memory runs (~400MB vs ~3GB).
- Generated output lands in `./www/` by default (relative to working directory). The output directories `allium/www_baseline/` and `allium/www_after/` are gitignored for output comparison workflows.
- See `.cursorrules` for the output comparison workflow required before/after major HTML-affecting changes.
