# Template Optimization Architecture

## Overview

This document describes the template optimization pattern implemented in Allium, specifically focusing on the migration of complex logic from Jinja2 templates to Python backend code for improved performance, testability, and maintainability.

## Problem Statement

### Original Challenge
- **Complex template logic**: Jinja2 templates contained extensive computational logic
- **Performance bottlenecks**: Template rendering became slow with complex calculations
- **Testing difficulties**: Logic embedded in templates was hard to unit test
- **Code maintainability**: Business logic scattered between Python and template files
- **Debugging complexity**: Template errors were harder to trace and fix

### Specific Example: Contact Pages
The contact detail pages originally performed complex calculations directly in Jinja2:
- Bandwidth breakdown filtering and formatting
- Consensus weight percentage calculations
- Operator intelligence color coding
- Statistical outliers computation
- Uptime highlighting with floating-point precision handling

## Solution Architecture

### Pattern: Pre-Computed Display Data

#### Core Principle
Move computational logic from templates to Python backend, providing templates with pre-formatted, display-ready data.

```python
# Before: Complex template logic
{% if relays.json.smart_context and relays.json.smart_context.contact_intelligence %}
    {% set contact_intel = relays.json.smart_context.contact_intelligence.template_optimized[contact_hash] %}
    {% if 'Poor' in contact_intel.portfolio_diversity %}
        <span style="color: #c82333; font-weight: bold;">Poor</span>
    {% elif 'Okay' in contact_intel.portfolio_diversity %}
        <span style="color: #cc9900; font-weight: bold;">Okay</span>
    {% endif %}
{% endif %}

# After: Pre-computed display data
{{ intelligence.network_diversity|safe }}  # Already formatted with colors
```

#### Implementation Structure

```python
def _compute_contact_display_data(self, relay_data, bandwidth_unit, reliability, contact_hash, members):
    """
    Pre-compute all display-specific data for contact pages.
    
    Returns:
        dict: Ready-to-display data with formatting and calculations complete
    """
    display_data = {}
    
    # 1. Bandwidth breakdown with zero-value filtering
    display_data['bandwidth_breakdown'] = self._format_bandwidth_breakdown(relay_data, bandwidth_unit)
    
    # 2. Consensus weight breakdown with percentage formatting  
    display_data['consensus_weight_breakdown'] = self._format_consensus_breakdown(relay_data)
    
    # 3. Operator intelligence with color coding
    display_data['operator_intelligence'] = self._format_intelligence_data(contact_hash)
    
    # 4. Uptime formatting with highlighting logic
    display_data['uptime_formatted'] = self._format_uptime_display(reliability)
    
    # 5. Statistical outliers with tooltip generation
    display_data['outliers'] = self._compute_outliers_display(reliability)
    
    return display_data
```

### Architecture Benefits

#### 1. Performance Improvements
- **Reduced template complexity**: Templates focus purely on presentation
- **Faster rendering**: Complex calculations done once in Python vs. repeatedly in template
- **Better caching potential**: Pre-computed data can be cached more effectively

#### 2. Enhanced Testability
```python
def test_bandwidth_breakdown_formatting(self):
    """Test bandwidth breakdown with zero-value filtering."""
    result = self.relays._compute_contact_display_data(test_data, 'MB/s', None, 'hash', [])
    self.assertIn('50.0 MB/s guard', result['bandwidth_breakdown'])
    self.assertNotIn('0.00 MB/s middle', result['bandwidth_breakdown'])  # Filtered out
```

#### 3. Improved Maintainability
- **Single responsibility**: Templates handle presentation, Python handles logic
- **Easier debugging**: Python stack traces vs. template error messages
- **Code reusability**: Display logic can be shared across different templates

#### 4. Better Error Handling
```python
def _format_intelligence_rating(self, rating_text):
    """Format intelligence ratings with proper error handling."""
    if not rating_text or ', ' not in rating_text:
        return rating_text  # Graceful degradation
    
    try:
        rating, details = rating_text.split(', ', 1)
        return self._apply_color_coding(rating, details)
    except Exception as e:
        logger.warning(f"Intelligence rating formatting failed: {e}")
        return rating_text  # Fallback to original
```

