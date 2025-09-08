"""
Command-line argument parser for the commit grouping system.
"""

import argparse
from typing import List

from ..llm import get_available_providers


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the main argument parser"""
    
    parser = argparse.ArgumentParser(
        prog='groupit',
        description='Intelligent commit grouping agent with semantic analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  groupit analyze --staged --llm openai --api-key YOUR_KEY
  groupit analyze --llm gemini --output results.json
  groupit commit results.json --execute
  groupit status
        """
    )
    
    # Global options
    parser.add_argument(
        '--version',
        action='store_true',
        help='Show version information and exit'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode with verbose logging'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration file'
    )
    
    # Create subparsers
    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands',
        metavar='COMMAND'
    )
    
    # Analyze command
    analyze_parser = subparsers.add_parser(
        'analyze',
        help='Analyze changes and create commit groups',
        description='Analyze Git changes using AI-powered semantic grouping'
    )
    _add_analyze_arguments(analyze_parser)
    
    # Commit command
    commit_parser = subparsers.add_parser(
        'commit',
        help='Create commits from analysis results',
        description='Create Git commits from previously analyzed groups'
    )
    _add_commit_arguments(commit_parser)
    
    # Status command
    status_parser = subparsers.add_parser(
        'status',
        help='Show current repository and agent status',
        description='Display information about the repository and agent configuration'
    )
    _add_status_arguments(status_parser)
    
    # Validate command
    validate_parser = subparsers.add_parser(
        'validate',
        help='Validate configuration and dependencies',
        description='Check if all required dependencies and configurations are available'
    )
    _add_validate_arguments(validate_parser)
    
    return parser


def _add_analyze_arguments(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the analyze command"""
    
    # Git options
    git_group = parser.add_argument_group('Git options')
    git_group.add_argument(
        '--staged',
        action='store_true',
        help='Analyze only staged changes (default: working directory changes)'
    )
    
    # Clustering options
    clustering_group = parser.add_argument_group('Clustering options')
    clustering_group.add_argument(
        '--eps',
        type=float,
        default=0.35,
        help='DBSCAN eps parameter for clustering (default: 0.35)'
    )
    clustering_group.add_argument(
        '--min-samples',
        type=int,
        default=2,
        help='DBSCAN minimum samples parameter (default: 2)'
    )
    clustering_group.add_argument(
        '--alpha',
        type=float,
        default=0.4,
        help='Graph weight factor in similarity calculation (default: 0.4)'
    )
    
    # LLM options
    llm_group = parser.add_argument_group('LLM options')
    
    available_providers = []
    try:
        available_providers = get_available_providers()
    except Exception:
        available_providers = ['openai', 'gemini']
    
    llm_group.add_argument(
        '--llm',
        choices=available_providers + ['none'],
        default='openai',
        help=f'LLM provider for semantic analysis (default: openai, available: {", ".join(available_providers)})'
    )
    llm_group.add_argument(
        '--api-key',
        type=str,
        help='API key for LLM provider (can also use environment variables)'
    )
    llm_group.add_argument(
        '--model',
        type=str,
        help='Specific model to use (uses provider default if not specified)'
    )
    llm_group.add_argument(
        '--temperature',
        type=float,
        default=0.3,
        help='LLM temperature for generation (default: 0.3)'
    )
    
    # Processing options
    processing_group = parser.add_argument_group('Processing options')
    processing_group.add_argument(
        '--max-iterations',
        type=int,
        default=2,
        help='Maximum iterations for semantic grouping (default: 2)'
    )
    processing_group.add_argument(
        '--batch-size',
        type=int,
        default=5,
        help='Batch size for processing large numbers of groups (default: 5)'
    )
    processing_group.add_argument(
        '--no-caching',
        action='store_true',
        help='Disable caching for this run'
    )
    
    # Output options
    output_group = parser.add_argument_group('Output options')
    output_group.add_argument(
        '--output', '-o',
        type=str,
        help='Save results to JSON file'
    )
    output_group.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    output_group.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress non-essential output'
    )


def _add_commit_arguments(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the commit command"""
    
    parser.add_argument(
        'input_file',
        type=str,
        help='JSON file containing analysis results'
    )
    
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually create commits (default is dry-run)'
    )
    
    parser.add_argument(
        '--auto-confirm',
        action='store_true',
        help="Don't ask for confirmation before creating commits"
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force commit creation even if repository is dirty'
    )


def _add_status_arguments(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the status command"""
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output status in JSON format'
    )
    
    parser.add_argument(
        '--detailed',
        action='store_true',
        help='Show detailed status information'
    )


def _add_validate_arguments(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the validate command"""
    
    parser.add_argument(
        '--llm-provider',
        type=str,
        help='Validate specific LLM provider'
    )
    
    parser.add_argument(
        '--api-key',
        type=str,
        help='API key to validate'
    )
    
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Attempt to fix validation issues'
    )


def validate_arguments(args: argparse.Namespace) -> List[str]:
    """
    Validate parsed arguments and return list of validation errors
    
    Args:
        args: Parsed arguments from argparse
        
    Returns:
        List of validation error messages
    """
    errors = []
    
    # Validate analyze command arguments
    if args.command == 'analyze':
        if args.eps <= 0:
            errors.append("--eps must be positive")
        
        if args.min_samples < 1:
            errors.append("--min-samples must be at least 1")
        
        if args.alpha < 0 or args.alpha > 1:
            errors.append("--alpha must be between 0 and 1")
        
        if args.temperature < 0 or args.temperature > 2:
            errors.append("--temperature must be between 0 and 2")
        
        if args.max_iterations < 1:
            errors.append("--max-iterations must be at least 1")
        
        if args.batch_size < 1:
            errors.append("--batch-size must be at least 1")
        
        if args.quiet and args.verbose:
            errors.append("Cannot use both --quiet and --verbose")
    
    # Validate commit command arguments
    elif args.command == 'commit':
        import os
        if not os.path.exists(args.input_file):
            errors.append(f"Input file does not exist: {args.input_file}")
        
        if not args.input_file.endswith('.json'):
            errors.append("Input file must be a JSON file")
    
    return errors
