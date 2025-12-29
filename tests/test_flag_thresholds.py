"""
Tests for flag_thresholds.py

Tests the centralized module for Tor relay flag threshold constants and eligibility logic.
These tests help ensure flag threshold logic matches Tor's dir-spec.
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'allium', 'lib'))

from consensus.flag_thresholds import (
    # Constants
    SECONDS_PER_DAY,
    GUARD_BW_GUARANTEE,
    GUARD_TK_DEFAULT,
    GUARD_WFU_DEFAULT,
    HSDIR_TK_DEFAULT,
    HSDIR_WFU_DEFAULT,
    FAST_BW_GUARANTEE,
    FLAG_ORDER,
    FLAG_ORDER_MAP,
    # Functions
    parse_wfu_threshold,
    format_time_as_days,
    format_wfu_as_percent,
    check_guard_eligibility,
    check_hsdir_eligibility,
    check_fast_eligibility,
    check_stable_eligibility,
    get_flag_thresholds_summary,
    sort_flags,
)


class TestConstants:
    """Tests for flag threshold constants."""
    
    def test_seconds_per_day(self):
        """Test SECONDS_PER_DAY is correct."""
        assert SECONDS_PER_DAY == 86400
        assert SECONDS_PER_DAY == 24 * 60 * 60
    
    def test_guard_bw_guarantee(self):
        """Test Guard BW guarantee is 2 MB/s."""
        assert GUARD_BW_GUARANTEE == 2_000_000  # 2 MB/s
    
    def test_guard_tk_default(self):
        """Test Guard TK default is 8 days."""
        assert GUARD_TK_DEFAULT == 8 * SECONDS_PER_DAY
        assert GUARD_TK_DEFAULT == 691200
    
    def test_guard_wfu_default(self):
        """Test Guard WFU default is 98%."""
        assert GUARD_WFU_DEFAULT == 0.98
    
    def test_hsdir_tk_default(self):
        """Test HSDir TK default is 25 hours per dir-spec."""
        # Per dir-spec Section 3.4.2, default hsdir-tk is 25 hours
        assert HSDIR_TK_DEFAULT == 25 * 3600  # 25 hours
        assert HSDIR_TK_DEFAULT == 90000
    
    def test_hsdir_wfu_default(self):
        """Test HSDir WFU default is 98%."""
        assert HSDIR_WFU_DEFAULT == 0.98
    
    def test_fast_bw_guarantee(self):
        """Test Fast BW guarantee is 100 KB/s."""
        assert FAST_BW_GUARANTEE == 100_000  # 100 KB/s


class TestParseWfuThreshold:
    """Tests for parse_wfu_threshold function."""
    
    def test_parse_float_fraction(self):
        """Test parsing float fraction."""
        assert parse_wfu_threshold(0.98) == 0.98
        assert parse_wfu_threshold(0.5) == 0.5
        assert parse_wfu_threshold(1.0) == 1.0
    
    def test_parse_string_percent(self):
        """Test parsing string with percent sign."""
        assert parse_wfu_threshold('98%') == 0.98
        assert parse_wfu_threshold('50%') == 0.5
        assert parse_wfu_threshold('100%') == 1.0
    
    def test_parse_string_fraction(self):
        """Test parsing string fraction."""
        assert parse_wfu_threshold('0.98') == 0.98
        assert parse_wfu_threshold('0.5') == 0.5
    
    def test_parse_integer(self):
        """Test parsing integer."""
        assert parse_wfu_threshold(1) == 1.0
        assert parse_wfu_threshold(0) == 0.0
    
    def test_parse_none(self):
        """Test parsing None returns None."""
        assert parse_wfu_threshold(None) is None
    
    def test_parse_invalid_string(self):
        """Test parsing invalid string returns None."""
        assert parse_wfu_threshold('invalid') is None
        assert parse_wfu_threshold('abc%') is None


class TestFormatTimeAsDays:
    """Tests for format_time_as_days function."""
    
    def test_format_one_day(self):
        """Test formatting one day."""
        assert format_time_as_days(SECONDS_PER_DAY) == '1.0d'
    
    def test_format_eight_days(self):
        """Test formatting eight days."""
        assert format_time_as_days(8 * SECONDS_PER_DAY) == '8.0d'
    
    def test_format_fractional_days(self):
        """Test formatting fractional days."""
        assert format_time_as_days(1.5 * SECONDS_PER_DAY) == '1.5d'
    
    def test_format_none(self):
        """Test formatting None returns N/A."""
        assert format_time_as_days(None) == 'N/A'
    
    def test_format_custom_decimals(self):
        """Test formatting with custom decimals."""
        assert format_time_as_days(1.234 * SECONDS_PER_DAY, decimals=2) == '1.23d'


class TestFormatWfuAsPercent:
    """Tests for format_wfu_as_percent function."""
    
    def test_format_98_percent(self):
        """Test formatting 0.98 as 98.0%."""
        assert format_wfu_as_percent(0.98) == '98.0%'
    
    def test_format_100_percent(self):
        """Test formatting 1.0 as 100.0%."""
        assert format_wfu_as_percent(1.0) == '100.0%'
    
    def test_format_50_percent(self):
        """Test formatting 0.5 as 50.0%."""
        assert format_wfu_as_percent(0.5) == '50.0%'
    
    def test_format_none(self):
        """Test formatting None returns N/A."""
        assert format_wfu_as_percent(None) == 'N/A'
    
    def test_format_custom_decimals(self):
        """Test formatting with custom decimals."""
        assert format_wfu_as_percent(0.98765, decimals=2) == '98.77%'


class TestCheckGuardEligibility:
    """Tests for check_guard_eligibility function."""
    
    def test_eligible_relay(self):
        """Test a relay that meets all Guard requirements."""
        result = check_guard_eligibility(
            wfu=0.99,
            tk=10 * SECONDS_PER_DAY,
            bandwidth=3_000_000,  # 3 MB/s, above 2 MB/s guarantee
        )
        
        assert result['eligible'] == True
        assert result['wfu_met'] == True
        assert result['tk_met'] == True
        assert result['bw_meets_guarantee'] == True
        assert result['bw_eligible'] == True
    
    def test_ineligible_low_wfu(self):
        """Test a relay with low WFU."""
        result = check_guard_eligibility(
            wfu=0.90,  # Below 98%
            tk=10 * SECONDS_PER_DAY,
            bandwidth=3_000_000,
        )
        
        assert result['eligible'] == False
        assert result['wfu_met'] == False
    
    def test_ineligible_low_tk(self):
        """Test a relay with low time-known."""
        result = check_guard_eligibility(
            wfu=0.99,
            tk=5 * SECONDS_PER_DAY,  # Below 8 days
            bandwidth=3_000_000,
        )
        
        assert result['eligible'] == False
        assert result['tk_met'] == False
    
    def test_ineligible_low_bandwidth(self):
        """Test a relay with low bandwidth."""
        result = check_guard_eligibility(
            wfu=0.99,
            tk=10 * SECONDS_PER_DAY,
            bandwidth=1_000_000,  # 1 MB/s, below 2 MB/s guarantee
        )
        
        assert result['eligible'] == False
        assert result['bw_meets_guarantee'] == False
    
    def test_eligible_via_top25(self):
        """Test a relay eligible via top 25% threshold."""
        result = check_guard_eligibility(
            wfu=0.99,
            tk=10 * SECONDS_PER_DAY,
            bandwidth=1_500_000,  # 1.5 MB/s, below guarantee but in top 25%
            bw_top25_threshold=1_000_000,  # Top 25% is 1 MB/s
        )
        
        assert result['eligible'] == True
        assert result['bw_meets_guarantee'] == False
        assert result['bw_in_top25'] == True
        assert result['bw_eligible'] == True


class TestCheckHsdirEligibility:
    """Tests for check_hsdir_eligibility function."""
    
    def test_eligible_relay(self):
        """Test a relay that meets HSDir requirements (above 25 hour default)."""
        result = check_hsdir_eligibility(
            wfu=0.99,
            tk=30 * 3600,  # 30 hours, above 25 hour default
        )
        
        assert result['eligible'] == True
        assert result['wfu_met'] == True
        assert result['tk_met'] == True
    
    def test_ineligible_low_wfu(self):
        """Test a relay with low WFU."""
        result = check_hsdir_eligibility(
            wfu=0.90,
            tk=12 * SECONDS_PER_DAY,
        )
        
        assert result['eligible'] == False
        assert result['wfu_met'] == False
    
    def test_ineligible_low_tk(self):
        """Test a relay with low time-known (below 25 hour default)."""
        result = check_hsdir_eligibility(
            wfu=0.99,
            tk=20 * 3600,  # 20 hours, below 25 hour default
        )
        
        assert result['eligible'] == False
        assert result['tk_met'] == False


class TestCheckFastEligibility:
    """Tests for check_fast_eligibility function."""
    
    def test_eligible_via_guarantee(self):
        """Test a relay eligible via 100 KB/s guarantee."""
        result = check_fast_eligibility(bandwidth=150_000)
        
        assert result['eligible'] == True
        assert result['meets_guarantee'] == True
    
    def test_eligible_via_threshold(self):
        """Test a relay eligible via fast threshold."""
        result = check_fast_eligibility(
            bandwidth=80_000,  # Below 100 KB/s guarantee
            fast_threshold=50_000,  # But above this threshold
        )
        
        assert result['eligible'] == True
        assert result['meets_guarantee'] == False
        assert result['meets_threshold'] == True
    
    def test_ineligible_below_all(self):
        """Test a relay ineligible due to low bandwidth."""
        result = check_fast_eligibility(
            bandwidth=50_000,  # Below 100 KB/s
            fast_threshold=100_000,  # Also below threshold
        )
        
        assert result['eligible'] == False
        assert result['meets_guarantee'] == False
        assert result['meets_threshold'] == False


class TestCheckStableEligibility:
    """Tests for check_stable_eligibility function."""
    
    def test_eligible_via_uptime(self):
        """Test a relay eligible via uptime threshold."""
        result = check_stable_eligibility(
            uptime=100_000,
            mtbf=0,
            uptime_threshold=50_000,
            mtbf_threshold=100_000,
        )
        
        assert result['eligible'] == True
        assert result['uptime_met'] == True
        assert result['mtbf_met'] == False
    
    def test_eligible_via_mtbf(self):
        """Test a relay eligible via MTBF threshold."""
        result = check_stable_eligibility(
            uptime=0,
            mtbf=100_000,
            uptime_threshold=100_000,
            mtbf_threshold=50_000,
        )
        
        assert result['eligible'] == True
        assert result['uptime_met'] == False
        assert result['mtbf_met'] == True
    
    def test_ineligible(self):
        """Test a relay ineligible for Stable."""
        result = check_stable_eligibility(
            uptime=10_000,
            mtbf=10_000,
            uptime_threshold=50_000,
            mtbf_threshold=50_000,
        )
        
        assert result['eligible'] == False
        assert result['uptime_met'] == False
        assert result['mtbf_met'] == False


class TestGetFlagThresholdsSummary:
    """Tests for get_flag_thresholds_summary function."""
    
    def test_empty_thresholds(self):
        """Test with empty thresholds uses defaults."""
        result = get_flag_thresholds_summary({})
        
        assert result['guard_wfu'] == GUARD_WFU_DEFAULT
        assert result['guard_tk'] == GUARD_TK_DEFAULT
        assert result['hsdir_wfu'] == HSDIR_WFU_DEFAULT
        assert result['hsdir_tk'] == HSDIR_TK_DEFAULT
    
    def test_custom_thresholds(self):
        """Test with custom thresholds."""
        thresholds = {
            'guard-wfu': '95%',
            'guard-tk': 500000,
            'guard-bw-inc-exits': 3000000,
            'stable-uptime': 100000,
            'fast-speed': 200000,
        }
        
        result = get_flag_thresholds_summary(thresholds)
        
        assert result['guard_wfu'] == 0.95
        assert result['guard_tk'] == 500000
        assert result['guard_bw_inc_exits'] == 3000000
        assert result['stable_uptime'] == 100000
        assert result['fast_speed'] == 200000


class TestSortFlags:
    """Tests for sort_flags function."""
    
    def test_empty_list(self):
        """Test sorting empty list."""
        assert sort_flags([]) == []
    
    def test_single_flag(self):
        """Test sorting single flag."""
        assert sort_flags(['Running']) == ['Running']
    
    def test_authority_first(self):
        """Test Authority flag comes first."""
        flags = ['Running', 'Authority', 'Valid']
        result = sort_flags(flags)
        assert result[0] == 'Authority'
    
    def test_canonical_order(self):
        """Test flags are sorted in canonical order."""
        flags = ['Valid', 'Guard', 'Exit', 'Fast', 'Running']
        result = sort_flags(flags)
        
        # Exit should come before Fast, Guard after Fast
        assert result.index('Exit') < result.index('Fast')
        assert result.index('Fast') < result.index('Guard')
        assert result.index('Guard') < result.index('Running')
        assert result.index('Running') < result.index('Valid')
    
    def test_unknown_flags_sorted_last(self):
        """Test unknown flags are sorted alphabetically at end."""
        flags = ['Running', 'UnknownFlag', 'Valid']
        result = sort_flags(flags)
        
        # UnknownFlag should come after Running and Valid
        assert result.index('Running') < result.index('Valid')
        assert result.index('Valid') < result.index('UnknownFlag')


class TestFlagOrderMap:
    """Tests for FLAG_ORDER_MAP constant."""
    
    def test_authority_is_first(self):
        """Test Authority has lowest index."""
        assert FLAG_ORDER_MAP.get('Authority') == 0
    
    def test_all_flags_have_index(self):
        """Test all FLAG_ORDER flags have an index."""
        for flag in FLAG_ORDER:
            assert flag in FLAG_ORDER_MAP
    
    def test_indices_are_sequential(self):
        """Test indices are sequential from 0."""
        expected = list(range(len(FLAG_ORDER)))
        actual = [FLAG_ORDER_MAP[f] for f in FLAG_ORDER]
        assert actual == expected


class TestGuardEligibilityEdgeCases:
    """Edge case tests for Guard eligibility checking."""
    
    def test_exactly_at_wfu_threshold(self):
        """Test relay exactly at 98% WFU threshold."""
        result = check_guard_eligibility(
            wfu=0.98,  # Exactly at threshold
            tk=10 * SECONDS_PER_DAY,
            bandwidth=3_000_000,
        )
        
        assert result['wfu_met'] == True
        assert result['eligible'] == True
    
    def test_exactly_at_tk_threshold(self):
        """Test relay exactly at 8 days TK threshold."""
        result = check_guard_eligibility(
            wfu=0.99,
            tk=8 * SECONDS_PER_DAY,  # Exactly at threshold
            bandwidth=3_000_000,
        )
        
        assert result['tk_met'] == True
        assert result['eligible'] == True
    
    def test_exactly_at_bw_guarantee(self):
        """Test relay exactly at 2 MB/s BW threshold."""
        result = check_guard_eligibility(
            wfu=0.99,
            tk=10 * SECONDS_PER_DAY,
            bandwidth=2_000_000,  # Exactly at threshold
        )
        
        assert result['bw_meets_guarantee'] == True
        assert result['eligible'] == True
    
    def test_just_below_wfu_threshold(self):
        """Test relay just below 98% WFU threshold."""
        result = check_guard_eligibility(
            wfu=0.9799,  # Just below
            tk=10 * SECONDS_PER_DAY,
            bandwidth=3_000_000,
        )
        
        assert result['wfu_met'] == False
        assert result['eligible'] == False
    
    def test_just_below_tk_threshold(self):
        """Test relay just below 8 days TK threshold."""
        result = check_guard_eligibility(
            wfu=0.99,
            tk=8 * SECONDS_PER_DAY - 1,  # 1 second below
            bandwidth=3_000_000,
        )
        
        assert result['tk_met'] == False
        assert result['eligible'] == False
    
    def test_just_below_bw_guarantee(self):
        """Test relay just below 2 MB/s BW threshold."""
        result = check_guard_eligibility(
            wfu=0.99,
            tk=10 * SECONDS_PER_DAY,
            bandwidth=1_999_999,  # Just below
        )
        
        assert result['bw_meets_guarantee'] == False
    
    def test_zero_values(self):
        """Test with all zero values."""
        result = check_guard_eligibility(
            wfu=0,
            tk=0,
            bandwidth=0,
        )
        
        assert result['eligible'] == False
        assert result['wfu_met'] == False
        assert result['tk_met'] == False
        assert result['bw_eligible'] == False
    
    def test_none_values_treated_as_zero(self):
        """Test that None values are handled as zero."""
        result = check_guard_eligibility(
            wfu=None,
            tk=None,
            bandwidth=None,
        )
        
        assert result['eligible'] == False
        assert result['wfu_value'] == 0
        assert result['tk_value'] == 0
        assert result['bw_value'] == 0
    
    def test_custom_thresholds(self):
        """Test with custom authority thresholds."""
        result = check_guard_eligibility(
            wfu=0.95,
            tk=5 * SECONDS_PER_DAY,
            bandwidth=1_500_000,
            wfu_threshold=0.95,  # Lower threshold
            tk_threshold=5 * SECONDS_PER_DAY,  # Lower threshold
            bw_top25_threshold=1_000_000,  # Low top25 threshold
        )
        
        assert result['wfu_met'] == True
        assert result['tk_met'] == True
        assert result['bw_in_top25'] == True
        assert result['eligible'] == True


class TestHsdirEligibilityEdgeCases:
    """Edge case tests for HSDir eligibility checking."""
    
    def test_exactly_at_hsdir_tk_default(self):
        """Test relay exactly at 25 hour HSDir TK threshold."""
        result = check_hsdir_eligibility(
            wfu=0.99,
            tk=25 * 3600,  # Exactly 25 hours (dir-spec default)
        )
        
        assert result['tk_met'] == True
        assert result['eligible'] == True
    
    def test_just_below_hsdir_tk_default(self):
        """Test relay just below 25 hour HSDir TK threshold."""
        result = check_hsdir_eligibility(
            wfu=0.99,
            tk=25 * 3600 - 1,  # 1 second below
        )
        
        assert result['tk_met'] == False
        assert result['eligible'] == False
    
    def test_moria1_hsdir_tk_threshold(self):
        """Test relay meeting moria1's stricter ~10 day HSDir TK threshold."""
        # moria1 uses approximately 10 days (848498 seconds)
        moria1_tk = 848498
        result = check_hsdir_eligibility(
            wfu=0.99,
            tk=moria1_tk,
            tk_threshold=moria1_tk,  # Use moria1's threshold
        )
        
        assert result['tk_met'] == True
        assert result['eligible'] == True
    
    def test_between_default_and_moria1(self):
        """Test relay between 25 hours and 10 days."""
        result = check_hsdir_eligibility(
            wfu=0.99,
            tk=5 * SECONDS_PER_DAY,  # 5 days
        )
        
        # Should meet default 25 hour threshold
        assert result['tk_met'] == True
        assert result['eligible'] == True


