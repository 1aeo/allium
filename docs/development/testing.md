# Testing Guide

**Audience**: Contributors  
**Scope**: Test suite layout, `pytest.ini` defaults, and testing conventions

## Running Tests

`pytest.ini` sets `testpaths = tests`, `pythonpath = .`, `-m "not slow"`, and `--timeout=30` (`--timeout-method=thread`) by default.

```bash
# Default suite (excludes tests marked 'slow')
pytest

# Include slow tests (override default -m "not slow")
pytest -m ""

# With coverage
pytest --cov=allium --cov-report=html

# Specific file
pytest tests/unit/test_seo.py

# Specific test
pytest tests/unit/coordinator/test_coordinator.py::TestRelayCount::test_relay_count

# Verbose
pytest -v
```

## Test Organization

Tests are organized by scope and subsystem under `tests/`:

```
tests/
├── conftest.py                 # Shared pytest fixtures (e.g., jinja_env)
├── unit/                       # Fast unit tests (no external network)
│   ├── aroi/                   # AROI validation and leaderboard tests
│   ├── charts/                 # History and pressure chart tests
│   ├── consensus/              # Consensus evaluation and authority tests
│   ├── coordinator/            # Coordinator orchestration tests
│   ├── exit_dns_health/        # Exit DNS health and resolver tests
│   ├── infrastructure/         # CLI validation, cache fallback, infra tests
│   ├── relays/                 # Relay processing, sorting, overload tests
│   ├── templates/              # Template rendering, escaping, search index tests
│   ├── uptime/                 # Uptime utilities and percentile tests
│   ├── workers/                # API workers, timeouts, retries, caching tests
│   └── test_*.py               # Cross-cutting unit tests (SEO, metrics, etc.)
├── integration/                # Multi-component integration tests
├── regression/                 # Bug-fix regression tests
├── system/                     # System/E2E tests (may require real network)
├── fixtures/                   # Canned JSON fixtures (e.g., fixtures/ci/)
└── helpers/                    # Shared test helpers and fixture builders
```

## Naming Conventions

### Files

Place test modules under the matching directory using `test_<component>.py`:

- `tests/unit/coordinator/test_coordinator.py`
- `tests/integration/test_full_workflow.py`
- `tests/regression/test_allium_entrypoint.py`
- `tests/system/test_real_api.py`

### Functions

```python
def test_component_action_expected_outcome(self):
```

Examples:
- `test_coordinator_initialization_sets_all_parameters_correctly`
- `test_route_for_html_uses_clean_public_routes`
- `test_contact_precomputation_stores_required_metadata`

## Writing Tests

### Basic Structure

```python
from allium.lib.ip_utils import safe_parse_ip_address


class TestIpUtils:
    """Tests for IP address parsing."""

    def test_valid_ipv4_with_port(self):
        ip, version = safe_parse_ip_address("192.0.2.1:9001")
        assert (ip, version) == ("192.0.2.1", 4)

    def test_invalid_input_returns_none(self):
        assert safe_parse_ip_address(None) == (None, None)
```

### Using Fixtures

```python
import pytest


@pytest.fixture
def sample_relay_data():
    return {
        "fingerprint": "ABC123",
        "nickname": "TestRelay",
        "observed_bandwidth": 1000000,
    }


def test_with_fixture(sample_relay_data):
    assert sample_relay_data["nickname"] == "TestRelay"
```

## Test Categories

Markers defined in `pytest.ini`: `unit`, `integration`, `regression`, `system`, `slow`.

| Directory / Marker | Purpose | Speed | External Dependencies |
|--------------------|---------|-------|----------------------|
| `tests/unit/` (`unit`) | Single module or helper | Fast | None |
| `tests/integration/` (`integration`) | Multiple components | Medium | None (unless marked `slow`) |
| `tests/regression/` (`regression`) | Bug-fix guards | Fast | None |
| `tests/system/` (`system`, `slow`) | End-to-end checks | Slow | May use real APIs |

## Output Comparison (Full-Site Regression Testing)

For changes that affect generated HTML, charts, or archive parsing, use `compare_outputs.py` to classify every file in the ~22k-file site (`identical`, `timestamp-only`, or `content diff`). See the **Output Comparison (Major Changes)** section in [CONTRIBUTING.md](../../CONTRIBUTING.md#output-comparison-major-changes) for the full baseline/candidate workflow and pressure-history cache instructions.

## CI Integration

Tests run automatically on PR via GitHub Actions (`.github/workflows/ci.yml`), executing `python -m pytest tests/ -v --cov=. --cov-report=xml -m "not slow"` alongside `flake8` and template checks.

## How to Verify

```bash
# Run default test suite
pytest

# Check collected test count
pytest --collect-only | tail -1
```
