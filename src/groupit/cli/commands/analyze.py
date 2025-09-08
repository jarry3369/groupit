"""
Analyze command implementation.
"""

import argparse
import sys
from pathlib import Path

from rich.console import Console

from ...core import CommitGroupingAgent
from ...config import setup_logging, get_settings, update_settings

console = Console()


def analyze_command(args: argparse.Namespace) -> int:
    """
    Execute the analyze command
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Setup logging based on arguments
        _setup_logging_for_command(args)
        
        # Update settings based on arguments
        _update_settings_from_args(args)
        
        # Initialize agent
        agent = CommitGroupingAgent()
        
        # Validate LLM configuration if needed
        if args.llm != 'none' and not _validate_llm_config(args):
            return 1
        
        # Prepare pipeline overrides
        pipeline_overrides = _extract_pipeline_overrides(args)
        
        # Execute analysis
        result = agent.analyze_changes(
            staged=args.staged,
            llm_provider=args.llm if args.llm != 'none' else None,
            llm_api_key=args.api_key,
            output_file=args.output,
            **pipeline_overrides
        )
        
        if result is None:
            console.print("[yellow]No changes to analyze[/yellow]")
            return 0
        
        # Show summary
        if not args.quiet:
            _show_analysis_summary(result)
        
        console.print("[green]Analysis completed successfully[/green]")
        return 0
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Analysis interrupted by user[/yellow]")
        return 130  # Standard exit code for SIGINT
        
    except Exception as e:
        console.print(f"[red]Analysis failed: {e}[/red]")
        if args.debug:
            import traceback
            console.print("[red]Traceback:[/red]")
            console.print(traceback.format_exc())
        return 1


def _setup_logging_for_command(args: argparse.Namespace) -> None:
    """Setup logging based on command arguments"""
    from ...config.logging_config import LoggingSettings
    
    # Determine log level
    if args.debug:
        level = 'DEBUG'
    elif args.verbose:
        level = 'INFO'
    elif args.quiet:
        level = 'WARNING'
    else:
        level = 'INFO'
    
    # Setup logging
    logging_settings = LoggingSettings(
        level=level,
        enable_console=not args.quiet,
        enable_file=args.debug  # Enable file logging in debug mode
    )
    
    setup_logging(logging_settings)


def _update_settings_from_args(args: argparse.Namespace) -> None:
    """Update global settings based on command arguments"""
    updates = {}
    
    if args.debug:
        updates['debug'] = True
    
    if args.verbose:
        updates['verbose'] = True
    
    if hasattr(args, 'no_caching') and args.no_caching:
        updates['performance'] = get_settings().performance
        updates['performance'].enable_caching = False
    
    if updates:
        update_settings(**updates)


def _validate_llm_config(args: argparse.Namespace) -> bool:
    """Validate LLM configuration"""
    if args.llm == 'none':
        return True
    
    # Import here to avoid circular imports
    from ...llm.providers.registry import provider_requires_api_key
    
    # Check if API key is available for providers that require it
    try:
        requires_key = provider_requires_api_key(args.llm)
    except ValueError:
        # Provider not found, assume it requires API key
        requires_key = True
    
    if requires_key and not args.api_key:
        # Try to get from environment
        import os
        env_key = f'{args.llm.upper()}_API_KEY'
        if not os.getenv(env_key):
            console.print(f"[red]Error: API key required for {args.llm} provider[/red]")
            console.print(f"[yellow]Set {env_key} environment variable or use --api-key option[/yellow]")
            return False
    
    # Try to validate provider
    try:
        from ...llm import validate_provider
        api_key_for_validation = args.api_key if requires_key else "dummy"
        if not validate_provider(args.llm, api_key_for_validation):
            console.print(f"[yellow]Warning: Could not validate {args.llm} provider[/yellow]")
            console.print("[yellow]Proceeding anyway, but analysis might fail[/yellow]")
    except Exception as e:
        console.print(f"[yellow]Warning: Provider validation failed: {e}[/yellow]")
    
    return True


def _extract_pipeline_overrides(args: argparse.Namespace) -> dict:
    """Extract pipeline configuration overrides from arguments"""
    overrides = {}
    
    # Clustering parameters
    if hasattr(args, 'eps'):
        overrides['eps'] = args.eps
    if hasattr(args, 'min_samples'):
        overrides['min_samples'] = args.min_samples
    if hasattr(args, 'alpha'):
        overrides['alpha'] = args.alpha
    
    # LLM parameters
    if hasattr(args, 'model') and args.model:
        overrides['model'] = args.model
    if hasattr(args, 'temperature'):
        overrides['temperature'] = args.temperature
    
    # Processing parameters
    if hasattr(args, 'max_iterations'):
        overrides['max_iterations'] = args.max_iterations
    if hasattr(args, 'batch_size'):
        overrides['batch_size'] = args.batch_size
    
    return overrides


def _show_analysis_summary(result) -> None:
    """Show a brief summary of analysis results"""
    from rich.table import Table
    
    # Create summary table
    summary_table = Table(show_header=True, header_style="bold cyan")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="white")
    
    stage_summary = result.get_stage_summary()
    
    summary_table.add_row("Initial Groups", str(stage_summary['stage1_primary']))
    summary_table.add_row("Final Groups", str(stage_summary['stage4_final']))
    summary_table.add_row("Compression Ratio", f"{result.compression_ratio:.2f}")
    summary_table.add_row("Execution Time", f"{result.execution_time:.2f}s")
    
    total_files = sum(len(group.files) for group in result.final_groups)
    total_changes = sum(len(group.blocks) for group in result.final_groups)
    
    summary_table.add_row("Total Files", str(total_files))
    summary_table.add_row("Total Changes", str(total_changes))
    
    from rich.panel import Panel
    console.print(Panel(summary_table, title="Analysis Summary", border_style="green"))