class TestFastEligibilityEdgeCases:
    """Edge case tests for Fast eligibility checking."""
    
    def test_exactly_at_fast_guarantee(self):
        """Test relay exactly at 100 KB/s Fast threshold."""
        result = check_fast_eligibility(
            bandwidth=100_000,  # Exactly 100 KB/s
        )
        
        assert result['meets_guarantee'] == True
        assert result['eligible'] == True
    
    def test_just_below_fast_guarantee(self):
        """Test relay just below 100 KB/s Fast threshold."""
        result = check_fast_eligibility(
            bandwidth=99_999,  # Just below
            fast_threshold=0,  # No dynamic threshold
        )
        
        assert result['meets_guarantee'] == False
        assert result['eligible'] == False
    
    def test_zero_bandwidth(self):
        """Test relay with zero bandwidth."""
        result = check_fast_eligibility(bandwidth=0)
        
        assert result['meets_guarantee'] == False
        assert result['eligible'] == False


class TestStableEligibilityEdgeCases:
    """Edge case tests for Stable eligibility checking."""
    
    def test_both_thresholds_met(self):
        """Test relay meeting both uptime and MTBF thresholds."""
        result = check_stable_eligibility(
            uptime=100_000,
            mtbf=100_000,
            uptime_threshold=50_000,
            mtbf_threshold=50_000,
        )
        
        assert result['uptime_met'] == True
        assert result['mtbf_met'] == True
        assert result['eligible'] == True
    
    def test_neither_threshold_met(self):
        """Test relay meeting neither threshold."""
        result = check_stable_eligibility(
            uptime=10_000,
            mtbf=10_000,
            uptime_threshold=50_000,
            mtbf_threshold=50_000,
        )
        
        assert result['uptime_met'] == False
        assert result['mtbf_met'] == False
        assert result['eligible'] == False
    
    def test_zero_thresholds(self):
        """Test with zero thresholds (none required)."""
        result = check_stable_eligibility(
            uptime=0,
            mtbf=0,
            uptime_threshold=0,
            mtbf_threshold=0,
        )
        
        # With zero thresholds, nothing is "met"
        assert result['uptime_met'] == False
        assert result['mtbf_met'] == False
        assert result['eligible'] == False


