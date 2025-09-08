"""
LLM Factory for creating and managing LLM provider instances.
"""

import logging
from typing import Optional, Dict, Any
from functools import lru_cache

from .base import LLMProvider
from .providers.registry import create_provider, get_available_providers, is_provider_available
from ..config.settings import get_settings, LLMSettings

logger = logging.getLogger(__name__)


class LLMFactory:
    """Factory for creating and managing LLM providers"""
    
    def __init__(self):
        self._instances: Dict[str, LLMProvider] = {}
    
    def create_provider(
        self,
        provider_name: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> LLMProvider:
        """
        Create LLM provider instance
        
        Args:
            provider_name: Name of the provider ('openai', 'gemini', etc.)
            api_key: API key for the provider
            model: Model to use
            **kwargs: Additional provider-specific parameters
        
        Returns:
            LLMProvider instance
        
        Raises:
            ValueError: If provider is not available or configuration is invalid
        """
        # Load settings if not provided
        settings = get_settings()
        
        if provider_name is None:
            provider_name = settings.llm.provider
        
        if api_key is None:
            # Try to get API key from settings or environment
            llm_settings = LLMSettings(provider=provider_name)
            api_key = llm_settings.api_key
        
        # Ollama doesn't require API key (local server)
        if not api_key and provider_name != 'ollama':
            raise ValueError(f"API key required for {provider_name} provider")
        
        # Use dummy API key for ollama if none provided
        if provider_name == 'ollama' and not api_key:
            api_key = "dummy"
        
        if not is_provider_available(provider_name):
            available = get_available_providers()
            raise ValueError(f"Provider '{provider_name}' not available. Available providers: {available}")
        
        # Create cache key (different handling for providers without API key)
        if provider_name == 'ollama':
            cache_key = f"{provider_name}:local:{model}"
        else:
            cache_key = f"{provider_name}:{api_key[:8]}:{model}"
        
        # Return cached instance if exists
        if cache_key in self._instances:
            return self._instances[cache_key]
        
        # Merge configuration
        config = {
            'model': model or settings.llm.model,
            'temperature': settings.llm.temperature,
            'timeout': settings.llm.timeout,
            'retry_attempts': settings.llm.retry_attempts,
            **kwargs
        }
        
        logger.debug(f"Creating {provider_name} provider with model: {config.get('model', 'default')}")
        
        try:
            provider = create_provider(provider_name, api_key, **config)
            
            # Cache the instance
            self._instances[cache_key] = provider
            
            return provider
            
        except Exception as e:
            raise ValueError(f"Failed to create {provider_name} provider: {e}")
    
    def get_provider(
        self,
        provider_name: Optional[str] = None,
        **kwargs
    ) -> LLMProvider:
        """Get or create provider instance (convenience method)"""
        return self.create_provider(provider_name=provider_name, **kwargs)
    
    def clear_cache(self) -> None:
        """Clear all cached provider instances"""
        self._instances.clear()
        logger.debug("Cleared LLM provider cache")
    
    def get_cached_providers(self) -> Dict[str, LLMProvider]:
        """Get all cached provider instances"""
        return self._instances.copy()
    
    def validate_provider_config(
        self,
        provider_name: str,
        api_key: Optional[str] = None
    ) -> bool:
        """
        Validate provider configuration
        
        Args:
            provider_name: Name of the provider
            api_key: API key to validate
        
        Returns:
            True if configuration is valid
        """
        try:
            provider = self.create_provider(provider_name, api_key)
            
            # Try a simple test request
            test_response = provider.generate(
                prompt="Hello",
                max_tokens=5,
                temperature=0.0
            )
            
            return bool(test_response.content)
            
        except Exception as e:
            logger.warning(f"Provider validation failed for {provider_name}: {e}")
            return False


# Global factory instance
_factory = LLMFactory()


@lru_cache(maxsize=None)
def get_llm_provider(
    provider_name: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs
) -> LLMProvider:
    """
    Get LLM provider instance (cached)
    
    This is the main entry point for getting LLM providers.
    The function is cached to avoid recreating providers with the same parameters.
    """
    return _factory.create_provider(
        provider_name=provider_name,
        api_key=api_key,
        model=model,
        **kwargs
    )


def clear_provider_cache() -> None:
    """Clear LLM provider cache"""
    _factory.clear_cache()
    get_llm_provider.cache_clear()


def validate_provider(provider_name: str, api_key: Optional[str] = None) -> bool:
    """Validate LLM provider configuration"""
    return _factory.validate_provider_config(provider_name, api_key)


def get_provider_statistics() -> Dict[str, Any]:
    """Get statistics for all cached providers"""
    providers = _factory.get_cached_providers()
    
    stats = {
        'total_providers': len(providers),
        'providers': {}
    }
    
    for key, provider in providers.items():
        stats['providers'][key] = provider.get_statistics()
    
    return stats
