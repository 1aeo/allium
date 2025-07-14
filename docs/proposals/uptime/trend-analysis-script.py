#!/usr/bin/env python3
"""
Onionoo Uptime Trend Analysis and Anomaly Detection

This script analyzes Tor relay uptime data from the Onionoo API to identify:
1. Overall network trends
2. Relay family-specific patterns
3. Anomalies in uptime behavior
4. Statistical insights and visualizations

Author: Analysis for Allium project
"""

import requests
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

class OnionooUptimeAnalyzer:
    def __init__(self):
        self.base_url = "https://onionoo.torproject.org"
        self.uptime_data = None
        self.relay_data = None
        self.processed_data = None
        
    def fetch_uptime_data(self):
        """Fetch uptime data from Onionoo API"""
        print("Fetching uptime data from Onionoo API...")
        try:
            response = requests.get(f"{self.base_url}/uptime", timeout=30)
            response.raise_for_status()
            self.uptime_data = response.json()
            print(f"Successfully fetched data for {len(self.uptime_data.get('relays', []))} relays")
            return True
        except requests.RequestException as e:
            print(f"Error fetching uptime data: {e}")
            return False
    
    def fetch_relay_details(self):
        """Fetch relay details for family analysis"""
        print("Fetching relay details...")
        try:
            response = requests.get(f"{self.base_url}/details", timeout=30)
            response.raise_for_status()
            self.relay_data = response.json()
            print(f"Successfully fetched details for {len(self.relay_data.get('relays', []))} relays")
            return True
        except requests.RequestException as e:
            print(f"Error fetching relay details: {e}")
            return False
    
    def decode_uptime_values(self, values, factor):
        """Decode uptime values from Onionoo format"""
        if not values or not factor:
            return []
        return [v * factor if v is not None else None for v in values]
    
    def process_uptime_data(self):
        """Process raw uptime data into structured format"""
        print("Processing uptime data...")
        
        if not self.uptime_data:
            print("No uptime data available")
            return False
        
        processed_relays = []
        
        for relay in self.uptime_data.get('relays', []):
            fingerprint = relay.get('fingerprint')
            uptime_info = relay.get('uptime', {})
            
            relay_data = {
                'fingerprint': fingerprint,
                'uptime_1_month': [],
                'uptime_6_months': [],
                'uptime_1_year': [],
                'uptime_5_years': [],
                'avg_uptime_1_month': None,
                'avg_uptime_6_months': None,
                'avg_uptime_1_year': None,
                'avg_uptime_5_years': None,
                'uptime_variance_1_month': None,
                'uptime_variance_6_months': None,
                'uptime_variance_1_year': None,
                'uptime_variance_5_years': None
            }
            
            # Process each time period
            for period in ['1_month', '6_months', '1_year', '5_years']:
                period_data = uptime_info.get(period, {})
                values = period_data.get('values', [])
                factor = period_data.get('factor', 1)
                
                if values and factor:
                    decoded_values = self.decode_uptime_values(values, factor)
                    # Filter out None values
                    valid_values = [v for v in decoded_values if v is not None]
                    
                    relay_data[f'uptime_{period}'] = valid_values
                    
                    if valid_values:
                        relay_data[f'avg_uptime_{period}'] = np.mean(valid_values)
                        relay_data[f'uptime_variance_{period}'] = np.var(valid_values)
            
            processed_relays.append(relay_data)
        
        self.processed_data = pd.DataFrame(processed_relays)
        print(f"Processed data for {len(self.processed_data)} relays")
        return True
    
    def identify_relay_families(self):
        """Identify relay families based on contact info"""
        if not self.relay_data:
            print("No relay details available for family analysis")
            return {}
        
        families = {}
        nothingtohide_relays = []
        oeo_relays = []
        
        for relay in self.relay_data.get('relays', []):
            fingerprint = relay.get('fingerprint')
            contact = relay.get('contact', '').lower()
            
            # Look for nothingtohide.nl family
            if 'nothingtohide' in contact or 'nothingtohide.nl' in contact:
                nothingtohide_relays.append(fingerprint)
            
            # Look for 1aeo family (various patterns)
            if ('1aeo' in contact or 'aeo' in contact or 
                'tor@1aeo' in contact or '1aeo.net' in contact):
                oeo_relays.append(fingerprint)
        
        families['nothingtohide.nl'] = nothingtohide_relays
        families['1aeo'] = oeo_relays
        
        print(f"Identified {len(nothingtohide_relays)} nothingtohide.nl relays")
        print(f"Identified {len(oeo_relays)} 1aeo relays")
        
        return families
    
    def analyze_network_trends(self):
        """Analyze overall network uptime trends"""
        print("\n=== NETWORK-WIDE TREND ANALYSIS ===")
        
        if self.processed_data is None:
            print("No processed data available")
            return
        
        # Calculate network-wide statistics
        network_stats = {}
        
        for period in ['1_month', '6_months', '1_year', '5_years']:
            avg_col = f'avg_uptime_{period}'
            valid_data = self.processed_data[avg_col].dropna()
            
            if len(valid_data) > 0:
                network_stats[period] = {
                    'mean_uptime': valid_data.mean(),
                    'median_uptime': valid_data.median(),
                    'std_uptime': valid_data.std(),
                    'min_uptime': valid_data.min(),
                    'max_uptime': valid_data.max(),
                    'q25': valid_data.quantile(0.25),
                    'q75': valid_data.quantile(0.75),
                    'relay_count': len(valid_data)
                }
        
        # Print network statistics
        for period, stats in network_stats.items():
            print(f"\n{period.replace('_', ' ').title()} Statistics:")
            print(f"  Mean Uptime: {stats['mean_uptime']:.3f}")
            print(f"  Median Uptime: {stats['median_uptime']:.3f}")
            print(f"  Std Deviation: {stats['std_uptime']:.3f}")
            print(f"  Min Uptime: {stats['min_uptime']:.3f}")
            print(f"  Max Uptime: {stats['max_uptime']:.3f}")
            print(f"  25th Percentile: {stats['q25']:.3f}")
            print(f"  75th Percentile: {stats['q75']:.3f}")
            print(f"  Relay Count: {stats['relay_count']}")
        
        return network_stats
    
    def analyze_family_trends(self, families):
        """Analyze uptime trends for specific relay families"""
        print("\n=== FAMILY-SPECIFIC TREND ANALYSIS ===")
        
        family_stats = {}
        
        for family_name, fingerprints in families.items():
            if not fingerprints:
                continue
                
            print(f"\n--- {family_name} Family Analysis ---")
            
            # Filter data for this family
            family_data = self.processed_data[
                self.processed_data['fingerprint'].isin(fingerprints)
            ]
            
            if family_data.empty:
                print(f"No uptime data found for {family_name} family")
                continue
            
            family_stats[family_name] = {}
            
            for period in ['1_month', '6_months', '1_year', '5_years']:
                avg_col = f'avg_uptime_{period}'
                valid_data = family_data[avg_col].dropna()
                
                if len(valid_data) > 0:
                    stats = {
                        'mean_uptime': valid_data.mean(),
                        'median_uptime': valid_data.median(),
                        'std_uptime': valid_data.std(),
                        'min_uptime': valid_data.min(),
                        'max_uptime': valid_data.max(),
                        'relay_count': len(valid_data)
                    }
                    
                    family_stats[family_name][period] = stats
                    
                    print(f"  {period.replace('_', ' ').title()}:")
                    print(f"    Mean Uptime: {stats['mean_uptime']:.3f}")
                    print(f"    Median Uptime: {stats['median_uptime']:.3f}")
                    print(f"    Std Deviation: {stats['std_uptime']:.3f}")
                    print(f"    Relay Count: {stats['relay_count']}")
        
        return family_stats
    
    def detect_anomalies(self):
        """Detect anomalies in uptime patterns"""
        print("\n=== ANOMALY DETECTION ===")
        
        anomalies = {}
        
        # Isolation Forest for anomaly detection
        for period in ['1_month', '6_months', '1_year', '5_years']:
            avg_col = f'avg_uptime_{period}'
            var_col = f'uptime_variance_{period}'
            
            # Prepare data for anomaly detection
            features = []
            fingerprints = []
            
            for idx, row in self.processed_data.iterrows():
                if pd.notna(row[avg_col]) and pd.notna(row[var_col]):
                    features.append([row[avg_col], row[var_col]])
                    fingerprints.append(row['fingerprint'])
            
            if len(features) < 10:  # Need minimum samples
                continue
            
            features = np.array(features)
            
            # Standardize features
            scaler = StandardScaler()
            features_scaled = scaler.fit_transform(features)
            
            # Apply Isolation Forest
            iso_forest = IsolationForest(contamination=0.1, random_state=42)
            anomaly_labels = iso_forest.fit_predict(features_scaled)
            
            # Identify anomalies
            anomaly_indices = np.where(anomaly_labels == -1)[0]
            
            period_anomalies = []
            for idx in anomaly_indices:
                period_anomalies.append({
                    'fingerprint': fingerprints[idx],
                    'avg_uptime': features[idx][0],
                    'uptime_variance': features[idx][1],
                    'anomaly_score': iso_forest.decision_function(features_scaled[idx:idx+1])[0]
                })
            
            anomalies[period] = period_anomalies
            
            print(f"\n{period.replace('_', ' ').title()} Anomalies:")
            print(f"  Detected {len(period_anomalies)} anomalous relays")
            
            # Show top 5 anomalies
            sorted_anomalies = sorted(period_anomalies, key=lambda x: x['anomaly_score'])
            for i, anomaly in enumerate(sorted_anomalies[:5]):
                print(f"  {i+1}. {anomaly['fingerprint'][:16]}...")
                print(f"     Avg Uptime: {anomaly['avg_uptime']:.3f}")
                print(f"     Variance: {anomaly['uptime_variance']:.6f}")
                print(f"     Anomaly Score: {anomaly['anomaly_score']:.3f}")
        
        return anomalies
    
    def statistical_analysis(self):
        """Perform statistical analysis on uptime data"""
        print("\n=== STATISTICAL ANALYSIS ===")
        
        # Correlation analysis between different time periods
        correlation_data = []
        periods = ['1_month', '6_months', '1_year', '5_years']
        
        for period in periods:
            avg_col = f'avg_uptime_{period}'
            valid_data = self.processed_data[avg_col].dropna()
            if len(valid_data) > 0:
                correlation_data.append(valid_data)
        
        if len(correlation_data) >= 2:
            # Create correlation matrix
            corr_df = pd.DataFrame()
            for i, period in enumerate(periods):
                if i < len(correlation_data):
                    corr_df[period] = correlation_data[i]
            
            correlation_matrix = corr_df.corr()
            print("\nCorrelation Matrix (Uptime across time periods):")
            print(correlation_matrix.round(3))
        
        # Distribution analysis
        print("\n--- Distribution Analysis ---")
        for period in periods:
            avg_col = f'avg_uptime_{period}'
            valid_data = self.processed_data[avg_col].dropna()
            
            if len(valid_data) > 10:
                # Normality test
                stat, p_value = stats.shapiro(valid_data[:5000])  # Shapiro-Wilk test (max 5000 samples)
                print(f"\n{period.replace('_', ' ').title()} Distribution:")
                print(f"  Shapiro-Wilk test p-value: {p_value:.6f}")
                print(f"  Normal distribution: {'Yes' if p_value > 0.05 else 'No'}")
                
                # Skewness and kurtosis
                skewness = stats.skew(valid_data)
                kurtosis = stats.kurtosis(valid_data)
                print(f"  Skewness: {skewness:.3f}")
                print(f"  Kurtosis: {kurtosis:.3f}")
    
    def create_visualizations(self):
        """Create visualizations for the analysis"""
        print("\n=== CREATING VISUALIZATIONS ===")
        
        # Set up the plotting style
        plt.style.use('seaborn-v0_8')
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Onionoo Uptime Analysis', fontsize=16, fontweight='bold')
        
        periods = ['1_month', '6_months', '1_year', '5_years']
        
        # Plot 1: Distribution of average uptime across time periods
        ax1 = axes[0, 0]
        uptime_data = []
        labels = []
        
        for period in periods:
            avg_col = f'avg_uptime_{period}'
            valid_data = self.processed_data[avg_col].dropna()
            if len(valid_data) > 0:
                uptime_data.append(valid_data)
                labels.append(period.replace('_', ' ').title())
        
        if uptime_data:
            ax1.boxplot(uptime_data, labels=labels)
            ax1.set_title('Uptime Distribution by Time Period')
            ax1.set_ylabel('Average Uptime')
            ax1.tick_params(axis='x', rotation=45)
        
        # Plot 2: Histogram of 1-month uptime
        ax2 = axes[0, 1]
        month_data = self.processed_data['avg_uptime_1_month'].dropna()
        if len(month_data) > 0:
            ax2.hist(month_data, bins=50, alpha=0.7, edgecolor='black')
            ax2.set_title('1-Month Uptime Distribution')
            ax2.set_xlabel('Average Uptime')
            ax2.set_ylabel('Frequency')
        
        # Plot 3: Scatter plot of uptime vs variance
        ax3 = axes[1, 0]
        avg_data = self.processed_data['avg_uptime_1_month'].dropna()
        var_data = self.processed_data['uptime_variance_1_month'].dropna()
        
        # Find common indices
        common_indices = avg_data.index.intersection(var_data.index)
        if len(common_indices) > 0:
            ax3.scatter(avg_data[common_indices], var_data[common_indices], alpha=0.6)
            ax3.set_title('Uptime vs Variance (1 Month)')
            ax3.set_xlabel('Average Uptime')
            ax3.set_ylabel('Uptime Variance')
        
        # Plot 4: Time series comparison
        ax4 = axes[1, 1]
        period_means = []
        period_labels = []
        
        for period in periods:
            avg_col = f'avg_uptime_{period}'
            valid_data = self.processed_data[avg_col].dropna()
            if len(valid_data) > 0:
                period_means.append(valid_data.mean())
                period_labels.append(period.replace('_', ' ').title())
        
        if period_means:
            ax4.plot(period_labels, period_means, marker='o', linewidth=2, markersize=8)
            ax4.set_title('Average Network Uptime by Time Period')
            ax4.set_ylabel('Mean Uptime')
            ax4.tick_params(axis='x', rotation=45)
            ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig('onionoo_uptime_analysis.png', dpi=300, bbox_inches='tight')
        print("Visualizations saved as 'onionoo_uptime_analysis.png'")
        
        return fig
    
    def generate_report(self, network_stats, family_stats, anomalies):
        """Generate a comprehensive analysis report"""
        print("\n=== GENERATING COMPREHENSIVE REPORT ===")
        
        report = []
        report.append("# Onionoo Uptime Trend Analysis and Anomaly Detection Report")
        report.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Executive Summary
        report.append("## Executive Summary")
        report.append("")
        
        if network_stats:
            latest_period = '1_month'
            if latest_period in network_stats:
                stats = network_stats[latest_period]
                report.append(f"- **Network Overview**: {stats['relay_count']} relays analyzed")
                report.append(f"- **Average Uptime (1 month)**: {stats['mean_uptime']:.1%}")
                report.append(f"- **Median Uptime (1 month)**: {stats['median_uptime']:.1%}")
                report.append(f"- **Uptime Variability**: σ = {stats['std_uptime']:.3f}")
        
        total_anomalies = sum(len(anomalies.get(period, [])) for period in anomalies)
        report.append(f"- **Anomalies Detected**: {total_anomalies} across all time periods")
        report.append("")
        
        # Network-wide Analysis
        report.append("## Network-wide Trend Analysis")
        report.append("")
        
        if network_stats:
            for period, stats in network_stats.items():
                report.append(f"### {period.replace('_', ' ').title()}")
                report.append(f"- **Relay Count**: {stats['relay_count']}")
                report.append(f"- **Mean Uptime**: {stats['mean_uptime']:.1%}")
                report.append(f"- **Median Uptime**: {stats['median_uptime']:.1%}")
                report.append(f"- **Standard Deviation**: {stats['std_uptime']:.3f}")
                report.append(f"- **Range**: {stats['min_uptime']:.1%} - {stats['max_uptime']:.1%}")
                report.append(f"- **Interquartile Range**: {stats['q25']:.1%} - {stats['q75']:.1%}")
                report.append("")
        
        # Family Analysis
        report.append("## Relay Family Analysis")
        report.append("")
        
        if family_stats:
            for family_name, family_data in family_stats.items():
                report.append(f"### {family_name}")
                report.append("")
                
                for period, stats in family_data.items():
                    report.append(f"**{period.replace('_', ' ').title()}**:")
                    report.append(f"- Relay Count: {stats['relay_count']}")
                    report.append(f"- Mean Uptime: {stats['mean_uptime']:.1%}")
                    report.append(f"- Median Uptime: {stats['median_uptime']:.1%}")
                    report.append(f"- Standard Deviation: {stats['std_uptime']:.3f}")
                    report.append("")
        else:
            report.append("No family data available for analysis.")
            report.append("")
        
        # Anomaly Detection
        report.append("## Anomaly Detection Results")
        report.append("")
        
        if anomalies:
            for period, period_anomalies in anomalies.items():
                if period_anomalies:
                    report.append(f"### {period.replace('_', ' ').title()}")
                    report.append(f"Detected {len(period_anomalies)} anomalous relays:")
                    report.append("")
                    
                    # Show top 10 anomalies
                    sorted_anomalies = sorted(period_anomalies, key=lambda x: x['anomaly_score'])
                    for i, anomaly in enumerate(sorted_anomalies[:10]):
                        report.append(f"{i+1}. **{anomaly['fingerprint'][:16]}...**")
                        report.append(f"   - Average Uptime: {anomaly['avg_uptime']:.1%}")
                        report.append(f"   - Uptime Variance: {anomaly['uptime_variance']:.6f}")
                        report.append(f"   - Anomaly Score: {anomaly['anomaly_score']:.3f}")
                        report.append("")
        
        # Key Findings
        report.append("## Key Findings")
        report.append("")
        
        findings = []
        
        # Network health assessment
        if network_stats and '1_month' in network_stats:
            mean_uptime = network_stats['1_month']['mean_uptime']
            if mean_uptime > 0.95:
                findings.append("✅ **Network Health**: Excellent - High average uptime across the network")
            elif mean_uptime > 0.90:
                findings.append("⚠️ **Network Health**: Good - Moderate uptime performance")
            else:
                findings.append("❌ **Network Health**: Concerning - Low average uptime detected")
        
        # Stability assessment
        if network_stats:
            periods = ['1_month', '6_months', '1_year', '5_years']
            available_periods = [p for p in periods if p in network_stats]
            if len(available_periods) >= 2:
                recent_std = network_stats[available_periods[0]]['std_uptime']
                if recent_std < 0.1:
                    findings.append("✅ **Network Stability**: High - Low variance in uptime")
                elif recent_std < 0.2:
                    findings.append("⚠️ **Network Stability**: Moderate - Some uptime variance")
                else:
                    findings.append("❌ **Network Stability**: Low - High uptime variance detected")
        
        # Anomaly assessment
        if anomalies:
            total_anomalies = sum(len(anomalies.get(period, [])) for period in anomalies)
            total_relays = len(self.processed_data)
            anomaly_rate = total_anomalies / total_relays if total_relays > 0 else 0
            
            if anomaly_rate < 0.05:
                findings.append("✅ **Anomaly Rate**: Low - Few unusual uptime patterns detected")
            elif anomaly_rate < 0.15:
                findings.append("⚠️ **Anomaly Rate**: Moderate - Some relays showing unusual patterns")
            else:
                findings.append("❌ **Anomaly Rate**: High - Many relays showing unusual uptime patterns")
        
        for finding in findings:
            report.append(f"- {finding}")
        
        report.append("")
        
        # Recommendations
        report.append("## Recommendations")
        report.append("")
        report.append("1. **Monitor Anomalous Relays**: Investigate relays with unusual uptime patterns")
        report.append("2. **Family Performance**: Compare family performance against network averages")
        report.append("3. **Trend Monitoring**: Establish baseline metrics for ongoing monitoring")
        report.append("4. **Capacity Planning**: Use uptime trends to inform network capacity decisions")
        report.append("")
        
        # Technical Notes
        report.append("## Technical Notes")
        report.append("")
        report.append("- **Data Source**: Onionoo API (https://onionoo.torproject.org/)")
        report.append("- **Anomaly Detection**: Isolation Forest algorithm with 10% contamination threshold")
        report.append("- **Uptime Encoding**: Values decoded using factor provided by API (999 = 99.9%)")
        report.append("- **Family Identification**: Based on contact information patterns")
        report.append("")
        
        # Save report
        report_content = "\n".join(report)
        with open('onionoo_uptime_analysis_report.md', 'w') as f:
            f.write(report_content)
        
        print("Report saved as 'onionoo_uptime_analysis_report.md'")
        return report_content
    
    def run_full_analysis(self):
        """Run the complete analysis pipeline"""
        print("Starting comprehensive Onionoo uptime analysis...")
        print("=" * 60)
        
        # Step 1: Fetch data
        if not self.fetch_uptime_data():
            return False
        
        if not self.fetch_relay_details():
            print("Warning: Could not fetch relay details, family analysis will be limited")
        
        # Step 2: Process data
        if not self.process_uptime_data():
            return False
        
        # Step 3: Identify families
        families = self.identify_relay_families()
        
        # Step 4: Analyze trends
        network_stats = self.analyze_network_trends()
        family_stats = self.analyze_family_trends(families)
        
        # Step 5: Detect anomalies
        anomalies = self.detect_anomalies()
        
        # Step 6: Statistical analysis
        self.statistical_analysis()
        
        # Step 7: Create visualizations
        self.create_visualizations()
        
        # Step 8: Generate report
        self.generate_report(network_stats, family_stats, anomalies)
        
        print("\n" + "=" * 60)
        print("Analysis complete! Check the generated files:")
        print("- onionoo_uptime_analysis.png (visualizations)")
        print("- onionoo_uptime_analysis_report.md (comprehensive report)")
        
        return True

def main():
    """Main function to run the analysis"""
    analyzer = OnionooUptimeAnalyzer()
    
    try:
        success = analyzer.run_full_analysis()
        if success:
            print("\n✅ Analysis completed successfully!")
        else:
            print("\n❌ Analysis failed!")
            return 1
    except KeyboardInterrupt:
        print("\n⚠️ Analysis interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Analysis failed with error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())