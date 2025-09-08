"""
Summary generator processor using LLM to create natural language summaries.
"""

from typing import List, Dict, Any, Optional

from .base import CommitGroupProcessor, ProcessorError
from ..core.models import CommitGroup
from ..llm import get_llm_provider, LLMError
from ..config import get_logger

logger = get_logger(__name__)


class SummaryGeneratorProcessor(CommitGroupProcessor):
    """Processor for generating natural language summaries of commit groups"""
    
    def __init__(
        self,
        llm_provider: str = 'openai',
        api_key: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__("SummaryGenerator", config)
        self.llm_provider_name = llm_provider
        self.api_key = api_key
        self._llm_provider = None
        
    @property
    def llm_provider(self):
        """Lazy initialization of LLM provider"""
        if self._llm_provider is None:
            try:
                self._llm_provider = get_llm_provider(
                    provider_name=self.llm_provider_name,
                    api_key=self.api_key
                )
            except Exception as e:
                raise ProcessorError(f"Failed to initialize LLM provider: {e}")
        return self._llm_provider
    
    def process(self, input_data: List[CommitGroup]) -> List[CommitGroup]:
        """
        Generate natural language summaries for commit groups
        
        Args:
            input_data: List of CommitGroup objects
            
        Returns:
            List of CommitGroup objects with summaries added
        """
        if not input_data:
            return []
        
        logger.info(f"Generating summaries for {len(input_data)} groups")
        
        groups_with_summaries = []
        successful_summaries = 0
        
        for group in input_data:
            try:
                summary = self._generate_summary(group)
                
                # Create new group with summary
                updated_group = CommitGroup(
                    group_id=group.group_id,
                    blocks=group.blocks,
                    files=group.files,
                    summary=summary,
                    commit_message=group.commit_message,
                    semantic_theme=group.semantic_theme,
                    confidence_score=group.confidence_score,
                    metadata={
                        **group.metadata,
                        'summary_generated': True,
                        'summary_provider': self.llm_provider_name
                    }
                )
                
                groups_with_summaries.append(updated_group)
                successful_summaries += 1
                
                logger.debug(f"Generated summary for group {group.group_id}: {summary[:100]}...")
                
            except Exception as e:
                logger.warning(f"Failed to generate summary for group {group.group_id}: {e}")
                
                # Use fallback summary
                fallback_summary = self._create_fallback_summary(group)
                
                updated_group = CommitGroup(
                    group_id=group.group_id,
                    blocks=group.blocks,
                    files=group.files,
                    summary=fallback_summary,
                    commit_message=group.commit_message,
                    semantic_theme=group.semantic_theme,
                    confidence_score=group.confidence_score,
                    metadata={
                        **group.metadata,
                        'summary_generated': False,
                        'summary_fallback': True,
                        'summary_error': str(e)
                    }
                )
                
                groups_with_summaries.append(updated_group)
        
        logger.info(f"Generated {successful_summaries}/{len(input_data)} summaries successfully")
        return groups_with_summaries
    
    def _generate_summary(self, group: CommitGroup) -> str:
        """Generate summary using LLM"""
        prompt = self._create_summary_prompt(group)
        
        try:
            response = self.llm_provider.generate(
                prompt=prompt,
                system_prompt="You are a code change summarizer. Create concise, informative summaries.",
                temperature=0.3,
                max_tokens=200
            )
            
            return response.content.strip()
            
        except LLMError as e:
            logger.error(f"LLM error generating summary: {e}")
            raise ProcessorError(f"LLM summary generation failed: {e}")
    
    def _create_summary_prompt(self, group: CommitGroup) -> str:
        """Create prompt for summarizing a commit group"""
        # Extract enhanced context
        enhanced_context = self._extract_enhanced_context(group)
        
        prompt = f"""Summarize the following code change group in natural language. 
Focus on:
- What was changed (e.g., added features, fixed bugs)
- Affected components or areas
- Overall purpose or theme
- Code quality and architectural impact
Keep it concise, 2-4 sentences.

Group details:
Files: {', '.join(group.files)}
{enhanced_context}

Sample changes:
"""
        
        # Add sample changes (limit to first 3 blocks)
        for block in group.blocks[:3]:
            prompt += f"- {block.file_path}: {block.kind} at lines {block.start_line}-{block.end_line}\n"
            if block.imports:
                prompt += f"  Imports: {', '.join(block.imports[:3])}\n"
        
        # Add detected patterns if available
        if group.metadata.get('patterns'):
            top_patterns = sorted(
                group.metadata['patterns'].items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:2]
            significant_patterns = [p[0] for p in top_patterns if p[1] > 0.1]
            if significant_patterns:
                prompt += f"Detected patterns: {', '.join(significant_patterns)}\n"
        
        return prompt
    
    def _extract_enhanced_context(self, group: CommitGroup) -> str:
        """Extract enhanced context from the group"""
        context_info = []
        
        # Analyze languages
        languages = set()
        for block in group.blocks:
            if hasattr(block, 'lang') and block.lang:
                languages.add(block.lang)
        
        if languages:
            context_info.append(f"Languages: {', '.join(languages)}")
        
        # Analyze file types
        file_extensions = set()
        for file_path in group.files:
            if '.' in file_path:
                ext = file_path.split('.')[-1]
                file_extensions.add(ext)
        
        if file_extensions:
            context_info.append(f"File types: {', '.join(file_extensions)}")
        
        # Analyze directory structure
        directories = set()
        for file_path in group.files:
            directory = '/'.join(file_path.split('/')[:-1])
            if directory:
                directories.add(directory)
        
        if directories:
            common_dirs = [d for d in directories if len(d.split('/')) <= 2]  # Top-level dirs
            if common_dirs:
                context_info.append(f"Directories: {', '.join(common_dirs[:3])}")
        
        return '\n'.join(context_info) if context_info else ""
    
    def _create_fallback_summary(self, group: CommitGroup) -> str:
        """Create heuristic-based fallback summary"""
        patterns = group.metadata.get('patterns', {})
        
        if patterns:
            main_pattern = max(patterns.items(), key=lambda x: x[1])[0]
        else:
            main_pattern = 'update'
        
        # Get common directory
        if group.files:
            common_path = ""
            try:
                import os
                common_path = os.path.commonpath(group.files)
                scope = os.path.basename(common_path) if common_path else 'multiple areas'
            except ValueError:
                scope = 'multiple areas'
        else:
            scope = 'unknown area'
        
        return (
            f"This group involves {main_pattern} changes in {scope}, "
            f"affecting {len(group.files)} files. "
            f"Key modifications include {len(group.blocks)} code blocks with "
            f"potential imports and structural updates."
        )
    
    def get_summary_statistics(self, groups: List[CommitGroup]) -> Dict[str, Any]:
        """Get statistics about summary generation"""
        total_groups = len(groups)
        generated_summaries = sum(1 for g in groups if g.metadata.get('summary_generated', False))
        fallback_summaries = sum(1 for g in groups if g.metadata.get('summary_fallback', False))
        
        summary_lengths = [len(g.summary) for g in groups if g.summary]
        
        return {
            'total_groups': total_groups,
            'generated_summaries': generated_summaries,
            'fallback_summaries': fallback_summaries,
            'success_rate': generated_summaries / total_groups if total_groups > 0 else 0,
            'avg_summary_length': sum(summary_lengths) / len(summary_lengths) if summary_lengths else 0,
            'provider': self.llm_provider_name
        }
