"""
Auth command implementation.
"""

import argparse
import getpass
import json

from rich.console import Console
from rich.table import Table

from ...auth import AuthService, CredentialStoreUnavailableError

console = Console()


def auth_command(args: argparse.Namespace) -> int:
    """Execute the auth command group."""
    service = AuthService()

    try:
        if args.auth_action == 'login':
            return _login(service, args)
        if args.auth_action == 'logout':
            return _logout(service, args)
        if args.auth_action == 'status':
            return _status(service, args)

        console.print("[red]Unknown auth action[/red]")
        return 1
    except CredentialStoreUnavailableError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1
    except Exception as exc:
        console.print(f"[red]Auth command failed: {exc}[/red]")
        return 1


def _login(service: AuthService, args: argparse.Namespace) -> int:
    if args.provider == 'ollama':
        console.print("[green]ollama does not require authentication[/green]")
        return 0

    credential = args.api_key
    if not credential:
        credential = getpass.getpass(f"{args.provider} API key: ")

    if not credential:
        console.print("[red]No API key provided[/red]")
        return 1

    if args.api_key:
        console.print(
            "[yellow]Warning: passing API keys via --api-key can expose them in shell history.[/yellow]"
        )

    result = service.login(args.provider, credential, validate=not args.no_validate)
    validation_label = service.format_validation_label(result.validation_state)
    console.print(f"[green]Stored credential for {args.provider}[/green]")
    console.print(f"Validation: {validation_label}")
    console.print(f"[dim]{result.diagnostic}[/dim]")
    return 0


def _logout(service: AuthService, args: argparse.Namespace) -> int:
    service.logout(args.provider)
    console.print(f"[green]Removed stored credential for {args.provider}[/green]")
    return 0


def _status(service: AuthService, args: argparse.Namespace) -> int:
    rows = []
    for provider in service.available_providers():
        inspection = service.inspect(provider)
        row = {
            'provider': provider,
            'active_source': inspection.active_source,
            'validation': service.format_validation_label(inspection.validation_state),
            'diagnostic': inspection.diagnostic,
            'stored_available': inspection.stored_available,
            'env_available': inspection.env_available,
        }
        rows.append(row)

    if getattr(args, 'json', False):
        print(json.dumps(rows, indent=2))
        return 0

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Provider", style="cyan")
    table.add_column("Active Source", style="white")
    table.add_column("Validation", style="white")
    table.add_column("Stored", style="white")
    table.add_column("Env", style="white")
    table.add_column("Diagnostic", style="dim")

    for row in rows:
        table.add_row(
            row['provider'],
            row['active_source'],
            row['validation'],
            'yes' if row['stored_available'] else 'no',
            'yes' if row['env_available'] else 'no',
            row['diagnostic'],
        )

    console.print(table)
    return 0
