#!/usr/bin/env python3
"""
Page Context Generation Module - consolidates all page context creation patterns.

This module provides:
- Unified page context generation for all page types
- Template variable standardization
- Common context mapping patterns
- Centralized breadcrumb management
"""

from typing import Any, Dict, Optional, Union
import os


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
    
    def get_detail_context(self, category: str, value: str) -> Dict[str, Any]:
        """Get context for detail pages with proper breadcrumb mapping."""
        breadcrumb_type, data_key = self.detail_breadcrumb_mapping.get(
            category, (f"{category}_detail", category)
        )
        breadcrumb_data = {data_key: value}
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


class TemplateContextBuilder:
    """Builder class for constructing complete template contexts."""
    
    def __init__(self, relays_instance=None):
        """Initialize with relays instance for accessing data."""
        self.relays = relays_instance
        self.context_generator = PageContextGenerator(relays_instance)
        self.context = {}
    
    def set_base_context(self, page_type: str, breadcrumb_type: Optional[str] = None,
                        breadcrumb_data: Optional[Dict[str, Any]] = None) -> 'TemplateContextBuilder':
        """Set base page context."""
        self.context.update(self.context_generator.get_base_context(
            page_type, breadcrumb_type, breadcrumb_data
        ))
        return self
    
    def add_relays_context(self, relays_instance=None) -> 'TemplateContextBuilder':
        """Add relays instance to context."""
        relays = relays_instance or self.relays
        if relays:
            self.context['relays'] = relays
        return self
    
    def add_pagination_context(self, sorted_by: Optional[str] = None, 
                             reverse: bool = True, is_index: bool = False) -> 'TemplateContextBuilder':
        """Add pagination-related context."""
        self.context.update({
            'sorted_by': sorted_by,
            'reverse': reverse,
            'is_index': is_index
        })
        return self
    
    def add_bandwidth_context(self, bandwidth_data: Dict[str, Any]) -> 'TemplateContextBuilder':
        """Add bandwidth-related context."""
        self.context.update({
            'bandwidth': bandwidth_data.get('bandwidth'),
            'bandwidth_unit': bandwidth_data.get('bandwidth_unit'),
            'guard_bandwidth': bandwidth_data.get('guard_bandwidth'),
            'middle_bandwidth': bandwidth_data.get('middle_bandwidth'),
            'exit_bandwidth': bandwidth_data.get('exit_bandwidth')
        })
        return self
    
    def add_consensus_weight_context(self, weight_data: Dict[str, Any]) -> 'TemplateContextBuilder':
        """Add consensus weight-related context."""
        self.context.update({
            'consensus_weight_fraction': weight_data.get('consensus_weight_fraction'),
            'guard_consensus_weight_fraction': weight_data.get('guard_consensus_weight_fraction'),
            'middle_consensus_weight_fraction': weight_data.get('middle_consensus_weight_fraction'),
            'exit_consensus_weight_fraction': weight_data.get('exit_consensus_weight_fraction')
        })
        return self
    
    def add_relay_counts_context(self, count_data: Dict[str, int]) -> 'TemplateContextBuilder':
        """Add relay count-related context."""
        self.context.update({
            'exit_count': count_data.get('exit_count', 0),
            'guard_count': count_data.get('guard_count', 0),
            'middle_count': count_data.get('middle_count', 0)
        })
        return self
    
    def add_network_position_context(self, network_position: Dict[str, Any]) -> 'TemplateContextBuilder':
        """Add network position context."""
        self.context['network_position'] = network_position
        return self
    
    def add_contact_context(self, contact_data: Dict[str, Any]) -> 'TemplateContextBuilder':
        """Add contact-specific context."""
        self.context.update({
            'contact_rankings': contact_data.get('contact_rankings', []),
            'operator_reliability': contact_data.get('operator_reliability'),
            'contact_display_data': contact_data.get('contact_display_data'),
            'primary_country_data': contact_data.get('primary_country_data')
        })
        return self
    
    def add_template_optimizations(self, optimization_data: Dict[str, Any]) -> 'TemplateContextBuilder':
        """Add template optimization context (pre-computed values)."""
        self.context.update({
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
        return self
    
    def add_misc_context(self, misc_data: Dict[str, Any]) -> 'TemplateContextBuilder':
        """Add miscellaneous context data."""
        self.context.update(misc_data)
        return self
    
    def add_timestamp_context(self, timestamp: str) -> 'TemplateContextBuilder':
        """Add timestamp context."""
        self.context['timestamp_str'] = timestamp
        return self
    
    def build(self) -> Dict[str, Any]:
        """Build and return the complete template context."""
        return self.context.copy()


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
        builder = TemplateContextBuilder(self.relays)
        
        # Add misc page context
        misc_ctx = self.context_generator.get_misc_context(page_name)
        builder.context.update(misc_ctx)
        
        # Add relays and pagination
        builder.add_relays_context().add_pagination_context(sorted_by, reverse, is_index)
        
        # Add template-specific context
        if template_name == "misc-families.html" and self.relays:
            family_stats = self.relays.json.get('family_statistics', {
                'centralization_percentage': '0.0',
                'largest_family_size': 0,
                'large_family_count': 0
            })
            builder.add_misc_context(family_stats)
        elif template_name == "misc-authorities.html" and self.relays:
            authorities_data = self.relays._get_directory_authorities_data()
            builder.add_misc_context(authorities_data)
        
        return builder.build()
    
    def get_detail_page_context(self, category: str, value: str, 
                               page_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get standard context for detail pages."""
        builder = TemplateContextBuilder(self.relays)
        
        # Add detail page context
        detail_ctx = self.context_generator.get_detail_context(category, value)
        builder.context.update(detail_ctx)
        
        # Add relays context
        builder.add_relays_context()
        
        # Add page-specific data
        if 'bandwidth_data' in page_data:
            builder.add_bandwidth_context(page_data['bandwidth_data'])
        
        if 'consensus_weight_data' in page_data:
            builder.add_consensus_weight_context(page_data['consensus_weight_data'])
        
        if 'count_data' in page_data:
            builder.add_relay_counts_context(page_data['count_data'])
        
        if 'network_position' in page_data:
            builder.add_network_position_context(page_data['network_position'])
        
        if 'contact_data' in page_data and category == 'contact':
            builder.add_contact_context(page_data['contact_data'])
        
        if 'template_optimizations' in page_data:
            builder.add_template_optimizations(page_data['template_optimizations'])
        
        # Add common variables
        builder.add_misc_context({
            'key': category,
            'value': value,
            'is_index': False
        })
        
        return builder.build()
    
    def get_relay_page_context(self, relay_data: Dict[str, Any], 
                              contact_display_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get standard context for relay pages."""
        builder = TemplateContextBuilder(self.relays)
        
        # Add relay page context
        relay_ctx = self.context_generator.get_relay_context(relay_data)
        builder.context.update(relay_ctx)
        
        # Add relays and relay-specific data
        builder.add_relays_context().add_misc_context({
            'relay': relay_data,
            'contact_display_data': contact_display_data
        })
        
        return builder.build()
    
    def get_index_page_context(self, page_name: Optional[str] = None,
                              timestamp: Optional[str] = None) -> Dict[str, Any]:
        """Get standard context for index pages."""
        builder = TemplateContextBuilder(self.relays)
        
        # Add index page context  
        index_ctx = self.context_generator.get_index_context(page_name)
        builder.context.update(index_ctx)
        
        # Add relays context
        builder.add_relays_context()
        
        # Add timestamp if provided
        if timestamp:
            builder.add_timestamp_context(timestamp)
        
        return builder.build()


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


def get_detail_page_context(category: str, value: str) -> Dict[str, Any]:
    """Helper function for creating detail page contexts with consistent structure."""
    generator = PageContextGenerator()
    return generator.get_detail_context(category, value)


def create_template_context_builder(relays_instance=None) -> TemplateContextBuilder:
    """Create a new template context builder."""
    return TemplateContextBuilder(relays_instance)


def create_standard_contexts(relays_instance=None) -> StandardTemplateContexts:
    """Create a new standard template contexts instance."""
    return StandardTemplateContexts(relays_instance)