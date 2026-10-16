"""CI setup job bounds a slow Onionoo details fetch with the existing cache.

The setup end-to-end job seeds allium/data/cache/onionoo_details.json from
tests/fixtures/ci/onionoo_details.json before generation. workers.py already
uses the fresh-cache timeout (no retries) and returns that document when the
live request times out. Production builds do not set ALLIUM_CI_DETAILS_FALLBACK.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import call, patch

from allium.lib import workers
from allium.lib.file_io_utils import create_cache_manager, create_timestamp_manager

REPO = Path(__file__).resolve().parents[3]
FIXTURE = REPO / "tests" / "fixtures" / "ci" / "onionoo_details.json"
HELPER = REPO / "scripts" / "ci_onionoo_details.sh"
DETAILS_URL = "https://onionoo.torproject.org/details"


def _load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_ci_details_fixture_is_a_usable_onionoo_document():
    document = _load_fixture()
    assert workers._validate_onionoo_document(document) is True
    assert document["relays"]
    published = document["relays_published"]
    for relay in document["relays"]:
        assert len(relay["fingerprint"]) == 40
        assert relay["running"] is True
        assert relay["last_seen"] == published
        assert isinstance(relay["exit_policy_summary"], dict)


def test_fresh_details_cache_times_out_once_at_the_fresh_budget(tmp_path):
    """Seeding a fresh cache is what keeps the setup job off the 5-minute budget."""
    document = _load_fixture()
    cache = create_cache_manager(str(tmp_path))
    stamps = create_timestamp_manager(str(tmp_path))
    logs = []
    with patch.object(workers, "_cache_manager", cache), \
         patch.object(workers, "_timestamp_manager", stamps), \
         patch.object(workers, "_save_state", lambda: True), \
         patch.object(workers, "_fetch_url_with_total_timeout",
                      side_effect=workers.TotalTimeoutError("slow")) as fetch, \
         patch.object(workers.time, "sleep"):
        workers._save_cache("onionoo_details", document)
        result = workers._fetch_with_cache_fallback(
            DETAILS_URL, workers.DETAILS_CONFIG, progress_logger=logs.append)

    assert workers.DETAILS_CONFIG.retry_on_fresh_cache is False
    assert workers.DETAILS_TIMEOUT_FRESH_CACHE <= 90
    assert workers.DETAILS_TIMEOUT_STALE_CACHE >= 300
    assert result == document
    assert fetch.call_args == call(
        DETAILS_URL, workers.DETAILS_TIMEOUT_FRESH_CACHE, None, response_headers={})
    assert fetch.call_count == 1
    assert "using cached onionoo details data due to timeout" in logs


def _bash(script, cwd, env):
    return subprocess.run(
        ["bash", "-c", script],
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _helper_env(fixture=None, enabled=True):
    env = os.environ.copy()
    env.pop("ALLIUM_CI_DETAILS_FALLBACK", None)
    env.pop("ALLIUM_CI_DETAILS_FIXTURE", None)
    if enabled:
        env["ALLIUM_CI_DETAILS_FALLBACK"] = "1"
    if fixture is not None:
        env["ALLIUM_CI_DETAILS_FIXTURE"] = str(fixture)
    return env


def test_seed_writes_details_cache_without_a_conditional_timestamp(tmp_path):
    checkout = tmp_path / "allium-src"
    (checkout / "allium" / "lib").mkdir(parents=True)
    (checkout / "allium" / "lib" / "workers.py").write_text("# marker\n", encoding="utf-8")
    stamp = checkout / "allium" / "data" / "cache" / "onionoo_details_timestamp.txt"
    stamp.parent.mkdir(parents=True)
    stamp.write_text("Mon, 01 Jan 2024 00:00:00 GMT\n", encoding="utf-8")

    completed = _bash(
        'source "%s"; seed_ci_onionoo_details_cache' % HELPER,
        checkout,
        _helper_env(FIXTURE),
    )
    assert completed.returncode == 0, completed.stderr
    cached = json.loads(
        (checkout / "allium" / "data" / "cache" / "onionoo_details.json").read_text(encoding="utf-8"))
    assert cached == _load_fixture()
    assert not stamp.exists()
    assert "seeded Onionoo details cache" in completed.stdout


def test_seed_is_a_noop_unless_the_setup_job_opts_in(tmp_path):
    checkout = tmp_path / "allium-src"
    (checkout / "allium" / "lib").mkdir(parents=True)
    (checkout / "allium" / "lib" / "workers.py").write_text("# marker\n", encoding="utf-8")
    completed = _bash(
        'source "%s"; seed_ci_onionoo_details_cache' % HELPER,
        checkout,
        _helper_env(FIXTURE, enabled=False),
    )
    assert completed.returncode == 0, completed.stderr
    assert not (checkout / "allium" / "data" / "cache" / "onionoo_details.json").exists()


def test_seed_fails_when_the_job_opted_in_but_the_fixture_is_missing(tmp_path):
    checkout = tmp_path / "allium-src"
    (checkout / "allium" / "lib").mkdir(parents=True)
    (checkout / "allium" / "lib" / "workers.py").write_text("# marker\n", encoding="utf-8")
    completed = _bash(
        'source "%s"; seed_ci_onionoo_details_cache' % HELPER,
        checkout,
        _helper_env(tmp_path / "missing.json"),
    )
    assert completed.returncode == 1
    assert "fixture was not found" in completed.stdout


def test_fixture_http_fallback_generates_index_html(tmp_path):
    """The setup job's second path: serve the fixture and still render the site."""
    out = tmp_path / "www"
    data_dir = REPO / "allium" / "data"
    backup = tmp_path / "data-backup"
    existed = data_dir.exists()
    if existed:
        shutil.copytree(data_dir, backup)
    env = _helper_env(FIXTURE, enabled=False)
    script = 'source "%s"; generate_from_ci_onionoo_fixture "%s" allium/allium.py' % (HELPER, out)
    try:
        completed = _bash(script, REPO, env)
    finally:
        if data_dir.exists():
            shutil.rmtree(data_dir)
        if existed:
            shutil.copytree(backup, data_dir)
    assert completed.returncode == 0, completed.stderr + completed.stdout
    index = (out / "index.html").read_text(encoding="utf-8", errors="replace")
    assert "<html" in index
    assert "generating from the committed details fixture" in completed.stdout
    assert "127.0.0.1" in completed.stdout


