"""
CommitGroup data model for representing groups of related commits/changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from .change_block import ChangeBlock


@dataclass
class CommitGroup:
    """Represents a group of related commits/changes with enhanced metadata"""
    
    group_id: int
    blocks: List[ChangeBlock]
    files: List[str]
    summary: Optional[str] = None
    commit_message: Optional[str] = None
    semantic_theme: Optional[str] = None
    confidence_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert CommitGroup to dictionary representation"""
        return {
            'group_id': int(self.group_id),  # Convert numpy int64 to Python int
            'files': self.files,
            'summary': self.summary,
            'commit_message': self.commit_message,
            'semantic_theme': self.semantic_theme,
            'confidence_score': float(self.confidence_score),  # Convert numpy float to Python float
            'metadata': self.metadata,
            'changes': [
                {
                    'file': block.file_path,
                    'lines': f"{block.start_line}-{block.end_line}",
                    'kind': block.kind,
                    'imports': block.imports
                } for block in self.blocks
            ]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CommitGroup:
        """Create CommitGroup from dictionary representation"""
        return cls(
            group_id=data['group_id'],
            blocks=[],  # Blocks would need to be reconstructed separately
            files=data['files'],
            summary=data.get('summary'),
            commit_message=data.get('commit_message'),
            semantic_theme=data.get('semantic_theme'),
            confidence_score=data.get('confidence_score', 0.0),
            metadata=data.get('metadata', {})
        )
    
    @property
    def block_count(self) -> int:
        """Number of change blocks in this group"""
        return len(self.blocks)
    
    @property
    def file_count(self) -> int:
        """Number of unique files in this group"""
        return len(self.files)
    
    def add_block(self, block: ChangeBlock) -> None:
        """Add a change block to this group"""
        self.blocks.append(block)
        if block.file_path not in self.files:
            self.files.append(block.file_path)
            self.files.sort()
    
    def merge_with(self, other: CommitGroup) -> CommitGroup:
        """Merge this group with another group"""
        merged_blocks = self.blocks + other.blocks
        merged_files = sorted(set(self.files + other.files))
        merged_summaries = []
        
        if self.summary:
            merged_summaries.append(self.summary)
        if other.summary:
            merged_summaries.append(other.summary)
        
        merged_metadata = {**self.metadata, **other.metadata}
        merged_metadata.update({
            'merged_from': [self.group_id, other.group_id],
            'merge_timestamp': None  # Would be set by caller
        })
        
        return CommitGroup(
            group_id=min(self.group_id, other.group_id),
            blocks=merged_blocks,
            files=merged_files,
            summary="\n".join(merged_summaries) if merged_summaries else None,
            semantic_theme=self.semantic_theme or other.semantic_theme,
            confidence_score=max(self.confidence_score, other.confidence_score),
            metadata=merged_metadata
        )