## Implementation Guidelines

### 1. Data Flow Pattern

```
Raw Data → Python Processing → Display Data → Template Rendering → HTML Output
    ↓              ↓                ↓              ↓              ↓
Relay JSON → _compute_display_data() → Formatted Dict → Jinja2 → Final Page
```

### 2. Naming Conventions

- **Method naming**: `_compute_{section}_display_data()`
- **Data structure**: `{section}_display_data` in template context
- **Helper methods**: `_format_{specific_data_type}()`

### 3. Template Integration

```python
# In template rendering code
contact_display_data = self._compute_contact_display_data(
    relay_data, bandwidth_unit, reliability, contact_hash, members
)

# Pass to template
template.render(
    # ... other context ...
    contact_display_data=contact_display_data
)
```

```html
<!-- In template -->
{% if contact_display_data.bandwidth_breakdown %}
    <span title="Bandwidth breakdown">{{ contact_display_data.bandwidth_breakdown }}</span>
{% endif %}
```

### 4. Error Handling Strategy

- **Graceful degradation**: Always provide fallback values
- **Logging**: Log warnings for data processing issues
- **Validation**: Validate input data before processing
- **Safe defaults**: Return empty or default values rather than raising exceptions

## Testing Strategy

### Unit Testing
```python
class TestContactDisplayData(unittest.TestCase):
    def test_bandwidth_breakdown_with_mixed_types(self):
        """Test bandwidth breakdown with guard, middle, and exit relays."""
        
    def test_zero_value_filtering(self):
        """Test that zero values are properly filtered from display."""
        
    def test_uptime_highlighting_thresholds(self):
        """Test uptime highlighting for various percentage values."""
```

### Integration Testing
```python  
class TestTemplateIntegration(unittest.TestCase):
    def test_template_renders_with_display_data(self):
        """Test that template renders correctly with pre-computed data."""
        
    def test_template_handles_missing_display_data(self):
        """Test graceful handling when display data is unavailable."""
```

### Regression Testing
```python
class TestDataIntegrityRegression(unittest.TestCase):
    def test_calculations_match_original_logic(self):
        """Verify refactored calculations match original template logic."""
```

## Migration Checklist

When applying this pattern to new templates:

- [ ] **Identify complex template logic** - Look for calculations, conditionals, formatting
- [ ] **Create display data method** - Implement `_compute_{section}_display_data()`
- [ ] **Add comprehensive tests** - Unit tests for all logic paths
- [ ] **Update template** - Replace logic with pre-computed data usage
- [ ] **Add error handling** - Graceful degradation for edge cases
- [ ] **Verify data integrity** - Regression tests to ensure calculations unchanged
- [ ] **Performance testing** - Measure improvement vs. original implementation

## Best Practices

### Do's ✅
- **Pre-compute all complex formatting** in Python
- **Use helper methods** for specific data transformations
- **Implement comprehensive error handling** with fallbacks
- **Write extensive unit tests** for display logic
- **Document data structures** passed to templates
- **Use safe template filters** (`|safe`) only for pre-validated HTML

### Don'ts ❌
- **Don't mix business logic in templates** - Keep templates purely presentational
- **Don't skip error handling** - Always provide graceful degradation
- **Don't forget regression tests** - Verify calculations remain identical
- **Don't ignore performance** - Measure and optimize display data computation
- **Don't break template abstraction** - Keep display data structure clean and documented

## Future Considerations

### Potential Extensions
1. **Caching layer**: Cache pre-computed display data for repeated requests
2. **Async processing**: Move heavy calculations to background tasks
3. **Template compilation**: Pre-compile templates with display data schemas
4. **Data validation**: JSON schema validation for display data structures

### Monitoring and Metrics
- **Template rendering time**: Before vs. after optimization
- **Memory usage**: Display data structure size and memory impact  
- **Error rates**: Track display data computation failures
- **Cache hit rates**: If caching is implemented

## Conclusion

The template optimization pattern successfully addresses performance, testability, and maintainability challenges by separating computational logic from presentation logic. This architectural approach has proven effective for the contact page refactoring and provides a blueprint for future template optimizations throughout the Allium codebase.