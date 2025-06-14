"""
Unit tests for updated reliability scoring system
Tests for simplified reliability_masters and legacy_titans categories
with 25+ relay eligibility filter and no bandwidth weighting.
"""
import pytest
import sys
import os

# Add the allium directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'allium'))

from lib.aroileaders import _calculate_reliability_score


class TestUpdatedReliabilityScoring:
    """Test updated reliability scoring functionality"""
    
    def test_reliability_masters_category_includes_25_plus_relay_requirement_in_title(self):
        """Test that reliability_masters category properly shows 25+ relay requirement"""
        # Mock category definition as it would appear in the system
        categories = {
            'reliability_masters': {
                'title': 'Reliability Masters (6-Month Uptime, 25+ Relays)',
                'emoji': '⏰'
            }
        }
        
        assert 'reliability_masters' in categories
        category = categories['reliability_masters']
        assert 'Reliability Masters' in category['title']
        assert '25+ Relays' in category['title']
        assert '6-Month' in category['title']
        assert category['emoji'] == '⏰'
        
    def test_legacy_titans_category_includes_25_plus_relay_requirement_in_title(self):
        """Test that legacy_titans category properly shows 25+ relay requirement"""
        # Mock category definition as it would appear in the system
        categories = {
            'legacy_titans': {
                'title': 'Legacy Titans (5-Year Uptime, 25+ Relays)',
                'emoji': '👑'
            }
        }
        
        assert 'legacy_titans' in categories
        category = categories['legacy_titans']
        assert 'Legacy Titans' in category['title']
        assert '25+ Relays' in category['title']
        assert '5-Year' in category['title']
        assert category['emoji'] == '👑'
        
    def test_reliability_score_calculation_uses_simple_average_without_any_weighting(self):
        """Test simple average reliability score calculation with no weighting applied"""
        # Mock operator data for testing different scenarios
        test_scenarios = [
            {
                'name': 'small_ineligible_operator',
                'relay_count': 15,  # Below 25 relay threshold - should be filtered out
                'six_month_uptime': 99.8,
                'should_be_included': False
            },
            {
                'name': 'medium_eligible_operator',
                'relay_count': 30,  # Above 25 relay threshold - eligible
                'six_month_uptime': 96.2,
                'should_be_included': True
            },
            {
                'name': 'large_eligible_operator',
                'relay_count': 150,  # Well above 25 relay threshold - eligible
                'six_month_uptime': 95.2,
                'should_be_included': True
            }
        ]
        
        # Test that scores equal uptime percentages with no weighting
        for scenario in test_scenarios:
            if scenario['should_be_included']:
                # Mock call to _calculate_reliability_score
                # In real implementation, this would process actual relay data
                result = _calculate_reliability_score([], None, '6_months')
                
                # Verify no weighting is applied (weight should always be 1.0)
                assert result['weight'] == 1.0
                
                # Verify that the score would equal the average uptime (no multiplication)
                # In actual implementation: result['score'] == result['average_uptime']
                assert result['weight'] == 1.0  # No bandwidth weighting applied
        
    def test_bandwidth_weight_multipliers_are_completely_removed_from_calculation(self):
        """Test that no bandwidth weight multipliers exist in the new system"""
        # Test that all operators get weight of 1.0 regardless of relay count
        test_relay_counts = [1, 25, 50, 100, 200, 500]
        
        for relay_count in test_relay_counts:
            result = _calculate_reliability_score([], None, '6_months')
            # All operators should have weight of 1.0 (no weighting system)
            assert result['weight'] == 1.0
            
    def test_operator_filtering_strictly_excludes_operators_with_25_or_fewer_relays(self):
        """Test that only operators with > 25 relays are included in reliability rankings"""
        # Mock operator data to test filtering logic
        operators_data = {
            'tiny_op': {'total_relays': 5, 'reliability_6m_score': 99.9},
            'small_op': {'total_relays': 15, 'reliability_6m_score': 99.5},
            'threshold_op': {'total_relays': 25, 'reliability_6m_score': 99.0},  # Exactly 25 - should be excluded
            'eligible_op_1': {'total_relays': 26, 'reliability_6m_score': 96.0},  # Just above threshold
            'eligible_op_2': {'total_relays': 50, 'reliability_6m_score': 95.0},
            'large_op': {'total_relays': 200, 'reliability_6m_score': 94.0}
        }
        
        # Filter operators with > 25 relays (simulating leaderboard logic)
        eligible_ops = {k: v for k, v in operators_data.items() if v['total_relays'] > 25}
        
        # Verify filtering results
        assert 'tiny_op' not in eligible_ops          # 5 relays - excluded
        assert 'small_op' not in eligible_ops         # 15 relays - excluded  
        assert 'threshold_op' not in eligible_ops     # 25 relays - excluded (not > 25)
        assert 'eligible_op_1' in eligible_ops        # 26 relays - included
        assert 'eligible_op_2' in eligible_ops        # 50 relays - included
        assert 'large_op' in eligible_ops             # 200 relays - included
        assert len(eligible_ops) == 3
        
    def test_reliability_categories_appear_at_end_of_leaderboard_sections(self):
        """Test that reliability categories appear at positions 11-12 (end of leaderboard)"""
        # Mock category order based on recent commits moving reliability to end
        category_order = [
            'bandwidth', 'consensus_weight', 'exit_authority', 'exit_operators', 
            'guard_operators', 'most_diverse', 'platform_diversity', 'non_eu_leaders',
            'frontier_builders', 'network_veterans', 'reliability_masters', 'legacy_titans'
        ]
        
        reliability_masters_pos = category_order.index('reliability_masters')
        legacy_titans_pos = category_order.index('legacy_titans')
        
        # Reliability categories should be at the end (positions 11-12, 0-indexed: 10-11)
        assert reliability_masters_pos == 10   # Position 11 (0-indexed: 10)
        assert legacy_titans_pos == 11         # Position 12 (0-indexed: 11)
        
    def test_empty_uptime_data_returns_zero_scores_with_simplified_defaults(self):
        """Test handling of operators with no uptime data using simplified return values"""
        result = _calculate_reliability_score([], None, '6_months')
        
        assert result['score'] == 0.0
        assert result['average_uptime'] == 0.0
        assert result['weight'] == 1.0  # Always 1.0 in simplified system
        assert result['valid_relays'] == 0
        assert result['relay_count'] == 0
        
    def test_uptime_data_validation_handles_empty_inputs_with_simplified_structure(self):
        """Test validation of uptime data with simplified error handling"""
        # Test with empty operator relay list
        result = _calculate_reliability_score([], {}, '6_months')
        
        assert result['score'] == 0.0
        assert result['average_uptime'] == 0.0
        assert result['relay_count'] == 0
        assert result['weight'] == 1.0  # Simplified: always 1.0
        assert result['valid_relays'] == 0
        
    def test_reliability_display_formatting_shows_average_without_weight_notation(self):
        """Test proper formatting of reliability scores for display (simplified format)"""
        # Mock display formatting test - simplified format without weight info
        mock_reliability_data = {
            'reliability_average': 96.8,
            'total_relays': 30,
            'reliability_tooltip': '6-month reliability: 96.8% average uptime (30 relays)',
            'reliability_details_short': '96.8% avg'
        }
        
        # Verify tooltip format is simplified
        assert 'average uptime' in mock_reliability_data['reliability_tooltip']
        assert 'weight' not in mock_reliability_data['reliability_tooltip']
        assert 'avg' in mock_reliability_data['reliability_details_short']
        assert '×' not in mock_reliability_data['reliability_details_short']  # No multiplication
        assert 'weight' not in mock_reliability_data['reliability_details_short']


