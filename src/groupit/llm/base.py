"""
Base classes for LLM provider abstraction.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import time
import logging

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for LLM-related errors"""
    pass


class LLMTimeoutError(LLMError):
    """Exception raised when LLM request times out"""
    pass


class LLMQuotaExceededError(LLMError):
    """Exception raised when LLM quota is exceeded"""
    pass


class LLMInvalidResponseError(LLMError):
    """Exception raised when LLM returns invalid response"""
    pass


@dataclass
class LLMResponse:
    """Standardized response from LLM providers"""
    
    content: str
    model: str
    provider: str
    tokens_used: int = 0
    response_time: float = 0.0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class LLMRequest:
    """Standardized request to LLM providers"""
    
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.3
    max_tokens: Optional[int] = None
    model: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    # Provider metadata
    requires_api_key: bool = True  # Most providers require API key
    
    def __init__(self, api_key: str, model: Optional[str] = None, **kwargs):
        self.api_key = api_key
        self.model = model
        self.config = kwargs
        self.request_count = 0
        self.total_tokens = 0
        self._setup_provider()
    
    @abstractmethod
    def _setup_provider(self) -> None:
        """Setup provider-specific configuration"""
        pass
    
    @abstractmethod
    def _make_request(self, request: LLMRequest) -> LLMResponse:
        """Make actual request to LLM provider"""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the LLM provider"""
        pass
    
    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model for this provider"""
        pass
    
    @property
    @abstractmethod
    def supported_models(self) -> List[str]:
        """List of supported models"""
        pass
    
    def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        retry_attempts: int = 3,
        **kwargs
    ) -> LLMResponse:
        """
        Generate response from LLM with retry logic and error handling
        
        Args:
            prompt: The main prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            model: Model to use (defaults to provider default)
            retry_attempts: Number of retry attempts on failure
            **kwargs: Additional provider-specific parameters
        
        Returns:
            LLMResponse object containing the generated content
        
        Raises:
            LLMError: On various LLM-related errors
        """
        request = LLMRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model or self.model or self.default_model,
            metadata=kwargs
        )
        
        last_error = None
        start_time = time.time()
        
        for attempt in range(retry_attempts):
            try:
                logger.debug(f"LLM request attempt {attempt + 1}/{retry_attempts}")
                response = self._make_request(request)
                
                # Update statistics
                self.request_count += 1
                self.total_tokens += response.tokens_used
                response.response_time = time.time() - start_time
                
                logger.debug(f"LLM response received: {response.tokens_used} tokens")
                return response
                
            except LLMQuotaExceededError:
                # Don't retry on quota errors
                raise
            except Exception as e:
                last_error = e
                if attempt < retry_attempts - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"LLM request failed (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"LLM request failed after {retry_attempts} attempts: {e}")
        
        # All attempts failed
        if isinstance(last_error, LLMError):
            raise last_error
        else:
            raise LLMError(f"LLM request failed: {last_error}")
    
    def validate_model(self, model: str) -> bool:
        """Check if model is supported by this provider"""
        return model in self.supported_models
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for given text (rough approximation)"""
        # Rough estimation: 1 token ≈ 4 characters for English text
        return len(text) // 4
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get usage statistics for this provider"""
        return {
            'provider': self.provider_name,
            'request_count': self.request_count,
            'total_tokens': self.total_tokens,
            'model': self.model or self.default_model
        }
