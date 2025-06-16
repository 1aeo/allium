#!/usr/bin/env python3

import re
import pytest
from pathlib import Path

class TestAnchorLinks:
    """Test suite for anchor link functionality in relay-info.html"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.template_path = Path(__file__).parent.parent / "allium" / "templates" / "relay-info.html"
        with open(self.template_path, 'r') as f:
            self.template_content = f.read()
    
    def test_anchor_links_present(self):
        """Test that all required anchor links are present in the template"""
        required_anchors = [
            'ipv4-exit-policy-summary',
            'ipv6-exit-policy-summary', 
            'exit-policy',
            'effective-family',
            'alleged-family',
            'indirect-family'
        ]
        
        for anchor in required_anchors:
            # Check for anchor ID
            assert f'id="{anchor}"' in self.template_content, f"Missing anchor ID: {anchor}"
            
            # Check for anchor link
            assert f'href="#{anchor}"' in self.template_content, f"Missing anchor link: {anchor}"
    
    def test_anchor_structure(self):
        """Test that anchor links have the correct HTML structure"""
        # Look for section header structure
        section_header_pattern = r'<div class="section-header">'
        matches = re.findall(section_header_pattern, self.template_content)
        assert len(matches) >= 6, "Missing section header divs for anchor links"
        

        

    
    def test_css_classes_present(self):
        """Test that required CSS classes are present"""
        required_classes = [
            'section-header',
            'anchor-link'
        ]
        
        for css_class in required_classes:
            assert f'class="{css_class}"' in self.template_content or f'class="{css_class} ' in self.template_content, f"Missing CSS class: {css_class}"
    

    
    def test_css_target_highlighting(self):
        """Test that CSS target highlighting is present"""
        target_css = ':target {'
        assert target_css in self.template_content, "Missing CSS target highlighting"
        
        # Check for highlight properties
        assert 'background-color:' in self.template_content, "Missing background color for target highlighting"
    
    def test_anchor_accessibility(self):
        """Test that anchor links are accessible"""
        # Anchor links should still be accessible via direct clicks
        anchor_link_pattern = r'<a href="#[^"]*" class="anchor-link"[^>]*>'
        matches = re.findall(anchor_link_pattern, self.template_content)
        assert len(matches) >= 6, "Missing accessible anchor links"
        


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 