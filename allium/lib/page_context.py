#!/usr/bin/env python3
"""
Page Context Generation Module - consolidates all page context creation patterns.

This module provides:
- Unified page context generation for all page types
- Template variable standardization
- Common context mapping patterns
- Centralized breadcrumb management
"""

from typing import Any, Dict, Optional


class PageContextGenerator:
    """Centralized page context generation for all Allium page types."""
    
    def __init__(self, relays_instance=None):
        """Initialize with optional relays instance for advanced context generation."""
        self.relays = relays_instance
        
        # Standard path prefixes for different page types
        self.path_prefixes = {
            'index': './',
            'misc': '../',
            'detail': '../../',
            'relay': '../../'
        }
        
        # Breadcrumb type mappings for detail pages
        self.detail_breadcrumb_mapping = {
            'as': ('as_detail', 'as_number'),
            'contact': ('contact_detail', 'contact_hash'),
            'country': ('country_detail', 'country_name'),
            'family': ('family_detail', 'family_hash'),
            'platform': ('platform_detail', 'platform_name'),
            'first_seen': ('first_seen_detail', 'date'),
            'flag': ('flag_detail', 'flag_name'),
        }
    
    def get_base_context(self, page_type: str, breadcrumb_type: Optional[str] = None, 
                        breadcrumb_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get base page context with path_prefix and breadcrumb info."""
        ctx = {
            'path_prefix': self.path_prefixes.get(page_type, self.path_prefixes['misc'])
        }
        
        # Add breadcrumb information if provided
        if breadcrumb_type:
            ctx['breadcrumb_type'] = breadcrumb_type
            ctx['breadcrumb_data'] = breadcrumb_data or {}
        
        return ctx
    
    def get_misc_context(self, page_name: str) -> Dict[str, Any]:
        """Get context for miscellaneous pages."""
        return self.get_base_context('misc', 'misc_listing', {'page_name': page_name})
    
    def get_detail_context(self, category: str, value: str,
                           display_value: str = None) -> Dict[str, Any]:
        """Get context for detail pages with proper breadcrumb mapping.

        display_value, when given, is shown in the breadcrumb instead of
        the raw sorted key (e.g. 'United States' instead of 'US').
        """
        breadcrumb_type, data_key = self.detail_breadcrumb_mapping.get(
            category, (f"{category}_detail", category)
        )
        breadcrumb_data = {data_key: display_value or value}
        return self.get_base_context('detail', breadcrumb_type, breadcrumb_data)
    
    def get_relay_context(self, relay_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get context for individual relay pages."""
        return self.get_base_context('detail', 'relay_detail', {
            'nickname': relay_data.get('nickname', relay_data.get('fingerprint', 'Unknown')),
            'fingerprint': relay_data.get('fingerprint', 'Unknown'),
            'as_number': relay_data.get('as', '')
        })
    
    def get_index_context(self, page_name: Optional[str] = None) -> Dict[str, Any]:
        """Get context for index pages."""
        ctx = self.get_base_context('index', 'home')
        if page_name:
            ctx['breadcrumb_data'] = {'page_name': page_name}
        return ctx


class StandardTemplateContexts:
    """Pre-configured template contexts for common page types."""
    
    def __init__(self, relays_instance=None):
        """Initialize with relays instance."""
        self.relays = relays_instance
        self.context_generator = PageContextGenerator(relays_instance)
    
    def get_misc_page_context(self, template_name: str, page_name: str, 
                             sorted_by: Optional[str] = None, reverse: bool = True,
                             is_index: bool = False) -> Dict[str, Any]:
        """Get standard context for miscellaneous pages."""
        context = self.context_generator.get_misc_context(page_name)
        if self.relays:
            context['relays'] = self.relays
        context.update({
            'sorted_by': sorted_by,
            'reverse': reverse,
            'is_index': is_index
        })

        # Template-specific context
        if template_name == "misc-families.html" and self.relays:
            context.update(self.relays.json.get('family_statistics', {
                'centralization_percentage': '0.0',
                'largest_family_size': 0,
                'large_family_count': 0
            }))
        elif template_name == "misc-authorities.html" and self.relays:
            context.update(self.relays._get_directory_authorities_data())

        return context
    
    def get_detail_page_context(self, category: str, value: str, 
                               page_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get standard context for detail pages."""
        context = self.context_generator.get_detail_context(category, value)
        if self.relays:
            context['relays'] = self.relays

        # Page-specific data
        if 'bandwidth_data' in page_data:
            bandwidth_data = page_data['bandwidth_data']
            context.update({
                'bandwidth': bandwidth_data.get('bandwidth'),
                'bandwidth_unit': bandwidth_data.get('bandwidth_unit'),
                'guard_bandwidth': bandwidth_data.get('guard_bandwidth'),
                'middle_bandwidth': bandwidth_data.get('middle_bandwidth'),
                'exit_bandwidth': bandwidth_data.get('exit_bandwidth')
            })

        if 'consensus_weight_data' in page_data:
            weight_data = page_data['consensus_weight_data']
            context.update({
                'consensus_weight_fraction': weight_data.get('consensus_weight_fraction'),
                'guard_consensus_weight_fraction': weight_data.get('guard_consensus_weight_fraction'),
                'middle_consensus_weight_fraction': weight_data.get('middle_consensus_weight_fraction'),
                'exit_consensus_weight_fraction': weight_data.get('exit_consensus_weight_fraction')
            })

        if 'count_data' in page_data:
            count_data = page_data['count_data']
            context.update({
                'exit_count': count_data.get('exit_count', 0),
                'guard_count': count_data.get('guard_count', 0),
                'middle_count': count_data.get('middle_count', 0)
            })

        if 'network_position' in page_data:
            context['network_position'] = page_data['network_position']

        if 'contact_data' in page_data and category == 'contact':
            contact_data = page_data['contact_data']
            context.update({
                'contact_rankings': contact_data.get('contact_rankings', []),
                'operator_reliability': contact_data.get('operator_reliability'),
                'contact_display_data': contact_data.get('contact_display_data'),
                'primary_country_data': contact_data.get('primary_country_data')
            })

        if 'template_optimizations' in page_data:
            optimization_data = page_data['template_optimizations']
            context.update({
                'consensus_weight_percentage': optimization_data.get('consensus_weight_percentage'),
                'guard_consensus_weight_percentage': optimization_data.get('guard_consensus_weight_percentage'),
                'middle_consensus_weight_percentage': optimization_data.get('middle_consensus_weight_percentage'),
                'exit_consensus_weight_percentage': optimization_data.get('exit_consensus_weight_percentage'),
                'guard_relay_text': optimization_data.get('guard_relay_text'),
                'middle_relay_text': optimization_data.get('middle_relay_text'),
                'exit_relay_text': optimization_data.get('exit_relay_text'),
                'has_guard': optimization_data.get('has_guard', False),
                'has_middle': optimization_data.get('has_middle', False),
                'has_exit': optimization_data.get('has_exit', False),
                'has_typed_relays': optimization_data.get('has_typed_relays', False)
            })

        # Common variables
        context.update({
            'key': category,
            'value': value,
            'is_index': False
        })

        return context

    def get_relay_page_context(self, relay_data: Dict[str, Any], 
                              contact_display_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get standard context for relay pages."""
        context = self.context_generator.get_relay_context(relay_data)
        if self.relays:
            context['relays'] = self.relays
        context.update({
            'relay': relay_data,
            'contact_display_data': contact_display_data
        })
        return context
    
    def get_index_page_context(self, page_name: Optional[str] = None,
                              timestamp: Optional[str] = None) -> Dict[str, Any]:
        """Get standard context for index pages."""
        context = self.context_generator.get_index_context(page_name)
        if self.relays:
            context['relays'] = self.relays
        if timestamp:
            context['timestamp_str'] = timestamp
        return context


# Convenience functions for backward compatibility
def get_page_context(page_type: str, breadcrumb_type: Optional[str] = None, 
                    breadcrumb_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get page context with path_prefix and breadcrumb info for different page types."""
    generator = PageContextGenerator()
    return generator.get_base_context(page_type, breadcrumb_type, breadcrumb_data)


def get_misc_page_context(page_name: str) -> Dict[str, Any]:
    """Helper function for creating misc page contexts with consistent structure."""
    generator = PageContextGenerator()
    return generator.get_misc_context(page_name)


def get_detail_page_context(category: str, value: str,
                            display_value: str = None) -> Dict[str, Any]:
    """Helper function for creating detail page contexts with consistent structure."""
    generator = PageContextGenerator()
    return generator.get_detail_context(category, value, display_value)

