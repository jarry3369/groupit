"""
Status command implementation.
"""

import argparse
import json

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from ...core import CommitGroupingAgent

console = Console()


def status_command(args: argparse.Namespace) -> int:
    """
    Execute the status command
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Initialize agent
        agent = CommitGroupingAgent()
        
        # Get status information
        status = agent.get_status()
        
        if args.json:
            # Output as JSON
            print(json.dumps(status, indent=2))
        else:
            # Output as formatted tables
            _display_status(status, detailed=args.detailed)
        
        return 0
        
    except Exception as e:
        console.print(f"[red]Failed to get status: {e}[/red]")
        return 1


def _display_status(status: dict, detailed: bool = False) -> None:
    """Display status information in formatted tables"""
    
    # Repository status
    repo_status = status.get('repository', {})
    if 'error' in repo_status:
        console.print(f"[red]Repository Error: {repo_status['error']}[/red]")
    else:
        repo_table = Table(show_header=True, header_style="bold cyan")
        repo_table.add_column("Property", style="cyan")
        repo_table.add_column("Value", style="white")
        
        repo_table.add_row("Repository Path", repo_status.get('repository_path', 'Unknown'))
        repo_table.add_row("Current Branch", repo_status.get('current_branch', 'Unknown'))
        repo_table.add_row("Is Dirty", "Yes" if repo_status.get('is_dirty', False) else "No")
        repo_table.add_row("Untracked Files", str(repo_status.get('untracked_files', 0)))
        repo_table.add_row("Staged Files", str(repo_status.get('staged_files', 0)))
        repo_table.add_row("Modified Files", str(repo_status.get('modified_files', 0)))
        
        console.print(Panel(repo_table, title="Repository Status", border_style="blue"))
    
    # Agent settings
    settings = status.get('settings', {})
    settings_table = Table(show_header=True, header_style="bold green")
    settings_table.add_column("Setting", style="cyan")
    settings_table.add_column("Value", style="white")
    
    settings_table.add_row("LLM Provider", settings.get('llm_provider', 'Unknown'))
    settings_table.add_row("Debug Mode", "Yes" if settings.get('debug_mode', False) else "No")
    settings_table.add_row("Performance Caching", "Yes" if settings.get('performance_caching', False) else "No")
    
    console.print(Panel(settings_table, title="Agent Settings", border_style="green"))
    
    # Pipeline information (if detailed)
    if detailed:
        pipeline_info = status.get('pipeline', {})
        if pipeline_info:
            pipeline_table = Table(show_header=True, header_style="bold magenta")
            pipeline_table.add_column("Property", style="cyan")
            pipeline_table.add_column("Value", style="white")
            
            pipeline_table.add_row("Pipeline Name", pipeline_info.get('pipeline_name', 'Unknown'))
            pipeline_table.add_row("Processor Count", str(pipeline_info.get('processor_count', 0)))
            
            console.print(Panel(pipeline_table, title="Pipeline Information", border_style="magenta"))