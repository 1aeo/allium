"""
Tier 1 Intelligence Engine - Complete Implementation
All calculations moved from Jinja2 templates to Python for maximum performance.
"""

class IntelligenceEngine:
    """Complete Tier 1 Intelligence Engine - implements all design doc requirements"""
    
    def __init__(self, relays_data):
        """Initialize with processed relay data structure"""
        self.relays = relays_data.get('relays', [])
        self.sorted_data = relays_data.get('sorted', {})
        self.network_totals = relays_data.get('network_totals', {})
        self.family_stats = relays_data.get('family_statistics', {})
        
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
            'capacity_distribution': self._layer13_capacity_distribution()
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
                'hostname_coverage': '0.0', 'unique_versions': 0, 'critical_as_count': 0,
                'concentration_risk_level': 'UNKNOWN', 'synchronization_risk': 'UNKNOWN'
            }},
            'geographic_clustering': {'template_optimized': {
                'five_eyes_percentage': '0.0', 'fourteen_eyes_percentage': '0.0',
                'five_eyes_influence': '0.0', 'fourteen_eyes_influence': '0.0',
                'overall_risk_level': 'UNKNOWN', 'concentration_hhi_interpretation': 'UNKNOWN',
                'regional_hhi': '0.000'
            }},
            'capacity_distribution': {'template_optimized': {
                'gini_coefficient': '0.000', 'diversity_status': 'UNKNOWN',
                'exit_capacity_status': 'UNKNOWN', 'guard_capacity_percentage': '0.0',
                'exit_capacity_percentage': '0.0'
            }}
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
        """Layer 7: Complete performance analysis using existing network totals"""
        template_values = {}
        
        # Use pre-computed measured percentage
        template_values['measured_percentage'] = f"{self.network_totals.get('measured_percentage', 0):.1f}"
        
        # Count underutilized relays and create fingerprint list
        underutilized_relays = []
        for relay in self.relays:
            bandwidth = relay.get('observed_bandwidth', 0)
            consensus_weight = relay.get('consensus_weight', 0)
            if bandwidth > 10000000 and consensus_weight < bandwidth * 0.0000005:  # 10MB+ but low weight
                underutilized_relays.append(relay.get('fingerprint', ''))
        
        template_values['underutilized_count'] = len(underutilized_relays)
        template_values['underutilized_fingerprints'] = underutilized_relays
        
        # Calculate efficiency ratio (simple average)
        total_bandwidth = sum(relay.get('observed_bandwidth', 0) for relay in self.relays)
        total_consensus_weight = sum(relay.get('consensus_weight', 0) for relay in self.relays)
        if total_bandwidth > 0:
            efficiency_ratio = total_consensus_weight / total_bandwidth * 1000000  # Scale for readability
            template_values['efficiency_ratio'] = f"{efficiency_ratio:.2f}"
        else:
            template_values['efficiency_ratio'] = '0.00'
        
        return {'template_optimized': template_values}
    
    def _layer10_infrastructure_dependency(self):
        """Layer 10: Complete infrastructure analysis"""
        template_values = {}
        
        # DNS hostname coverage
        hostname_count = sum(1 for relay in self.relays 
                           if relay.get('or_addresses', [''])[0] and 
                           not relay.get('or_addresses', [''])[0].replace('.', '').replace(':', '').isdigit())
        template_values['hostname_coverage'] = f"{(hostname_count / len(self.relays) * 100):.1f}" if self.relays else '0.0'
        
        # Version diversity
        versions = set(relay.get('version', 'Unknown') for relay in self.relays)
        template_values['unique_versions'] = len(versions)
        
        # Critical ASes analysis (ASes with >5% of network)
        critical_as_count = 0
        if 'as' in self.sorted_data:
            for as_data in self.sorted_data['as'].values():
                if as_data.get('consensus_weight_fraction', 0) > 0.05:
                    critical_as_count += 1
        template_values['critical_as_count'] = critical_as_count
        
        # Concentration risk level based on largest AS
        if 'as' in self.sorted_data:
            networks = list(self.sorted_data['as'].values())
            if networks:
                largest_as_weight = max(n.get('consensus_weight_fraction', 0) for n in networks)
                if largest_as_weight > 0.15:
                    template_values['concentration_risk_level'] = 'HIGH'
                elif largest_as_weight > 0.10:
                    template_values['concentration_risk_level'] = 'MEDIUM'
                else:
                    template_values['concentration_risk_level'] = 'LOW'
            else:
                template_values['concentration_risk_level'] = 'UNKNOWN'
        else:
            template_values['concentration_risk_level'] = 'UNKNOWN'
        
        # Version synchronization risk
        if len(versions) <= 3:
            template_values['synchronization_risk'] = 'HIGH'
        elif len(versions) <= 6:
            template_values['synchronization_risk'] = 'MEDIUM'
        else:
            template_values['synchronization_risk'] = 'LOW'
        
        return {'template_optimized': template_values}
    
    def _layer11_geographic_clustering(self):
        """Layer 11: Complete geographic analysis"""
        template_values = {}
        
        # Five/Fourteen Eyes analysis
        five_eyes = {'us', 'gb', 'ca', 'au', 'nz'}
        fourteen_eyes = five_eyes | {'de', 'fr', 'it', 'es', 'nl', 'be', 'dk', 'se', 'no'}
        
        five_eyes_weight = fourteen_eyes_weight = 0
        for country_code, country_data in self.sorted_data.get('country', {}).items():
            weight = country_data.get('consensus_weight_fraction', 0)
            if country_code.lower() in five_eyes:
                five_eyes_weight += weight
            if country_code.lower() in fourteen_eyes:
                fourteen_eyes_weight += weight
        
        template_values['five_eyes_percentage'] = f"{five_eyes_weight * 100:.1f}"
        template_values['fourteen_eyes_percentage'] = f"{fourteen_eyes_weight * 100:.1f}"
        template_values['five_eyes_influence'] = f"{five_eyes_weight * 100:.1f}"
        template_values['fourteen_eyes_influence'] = f"{fourteen_eyes_weight * 100:.1f}"
        
        # Overall risk assessment
        if five_eyes_weight > 0.25:
            template_values['overall_risk_level'] = 'HIGH'
        elif fourteen_eyes_weight > 0.40:
            template_values['overall_risk_level'] = 'MEDIUM'
        else:
            template_values['overall_risk_level'] = 'LOW'
        
        # Regional HHI calculation
        regional_hhi = self._calculate_regional_hhi()
        template_values['regional_hhi'] = f"{regional_hhi:.3f}"
        
        if regional_hhi > 0.25:
            template_values['concentration_hhi_interpretation'] = 'HIGH'
        elif regional_hhi > 0.15:
            template_values['concentration_hhi_interpretation'] = 'MEDIUM'
        else:
            template_values['concentration_hhi_interpretation'] = 'LOW'
        
        return {'template_optimized': template_values}
    
    def _layer13_capacity_distribution(self):
        """Layer 13: Complete capacity analysis"""
        template_values = {}
        
        # Gini coefficient
        weights = [relay.get('consensus_weight_fraction', 0) for relay in self.relays if relay.get('consensus_weight_fraction', 0) > 0]
        if weights:
            gini = self._calculate_gini_coefficient(sorted(weights))
            template_values['gini_coefficient'] = f"{gini:.3f}"
            template_values['diversity_status'] = 'HIGH' if gini > 0.6 else 'MEDIUM' if gini > 0.4 else 'LOW'
        else:
            template_values['gini_coefficient'] = '0.000'
            template_values['diversity_status'] = 'UNKNOWN'
        
        # Role-specific capacity percentages
        guard_weight = sum(relay.get('consensus_weight_fraction', 0) for relay in self.relays if 'Guard' in relay.get('flags', []))
        exit_weight = sum(relay.get('consensus_weight_fraction', 0) for relay in self.relays if 'Exit' in relay.get('flags', []))
        
        template_values['guard_capacity_percentage'] = f"{guard_weight * 100:.1f}"
        template_values['exit_capacity_percentage'] = f"{exit_weight * 100:.1f}"
        
        # Exit capacity status
        template_values['exit_capacity_status'] = 'HIGH' if exit_weight > 0.2 else 'MEDIUM' if exit_weight > 0.1 else 'LOW'
        
        return {'template_optimized': template_values}
    
    def _calculate_gini_coefficient(self, sorted_values):
        """Calculate Gini coefficient efficiently"""
        n = len(sorted_values)
        if n <= 1:
            return 0.0
        
        total = sum(sorted_values)
        if total == 0:
            return 0.0
        
        gini_sum = sum((2 * (i + 1) - n - 1) * value for i, value in enumerate(sorted_values))
        return gini_sum / (n * total)
    
    def _calculate_regional_hhi(self):
        """Calculate regional HHI for geographic concentration"""
        if 'country' not in self.sorted_data:
            return 0.0
        
        # Simple regional mapping
        regions = {
            'north_america': {'us', 'ca'},
            'europe': {'de', 'fr', 'gb', 'nl', 'it', 'es', 'se', 'no', 'dk', 'fi'},
            'asia_pacific': {'jp', 'au', 'nz', 'kr', 'sg', 'hk'},
            'other': set()
        }
        
        regional_weights = {region: 0.0 for region in regions.keys()}
        
        for country_code, country_data in self.sorted_data['country'].items():
            weight = country_data.get('consensus_weight_fraction', 0)
            assigned = False
            
            for region, countries in regions.items():
                if region != 'other' and country_code.lower() in countries:
                    regional_weights[region] += weight
                    assigned = True
                    break
            
            if not assigned:
                regional_weights['other'] += weight
        
        # Calculate HHI
        return sum(weight ** 2 for weight in regional_weights.values()) 