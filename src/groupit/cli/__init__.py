"""
Command-line interface for the commit grouping system.
"""

from .parser import create_parser
from .commands import analyze_command, commit_command

__all__ = ['create_parser', 'analyze_command', 'commit_command']
