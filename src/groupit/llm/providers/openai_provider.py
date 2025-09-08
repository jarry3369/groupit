"""
OpenAI LLM provider implementation.
"""

import json
import logging
from typing import List, Optional, Dict, Any

from ..base import LLMProvider, LLMRequest, LLMResponse, LLMError, LLMQuotaExceededError, LLMTimeoutError

logger = logging.getLogger(__name__)

try:
    import openai
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False
    logger.warning("OpenAI library not available. Install with: pip install openai")


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider implementation"""
    
    def _setup_provider(self) -> None:
        """Setup OpenAI-specific configuration"""
        if not _HAS_OPENAI:
            raise LLMError("OpenAI library not installed. Install with: pip install openai")
        
        openai.api_key = self.api_key
        
        # Setup client with custom configuration
        client_kwargs = {}
        if 'timeout' in self.config:
            client_kwargs['timeout'] = self.config['timeout']
        if 'base_url' in self.config:
            client_kwargs['base_url'] = self.config['base_url']
        
        self.client = openai.OpenAI(api_key=self.api_key, **client_kwargs)
    
    @property
    def provider_name(self) -> str:
        return "openai"
    
    @property
    def default_model(self) -> str:
        return "gpt-4o"
    
    @property
    def supported_models(self) -> List[str]:
        return [
            "gpt-4o",
            "gpt-4",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k"
        ]
    
    def _make_request(self, request: LLMRequest) -> LLMResponse:
        """Make request to OpenAI API"""
        try:
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
                "temperature": request.temperature,
            }
            
            if request.max_tokens:
                api_params["max_tokens"] = request.max_tokens
            
            # Add any additional parameters from metadata
            for key, value in request.metadata.items():
                if key in ['top_p', 'frequency_penalty', 'presence_penalty', 'stop']:
                    api_params[key] = value
            
            logger.debug(f"Making OpenAI API call with model: {request.model}")
            
            # Make the API call
            response = self.client.chat.completions.create(**api_params)
            
            # Extract response data
            content = response.choices[0].message.content
            if not content:
                raise LLMError("OpenAI returned empty response")
            
            # Calculate token usage
            tokens_used = 0
            if hasattr(response, 'usage') and response.usage:
                tokens_used = response.usage.total_tokens
            
            return LLMResponse(
                content=content.strip(),
                model=request.model,
                provider=self.provider_name,
                tokens_used=tokens_used,
                metadata={
                    'finish_reason': response.choices[0].finish_reason,
                    'response_id': response.id,
                    'created': response.created
                }
            )
            
        except openai.AuthenticationError as e:
            raise LLMError(f"OpenAI authentication failed: {e}")
        except openai.RateLimitError as e:
            raise LLMQuotaExceededError(f"OpenAI rate limit exceeded: {e}")
        except openai.APITimeoutError as e:
            raise LLMTimeoutError(f"OpenAI request timed out: {e}")
        except openai.BadRequestError as e:
            raise LLMError(f"OpenAI bad request: {e}")
        except Exception as e:
            raise LLMError(f"OpenAI API error: {e}")
    
    def parse_json_response(self, response: LLMResponse) -> Dict[str, Any]:
        """Parse JSON response from OpenAI with error handling"""
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
            
            raise LLMError(f"Could not parse JSON from OpenAI response: {response.content[:200]}...")
    
    def get_available_models(self) -> List[str]:
        """Get list of available models from OpenAI API"""
        try:
            models = self.client.models.list()
            return [model.id for model in models.data if model.id.startswith('gpt')]
        except Exception as e:
            logger.warning(f"Could not fetch OpenAI models: {e}")
            return self.supported_models
