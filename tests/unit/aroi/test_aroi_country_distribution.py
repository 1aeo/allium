#!/usr/bin/env python3
"""
Test: Geographic AROI Operator Distribution
Tests top 3 countries by validated AROI operator count calculation
"""

import unittest
from allium.lib.aroi_validation import calculate_aroi_validation_metrics


class TestAROICountryDistribution(unittest.TestCase):
    """Test geographic distribution of validated AROI operators."""
    
    def test_top_3_countries_basic(self):
        """Test basic top 3 countries calculation with clear distribution."""
        # Mock relays with AROI domains from different countries
        relays = [
            # Germany - 3 operators (domains: de1, de2, de3)
            {'fingerprint': 'DE1A', 'aroi_domain': 'de1.example', 'country': 'de'},
            {'fingerprint': 'DE1B', 'aroi_domain': 'de1.example', 'country': 'de'},
            {'fingerprint': 'DE2A', 'aroi_domain': 'de2.example', 'country': 'de'},
            {'fingerprint': 'DE3A', 'aroi_domain': 'de3.example', 'country': 'de'},
            
            # United States - 2 operators (domains: us1, us2)
            {'fingerprint': 'US1A', 'aroi_domain': 'us1.example', 'country': 'us'},
            {'fingerprint': 'US2A', 'aroi_domain': 'us2.example', 'country': 'us'},
            
            # Netherlands - 1 operator (domain: nl1)
            {'fingerprint': 'NL1A', 'aroi_domain': 'nl1.example', 'country': 'nl'},
            
            # France - 1 operator (domain: fr1)
            {'fingerprint': 'FR1A', 'aroi_domain': 'fr1.example', 'country': 'fr'},
        ]
        
        # Mock validation data - all validated
        validation_data = {
            'metadata': {'timestamp': '2025-11-29T00:00:00Z'},
            'statistics': {'proof_types': {}},
            'results': [
                {'fingerprint': 'DE1A', 'valid': True},
                {'fingerprint': 'DE1B', 'valid': True},
                {'fingerprint': 'DE2A', 'valid': True},
                {'fingerprint': 'DE3A', 'valid': True},
                {'fingerprint': 'US1A', 'valid': True},
                {'fingerprint': 'US2A', 'valid': True},
                {'fingerprint': 'NL1A', 'valid': True},
                {'fingerprint': 'FR1A', 'valid': True},
            ]
        }
        
        metrics = calculate_aroi_validation_metrics(relays, validation_data, 
                                                     calculate_operator_metrics=True)
        
        # Check top 3 countries returned
        self.assertIn('top_3_aroi_countries', metrics)
        top_3 = metrics['top_3_aroi_countries']
        
        self.assertEqual(len(top_3), 3, "Should return exactly 3 countries")
        
        # Check rank 1 (Germany with 3 operators)
        # Note: country codes are stored as provided in relay data (lowercase)
        self.assertEqual(top_3[0]['rank'], 1)
        self.assertEqual(top_3[0]['country_code'], 'de')
        self.assertEqual(top_3[0]['count'], 3)
        self.assertAlmostEqual(top_3[0]['percentage'], 42.857, places=1)  # 3/7 = 42.857%
        
        # Check rank 2 (US with 2 operators)
        self.assertEqual(top_3[1]['rank'], 2)
        self.assertEqual(top_3[1]['country_code'], 'us')
        self.assertEqual(top_3[1]['count'], 2)
        self.assertAlmostEqual(top_3[1]['percentage'], 28.571, places=1)  # 2/7 = 28.571%
        
        # Check rank 3 (NL or FR with 1 operator - could be either)
        self.assertEqual(top_3[2]['rank'], 3)
        self.assertIn(top_3[2]['country_code'], ['nl', 'fr'])
        self.assertEqual(top_3[2]['count'], 1)
        self.assertAlmostEqual(top_3[2]['percentage'], 14.285, places=1)  # 1/7 = 14.285%
    
    def test_top_3_countries_with_invalid_operators(self):
        """Test that only validated operators are counted."""
        relays = [
            # DE - 2 valid, 1 invalid
            {'fingerprint': 'DE1A', 'aroi_domain': 'de1.example', 'country': 'de'},
            {'fingerprint': 'DE2A', 'aroi_domain': 'de2.example', 'country': 'de'},
            {'fingerprint': 'DE3A', 'aroi_domain': 'de3.example', 'country': 'de'},
            
            # US - 1 valid, 1 invalid
            {'fingerprint': 'US1A', 'aroi_domain': 'us1.example', 'country': 'us'},
            {'fingerprint': 'US2A', 'aroi_domain': 'us2.example', 'country': 'us'},
        ]
        
        validation_data = {
            'metadata': {'timestamp': '2025-11-29T00:00:00Z'},
            'statistics': {'proof_types': {}},
            'results': [
                {'fingerprint': 'DE1A', 'valid': True},
                {'fingerprint': 'DE2A', 'valid': True},
                {'fingerprint': 'DE3A', 'valid': False, 'error': 'DNS lookup failed'},  # Invalid
                {'fingerprint': 'US1A', 'valid': True},
                {'fingerprint': 'US2A', 'valid': False, 'error': 'Connection error'},  # Invalid
            ]
        }
        
        metrics = calculate_aroi_validation_metrics(relays, validation_data,
                                                     calculate_operator_metrics=True)
        
        top_3 = metrics['top_3_aroi_countries']
        
        # Should only count validated: de=2, us=1
        self.assertEqual(top_3[0]['country_code'], 'de')
        self.assertEqual(top_3[0]['count'], 2)
        self.assertEqual(top_3[1]['country_code'], 'us')
        self.assertEqual(top_3[1]['count'], 1)
    
    def test_top_3_countries_fewer_than_three(self):
        """Test when there are fewer than 3 countries with validated operators."""
        relays = [
            {'fingerprint': 'DE1A', 'aroi_domain': 'de1.example', 'country': 'de'},
            {'fingerprint': 'US1A', 'aroi_domain': 'us1.example', 'country': 'us'},
        ]
        
        validation_data = {
            'metadata': {'timestamp': '2025-11-29T00:00:00Z'},
            'statistics': {'proof_types': {}},
            'results': [
                {'fingerprint': 'DE1A', 'valid': True},
                {'fingerprint': 'US1A', 'valid': True},
            ]
        }
        
        metrics = calculate_aroi_validation_metrics(relays, validation_data,
                                                     calculate_operator_metrics=True)
        
        top_3 = metrics['top_3_aroi_countries']
        
        # Should return only 2 countries
        self.assertEqual(len(top_3), 2)
        self.assertEqual(top_3[0]['rank'], 1)
        self.assertEqual(top_3[1]['rank'], 2)
    
    def test_top_3_countries_no_validation_data(self):
        """Test graceful handling when no validation data available."""
        relays = [
            {'fingerprint': 'DE1A', 'aroi_domain': 'de1.example', 'country': 'de'},
        ]
        
        metrics = calculate_aroi_validation_metrics(relays, None,
                                                     calculate_operator_metrics=True)
        
        # Should return empty list
        self.assertIn('top_3_aroi_countries', metrics)
        self.assertEqual(metrics['top_3_aroi_countries'], [])
    
    def test_top_3_countries_missing_country_data(self):
        """Test handling of relays with missing country information."""
        relays = [
            {'fingerprint': 'DE1A', 'aroi_domain': 'de1.example', 'country': 'de'},
            {'fingerprint': 'XX1A', 'aroi_domain': 'unknown.example'},  # Missing country
            {'fingerprint': 'XX2A', 'aroi_domain': 'unknown2.example', 'country': 'unknown'},  # Unknown country
        ]
        
        validation_data = {
            'metadata': {'timestamp': '2025-11-29T00:00:00Z'},
            'statistics': {'proof_types': {}},
            'results': [
                {'fingerprint': 'DE1A', 'valid': True},
                {'fingerprint': 'XX1A', 'valid': True},
                {'fingerprint': 'XX2A', 'valid': True},
            ]
        }
        
        metrics = calculate_aroi_validation_metrics(relays, validation_data,
                                                     calculate_operator_metrics=True)
        
        top_3 = metrics['top_3_aroi_countries']
        
        # Should only include de (others have missing/invalid country)
        self.assertEqual(len(top_3), 1)
        self.assertEqual(top_3[0]['country_code'], 'de')
        self.assertEqual(top_3[0]['count'], 1)
    
    def test_top_3_countries_operator_metrics_disabled(self):
        """Test that top_3_aroi_countries is empty when operator metrics disabled."""
        relays = [
            {'fingerprint': 'DE1A', 'aroi_domain': 'de1.example', 'country': 'de'},
        ]
        
        validation_data = {
            'metadata': {'timestamp': '2025-11-29T00:00:00Z'},
            'statistics': {'proof_types': {}},
            'results': [
                {'fingerprint': 'DE1A', 'valid': True},
            ]
        }
        
        metrics = calculate_aroi_validation_metrics(relays, validation_data,
                                                     calculate_operator_metrics=False)
        
        # Should have default empty list
        self.assertIn('top_3_aroi_countries', metrics)
        self.assertEqual(metrics['top_3_aroi_countries'], [])
    
    def test_top_3_countries_percentage_calculation(self):
        """Test percentage calculations are accurate."""
        # Create 10 operators across 3 countries
        relays = []
        validation_results = []
        
        # 5 in DE
        for i in range(5):
            fp = f'DE{i}A'
            domain = f'de{i}.example'
            relays.append({'fingerprint': fp, 'aroi_domain': domain, 'country': 'de'})
            validation_results.append({'fingerprint': fp, 'valid': True})
        
        # 3 in US
        for i in range(3):
            fp = f'US{i}A'
            domain = f'us{i}.example'
            relays.append({'fingerprint': fp, 'aroi_domain': domain, 'country': 'us'})
            validation_results.append({'fingerprint': fp, 'valid': True})
        
        # 2 in NL
        for i in range(2):
            fp = f'NL{i}A'
            domain = f'nl{i}.example'
            relays.append({'fingerprint': fp, 'aroi_domain': domain, 'country': 'nl'})
            validation_results.append({'fingerprint': fp, 'valid': True})
        
        validation_data = {
            'metadata': {'timestamp': '2025-11-29T00:00:00Z'},
            'statistics': {'proof_types': {}},
            'results': validation_results
        }
        
        metrics = calculate_aroi_validation_metrics(relays, validation_data,
                                                     calculate_operator_metrics=True)
        
        top_3 = metrics['top_3_aroi_countries']
        
        # de: 5/10 = 50%
        self.assertEqual(top_3[0]['country_code'], 'de')
        self.assertAlmostEqual(top_3[0]['percentage'], 50.0, places=1)
        
        # us: 3/10 = 30%
        self.assertEqual(top_3[1]['country_code'], 'us')
        self.assertAlmostEqual(top_3[1]['percentage'], 30.0, places=1)
        
        # nl: 2/10 = 20%
        self.assertEqual(top_3[2]['country_code'], 'nl')
        self.assertAlmostEqual(top_3[2]['percentage'], 20.0, places=1)


if __name__ == '__main__':
    unittest.main()

