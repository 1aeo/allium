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
        """Layer 10: Infrastructure dependency analysis focusing on critical ASes and version synchronization"""
        template_values = {}
        
        # Version diversity
        versions = set(relay.get('version', 'Unknown') for relay in self.relays)
        template_values['unique_versions'] = len(versions)
        
        # Critical ASes analysis (ASes with >5% of network) and single points of failure
        critical_as_list = []
        critical_as_names = []
        if 'as' in self.sorted_data:
            for as_number, as_data in self.sorted_data['as'].items():
                weight_fraction = as_data.get('consensus_weight_fraction', 0)
                if weight_fraction > 0.05:  # >5% threshold
                    as_name = as_data.get('as_name', f'AS{as_number}')
                    critical_as_list.append(as_number)
                    critical_as_names.append(f"AS{as_number} ({as_name[:30]}{'...' if len(as_name) > 30 else ''})")
        
        template_values['critical_as_count'] = len(critical_as_list)
        template_values['critical_as_list'] = critical_as_names
        
        # Version synchronization risk with explanation
        version_count = len(versions)
        if version_count <= 3:
            template_values['synchronization_risk'] = 'HIGH'
            template_values['sync_risk_tooltip'] = f'Only {version_count} Tor versions detected - high risk of coordinated updates/vulnerabilities'
        elif version_count <= 6:
            template_values['synchronization_risk'] = 'MEDIUM'
            template_values['sync_risk_tooltip'] = f'{version_count} Tor versions detected - moderate diversity, some coordination risk'
        else:
            template_values['synchronization_risk'] = 'LOW'
            template_values['sync_risk_tooltip'] = f'{version_count} Tor versions detected - good diversity, low coordination risk'
        
        return {'template_optimized': template_values}
    
    def _layer11_geographic_clustering(self):
        """Layer 11: Complete geographic analysis with enhanced regional details"""
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
        
        # Regional HHI calculation with top 3 regions
        regional_hhi, regional_stats = self._calculate_regional_hhi_detailed()
        template_values['regional_hhi'] = f"{regional_hhi:.3f}"
        
        # HHI interpretation and tooltip
        if regional_hhi > 0.25:
            template_values['concentration_hhi_interpretation'] = 'HIGH'
        elif regional_hhi > 0.15:
            template_values['concentration_hhi_interpretation'] = 'MEDIUM'
        else:
            template_values['concentration_hhi_interpretation'] = 'LOW'
        
        # Enhanced tooltips and top regions
        template_values['hhi_tooltip'] = f'Herfindahl-Hirschman Index measures concentration: 0=perfect distribution, 1=complete concentration. Current HHI: {regional_hhi:.3f}'
        template_values['regional_concentration_tooltip'] = 'Regional distribution of Tor network capacity by geographic regions'
        
        # Top 3 regions by weight
        top_regions = sorted(regional_stats.items(), key=lambda x: x[1], reverse=True)[:3]
        top_3_text = ', '.join([f"{region.title().replace('_', ' ')}: {weight*100:.1f}%" for region, weight in top_regions if weight > 0])
        template_values['top_3_regions'] = top_3_text if top_3_text else 'Insufficient data'
        
        return {'template_optimized': template_values}
    
    def _layer13_capacity_distribution(self):
        """Layer 13: Complete capacity analysis with Gini explanation"""
        template_values = {}
        
        # Gini coefficient with enhanced tooltip
        weights = [relay.get('consensus_weight_fraction', 0) for relay in self.relays if relay.get('consensus_weight_fraction', 0) > 0]
        if weights:
            gini = self._calculate_gini_coefficient(sorted(weights))
            template_values['gini_coefficient'] = f"{gini:.3f}"
            template_values['diversity_status'] = 'HIGH' if gini > 0.6 else 'MEDIUM' if gini > 0.4 else 'LOW'
            template_values['gini_tooltip'] = f'Gini coefficient measures inequality: 0=perfect equality, 1=complete inequality. Current: {gini:.3f} indicates {"high" if gini > 0.6 else "medium" if gini > 0.4 else "low"} capacity concentration among relays'
        else:
            template_values['gini_coefficient'] = '0.000'
            template_values['diversity_status'] = 'UNKNOWN'
            template_values['gini_tooltip'] = 'Gini coefficient measures wealth inequality - unable to calculate due to insufficient data'
        
        # Role-specific capacity percentages
        guard_weight = sum(relay.get('consensus_weight_fraction', 0) for relay in self.relays if 'Guard' in relay.get('flags', []))
        exit_weight = sum(relay.get('consensus_weight_fraction', 0) for relay in self.relays if 'Exit' in relay.get('flags', []))
        
        template_values['guard_capacity_percentage'] = f"{guard_weight * 100:.1f}"
        template_values['exit_capacity_percentage'] = f"{exit_weight * 100:.1f}"
        
        # Guard capacity status and tooltip
        template_values['guard_capacity_status'] = 'HIGH' if guard_weight > 0.6 else 'MEDIUM' if guard_weight > 0.4 else 'LOW'
        template_values['guard_capacity_tooltip'] = f'Guard capacity indicates availability of relays that can serve as entry points to the Tor network. Thresholds: HIGH >60%, MEDIUM 40-60%, LOW ≤40%. Current: {guard_weight * 100:.1f}%'
        
        # Exit capacity status and tooltip
        template_values['exit_capacity_status'] = 'HIGH' if exit_weight > 0.2 else 'MEDIUM' if exit_weight > 0.1 else 'LOW'
        template_values['exit_capacity_tooltip'] = f'Exit capacity indicates availability of relays that can serve as exit points from the Tor network. Thresholds: HIGH >20%, MEDIUM 10-20%, LOW ≤10%. Current: {exit_weight * 100:.1f}%'
        
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
    
    def _calculate_network_position(self, guard_count, middle_count, exit_count, total_relays):
        """Calculate network position strategic label and formatted string"""
        total_roles = guard_count + middle_count + exit_count
        
        if total_roles <= 0:
            return {
                'label': 'no role data',
                'formatted_string': f'no role data ({total_relays} total relays)'
            }
        
        # Calculate percentages
        guard_pct = int(round(guard_count / total_roles * 100))
        middle_pct = int(round(middle_count / total_roles * 100))
        exit_pct = int(round(exit_count / total_roles * 100))
        
        # Determine strategic label using the same logic as template
        if guard_count == total_roles:
            label = 'guard-only'
            percentage_breakdown = f'{guard_pct}% guard'
        elif exit_count == total_roles:
            label = 'exit-only'
            percentage_breakdown = f'{exit_pct}% exit'
        elif middle_count == total_roles:
            label = 'middle-only'
            percentage_breakdown = f'{middle_pct}% middle'
        elif guard_pct > 60:
            label = 'guard-focused'
            percentage_breakdown = f'{guard_pct}% guard, {middle_pct}% middle, {exit_pct}% exit'
        elif exit_pct > 40:
            label = 'exit-focused'
            percentage_breakdown = f'{guard_pct}% guard, {middle_pct}% middle, {exit_pct}% exit'
        elif guard_pct > 20 and exit_pct > 20:
            label = 'multi-role'
            percentage_breakdown = f'{guard_pct}% guard, {middle_pct}% middle, {exit_pct}% exit'
        else:
            label = 'balanced'
            percentage_breakdown = f'{guard_pct}% guard, {middle_pct}% middle, {exit_pct}% exit'
        
        # Create relay count description with proper pluralization
        guard_desc = f'{guard_count} guard{"s" if guard_count != 1 else ""}'
        middle_desc = f'{middle_count} middle{"s" if middle_count != 1 else ""}'
        exit_desc = f'{exit_count} exit{"s" if exit_count != 1 else ""}'
        
        formatted_string = f'{label}, {percentage_breakdown} ({total_relays} total relays, {guard_desc}, {middle_desc}, {exit_desc})'
        
        return {
            'label': label,
            'percentage_breakdown': percentage_breakdown,
            'formatted_string': formatted_string,
            'guard_percentage': guard_pct,
            'middle_percentage': middle_pct,
            'exit_percentage': exit_pct
        }
    
    def _calculate_regional_hhi_detailed(self):
        """Calculate regional HHI with detailed regional statistics"""
        if 'country' not in self.sorted_data:
            return 0.0, {}
        
        # Regional mapping (using centralized definitions)
        from .country_utils import get_standard_regions
        regions = get_standard_regions()
        regions['other'] = set()  # Add 'other' category for unmatched countries
        
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
        hhi = sum(weight ** 2 for weight in regional_weights.values())
        return hhi, regional_weights

    def _layer14_contact_intelligence(self):
        """Layer 14: Contact-specific intelligence for Phase 1 + Phase 2 features"""
        contact_intelligence = {}
        
        # Get underutilized fingerprints for performance analysis (reuse existing calculation)
        underutilized_fingerprints = set()
        for relay in self.relays:
            bandwidth = relay.get('observed_bandwidth', 0)
            consensus_weight = relay.get('consensus_weight', 0)
            if bandwidth > 10000000 and consensus_weight < bandwidth * 0.0000005:  # Same criteria as layer 7
                underutilized_fingerprints.add(relay.get('fingerprint', ''))
        

        
        # Process each contact
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
                    network_rating = "Poor"
                elif unique_as_count <= 3:
                    network_rating = "Okay"
                else:
                    network_rating = "Great"
                
                portfolio_diversity = f"{network_rating}, {unique_as_count} network{'s' if unique_as_count != 1 else ''}"
                

                
                # 3. Measurement Status
                measured_count = contact_data.get('measured_count', 0)
                total_relays = len(contact_relays)
                measurement_status = f"{measured_count}/{total_relays} relays measured by authorities"
                
                # PHASE 2 FEATURES (advanced analytics)
                
                # 4. Geographic Diversity Assessment (with consistent rating)
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
                
                # 5. Performance Insights
                contact_fingerprints = [relay.get('fingerprint') for relay in contact_relays if relay.get('fingerprint')]
                underutilized_count = sum(1 for fp in contact_fingerprints if fp in underutilized_fingerprints)
                
                # Get top 2 underutilized relay fingerprints for this contact
                contact_underutilized_fps = [fp for fp in contact_fingerprints if fp in underutilized_fingerprints][:2]
                
                if total_relays > 0:
                    if underutilized_count == 0:
                        perf_status = "optimal efficiency"
                    elif underutilized_count == total_relays:
                        perf_status = "needs optimization"
                    else:
                        perf_status = "mixed performance"
                else:
                    perf_status = "no data"
                
                # 6. Infrastructure Diversity Analysis (with consistent rating)
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
                

                
                # 8. Operational Maturity
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
                
                # Store complete intelligence for this contact (Phase 1 + Phase 2)
                contact_intelligence[contact_hash] = {
                    # Phase 1: Foundation metrics (moved from template)
                    'portfolio_diversity': portfolio_diversity,
                    'measurement_status': measurement_status,
                    
                    # Phase 2: Advanced analytics
                    'geographic_countries': country_count,
                    'geographic_risk': geo_risk,
                    'performance_underutilized': underutilized_count,
                    'performance_underutilized_fps': contact_underutilized_fps,
                    'performance_status': perf_status,
                    'infrastructure_platforms': platform_count,
                    'infrastructure_versions': version_count,
                    'infrastructure_risk': infra_risk,
                    'maturity': maturity
                }
        
        return {'template_optimized': contact_intelligence} 