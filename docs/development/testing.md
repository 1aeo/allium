# Test Naming Standards

## Overview
This document outlines the standardized naming convention for all unit tests in the Allium project, including both test files and test functions.

## Test File Naming Convention

Test files should follow this format:
```
test_[test_type]_[component]_[context].py
```

### Components of Test File Names

1. **test_type**: The type of testing being performed
   - `unit` - Unit tests for individual components
   - `integration` - Integration tests across multiple components  
   - `system` - Full system/end-to-end tests
   - `acceptance` - User acceptance tests

2. **component**: The main component or system being tested
   - `infrastructure` - Basic project setup, dependencies, templates
   - `reliability_scoring` - Reliability masters and legacy titans features
   - `coordinator` - API coordination system
   - `workers` - Worker system for data fetching
   - `cache_state` - Cache and state management
   - `multiapi` - Multi-API system functionality
   - `leaderboards` - AROI leaderboards system

3. **context**: Optional additional context
   - `real_api` - Tests that use real external APIs
   - `mock_data` - Tests using mock/simulated data
   - `performance` - Performance and benchmarking tests
   - `edge_cases` - Edge case and error condition tests
   - `network_health` - Network health dashboard tests

### Test File Examples

#### Current (Inconsistent)
```
test_basic.py                 # Too generic
test_reliability_scoring.py   # Missing test type
test_integration.py           # Missing component context
test_integration_real.py      # Unclear what's being integrated
test_workers.py              # Missing test type
test_coordinator.py          # Missing test type
test_cache_state.py          # Missing test type
test_multiapi_system.py      # Inconsistent format
```

#### Standardized Format
```
test_unit_infrastructure.py           # Basic infrastructure tests
test_unit_reliability_scoring.py      # Reliability scoring unit tests
test_unit_coordinator.py              # Coordinator unit tests
test_unit_workers.py                  # Worker system unit tests
test_unit_cache_state.py              # Cache and state unit tests
test_unit_multiapi.py                 # Multi-API unit tests

test_integration_full_workflow.py     # Full workflow integration tests
test_integration_api_coordination.py  # API coordination integration
test_system_real_api.py               # Full system tests with real APIs
test_integration_mock_data.py         # Integration tests with mock data
```

### Test File Organization Hierarchy

```
tests/
├── unit/                              # Unit test files
│   ├── test_unit_infrastructure.py
│   ├── test_unit_reliability_scoring.py
│   ├── test_unit_coordinator.py
│   ├── test_unit_workers.py
│   ├── test_unit_cache_state.py
│   └── test_unit_multiapi.py
├── integration/                       # Integration test files
│   ├── test_integration_full_workflow.py
│   ├── test_integration_api_coordination.py
│   └── test_integration_mock_data.py
├── system/                           # System test files
│   ├── test_system_real_api.py
│   └── test_system_performance.py
└── acceptance/                       # Acceptance test files
    └── test_acceptance_user_workflows.py
```

## Test Function Naming Convention

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

1. **Clarity**: Both files and tests clearly state what they're testing and what the expected outcome is
2. **Consistency**: All files and tests follow the same naming pattern
3. **Organization**: Clear separation between unit, integration, and system tests
4. **Searchability**: Easy to find files and tests related to specific components or outcomes
5. **Self-Documentation**: File and test names serve as documentation of expected behavior

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

### ✅ Current Files (To Be Renamed)
- `test_basic.py` → `test_unit_infrastructure.py`
- `test_reliability_scoring.py` → `test_unit_reliability_scoring.py` 
- `test_workers.py` → `test_unit_workers.py`
- `test_coordinator.py` → `test_unit_coordinator.py`
- `test_cache_state.py` → `test_unit_cache_state.py`
- `test_multiapi_system.py` → `test_unit_multiapi.py`
- `test_integration.py` → `test_integration_full_workflow.py`
- `test_integration_real.py` → `test_system_real_api.py`

### 🔄 Future Organization
- Create `tests/unit/`, `tests/integration/`, `tests/system/` directories
- Move files to appropriate directories based on test type
- Update import paths in test runner configurations

### 📋 Guidelines for New Test Files

1. Always use the standardized file naming format
2. Place files in the appropriate test type directory
3. Include comprehensive module docstrings explaining the file's purpose
4. Group related test classes logically within each file
5. Use descriptive class and function names that match the conventions
6. Include clear assertions with meaningful error messages

## Migration Plan

### Phase 1: Rename Files (Immediate)
1. Rename existing test files to follow the new convention
2. Update any import references
3. Update pytest configuration if needed

### Phase 2: Reorganize Structure (Future)
1. Create directory structure (`unit/`, `integration/`, `system/`)
2. Move files to appropriate directories
3. Update CI/CD pipeline configurations
4. Update documentation references

This standard ensures our test suite is maintainable, discoverable, and self-documenting at both the file and function level. 