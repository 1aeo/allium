"""
Flag History Analysis Utilities for Tor Relay Operators

This module provides comprehensive flag history metrics using the Onionoo uptime API
to help relay operators understand their flag performance, stability, and reliability
over different time periods.

Key Metrics:
1. Flag Consistency - How stable are flags over time  
2. Role Performance - Performance analysis per flag/role
3. Flag Transitions - When flags were gained/lost
4. Comparative Analysis - Flag performance vs network averages
5. Flag Stability Score - Overall flag reliability rating
"""

import statistics
from datetime import datetime, timedelta


class FlagHistoryAnalyzer:
    """Analyze flag history and performance for Tor relays"""
    
    # Flag importance weights for stability scoring
    FLAG_WEIGHTS = {
        'Running': 1.0,  # Critical - basic operational status
        'Guard': 0.9,    # High importance - entry point role
        'Exit': 0.9,     # High importance - exit point role
        'Fast': 0.7,     # Medium importance - performance indicator
        'Stable': 0.8,   # High importance - reliability indicator
        'Authority': 1.0, # Critical - directory authority
        'HSDir': 0.6,    # Medium importance - hidden service directory
        'V2Dir': 0.5,    # Lower importance - directory service
        'Valid': 0.9,    # High importance - relay validity
    }
    
    # Flag descriptions for user-friendly display
    FLAG_DESCRIPTIONS = {
        'Running': 'Basic operational status - relay is active and reachable',
        'Guard': 'Entry guard eligibility - can serve as first hop in circuits',
        'Exit': 'Exit node capability - can serve as final hop to internet',
        'Fast': 'High-performance indicator - meets bandwidth thresholds',  
        'Stable': 'Long-term reliability - consistent uptime over time',
        'Authority': 'Directory authority - helps coordinate the network',
        'HSDir': 'Hidden service directory - stores onion service descriptors',
        'V2Dir': 'Directory mirror - serves directory information to clients',
        'Valid': 'Relay validity - passes basic directory authority checks',
    }

    def __init__(self, uptime_data):
        """
        Initialize flag history analyzer with uptime data from Onionoo API
        
        Args:
            uptime_data (dict): Uptime data from Onionoo API
        """
        self.uptime_data = uptime_data

    def analyze_relay_flag_history(self, fingerprint):
        """
        Analyze flag history for a single relay
        
        Args:
            fingerprint (str): Relay fingerprint
            
        Returns:
            dict: Comprehensive flag history analysis
        """
        relay_uptime = self._find_relay_uptime_data(fingerprint)
        if not relay_uptime or not relay_uptime.get('flags'):
            return self._empty_flag_analysis()
        
        analysis = {
            'flag_consistency': self._analyze_flag_consistency(relay_uptime['flags']),
            'role_performance': self._analyze_role_performance(relay_uptime['flags']),
            'flag_stability_score': self._calculate_flag_stability_score(relay_uptime['flags']),
            'comparative_analysis': self._analyze_flag_performance_vs_network(relay_uptime['flags']),
            'flag_timeline': self._reconstruct_flag_timeline(relay_uptime['flags']),
            'reliability_by_role': self._calculate_role_reliability(relay_uptime['flags']),
            'flag_metrics_summary': self._generate_flag_metrics_summary(relay_uptime['flags'])
        }
        
        return analysis

    def analyze_operator_flag_performance(self, operator_relays):
        """
        Analyze flag performance across all relays for an operator
        
        Args:
            operator_relays (list): List of relay objects for the operator
            
        Returns:
            dict: Operator-wide flag performance analysis
        """
        operator_analysis = {
            'overall_flag_stability': 0.0,
            'flag_performance_by_role': {},
            'consistency_metrics': {},
            'reliability_trends': {},
            'problem_relays': [],
            'excellent_performers': [],
            'operator_flag_summary': {}
        }
        
        all_flag_scores = []
        role_performances = {}
        
        for relay in operator_relays:
            fingerprint = relay.get('fingerprint')
            if not fingerprint:
                continue
                
            relay_analysis = self.analyze_relay_flag_history(fingerprint)
            
            # Collect overall stability score
            stability_score = relay_analysis['flag_stability_score']['overall_score']
            if stability_score > 0:
                all_flag_scores.append(stability_score)
                
                # Categorize relay performance
                if stability_score >= 95:
                    operator_analysis['excellent_performers'].append({
                        'nickname': relay.get('nickname', 'Unknown'),
                        'fingerprint': fingerprint,
                        'stability_score': stability_score
                    })
                elif stability_score < 80:
                    operator_analysis['problem_relays'].append({
                        'nickname': relay.get('nickname', 'Unknown'),
                        'fingerprint': fingerprint,
                        'stability_score': stability_score,
                        'issues': relay_analysis['flag_metrics_summary'].get('issues', [])
                    })
            
            # Aggregate role performance
            for role, metrics in relay_analysis['role_performance'].items():
                if role not in role_performances:
                    role_performances[role] = []
                role_performances[role].append(metrics['reliability_percentage'])
        
        # Calculate operator-wide metrics
        if all_flag_scores:
            operator_analysis['overall_flag_stability'] = sum(all_flag_scores) / len(all_flag_scores)
            
        # Calculate role-specific averages
        for role, scores in role_performances.items():
            if scores:
                operator_analysis['flag_performance_by_role'][role] = {
                    'average_reliability': sum(scores) / len(scores),
                    'relay_count': len(scores),
                    'min_reliability': min(scores),
                    'max_reliability': max(scores),
                    'std_deviation': statistics.stdev(scores) if len(scores) > 1 else 0.0
                }
        
        operator_analysis['operator_flag_summary'] = self._generate_operator_flag_summary(operator_analysis)
        
        return operator_analysis

    def _find_relay_uptime_data(self, fingerprint):
        """Find uptime data for a specific relay by fingerprint"""
        if not self.uptime_data or not self.uptime_data.get('relays'):
            return None
            
        for relay in self.uptime_data['relays']:
            if relay.get('fingerprint') == fingerprint:
                return relay
        return None

    def _analyze_flag_consistency(self, flags_data):
        """
        Analyze consistency of flags over time
        
        Args:
            flags_data (dict): Flag-specific uptime data from Onionoo
            
        Returns:
            dict: Flag consistency metrics
        """
        consistency_metrics = {
            'stable_flags': [],      # Flags with >95% uptime
            'unstable_flags': [],    # Flags with <80% uptime
            'intermittent_flags': [], # Flags with 80-95% uptime
            'overall_consistency': 0.0,
            'flag_reliability_scores': {}
        }
        
        total_consistency = 0.0
        flag_count = 0
        
        for flag_name, flag_data in flags_data.items():
            reliability = self._calculate_flag_reliability(flag_data)
            if reliability is not None:
                consistency_metrics['flag_reliability_scores'][flag_name] = reliability
                total_consistency += reliability
                flag_count += 1
                
                # Categorize flag stability
                if reliability >= 95:
                    consistency_metrics['stable_flags'].append({
                        'flag': flag_name,
                        'reliability': reliability,
                        'description': self.FLAG_DESCRIPTIONS.get(flag_name, f'{flag_name} flag')
                    })
                elif reliability < 80:
                    consistency_metrics['unstable_flags'].append({
                        'flag': flag_name,
                        'reliability': reliability,
                        'description': self.FLAG_DESCRIPTIONS.get(flag_name, f'{flag_name} flag')
                    })
                else:
                    consistency_metrics['intermittent_flags'].append({
                        'flag': flag_name,
                        'reliability': reliability,
                        'description': self.FLAG_DESCRIPTIONS.get(flag_name, f'{flag_name} flag')
                    })
        
        if flag_count > 0:
            consistency_metrics['overall_consistency'] = total_consistency / flag_count
            
        return consistency_metrics

    def _analyze_role_performance(self, flags_data):
        """
        Analyze performance by role (Guard, Exit, etc.)
        
        Args:
            flags_data (dict): Flag-specific uptime data
            
        Returns:
            dict: Role-specific performance metrics
        """
        role_performance = {}
        
        for flag_name, flag_data in flags_data.items():
            reliability = self._calculate_flag_reliability(flag_data)
            if reliability is not None:
                role_performance[flag_name] = {
                    'reliability_percentage': reliability,
                    'role_description': self.FLAG_DESCRIPTIONS.get(flag_name, f'{flag_name} flag'),
                    'importance_weight': self.FLAG_WEIGHTS.get(flag_name, 0.5),
                    'performance_grade': self._get_performance_grade(reliability),
                    'time_periods': self._analyze_flag_time_periods(flag_data)
                }
        
        return role_performance

    def _calculate_flag_stability_score(self, flags_data):
        """
        Calculate overall flag stability score
        
        Args:
            flags_data (dict): Flag-specific uptime data
            
        Returns:
            dict: Stability score and breakdown
        """
        weighted_scores = []
        total_weight = 0.0
        flag_breakdown = {}
        
        for flag_name, flag_data in flags_data.items():
            reliability = self._calculate_flag_reliability(flag_data)
            if reliability is not None:
                weight = self.FLAG_WEIGHTS.get(flag_name, 0.5)
                weighted_scores.append(reliability * weight)
                total_weight += weight
                
                flag_breakdown[flag_name] = {
                    'reliability': reliability,
                    'weight': weight,
                    'weighted_score': reliability * weight
                }
        
        overall_score = sum(weighted_scores) / total_weight if total_weight > 0 else 0.0
        
        return {
            'overall_score': overall_score,
            'score_grade': self._get_performance_grade(overall_score),
            'flag_breakdown': flag_breakdown,
            'total_flags_analyzed': len(flag_breakdown)
        }

    def _analyze_flag_performance_vs_network(self, flags_data):
        """
        Compare flag performance against network averages
        (This would require network-wide flag data for full implementation)
        
        Args:
            flags_data (dict): Flag-specific uptime data
            
        Returns:
            dict: Comparative analysis results
        """
        # For now, return comparison against expected benchmarks
        # In full implementation, this would compare against network averages
        
        benchmarks = {
            'Running': 98.0,   # Expected 98%+ uptime for running flag
            'Guard': 95.0,     # Expected 95%+ for guard eligibility
            'Exit': 95.0,      # Expected 95%+ for exit capability
            'Fast': 90.0,      # Expected 90%+ for fast flag
            'Stable': 97.0,    # Expected 97%+ for stable flag
            'Authority': 99.0, # Expected 99%+ for authorities
        }
        
        comparative_analysis = {
            'vs_benchmarks': {},
            'performance_summary': {
                'above_benchmark': 0,
                'below_benchmark': 0,
                'total_compared': 0
            }
        }
        
        for flag_name, flag_data in flags_data.items():
            reliability = self._calculate_flag_reliability(flag_data)
            benchmark = benchmarks.get(flag_name)
            
            if reliability is not None and benchmark is not None:
                comparative_analysis['vs_benchmarks'][flag_name] = {
                    'relay_performance': reliability,
                    'benchmark': benchmark,
                    'difference': reliability - benchmark,
                    'meets_benchmark': reliability >= benchmark
                }
                
                comparative_analysis['performance_summary']['total_compared'] += 1
                if reliability >= benchmark:
                    comparative_analysis['performance_summary']['above_benchmark'] += 1
                else:
                    comparative_analysis['performance_summary']['below_benchmark'] += 1
        
        return comparative_analysis

    def _reconstruct_flag_timeline(self, flags_data):
        """
        Reconstruct timeline of flag changes (simplified version)
        
        Args:
            flags_data (dict): Flag-specific uptime data
            
        Returns:
            dict: Timeline reconstruction
        """
        # This would require more detailed analysis of the time series data
        # For now, return a simplified analysis
        
        timeline = {
            'current_flags': list(flags_data.keys()),
            'flag_count': len(flags_data),
            'estimated_stability': {},
            'timeline_note': 'Full timeline reconstruction requires detailed time series analysis'
        }
        
        for flag_name, flag_data in flags_data.items():
            reliability = self._calculate_flag_reliability(flag_data)
            if reliability is not None:
                timeline['estimated_stability'][flag_name] = reliability
        
        return timeline

    def _calculate_role_reliability(self, flags_data):
        """
        Calculate reliability by major role categories
        
        Args:
            flags_data (dict): Flag-specific uptime data
            
        Returns:
            dict: Role-based reliability metrics
        """
        role_reliability = {
            'entry_guard': None,
            'exit_node': None,
            'relay_operation': None,
            'directory_services': None
        }
        
        # Entry guard reliability (Guard flag)
        if 'Guard' in flags_data:
            role_reliability['entry_guard'] = self._calculate_flag_reliability(flags_data['Guard'])
        
        # Exit node reliability (Exit flag)
        if 'Exit' in flags_data:
            role_reliability['exit_node'] = self._calculate_flag_reliability(flags_data['Exit'])
        
        # Basic relay operation (Running flag)
        if 'Running' in flags_data:
            role_reliability['relay_operation'] = self._calculate_flag_reliability(flags_data['Running'])
        
        # Directory services (V2Dir, HSDir flags)
        dir_flags = ['V2Dir', 'HSDir']
        dir_reliabilities = []
        for flag in dir_flags:
            if flag in flags_data:
                reliability = self._calculate_flag_reliability(flags_data[flag])
                if reliability is not None:
                    dir_reliabilities.append(reliability)
        
        if dir_reliabilities:
            role_reliability['directory_services'] = sum(dir_reliabilities) / len(dir_reliabilities)
        
        return role_reliability

    def _generate_flag_metrics_summary(self, flags_data):
        """
        Generate summary of flag metrics for display
        
        Args:
            flags_data (dict): Flag-specific uptime data
            
        Returns:
            dict: Summary metrics for display
        """
        summary = {
            'total_flags': len(flags_data),
            'critical_flags_count': 0,
            'excellent_flags': [],
            'concerning_flags': [],
            'issues': [],
            'recommendations': []
        }
        
        critical_flags = ['Running', 'Guard', 'Exit', 'Authority', 'Valid']
        
        for flag_name, flag_data in flags_data.items():
            reliability = self._calculate_flag_reliability(flag_data)
            if reliability is not None:
                if flag_name in critical_flags:
                    summary['critical_flags_count'] += 1
                
                if reliability >= 98:
                    summary['excellent_flags'].append(flag_name)
                elif reliability < 85:
                    summary['concerning_flags'].append(flag_name)
                    summary['issues'].append(f'{flag_name} flag reliability below 85% ({reliability:.1f}%)')
        
        # Generate recommendations
        if summary['concerning_flags']:
            summary['recommendations'].append('Review relay configuration and infrastructure for concerning flags')
        if summary['critical_flags_count'] == 0:
            summary['recommendations'].append('Consider configuring relay for Guard or Exit role')
        if len(summary['excellent_flags']) > 0:
            summary['recommendations'].append('Excellent flag reliability - maintain current practices')
        
        return summary

    def _calculate_flag_reliability(self, flag_data):
        """
        Calculate reliability percentage for a single flag
        
        Args:
            flag_data (dict): Single flag uptime data
            
        Returns:
            float or None: Reliability percentage (0-100) or None if no data
        """
        # Try 1-month data first, then 6-month as fallback
        for period in ['1_month', '6_months']:
            if period in flag_data and flag_data[period].get('values'):
                values = [v for v in flag_data[period]['values'] if v is not None]
                if values:
                    # Normalize from 0-999 scale to 0-100 percentage
                    avg_raw = sum(values) / len(values)
                    return (avg_raw / 999) * 100
        
        return None

    def _analyze_flag_time_periods(self, flag_data):
        """
        Analyze flag performance across different time periods
        
        Args:
            flag_data (dict): Single flag uptime data
            
        Returns:
            dict: Time period analysis
        """
        time_periods = {}
        
        for period in ['1_month', '6_months', '1_year', '5_years']:
            if period in flag_data and flag_data[period].get('values'):
                values = [v for v in flag_data[period]['values'] if v is not None]
                if values:
                    avg_raw = sum(values) / len(values)
                    reliability = (avg_raw / 999) * 100
                    time_periods[period] = {
                        'reliability': reliability,
                        'data_points': len(values),
                        'period_display': period.replace('_', ' ').title()
                    }
        
        return time_periods

    def _get_performance_grade(self, reliability):
        """
        Get performance grade for reliability percentage
        
        Args:
            reliability (float): Reliability percentage (0-100)
            
        Returns:
            str: Performance grade
        """
        if reliability >= 98:
            return 'Excellent'
        elif reliability >= 95:
            return 'Good'
        elif reliability >= 90:
            return 'Fair'
        elif reliability >= 80:
            return 'Poor'
        else:
            return 'Critical'

    def _generate_operator_flag_summary(self, operator_analysis):
        """
        Generate operator-wide flag performance summary
        
        Args:
            operator_analysis (dict): Operator analysis data
            
        Returns:
            dict: Summary for display
        """
        summary = {
            'overall_grade': self._get_performance_grade(operator_analysis['overall_flag_stability']),
            'best_performing_role': None,
            'worst_performing_role': None,
            'total_excellent_relays': len(operator_analysis['excellent_performers']),
            'total_problem_relays': len(operator_analysis['problem_relays']),
            'recommendations': []
        }
        
        # Find best and worst performing roles
        role_performances = operator_analysis['flag_performance_by_role']
        if role_performances:
            best_role = max(role_performances.items(), key=lambda x: x[1]['average_reliability'])
            worst_role = min(role_performances.items(), key=lambda x: x[1]['average_reliability'])
            
            summary['best_performing_role'] = {
                'role': best_role[0],
                'average_reliability': best_role[1]['average_reliability']
            }
            summary['worst_performing_role'] = {
                'role': worst_role[0],
                'average_reliability': worst_role[1]['average_reliability']
            }
        
        # Generate recommendations
        if summary['total_problem_relays'] > 0:
            summary['recommendations'].append(f'Address {summary["total_problem_relays"]} relays with poor flag stability')
        if summary['overall_grade'] in ['Excellent', 'Good']:
            summary['recommendations'].append('Maintain excellent flag stability practices')
        else:
            summary['recommendations'].append('Focus on improving overall flag reliability')
        
        return summary

    def _empty_flag_analysis(self):
        """Return empty analysis structure when no flag data is available"""
        return {
            'flag_consistency': {'stable_flags': [], 'unstable_flags': [], 'intermittent_flags': [], 'overall_consistency': 0.0, 'flag_reliability_scores': {}},
            'role_performance': {},
            'flag_stability_score': {'overall_score': 0.0, 'score_grade': 'No Data', 'flag_breakdown': {}, 'total_flags_analyzed': 0},
            'comparative_analysis': {'vs_benchmarks': {}, 'performance_summary': {'above_benchmark': 0, 'below_benchmark': 0, 'total_compared': 0}},
            'flag_timeline': {'current_flags': [], 'flag_count': 0, 'estimated_stability': {}, 'timeline_note': 'No flag data available'},
            'reliability_by_role': {'entry_guard': None, 'exit_node': None, 'relay_operation': None, 'directory_services': None},
            'flag_metrics_summary': {'total_flags': 0, 'critical_flags_count': 0, 'excellent_flags': [], 'concerning_flags': [], 'issues': ['No flag history data available'], 'recommendations': ['Enable flag history tracking']}
        }


