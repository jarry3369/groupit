"""
GroupingResult data model for representing the complete result of the grouping pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any

from .commit_group import CommitGroup


@dataclass
class GroupingResult:
    """Complete result of the commit grouping pipeline"""
    
    timestamp: str
    repo_path: str
    stage1_groups: List[CommitGroup]  # After primary grouping
    summary_groups: List[CommitGroup]  # After natural language summary
    semantic_groups: List[CommitGroup]  # After LLM semantic grouping
    final_groups: List[CommitGroup]    # After improved message generation
    execution_time: float
    config: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert GroupingResult to dictionary representation"""
        return {
            'timestamp': self.timestamp,
            'repo_path': self.repo_path,
            'execution_time': float(self.execution_time),  # Convert numpy float to Python float
            'config': self.config,
            'stage1_groups': [group.to_dict() for group in self.stage1_groups],
            'summary_groups': [group.to_dict() for group in self.summary_groups],
            'semantic_groups': [group.to_dict() for group in self.semantic_groups],
            'final_groups': [group.to_dict() for group in self.final_groups]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GroupingResult:
        """Create GroupingResult from dictionary representation"""
        return cls(
            timestamp=data['timestamp'],
            repo_path=data['repo_path'],
            execution_time=data['execution_time'],
            config=data['config'],
            stage1_groups=[CommitGroup.from_dict(g) for g in data.get('stage1_groups', [])],
            summary_groups=[CommitGroup.from_dict(g) for g in data.get('summary_groups', [])],
            semantic_groups=[CommitGroup.from_dict(g) for g in data.get('semantic_groups', [])],
            final_groups=[CommitGroup.from_dict(g) for g in data.get('final_groups', [])]
        )
    
    @property
    def total_groups_processed(self) -> int:
        """Total number of groups processed across all stages"""
        return len(self.stage1_groups)
    
    @property
    def final_group_count(self) -> int:
        """Number of final groups after all processing"""
        return len(self.final_groups)
    
    @property
    def compression_ratio(self) -> float:
        """Ratio of final groups to initial groups (measure of consolidation)"""
        if not self.stage1_groups:
            return 0.0
        return len(self.final_groups) / len(self.stage1_groups)
    
    def get_stage_summary(self) -> Dict[str, int]:
        """Get summary of group counts at each stage"""
        return {
            'stage1_primary': len(self.stage1_groups),
            'stage2_summary': len(self.summary_groups),
            'stage3_semantic': len(self.semantic_groups),
            'stage4_final': len(self.final_groups)
        }
