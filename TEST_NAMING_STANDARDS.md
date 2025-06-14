# Test Naming Standards

## Overview
This document outlines the standardized naming convention for all unit tests in the Allium project.

## Naming Convention

All test functions should follow this format:
```
test_[component]_[action]_[expected_outcome]_[additional_context]
```

### Components of the Name

1. **component**: The main component being tested (e.g., `coordinator`, `worker_status`, `cache_file`, `reliability_score`)
2. **action**: What action is being performed (e.g., `initialization`, `save_and_load`, `calculation`, `filtering`)
3. **expected_outcome**: What should happen (e.g., `succeeds`, `fails`, `returns_none`, `raises_error`)
4. **additional_context**: Optional context about the conditions (e.g., `when_api_call_fails`, `with_empty_data`, `gracefully`)

## Examples

### Before (Inconsistent)
```python
def test_coordinator_initialization(self):
def test_save_and_load_cache(self):
def test_reliability_masters_category_exists(self):
def test_empty_uptime_data_handling(self):
```

### After (Standardized)
```python
def test_coordinator_initialization_sets_all_parameters_correctly(self):
def test_cache_file_save_and_load_preserves_data_integrity(self):
def test_reliability_masters_category_definition_includes_required_properties(self):
def test_empty_uptime_data_returns_zero_scores_with_default_values(self):
```

## Benefits

1. **Clarity**: Tests clearly state what they're testing and what the expected outcome is
2. **Consistency**: All tests follow the same naming pattern
3. **Searchability**: Easy to find tests related to specific components or outcomes
4. **Self-Documentation**: Test names serve as documentation of expected behavior

## Pattern Categories

### Component Tests
- `test_[component]_initialization_[outcome]_[context]`
- `test_[component]_configuration_[outcome]_[context]`

### Functionality Tests  
- `test_[component]_[action]_[outcome]_[context]`
- `test_[component]_[action]_handles_[error_case]_gracefully`

### Data Processing Tests
- `test_[component]_[processing_action]_[outcome]_[data_context]`
- `test_[component]_validation_[outcome]_[input_context]`

### Integration Tests
- `test_[system]_[workflow]_[outcome]_[integration_context]`
- `test_[component]_integration_[outcome]_[system_context]`

### Error Handling Tests
- `test_[component]_[action]_handles_[error_type]_gracefully`
- `test_[component]_[action]_returns_[fallback]_when_[error_condition]`

## File Organization

Each test file should be organized into logical test classes:

```python
class TestComponentCore:
    """Test core functionality of the component"""
    
class TestComponentErrorHandling:
    """Test error handling and edge cases"""
    
class TestComponentIntegration:
    """Test integration with other components"""
```

## Implementation Status

### ✅ Completed Files
- `tests/test_basic.py` - Basic infrastructure tests
- `tests/test_reliability_scoring.py` - Reliability scoring system tests
- `tests/test_workers.py` - Worker system tests (partial)
- `tests/test_coordinator.py` - Coordinator system tests (partial)

### 🔄 In Progress
- `tests/test_integration.py` - Integration flow tests
- `tests/test_cache_state.py` - Cache and state management tests
- `tests/test_integration_real.py` - Real API integration tests

### 📋 Guidelines for New Tests

1. Always use the standardized naming format
2. Include comprehensive docstrings explaining the test purpose
3. Group related tests into logical test classes
4. Use descriptive variable names that match the test context
5. Include clear assertions with meaningful error messages

This standard ensures our test suite is maintainable, discoverable, and self-documenting. 