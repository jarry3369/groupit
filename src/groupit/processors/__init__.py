"""
Processing pipeline components for commit grouping.
"""

from .base import BaseProcessor, ProcessorResult, ProcessorPipeline
from .primary_grouping import PrimaryGroupingProcessor
from .summary_generator import SummaryGeneratorProcessor
from .semantic_grouper import SemanticGrouperProcessor
from .message_generator import MessageGeneratorProcessor

__all__ = [
    'BaseProcessor',
    'ProcessorResult',
    'ProcessorPipeline',
    'PrimaryGroupingProcessor',
    'SummaryGeneratorProcessor', 
    'SemanticGrouperProcessor',
    'MessageGeneratorProcessor'
]
