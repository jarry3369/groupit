"""
Core components for the commit grouping system.

This module uses lazy loading (PEP 562) to avoid importing heavy
ML dependencies (sklearn, numpy, networkx, sentence-transformers)
until they are actually needed.
"""

__all__ = [
    'CommitGroupingPipeline', 
    'CommitGroupingAgent',
    'ChangeBlock',
    'collect_diff', 
    'build_blocks',
    'build_graph',
    'make_corpus',
    'vectorize',
    'build_ts_tree'
]

# Cache for lazy-loaded components
_cached_components: dict = {}


def __getattr__(name: str):
    """Lazy import of core components (PEP 562)."""
    global _cached_components
    
    if name in _cached_components:
        return _cached_components[name]
    
    if name == 'CommitGroupingPipeline':
        from .pipeline import CommitGroupingPipeline
        _cached_components['CommitGroupingPipeline'] = CommitGroupingPipeline
        return CommitGroupingPipeline
    
    if name == 'CommitGroupingAgent':
        from .agent import CommitGroupingAgent
        _cached_components['CommitGroupingAgent'] = CommitGroupingAgent
        return CommitGroupingAgent
    
    if name == 'ChangeBlock':
        from .models.change_block import ChangeBlock
        _cached_components['ChangeBlock'] = ChangeBlock
        return ChangeBlock
    
    if name in ('collect_diff', 'build_blocks'):
        from .git_operations import collect_diff, build_blocks
        _cached_components.update({
            'collect_diff': collect_diff,
            'build_blocks': build_blocks
        })
        return _cached_components[name]
    
    if name in ('build_graph', 'make_corpus', 'vectorize'):
        from .clustering import build_graph, make_corpus, vectorize
        _cached_components.update({
            'build_graph': build_graph,
            'make_corpus': make_corpus,
            'vectorize': vectorize
        })
        return _cached_components[name]
    
    if name == 'build_ts_tree':
        from .parsing import build_ts_tree
        _cached_components['build_ts_tree'] = build_ts_tree
        return build_ts_tree
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
