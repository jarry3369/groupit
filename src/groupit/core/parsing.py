"""
Tree-sitter parsing functionality for AST analysis.
"""

from pathlib import Path
from typing import Optional, List, Tuple, Any

# Tree-sitter imports
try:
    from tree_sitter import Parser, Language
    _HAS_TS = True
except ImportError:
    _HAS_TS = False
    Parser = None
    Language = None


def _get_language(lang: str):
    """Get language object for given language name - dynamic loading with language support"""
    try:
        # Import language support system
        from ..language_support import language_registry
        
        # Get language definition to find correct tree-sitter name
        lang_def = language_registry.get_language_def(lang)
        if not lang_def or not lang_def.tree_sitter_name:
            return None
        
        # Use the tree_sitter_name from language definition
        tree_sitter_name = lang_def.tree_sitter_name
        module_name = f"tree_sitter_{tree_sitter_name}"
        
        # Dynamic import based on tree-sitter name
        module = __import__(module_name)
        if hasattr(module, 'language'):
            return module.language()
        return None
    except ImportError:
        return None


def ts_parser_for(lang: str) -> Optional[Parser]:
    """Create tree-sitter parser for given language"""
    if not _HAS_TS:
        return None
    try:
        parser = Parser()
        language_obj = _get_language(lang)
        if language_obj:
            parser.language = Language(language_obj)
            return parser
        return None
    except Exception:
        return None


def build_ts_tree(repo_root: Path, file_path: str, lang: str):
    """Build tree-sitter AST for a file with enhanced structural analysis"""
    from .git_operations import read_file
    
    code = read_file(repo_root, file_path)
    if not code:
        return None, None
    parser = ts_parser_for(lang)
    if not parser:
        return None, None
    try:
        tree = parser.parse(bytes(code, 'utf-8'))
    except Exception:
        return None, None

    nodes = []
    nid = 1
    
    # Priority order for different node types (higher priority = more important for grouping)
    priority_types = {
        'function_definition': 10,
        'class_definition': 10,
        'method_definition': 10,
        'import_statement': 8,
        'import_from_statement': 8,
        'decorated_definition': 9,
        'if_statement': 5,
        'for_statement': 5,
        'while_statement': 5,
        'try_statement': 5,
        'with_statement': 5,
        'expression_statement': 3,
        'assignment': 4,
        'return_statement': 4,
        'call': 3,
        'string': 2,
        'comment': 1
    }
    
    def get_priority(node_type: str) -> int:
        return priority_types.get(node_type, 0)
    
    def collect_nodes(node, depth=0):
        nonlocal nid
        if node.is_named:
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            priority = get_priority(node.type)
            
            # Only collect nodes that are meaningful for grouping
            if priority > 0 or node.type in ['module', 'block', 'statement_block']:
                nodes.append((node, start_line, end_line, nid, priority, depth))
                nid += 1
        
        # Recursively process children
        for child in node.children:
            collect_nodes(child, depth + 1)
    
    collect_nodes(tree.root_node)
    
    # Sort nodes by priority (higher first), then by line number
    nodes.sort(key=lambda x: (-x[4], x[1]))
    
    return tree, [(n, sl, el, nid) for n, sl, el, nid, _, _ in nodes]