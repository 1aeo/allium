#!/usr/bin/env python3
"""
Test suite for anchor link functionality in relay-info.html.
Uses parametrized tests for better efficiency and cleaner output.
"""

import re
import time
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
        """Test that CSS target highlighting is present in relay-info page CSS"""
        # CSS was extracted to external file in Phase 5
        css_path = Path(__file__).parent.parent.parent.parent / "allium" / "static" / "css" / "relay-info.css"
        assert css_path.exists(), f"External CSS file missing: {css_path}"
        css_content = css_path.read_text()
        
        target_css = ':target {'
        assert target_css in css_content, "Missing CSS target highlighting"
        
        # Check for highlight properties
        assert 'background-color:' in css_content, "Missing background color for target highlighting"
    
    def test_anchor_accessibility(self, template_content):
        """Test that anchor links are accessible"""
        # Anchor links should still be accessible via direct clicks
        anchor_link_pattern = r'<a href="#[^"]*" class="anchor-link"[^>]*>'
        matches = re.findall(anchor_link_pattern, template_content)
        assert len(matches) >= 6, "Missing accessible anchor links"


class TestIssueSectionLinks:
    """Issues Detected entries must hyperlink to the section with more details."""

    def test_issue_titles_are_links(self, template_content):
        """Real issues render their title as an in-page anchor link."""
        assert 'class="issue-link"' in template_content
        assert 'href="#{{ issue.section|default(\'status\') }}"' in template_content

    def test_description_link_html_rendered_by_template(self, template_content):
        """The view (not the data layer) builds the in-description anchor HTML."""
        assert 'issue.description_link' in template_content
        assert 'href="#{{ issue.description_link.target }}"' in template_content
        # Descriptions are plain text across all issue types; only
        # description_link carries the target for the view to render
        import time as _time
        from allium.lib.relay_diagnostics import generate_issues_from_consensus

        SECONDS_PER_DAY = 86400
        issues = generate_issues_from_consensus({
            'in_consensus': False,
            'vote_count': 2, 'total_authorities': 9,
            'authority_votes': [{'voted': True, 'flags': ['StaleDesc'],
                                 'wfu': 0.5, 'tk': 3600}],
            'reachability': {'ipv4_reachable_count': 2,
                             'ipv4_reachable_authorities': ['bastet', 'dannenberg'],
                             'ipv6_reachable_count': 0, 'ipv6_tested_count': 8,
                             'ipv6_not_tested_authorities': []},
            'flag_eligibility': {'stable': {'eligible_count': 0}},
            'bandwidth': {'deviation': 5000, 'median': 100,
                          'bw_auth_measured_count': 1, 'bw_auth_total': 6},
        }, current_flags=['BadExit', 'MiddleOnly'], observed_bandwidth=100_000,
            version='0.4.7.0', recommended_version=False)
        assert issues
        for issue in issues:
            assert '<a ' not in issue['description'], issue['title']

    def test_note_titles_are_links(self, template_content):
        """Info notes render their title as an in-page anchor link."""
        assert 'href="#{{ note.section|default(\'status\') }}"' in template_content

    def test_issue_link_css_defined(self):
        css_path = Path(__file__).parent.parent.parent.parent / "allium" / "static" / "css" / "relay-info.css"
        assert css_path.exists(), "External CSS file missing: relay-info.css"
        css_content = css_path.read_text()
        assert '.issue-link {' in css_content, "Missing .issue-link CSS rule"

    def test_all_diagnostic_sections_have_template_anchors(self, template_content):
        """Every `section` value relay_diagnostics produces must resolve to an
        id in relay-info.html so issue hyperlinks never point at a missing anchor."""
        from allium.lib.relay_diagnostics import generate_relay_issues

        SECONDS_PER_DAY = 86400
        now_ms = int(time.time() * 1000)
        consensus_data = {
            'in_consensus': False,
            'vote_count': 2,
            'total_authorities': 9,
            'authority_votes': [
                {'voted': True, 'flags': ['StaleDesc', 'Running'],
                 'wfu': 0.90, 'tk': 3 * SECONDS_PER_DAY},
            ],
            'reachability': {
                'ipv4_reachable_count': 3,
                'ipv4_reachable_authorities': ['bastet', 'dannenberg', 'dizum'],
                'ipv6_reachable_count': 0,
                'ipv6_not_tested_authorities': ['moria1'],
            },
            'flag_eligibility': {'stable': {'eligible_count': 2}},
            'bandwidth': {'deviation': 10000, 'median': 5000,
                          'bw_auth_measured_count': 1, 'bw_auth_total': 6},
        }
        relay = {
            'flags': ['BadExit', 'MiddleOnly'],
            'observed_bandwidth': 1_000_000,
            'version': '0.4.8.10',
            'recommended_version': False,
            'overload_general_timestamp': now_ms - 3600000,
            'overload_fd_exhausted': {'timestamp': now_ms},
            'overload_ratelimits': {'rate-limit': 1_000_000, 'burst-limit': 2_000_000,
                                    'write-count': 1, 'read-count': 1},
        }
        from allium.lib.consensus.consensus_evaluation import FLAG_ROW_ANCHORS

        issues = generate_relay_issues(relay, consensus_data)
        assert len(issues) >= 10  # fixture should trigger many issue types
        sections = {i['section'] for i in issues}
        assert 'flag-running-ipv4' in sections
        assert 'col-cons-wt' in sections
        assert 'overload-general' in sections
        assert 'id="{{ row.anchor }}"' in template_content
        for section in sections:
            if section.startswith('flag-'):
                assert section in set(FLAG_ROW_ANCHORS.values()), section
            else:
                assert f'id="{section}"' in template_content, \
                    f"Issue section anchor missing from template: {section}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
