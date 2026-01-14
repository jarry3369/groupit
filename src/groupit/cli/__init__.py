"""
Command-line interface for the commit grouping system.

This module uses lazy loading (PEP 562) to avoid importing heavy
dependencies until they are actually needed.
"""

__all__ = ['create_parser', 'analyze_command', 'commit_command', 'status_command', 'validate_command']

# Cache for lazy-loaded components
_cached: dict = {}


def __getattr__(name: str):
    """Lazy import of CLI components (PEP 562)."""
    global _cached
    
    if name in _cached:
        return _cached[name]
    
    if name == 'create_parser':
        from .parser import create_parser
        _cached['create_parser'] = create_parser
        return create_parser
    
    if name == 'analyze_command':
        from .commands import analyze_command
        _cached['analyze_command'] = analyze_command
        return analyze_command
    
    if name == 'commit_command':
        from .commands import commit_command
        _cached['commit_command'] = commit_command
        return commit_command
    
    if name == 'status_command':
        from .commands import status_command
        _cached['status_command'] = status_command
        return status_command
    
    if name == 'validate_command':
        from .commands import validate_command
        _cached['validate_command'] = validate_command
        return validate_command
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