class TestParseWfuEdgeCases:
    """Edge case tests for WFU parsing."""
    
    def test_parse_zero_percent(self):
        """Test parsing 0%."""
        assert parse_wfu_threshold('0%') == 0.0
    
    def test_parse_100_percent(self):
        """Test parsing 100%."""
        assert parse_wfu_threshold('100%') == 1.0
    
    def test_parse_fractional_percent(self):
        """Test parsing fractional percentage."""
        assert parse_wfu_threshold('98.5%') == 0.985
    
    def test_parse_string_with_whitespace(self):
        """Test parsing string with whitespace."""
        assert parse_wfu_threshold('  0.98  ') == 0.98
        assert parse_wfu_threshold('  98%  ') == 0.98
    
    def test_parse_empty_string(self):
        """Test parsing empty string."""
        assert parse_wfu_threshold('') is None
    
    def test_parse_negative_value(self):
        """Test parsing negative value (invalid but shouldn't crash)."""
        result = parse_wfu_threshold(-0.5)
        assert result == -0.5  # Returns the value even if invalid


class TestFormatFunctions:
    """Tests for formatting functions."""
    
    def test_format_time_as_days_zero(self):
        """Test formatting zero seconds."""
        assert format_time_as_days(0) == '0.0d'
    
    def test_format_time_as_days_hours(self):
        """Test formatting 25 hours."""
        assert format_time_as_days(25 * 3600) == '1.0d'  # 25h rounds to 1.0d
    
    def test_format_time_as_days_very_large(self):
        """Test formatting very large time (1 year)."""
        result = format_time_as_days(365 * SECONDS_PER_DAY)
        assert result == '365.0d'
    
    def test_format_wfu_as_percent_zero(self):
        """Test formatting zero WFU."""
        assert format_wfu_as_percent(0) == '0.0%'
    
    def test_format_wfu_as_percent_edge_values(self):
        """Test formatting edge WFU values."""
        assert format_wfu_as_percent(0.001) == '0.1%'
        assert format_wfu_as_percent(0.999) == '99.9%'


