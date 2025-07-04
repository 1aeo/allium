"""
Statistical utilities module to eliminate duplication across the codebase.

This module consolidates statistical calculations that were duplicated across:
- uptime_utils.py (percentile calculations, outlier detection)
- intelligence_engine.py (percentile rank, median calculations)
- Multiple test files (statistical outlier tests)
- relays.py (z-score calculations)
"""

import math
import statistics
import sys
from typing import List, Dict, Any, Optional, Tuple


class StatisticalUtils:
    """
    Centralized statistical calculations to eliminate code duplication.
    
    Consolidates duplicate statistical logic from:
    - calculate_percentile() in uptime_utils.py
    - _calculate_percentile_rank() in intelligence_engine.py
    - _calculate_median() in intelligence_engine.py
    - calculate_statistical_outliers() in uptime_utils.py
    - _calculate_period_statistics() in uptime_utils.py
    """
    
    @staticmethod
    def calculate_percentile(data: List[float], percentile: float) -> float:
        """
        Calculate percentile using numpy-style linear interpolation.
        
        Consolidates the duplicate percentile calculation logic found in uptime_utils.py.
        
        Args:
            data: Sorted list of numeric values
            percentile: Percentile to calculate (0-100)
            
        Returns:
            Calculated percentile value
        """
        if not data:
            return 0.0
        
        n = len(data)
        if n == 1:
            return data[0]
        
        # Use method similar to numpy.percentile with linear interpolation
        k = (n - 1) * (percentile / 100.0)
        f = int(k)
        c = k - f
        
        if f >= n - 1:
            return data[-1]
        
        return data[f] + c * (data[f + 1] - data[f])
    
    @staticmethod
    def calculate_percentiles(data: List[float], percentile_list: List[float] = None) -> Dict[str, float]:
        """
        Calculate multiple percentiles efficiently.
        
        Uses Python 3.8+ statistics.quantiles when available, falls back to manual calculation.
        Consolidates the percentile calculation logic from uptime_utils.py.
        
        Args:
            data: List of numeric values (will be sorted internally)
            percentile_list: List of percentiles to calculate (default: common percentiles)
            
        Returns:
            Dictionary mapping percentile names to values
        """
        if not data:
            return {}
        
        if percentile_list is None:
            percentile_list = [5, 25, 50, 75, 90, 95, 99]
        
        # Sort data for percentile calculations
        sorted_data = sorted(data)
        
        try:
            # Use Python 3.8+ statistics.quantiles when available
            if sys.version_info >= (3, 8):
                quantile_values = statistics.quantiles(sorted_data, n=100, method='inclusive')
                percentiles = {}
                for p in percentile_list:
                    if p == 50:
                        percentiles[f'{p}th'] = statistics.median(sorted_data)
                    else:
                        # Convert percentile to quantile index (1-based to 0-based)
                        idx = max(0, min(98, p - 1))
                        percentiles[f'{p}th'] = quantile_values[idx]
                return percentiles
            else:
                raise ImportError("Using fallback calculation")
        except (ImportError, IndexError):
            # Fallback to manual calculation
            percentiles = {}
            for p in percentile_list:
                percentiles[f'{p}th'] = StatisticalUtils.calculate_percentile(sorted_data, p)
            return percentiles
    
    @staticmethod
    def calculate_percentile_rank(value: float, sorted_data: List[float]) -> float:
        """
        Calculate percentile rank of a value within a dataset.
        
        Consolidates the _calculate_percentile_rank() logic from intelligence_engine.py.
        
        Args:
            value: Value to find percentile rank for
            sorted_data: Sorted list of values to compare against
            
        Returns:
            Percentile rank (0-100)
        """
        if not sorted_data or value == 0:
            return 0.0
        
        below_count = sum(1 for v in sorted_data if v < value)
        percentile = (below_count / len(sorted_data)) * 100
        
        return max(1, min(99, round(percentile)))
    
    @staticmethod
    def calculate_basic_statistics(values: List[float]) -> Optional[Dict[str, float]]:
        """
        Calculate basic statistical measures for a dataset.
        
        Consolidates the _calculate_period_statistics() logic from uptime_utils.py.
        
        Args:
            values: List of numeric values
            
        Returns:
            Dictionary with mean, median, std_dev, variance, min, max, count
        """
        if len(values) < 1:
            return None
        
        try:
            # Calculate basic statistics
            count = len(values)
            mean = statistics.mean(values)
            median = statistics.median(values)
            
            if count > 1:
                std_dev = statistics.stdev(values)
                variance = statistics.variance(values)
            else:
                std_dev = 0.0
                variance = 0.0
            
            return {
                'mean': mean,
                'median': median,
                'std_dev': std_dev,
                'variance': variance,
                'min': min(values),
                'max': max(values),
                'count': count
            }
        except statistics.StatisticsError:
            return None
    
    @staticmethod
    def calculate_outliers(values: List[float], data_mapping: Dict[str, Dict] = None, 
                          std_dev_threshold: float = 2.0) -> Dict[str, List[Dict]]:
        """
        Detect statistical outliers using standard deviation thresholds.
        
        Consolidates the calculate_statistical_outliers() logic from uptime_utils.py.
        
        Args:
            values: List of numeric values
            data_mapping: Optional mapping of identifiers to data dictionaries
            std_dev_threshold: Number of standard deviations for outlier detection
            
        Returns:
            Dictionary with 'low_outliers' and 'high_outliers' lists
        """
        if len(values) < 3:  # Need at least 3 data points for meaningful std dev
            return {'low_outliers': [], 'high_outliers': []}
        
        try:
            mean_value = statistics.mean(values)
            std_dev = statistics.stdev(values)
            
            low_threshold = mean_value - (std_dev_threshold * std_dev)
            high_threshold = mean_value + (std_dev_threshold * std_dev)
            
            low_outliers = []
            high_outliers = []
            
            if data_mapping:
                # Use provided data mapping
                for identifier, data_dict in data_mapping.items():
                    value = data_dict.get('uptime', data_dict.get('value', 0))
                    
                    if value < low_threshold:
                        outlier_data = data_dict.copy()
                        outlier_data['deviation'] = abs(value - mean_value) / std_dev
                        low_outliers.append(outlier_data)
                    elif value > high_threshold:
                        outlier_data = data_dict.copy()
                        outlier_data['deviation'] = abs(value - mean_value) / std_dev
                        high_outliers.append(outlier_data)
            else:
                # Simple value-based outlier detection
                for i, value in enumerate(values):
                    if value < low_threshold:
                        low_outliers.append({
                            'value': value,
                            'index': i,
                            'deviation': abs(value - mean_value) / std_dev
                        })
                    elif value > high_threshold:
                        high_outliers.append({
                            'value': value,
                            'index': i,
                            'deviation': abs(value - mean_value) / std_dev
                        })
            
            return {'low_outliers': low_outliers, 'high_outliers': high_outliers}
            
        except statistics.StatisticsError:
            # Handle case where all values are identical (std dev = 0)
            return {'low_outliers': [], 'high_outliers': []}
    
    @staticmethod
    def calculate_z_score(value: float, mean: float, std_dev: float) -> Optional[float]:
        """
        Calculate z-score (standard score) for a value.
        
        Consolidates z-score calculation logic from relays.py.
        
        Args:
            value: Value to calculate z-score for
            mean: Mean of the distribution
            std_dev: Standard deviation of the distribution
            
        Returns:
            Z-score or None if std_dev is 0
        """
        if std_dev == 0:
            return None
        
        return (value - mean) / std_dev
    
    @staticmethod
    def classify_by_z_score(z_score: Optional[float], 
                           thresholds: Dict[str, float] = None) -> str:
        """
        Classify a value based on its z-score.
        
        Consolidates z-score classification logic from relays.py.
        
        Args:
            z_score: Calculated z-score
            thresholds: Custom thresholds for classification
            
        Returns:
            Classification string
        """
        if z_score is None:
            return 'insufficient_data'
        
        if thresholds is None:
            thresholds = {
                'high_outlier': 2.0,
                'above_average': 0.3,
                'low_outlier': -2.0
            }
        
        if z_score >= thresholds.get('high_outlier', 2.0):
            return 'high_outlier'
        elif z_score >= thresholds.get('above_average', 0.3):
            return 'above_average'
        elif z_score <= thresholds.get('low_outlier', -2.0):
            return 'low_outlier'
        else:
            return 'normal'
    
    @staticmethod
    def calculate_confidence_intervals(values: List[float], confidence_level: float = 0.95) -> Optional[Dict[str, float]]:
        """
        Calculate confidence intervals for a dataset.
        
        Provides additional statistical utility for future enhancements.
        
        Args:
            values: List of numeric values
            confidence_level: Confidence level (0.0-1.0)
            
        Returns:
            Dictionary with lower_bound, upper_bound, margin_of_error
        """
        if len(values) < 2:
            return None
        
        try:
            mean = statistics.mean(values)
            std_dev = statistics.stdev(values)
            n = len(values)
            
            # Use t-distribution for small samples (n < 30) or normal for large samples
            if n < 30:
                # Simplified t-distribution approximation
                t_value = 2.0 if confidence_level >= 0.95 else 1.7
            else:
                # Normal distribution z-scores
                t_value = 1.96 if confidence_level >= 0.95 else 1.64
            
            margin_of_error = t_value * (std_dev / math.sqrt(n))
            
            return {
                'lower_bound': mean - margin_of_error,
                'upper_bound': mean + margin_of_error,
                'margin_of_error': margin_of_error,
                'mean': mean
            }
        except statistics.StatisticsError:
            return None


# Convenience functions for backwards compatibility
def calculate_percentile(data: List[float], percentile: float) -> float:
    """Backwards compatibility wrapper for StatisticalUtils.calculate_percentile"""
    return StatisticalUtils.calculate_percentile(data, percentile)


def calculate_statistical_outliers(values: List[float], data_mapping: Dict[str, Dict] = None, 
                                  std_dev_threshold: float = 2.0) -> Dict[str, List[Dict]]:
    """Backwards compatibility wrapper for StatisticalUtils.calculate_outliers"""
    return StatisticalUtils.calculate_outliers(values, data_mapping, std_dev_threshold)