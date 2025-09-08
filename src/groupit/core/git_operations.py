"""
Git operations and diff processing functionality.
"""

from pathlib import Path
from typing import List, Tuple, Dict, Optional
from git import Repo
from unidiff import PatchSet
from rich.console import Console

from .models.change_block import ChangeBlock
from .parsing import build_ts_tree
from ..language_support import (
    load_parsers_for_files, 
    detect_language_from_path,
    analyze_staged_files_for_parsers,
    get_raster_image_extensions,
    get_vector_image_extensions,
    categorize_file_by_extension
)

console = Console()


def collect_diff(repo: Repo, staged: bool) -> PatchSet:
    """Collect git diff as PatchSet"""
    if staged:
        diff_text = repo.git.diff('--staged', unified=0)
    else:
        diff_text = repo.git.diff('HEAD', unified=0)
    return PatchSet(diff_text)


def added_line_ranges_from_hunks(file_patch) -> List[Tuple[int, int]]:
    """Extract line ranges from diff hunks"""
    ranges = []
    for h in file_patch:
        start = None
        cur = None
        for line in h:
            if getattr(line, 'is_added', False) or getattr(line, 'is_removed', False):
                lno = line.target_line_no or line.source_line_no
                if start is None:
                    start = lno
                cur = lno
            else:
                if start is not None and cur is not None:
                    ranges.append((start, cur))
                    start = None
                    cur = None
        if start is not None and cur is not None:
            ranges.append((start, cur))
    
    # Coalesce overlapping ranges
    coalesced = []
    for s, e in sorted(ranges):
        if not coalesced or s > coalesced[-1][1] + 1:
            coalesced.append([s, e])
        else:
            coalesced[-1][1] = max(coalesced[-1][1], e)
    return [(s, e) for s, e in coalesced]


