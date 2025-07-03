"""
Basic tests for allium project
"""
import sys
import os
import pytest
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError

# Add the allium directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'allium'))


def test_jinja2_dependency_import_succeeds_without_errors():
    """Test that Jinja2 can be imported successfully"""
    from jinja2 import Environment
    assert Environment is not None


def test_templates_directory_exists_at_expected_path():
    """Test that the templates directory exists"""
    template_dir = os.path.join(os.path.dirname(__file__), '..', 'allium', 'templates')
    assert os.path.exists(template_dir), f"Template directory not found: {template_dir}"


def test_all_jinja2_templates_have_valid_syntax_without_errors():
    """Validate that all Jinja2 templates have correct syntax"""
    template_dir = os.path.join(os.path.dirname(__file__), '..', 'allium', 'templates')
    
    if not os.path.exists(template_dir):
        pytest.skip("Template directory not found")
    
    env = Environment(loader=FileSystemLoader(template_dir))
    
    # Add custom filters for template compatibility
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'allium'))
    from allium.lib.relays import determine_unit_filter, format_bandwidth_with_unit, format_bandwidth_filter, format_time_ago
    env.filters['determine_unit'] = determine_unit_filter
    env.filters['format_bandwidth_with_unit'] = format_bandwidth_with_unit
    env.filters['format_bandwidth'] = format_bandwidth_filter
    env.filters['format_time_ago'] = format_time_ago
    
    template_files = []
    for root, dirs, files in os.walk(template_dir):
        for file in files:
            if file.endswith('.html'):
                template_path = os.path.relpath(os.path.join(root, file), template_dir)
                template_files.append(template_path)
    
    assert len(template_files) > 0, "No template files found"
    
    for template_path in template_files:
        try:
            template = env.get_template(template_path)
            assert template is not None, f"Template {template_path} failed to load"
        except TemplateSyntaxError as e:
            pytest.fail(f"Template {template_path} has syntax error: {e}")


def test_main_allium_script_file_exists_at_expected_location():
    """Test that the main allium.py file exists"""
    allium_file = os.path.join(os.path.dirname(__file__), '..', 'allium', 'allium.py')
    assert os.path.exists(allium_file), "Main allium.py file not found"


def test_aroileaders_module_import_succeeds_with_expected_functions():
    """Test that aroileaders module can be imported (if available)"""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'allium', 'lib'))
        import allium.lib.aroileaders as aroileaders
        # If import succeeds, test that it has expected attributes
        assert hasattr(aroileaders, '_calculate_aroi_leaderboards') or hasattr(aroileaders, 'calculate_aroi_leaderboards'), \
            "aroileaders module missing expected functions"
    except ImportError:
        # This is acceptable in CI environment
        pytest.skip("aroileaders module not available (acceptable in CI)")


def test_requirements_file_exists_and_contains_required_dependencies():
    """Test that requirements.txt exists and has content"""
    req_file = os.path.join(os.path.dirname(__file__), '..', 'config', 'requirements.txt')
    assert os.path.exists(req_file), "requirements.txt not found in config directory"
    
    with open(req_file, 'r') as f:
        content = f.read().strip()
        assert 'Jinja2' in content, "Jinja2 dependency not found in requirements.txt"


if __name__ == "__main__":
    pytest.main([__file__]) 