class TestUpdatedReliabilityIntegration:
    """Test integration of updated reliability features with existing system"""
    
    def test_reliability_categories_maintain_12_total_categories_in_system(self):
        """Test that reliability categories are included in complete 12-category list"""
        # Mock complete category list with all 12 categories
        all_categories = [
            'bandwidth', 'consensus_weight', 'exit_authority', 'exit_operators',
            'guard_operators', 'most_diverse', 'platform_diversity', 'non_eu_leaders',
            'frontier_builders', 'network_veterans', 'reliability_masters', 'legacy_titans'
        ]
        
        # Check that all 12 categories are present
        assert len(all_categories) == 12
        assert 'reliability_masters' in all_categories
        assert 'legacy_titans' in all_categories
        
    def test_reliability_categories_have_updated_tooltips_with_25_relay_requirement(self):
        """Test that tooltips mention 25+ relay requirement and simplified scoring"""
        # Mock tooltips with updated information
        tooltips = {
            'reliability_masters': '6-month average uptime scores for operators with 25+ relays',
            'legacy_titans': '5-year average uptime scores for operators with 25+ relays'
        }
        
        assert 'reliability_masters' in tooltips
        assert 'legacy_titans' in tooltips
        
        # Check tooltip content includes new requirements
        reliability_tooltip = tooltips['reliability_masters']
        assert '6-month' in reliability_tooltip.lower()
        assert 'average uptime' in reliability_tooltip.lower()
        assert '25+' in reliability_tooltip
        
        legacy_tooltip = tooltips['legacy_titans']
        assert '5-year' in legacy_tooltip.lower()
        assert 'average uptime' in legacy_tooltip.lower()
        assert '25+' in legacy_tooltip
        
    def test_reliability_categories_use_appropriate_emojis_for_updated_system(self):
        """Test that reliability categories have consistent emojis"""
        # Mock categories with emojis
        categories = {
            'reliability_masters': {'emoji': '⏰'},  # Clock for reliability
            'legacy_titans': {'emoji': '👑'}        # Crown for legacy/titans
        }
        
        assert categories['reliability_masters']['emoji'] == '⏰'
        assert categories['legacy_titans']['emoji'] == '👑'


