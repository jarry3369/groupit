"""
Google Gemini LLM provider implementation.
"""

import json
import logging
from typing import List, Optional, Dict, Any

from ..base import LLMProvider, LLMRequest, LLMResponse, LLMError, LLMQuotaExceededError, LLMTimeoutError

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    _HAS_GEMINI = True
except ImportError:
    _HAS_GEMINI = False
    logger.warning("Google Generative AI library not available. Install with: pip install google-generativeai")


class GeminiProvider(LLMProvider):
    """Google Gemini LLM provider implementation"""
    
    def _setup_provider(self) -> None:
        """Setup Gemini-specific configuration"""
        if not _HAS_GEMINI:
            raise LLMError("Google Generative AI library not installed. Install with: pip install google-generativeai")
        
        genai.configure(api_key=self.api_key)
        
        # Initialize model
        model_name = self.model or self.default_model
        
        # Prepare generation config
        generation_config = {}
        if 'temperature' in self.config:
            generation_config['temperature'] = self.config['temperature']
        if 'max_output_tokens' in self.config:
            generation_config['max_output_tokens'] = self.config['max_output_tokens']
        
        self.model_instance = genai.GenerativeModel(
            model_name=model_name,
            generation_config=generation_config if generation_config else None
        )
    
    @property
    def provider_name(self) -> str:
        return "gemini"
    
    @property
    def default_model(self) -> str:
        return "gemini-2.5-flash-lite"
    
    @property
    def supported_models(self) -> List[str]:
        return [
            "gemini-2.0-flash-lite",
            "gemini-2.0-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
        ]
    
    def _make_request(self, request: LLMRequest) -> LLMResponse:
        """Make request to Gemini API"""
        try:
            # Prepare prompt
            full_prompt = request.prompt
            if request.system_prompt:
                full_prompt = f"{request.system_prompt}\n\n{request.prompt}"
            
            # Prepare generation config for this request
            generation_config = {
                'temperature': request.temperature,
            }
            
            if request.max_tokens:
                generation_config['max_output_tokens'] = request.max_tokens
            
            # Add any additional parameters from metadata
            for key, value in request.metadata.items():
                if key in ['top_p', 'top_k', 'candidate_count']:
                    generation_config[key] = value
            
            logger.debug(f"Making Gemini API call with model: {request.model}")
            
            # Make the API call
            response = self.model_instance.generate_content(
                full_prompt,
                generation_config=generation_config
            )
            
            # Extract response data
            if not response.text:
                raise LLMError("Gemini returned empty response")
            
            content = response.text.strip()
            
            # Estimate token usage (Gemini doesn't provide exact count in all cases)
            tokens_used = self.estimate_tokens(full_prompt + content)
            
            # Try to get actual token count if available
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                if hasattr(response.usage_metadata, 'total_token_count'):
                    tokens_used = response.usage_metadata.total_token_count
            
            return LLMResponse(
                content=content,
                model=request.model,
                provider=self.provider_name,
                tokens_used=tokens_used,
                metadata={
                    'finish_reason': getattr(response.candidates[0], 'finish_reason', None) if response.candidates else None,
                    'safety_ratings': [
                        {
                            'category': rating.category.name,
                            'probability': rating.probability.name
                        }
                        for rating in response.candidates[0].safety_ratings
                    ] if response.candidates and response.candidates[0].safety_ratings else []
                }
            )
            
        except Exception as e:
            # Handle specific Gemini errors
            error_message = str(e).lower()
            
            if 'quota' in error_message or 'rate limit' in error_message:
                raise LLMQuotaExceededError(f"Gemini quota exceeded: {e}")
            elif 'timeout' in error_message:
                raise LLMTimeoutError(f"Gemini request timed out: {e}")
            elif 'api_key' in error_message or 'authentication' in error_message:
                raise LLMError(f"Gemini authentication failed: {e}")
            elif 'safety' in error_message or 'blocked' in error_message:
                raise LLMError(f"Gemini safety filter blocked request: {e}")
            else:
                raise LLMError(f"Gemini API error: {e}")
    
    def parse_json_response(self, response: LLMResponse) -> Dict[str, Any]:
        """Parse JSON response from Gemini with error handling"""
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
            
            raise LLMError(f"Could not parse JSON from Gemini response: {response.content[:200]}...")
    
    def get_available_models(self) -> List[str]:
        """Get list of available models from Gemini API"""
        try:
            models = genai.list_models()
            return [model.name.split('/')[-1] for model in models if 'generateContent' in model.supported_generation_methods]
        except Exception as e:
            logger.warning(f"Could not fetch Gemini models: {e}")
            return self.supported_models
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for Gemini (more accurate estimation)"""
        # Gemini uses similar tokenization to other models
        # Rough estimation: 1 token ≈ 3.5 characters for mixed content
        return int(len(text) / 3.5)
