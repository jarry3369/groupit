"""
LLM provider abstraction and management.

This module uses lazy loading (PEP 562) to avoid importing heavy
dependencies until they are actually needed.
"""

__all__ = [
    'LLMProvider', 
    'LLMResponse', 
    'LLMError',
    'LLMFactory', 
    'get_llm_provider',
    'validate_provider',
    'register_provider',
    'get_available_providers'
]

# Cache for lazy-loaded modules
_cached_imports: dict = {}


def __getattr__(name: str):
    """Lazy import of LLM components (PEP 562)."""
    global _cached_imports
    
    if name in _cached_imports:
        return _cached_imports[name]
    
    if name in ('LLMProvider', 'LLMResponse', 'LLMError'):
        from .base import LLMProvider, LLMResponse, LLMError
        _cached_imports.update({
            'LLMProvider': LLMProvider,
            'LLMResponse': LLMResponse,
            'LLMError': LLMError
        })
        return _cached_imports[name]
    
    if name in ('LLMFactory', 'get_llm_provider', 'validate_provider'):
        from .factory import LLMFactory, get_llm_provider, validate_provider
        _cached_imports.update({
            'LLMFactory': LLMFactory,
            'get_llm_provider': get_llm_provider,
            'validate_provider': validate_provider
        })
        return _cached_imports[name]
    
    if name in ('register_provider', 'get_available_providers'):
        from .providers.registry import register_provider, get_available_providers
        _cached_imports.update({
            'register_provider': register_provider,
            'get_available_providers': get_available_providers
        })
        return _cached_imports[name]
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