class TestGetFlagThresholdsSummaryComprehensive:
    """Comprehensive tests for get_flag_thresholds_summary."""
    
    def test_all_fields_present(self):
        """Test that all expected fields are present."""
        result = get_flag_thresholds_summary({})
        
        expected_fields = [
            'guard_wfu', 'guard_tk', 'guard_bw_inc_exits',
            'hsdir_wfu', 'hsdir_tk',
            'stable_uptime', 'stable_mtbf',
            'fast_speed',
            'enough_mtbf', 'min_bw_fr',
        ]
        
        for field in expected_fields:
            assert field in result, f"Missing field: {field}"
    
    def test_wfu_percentage_conversion(self):
        """Test that percentage WFU values are converted."""
        thresholds = {'guard-wfu': '95%', 'hsdir-wfu': '96%'}
        result = get_flag_thresholds_summary(thresholds)
        
        assert result['guard_wfu'] == 0.95
        assert result['hsdir_wfu'] == 0.96
    
    def test_default_fallback_for_missing(self):
        """Test that missing values use defaults."""
        result = get_flag_thresholds_summary({})
        
        assert result['guard_wfu'] == GUARD_WFU_DEFAULT
        assert result['guard_tk'] == GUARD_TK_DEFAULT
        assert result['hsdir_wfu'] == HSDIR_WFU_DEFAULT
        assert result['hsdir_tk'] == HSDIR_TK_DEFAULT


class TestTimeConstants:
    """Tests for time constants accuracy."""
    
    def test_seconds_per_week(self):
        """Test SECONDS_PER_WEEK is correct."""
        from consensus.flag_thresholds import SECONDS_PER_WEEK
        assert SECONDS_PER_WEEK == 7 * 24 * 60 * 60
        assert SECONDS_PER_WEEK == 604800
    
    def test_seconds_per_hour(self):
        """Test SECONDS_PER_HOUR is correct."""
        from consensus.flag_thresholds import SECONDS_PER_HOUR
        assert SECONDS_PER_HOUR == 60 * 60
        assert SECONDS_PER_HOUR == 3600
    
    def test_seconds_per_minute(self):
        """Test SECONDS_PER_MINUTE is correct."""
        from consensus.flag_thresholds import SECONDS_PER_MINUTE
        assert SECONDS_PER_MINUTE == 60
