"""
ChangeBlock data model for representing code changes.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ChangeBlock:
    """Represents a block of code changes"""
    file_path: str
    lang: str
    start_line: int
    end_line: int
    diff_text: str
    code_text: str
    imports: List[str] = field(default_factory=list)
    basename: str = ""
    kind: str = "hunk"
    ast_node_id: Optional[int] = None

    def key(self) -> str:
        return f"{self.file_path}:{self.start_line}-{self.end_line}"