def test_ci_helper_script_is_not_gitignored():
    """*.sh is ignored. This helper has to stay tracked, like setup.sh."""
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "scripts/ci_onionoo_details.sh"],
        cwd=str(REPO),
        check=False,
    )
    assert ignored.returncode != 0


def test_live_failure_is_not_replaced_by_the_fixture(tmp_path):
    """Exit 1 stays a failure. Exit 0 with no page is the only fixture path."""
    page = tmp_path / "www" / "index.html"
    page.parent.mkdir()
    page.write_text("<html lang=\"en\"></html>\n", encoding="utf-8")
    missing = tmp_path / "www" / "missing.html"
    script = """
set -e
source "%s"
printf 'fail:%%s\\n' "$(ci_live_generation_outcome 1 "%s")"
printf 'fallback:%%s\\n' "$(ci_live_generation_outcome 0 "%s")"
printf 'ok:%%s\\n' "$(ci_live_generation_outcome 0 "%s")"
ALLIUM_CI_DETAILS_FALLBACK=
printf 'prod:%%s\\n' "$(ci_live_generation_outcome 0 "%s")"
""" % (HELPER, missing, missing, page, missing)
    completed = _bash(script, tmp_path, _helper_env(FIXTURE))
    assert completed.returncode == 0, completed.stderr
    lines = dict(line.split(":", 1) for line in completed.stdout.splitlines() if ":" in line)
    assert lines["fail"] == "fail"
    assert lines["fallback"] == "fallback"
    assert lines["ok"] == "ok"
    assert lines["prod"] == "ok"


def test_setup_job_keeps_the_hang_backstop_and_opts_into_the_cache():
    workflow = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    setup = (REPO / "setup.sh").read_text(encoding="utf-8")
    assert "timeout 1800" not in workflow
    assert "timeout 900 bash setup.sh" in workflow
    assert 'ALLIUM_CI_DETAILS_FALLBACK: "1"' in workflow
    assert "seed_ci_onionoo_details_cache" in setup
    assert "generate_from_ci_onionoo_fixture" in setup
    # A non-zero allium exit is a real failure. Only the exit-0 / no-page
    # path, which is how allium reports a missing Onionoo document, may
    # generate from the fixture.
    assert 'echo "❌ Setup script exited with code $setup_exit_code"' in workflow
    assert "exit 1" in workflow[workflow.find("Setup script exited"):workflow.find("Setup script exited") + 200]
