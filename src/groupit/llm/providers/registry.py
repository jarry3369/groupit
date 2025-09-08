"""
LLM provider registry for dynamic provider management.
"""

import logging
from typing import Dict, List, Type, Optional

from ..base import LLMProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Registry for managing LLM providers"""
    
    def __init__(self):
        self._providers: Dict[str, Type[LLMProvider]] = {}
        self._initialize_builtin_providers()
    
    def _initialize_builtin_providers(self) -> None:
        """Initialize built-in providers"""
        try:
            from .openai_provider import OpenAIProvider
            self.register('openai', OpenAIProvider)
        except ImportError:
            logger.warning("OpenAI provider not available")
        
        try:
            from .gemini_provider import GeminiProvider
            self.register('gemini', GeminiProvider)
        except ImportError:
            logger.warning("Gemini provider not available")
        
        try:
            from .ollama_provider import OllamaProvider
            self.register('ollama', OllamaProvider)
        except ImportError:
            logger.warning("Ollama provider not available")
    
    def register(self, name: str, provider_class: Type[LLMProvider]) -> None:
        """Register a new LLM provider"""
        if not issubclass(provider_class, LLMProvider):
            raise ValueError(f"Provider class must inherit from LLMProvider")
        
        self._providers[name] = provider_class
        logger.debug(f"Registered LLM provider: {name}")
    
    def unregister(self, name: str) -> None:
        """Unregister an LLM provider"""
        if name in self._providers:
            del self._providers[name]
            logger.debug(f"Unregistered LLM provider: {name}")
    
    def get_provider_class(self, name: str) -> Type[LLMProvider]:
        """Get provider class by name"""
        if name not in self._providers:
            raise ValueError(f"Unknown LLM provider: {name}. Available providers: {list(self._providers.keys())}")
        
        return self._providers[name]
    
    def create_provider(self, name: str, api_key: str, **kwargs) -> LLMProvider:
        """Create provider instance"""
        provider_class = self.get_provider_class(name)
        return provider_class(api_key=api_key, **kwargs)
    
    def get_available_providers(self) -> List[str]:
        """Get list of available provider names"""
        return list(self._providers.keys())
    
    def is_provider_available(self, name: str) -> bool:
        """Check if provider is available"""
        return name in self._providers
    
    def provider_requires_api_key(self, name: str) -> bool:
        """Check if a specific provider requires an API key"""
        if name not in self._providers:
            raise ValueError(f"Provider '{name}' not found")
        
        provider_class = self._providers[name]
        return getattr(provider_class, 'requires_api_key', True)
    
    def get_providers_requiring_api_key(self) -> List[str]:
        """Get list of providers that require API key"""
        return [
            name for name, provider_class in self._providers.items()
            if getattr(provider_class, 'requires_api_key', True)
        ]
    
    def get_providers_without_api_key(self) -> List[str]:
        """Get list of providers that don't require API key"""
        return [
            name for name, provider_class in self._providers.items()
            if not getattr(provider_class, 'requires_api_key', True)
        ]


# Global registry instance
_registry = ProviderRegistry()


def register_provider(name: str, provider_class: Type[LLMProvider]) -> None:
    """Register a new LLM provider globally"""
    _registry.register(name, provider_class)


def get_available_providers() -> List[str]:
    """Get list of available provider names"""
    return _registry.get_available_providers()


def get_provider_class(name: str) -> Type[LLMProvider]:
    """Get provider class by name"""
    return _registry.get_provider_class(name)


def create_provider(name: str, api_key: str, **kwargs) -> LLMProvider:
    """Create provider instance"""
    return _registry.create_provider(name, api_key, **kwargs)


def is_provider_available(name: str) -> bool:
    """Check if provider is available"""
    return _registry.is_provider_available(name)


def provider_requires_api_key(name: str) -> bool:
    """Check if a specific provider requires an API key"""
    return _registry.provider_requires_api_key(name)


def get_providers_requiring_api_key() -> List[str]:
    """Get list of providers that require API key"""
    return _registry.get_providers_requiring_api_key()


def get_providers_without_api_key() -> List[str]:
    """Get list of providers that don't require API key"""
    return _registry.get_providers_without_api_key()
