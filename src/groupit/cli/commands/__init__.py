"""
CLI command implementations.

This module uses lazy loading (PEP 562) to avoid importing heavy
dependencies (core, llm, rich) until a command is actually invoked.
"""

__all__ = ['analyze_command', 'commit_command', 'status_command', 'validate_command']

# Cache for lazy-loaded commands
_cached_commands: dict = {}


def __getattr__(name: str):
    """Lazy import of CLI commands (PEP 562)."""
    global _cached_commands
    
    if name in _cached_commands:
        return _cached_commands[name]
    
    if name == 'analyze_command':
        from .analyze import analyze_command
        _cached_commands['analyze_command'] = analyze_command
        return analyze_command
    
    if name == 'commit_command':
        from .commit import commit_command
        _cached_commands['commit_command'] = commit_command
        return commit_command
    
    if name == 'status_command':
        from .status import status_command
        _cached_commands['status_command'] = status_command
        return status_command
    
    if name == 'validate_command':
        from .validate import validate_command
        _cached_commands['validate_command'] = validate_command
        return validate_command
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
