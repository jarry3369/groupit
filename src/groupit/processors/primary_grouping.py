"""
Primary grouping processor using DBSCAN and structural analysis.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_distances
from sklearn.cluster import DBSCAN

from .base import CommitGroupProcessor, ProcessorError
from ..core.models import CommitGroup
from ..core.models.change_block import ChangeBlock
from ..core.clustering import build_graph, make_corpus, vectorize, adjacency_matrix_from_graph
from ..config import get_logger

logger = get_logger(__name__)


class StructuralAnalyzer:
    """Enhanced structural analysis with multiple similarity metrics"""
    
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        
    def analyze_semantic_patterns(self, blocks: List[ChangeBlock]) -> Dict[str, float]:
        """Extract semantic patterns from code changes"""
        patterns = {
            'refactoring': 0.0,
            'feature': 0.0,
            'bugfix': 0.0,
            'test': 0.0,
            'documentation': 0.0,
            'performance': 0.0,
            'security': 0.0
        }
        
        for block in blocks:
            text = block.diff_text.lower()
            
            # Pattern detection using regex
            import re
            if re.search(r'(refactor|restructure|reorganize|cleanup)', text):
                patterns['refactoring'] += 1
            if re.search(r'(feat|feature|implement|add\s+new)', text):
                patterns['feature'] += 1
            if re.search(r'(fix|bug|issue|error|exception)', text):
                patterns['bugfix'] += 1
            if re.search(r'(test|spec|assert|expect|mock)', text):
                patterns['test'] += 1
            if re.search(r'(doc|comment|readme|todo)', text):
                patterns['documentation'] += 1
            if re.search(r'(perf|optimize|speed|cache|lazy)', text):
                patterns['performance'] += 1
            if re.search(r'(security|auth|encrypt|sanitize|validate)', text):
                patterns['security'] += 1
                
        # Normalize
        total = sum(patterns.values())
        if total > 0:
            for key in patterns:
                patterns[key] /= total
                
        return patterns
    
    def calculate_architectural_similarity(self, blocks: List[ChangeBlock]) -> np.ndarray:
        """Calculate architectural-level similarity between blocks"""
        n = len(blocks)
        sim_matrix = np.zeros((n, n))
        
        for i in range(n):
            for j in range(i+1, n):
                sim = 0.0
                
                # Same directory structure
                dir_i = os.path.dirname(blocks[i].file_path)
                dir_j = os.path.dirname(blocks[j].file_path)
                if dir_i == dir_j:
                    sim += 0.3
                elif dir_i and dir_j and os.path.commonpath([dir_i, dir_j]):
                    sim += 0.1
                    
                # Similar file types
                if blocks[i].kind == blocks[j].kind:
                    sim += 0.2
                    
                # Shared imports
                imports_i = set(blocks[i].imports)
                imports_j = set(blocks[j].imports)
                if imports_i and imports_j:
                    jaccard = len(imports_i & imports_j) / len(imports_i | imports_j)
                    sim += 0.5 * jaccard
                    
                sim_matrix[i, j] = sim_matrix[j, i] = sim
                
        return sim_matrix


class PrimaryGroupingProcessor(CommitGroupProcessor):
    """Processor for primary structural grouping using DBSCAN"""
    
    def __init__(
        self, 
        repo_root: Path,
        eps: float = 0.35,
        min_samples: int = 2,
        alpha: float = 0.4,
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__("PrimaryGrouping", config)
        self.repo_root = repo_root
        self.eps = eps
        self.min_samples = min_samples
        self.alpha = alpha
        self.analyzer = StructuralAnalyzer(repo_root)
        
    def process(self, input_data: List[ChangeBlock]) -> List[CommitGroup]:
        """
        Perform primary grouping using DBSCAN and structural analysis
        
        Args:
            input_data: List of ChangeBlock objects
            
        Returns:
            List of CommitGroup objects
        """
        if not input_data:
            return []
        
        logger.info(f"Starting primary grouping for {len(input_data)} change blocks")
        
        try:
            # Build graph and compute vectors
            graph = build_graph(input_data)
            corpus = make_corpus(input_data)
            _, X = vectorize(corpus)
            
            # Enhanced similarity with architectural patterns
            arch_sim = self.analyzer.calculate_architectural_similarity(input_data)
            
            # Combine different similarity metrics
            D_cos = cosine_distances(X)
            nodes = [block.key() for block in input_data]
            A = adjacency_matrix_from_graph(graph, nodes)
            
            # Three-way combination: content + graph + architecture
            S = (1.0 - D_cos) * 0.4 + A * 0.3 + arch_sim * 0.3
            D = np.clip(1.0 - S, 0.0, 1.0)
            
            # Perform DBSCAN clustering
            db = DBSCAN(eps=self.eps, min_samples=self.min_samples, metric='precomputed')
            labels = db.fit_predict(D)
            
            # Handle noise points by giving them unique labels
            if (labels == -1).any():
                next_id = labels.max() + 1
                for i, label in enumerate(labels):
                    if label == -1:
                        labels[i] = next_id
                        next_id += 1
            
            # Create CommitGroup objects
            groups_dict: Dict[int, List[ChangeBlock]] = defaultdict(list)
            for block, label in zip(input_data, labels):
                groups_dict[label].append(block)
            
            groups = []
            for group_id, group_blocks in groups_dict.items():
                files = sorted(set(block.file_path for block in group_blocks))
                patterns = self.analyzer.analyze_semantic_patterns(group_blocks)
                
                group = CommitGroup(
                    group_id=group_id,
                    blocks=group_blocks,
                    files=files,
                    metadata={
                        'stage': 'primary',
                        'patterns': patterns,
                        'block_count': len(group_blocks),
                        'file_count': len(files),
                        'clustering_params': {
                            'eps': self.eps,
                            'min_samples': self.min_samples,
                            'alpha': self.alpha
                        }
                    }
                )
                groups.append(group)
            
            logger.info(f"Created {len(groups)} primary groups")
            return groups
            
        except Exception as e:
            logger.error(f"Primary grouping failed: {e}")
            raise ProcessorError(f"Primary grouping failed: {e}")
    
    def validate_input(self, input_data: List[ChangeBlock]) -> bool:
        """Validate input is a list of ChangeBlock objects"""
        if not isinstance(input_data, list):
            return False
        
        # Import ChangeBlock here to avoid circular imports
        from ..core.models.change_block import ChangeBlock
        return all(isinstance(item, ChangeBlock) for item in input_data)
    
    def get_clustering_statistics(self, groups: List[CommitGroup]) -> Dict[str, Any]:
        """Get statistics about the clustering results"""
        if not groups:
            return {}
        
        group_sizes = [len(group.blocks) for group in groups]
        file_counts = [len(group.files) for group in groups]
        
        return {
            'total_groups': len(groups),
            'avg_group_size': sum(group_sizes) / len(group_sizes),
            'min_group_size': min(group_sizes),
            'max_group_size': max(group_sizes),
            'avg_files_per_group': sum(file_counts) / len(file_counts),
            'total_blocks': sum(group_sizes),
            'total_files': sum(len(group.files) for group in groups)
        }
