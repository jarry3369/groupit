"""
Pipeline orchestration for the commit grouping system.
"""

import datetime
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from .models import CommitGroup, GroupingResult
from ..processors import (
    PrimaryGroupingProcessor,
    SummaryGeneratorProcessor,
    SemanticGrouperProcessor,
    MessageGeneratorProcessor,
    ProcessorPipeline,
    ProcessorResult
)
from .models.change_block import ChangeBlock
from ..config import get_settings, get_logger

logger = get_logger(__name__)


class CommitGroupingPipeline:
    """
    Main pipeline orchestrator for the commit grouping system.
    
    This class manages the four-stage pipeline:
    1. Primary grouping (DBSCAN + structural analysis)
    2. Summary generation (natural language summaries)
    3. Semantic grouping (LLM-based grouping and merging)
    4. Message generation (conventional commit messages)
    """
    
    def __init__(
        self,
        repo_root: Path,
        settings: Optional[Dict[str, Any]] = None
    ):
        self.repo_root = repo_root
        self.settings = settings or get_settings()
        self.execution_history: List[ProcessorResult] = []
        self._pipeline: Optional[ProcessorPipeline] = None
        
    def create_pipeline(
        self,
        llm_provider: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        **overrides
    ) -> ProcessorPipeline:
        """
        Create and configure the processing pipeline
        
        Args:
            llm_provider: LLM provider to use
            llm_api_key: API key for LLM provider
            **overrides: Override default settings
        
        Returns:
            Configured ProcessorPipeline
        """
        # Use settings with overrides
        llm_provider = llm_provider or self.settings.llm.provider
        llm_api_key = llm_api_key or self.settings.llm.api_key
        
        # Create processors with dependency injection
        pipeline = ProcessorPipeline("CommitGrouping")
        
        # Stage 1: Primary Grouping
        primary_processor = PrimaryGroupingProcessor(
            repo_root=self.repo_root,
            eps=overrides.get('eps', self.settings.clustering.eps),
            min_samples=overrides.get('min_samples', self.settings.clustering.min_samples),
            alpha=overrides.get('alpha', self.settings.clustering.alpha),
            config={
                'stage': 'primary',
                'description': 'DBSCAN and structural analysis grouping'
            }
        )
        pipeline.add_processor(primary_processor)
        
        # Stage 2: Summary Generation
        summary_processor = SummaryGeneratorProcessor(
            llm_provider=llm_provider,
            api_key=llm_api_key,
            config={
                'stage': 'summary',
                'description': 'Natural language summary generation'
            }
        )
        pipeline.add_processor(summary_processor)
        
        # Stage 3: Semantic Grouping
        semantic_processor = SemanticGrouperProcessor(
            repo_root=self.repo_root,
            llm_provider=llm_provider,
            api_key=llm_api_key,
            max_iterations=overrides.get('max_iterations', self.settings.clustering.max_iterations),
            batch_size=overrides.get('batch_size', self.settings.clustering.batch_size),
            config={
                'stage': 'semantic',
                'description': 'LLM-based semantic grouping and merging'
            }
        )
        pipeline.add_processor(semantic_processor)
        
        # Stage 4: Message Generation
        message_processor = MessageGeneratorProcessor(
            llm_provider=llm_provider,
            api_key=llm_api_key,
            config={
                'stage': 'message',
                'description': 'Conventional commit message generation'
            }
        )
        pipeline.add_processor(message_processor)
        
        self._pipeline = pipeline
        return pipeline
    
    def execute(
        self,
        change_blocks: List[ChangeBlock],
        llm_provider: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        **overrides
    ) -> GroupingResult:
        """
        Execute the complete commit grouping pipeline
        
        Args:
            change_blocks: List of ChangeBlock objects to process
            llm_provider: LLM provider to use
            llm_api_key: API key for LLM provider
            **overrides: Override default settings
        
        Returns:
            GroupingResult containing all stages of processing
        """
        start_time = datetime.datetime.now()
        
        logger.info(f"Starting commit grouping pipeline with {len(change_blocks)} change blocks")
        
        try:
            # Create pipeline if not exists
            if self._pipeline is None:
                self.create_pipeline(llm_provider, llm_api_key, **overrides)
            
            # Execute pipeline with change blocks
            result = self._pipeline.execute(change_blocks)
            
            if result.failed:
                raise RuntimeError(f"Pipeline execution failed: {result.error}")
            
            # Extract results from each stage
            stage_results = self._extract_stage_results()
            
            # Create final result
            end_time = datetime.datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            grouping_result = GroupingResult(
                timestamp=start_time.isoformat(),
                repo_path=str(self.repo_root),
                stage1_groups=stage_results.get('stage1_groups', []),
                summary_groups=stage_results.get('summary_groups', []),
                semantic_groups=stage_results.get('semantic_groups', []),
                final_groups=result.data,
                execution_time=execution_time,
                config={
                    'llm_provider': llm_provider or self.settings.llm.provider,
                    'eps': overrides.get('eps', self.settings.clustering.eps),
                    'min_samples': overrides.get('min_samples', self.settings.clustering.min_samples),
                    'alpha': overrides.get('alpha', self.settings.clustering.alpha),
                    'max_iterations': overrides.get('max_iterations', self.settings.clustering.max_iterations),
                    'batch_size': overrides.get('batch_size', self.settings.clustering.batch_size),
                    **overrides
                }
            )
            
            logger.info(f"Pipeline completed successfully in {execution_time:.2f}s")
            logger.info(f"Final result: {len(grouping_result.final_groups)} commit groups")
            
            return grouping_result
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            raise RuntimeError(f"Pipeline execution failed: {e}")
    
    def _extract_stage_results(self) -> Dict[str, List[CommitGroup]]:
        """Extract results from each pipeline stage"""
        stage_results = {}
        
        if self._pipeline and self._pipeline.execution_history:
            for i, result in enumerate(self._pipeline.execution_history):
                stage_name = result.metadata.get('processor_name', f'stage_{i+1}')
                
                if stage_name == 'PrimaryGrouping':
                    stage_results['stage1_groups'] = result.data or []
                elif stage_name == 'SummaryGenerator':
                    stage_results['summary_groups'] = result.data or []
                elif stage_name == 'SemanticGrouper':
                    stage_results['semantic_groups'] = result.data or []
        
        return stage_results
    
    def get_pipeline_statistics(self) -> Dict[str, Any]:
        """Get comprehensive pipeline statistics"""
        if not self._pipeline:
            return {}
        
        stats = self._pipeline.get_pipeline_statistics()
        
        # Add additional statistics
        stats.update({
            'repo_root': str(self.repo_root),
            'settings_summary': {
                'llm_provider': self.settings.llm.provider,
                'clustering_eps': self.settings.clustering.eps,
                'clustering_min_samples': self.settings.clustering.min_samples,
                'performance_caching': self.settings.performance.enable_caching,
                'performance_parallel': self.settings.performance.enable_parallel_processing
            }
        })
        
        return stats
    
    def reset_pipeline(self) -> None:
        """Reset pipeline for reuse"""
        self._pipeline = None
        self.execution_history.clear()
        logger.debug("Pipeline reset")
    
    def validate_configuration(self) -> List[str]:
        """
        Validate pipeline configuration
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Validate settings
        settings_errors = self.settings.validate()
        errors.extend(settings_errors)
        
        # Validate repo root
        if not self.repo_root.exists():
            errors.append(f"Repository root does not exist: {self.repo_root}")
        
        # Validate LLM provider availability
        try:
            from ..llm import get_available_providers
            available_providers = get_available_providers()
            if self.settings.llm.provider not in available_providers:
                errors.append(f"LLM provider '{self.settings.llm.provider}' not available. Available: {available_providers}")
        except ImportError:
            errors.append("LLM module not available")
        
        return errors


class PipelineBuilder:
    """Builder pattern for creating customized pipelines"""
    
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.processors = []
        self.config = {}
        
    def add_primary_grouping(
        self,
        eps: float = 0.35,
        min_samples: int = 2,
        alpha: float = 0.4
    ) -> 'PipelineBuilder':
        """Add primary grouping processor"""
        processor = PrimaryGroupingProcessor(
            repo_root=self.repo_root,
            eps=eps,
            min_samples=min_samples,
            alpha=alpha
        )
        self.processors.append(processor)
        return self
    
    def add_summary_generation(
        self,
        llm_provider: str = 'openai',
        api_key: Optional[str] = None
    ) -> 'PipelineBuilder':
        """Add summary generation processor"""
        processor = SummaryGeneratorProcessor(
            llm_provider=llm_provider,
            api_key=api_key
        )
        self.processors.append(processor)
        return self
    
    def add_semantic_grouping(
        self,
        llm_provider: str = 'openai',
        api_key: Optional[str] = None,
        max_iterations: int = 2,
        batch_size: int = 5
    ) -> 'PipelineBuilder':
        """Add semantic grouping processor"""
        processor = SemanticGrouperProcessor(
            repo_root=self.repo_root,
            llm_provider=llm_provider,
            api_key=api_key,
            max_iterations=max_iterations,
            batch_size=batch_size
        )
        self.processors.append(processor)
        return self
    
    def add_message_generation(
        self,
        llm_provider: str = 'openai',
        api_key: Optional[str] = None
    ) -> 'PipelineBuilder':
        """Add message generation processor"""
        processor = MessageGeneratorProcessor(
            llm_provider=llm_provider,
            api_key=api_key
        )
        self.processors.append(processor)
        return self
    
    def build(self) -> ProcessorPipeline:
        """Build the pipeline"""
        pipeline = ProcessorPipeline("CustomCommitGrouping")
        
        for processor in self.processors:
            pipeline.add_processor(processor)
        
        return pipeline
