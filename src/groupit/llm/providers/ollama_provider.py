"""
Ollama LLM provider implementation for local models.
"""

import json
import logging
from typing import List, Optional, Dict, Any

from ..base import LLMProvider, LLMRequest, LLMResponse, LLMError, LLMQuotaExceededError, LLMTimeoutError

logger = logging.getLogger(__name__)

def _check_ollama_availability():
    """Check if ollama library is available"""
    try:
        import ollama
        return True, ollama
    except ImportError:
        return False, None

# Initial check
_HAS_OLLAMA, _ollama_module = _check_ollama_availability()
if not _HAS_OLLAMA:
    logger.warning("Ollama library not available. Install with: pip install ollama")


class OllamaProvider(LLMProvider):
    """Ollama LLM provider implementation for local models"""
    
    # Ollama doesn't require API key (local server)
    requires_api_key: bool = False
    
    def __init__(self, api_key: str = "", model: Optional[str] = None, **kwargs):
        # Default configuration for Ollama (set before calling super)
        self.base_url = kwargs.get('base_url', 'http://localhost:11434')
        self.timeout = kwargs.get('timeout', 30.0)
        
        # Ollama doesn't need API key, but we override to make it optional
        super().__init__(api_key="dummy", model=model, **kwargs)
        
    def _setup_provider(self) -> None:
        """Setup Ollama-specific configuration"""
        # Re-check ollama availability at runtime
        global _HAS_OLLAMA, _ollama_module
        if not _HAS_OLLAMA:
            _HAS_OLLAMA, _ollama_module = _check_ollama_availability()
        
        if not _HAS_OLLAMA:
            raise LLMError("Ollama library not installed. Install with: pip install ollama")
        
        # Setup client with custom configuration
        client_kwargs = {
            'host': self.base_url,
            'timeout': self.timeout
        }
        
        try:
            self.client = _ollama_module.Client(**client_kwargs)
            
            # Test connection by listing models
            self._test_connection()
            
        except Exception as e:
            raise LLMError(f"Failed to connect to Ollama server at {self.base_url}: {e}")
    
    def _test_connection(self) -> None:
        """Test connection to Ollama server"""
        try:
            self.client.list()
        except Exception as e:
            raise LLMError(f"Cannot connect to Ollama server at {self.base_url}. Make sure Ollama is running: {e}")
    
    @property
    def provider_name(self) -> str:
        return "ollama"
    
    @property
    def default_model(self) -> str:
        """Get the first available model as default"""
        try:
            models = self.get_available_models()
            if models:
                return models[0]
            else:
                return "llama2"  # Fallback default
        except:
            return "llama2"  # Fallback default
    
    @property
    def supported_models(self) -> List[str]:
        """Get list of models available on the Ollama server"""
        try:
            return self.get_available_models()
        except:
            # Fallback to common models if can't connect
            return [
                "llama2",
                "llama2:7b",
                "llama2:13b",
                "llama2:70b",
                "codellama",
                "codellama:7b",
                "codellama:13b",
                "mistral",
                "mistral:7b",
                "phi",
                "neural-chat",
                "starcode",
                "orca-mini",
                "vicuna"
            ]
    
    def get_available_models(self) -> List[str]:
        """Get list of available models from Ollama server"""
        try:
            models_response = self.client.list()
            models = []
            
            # Handle both old dict format and new object format
            if hasattr(models_response, 'models'):
                # New object format
                for model in models_response.models:
                    if hasattr(model, 'model'):
                        models.append(model.model)
                    elif hasattr(model, 'name'):
                        models.append(model.name)
            elif isinstance(models_response, dict) and 'models' in models_response:
                # Old dict format (for backward compatibility)
                for model in models_response['models']:
                    if 'name' in model:
                        models.append(model['name'])
                    elif 'model' in model:
                        models.append(model['model'])
            
            return models
            
        except Exception as e:
            logger.warning(f"Could not fetch Ollama models: {e}")
            return []
    
    def _make_request(self, request: LLMRequest) -> LLMResponse:
        """Make request to Ollama server"""
        try:
            # Prepare messages for chat API
            messages = []
            
            # Add system message if provided
            if request.system_prompt:
                messages.append({
                    "role": "system",
                    "content": request.system_prompt
                })
            
            # Add user message
            messages.append({
                "role": "user", 
                "content": request.prompt
            })
            
            # Prepare API call parameters
            api_params = {
                "model": request.model,
                "messages": messages,
                "stream": False,  # We want complete response, not streaming
                "options": {
                    "temperature": request.temperature,
                }
            }
            
            # Add max_tokens if specified (as num_predict in Ollama)
            if request.max_tokens:
                api_params["options"]["num_predict"] = request.max_tokens
            
            # Add any additional parameters from metadata
            options = api_params["options"]
            for key, value in request.metadata.items():
                if key in ['top_p', 'top_k', 'repeat_penalty', 'seed']:
                    options[key] = value
            
            logger.debug(f"Making Ollama API call with model: {request.model}")
            
            # Make the API call
            response = self.client.chat(**api_params)
            
            # Extract response data
            if 'message' not in response or 'content' not in response['message']:
                raise LLMError("Ollama returned invalid response format")
            
            content = response['message']['content']
            if not content:
                raise LLMError("Ollama returned empty response")
            
            # Extract token usage if available
            tokens_used = 0
            if 'prompt_eval_count' in response and 'eval_count' in response:
                tokens_used = response.get('prompt_eval_count', 0) + response.get('eval_count', 0)
            
            # Calculate response time if available
            response_time = 0.0
            if 'total_duration' in response:
                response_time = response['total_duration'] / 1_000_000_000  # Convert nanoseconds to seconds
            
            return LLMResponse(
                content=content.strip(),
                model=request.model,
                provider=self.provider_name,
                tokens_used=tokens_used,
                response_time=response_time,
                metadata={
                    'eval_count': response.get('eval_count', 0),
                    'eval_duration': response.get('eval_duration', 0),
                    'prompt_eval_count': response.get('prompt_eval_count', 0),
                    'prompt_eval_duration': response.get('prompt_eval_duration', 0),
                    'total_duration': response.get('total_duration', 0),
                    'load_duration': response.get('load_duration', 0),
                }
            )
            
        except Exception as e:
            # Handle ollama specific exceptions if available
            if _ollama_module and hasattr(_ollama_module, 'ResponseError') and isinstance(e, _ollama_module.ResponseError):
                if "model" in str(e).lower() and "not found" in str(e).lower():
                    available_models = self.get_available_models()
                    raise LLMError(f"Model '{request.model}' not found on Ollama server. Available models: {available_models}")
                raise LLMError(f"Ollama response error: {e}")
            elif _ollama_module and hasattr(_ollama_module, 'RequestError') and isinstance(e, _ollama_module.RequestError):
                raise LLMTimeoutError(f"Ollama request error: {e}")
            else:
                raise LLMError(f"Ollama API error: {e}")
    
    def parse_json_response(self, response: LLMResponse) -> Dict[str, Any]:
        """Parse JSON response from Ollama with error handling"""
        try:
            # Try to parse the entire content as JSON
            return json.loads(response.content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response.content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            
            # Try to find JSON object in the text
            json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            
            raise LLMError(f"Could not parse JSON from Ollama response: {response.content[:200]}...")
    
    def pull_model(self, model_name: str) -> bool:
        """Pull a model from Ollama registry"""
        try:
            logger.info(f"Pulling model {model_name} from Ollama registry...")
            self.client.pull(model_name)
            logger.info(f"Successfully pulled model {model_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to pull model {model_name}: {e}")
            return False
    
    def delete_model(self, model_name: str) -> bool:
        """Delete a model from Ollama"""
        try:
            logger.info(f"Deleting model {model_name}...")
            self.client.delete(model_name)
            logger.info(f"Successfully deleted model {model_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete model {model_name}: {e}")
            return False
    
    def show_model_info(self, model_name: str) -> Dict[str, Any]:
        """Get detailed information about a model"""
        try:
            return self.client.show(model_name)
        except Exception as e:
            logger.error(f"Failed to get model info for {model_name}: {e}")
            return {}
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for given text (rough approximation)"""
        # Rough estimation: 1 token ≈ 4 characters for English text
        # This is a simple approximation, actual tokenization may vary by model
        return len(text) // 4