def read_file(repo_root: Path, rel_path: str) -> str:
    """Read file content safely"""
    try:
        with open(repo_root / rel_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ""


def extract_imports(lang: str, text: str) -> List[str]:
    """Extract imports using the enhanced language support system"""
    from ..language_support import language_registry
    
    lang_def = language_registry.get_language_def(lang)
    if not lang_def or not lang_def.import_pattern:
        return []
    
    out = []
    for m in lang_def.import_pattern.finditer(text):
        groups = m.groups()
        if lang == 'python':
            # Python has special handling for from/import patterns
            mod = groups[0] or groups[1]
        else:
            # For most languages, take the first non-empty group
            mod = next((g for g in groups if g), '')
        if mod:
            out.append(mod)
    return list(dict.fromkeys(out))


def ts_blocks_from_diff(repo_root: Path, file_path: str, lang: str, added_lines: List[Tuple[int, int]]) -> List[ChangeBlock]:
    """Create ChangeBlocks from diff using enhanced tree-sitter AST analysis"""
    tree, nodes = build_ts_tree(repo_root, file_path, lang)
    code = read_file(repo_root, file_path)
    if not code:
        return []

    if tree is None or not nodes:
        blocks = []
        lines = code.splitlines()
        for s, e in added_lines:
            code_slice = "\n".join(lines[s-1:e])
            blocks.append(ChangeBlock(
                file_path=file_path, 
                lang=lang, 
                start_line=s, 
                end_line=e, 
                diff_text=code_slice, 
                code_text=code_slice, 
                imports=extract_imports(lang, code_slice), 
                basename=Path(file_path).stem
            ))
        return blocks

    blocks = []
    
    # For new files (entire file is added), split by structural boundaries
    if len(added_lines) == 1 and added_lines[0][0] == 1:
        # This is likely a new file - split by structural boundaries
        structural_blocks = split_file_by_structural_boundaries(code, nodes, file_path, lang)
        blocks.extend(structural_blocks)
        return blocks
    else:
        # For modified files, use the existing logic
        structural_groups = []
        current_group = []
        
        for s, e in added_lines:
            if not current_group:
                current_group = [(s, e)]
            else:
                # Check if this change is structurally related to the current group
                last_s, last_e = current_group[-1]
                
                # Find the most specific AST node for the current change
                candidates = [(n, sl, el, nid) for (n, sl, el, nid) in nodes if sl <= s and el >= e]
                last_candidates = [(n, sl, el, nid) for (n, sl, el, nid) in nodes if sl <= last_s and el >= last_e]
                
                # Check if they belong to the same structural unit (function, class, etc.)
                same_structure = False
                if candidates and last_candidates:
                    # Get the most specific structural node for each
                    current_structural = None
                    last_structural = None
                    
                    for n, sl, el, nid in candidates:
                        if n.type in ['function_definition', 'class_definition', 'method_definition']:
                            current_structural = (n.type, nid)
                            break
                    
                    for n, sl, el, nid in last_candidates:
                        if n.type in ['function_definition', 'class_definition', 'method_definition']:
                            last_structural = (n.type, nid)
                            break
                    
                    # If both have the same structural parent, group them together
                    if current_structural and last_structural and current_structural == last_structural:
                        same_structure = True
                
                # Also check line proximity (within 20 lines)
                if not same_structure and abs(s - last_e) <= 20:
                    # Check if they're in the same logical block (imports, etc.)
                    current_imports = any(n.type in ['import_statement', 'import_from_statement'] 
                                       for n, sl, el, nid in candidates)
                    last_imports = any(n.type in ['import_statement', 'import_from_statement'] 
                                     for n, sl, el, nid in last_candidates)
                    
                    if current_imports and last_imports:
                        same_structure = True
                
                if same_structure:
                    current_group.append((s, e))
                else:
                    # Start a new group
                    structural_groups.append(current_group)
                    current_group = [(s, e)]
        
        if current_group:
            structural_groups.append(current_group)
        
        # Create blocks for each structural group
        for group in structural_groups:
            if not group:
                continue
                
            # Find the best AST node for this group
            group_start = min(s for s, e in group)
            group_end = max(e for s, e in group)
            
            candidates = [(n, sl, el, nid) for (n, sl, el, nid) in nodes 
                         if sl <= group_start and el >= group_end]
            
            if candidates:
                # Prefer function/class definitions, then imports, then smallest node
                function_candidates = [(n, sl, el, nid) for (n, sl, el, nid) in candidates 
                                     if n.type in ['function_definition', 'class_definition', 'method_definition']]
                import_candidates = [(n, sl, el, nid) for (n, sl, el, nid) in candidates 
                                   if n.type in ['import_statement', 'import_from_statement']]
                
                if function_candidates:
                    n, sl, el, nid = min(function_candidates, key=lambda t: t[2]-t[1])
                elif import_candidates:
                    n, sl, el, nid = min(import_candidates, key=lambda t: t[2]-t[1])
                else:
                    n, sl, el, nid = min(candidates, key=lambda t: t[2]-t[1])
                
                code_slice = "\n".join(code.splitlines()[sl-1:el])
                diff_slice = "\n".join(code.splitlines()[group_start-1:group_end])
                
                blocks.append(ChangeBlock(
                    file_path=file_path, 
                    lang=lang, 
                    start_line=sl, 
                    end_line=el, 
                    diff_text=diff_slice, 
                    code_text=code_slice, 
                    imports=extract_imports(lang, code_slice), 
                    basename=Path(file_path).stem, 
                    kind=n.type, 
                    ast_node_id=nid
                ))
            else:
                # Fallback to line-based grouping
                diff_slice = "\n".join(code.splitlines()[group_start-1:group_end])
                blocks.append(ChangeBlock(
                    file_path=file_path, 
                    lang=lang, 
                    start_line=group_start, 
                    end_line=group_end, 
                    diff_text=diff_slice, 
                    code_text=diff_slice, 
                    imports=extract_imports(lang, diff_slice), 
                    basename=Path(file_path).stem, 
                    kind='hunk'
                ))

    return blocks


def split_file_by_structural_boundaries(code: str, nodes: List, file_path: str, lang: str) -> List[ChangeBlock]:
    """Split a new file into structural blocks based on AST analysis"""
    blocks = []
    lines = code.splitlines()
    
    # Find all structural boundaries (functions, classes, imports)
    structural_nodes = []
    for n, sl, el, nid in nodes:
        if n.type in ['function_definition', 'class_definition', 'method_definition', 
                     'import_statement', 'import_from_statement']:
            structural_nodes.append((n, sl, el, nid))
    
    if not structural_nodes:
        # No structural boundaries found, treat as single block
        blocks.append(ChangeBlock(
            file_path=file_path,
            lang=lang,
            start_line=1,
            end_line=len(lines),
            diff_text=code,
            code_text=code,
            imports=extract_imports(lang, code),
            basename=Path(file_path).stem,
            kind='module'
        ))
        return blocks
    
    # Sort by line number
    structural_nodes.sort(key=lambda x: x[1])
    
    # Group related structural elements
    current_group = []
    for n, sl, el, nid in structural_nodes:
        if not current_group:
            current_group = [(n, sl, el, nid)]
        else:
            # Check if this should be grouped with the previous elements
            last_n, last_sl, last_el, last_nid = current_group[-1]
            
            # Group imports together
            if (n.type in ['import_statement', 'import_from_statement'] and 
                last_n.type in ['import_statement', 'import_from_statement']):
                current_group.append((n, sl, el, nid))
            # Group functions/classes that are close together (within 10 lines)
            elif (n.type in ['function_definition', 'class_definition', 'method_definition'] and 
                  last_n.type in ['function_definition', 'class_definition', 'method_definition'] and
                  sl - last_el <= 10):
                current_group.append((n, sl, el, nid))
            else:
                # Create block for current group
                if current_group:
                    create_structural_block(current_group, lines, file_path, lang, blocks)
                current_group = [(n, sl, el, nid)]
    
    # Create block for the last group
    if current_group:
        create_structural_block(current_group, lines, file_path, lang, blocks)
    
    return blocks


def create_structural_block(group: List, lines: List[str], file_path: str, lang: str, blocks: List[ChangeBlock]):
    """Create a ChangeBlock from a group of structural nodes"""
    if not group:
        return
    
    # Find the range for this group
    start_line = min(sl for _, sl, _, _ in group)
    end_line = max(el for _, _, el, _ in group)
    
    # Get the code slice
    code_slice = "\n".join(lines[start_line-1:end_line])
    
    # Determine the primary type
    primary_type = group[0][0].type
    if len(group) > 1:
        # If mixed types, use the most common or most important
        types = [n.type for n, _, _, _ in group]
        if 'function_definition' in types:
            primary_type = 'function_definition'
        elif 'class_definition' in types:
            primary_type = 'class_definition'
        elif 'import_statement' in types or 'import_from_statement' in types:
            primary_type = 'import_group'
    
    blocks.append(ChangeBlock(
        file_path=file_path,
        lang=lang,
        start_line=start_line,
        end_line=end_line,
        diff_text=code_slice,
        code_text=code_slice,
        imports=extract_imports(lang, code_slice),
        basename=Path(file_path).stem,
        kind=primary_type,
        ast_node_id=group[0][3]  # Use the first node's ID
    ))


def build_blocks(repo_root: Path, patch: PatchSet) -> List[ChangeBlock]:
    """Build change blocks with enhanced language support and dynamic parser loading"""
    blocks: List[ChangeBlock] = []
    
    # Collect all file paths from the patch
    file_paths = [file_patch.path for file_patch in patch if not file_patch.is_removed_file]
    
    # Load required parsers dynamically based on file types
    loaded_parsers = load_parsers_for_files(file_paths)
    if loaded_parsers:
        console.print(f"[blue]Loaded parsers: {', '.join(loaded_parsers)}[/blue]")
    
    processed_files = set()
    skipped_files = []
    
    for file_patch in patch:
        file_path = file_patch.path
        
        if file_patch.is_removed_file:
            blocks.append(ChangeBlock(
                file_path=file_path,
                lang="unknown",
                start_line=0,
                end_line=0,
                diff_text=f"File removed: {file_path}",
                code_text="",
                imports=[],
                basename=Path(file_path).stem,
                kind="removal"
            ))
            continue
        
        # Detect language
        lang = detect_language_from_path(file_path)
        
        if not lang:
            # Check if it's a binary file by examining file type
            file_ext = Path(file_path).suffix.lower()
            raster_extensions = get_raster_image_extensions()
            vector_extensions = get_vector_image_extensions()
            
            if file_ext in raster_extensions or file_ext in vector_extensions:
                lang = 'image_raster' if file_ext in raster_extensions else 'image_vector'
                blocks.append(ChangeBlock(
                    file_path=file_path,
                    lang=lang,
                    start_line=0,
                    end_line=0,
                    diff_text=f"Binary file: {file_path}",
                    code_text="",
                    imports=[],
                    basename=Path(file_path).stem,
                    kind="binary"
                ))
                continue
            else:
                skipped_files.append(file_path)
                continue
                
        # Get line ranges
        added_lines = added_line_ranges_from_hunks(file_patch)
        if not added_lines:
            continue
            
        # Create blocks using tree-sitter if possible
        file_blocks = ts_blocks_from_diff(repo_root, file_path, lang, added_lines)
        blocks.extend(file_blocks)
        processed_files.add(file_path)
    
    # Detect languages and categories for analysis
    detected_languages = set()
    file_categories = set()
    
    for block in blocks:
        if block.lang != "unknown":
            detected_languages.add(block.lang)
            
        # Categorize files using the language support system
        category = categorize_file_by_extension(block.file_path)
        if category:
            file_categories.add(category)
        else:
            # Default to 'code' for unknown file types
            file_categories.add('code')
    
    return blocks


def stage_and_commit(repo: Repo, blist: List[ChangeBlock], message: str):
    """Stage files and create commit"""
    files = sorted({b.file_path for b in blist})
    repo.index.add(files)
    repo.index.commit(message)
