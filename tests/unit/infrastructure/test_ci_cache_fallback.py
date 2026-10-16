"""CI seeds every enabled API cache and uses it when a live fetch times out.

The setup job sets ALLIUM_CI_CACHE_FALLBACK=1. Production does not, so a
normal install still hits the network and never copies these fixtures.
"""

import gc
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from allium.lib import workers
from allium.lib.coordinator import Coordinator
from allium.lib.file_io_utils import create_cache_manager, create_timestamp_manager

REPO = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO / "tests" / "fixtures" / "ci"
HELPER = REPO / "scripts" / "ci_cache_fallback.sh"
HTTP_APIS = (
    workers.DETAILS_CONFIG,
    workers.UPTIME_CONFIG,
    workers.BANDWIDTH_CONFIG,
    workers.AROI_CONFIG,
    workers.EXIT_DNS_HEALTH_CONFIG,
)


def _load(name):
    return json.loads((FIXTURE_DIR / ("%s.json" % name)).read_text(encoding="utf-8"))


def _now_stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bash(script, cwd, env):
    return subprocess.run(
        ["bash", "-c", script],
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _env(enabled=True, fixture_dir=None):
    env = os.environ.copy()
    env.pop("ALLIUM_CI_CACHE_FALLBACK", None)
    env.pop("ALLIUM_CI_FIXTURE_DIR", None)
    env.pop("ALLIUM_CI_DETAILS_FALLBACK", None)
    if enabled:
        env["ALLIUM_CI_CACHE_FALLBACK"] = "1"
    if fixture_dir is not None:
        env["ALLIUM_CI_FIXTURE_DIR"] = str(fixture_dir)
    return env


def _isolate(tmp_path):
    cache = create_cache_manager(str(tmp_path))
    stamps = create_timestamp_manager(str(tmp_path))
    return (
        patch.object(workers, "_cache_manager", cache),
        patch.object(workers, "_timestamp_manager", stamps),
        patch.object(workers, "_save_state", lambda: True),
        patch.object(time, "sleep", lambda *_args, **_kwargs: None),
        cache,
    )


def test_fixtures_cover_every_api_the_default_run_fetches():
    """--apis all (allium.py's default) is the set CI has to be able to substitute."""
    enabled = {config.api_name for config in Coordinator.iter_enabled_worker_entries("all")}
    on_disk = {path.stem for path in FIXTURE_DIR.glob("*.json")}
    listed = set(re.search(r'CI_CACHE_FIXTURES="([^"]*)"', HELPER.read_text(encoding="utf-8")).group(1).split())
    assert enabled == on_disk == listed
    details = [config.api_name for config in Coordinator.iter_enabled_worker_entries("details")]
    assert details == ["onionoo_details"]
    assert set(details) < enabled


def test_fixtures_pass_the_cache_validators():
    assert workers._validate_onionoo_document(_load("onionoo_details"))
    assert _load("onionoo_details")["relays"]
    for name in ("onionoo_uptime", "onionoo_bandwidth"):
        document = _load(name)
        assert workers._validate_onionoo_document(document)
        assert document["relays"] == []
    assert workers._validate_aroi_response(_load("aroi_validation"))
    assert workers._validate_exit_dns_health_response(_load("exit_dns_health"))
    collector = _load("collector_consensus")
    collector["fetched_at"] = _now_stamp()
    assert workers._validate_collector_cache(collector)
    assert workers._validate_descriptors_cache(_load("collector_descriptors"))


@pytest.mark.parametrize("config", HTTP_APIS, ids=lambda config: config.api_name)
def test_fresh_cache_timeout_returns_that_apis_fixture(config, tmp_path):
    """One attempt at the fresh-cache budget, then the seeded document."""
    document = _load(config.api_name)
    patches = _isolate(tmp_path)
    cache = patches[-1]
    logs = []
    with patches[0], patches[1], patches[2], patches[3], \
         patch.object(workers, "_fetch_url_with_total_timeout",
                      side_effect=workers.TotalTimeoutError("total timeout")) as fetch:
        cache.save_cache(config.api_name, document)
        result = workers._fetch_with_cache_fallback(
            "https://example.invalid/%s" % config.api_name,
            config,
            progress_logger=logs.append,
            return_fresh_cache=False,
        )
    assert config.retry_on_fresh_cache is False
    assert config.timeout_fresh_cache <= 90
    assert result == document
    assert fetch.call_count == 1
    assert fetch.call_args.args[1] == config.timeout_fresh_cache
    assert "using cached %s data due to timeout" % config.display_name in logs


@pytest.mark.parametrize("api_name, fetch", [
    ("onionoo_bandwidth", workers.fetch_onionoo_bandwidth),
    ("aroi_validation", workers.fetch_aroi_validation),
    ("exit_dns_health", workers.fetch_exit_dns_health),
])
def test_fresh_cache_short_circuit_does_not_hit_the_network(api_name, fetch, tmp_path):
    """These workers return a fresh cache before opening a socket."""
    document = _load(api_name)
    patches = _isolate(tmp_path)
    cache = patches[-1]
    with patches[0], patches[1], patches[2], patches[3], \
         patch.object(workers, "_fetch_url_with_total_timeout",
                      side_effect=AssertionError("network")) as called:
        cache.save_cache(api_name, document)
        if api_name == "onionoo_bandwidth":
            result = fetch("https://example.invalid/bandwidth", 12, progress_logger=None)
        else:
            result = fetch("https://example.invalid/%s" % api_name, progress_logger=None)
    assert result == document
    assert called.call_count == 0


def test_collector_fresh_cache_skips_the_network(tmp_path):
    document = _load("collector_consensus")
    document["fetched_at"] = _now_stamp()
    patches = _isolate(tmp_path)
    cache = patches[-1]
    with patches[0], patches[1], patches[2], patches[3], \
         patch("allium.lib.consensus.CollectorFetcher", side_effect=AssertionError("network")):
        cache.save_cache("collector_consensus", document)
        result = workers.fetch_collector_consensus_data(progress_logger=lambda _m: None)
    assert result["consensus_method_info"]["total_voters"] == 1
    assert workers.COLLECTOR_TIMEOUT_FRESH_CACHE <= 90


def test_collector_timeout_uses_the_fresh_budget_and_the_cache(tmp_path):
    document = _load("collector_consensus")
    document["fetched_at"] = _now_stamp()
    patches = _isolate(tmp_path)
    cache = patches[-1]
    seen = []

    class _Fetcher(object):
        def __init__(self, timeout=30, authorities=None, retry_count=2, retry_delay_base=1.0):
            seen.append(timeout)

        def fetch_all(self):
            raise TimeoutError("total timeout")

    with patches[0], patches[1], patches[2], patches[3], \
         patch("allium.lib.consensus.CollectorFetcher", _Fetcher):
        cache.save_cache("collector_consensus", document)
        path = Path(tmp_path) / "collector_consensus.json"
        old = time.time() - 7200
        os.utime(str(path), (old, old))
        result = workers.fetch_collector_consensus_data(progress_logger=lambda _m: None)
    assert seen == [workers.COLLECTOR_TIMEOUT_FRESH_CACHE]
    assert result["consensus_method_info"]["total_voters"] == 1


def test_descriptors_fresh_cache_skips_the_network(tmp_path):
    document = _load("collector_descriptors")
    patches = _isolate(tmp_path)
    cache = patches[-1]
    with patches[0], patches[1], patches[2], patches[3], \
         patch.object(workers, "_fetch_url_with_total_timeout",
                      side_effect=AssertionError("network")):
        cache.save_cache("collector_descriptors", document)
        result = workers.fetch_collector_descriptors(progress_logger=lambda _m: None)
    assert result["family_cert_groups"] == {}
    assert workers.DESCRIPTORS_TIMEOUT_FRESH_CACHE <= 90


def test_descriptors_timeout_uses_the_fresh_budget_and_the_cache(tmp_path):
    document = _load("collector_descriptors")
    patches = _isolate(tmp_path)
    cache = patches[-1]
    with patches[0], patches[1], patches[2], patches[3], \
         patch.object(workers, "_fetch_url_with_total_timeout",
                      side_effect=workers.TotalTimeoutError("total timeout")) as fetch:
        cache.save_cache("collector_descriptors", document)
        path = Path(tmp_path) / "collector_descriptors.json"
        old = time.time() - 7200
        os.utime(str(path), (old, old))
        result = workers.fetch_collector_descriptors(progress_logger=lambda _m: None)
    assert result["family_cert_fingerprints"] == []
    assert fetch.call_count >= 1
    assert {call.args[1] for call in fetch.call_args_list} == {workers.DESCRIPTORS_TIMEOUT_FRESH_CACHE}


def test_seed_writes_every_cache_without_a_conditional_timestamp(tmp_path):
    checkout = tmp_path / "allium-src"
    (checkout / "allium" / "lib").mkdir(parents=True)
    (checkout / "allium" / "lib" / "workers.py").write_text("# marker\n", encoding="utf-8")
    cache_dir = checkout / "allium" / "data" / "cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "onionoo_details_timestamp.txt").write_text("old\n", encoding="utf-8")
    (cache_dir / "collector_consensus_timestamp.txt").write_text("old\n", encoding="utf-8")

    completed = _bash('source "%s"; seed_ci_api_caches' % HELPER, checkout, _env())
    assert completed.returncode == 0, completed.stderr + completed.stdout
    for name in FIXTURE_DIR.glob("*.json"):
        assert (cache_dir / name.name).is_file()
        assert not (cache_dir / ("%s_timestamp.txt" % name.stem)).exists()
    details = json.loads((cache_dir / "onionoo_details.json").read_text(encoding="utf-8"))
    assert details == _load("onionoo_details")
    collector = json.loads((cache_dir / "collector_consensus.json").read_text(encoding="utf-8"))
    assert workers._validate_collector_cache(collector)
    assert "seeded API caches" in completed.stdout


def test_seed_is_a_noop_unless_the_setup_job_opts_in(tmp_path):
    checkout = tmp_path / "allium-src"
    (checkout / "allium" / "lib").mkdir(parents=True)
    (checkout / "allium" / "lib" / "workers.py").write_text("# marker\n", encoding="utf-8")
    completed = _bash('source "%s"; seed_ci_api_caches' % HELPER, checkout, _env(enabled=False))
    assert completed.returncode == 0, completed.stderr
    assert not (checkout / "allium" / "data" / "cache").exists()


def test_seed_rejects_a_details_only_fixture_directory(tmp_path):
    """Every declared API fixture is required, not only onionoo details."""
    checkout = tmp_path / "allium-src"
    (checkout / "allium" / "lib").mkdir(parents=True)
    (checkout / "allium" / "lib" / "workers.py").write_text("# marker\n", encoding="utf-8")
    partial = tmp_path / "partial"
    partial.mkdir()
    shutil.copy(str(FIXTURE_DIR / "onionoo_details.json"), str(partial / "onionoo_details.json"))
    completed = _bash('source "%s"; seed_ci_api_caches' % HELPER, checkout, _env(fixture_dir=partial))
    assert completed.returncode == 1
    assert "fixtures were not found" in completed.stdout
    assert not (checkout / "allium" / "data" / "cache" / "onionoo_details.json").exists()


def test_seed_fails_when_the_job_opted_in_but_the_fixtures_are_missing(tmp_path):
    checkout = tmp_path / "allium-src"
    (checkout / "allium" / "lib").mkdir(parents=True)
    (checkout / "allium" / "lib" / "workers.py").write_text("# marker\n", encoding="utf-8")
    empty = tmp_path / "empty"
    empty.mkdir()
    completed = _bash('source "%s"; seed_ci_api_caches' % HELPER, checkout, _env(fixture_dir=empty))
    assert completed.returncode == 1
    assert "fixtures were not found" in completed.stdout


def test_live_failure_is_not_replaced_by_the_fixtures(tmp_path):
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
ALLIUM_CI_CACHE_FALLBACK=
printf 'prod:%%s\\n' "$(ci_live_generation_outcome 0 "%s")"
""" % (HELPER, missing, missing, page, missing)
    completed = _bash(script, tmp_path, _env())
    assert completed.returncode == 0, completed.stderr
    lines = dict(line.split(":", 1) for line in completed.stdout.splitlines() if ":" in line)
    assert lines["fail"] == "fail"
    assert lines["fallback"] == "fallback"
    assert lines["ok"] == "ok"
    assert lines["prod"] == "ok"


def test_ci_generate_once_keeps_a_real_failure(tmp_path):
    """Exit 0 with a page is success. Exit 1 is not replaced by the fixtures."""
    fake = tmp_path / "fake_allium.py"
    fake.write_text(
        "import os, sys\n"
        "from pathlib import Path\n"
        "out = sys.argv[sys.argv.index('--out') + 1]\n"
        "if os.environ.get('ALLIUM_FAKE_HTML') == '1':\n"
        "    Path(out).mkdir(parents=True, exist_ok=True)\n"
        "    Path(out, 'index.html').write_text('<html></html>\\n')\n"
        "sys.exit(int(os.environ.get('ALLIUM_FAKE_EXIT', '0')))\n",
        encoding="utf-8",
    )
    script = """
set -e
source "%s"
export API_MODE="--apis details"
export ALLIUM_FAKE_EXIT ALLIUM_FAKE_HTML
out="%s/site"
ALLIUM_FAKE_EXIT=0 ALLIUM_FAKE_HTML=1 ci_generate_once "$out" "%s"
test -f "$out/index.html"
rm -rf "$out"
ALLIUM_FAKE_EXIT=7 ALLIUM_FAKE_HTML=0
if ci_generate_once "$out" "%s"; then
  echo "exit 7 was treated as success"
  exit 1
fi
echo "kept-failure"
""" % (HELPER, tmp_path, fake, fake)
    completed = _bash(script, tmp_path, _env())
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert "kept-failure" in completed.stdout
    assert "Generation failed with exit code 7" in completed.stdout
    assert not (tmp_path / "site" / "index.html").exists()


def test_fixture_http_fallback_generates_index_html(tmp_path):
    """Exit 0 and no page: serve the fixtures once. This is the setup job's details run."""
    out = tmp_path / "www"
    data_dir = REPO / "allium" / "data"
    backup = tmp_path / "data-backup"
    existed = data_dir.exists()
    if existed:
        shutil.copytree(str(data_dir), str(backup))
    script = (
        'source "%s"; generate_from_ci_fixtures "%s" allium/allium.py "--apis details"'
        % (HELPER, out)
    )
    try:
        completed = _bash(script, REPO, _env(enabled=False))
    finally:
        if data_dir.exists():
            shutil.rmtree(str(data_dir))
        if existed:
            shutil.copytree(str(backup), str(data_dir))
    assert completed.returncode == 0, completed.stderr + completed.stdout
    index = (out / "index.html").read_text(encoding="utf-8", errors="replace")
    assert "<html" in index
    assert "generating from committed API fixtures" in completed.stdout


def test_ci_helper_script_is_not_gitignored():
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "scripts/ci_cache_fallback.sh"],
        cwd=str(REPO),
        check=False,
    )
    assert ignored.returncode != 0
    ignored_old = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", "scripts/ci_onionoo_details.sh"],
        cwd=str(REPO),
        check=False,
    )
    # *.sh is ignored. The retired details helper must not be force-tracked.
    assert "ci_onionoo_details" not in (REPO / ".gitignore").read_text(encoding="utf-8")
    assert ignored_old.returncode == 0 or not (REPO / "scripts" / "ci_onionoo_details.sh").exists()


