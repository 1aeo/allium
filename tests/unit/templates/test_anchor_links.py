#!/usr/bin/env python3
"""
Test suite for anchor link functionality in relay-info.html.
Uses parametrized tests for better efficiency and cleaner output.
"""

import re
import pytest
from pathlib import Path


# List of required anchor IDs used across multiple tests
# These must have both id="..." and href="#..." in the template
REQUIRED_ANCHORS = [
    'ipv4-exit-policy-summary',
    'ipv6-exit-policy-summary', 
    'exit-policy',
]

# Backward-compatible anchors (id= only, no href= link — kept for external URL compatibility)
COMPAT_ANCHORS = [
    'effective-family',
    'alleged-family',
    'indirect-family',
]

# Required CSS classes
REQUIRED_CSS_CLASSES = ['section-header', 'anchor-link']


@pytest.fixture(scope="module")
def template_content():
    """Load template content once for all tests in this module."""
    # Go up from tests/unit/templates/ to project root
    template_path = Path(__file__).parent.parent.parent.parent / "allium" / "templates" / "relay-info.html"
    with open(template_path, 'r') as f:
        return f.read()


class TestAnchorLinks:
    """Test suite for anchor link functionality in relay-info.html"""
    
    @pytest.mark.parametrize("anchor", REQUIRED_ANCHORS)
    def test_anchor_id_present(self, template_content, anchor):
        """Test that anchor ID is present in the template"""
        assert f'id="{anchor}"' in template_content, f"Missing anchor ID: {anchor}"
    
    @pytest.mark.parametrize("anchor", REQUIRED_ANCHORS)
    def test_anchor_link_present(self, template_content, anchor):
        """Test that anchor link is present in the template"""
        assert f'href="#{anchor}"' in template_content, f"Missing anchor link: {anchor}"
    
    def test_anchor_structure(self, template_content):
        """Test that anchor links have the correct HTML structure"""
        # Look for section header structure
        section_header_pattern = r'<div class="section-header">'
        matches = re.findall(section_header_pattern, template_content)
        assert len(matches) >= 6, "Missing section header divs for anchor links"

    @pytest.mark.parametrize("anchor", COMPAT_ANCHORS)
    def test_compat_anchor_id_present(self, template_content, anchor):
        """Test that backward-compatible anchor IDs exist (for external URL compatibility)"""
        assert f'id="{anchor}"' in template_content, f"Missing compat anchor ID: {anchor}"

    @pytest.mark.parametrize("css_class", REQUIRED_CSS_CLASSES)
    def test_css_classes_present(self, template_content, css_class):
        """Test that required CSS classes are present"""
        assert (f'class="{css_class}"' in template_content or 
                f'class="{css_class} ' in template_content), f"Missing CSS class: {css_class}"

    def test_css_target_highlighting(self, template_content):
        """Test that CSS target highlighting is present"""
        target_css = ':target {'
        assert target_css in template_content, "Missing CSS target highlighting"
        
        # Check for highlight properties
        assert 'background-color:' in template_content, "Missing background color for target highlighting"
    
    def test_anchor_accessibility(self, template_content):
        """Test that anchor links are accessible"""
        # Anchor links should still be accessible via direct clicks
        anchor_link_pattern = r'<a href="#[^"]*" class="anchor-link"[^>]*>'
        matches = re.findall(anchor_link_pattern, template_content)
        assert len(matches) >= 6, "Missing accessible anchor links"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