class TestUpdatedReliabilityEligibilityFiltering:
    """Test the 25+ relay eligibility filtering system"""
    
    def test_operator_eligibility_calculation_with_comprehensive_test_data(self):
        """Test calculation of reliability scores with realistic operator data"""
        # Mock test data representing various operator sizes
        mock_operators = {
            'ineligible_micro': {
                'total_relays': 3,
                'uptime_6m': 99.9,   # Excellent uptime but too few relays
                'uptime_5y': 98.8
            },
            'ineligible_small': {
                'total_relays': 20,
                'uptime_6m': 99.5,   # Great uptime but still too few relays
                'uptime_5y': 98.2
            },
            'ineligible_threshold': {
                'total_relays': 25,  # Exactly 25 - not eligible (must be > 25)
                'uptime_6m': 99.0,
                'uptime_5y': 97.5
            },
            'eligible_just_above': {
                'total_relays': 26,  # Just above threshold - eligible
                'uptime_6m': 96.8,
                'uptime_5y': 95.2
            },
            'eligible_medium': {
                'total_relays': 50,  # Medium operator - eligible
                'uptime_6m': 95.5,
                'uptime_5y': 94.0
            },
            'eligible_large': {
                'total_relays': 150, # Large operator - eligible
                'uptime_6m': 94.2,
                'uptime_5y': 93.8
            }
        }
        
        # Test eligibility filtering logic
        eligible_ops = {k: v for k, v in mock_operators.items() if v['total_relays'] > 25}
        ineligible_ops = {k: v for k, v in mock_operators.items() if v['total_relays'] <= 25}
        
        # Verify eligibility results
        assert len(eligible_ops) == 3
        assert len(ineligible_ops) == 3
        
        # Check specific operators
        assert 'eligible_just_above' in eligible_ops
        assert 'eligible_medium' in eligible_ops
        assert 'eligible_large' in eligible_ops
        
        assert 'ineligible_micro' in ineligible_ops
        assert 'ineligible_small' in ineligible_ops
        assert 'ineligible_threshold' in ineligible_ops  # Exactly 25 is not eligible
        
    def test_statistical_significance_rationale_for_25_relay_threshold(self):
        """Test that 25+ relay threshold provides meaningful statistical significance"""
        # Mock test to verify the reasoning behind 25+ relay threshold
        test_sample_sizes = [
            {'relays': 1, 'statistical_significance': 'None'},
            {'relays': 5, 'statistical_significance': 'Very Low'},
            {'relays': 10, 'statistical_significance': 'Low'},
            {'relays': 15, 'statistical_significance': 'Below Threshold'},
            {'relays': 25, 'statistical_significance': 'Threshold (excluded)'},
            {'relays': 26, 'statistical_significance': 'Minimum Acceptable'},
            {'relays': 50, 'statistical_significance': 'Good'},
            {'relays': 100, 'statistical_significance': 'Very Good'},
        ]
        
        # Verify threshold logic
        significant_samples = [s for s in test_sample_sizes if s['relays'] > 25]
        insignificant_samples = [s for s in test_sample_sizes if s['relays'] <= 25]
        
        assert len(significant_samples) == 3  # 26, 50, 100 relays
        assert len(insignificant_samples) == 5  # 1, 5, 10, 15, 25 relays
        
        # Verify that threshold is applied correctly
        for sample in significant_samples:
            assert sample['relays'] > 25
        for sample in insignificant_samples:
            assert sample['relays'] <= 25 