def test_setup_job_keeps_the_hang_backstop_and_opts_into_every_cache():
    workflow = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    setup = (REPO / "setup.sh").read_text(encoding="utf-8")
    assert "timeout 1800" not in workflow
    assert "timeout 900 bash setup.sh" in workflow
    assert 'ALLIUM_CI_CACHE_FALLBACK: "1"' in workflow
    assert "ALLIUM_CI_DETAILS_FALLBACK" not in workflow
    assert "seed_ci_api_caches" in setup
    assert "ci_generate_once" in setup
    assert "generate_from_ci_onionoo_fixture" not in setup
    assert 'echo "❌ Setup script exited with code $setup_exit_code"' in workflow
    assert "exit 1" in workflow[workflow.find("Setup script exited"):workflow.find("Setup script exited") + 200]


def _run_allium(tmp_path, cache_dir, apis):
    """Run allium.py in-process with every socket fetch raising a timeout."""
    repo_allium = str(REPO / "allium")
    original_sleep = time.sleep
    original_exit = os._exit
    original_argv = sys.argv
    original_path = sys.path[:]
    code = 1
    out = tmp_path / "site"

    def _timeout(*_args, **_kwargs):
        raise live.TotalTimeoutError("total timeout")

    def _exit(status):
        raise SystemExit(status)

    sys.path.insert(0, repo_allium)
    try:
        import lib.workers as live
        live._cache_manager = create_cache_manager(str(cache_dir))
        live._timestamp_manager = create_timestamp_manager(str(cache_dir))
        live._save_state = lambda: True
        live._fetch_url_with_total_timeout = _timeout
        time.sleep = lambda *_args, **_kwargs: None
        os._exit = _exit
        sys.argv = [
            "allium.py", "--apis", apis, "--no-charts", "--workers", "1",
            "--out", str(out),
        ]
        try:
            runpy.run_path(str(REPO / "allium" / "allium.py"), run_name="__main__")
            code = 0
        except SystemExit as exc:
            code = exc.code if exc.code is not None else 0
    finally:
        time.sleep = original_sleep
        os._exit = original_exit
        sys.argv = original_argv
        sys.path[:] = original_path
        for name in list(sys.modules):
            if name == "lib" or name.startswith("lib."):
                del sys.modules[name]
        gc.unfreeze()
        gc.enable()
    return code, out


