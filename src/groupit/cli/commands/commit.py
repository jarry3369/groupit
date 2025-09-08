"""
Commit command implementation.
"""

import argparse
from pathlib import Path

from rich.console import Console

from ...core import CommitGroupingAgent

console = Console()


def commit_command(args: argparse.Namespace) -> int:
    """
    Execute the commit command
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Validate input file
        input_path = Path(args.input_file)
        if not input_path.exists():
            console.print(f"[red]Error: Input file does not exist: {args.input_file}[/red]")
            return 1
        
        # Initialize agent
        agent = CommitGroupingAgent()
        
        # Check repository status if not forcing
        if not args.force and not _check_repository_status(agent):
            return 1
        
        # Load analysis results
        console.print(f"[cyan]Loading analysis results from {args.input_file}[/cyan]")
        try:
            result = agent.load_results(args.input_file)
        except Exception as e:
            console.print(f"[red]Failed to load results: {e}[/red]")
            return 1
        
        # Validate results
        if not result.final_groups:
            console.print("[yellow]No groups found in results file[/yellow]")
            return 0
        
        # Show what will be committed
        if not args.execute:
            console.print("[yellow]This is a dry run. Use --execute to actually create commits.[/yellow]")
        
        # Create commits
        agent.create_commits(
            result=result,
            dry_run=not args.execute,
            auto_confirm=args.auto_confirm
        )
        
        if args.execute:
            console.print("[green]Commits created successfully[/green]")
        else:
            console.print("[yellow]Dry run completed[/yellow]")
        
        return 0
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Commit creation interrupted by user[/yellow]")
        return 130  # Standard exit code for SIGINT
        
    except Exception as e:
        console.print(f"[red]Commit creation failed: {e}[/red]")
        if hasattr(args, 'debug') and args.debug:
            import traceback
            console.print("[red]Traceback:[/red]")
            console.print(traceback.format_exc())
        return 1


def _check_repository_status(agent: CommitGroupingAgent) -> bool:
    """
    Check repository status and warn about potential issues
    
    Args:
        agent: CommitGroupingAgent instance
        
    Returns:
        True if safe to proceed, False otherwise
    """
    try:
        status = agent.get_status()
        repo_status = status.get('repository', {})
        
        # Check if repository has untracked files
        untracked_count = repo_status.get('untracked_files', 0)
        if untracked_count > 0:
            console.print(f"[yellow]Warning: Repository has {untracked_count} untracked files[/yellow]")
        
        # Check if repository is dirty
        is_dirty = repo_status.get('is_dirty', False)
        if is_dirty:
            console.print("[yellow]Warning: Repository has uncommitted changes[/yellow]")
            
            from rich.prompt import Confirm
            if not Confirm.ask("Continue anyway?"):
                console.print("[yellow]Aborted by user[/yellow]")
                return False
        
        return True
        
    except Exception as e:
        console.print(f"[yellow]Warning: Could not check repository status: {e}[/yellow]")
        return True  # Proceed if we can't check status
