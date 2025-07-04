"""
Tier 1 Intelligence Engine - Complete Implementation
All calculations moved from Jinja2 templates to Python for maximum performance.
"""

import statistics
import math
from .statistical_utils import StatisticalUtils

class IntelligenceEngine:
    """Complete Tier 1 Intelligence Engine - implements all design doc requirements"""
    
    def __init__(self, relays_data):
        """Initialize with processed relay data structure"""
        self.relays = relays_data.get('relays', [])
        self.sorted_data = relays_data.get('sorted', {})
        self.network_totals = relays_data.get('network_totals', {})
        self.family_stats = relays_data.get('family_statistics', {})
        
        # Pre-calculate network-wide performance data once (major optimization)
        self._precompute_performance_data()
        
    def _precompute_performance_data(self):
        """Pre-calculate network performance data to eliminate duplication"""
        # Calculate network totals once (eliminates 5 loops per contact)
        self.network_total_bandwidth = self.network_totals.get('total_network_bandwidth', 0)
        self.guard_network_bandwidth = self.network_totals.get('total_guard_bandwidth', 0)
        self.exit_network_bandwidth = self.network_totals.get('total_exit_bandwidth', 0)
        self.network_total_consensus_weight = (
            self.network_totals.get('guard_consensus_weight', 0) + 
            self.network_totals.get('middle_consensus_weight', 0) + 
            self.network_totals.get('exit_consensus_weight', 0)
        )
        self.guard_network_consensus_weight = self.network_totals.get('guard_consensus_weight', 0)
        self.exit_network_consensus_weight = self.network_totals.get('exit_consensus_weight', 0)
        
        # Calculate network ratios once (reused in multiple methods)
        self.overall_network_ratio = self._calculate_cw_bw_ratio(self.network_total_consensus_weight, self.network_total_bandwidth)
        self.guard_network_ratio = self._calculate_cw_bw_ratio(self.guard_network_consensus_weight, self.guard_network_bandwidth)
        self.exit_network_ratio = self._calculate_cw_bw_ratio(self.exit_network_consensus_weight, self.exit_network_bandwidth)
        
        # Pre-calculate underutilized fingerprints once (eliminates duplication)
        self.underutilized_fingerprints = self._get_underutilized_fingerprints()
        
        # Pre-calculate network-wide relay ratios for percentile calculations once
        self.all_relay_ratios, self.guard_relay_ratios, self.exit_relay_ratios = self._calculate_network_relay_ratios()
        
        # Calculate medians once (reused in multiple places)
        self.overall_network_median = self._calculate_median(self.all_relay_ratios)
        self.guard_network_median = self._calculate_median(self.guard_relay_ratios)
        self.exit_network_median = self._calculate_median(self.exit_relay_ratios)
        
    def _calculate_cw_bw_ratio(self, consensus_weight, bandwidth):
        """Centralized CW/BW ratio calculation - eliminates duplication"""
        return consensus_weight / bandwidth * 1000000 if bandwidth > 0 else 0.0
        
    def _get_underutilized_fingerprints(self):
        """Centralized underutilized relay detection - eliminates duplication"""
        underutilized = set()
        for relay in self.relays:
            bandwidth = relay.get('observed_bandwidth', 0)
            consensus_weight = relay.get('consensus_weight', 0)
            if bandwidth > 10000000 and consensus_weight < bandwidth * 0.0000005:
                underutilized.add(relay.get('fingerprint', ''))
        return underutilized
        
    def _calculate_network_relay_ratios(self):
        """Pre-calculate all network relay ratios once - major optimization"""
        all_ratios, guard_ratios, exit_ratios = [], [], []
        
        for relay in self.relays:
            bandwidth = relay.get('observed_bandwidth', 0)
            consensus_weight = relay.get('consensus_weight', 0)
            flags = relay.get('flags', [])
            
            if bandwidth > 0:
                ratio = self._calculate_cw_bw_ratio(consensus_weight, bandwidth)
                all_ratios.append(ratio)
                
                if 'Guard' in flags:
                    guard_ratios.append(ratio)
                if 'Exit' in flags:
                    exit_ratios.append(ratio)
        
        # Sort once for all percentile calculations
        all_ratios.sort()
        guard_ratios.sort()
        exit_ratios.sort()
        
        return all_ratios, guard_ratios, exit_ratios
    
    def _calculate_median(self, sorted_list):
        """Centralized median calculation using unified StatisticalUtils"""
        if not sorted_list:
            return 0
        return statistics.median(sorted_list)
    
    def _calculate_percentile_rank(self, value, sorted_ratio_list):
        """Centralized percentile calculation using unified StatisticalUtils"""
        return StatisticalUtils.calculate_percentile_rank(value, sorted_ratio_list)
        
    def analyze_all_layers(self):
        """Execute all Tier 1 layers using existing data - no recalculation"""
        if not self.sorted_data:
            return self._get_empty_template_values()
        
        return {
            'basic_relationships': self._layer1_basic_relationships(),
            'concentration_patterns': self._layer2_concentration_patterns(),
            'performance_correlation': self._layer7_performance_correlation(),
            'infrastructure_dependency': self._layer10_infrastructure_dependency(),
            'geographic_clustering': self._layer11_geographic_clustering(),
            'capacity_distribution': self._layer13_capacity_distribution(),
            'contact_intelligence': self._layer14_contact_intelligence()
        }
    
    def _get_empty_template_values(self):
        """Return empty template values when sorted data unavailable"""
        return {
            'basic_relationships': {'template_optimized': {
                'total_countries': 0, 'total_networks': 0, 'total_operators': 0,
                'total_families': 0, 'total_platforms': 0
            }},
            'concentration_patterns': {'template_optimized': {
                'countries_top_3_percentage': '0.0', 'countries_significant_count': 0, 'countries_five_eyes_percentage': '0.0',
                'networks_largest_percentage': '0.0', 'networks_top_3_percentage': '0.0', 'networks_single_relay_count': 0,
                'contacts_largest_percentage': '0.0', 'contacts_top_10_percentage': '0.0', 'contacts_no_contact_percentage': '0.0',
                'platforms_linux_percentage': '0.0', 'platforms_windows_percentage': '0.0', 'platforms_bsd_percentage': '0.0'
            }},
            'performance_correlation': {'template_optimized': {
                'measured_percentage': '0.0', 'underutilized_count': 0, 'underutilized_fingerprints': [],
                'efficiency_ratio': '0.00'
            }},
            'infrastructure_dependency': {'template_optimized': {
                'unique_versions': 0, 'critical_as_count': 0, 'critical_as_list': [],
                'synchronization_risk': 'UNKNOWN', 'sync_risk_tooltip': 'Sync risk assessment unavailable'
            }},
            'geographic_clustering': {'template_optimized': {
                'five_eyes_percentage': '0.0', 'fourteen_eyes_percentage': '0.0',
                'five_eyes_influence': '0.0', 'fourteen_eyes_influence': '0.0',
                'concentration_hhi_interpretation': 'UNKNOWN', 'regional_hhi': '0.000',
                'hhi_tooltip': 'HHI measurement unavailable', 'top_3_regions': 'No data',
                'regional_concentration_tooltip': 'Regional analysis unavailable'
            }},
            'capacity_distribution': {'template_optimized': {
                'gini_coefficient': '0.000', 'diversity_status': 'UNKNOWN',
                'exit_capacity_status': 'UNKNOWN', 'guard_capacity_percentage': '0.0',
                'exit_capacity_percentage': '0.0', 'gini_tooltip': 'Gini coefficient calculation unavailable'
            }},
            'contact_intelligence': {'template_optimized': {}}
        }
    
    def _layer1_basic_relationships(self):
        """Layer 1: Basic counts using existing sorted data"""
        return {
            'template_optimized': {
                'total_countries': len(self.sorted_data.get('country', {})),
                'total_networks': len(self.sorted_data.get('as', {})),
                'total_operators': len(self.sorted_data.get('contact', {})),
                'total_families': len(self.sorted_data.get('family', {})),
                'total_platforms': len(self.sorted_data.get('platform', {}))
            }
        }
    
    def _layer2_concentration_patterns(self):
        """Layer 2: Complete concentration analysis using existing sorted data"""
        template_values = {}
        
        # Countries concentration analysis
        countries = list(self.sorted_data.get('country', {}).values())
        if countries:
            sorted_countries = sorted(countries, key=lambda x: x.get('consensus_weight_fraction', 0), reverse=True)
            top_3_weight = sum(c.get('consensus_weight_fraction', 0) for c in sorted_countries[:3])
            template_values['countries_top_3_percentage'] = f"{top_3_weight * 100:.1f}"
            
            # Significant countries (>1% of network)
            significant_countries = len([c for c in countries if c.get('consensus_weight_fraction', 0) > 0.01])
            template_values['countries_significant_count'] = significant_countries
            
            # Five Eyes concentration
            five_eyes_codes = {'us', 'gb', 'ca', 'au', 'nz'}
            five_eyes_weight = sum(country_data.get('consensus_weight_fraction', 0) 
                                 for country_code, country_data in self.sorted_data['country'].items() 
                                 if country_code.lower() in five_eyes_codes)
            template_values['countries_five_eyes_percentage'] = f"{five_eyes_weight * 100:.1f}"
        else:
            template_values.update({
                'countries_top_3_percentage': '0.0',
                'countries_significant_count': 0,
                'countries_five_eyes_percentage': '0.0'
            })
        
        # Networks concentration analysis
        networks = list(self.sorted_data.get('as', {}).values())
        if networks:
            # Largest AS concentration
            largest_as = max(networks, key=lambda x: x.get('consensus_weight_fraction', 0))
            template_values['networks_largest_percentage'] = f"{largest_as.get('consensus_weight_fraction', 0) * 100:.1f}"
            
            # Top 3 ASes concentration
            sorted_networks = sorted(networks, key=lambda x: x.get('consensus_weight_fraction', 0), reverse=True)
            top_3_weight = sum(n.get('consensus_weight_fraction', 0) for n in sorted_networks[:3])
            template_values['networks_top_3_percentage'] = f"{top_3_weight * 100:.1f}"
            
            # Single relay networks
            single_relay_count = sum(1 for network_data in networks 
                                   if (network_data.get('guard_count', 0) + 
                                       network_data.get('middle_count', 0) + 
                                       network_data.get('exit_count', 0)) == 1)
            template_values['networks_single_relay_count'] = single_relay_count
        else:
            template_values.update({
                'networks_largest_percentage': '0.0',
                'networks_top_3_percentage': '0.0',
                'networks_single_relay_count': 0
            })
        
        # Contacts concentration analysis
        contacts = list(self.sorted_data.get('contact', {}).values())
        if contacts:
            # Largest operator concentration
            largest_operator = max(contacts, key=lambda x: x.get('consensus_weight_fraction', 0))
            template_values['contacts_largest_percentage'] = f"{largest_operator.get('consensus_weight_fraction', 0) * 100:.1f}"
            
            # Top 10 operators concentration
            sorted_contacts = sorted(contacts, key=lambda x: x.get('consensus_weight_fraction', 0), reverse=True)
            top_10_weight = sum(c.get('consensus_weight_fraction', 0) for c in sorted_contacts[:10])
            template_values['contacts_top_10_percentage'] = f"{top_10_weight * 100:.1f}"
            
            # No contact info percentage - check for empty contact info
            total_relays = len(self.relays)
            no_contact_count = sum(1 for relay in self.relays if not relay.get('contact', '').strip())
            template_values['contacts_no_contact_percentage'] = f"{(no_contact_count / total_relays * 100):.1f}" if total_relays > 0 else '0.0'
        else:
            template_values.update({
                'contacts_largest_percentage': '0.0',
                'contacts_top_10_percentage': '0.0',
                'contacts_no_contact_percentage': '0.0'
            })
        
        # Platforms concentration analysis
        if 'platform' in self.sorted_data:
            linux_weight = windows_weight = bsd_weight = 0
            for platform_name, platform_data in self.sorted_data['platform'].items():
                platform_lower = platform_name.lower()
                weight = platform_data.get('consensus_weight_fraction', 0)
                if 'linux' in platform_lower:
                    linux_weight += weight
                elif 'windows' in platform_lower:
                    windows_weight += weight
                elif 'bsd' in platform_lower or 'freebsd' in platform_lower or 'openbsd' in platform_lower:
                    bsd_weight += weight
            
            template_values['platforms_linux_percentage'] = f"{linux_weight * 100:.1f}"
            template_values['platforms_windows_percentage'] = f"{windows_weight * 100:.1f}"
            template_values['platforms_bsd_percentage'] = f"{bsd_weight * 100:.1f}"
        else:
            template_values.update({
                'platforms_linux_percentage': '0.0',
                'platforms_windows_percentage': '0.0',
                'platforms_bsd_percentage': '0.0'
            })
        
        return {'template_optimized': template_values}
    
    def _layer7_performance_correlation(self):
        """Layer 7: Complete performance analysis using pre-computed data"""
        template_values = {}
        
        # Use pre-computed measured percentage
        template_values['measured_percentage'] = f"{self.network_totals.get('measured_percentage', 0):.1f}"
        
        # Use pre-computed underutilized relays
        template_values['underutilized_count'] = len(self.underutilized_fingerprints)
        template_values['underutilized_fingerprints'] = list(self.underutilized_fingerprints)
        
        # Use pre-computed network ratio
        template_values['efficiency_ratio'] = f"{self.overall_network_ratio:.2f}"
        
        return {'template_optimized': template_values}
    
    def _layer10_infrastructure_dependency(self):
        """Layer 10: Infrastructure dependency analysis"""
        template_values = {}
        
        # Count unique versions
        versions = set()
        for relay in self.relays:
            if relay.get('version'):
                versions.add(relay.get('version'))
        
        template_values['unique_versions'] = len(versions)
        
        # Critical AS analysis (>5% of network)
        critical_as = []
        if 'as' in self.sorted_data:
            for as_number, as_data in self.sorted_data['as'].items():
                if as_data.get('consensus_weight_fraction', 0) > 0.05:
                    critical_as.append(as_number)
        
        template_values['critical_as_count'] = len(critical_as)
        template_values['critical_as_list'] = critical_as
        
        # Synchronization risk assessment
        if len(versions) == 1:
            template_values['synchronization_risk'] = 'HIGH'
            template_values['sync_risk_tooltip'] = 'All relays running same version - high synchronization risk'
        elif len(versions) <= 3:
            template_values['synchronization_risk'] = 'MEDIUM'
            template_values['sync_risk_tooltip'] = f'{len(versions)} versions - moderate synchronization risk'
        else:
            template_values['synchronization_risk'] = 'LOW'
            template_values['sync_risk_tooltip'] = f'{len(versions)} versions - low synchronization risk'
        
        return {'template_optimized': template_values}
    
    def _layer11_geographic_clustering(self):
        """Layer 11: Geographic clustering analysis"""
        template_values = {}
        
        # Five Eyes and Fourteen Eyes analysis
        five_eyes_codes = {'us', 'gb', 'ca', 'au', 'nz'}
        fourteen_eyes_codes = five_eyes_codes.union({'de', 'fr', 'it', 'es', 'nl', 'be', 'dk', 'no', 'se'})
        
        five_eyes_weight = 0
        fourteen_eyes_weight = 0
        
        if 'country' in self.sorted_data:
            for country_code, country_data in self.sorted_data['country'].items():
                weight = country_data.get('consensus_weight_fraction', 0)
                if country_code.lower() in five_eyes_codes:
                    five_eyes_weight += weight
                if country_code.lower() in fourteen_eyes_codes:
                    fourteen_eyes_weight += weight
        
        template_values['five_eyes_percentage'] = f"{five_eyes_weight * 100:.1f}"
        template_values['fourteen_eyes_percentage'] = f"{fourteen_eyes_weight * 100:.1f}"
        template_values['five_eyes_influence'] = f"{five_eyes_weight * 100:.1f}"
        template_values['fourteen_eyes_influence'] = f"{fourteen_eyes_weight * 100:.1f}"
        
        # Regional HHI calculation
        regional_hhi = self._calculate_regional_hhi_detailed()
        template_values['regional_hhi'] = f"{regional_hhi:.3f}"
        
        if regional_hhi < 0.15:
            template_values['concentration_hhi_interpretation'] = 'LOW'
            template_values['hhi_tooltip'] = 'Low geographic concentration - good diversity'
        elif regional_hhi < 0.25:
            template_values['concentration_hhi_interpretation'] = 'MODERATE'
            template_values['hhi_tooltip'] = 'Moderate geographic concentration'
        else:
            template_values['concentration_hhi_interpretation'] = 'HIGH'
            template_values['hhi_tooltip'] = 'High geographic concentration - limited diversity'
        
        # Top 3 regions
        if 'country' in self.sorted_data:
            sorted_countries = sorted(self.sorted_data['country'].items(), 
                                    key=lambda x: x[1].get('consensus_weight_fraction', 0), reverse=True)
            top_3 = [f"{country[0].upper()}: {country[1].get('consensus_weight_fraction', 0) * 100:.1f}%" 
                    for country in sorted_countries[:3]]
            template_values['top_3_regions'] = ', '.join(top_3)
            template_values['regional_concentration_tooltip'] = f"Top 3 countries: {', '.join(top_3)}"
        else:
            template_values['top_3_regions'] = 'No data'
            template_values['regional_concentration_tooltip'] = 'Regional analysis unavailable'
        
        return {'template_optimized': template_values}
    
    def _layer13_capacity_distribution(self):
        """Layer 13: Capacity distribution analysis"""
        template_values = {}
        
        # Gini coefficient calculation
        consensus_weights = [relay.get('consensus_weight', 0) for relay in self.relays]
        consensus_weights = [w for w in consensus_weights if w > 0]  # Remove zero weights
        
        if len(consensus_weights) > 1:
            gini = self._calculate_gini_coefficient(sorted(consensus_weights))
            template_values['gini_coefficient'] = f"{gini:.3f}"
            
            if gini < 0.4:
                template_values['diversity_status'] = 'EXCELLENT'
                template_values['gini_tooltip'] = 'Low inequality - excellent capacity distribution'
            elif gini < 0.6:
                template_values['diversity_status'] = 'GOOD'
                template_values['gini_tooltip'] = 'Moderate inequality - good capacity distribution'
            else:
                template_values['diversity_status'] = 'POOR'
                template_values['gini_tooltip'] = 'High inequality - concentrated capacity distribution'
        else:
            template_values['gini_coefficient'] = '0.000'
            template_values['diversity_status'] = 'UNKNOWN'
            template_values['gini_tooltip'] = 'Insufficient data for Gini calculation'
        
        # Guard and Exit capacity analysis
        guard_capacity = sum(relay.get('consensus_weight', 0) for relay in self.relays if 'Guard' in relay.get('flags', []))
        exit_capacity = sum(relay.get('consensus_weight', 0) for relay in self.relays if 'Exit' in relay.get('flags', []))
        total_capacity = sum(relay.get('consensus_weight', 0) for relay in self.relays)
        
        if total_capacity > 0:
            guard_percentage = (guard_capacity / total_capacity) * 100
            exit_percentage = (exit_capacity / total_capacity) * 100
            
            template_values['guard_capacity_percentage'] = f"{guard_percentage:.1f}"
            template_values['exit_capacity_percentage'] = f"{exit_percentage:.1f}"
            
            if exit_percentage < 10:
                template_values['exit_capacity_status'] = 'CRITICAL'
            elif exit_percentage < 20:
                template_values['exit_capacity_status'] = 'LOW'
            else:
                template_values['exit_capacity_status'] = 'ADEQUATE'
        else:
            template_values['guard_capacity_percentage'] = '0.0'
            template_values['exit_capacity_percentage'] = '0.0'
            template_values['exit_capacity_status'] = 'UNKNOWN'
        
        return {'template_optimized': template_values}
    
    def _calculate_gini_coefficient(self, sorted_values):
        """Calculate Gini coefficient for inequality measurement"""
        if not sorted_values or len(sorted_values) < 2:
            return 0.0
        
        n = len(sorted_values)
        total = sum(sorted_values)
        
        if total == 0:
            return 0.0
        
        # Calculate Gini coefficient using the standard formula
        cumulative_sum = 0
        gini_sum = 0
        
        for i, value in enumerate(sorted_values):
            cumulative_sum += value
            gini_sum += (2 * (i + 1) - n - 1) * value
        
        return gini_sum / (n * total)
    
    def _calculate_network_position(self, guard_count, middle_count, exit_count, total_relays):
        """Calculate network position classification"""
        if total_relays == 0:
            return {
                'label': 'no-relays',
                'formatted_string': 'No relays'
            }
        
        guard_pct = (guard_count / total_relays) * 100
        middle_pct = (middle_count / total_relays) * 100
        exit_pct = (exit_count / total_relays) * 100
        
        # Classification logic
        if guard_pct == 100:
            label = "guard-only"
            position_label = "Guard-only"
        elif exit_pct == 100:
            label = "exit-only"
            position_label = "Exit-only"
        elif middle_pct == 100:
            label = "middle-only"
            position_label = "Middle-only"
        elif guard_pct > 60:
            label = "guard-focused"
            position_label = "Guard-focused"
        elif exit_pct > 40:
            label = "exit-focused"
            position_label = "Exit-focused"
        elif guard_pct > 20 and exit_pct > 20:
            label = "multi-role"
            position_label = "Multi-role"
        else:
            label = "balanced"
            position_label = "Balanced"
        
        # Create detailed formatted string
        position_components = []
        if guard_count > 0:
            guard_text = 'guard' if guard_count == 1 else 'guards'
            position_components.append(f"{guard_count} {guard_text}")
        if middle_count > 0:
            middle_text = 'middle' if middle_count == 1 else 'middles'
            position_components.append(f"{middle_count} {middle_text}")
        if exit_count > 0:
            exit_text = 'exit' if exit_count == 1 else 'exits'
            position_components.append(f"{exit_count} {exit_text}")
        
        total_text = 'relay' if total_relays == 1 else 'relays'
        components_text = ', ' + ', '.join(position_components) if position_components else ''
        formatted_string = f"{position_label} ({total_relays} total {total_text}{components_text})"
        
        return {
            'label': label,
            'formatted_string': formatted_string
        }
    
    def _calculate_regional_hhi_detailed(self):
        """Calculate detailed regional HHI for geographic clustering"""
        if 'country' not in self.sorted_data:
            return 0.0
        
        # Sum of squares of market shares
        hhi = sum(country_data.get('consensus_weight_fraction', 0) ** 2 
                 for country_data in self.sorted_data['country'].values())
        
        return hhi
    
    def _layer14_contact_intelligence(self):
        """Layer 14: Contact-specific intelligence using pre-computed data"""
        contact_intelligence = {}
        
        # Process each contact using pre-computed performance data
        if 'contact' in self.sorted_data:
            for contact_hash, contact_data in self.sorted_data['contact'].items():
                # Get relays for this contact
                contact_relays = [self.relays[idx] for idx in contact_data.get('relays', [])]
                
                if not contact_relays:
                    continue
                
                # PHASE 1 FEATURES (moved from template to Python)
                
                # 1. Network Diversity (with consistent rating)
                unique_as_count = contact_data.get('unique_as_count', 0)
                
                # Determine network diversity rating
                if unique_as_count == 1:
                    # Special case: Check if this contact is the only operator in their AS
                    first_relay_as = contact_relays[0].get('as') if contact_relays else None
                    if (first_relay_as and 'as' in self.sorted_data and 
                        first_relay_as in self.sorted_data['as'] and
                        self.sorted_data['as'][first_relay_as].get('unique_contact_count', 0) == 1):
                        network_rating = "Great"
                        portfolio_diversity = f"{network_rating}, 1 AS with 1 operator"
                    else:
                        network_rating = "Poor"
                        portfolio_diversity = f"{network_rating}, {unique_as_count} network{'s' if unique_as_count != 1 else ''}"
                elif unique_as_count <= 3:
                    network_rating = "Okay"
                    portfolio_diversity = f"{network_rating}, {unique_as_count} network{'s' if unique_as_count != 1 else ''}"
                else:
                    network_rating = "Great"
                    portfolio_diversity = f"{network_rating}, {unique_as_count} network{'s' if unique_as_count != 1 else ''}"
                
                # 2. Measurement Status
                measured_count = contact_data.get('measured_count', 0)
                total_relays = len(contact_relays)
                measurement_status = f"{measured_count}/{total_relays} relays measured by authorities"
                
                # PHASE 2 FEATURES (advanced analytics)
                
                # 3. Geographic Diversity Assessment (with consistent rating)
                countries = set(relay.get('country') for relay in contact_relays if relay.get('country'))
                country_count = len(countries)
                
                # Determine geographic diversity rating
                if country_count == 1:
                    geo_rating = "Poor"
                elif country_count <= 3:
                    geo_rating = "Okay"
                else:
                    geo_rating = "Great"
                
                geo_risk = f"{geo_rating}, {country_count} countr{'y' if country_count == 1 else 'ies'}"
                
                # 4. Performance Insights - using pre-computed data
                contact_fingerprints = [relay.get('fingerprint') for relay in contact_relays if relay.get('fingerprint')]
                underutilized_count = sum(1 for fp in contact_fingerprints if fp in self.underutilized_fingerprints)
                underutilized_percentage = round((underutilized_count / total_relays * 100)) if total_relays > 0 else 0
                contact_underutilized_fps = [fp for fp in contact_fingerprints if fp in self.underutilized_fingerprints][:2]
                
                # Calculate operator CW/BW ratios using centralized function
                total_operator_bandwidth = sum(relay.get('observed_bandwidth', 0) for relay in contact_relays)
                total_operator_consensus_weight = sum(relay.get('consensus_weight', 0) for relay in contact_relays)
                
                # Calculate operator position-specific bandwidth and consensus weight
                operator_guard_bandwidth = operator_guard_consensus_weight = 0
                operator_exit_bandwidth = operator_exit_consensus_weight = 0
                
                for relay in contact_relays:
                    flags = relay.get('flags', [])
                    bandwidth = relay.get('observed_bandwidth', 0)
                    consensus_weight = relay.get('consensus_weight', 0)
                    
                    if 'Guard' in flags:
                        operator_guard_bandwidth += bandwidth
                        operator_guard_consensus_weight += consensus_weight
                    if 'Exit' in flags:
                        operator_exit_bandwidth += bandwidth
                        operator_exit_consensus_weight += consensus_weight
                
                # Use centralized ratio calculation
                operator_overall_ratio = self._calculate_cw_bw_ratio(total_operator_consensus_weight, total_operator_bandwidth)
                operator_guard_ratio = self._calculate_cw_bw_ratio(operator_guard_consensus_weight, operator_guard_bandwidth)
                operator_exit_ratio = self._calculate_cw_bw_ratio(operator_exit_consensus_weight, operator_exit_bandwidth)
                
                # Use pre-computed percentile calculations
                operator_overall_pct = self._calculate_percentile_rank(operator_overall_ratio, self.all_relay_ratios)
                operator_guard_pct = self._calculate_percentile_rank(operator_guard_ratio, self.guard_relay_ratios) if operator_guard_ratio > 0 else None
                operator_exit_pct = self._calculate_percentile_rank(operator_exit_ratio, self.exit_relay_ratios) if operator_exit_ratio > 0 else None
                
                # 5. Infrastructure Diversity Analysis (with consistent rating)
                platforms = set(relay.get('platform') for relay in contact_relays if relay.get('platform'))
                versions = set(relay.get('version') for relay in contact_relays if relay.get('version'))
                platform_count = len(platforms)
                version_count = len(versions)
                
                # Determine infrastructure diversity rating
                if platform_count == 1 and version_count == 1:
                    infra_rating = "Poor"
                elif platform_count <= 2 or version_count <= 2:
                    infra_rating = "Okay"
                else:
                    infra_rating = "Great"
                
                infra_risk = f"{infra_rating}, {platform_count} platform{'s' if platform_count != 1 else ''}, {version_count} version{'s' if version_count != 1 else ''}"
                
                # 6. Operational Maturity
                first_seen_dates = [relay.get('first_seen') for relay in contact_relays if relay.get('first_seen')]
                if first_seen_dates:
                    dates = [date.split(' ')[0] for date in first_seen_dates]
                    oldest_date = min(dates)
                    newest_date = max(dates)
                    
                    if oldest_date == newest_date:
                        maturity = f"Operating since {oldest_date} (all deployed together)"
                    else:
                        maturity = f"Operating since {oldest_date} (expanded through {newest_date})"
                else:
                    maturity = "No timeline data"
                
                # Store complete intelligence for this contact
                contact_intelligence[contact_hash] = {
                    # Phase 1: Foundation metrics
                    'portfolio_diversity': portfolio_diversity,
                    'measurement_status': measurement_status,
                    
                    # Phase 2: Advanced analytics
                    'geographic_countries': country_count,
                    'geographic_risk': geo_risk,
                    'performance_underutilized': underutilized_count,
                    'performance_underutilized_percentage': underutilized_percentage,
                    'performance_underutilized_fps': contact_underutilized_fps,
                    'performance_operator_overall_ratio': f"{operator_overall_ratio:.0f}",
                    'performance_operator_guard_ratio': f"{operator_guard_ratio:.0f}" if operator_guard_ratio > 0 else None,
                    'performance_operator_exit_ratio': f"{operator_exit_ratio:.0f}" if operator_exit_ratio > 0 else None,
                    'performance_network_overall_ratio': f"{self.overall_network_ratio:.0f}",
                    'performance_network_guard_ratio': f"{self.guard_network_ratio:.0f}",
                    'performance_network_exit_ratio': f"{self.exit_network_ratio:.0f}",
                    'performance_network_overall_median': f"{self.overall_network_median:.0f}",
                    'performance_network_guard_median': f"{self.guard_network_median:.0f}",
                    'performance_network_exit_median': f"{self.exit_network_median:.0f}",
                    'performance_operator_overall_pct': operator_overall_pct,
                    'performance_operator_guard_pct': operator_guard_pct if operator_guard_ratio > 0 else None,
                    'performance_operator_exit_pct': operator_exit_pct if operator_exit_ratio > 0 else None,
                    'performance_relay_count': len(self.all_relay_ratios),
                    'infrastructure_platforms': platform_count,
                    'infrastructure_versions': version_count,
                    'infrastructure_risk': infra_risk,
                    'maturity': maturity
                }
        
        return {'template_optimized': contact_intelligence} 