def _cache_from_seed(tmp_path):
    checkout = tmp_path / "src"
    (checkout / "allium" / "lib").mkdir(parents=True)
    (checkout / "allium" / "lib" / "workers.py").write_text("# marker\n", encoding="utf-8")
    completed = _bash('source "%s"; seed_ci_api_caches' % HELPER, checkout, _env())
    assert completed.returncode == 0, completed.stderr + completed.stdout
    return checkout / "allium" / "data" / "cache"


def test_index_html_when_every_enabled_api_times_out(tmp_path):
    cache_dir = _cache_from_seed(tmp_path)
    code, out = _run_allium(tmp_path, cache_dir, "all")
    assert code == 0
    index = (out / "index.html").read_text(encoding="utf-8", errors="replace")
    listing = (out / "top500.html").read_text(encoding="utf-8", errors="replace")
    assert "<html" in index
    assert "CIFallbackExit" in listing


def test_optional_apis_timing_out_still_write_index(tmp_path):
    """Uptime, bandwidth, AROI, exit DNS, and CollecTor are optional once details exists."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    shutil.copy(str(FIXTURE_DIR / "onionoo_details.json"), str(cache_dir / "onionoo_details.json"))
    code, out = _run_allium(tmp_path, cache_dir, "all")
    assert code == 0
    index = (out / "index.html").read_text(encoding="utf-8", errors="replace")
    listing = (out / "top500.html").read_text(encoding="utf-8", errors="replace")
    assert "<html" in index
    assert "CIFallbackExit" in listing
