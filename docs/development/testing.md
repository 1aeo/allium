# Testing Guide

**Audience**: Contributors  
**Scope**: Running tests and conventions

## Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=allium --cov-report=html

# Specific file
pytest tests/test_utils.py

# Specific test
pytest tests/test_utils.py::TestClassName::test_method

# Verbose
pytest -v
```

## Test Organization

All tests are in `tests/` (flat structure):

```
tests/
├── test_unit_*.py          # Unit tests
├── test_integration_*.py   # Integration tests
├── test_system_*.py        # System tests (may use real APIs)
├── test_regression_*.py    # Regression tests
└── test_*.py               # Other tests
```

## Naming Conventions

### Files

```
test_[type]_[component].py
```

Examples:
- `test_unit_coordinator.py`
- `test_integration_full_workflow.py`
- `test_system_real_api.py`

### Functions

```python
def test_component_action_expected_outcome(self):
```

Examples:
- `test_coordinator_initialization_succeeds`
- `test_cache_save_preserves_data`
- `test_empty_input_returns_default`

## Writing Tests

### Basic Structure

```python
import pytest
from allium.lib.module import function_to_test

class TestComponentName:
    """Tests for ComponentName"""
    
    def test_basic_functionality(self):
        result = function_to_test(input)
        assert result == expected
    
    def test_edge_case_handling(self):
        result = function_to_test(None)
        assert result == default_value
```

### Using Fixtures

```python
@pytest.fixture
def sample_relay_data():
    return {
        'fingerprint': 'ABC123',
        'nickname': 'TestRelay',
        'bandwidth': 1000000
    }

def test_with_fixture(sample_relay_data):
    result = process_relay(sample_relay_data)
    assert result['nickname'] == 'TestRelay'
```

## Test Categories

| Prefix | Purpose | Speed | External Dependencies |
|--------|---------|-------|----------------------|
| `test_unit_` | Single component | Fast | None |
| `test_integration_` | Multiple components | Medium | None |
| `test_system_` | Full system | Slow | May use real APIs |
| `test_regression_` | Bug fixes | Varies | None |

## CI Integration

Tests run automatically on PR via GitHub Actions. See `.github/workflows/ci.yml`.

Required for merge:
- All tests pass
- No linting errors (`flake8`)
- No security issues (`bandit`)

## How to Verify

```bash
# Run full test suite
pytest

# Check test count
pytest --collect-only | tail -1
```
