"""
Semantic grouper processor using LLM to analyze and merge related groups.
"""

import os
import re
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

from .base import CommitGroupProcessor, ProcessorError
from ..core.models import CommitGroup
from ..llm import get_llm_provider, LLMError
from ..config import get_logger

logger = get_logger(__name__)


class SemanticGrouperProcessor(CommitGroupProcessor):
    """Processor for semantic grouping and merging using LLM analysis"""
    
    def __init__(
        self,
        repo_root: Path,
        llm_provider: str = 'openai',
        api_key: Optional[str] = None,
        max_iterations: int = 2,
        batch_size: int = 5,
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__("SemanticGrouper", config)
        self.repo_root = repo_root
        self.llm_provider_name = llm_provider
        self.api_key = api_key
        self.max_iterations = max_iterations
        self.batch_size = batch_size
        self.max_context_chars = 4096
        self.debug_logs = []
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
        Perform semantic grouping and merging
        
        Args:
            input_data: List of CommitGroup objects with summaries
            
        Returns:
            List of semantically grouped CommitGroup objects
        """
        if not input_data:
            return []
        
        logger.info(f"Starting semantic grouping for {len(input_data)} groups")
        
        # Check if we need batch processing
        if len(input_data) > self.batch_size:
            logger.info(f"Using batch processing with batch size {self.batch_size}")
            return self._process_in_batches(input_data)
        else:
            return self._process_single_batch(input_data)
    
    def _process_in_batches(self, groups: List[CommitGroup]) -> List[CommitGroup]:
        """Process groups in batches"""
        batches = self._create_batches(groups, self.batch_size)
        all_analyses = []
        
        for i, batch in enumerate(batches):
            logger.debug(f"Processing batch {i+1}/{len(batches)}")
            analysis = self._perform_semantic_analysis(batch)
            all_analyses.append(analysis)
        
        # Combine all batch results
        combined_analysis = self._combine_batch_analyses(all_analyses)
        
        # Apply merge suggestions
        return self._apply_merge_suggestions(groups, combined_analysis)
    
    def _process_single_batch(self, groups: List[CommitGroup]) -> List[CommitGroup]:
        """Process groups as a single batch"""
        analysis = self._perform_semantic_analysis(groups)
        return self._apply_merge_suggestions(groups, analysis)
    
    def _create_batches(self, groups: List[CommitGroup], batch_size: int) -> List[List[CommitGroup]]:
        """Split groups into batches"""
        batches = []
        for i in range(0, len(groups), batch_size):
            batch = groups[i:i + batch_size]
            batches.append(batch)
        return batches
    
    def _perform_semantic_analysis(self, groups: List[CommitGroup]) -> Dict[str, Any]:
        """Perform semantic analysis using LLM"""
        for iteration in range(self.max_iterations):
            logger.debug(f"Semantic analysis iteration {iteration + 1}/{self.max_iterations}")
            
            prompt = self._create_grouping_prompt(groups)
            
            try:
                response = self.llm_provider.generate(
                    prompt=prompt,
                    system_prompt="You are an expert in semantic code analysis.",
                    temperature=0.3,
                    max_tokens=2000
                )
                
                # Parse JSON response
                try:
                    if hasattr(self.llm_provider, 'parse_json_response'):
                        result = self.llm_provider.parse_json_response(response)
                    else:
                        result = self._parse_json_response(response.content)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON response: {e}")
                    result = self._create_fallback_analysis(groups)
                
                # Log the response for debugging
                self.debug_logs.append({
                    'iteration': iteration + 1,
                    'response_length': len(str(result)),
                    'merge_suggestions_count': len(result.get('merge_suggestions', [])),
                    'timestamp': time.time()
                })
                
                # Check if we should continue with another iteration
                merge_suggestions = result.get('merge_suggestions', [])
                if not merge_suggestions or iteration == self.max_iterations - 1:
                    return result
                
                # Apply merges and prepare for next iteration
                groups = self._apply_merge_suggestions(groups, result)
                
            except Exception as e:
                logger.warning(f"Semantic analysis iteration {iteration + 1} failed: {e}")
                return self._create_fallback_analysis(groups)
        
        return self._create_fallback_analysis(groups)
    
    def _create_grouping_prompt(self, groups: List[CommitGroup]) -> str:
        """Create enhanced prompt for semantic grouping"""
        # Perform cross-group analysis
        cross_group_analysis = self._analyze_cross_group_data_flow(groups)
        
        prompt = """You are analyzing code changes for DATA FLOW and USER JOURNEY patterns.

CRITICAL: Look for these patterns that indicate changes are part of the same feature/flow:

DATA FLOW PATTERNS:
- Props drilling: data passed from parent → child → grandchild components
- Form data collection → validation → submission chains  
- API calls → data processing → UI display sequences
- User input → state updates → UI feedback loops

FILE HIERARCHY CLUES:
- page.tsx → component.tsx suggests parent-child relationship
- Similar component names in same directory suggest related functionality
- Shared variable/prop names across files indicate data passing

USER JOURNEY PATTERNS:
- Changes that enable a single user action (e.g., "request service")
- Related UI components that work together for one feature
- Sequential steps in a user workflow

ANALYZE THESE GROUPS:
"""
        
        # Add cross-group analysis
        if cross_group_analysis['merge_candidates']:
            prompt += f"\n🔍 CROSS-GROUP ANALYSIS (CRITICAL):\n"
            prompt += f"Found {len(cross_group_analysis['merge_candidates'])} potential merge candidates:\n"
            
            for candidate in cross_group_analysis['merge_candidates']:
                if candidate['type'] == 'page_component_relationship':
                    prompt += f"  🚨 HIGH PRIORITY: Page-Component relationship detected!\n"
                    prompt += f"    Page: {candidate['page_file']}\n"
                    prompt += f"    Component: {candidate['component_file']}\n"
                    prompt += f"    Groups: {candidate['groups']}\n"
                elif candidate['type'] == 'shared_variable':
                    prompt += f"  🔗 Shared variable '{candidate['variable']}' across groups {candidate['groups']}\n"
                elif candidate['type'] == 'shared_component':
                    prompt += f"  🏗️ Shared component '{candidate['component']}' across groups {candidate['groups']}\n"
        
        # Add group details
        for group in groups:
            prompt += f"\n{'='*50}\n"
            prompt += f"## Group {group.group_id}\n"
            prompt += f"📁 Files: {', '.join(group.files)}\n"
            
            # Add data flow analysis
            flow_analysis = self._analyze_data_flow_patterns(group.blocks)
            if flow_analysis['shared_variables']:
                prompt += f"🔗 Variables: {', '.join(list(flow_analysis['shared_variables'])[:10])}\n"
            
            if flow_analysis['component_usage']:
                prompt += f"🏗️ Components: {', '.join(list(flow_analysis['component_usage'])[:5])}\n"
            
            prompt += f"📝 Summary: {group.summary}\n"
            
            if group.semantic_theme:
                prompt += f"🎯 Theme: {group.semantic_theme}\n"
        
        prompt += f"""

{'='*50}

TASK: Analyze for DATA FLOW relationships and respond with JSON:

{{
    "merge_suggestions": [
        {{
            "groups_to_merge": [list of group IDs that should be merged],
            "reason": "detailed explanation of WHY these belong together",
            "data_flow_evidence": "specific evidence of data flowing between components",
            "user_journey_step": "what part of user journey this represents",
            "semantic_theme": "unified theme describing the complete feature/flow",
            "confidence_score": 0.0-1.0
        }}
    ],
    "analysis_notes": "additional insights about the overall change patterns"
}}

FOCUS ON: What is the END-USER trying to accomplish that requires these changes?
"""
        
        return prompt
    
    def _analyze_cross_group_data_flow(self, groups: List[CommitGroup]) -> Dict[str, Any]:
        """Analyze data flow patterns across different groups"""
        cross_group_analysis = {
            'shared_variables': set(),
            'component_connections': [],
            'merge_candidates': []
        }
        
        # Collect variables and components from all groups
        group_variables = {}
        group_components = {}
        
        for group in groups:
            group_vars = set()
            group_comps = set()
            
            for block in group.blocks:
                code_text = block.code_text + ' ' + block.diff_text
                
                # Extract variables
                vars_found = re.findall(r'\b(\w+)\s*[=:]\s*', code_text)
                group_vars.update(vars_found)
                
                # Extract components
                comps_found = re.findall(r'<(\w+)', code_text)
                group_comps.update(comps_found)
            
            group_variables[group.group_id] = group_vars
            group_components[group.group_id] = group_comps
        
        # Find shared variables between groups
        all_variables = set()
        for vars_set in group_variables.values():
            all_variables.update(vars_set)
        
        for var in all_variables:
            groups_with_var = [gid for gid, vars_set in group_variables.items() if var in vars_set]
            if len(groups_with_var) > 1:
                cross_group_analysis['shared_variables'].add(var)
                cross_group_analysis['merge_candidates'].append({
                    'type': 'shared_variable',
                    'variable': var,
                    'groups': groups_with_var,
                    'confidence': 0.8
                })
        
        # Analyze file path relationships
        for i, group1 in enumerate(groups):
            for j, group2 in enumerate(groups[i+1:], i+1):
                for file1 in group1.files:
                    for file2 in group2.files:
                        # Check for page-component relationship
                        if ('page.tsx' in file1 and 'components' in file2) or \
                           ('page.tsx' in file2 and 'components' in file1):
                            cross_group_analysis['merge_candidates'].append({
                                'type': 'page_component_relationship',
                                'page_file': file1 if 'page.tsx' in file1 else file2,
                                'component_file': file2 if 'page.tsx' in file1 else file1,
                                'groups': [group1.group_id, group2.group_id],
                                'confidence': 0.9
                            })
        
        return cross_group_analysis
    
    def _analyze_data_flow_patterns(self, blocks) -> Dict[str, Any]:
        """Analyze data flow patterns within blocks"""
        flow_analysis = {
            'shared_variables': set(),
            'component_usage': set(),
            'function_calls': set()
        }
        
        all_code = ' '.join(block.code_text + ' ' + block.diff_text for block in blocks)
        
        # Extract variables
        variable_matches = re.findall(r'(\w+)\s*=\s*', all_code)
        flow_analysis['shared_variables'].update(variable_matches)
        
        # Extract components
        component_matches = re.findall(r'<(\w+)', all_code)
        flow_analysis['component_usage'].update(component_matches)
        
        # Extract function calls
        function_matches = re.findall(r'(\w+)\s*\(', all_code)
        flow_analysis['function_calls'].update(function_matches)
        
        return flow_analysis
    
    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON response with fallback strategies"""
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
    
    def _create_fallback_analysis(self, groups: List[CommitGroup]) -> Dict[str, Any]:
        """Create fallback analysis when LLM fails"""
        result = {"merge_suggestions": []}
        
        # Simple heuristic: merge groups with shared files or similar paths
        for i, group1 in enumerate(groups):
            for j, group2 in enumerate(groups[i+1:], i+1):
                # Check for shared files
                shared_files = set(group1.files) & set(group2.files)
                if shared_files:
                    result["merge_suggestions"].append({
                        "groups_to_merge": [group1.group_id, group2.group_id],
                        "reason": f"Shared files: {', '.join(shared_files)}",
                        "semantic_theme": "Related file modifications",
                        "confidence_score": 0.7
                    })
                    continue
                
                # Check for similar directory structure
                try:
                    common_path = os.path.commonpath(group1.files + group2.files)
                    if common_path and len(common_path.split('/')) >= 2:
                        result["merge_suggestions"].append({
                            "groups_to_merge": [group1.group_id, group2.group_id],
                            "reason": f"Similar directory structure: {common_path}",
                            "semantic_theme": f"Updates in {os.path.basename(common_path)}",
                            "confidence_score": 0.6
                        })
                except ValueError:
                    pass  # No common path
        
        return result
    
    def _combine_batch_analyses(self, analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Combine analyses from multiple batches"""
        combined = {
            'merge_suggestions': [],
            'analysis_notes': []
        }
        
        for analysis in analyses:
            combined['merge_suggestions'].extend(analysis.get('merge_suggestions', []))
            if analysis.get('analysis_notes'):
                combined['analysis_notes'].append(analysis['analysis_notes'])
        
        return combined
    
    def _apply_merge_suggestions(self, groups: List[CommitGroup], analysis: Dict[str, Any]) -> List[CommitGroup]:
        """Apply merge suggestions to create new groups"""
        merged_groups = {}
        processed_ids = set()
        
        # Sort suggestions by confidence score
        suggestions = sorted(
            analysis.get('merge_suggestions', []), 
            key=lambda x: x.get('confidence_score', 0), 
            reverse=True
        )
        
        for suggestion in suggestions:
            groups_to_merge = suggestion['groups_to_merge']
            if any(gid in processed_ids for gid in groups_to_merge):
                continue
            
            merged_blocks = []
            merged_files = set()
            merged_summaries = []
            
            for gid in groups_to_merge:
                for group in groups:
                    if group.group_id == gid:
                        merged_blocks.extend(group.blocks)
                        merged_files.update(group.files)
                        if group.summary:
                            merged_summaries.append(group.summary)
                        processed_ids.add(gid)
            
            if merged_blocks:
                new_id = min(groups_to_merge)
                merged_group = CommitGroup(
                    group_id=new_id,
                    blocks=merged_blocks,
                    files=sorted(merged_files),
                    summary="\n".join(merged_summaries),
                    semantic_theme=suggestion.get('semantic_theme'),
                    confidence_score=suggestion.get('confidence_score', 0.5),
                    metadata={
                        'stage': 'semantic',
                        'merged_from': groups_to_merge,
                        'merge_reason': suggestion.get('reason'),
                        'data_flow_evidence': suggestion.get('data_flow_evidence'),
                        'user_journey_step': suggestion.get('user_journey_step'),
                        'provider': self.llm_provider_name
                    }
                )
                merged_groups[new_id] = merged_group
        
        # Add non-merged groups
        for group in groups:
            if group.group_id not in processed_ids:
                merged_groups[group.group_id] = group
        
        result = list(merged_groups.values())
        logger.info(f"Semantic grouping resulted in {len(result)} groups")
        return result
    
    def get_semantic_statistics(self, groups: List[CommitGroup]) -> Dict[str, Any]:
        """Get statistics about semantic grouping"""
        merged_groups = sum(1 for g in groups if g.metadata.get('merged_from'))
        total_iterations = len(self.debug_logs)
        
        return {
            'total_groups': len(groups),
            'merged_groups': merged_groups,
            'iterations_performed': total_iterations,
            'debug_logs_count': len(self.debug_logs),
            'provider': self.llm_provider_name
        }
