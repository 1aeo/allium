from typing import Any, Dict, Optional


def get_page_context(page_type: str, breadcrumb_type: Optional[str] = None, breadcrumb_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get page context with path_prefix and breadcrumb info for different page types"""
    contexts: Dict[str, Dict[str, Any]] = {
        'index': {'path_prefix': './'},
        'misc': {'path_prefix': '../'},
        'detail': {'path_prefix': '../../'}
    }
    ctx = contexts.get(page_type, contexts['misc']).copy()
    
    # Add breadcrumb information if provided
    if breadcrumb_type:
        ctx['breadcrumb_type'] = breadcrumb_type
        ctx['breadcrumb_data'] = breadcrumb_data or {}
    
    return ctx


def get_misc_page_context(page_name: str) -> Dict[str, Any]:
    """Helper function for creating misc page contexts with consistent structure"""
    return get_page_context('misc', 'misc_listing', {'page_name': page_name}) 