"""
Tests for CLI URL argument validation in allium.py.
"""

import argparse
import importlib.util
import os
import sys

import pytest


def _load_allium_cli_module():
    """Load allium/allium.py as a module for direct function testing."""
    project_root = os.path.join(os.path.dirname(__file__), "..", "..", "..")
    allium_dir = os.path.join(project_root, "allium")
    allium_cli = os.path.join(allium_dir, "allium.py")

    if allium_dir not in sys.path:
        sys.path.insert(0, allium_dir)

    spec = importlib.util.spec_from_file_location("allium_cli_module", allium_cli)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_validate_url_arguments_rejects_root_slash_base_url(capsys):
    """Prevent //domain links from a root slash base URL."""
    module = _load_allium_cli_module()
    args = argparse.Namespace(base_url="/")

    with pytest.raises(SystemExit) as exc_info:
        module.validate_url_arguments(args)

    assert exc_info.value.code == 1
    assert "--base-url cannot be '/'" in capsys.readouterr().out


def test_validate_url_arguments_allows_root_relative_subpath():
    """Subpath hosting must continue to be supported."""
    module = _load_allium_cli_module()
    args = argparse.Namespace(base_url="/tor-metrics")

    module.validate_url_arguments(args)


def test_validate_url_arguments_rejects_scheme_relative_base_url():
    """Scheme-relative URLs must be rejected."""
    module = _load_allium_cli_module()
    args = argparse.Namespace(base_url="//evil.example/path")

    with pytest.raises(SystemExit) as exc_info:
        module.validate_url_arguments(args)

    assert exc_info.value.code == 1
