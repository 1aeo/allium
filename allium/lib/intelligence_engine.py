"""
Smart Context Links Intelligence Engine - Tier 1 Implementation
Provides enhanced analytical capabilities for Tor relay network analysis

This engine implements 6 intelligence layers:
- Layer 1: Basic Relationships
- Layer 2: Concentration Patterns 
- Layer 7: Performance Correlation
- Layer 10: Infrastructure Dependency
- Layer 11: Geographic Clustering
- Layer 13: Capacity Distribution

All calculations are performed in Python for optimal performance,
replacing expensive Jinja2 template calculations.
"""

import math
import time
from functools import wraps

def timing(f):
    """Decorator to measure function execution time for performance monitoring"""
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        start = time.perf_counter()
        result = f(self, *args, **kwargs)
        end = time.perf_counter()
        duration = end - start
        print(f"[Intelligence] {f.__name__}: {duration:.4f}s")
        
        # Store timing data in instance
        if not hasattr(self, '_timing_data'):
            self._timing_data = {}
        self._timing_data[f.__name__] = duration
        
        return result
    return wrapper

class IntelligenceEngine:
    """Tier 1 Smart Context Links Intelligence Engine"""
    
    def __init__(self, relays_data):
        """Initialize engine with relay data structure"""
        self.relays = relays_data.get('relays', [])
        self.sorted_data = relays_data.get('sorted', {})
        self.network_totals = relays_data.get('network_totals', {})
        self.total_relays = len(self.relays)
        
    @timing
    def analyze_all_layers(self):
        """Execute all Tier 1 intelligence layers and return comprehensive analysis"""
        print("[Intelligence] Starting comprehensive Tier 1 analysis...")
        
        analysis = {
            'basic_relationships': self._layer1_basic_relationships(),
            'concentration_patterns': self._layer2_concentration_patterns(),
            'performance_correlation': self._layer7_performance_correlation(),
            'infrastructure_dependency': self._layer10_infrastructure_dependency(),
            'geographic_clustering': self._layer11_geographic_clustering(),
            'capacity_distribution': self._layer13_capacity_distribution()
        }
        
        # Include timing data in analysis
        analysis['timing'] = getattr(self, '_timing_data', {})
        
        print("[Intelligence] Tier 1 analysis complete")
        return analysis
    
    @timing 
    def _layer1_basic_relationships(self):
        """Layer 1: Basic relationship counting and categorization"""
        relationships = {}
        
        # Count unique entities per category
        for category in ['country', 'as', 'contact', 'family', 'platform', 'flag']:
            if category in self.sorted_data:
                relationships[f'{category}_count'] = len(self.sorted_data[category])
        
        return relationships
    
    @timing
    def _layer2_concentration_patterns(self):
        """Layer 2: Advanced concentration analysis using HHI"""
        patterns = {}
        
        # Pre-compute template values (replacing complex Jinja2 calculations)
        patterns['template_optimized'] = self._precompute_concentration_template_values()
        
        return patterns
    
    def _precompute_concentration_template_values(self):
        """Pre-compute template values to replace expensive Jinja2 calculations"""
        template_values = {}
        
        # Countries concentration (replacing misc-countries.html calculations)
        if 'country' in self.sorted_data:
            countries = list(self.sorted_data['country'].values())
            if countries:
                # Top 3 countries concentration
                sorted_countries = sorted(countries, key=lambda x: x.get('consensus_weight_fraction', 0), reverse=True)
                top_3_weight = sum(c.get('consensus_weight_fraction', 0) for c in sorted_countries[:3])
                template_values['countries_top_3_percentage'] = f"{top_3_weight * 100:.1f}"
                
                # Significant countries (>1% of network)
                significant_countries = len([c for c in countries if c.get('consensus_weight_fraction', 0) > 0.01])
                template_values['countries_significant_count'] = significant_countries
                
                # Five Eyes concentration
                five_eyes_codes = ['us', 'gb', 'ca', 'au', 'nz']
                five_eyes_weight = 0
                for country_code, country_data in self.sorted_data['country'].items():
                    if country_code.lower() in five_eyes_codes:
                        five_eyes_weight += country_data.get('consensus_weight_fraction', 0)
                template_values['countries_five_eyes_percentage'] = f"{five_eyes_weight * 100:.1f}"
        
        # Networks concentration (replacing misc-networks.html calculations)
        if 'as' in self.sorted_data:
            networks = list(self.sorted_data['as'].values())
            if networks:
                # Largest AS concentration
                largest_as = max(networks, key=lambda x: x.get('consensus_weight_fraction', 0))
                template_values['networks_largest_percentage'] = f"{largest_as.get('consensus_weight_fraction', 0) * 100:.1f}"
                
                # Top 3 ASes concentration
                sorted_networks = sorted(networks, key=lambda x: x.get('consensus_weight_fraction', 0), reverse=True)
                top_3_weight = sum(n.get('consensus_weight_fraction', 0) for n in sorted_networks[:3])
                template_values['networks_top_3_percentage'] = f"{top_3_weight * 100:.1f}"
                
                # Single relay networks
                single_relay_count = 0
                for network_data in networks:
                    total_relays = (network_data.get('guard_count', 0) + 
                                   network_data.get('middle_count', 0) + 
                                   network_data.get('exit_count', 0))
                    if total_relays == 1:
                        single_relay_count += 1
                template_values['networks_single_relay_count'] = single_relay_count
        
        # Contacts concentration (replacing misc-contacts.html calculations)
        if 'contact' in self.sorted_data:
            contacts = list(self.sorted_data['contact'].values())
            if contacts:
                # Largest operator concentration
                largest_operator = max(contacts, key=lambda x: x.get('consensus_weight_fraction', 0))
                template_values['contacts_largest_percentage'] = f"{largest_operator.get('consensus_weight_fraction', 0) * 100:.1f}"
                
                # Top 10 operators concentration
                sorted_contacts = sorted(contacts, key=lambda x: x.get('consensus_weight_fraction', 0), reverse=True)
                top_10_weight = sum(c.get('consensus_weight_fraction', 0) for c in sorted_contacts[:10])
                template_values['contacts_top_10_percentage'] = f"{top_10_weight * 100:.1f}"
                
                # No contact info percentage
                contact_relay_count = sum(c.get('guard_count', 0) + c.get('middle_count', 0) + c.get('exit_count', 0) for c in contacts)
                if self.total_relays > 0:
                    no_contact_relays = self.total_relays - contact_relay_count
                    template_values['contacts_no_contact_percentage'] = f"{(no_contact_relays / self.total_relays) * 100:.1f}"
                else:
                    template_values['contacts_no_contact_percentage'] = "0.0"
        
        # Platforms diversity (replacing misc-platforms.html calculations)
        if 'platform' in self.sorted_data:
            linux_weight = windows_weight = bsd_weight = 0
            for platform_name, platform_data in self.sorted_data['platform'].items():
                platform_lower = platform_name.lower()
                weight = platform_data.get('consensus_weight_fraction', 0)
                if 'linux' in platform_lower:
                    linux_weight += weight
                elif 'windows' in platform_lower:
                    windows_weight += weight
                elif 'bsd' in platform_lower:
                    bsd_weight += weight
            
            template_values['platforms_linux_percentage'] = f"{linux_weight * 100:.1f}"
            template_values['platforms_windows_percentage'] = f"{windows_weight * 100:.1f}"
            template_values['platforms_bsd_percentage'] = f"{bsd_weight * 100:.1f}"
        
        return template_values
    
    @timing
    def _layer7_performance_correlation(self):
        """Layer 7: Performance analysis and bandwidth correlation patterns"""
        performance = {}
        
        # Bandwidth efficiency analysis
        performance['bandwidth_efficiency'] = self._analyze_bandwidth_efficiency()
        
        # Measurement coverage analysis
        performance['measurement_analysis'] = self._analyze_measurement_coverage()
        
        # Capacity utilization patterns
        performance['capacity_utilization'] = self._analyze_capacity_utilization()
        
        # Performance by geography and infrastructure
        performance['geographic_performance'] = self._analyze_geographic_performance()
        performance['infrastructure_performance'] = self._analyze_infrastructure_performance()
        
        return performance
    
    @timing
    def _layer10_infrastructure_dependency(self):
        """Layer 10: Infrastructure dependency and hosting concentration analysis"""
        infrastructure = {}
        
        # AS concentration analysis
        infrastructure['hosting_concentration'] = self._analyze_hosting_concentration()
        
        # DNS and hostname patterns
        infrastructure['dns_patterns'] = self._analyze_dns_patterns()
        
        # Version synchronization detection
        infrastructure['version_patterns'] = self._analyze_version_patterns()
        
        # Single points of failure identification
        infrastructure['spof_analysis'] = self._identify_single_points_of_failure()
        
        return infrastructure
    
    @timing
    def _layer11_geographic_clustering(self):
        """Layer 11: Geographic clustering and regional vulnerability analysis"""
        geographic = {}
        
        # Physical proximity clustering (using lat/long when available)
        geographic['proximity_clusters'] = self._find_proximity_clusters()
        
        # Regional concentration analysis
        geographic['regional_concentration'] = self._analyze_regional_concentration()
        
        # Jurisdiction risk assessment
        geographic['jurisdiction_risks'] = self._analyze_jurisdiction_risks()
        
        # Diversity gap identification
        geographic['diversity_gaps'] = self._identify_geographic_diversity_gaps()
        
        return geographic
    
    @timing
    def _layer13_capacity_distribution(self):
        """Layer 13: Capacity distribution and load balancing optimization"""
        capacity = {}
        
        # Consensus weight distribution analysis
        capacity['weight_distribution'] = self._analyze_weight_distribution()
        
        # Role-specific capacity analysis
        capacity['role_capacity'] = self._analyze_role_specific_capacity()
        
        # Bottleneck identification
        capacity['bottlenecks'] = self._identify_capacity_bottlenecks()
        
        # Optimization recommendations
        capacity['optimization'] = self._generate_optimization_recommendations()
        
        return capacity
    
    def _analyze_bandwidth_efficiency(self):
        """Analyze bandwidth efficiency patterns"""
        efficiency = {}
        
        measured_bw = unmeasured_bw = 0
        measured_count = unmeasured_count = 0
        
        for relay in self.relays:
            bw = relay.get('observed_bandwidth', 0)
            if relay.get('measured'):
                measured_bw += bw
                measured_count += 1
            else:
                unmeasured_bw += bw
                unmeasured_count += 1
        
        total_bw = measured_bw + unmeasured_bw
        efficiency['measured_bandwidth_percentage'] = (measured_bw / total_bw * 100) if total_bw > 0 else 0
        efficiency['measured_relay_percentage'] = (measured_count / self.total_relays * 100) if self.total_relays > 0 else 0
        
        # Average bandwidth per relay type
        efficiency['avg_measured_bandwidth'] = (measured_bw / measured_count) if measured_count > 0 else 0
        efficiency['avg_unmeasured_bandwidth'] = (unmeasured_bw / unmeasured_count) if unmeasured_count > 0 else 0
        
        return efficiency
    
    def _analyze_measurement_coverage(self):
        """Analyze bandwidth authority measurement coverage"""
        coverage = {}
        
        # Coverage by role
        roles = ['Guard', 'Middle', 'Exit']
        for role in roles:
            role_measured = role_total = 0
            for relay in self.relays:
                if role in relay.get('flags', []):
                    role_total += 1
                    if relay.get('measured'):
                        role_measured += 1
            
            coverage[f'{role.lower()}_coverage'] = (role_measured / role_total * 100) if role_total > 0 else 0
        
        return coverage
    
    def _analyze_capacity_utilization(self):
        """Analyze capacity utilization patterns"""
        utilization = {}
        
        # Bandwidth vs consensus weight correlation
        total_bandwidth = sum(relay.get('observed_bandwidth', 0) for relay in self.relays)
        total_consensus_weight = sum(relay.get('consensus_weight', 0) for relay in self.relays)
        
        if total_consensus_weight > 0:
            utilization['bandwidth_to_weight_ratio'] = total_bandwidth / total_consensus_weight
        else:
            utilization['bandwidth_to_weight_ratio'] = 0
        
        # Underutilized vs overutilized relays
        underutilized = overutilized = 0
        for relay in self.relays:
            bandwidth = relay.get('observed_bandwidth', 0)
            consensus_weight = relay.get('consensus_weight', 0)
            
            if bandwidth > 0 and consensus_weight > 0:
                ratio = consensus_weight / bandwidth
                if ratio < 0.0000008:  # Underutilized (consensus weight much lower than bandwidth)
                    underutilized += 1
                elif ratio > 0.0000012:  # Overutilized (consensus weight higher than expected)
                    overutilized += 1
        
        utilization['underutilized_count'] = underutilized
        utilization['overutilized_count'] = overutilized
        utilization['underutilized_percentage'] = (underutilized / self.total_relays * 100) if self.total_relays > 0 else 0
        
        return utilization
    
    def _analyze_geographic_performance(self):
        """Analyze performance patterns by geography"""
        performance = {}
        
        if 'country' not in self.sorted_data:
            return performance
        
        country_performance = {}
        for country_code, country_data in self.sorted_data['country'].items():
            total_bandwidth = country_data.get('bandwidth', 0)
            relay_count = (country_data.get('guard_count', 0) + 
                          country_data.get('middle_count', 0) + 
                          country_data.get('exit_count', 0))
            
            avg_bandwidth = (total_bandwidth / relay_count) if relay_count > 0 else 0
            country_performance[country_code] = avg_bandwidth
        
        if country_performance:
            performance['avg_bandwidth_by_country'] = country_performance
            performance['highest_performing_country'] = max(country_performance, key=country_performance.get)
            performance['lowest_performing_country'] = min(country_performance, key=country_performance.get)
            performance['performance_variance'] = max(country_performance.values()) / max(min(country_performance.values()), 1)
        
        return performance
    
    def _analyze_infrastructure_performance(self):
        """Analyze performance patterns by infrastructure"""
        performance = {}
        
        if 'as' not in self.sorted_data:
            return performance
        
        as_performance = {}
        for as_number, as_data in self.sorted_data['as'].items():
            total_bandwidth = as_data.get('bandwidth', 0)
            relay_count = (as_data.get('guard_count', 0) + 
                          as_data.get('middle_count', 0) + 
                          as_data.get('exit_count', 0))
            
            avg_bandwidth = (total_bandwidth / relay_count) if relay_count > 0 else 0
            as_performance[as_number] = avg_bandwidth
        
        if as_performance:
            performance['avg_bandwidth_by_as'] = as_performance
            performance['highest_performing_as'] = max(as_performance, key=as_performance.get)
            performance['lowest_performing_as'] = min(as_performance, key=as_performance.get)
        
        return performance
    
    def _analyze_hosting_concentration(self):
        """Analyze hosting provider concentration"""
        if 'as' not in self.sorted_data:
            return {}
        
        # AS concentration metrics
        as_list = list(self.sorted_data['as'].values())
        
        concentration = {}
        if as_list:
            sorted_as = sorted(as_list, key=lambda x: x.get('consensus_weight_fraction', 0), reverse=True)
            
            concentration['top_1_as_percentage'] = f"{(sorted_as[0].get('consensus_weight_fraction', 0) * 100):.1f}" if sorted_as else "0.0"
            concentration['top_3_as_percentage'] = f"{sum(as_data.get('consensus_weight_fraction', 0) for as_data in sorted_as[:3]) * 100:.1f}"
            concentration['top_10_as_percentage'] = f"{sum(as_data.get('consensus_weight_fraction', 0) for as_data in sorted_as[:10]) * 100:.1f}"
            
            # Risk assessment
            top_1_weight = sorted_as[0].get('consensus_weight_fraction', 0) if sorted_as else 0
            concentration['risk_level'] = 'HIGH' if top_1_weight > 0.15 else 'MEDIUM' if top_1_weight > 0.10 else 'LOW'
        
        return concentration
    
    def _analyze_dns_patterns(self):
        """Analyze DNS and hostname patterns"""
        dns_patterns = {}
        
        # Analyze verified hostnames
        hostname_patterns = {}
        total_hostnames = 0
        
        for relay in self.relays:
            hostnames = relay.get('verified_host_names', [])
            for hostname in hostnames:
                if hostname:
                    total_hostnames += 1
                    # Extract domain from hostname
                    parts = hostname.split('.')
                    if len(parts) >= 2:
                        domain = '.'.join(parts[-2:])
                        hostname_patterns[domain] = hostname_patterns.get(domain, 0) + 1
        
        dns_patterns['common_domains'] = sorted(hostname_patterns.items(), key=lambda x: x[1], reverse=True)[:10]
        dns_patterns['unique_domains'] = len(hostname_patterns)
        dns_patterns['total_hostnames'] = total_hostnames
        dns_patterns['hostname_coverage'] = f"{(total_hostnames / self.total_relays * 100):.1f}" if self.total_relays > 0 else "0.0"
        
        return dns_patterns
    
    def _analyze_version_patterns(self):
        """Analyze Tor version patterns and coordination"""
        version_patterns = {}
        
        version_counts = {}
        for relay in self.relays:
            version = relay.get('version', '')
            if version:
                # Extract major.minor version
                version_parts = version.split('.')
                if len(version_parts) >= 2:
                    major_minor = f"{version_parts[0]}.{version_parts[1]}"
                    version_counts[major_minor] = version_counts.get(major_minor, 0) + 1
        
        if version_counts:
            total_relays = sum(version_counts.values())
            version_patterns['version_distribution'] = {
                version: f"{(count / total_relays * 100):.1f}" for version, count in version_counts.items()
            }
            version_patterns['most_common_version'] = max(version_counts, key=version_counts.get)
            version_patterns['version_diversity'] = len(version_counts)
            
            # Check for high concentration
            max_version_count = max(version_counts.values())
            version_patterns['concentration_risk'] = 'HIGH' if (max_version_count / total_relays) > 0.8 else 'MEDIUM' if (max_version_count / total_relays) > 0.6 else 'LOW'
        
        return version_patterns
    
    def _identify_single_points_of_failure(self):
        """Identify potential single points of failure"""
        spof = {}
        
        # High-capacity single points
        high_capacity_threshold = 0.05  # 5% of network capacity
        
        for category in ['as', 'country', 'contact']:
            if category in self.sorted_data:
                high_capacity_entities = []
                for entity, data in self.sorted_data[category].items():
                    weight_fraction = data.get('consensus_weight_fraction', 0)
                    if weight_fraction > high_capacity_threshold:
                        high_capacity_entities.append({
                            'entity': entity,
                            'weight_percentage': f"{weight_fraction * 100:.1f}",
                            'relay_count': (data.get('guard_count', 0) + 
                                           data.get('middle_count', 0) + 
                                           data.get('exit_count', 0))
                        })
                
                spof[f'{category}_spof'] = sorted(high_capacity_entities, 
                                                  key=lambda x: float(x['weight_percentage']), 
                                                  reverse=True)
        
        return spof
    
    def _find_proximity_clusters(self):
        """Find geographic proximity clusters using lat/long data"""
        clusters = {}
        
        # Group relays by approximate location (0.1 degree precision)
        location_groups = {}
        total_with_coords = 0
        
        for relay in self.relays:
            lat = relay.get('latitude')
            lon = relay.get('longitude')
            if lat is not None and lon is not None:
                total_with_coords += 1
                # Round to 0.1 degree precision for clustering
                lat_round = round(lat, 1)
                lon_round = round(lon, 1)
                location_key = f"{lat_round},{lon_round}"
                
                if location_key not in location_groups:
                    location_groups[location_key] = []
                location_groups[location_key].append(relay)
        
        # Identify significant clusters (5+ relays)
        significant_clusters = []
        for location, relays_in_cluster in location_groups.items():
            if len(relays_in_cluster) >= 5:
                total_bandwidth = sum(r.get('observed_bandwidth', 0) for r in relays_in_cluster)
                countries = list(set(r.get('country') for r in relays_in_cluster if r.get('country')))
                significant_clusters.append({
                    'location': location,
                    'relay_count': len(relays_in_cluster),
                    'total_bandwidth': total_bandwidth,
                    'countries': countries,
                    'country_count': len(countries)
                })
        
        clusters['significant_clusters'] = sorted(significant_clusters, 
                                                 key=lambda x: x['relay_count'], 
                                                 reverse=True)
        clusters['total_clusters'] = len(significant_clusters)
        clusters['coord_coverage'] = f"{(total_with_coords / self.total_relays * 100):.1f}" if self.total_relays > 0 else "0.0"
        
        return clusters
    
    def _analyze_regional_concentration(self):
        """Analyze regional concentration patterns"""
        regional = {}
        
        # Define regions
        regions = {
            'North America': ['us', 'ca', 'mx'],
            'Europe': ['de', 'fr', 'gb', 'nl', 'it', 'es', 'pl', 'se', 'ch', 'at', 'be', 'dk', 'fi', 'no', 'is', 'ie', 'pt'],
            'Asia Pacific': ['jp', 'kr', 'cn', 'in', 'au', 'nz', 'sg', 'hk', 'tw', 'th', 'my'],
            'Other': []  # Will catch everything else
        }
        
        region_stats = {}
        for region_name in regions:
            region_stats[region_name] = {
                'relay_count': 0,
                'bandwidth': 0,
                'consensus_weight': 0
            }
        
        # Categorize countries by region
        if 'country' in self.sorted_data:
            for country_code, country_data in self.sorted_data['country'].items():
                region_assigned = False
                for region_name, country_codes in regions.items():
                    if region_name != 'Other' and country_code.lower() in country_codes:
                        region_stats[region_name]['relay_count'] += (
                            country_data.get('guard_count', 0) + 
                            country_data.get('middle_count', 0) + 
                            country_data.get('exit_count', 0)
                        )
                        region_stats[region_name]['bandwidth'] += country_data.get('bandwidth', 0)
                        region_stats[region_name]['consensus_weight'] += country_data.get('consensus_weight_fraction', 0)
                        region_assigned = True
                        break
                
                if not region_assigned:
                    region_stats['Other']['relay_count'] += (
                        country_data.get('guard_count', 0) + 
                        country_data.get('middle_count', 0) + 
                        country_data.get('exit_count', 0)
                    )
                    region_stats['Other']['bandwidth'] += country_data.get('bandwidth', 0)
                    region_stats['Other']['consensus_weight'] += country_data.get('consensus_weight_fraction', 0)
        
        # Convert to percentages for display
        total_relays = sum(stats['relay_count'] for stats in region_stats.values())
        total_weight = sum(stats['consensus_weight'] for stats in region_stats.values())
        
        for region_name, stats in region_stats.items():
            stats['relay_percentage'] = f"{(stats['relay_count'] / total_relays * 100):.1f}" if total_relays > 0 else "0.0"
            stats['weight_percentage'] = f"{(stats['consensus_weight'] / total_weight * 100):.1f}" if total_weight > 0 else "0.0"
        
        regional['distribution'] = region_stats
        
        # Calculate regional concentration risk using HHI
        if total_weight > 0:
            hhi = sum((stats['consensus_weight'] / total_weight) ** 2 for stats in region_stats.values())
            regional['hhi'] = f"{hhi:.3f}"
            regional['risk_level'] = 'HIGH' if hhi > 0.25 else 'MEDIUM' if hhi > 0.15 else 'LOW'
        
        return regional
    
    def _analyze_jurisdiction_risks(self):
        """Analyze jurisdiction-based risks"""
        jurisdiction = {}
        
        # Five Eyes analysis
        five_eyes = ['us', 'gb', 'ca', 'au', 'nz']
        fourteen_eyes = five_eyes + ['de', 'fr', 'it', 'es', 'nl', 'be', 'dk', 'se', 'no']
        
        five_eyes_weight = fourteen_eyes_weight = 0
        five_eyes_relays = fourteen_eyes_relays = 0
        
        if 'country' in self.sorted_data:
            for country_code, country_data in self.sorted_data['country'].items():
                weight = country_data.get('consensus_weight_fraction', 0)
                relay_count = (country_data.get('guard_count', 0) + 
                              country_data.get('middle_count', 0) + 
                              country_data.get('exit_count', 0))
                
                if country_code.lower() in five_eyes:
                    five_eyes_weight += weight
                    five_eyes_relays += relay_count
                if country_code.lower() in fourteen_eyes:
                    fourteen_eyes_weight += weight
                    fourteen_eyes_relays += relay_count
        
        jurisdiction['five_eyes_weight_percentage'] = f"{five_eyes_weight * 100:.1f}"
        jurisdiction['five_eyes_relay_percentage'] = f"{(five_eyes_relays / self.total_relays * 100):.1f}" if self.total_relays > 0 else "0.0"
        jurisdiction['fourteen_eyes_weight_percentage'] = f"{fourteen_eyes_weight * 100:.1f}"
        jurisdiction['fourteen_eyes_relay_percentage'] = f"{(fourteen_eyes_relays / self.total_relays * 100):.1f}" if self.total_relays > 0 else "0.0"
        
        jurisdiction['five_eyes_risk'] = 'HIGH' if five_eyes_weight > 0.5 else 'MEDIUM' if five_eyes_weight > 0.3 else 'LOW'
        jurisdiction['fourteen_eyes_risk'] = 'HIGH' if fourteen_eyes_weight > 0.7 else 'MEDIUM' if fourteen_eyes_weight > 0.5 else 'LOW'
        
        return jurisdiction
    
    def _identify_geographic_diversity_gaps(self):
        """Identify underrepresented geographic regions"""
        gaps = {}
        
        # Expected high-capacity countries with low representation
        expected_countries = {
            'br': 'Brazil', 'in': 'India', 'ru': 'Russia', 'za': 'South Africa', 
            'kr': 'South Korea', 'jp': 'Japan', 'cn': 'China', 'eg': 'Egypt',
            'ng': 'Nigeria', 'mx': 'Mexico', 'ar': 'Argentina', 'tr': 'Turkey'
        }
        
        underrepresented = []
        missing = []
        
        if 'country' in self.sorted_data:
            for country_code, country_name in expected_countries.items():
                if country_code in self.sorted_data['country']:
                    weight = self.sorted_data['country'][country_code].get('consensus_weight_fraction', 0)
                    if weight < 0.01:  # Less than 1% representation
                        underrepresented.append({
                            'code': country_code,
                            'name': country_name,
                            'weight_percentage': f"{weight * 100:.2f}"
                        })
                else:
                    missing.append({
                        'code': country_code,
                        'name': country_name,
                        'weight_percentage': "0.00"
                    })
        
        gaps['underrepresented_countries'] = underrepresented
        gaps['missing_countries'] = missing
        gaps['total_gaps'] = len(underrepresented) + len(missing)
        
        return gaps
    
    def _analyze_weight_distribution(self):
        """Analyze consensus weight distribution patterns"""
        distribution = {}
        
        weights = [relay.get('consensus_weight_fraction', 0) for relay in self.relays if relay.get('consensus_weight_fraction', 0) > 0]
        weights.sort(reverse=True)
        
        if weights:
            distribution['gini_coefficient'] = f"{self._calculate_gini_coefficient(weights):.3f}"
            distribution['top_1_percent'] = f"{sum(weights[:max(1, len(weights)//100)]) * 100:.1f}"
            distribution['top_10_percent'] = f"{sum(weights[:max(1, len(weights)//10)]) * 100:.1f}"
            distribution['median_weight'] = f"{weights[len(weights)//2] * 100:.4f}" if weights else "0.0000"
            
            # Inequality assessment
            gini = self._calculate_gini_coefficient(weights)
            distribution['inequality_level'] = 'VERY_HIGH' if gini > 0.8 else 'HIGH' if gini > 0.6 else 'MEDIUM' if gini > 0.4 else 'LOW'
        
        return distribution
    
    def _calculate_gini_coefficient(self, values):
        """Calculate Gini coefficient for inequality measurement"""
        n = len(values)
        if n == 0:
            return 0
            
        # Sort values
        sorted_values = sorted(values)
        total = sum(sorted_values)
        if total == 0:
            return 0
            
        # Calculate Gini coefficient
        cumsum = 0
        gini = 0
        for i, value in enumerate(sorted_values):
            cumsum += value
            gini += (2 * (i + 1) - n - 1) * value
            
        return gini / (n * total)
    
    def _analyze_role_specific_capacity(self):
        """Analyze capacity distribution by relay role"""
        capacity = {}
        
        for role in ['Guard', 'Middle', 'Exit']:
            role_relays = [r for r in self.relays if role in r.get('flags', [])]
            if role_relays:
                total_bandwidth = sum(r.get('observed_bandwidth', 0) for r in role_relays)
                total_weight = sum(r.get('consensus_weight', 0) for r in role_relays)
                avg_bandwidth = total_bandwidth / len(role_relays)
                
                capacity[f'{role.lower()}_capacity'] = {
                    'relay_count': len(role_relays),
                    'total_bandwidth': total_bandwidth,
                    'total_weight': total_weight,
                    'avg_bandwidth': avg_bandwidth,
                    'percentage_of_network': f"{(len(role_relays) / self.total_relays * 100):.1f}" if self.total_relays > 0 else "0.0"
                }
        
        return capacity
    
    def _identify_capacity_bottlenecks(self):
        """Identify potential capacity bottlenecks"""
        bottlenecks = {}
        
        # Exit relay bottleneck analysis (most restrictive)
        exit_relays = [r for r in self.relays if 'Exit' in r.get('flags', [])]
        total_exit_bandwidth = sum(r.get('observed_bandwidth', 0) for r in exit_relays)
        total_bandwidth = sum(r.get('observed_bandwidth', 0) for r in self.relays)
        
        if total_bandwidth > 0:
            exit_bandwidth_ratio = total_exit_bandwidth / total_bandwidth
            bottlenecks['exit_bandwidth_ratio'] = f"{exit_bandwidth_ratio * 100:.1f}"
            bottlenecks['exit_bottleneck_risk'] = 'HIGH' if exit_bandwidth_ratio < 0.2 else 'MEDIUM' if exit_bandwidth_ratio < 0.3 else 'LOW'
        
        # Geographic bottlenecks
        if 'country' in self.sorted_data:
            country_weights = [(k, v.get('consensus_weight_fraction', 0)) for k, v in self.sorted_data['country'].items()]
            country_weights.sort(key=lambda x: x[1], reverse=True)
            
            # Check if top country has too much capacity
            if country_weights:
                top_country_weight = country_weights[0][1]
                bottlenecks['top_country_weight'] = f"{top_country_weight * 100:.1f}"
                bottlenecks['geographic_bottleneck_risk'] = 'HIGH' if top_country_weight > 0.4 else 'MEDIUM' if top_country_weight > 0.25 else 'LOW'
        
        return bottlenecks
    
    def _generate_optimization_recommendations(self):
        """Generate capacity optimization recommendations"""
        recommendations = []
        
        # Analyze current capacity distribution
        if 'as' in self.sorted_data:
            as_weights = [(k, v.get('consensus_weight_fraction', 0)) for k, v in self.sorted_data['as'].items()]
            as_weights.sort(key=lambda x: x[1], reverse=True)
            
            if as_weights and as_weights[0][1] > 0.15:
                recommendations.append({
                    'type': 'infrastructure_diversity',
                    'priority': 'HIGH',
                    'description': f'Consider diversifying from AS {as_weights[0][0]} (controls {as_weights[0][1]*100:.1f}% of network)',
                    'category': 'AS_CONCENTRATION'
                })
        
        if 'country' in self.sorted_data:
            country_weights = [(k, v.get('consensus_weight_fraction', 0)) for k, v in self.sorted_data['country'].items()]
            country_weights.sort(key=lambda x: x[1], reverse=True)
            
            if country_weights and country_weights[0][1] > 0.25:
                recommendations.append({
                    'type': 'geographic_diversity',
                    'priority': 'HIGH',
                    'description': f'Consider geographic diversification from {country_weights[0][0]} (controls {country_weights[0][1]*100:.1f}% of network)',
                    'category': 'GEOGRAPHIC_CONCENTRATION'
                })
        
        # Exit capacity recommendations
        exit_relays = [r for r in self.relays if 'Exit' in r.get('flags', [])]
        total_exit_bandwidth = sum(r.get('observed_bandwidth', 0) for r in exit_relays)
        total_bandwidth = sum(r.get('observed_bandwidth', 0) for r in self.relays)
        
        if total_bandwidth > 0 and (total_exit_bandwidth / total_bandwidth) < 0.25:
            recommendations.append({
                'type': 'exit_capacity',
                'priority': 'MEDIUM',
                'description': f'Network needs more exit capacity (currently {(total_exit_bandwidth / total_bandwidth * 100):.1f}% of total bandwidth)',
                'category': 'CAPACITY_BOTTLENECK'
            })
        
        return recommendations 