"""
Tests for CLI URL argument validation in allium.py.

Supported --base-url values must keep working. Only a bare slash (including
surrounding whitespace) is newly rejected, because vanity links are
"{base}/{domain}/" and "/" becomes a scheme-relative "//domain/" URL.
"""

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ALLIUM_DIR = PROJECT_ROOT / "allium"
_CLI_MODULE = None
_ADDED_MODULES = []


@pytest.fixture(scope="module", autouse=True)
def _drop_modules_loaded_by_the_cli():
    """allium.py imports `lib.*` from its own directory.

    Leaving that package in sys.modules publishes the real data paths and
    fails the worker cache-isolation scan. Drop only the modules this file
    loaded.
    """
    yield
    for name in _ADDED_MODULES:
        sys.modules.pop(name, None)


def _load_allium_cli_module():
    """Load allium/allium.py without leaving its directory on sys.path."""
    global _CLI_MODULE
    if _CLI_MODULE is not None:
        return _CLI_MODULE

    allium_dir = str(ALLIUM_DIR)
    allium_cli = os.path.join(allium_dir, "allium.py")
    inserted = allium_dir not in sys.path
    if inserted:
        sys.path.insert(0, allium_dir)
    before = set(sys.modules)
    try:
        spec = importlib.util.spec_from_file_location("allium_cli_module", allium_cli)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
    finally:
        if inserted:
            sys.path.remove(allium_dir)
        _ADDED_MODULES.extend(name for name in sys.modules if name not in before)
    _CLI_MODULE = module
    return module


def _vanity_href(base_url, domain="example.com"):
    """Same join the contact and relay templates use for a vanity URL."""
    return f"{base_url}/{domain}/"


def test_bare_slash_would_be_scheme_relative():
    """Documents the link the CLI must not be allowed to generate."""
    assert _vanity_href("/") == "//example.com/"


@pytest.mark.parametrize("base_url", [
    "/tor-metrics",
    "/tor-metrics/",
    "https://metrics.example.com",
    "https://example.com/tor-metrics",
    "http://metrics.example.com",
])
def test_supported_base_urls_stay_on_the_configured_host(base_url):
    """Subdirectory prefixes and absolute URLs do not become //host links."""
    href = _vanity_href(base_url)
    assert not href.startswith("//")
    assert href.startswith(base_url)


def test_validate_url_arguments_rejects_root_slash_base_url(capsys):
    """Prevent //domain links from a root slash base URL."""
    module = _load_allium_cli_module()
    args = argparse.Namespace(base_url="/")

    with pytest.raises(SystemExit) as exc_info:
        module.validate_url_arguments(args)

    assert exc_info.value.code == 1
    captured = capsys.readouterr().out
    assert "--base-url cannot be '/'" in captured
    assert "Omit --base-url" in captured


@pytest.mark.parametrize("base_url", [" /", "/ ", "\t/\n", " / ", "\\", "\\\t"])
def test_validate_url_arguments_rejects_whitespace_around_root_slash(base_url, capsys):
    """Whitespace, or a backslash a browser treats as a slash, is still '/'."""
    module = _load_allium_cli_module()
    args = argparse.Namespace(base_url=base_url)

    with pytest.raises(SystemExit) as exc_info:
        module.validate_url_arguments(args)

    assert exc_info.value.code == 1
    assert "--base-url cannot be '/'" in capsys.readouterr().out


@pytest.mark.parametrize("base_url", [
    "",
    "/tor-metrics",
    "/tor-metrics/",
    "/metrics",
    "https://metrics.example.com",
    "https://example.com/tor-metrics",
    "http://metrics.example.com",
])
def test_validate_url_arguments_allows_supported_base_urls(base_url):
    """Empty, subdirectory, and absolute base URLs remain valid."""
    module = _load_allium_cli_module()
    module.validate_url_arguments(argparse.Namespace(base_url=base_url))


def test_validate_url_arguments_allows_omitted_base_url():
    """The default site-root invocation does not pass base_url at all."""
    module = _load_allium_cli_module()
    module.validate_url_arguments(argparse.Namespace())


def test_validate_url_arguments_rejects_scheme_relative_base_url(capsys):
    """Scheme-relative URLs must be rejected."""
    module = _load_allium_cli_module()
    args = argparse.Namespace(base_url="//evil.example/path")

    with pytest.raises(SystemExit) as exc_info:
        module.validate_url_arguments(args)

    assert exc_info.value.code == 1
    captured = capsys.readouterr().out
    assert "must use http:// or https:// scheme" in captured
    assert "--base-url cannot be '/'" not in captured


@pytest.mark.parametrize("base_url", [
    "///",
    "//",
    "file:///tmp/site",
    " /tor-metrics",
    "/\\",
    "/\t/evil.example",
    "/\n/evil.example",
    "/\r/evil.example",
])
def test_validate_url_arguments_still_rejects_other_unsafe_base_urls(base_url, capsys):
    """Other unsafe values keep the existing scheme error."""
    module = _load_allium_cli_module()
    args = argparse.Namespace(base_url=base_url)

    with pytest.raises(SystemExit) as exc_info:
        module.validate_url_arguments(args)

    assert exc_info.value.code == 1
    captured = capsys.readouterr().out
    assert "must use http:// or https:// scheme" in captured
    assert "--base-url cannot be '/'" not in captured


def test_other_url_flags_still_reject_a_root_slash(capsys):
    """The slash exception is only for --base-url."""
    module = _load_allium_cli_module()
    args = argparse.Namespace(
        base_url="",
        onionoo_details_url="/",
    )

    with pytest.raises(SystemExit) as exc_info:
        module.validate_url_arguments(args)

    assert exc_info.value.code == 1
    assert "--onionoo-details-url must use http:// or https:// scheme" in capsys.readouterr().out


def _run_cli(args):
    return subprocess.run(
        [sys.executable, "allium.py"] + args,
        cwd=str(ALLIUM_DIR),
        capture_output=True,
        text=True,
        timeout=25,
    )


def test_cli_help_documents_bare_slash_rejection():
    result = _run_cli(["--help"])
    assert result.returncode == 0, result.stderr
    assert 'A bare "/" is rejected' in result.stdout
    assert "site-root output" in result.stdout


def test_cli_rejects_bare_slash_before_generating(tmp_path):
    """The real parser exits before Onionoo or page generation."""
    marker = tmp_path / "generated"
    result = _run_cli(["--base-url", "/", "--out", str(marker)])
    assert result.returncode == 1, result.stdout + result.stderr
    assert "--base-url cannot be '/'" in result.stdout
    assert not marker.exists()


def test_cli_rejects_whitespace_bare_slash(tmp_path):
    result = _run_cli(["--base-url", " / ", "--out", str(tmp_path / "www")])
    assert result.returncode == 1, result.stdout + result.stderr
    assert "--base-url cannot be '/'" in result.stdout
    assert not (tmp_path / "www").exists()
