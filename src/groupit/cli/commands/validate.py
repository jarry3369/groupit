"""
Validate command implementation.
"""

import argparse

from rich.console import Console

from ...auth import AuthService

console = Console()


def validate_command(args: argparse.Namespace) -> int:
    """
    Execute the validate command
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        console.print("[bold cyan]Validating Groupit Configuration[/bold cyan]")
        
        all_valid = True
        
        # Validate dependencies
        if not _validate_dependencies():
            all_valid = False
        
        # Validate LLM providers
        if not _validate_llm_providers(args.llm_provider, args.api_key):
            all_valid = False
        
        # Validate repository
        if not _validate_repository():
            all_valid = False
        
        # Validate configuration
        if not _validate_configuration():
            all_valid = False
        
        if all_valid:
            console.print("[green]✓ All validations passed[/green]")
            return 0
        else:
            console.print("[red]✗ Some validations failed[/red]")
            return 1
        
    except Exception as e:
        console.print(f"[red]Validation failed: {e}[/red]")
        return 1


def _validate_dependencies() -> bool:
    """Validate required dependencies"""
    console.print("\n[bold]Checking Dependencies[/bold]")
    
    dependencies = [
        ('git', 'GitPython'),
        ('sklearn', 'scikit-learn'),
        ('numpy', 'numpy'),
        ('rich', 'rich'),
        ('unidiff', 'unidiff'),
        ('networkx', 'networkx')
    ]
    
    all_valid = True
    
    for import_name, package_name in dependencies:
        try:
            __import__(import_name)
            console.print(f"[green]✓[/green] {package_name}")
        except ImportError:
            console.print(f"[red]✗[/red] {package_name} - Missing")
            all_valid = False
    
    # Check optional dependencies
    optional_deps = [
        ('openai', 'OpenAI'),
        ('google.genai', 'Google Gen AI')
    ]
    
    console.print("\n[dim]Optional Dependencies:[/dim]")
    for import_name, package_name in optional_deps:
        try:
            __import__(import_name)
            console.print(f"[green]✓[/green] {package_name}")
        except ImportError:
            console.print(f"[yellow]○[/yellow] {package_name} - Not available")
    
    return all_valid


def _validate_llm_providers(specific_provider: str = None, api_key: str = None) -> bool:
    """Validate LLM providers"""
    console.print("\n[bold]Checking LLM Providers[/bold]")
    
    try:
        from ...llm import get_available_providers
        
        providers = get_available_providers()
        console.print(f"Available providers: {', '.join(providers)}")
        
        if not providers:
            console.print("[red]✗ No LLM providers available[/red]")
            return False
        
        all_valid = True
        
        # If specific provider requested, validate only that one
        if specific_provider:
            providers_to_check = [specific_provider]
        else:
            providers_to_check = providers
        
        auth_service = AuthService()

        for provider in providers_to_check:
            if provider not in providers:
                console.print(f"[red]✗[/red] {provider} - Not available")
                all_valid = False
                continue

            if api_key:
                console.print(
                    f"[yellow]Warning:[/yellow] validating {provider} with deprecated --api-key override"
                )

            inspection = auth_service.inspect(provider)
            if not inspection.requires_auth:
                console.print(f"[green]✓[/green] {provider} - Local provider (no API key required)")
                continue

            if inspection.active_source == 'none' and not api_key:
                console.print(f"[yellow]○[/yellow] {provider} - {inspection.diagnostic}")
                continue

            is_valid, resolution = auth_service.validate_active(provider, explicit_api_key=api_key)
            label = auth_service.format_validation_label(resolution.validation_state)
            if is_valid:
                console.print(
                    f"[green]✓[/green] {provider} - Valid ({resolution.source}, {label})"
                )
            else:
                console.print(
                    f"[red]✗[/red] {provider} - Invalid or unreachable ({resolution.source}, {label})"
                )
                console.print(f"[dim]{resolution.diagnostic}[/dim]")
                all_valid = False
        
        return all_valid
        
    except ImportError:
        console.print("[red]✗ LLM module not available[/red]")
        return False


def _validate_repository() -> bool:
    """Validate Git repository"""
    console.print("\n[bold]Checking Repository[/bold]")
    
    try:
        from ...core import CommitGroupingAgent
        
        agent = CommitGroupingAgent()
        status = agent.get_status()
        
        repo_status = status.get('repository', {})
        
        if 'error' in repo_status:
            console.print(f"[red]✗[/red] Repository error: {repo_status['error']}")
            return False
        
        console.print(f"[green]✓[/green] Repository: {repo_status.get('repository_path', 'Unknown')}")
        console.print(f"[green]✓[/green] Branch: {repo_status.get('current_branch', 'Unknown')}")
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗[/red] Repository validation failed: {e}")
        return False


def _validate_configuration() -> bool:
    """Validate configuration"""
    console.print("\n[bold]Checking Configuration[/bold]")
    
    try:
        from ...config import get_settings
        from ...core.pipeline import CommitGroupingPipeline
        from pathlib import Path
        
        settings = get_settings()
        
        # Validate settings structure
        validation_errors = settings.validate()
        
        if validation_errors:
            console.print("[red]Configuration validation errors:[/red]")
            for error in validation_errors:
                console.print(f"[red]  ✗ {error}[/red]")
            return False
        
        # Test pipeline creation
        try:
            pipeline = CommitGroupingPipeline(Path.cwd())
            validation_errors = pipeline.validate_configuration()
            
            if validation_errors:
                console.print("[red]Pipeline validation errors:[/red]")
                for error in validation_errors:
                    console.print(f"[red]  ✗ {error}[/red]")
                return False
        except Exception as e:
            console.print(f"[red]✗[/red] Pipeline validation failed: {e}")
            return False
        
        console.print("[green]✓[/green] Configuration is valid")
        return True
        
    except Exception as e:
        console.print(f"[red]✗[/red] Configuration validation failed: {e}")
        return False