def create_flag_history_display_data(flag_analysis):
    """
    Create display-ready data for templates
    
    Args:
        flag_analysis (dict): Flag analysis from FlagHistoryAnalyzer
        
    Returns:
        dict: Template-ready display data
    """
    display_data = {
        'has_flag_data': flag_analysis['flag_stability_score']['total_flags_analyzed'] > 0,
        'overall_score': flag_analysis['flag_stability_score']['overall_score'],
        'overall_grade': flag_analysis['flag_stability_score']['score_grade'],
        'flag_performances': [],
        'consistency_summary': {
            'stable_count': len(flag_analysis['flag_consistency']['stable_flags']),
            'unstable_count': len(flag_analysis['flag_consistency']['unstable_flags']),
            'intermittent_count': len(flag_analysis['flag_consistency']['intermittent_flags'])
        },
        'role_reliabilities': flag_analysis['reliability_by_role'],
        'recommendations': flag_analysis['flag_metrics_summary']['recommendations'],
        'issues': flag_analysis['flag_metrics_summary']['issues']
    }
    
    # Format flag performances for display
    for flag_name, performance in flag_analysis['role_performance'].items():
        display_data['flag_performances'].append({
            'flag_name': flag_name,
            'reliability': performance['reliability_percentage'],
            'grade': performance['performance_grade'],
            'description': performance['role_description'],
            'importance': performance['importance_weight']
        })
    
    # Sort by importance and reliability
    display_data['flag_performances'].sort(key=lambda x: (x['importance'], x['reliability']), reverse=True)
    
    return display_data