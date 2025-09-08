"""
Base classes for processing pipeline components.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Generic, TypeVar
import time
import logging

from ..core.models import CommitGroup
from ..config import get_logger

logger = get_logger(__name__)

# Type variables for generic processor
InputType = TypeVar('InputType')
OutputType = TypeVar('OutputType')


@dataclass
class ProcessorResult:
    """Result from a processor execution"""
    
    success: bool
    data: Any
    execution_time: float
    metadata: Dict[str, Any]
    error: Optional[Exception] = None
    
    @property
    def failed(self) -> bool:
        """Check if processor failed"""
        return not self.success


class BaseProcessor(ABC, Generic[InputType, OutputType]):
    """Abstract base class for all processors in the pipeline"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self.execution_count = 0
        self.total_execution_time = 0.0
        self.last_error: Optional[Exception] = None
        
    @abstractmethod
    def process(self, input_data: InputType) -> OutputType:
        """
        Process input data and return output
        
        Args:
            input_data: Input data to process
            
        Returns:
            Processed output data
            
        Raises:
            ProcessorError: If processing fails
        """
        pass
    
    def execute(self, input_data: InputType) -> ProcessorResult:
        """
        Execute processor with timing and error handling
        
        Args:
            input_data: Input data to process
            
        Returns:
            ProcessorResult containing the result and metadata
        """
        start_time = time.time()
        
        try:
            logger.debug(f"Starting processor: {self.name}")
            
            # Validate input if validation is implemented
            if hasattr(self, 'validate_input'):
                validation_result = self.validate_input(input_data)
                if not validation_result:
                    raise ProcessorError(f"Input validation failed for {self.name}")
            
            # Process the data
            output_data = self.process(input_data)
            
            # Validate output if validation is implemented
            if hasattr(self, 'validate_output'):
                validation_result = self.validate_output(output_data)
                if not validation_result:
                    raise ProcessorError(f"Output validation failed for {self.name}")
            
            execution_time = time.time() - start_time
            
            # Update statistics
            self.execution_count += 1
            self.total_execution_time += execution_time
            
            logger.debug(f"Completed processor: {self.name} in {execution_time:.2f}s")
            
            return ProcessorResult(
                success=True,
                data=output_data,
                execution_time=execution_time,
                metadata={
                    'processor_name': self.name,
                    'execution_count': self.execution_count,
                    'config': self.config
                }
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.last_error = e
            
            logger.error(f"Processor {self.name} failed: {e}")
            
            return ProcessorResult(
                success=False,
                data=None,
                execution_time=execution_time,
                metadata={
                    'processor_name': self.name,
                    'error_type': type(e).__name__,
                    'config': self.config
                },
                error=e
            )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get processor execution statistics"""
        avg_time = self.total_execution_time / self.execution_count if self.execution_count > 0 else 0
        
        return {
            'name': self.name,
            'execution_count': self.execution_count,
            'total_execution_time': self.total_execution_time,
            'average_execution_time': avg_time,
            'last_error': str(self.last_error) if self.last_error else None,
            'config': self.config
        }
    
    def reset_statistics(self) -> None:
        """Reset processor statistics"""
        self.execution_count = 0
        self.total_execution_time = 0.0
        self.last_error = None


class ProcessorError(Exception):
    """Exception raised by processors"""
    pass


class CommitGroupProcessor(BaseProcessor[List[CommitGroup], List[CommitGroup]]):
    """Base class for processors that work with CommitGroup lists"""
    
    def validate_input(self, input_data: List[CommitGroup]) -> bool:
        """Validate input is a list of CommitGroup objects"""
        if not isinstance(input_data, list):
            return False
        
        return all(isinstance(item, CommitGroup) for item in input_data)
    
    def validate_output(self, output_data: List[CommitGroup]) -> bool:
        """Validate output is a list of CommitGroup objects"""
        if not isinstance(output_data, list):
            return False
        
        return all(isinstance(item, CommitGroup) for item in output_data)


class ProcessorPipeline:
    """Pipeline for chaining processors together"""
    
    def __init__(self, name: str):
        self.name = name
        self.processors: List[BaseProcessor] = []
        self.execution_history: List[ProcessorResult] = []
        
    def add_processor(self, processor: BaseProcessor) -> 'ProcessorPipeline':
        """Add a processor to the pipeline"""
        self.processors.append(processor)
        return self
    
    def execute(self, input_data: Any) -> ProcessorResult:
        """
        Execute the entire pipeline
        
        Args:
            input_data: Initial input data
            
        Returns:
            Final ProcessorResult
        """
        start_time = time.time()
        current_data = input_data
        self.execution_history.clear()
        
        try:
            for processor in self.processors:
                result = processor.execute(current_data)
                self.execution_history.append(result)
                
                if result.failed:
                    # Pipeline failed at this processor
                    total_time = time.time() - start_time
                    return ProcessorResult(
                        success=False,
                        data=None,
                        execution_time=total_time,
                        metadata={
                            'pipeline_name': self.name,
                            'failed_processor': processor.name,
                            'completed_processors': len(self.execution_history) - 1,
                            'total_processors': len(self.processors)
                        },
                        error=result.error
                    )
                
                current_data = result.data
            
            # All processors succeeded
            total_time = time.time() - start_time
            return ProcessorResult(
                success=True,
                data=current_data,
                execution_time=total_time,
                metadata={
                    'pipeline_name': self.name,
                    'completed_processors': len(self.processors),
                    'total_processors': len(self.processors),
                    'processor_times': [r.execution_time for r in self.execution_history]
                }
            )
            
        except Exception as e:
            total_time = time.time() - start_time
            return ProcessorResult(
                success=False,
                data=None,
                execution_time=total_time,
                metadata={
                    'pipeline_name': self.name,
                    'error_location': 'pipeline_execution'
                },
                error=e
            )
    
    def get_pipeline_statistics(self) -> Dict[str, Any]:
        """Get statistics for the entire pipeline"""
        processor_stats = [p.get_statistics() for p in self.processors]
        
        return {
            'pipeline_name': self.name,
            'processor_count': len(self.processors),
            'processor_statistics': processor_stats,
            'last_execution_history': [
                {
                    'processor': r.metadata.get('processor_name'),
                    'success': r.success,
                    'execution_time': r.execution_time
                }
                for r in self.execution_history
            ]
        }
