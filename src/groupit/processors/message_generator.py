"""
Message generator processor for creating conventional commit messages.
"""

import os
import json
from typing import List, Dict, Any, Optional

from .base import CommitGroupProcessor, ProcessorError
from ..core.models import CommitGroup
from ..llm import get_llm_provider, LLMError
from ..config import get_logger

logger = get_logger(__name__)


class MessageGeneratorProcessor(CommitGroupProcessor):
    """Processor for generating conventional commit messages"""
    
    def __init__(
        self,
        llm_provider: str = 'openai',
        api_key: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__("MessageGenerator", config)
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
        Generate conventional commit messages for groups
        
        Args:
            input_data: List of CommitGroup objects with summaries and themes
            
        Returns:
            List of CommitGroup objects with commit messages
        """
        if not input_data:
            return []
        
        logger.info(f"Generating commit messages for {len(input_data)} groups")
        
        groups_with_messages = []
        successful_messages = 0
        
        for group in input_data:
            try:
                message_data = self._generate_commit_message(group)
                
                # Create updated group with commit message
                updated_group = CommitGroup(
                    group_id=group.group_id,
                    blocks=group.blocks,
                    files=group.files,
                    summary=group.summary,
                    commit_message=message_data.get('commit_message'),
                    semantic_theme=group.semantic_theme,
                    confidence_score=group.confidence_score,
                    metadata={
                        **group.metadata,
                        'commit_type': message_data.get('type'),
                        'commit_scope': message_data.get('scope'),
                        'commit_description': message_data.get('description'),
                        'message_generated': True,
                        'message_provider': self.llm_provider_name
                    }
                )
                
                groups_with_messages.append(updated_group)
                successful_messages += 1
                
                logger.debug(f"Generated message for group {group.group_id}: {message_data.get('commit_message', 'N/A')[:100]}...")
                
            except Exception as e:
                logger.warning(f"Failed to generate commit message for group {group.group_id}: {e}")
                
                # Use fallback message
                fallback_message = self._create_fallback_message(group)
                
                updated_group = CommitGroup(
                    group_id=group.group_id,
                    blocks=group.blocks,
                    files=group.files,
                    summary=group.summary,
                    commit_message=fallback_message['commit_message'],
                    semantic_theme=group.semantic_theme,
                    confidence_score=group.confidence_score,
                    metadata={
                        **group.metadata,
                        'commit_type': fallback_message.get('type'),
                        'commit_scope': fallback_message.get('scope'),
                        'commit_description': fallback_message.get('description'),
                        'message_generated': False,
                        'message_fallback': True,
                        'message_error': str(e)
                    }
                )
                
                groups_with_messages.append(updated_group)
        
        logger.info(f"Generated {successful_messages}/{len(input_data)} commit messages successfully")
        return groups_with_messages
    
    def _generate_commit_message(self, group: CommitGroup) -> Dict[str, str]:
        """Generate commit message using LLM"""
        prompt = self._create_message_prompt(group)
        
        try:
            response = self.llm_provider.generate(
                prompt=prompt,
                system_prompt="You are a commit message expert. Create conventional commit messages.",
                temperature=0.3,
                max_tokens=300
            )
            
            # Parse JSON response
            try:
                if hasattr(self.llm_provider, 'parse_json_response'):
                    return self.llm_provider.parse_json_response(response)
                else:
                    return self._parse_json_response(response.content)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON response: {e}")
                return self._create_fallback_message(group)
            
        except LLMError as e:
            logger.error(f"LLM error generating commit message: {e}")
            raise ProcessorError(f"LLM commit message generation failed: {e}")
    
    def _create_message_prompt(self, group: CommitGroup) -> str:
        """Create prompt for generating commit message"""
        prompt = f"""Generate a conventional commit message for this group.
Format: type(scope): description

- Type: feat, fix, refactor, test, docs, perf, chore, style, ci, build
- Scope: affected area (optional but recommended)
- Description: concise what was done
- Add body if needed for details (multi-line)

Guidelines:
- Use present tense ("add" not "added")
- Keep description under 72 characters
- Be specific but concise
- Focus on WHAT and WHY, not HOW

Group Information:
Summary: {group.summary or 'No summary available'}
Theme: {group.semantic_theme or 'N/A'}
Files: {', '.join(group.files[:5])}{'...' if len(group.files) > 5 else ''}
Block Count: {len(group.blocks)}

"""
        
        # Add pattern analysis if available
        if group.metadata.get('patterns'):
            patterns = group.metadata['patterns']
            top_pattern = max(patterns.items(), key=lambda x: x[1])[0]
            prompt += f"Detected Pattern: {top_pattern}\n"
        
        # Add merge information if available
        if group.metadata.get('merged_from'):
            prompt += f"Merged from groups: {group.metadata['merged_from']}\n"
            if group.metadata.get('merge_reason'):
                prompt += f"Merge reason: {group.metadata['merge_reason']}\n"
        
        # Add file type analysis
        file_types = self._analyze_file_types(group.files)
        if file_types:
            prompt += f"File types: {', '.join(file_types)}\n"
        
        prompt += """
Respond with JSON:
{
    "commit_message": "full message (multi-line ok)",
    "type": "commit type",
    "scope": "commit scope",
    "description": "short description"
}

Examples:
- feat(auth): add user login validation
- fix(ui): resolve button alignment issue
- refactor(api): simplify user service endpoints
- docs(readme): update installation instructions
"""
        
        return prompt
    
    def _analyze_file_types(self, files: List[str]) -> List[str]:
        """Analyze file types to help determine scope and type"""
        file_types = set()
        
        for file_path in files:
            if '.' in file_path:
                ext = file_path.split('.')[-1].lower()
                
                # Map extensions to semantic types
                if ext in ['ts', 'tsx', 'js', 'jsx']:
                    if 'component' in file_path.lower() or 'tsx' in ext:
                        file_types.add('component')
                    elif 'test' in file_path.lower() or 'spec' in file_path.lower():
                        file_types.add('test')
                    elif 'api' in file_path.lower() or 'service' in file_path.lower():
                        file_types.add('api')
                    else:
                        file_types.add('frontend')
                elif ext in ['py', 'java', 'cpp', 'c', 'go', 'rust']:
                    file_types.add('backend')
                elif ext in ['md', 'txt', 'rst']:
                    file_types.add('docs')
                elif ext in ['css', 'scss', 'sass', 'less']:
                    file_types.add('styles')
                elif ext in ['json', 'yaml', 'yml', 'toml', 'ini']:
                    file_types.add('config')
                elif ext in ['dockerfile', 'sh', 'bat']:
                    file_types.add('build')
        
        return list(file_types)
    
    def _parse_json_response(self, content: str) -> Dict[str, str]:
        """Parse JSON response with fallback strategies"""
        import re
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            
            # Try to find JSON object in the text
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            
            raise ProcessorError(f"Could not parse JSON from response: {content[:200]}...")
    
    def _create_fallback_message(self, group: CommitGroup) -> Dict[str, str]:
        """Create heuristic-based fallback commit message"""
        # Determine commit type from patterns
        patterns = group.metadata.get('patterns', {})
        if patterns:
            main_pattern = max(patterns.items(), key=lambda x: x[1])[0]
            type_mapping = {
                'feature': 'feat',
                'bugfix': 'fix',
                'refactoring': 'refactor',
                'test': 'test',
                'documentation': 'docs',
                'performance': 'perf',
                'security': 'fix'
            }
            commit_type = type_mapping.get(main_pattern, 'chore')
        else:
            commit_type = 'chore'
        
        # Determine scope from files
        if group.files:
            try:
                common_path = os.path.commonpath(group.files)
                scope = os.path.basename(common_path) if common_path else None
            except ValueError:
                scope = None
            
            # Fallback scope determination
            if not scope:
                file_types = self._analyze_file_types(group.files)
                scope = file_types[0] if file_types else None
        else:
            scope = None
        
        # Create description
        file_count = len(group.files)
        if group.summary:
            # Try to extract first sentence from summary
            first_sentence = group.summary.split('.')[0].strip()
            if len(first_sentence) > 60:
                description = f"update {file_count} files"
            else:
                description = first_sentence.lower()
        else:
            description = f"update {file_count} files"
        
        # Format commit message
        if scope:
            commit_message = f"{commit_type}({scope}): {description}"
        else:
            commit_message = f"{commit_type}: {description}"
        
        # Add body if we have a good summary
        if group.summary and len(group.summary) > len(description) + 20:
            commit_message += f"\n\n{group.summary}"
        
        return {
            "commit_message": commit_message,
            "type": commit_type,
            "scope": scope or "",
            "description": description
        }
    
    def get_message_statistics(self, groups: List[CommitGroup]) -> Dict[str, Any]:
        """Get statistics about commit message generation"""
        total_groups = len(groups)
        generated_messages = sum(1 for g in groups if g.metadata.get('message_generated', False))
        fallback_messages = sum(1 for g in groups if g.metadata.get('message_fallback', False))
        
        # Analyze commit types
        commit_types = {}
        for group in groups:
            commit_type = group.metadata.get('commit_type', 'unknown')
            commit_types[commit_type] = commit_types.get(commit_type, 0) + 1
        
        # Analyze message lengths
        message_lengths = [len(g.commit_message) for g in groups if g.commit_message]
        
        return {
            'total_groups': total_groups,
            'generated_messages': generated_messages,
            'fallback_messages': fallback_messages,
            'success_rate': generated_messages / total_groups if total_groups > 0 else 0,
            'commit_types': commit_types,
            'avg_message_length': sum(message_lengths) / len(message_lengths) if message_lengths else 0,
            'provider': self.llm_provider_name
        }
