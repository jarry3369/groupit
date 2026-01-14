"""
Centralized constants for the groupit package.

This module contains constants that need to be shared across multiple modules
without triggering heavy imports. Add new providers here when extending support.
"""

# Known LLM providers - used by CLI parser for help text
# These are validated at runtime when actually used
KNOWN_LLM_PROVIDERS: list[str] = ['openai', 'gemini', 'ollama']
