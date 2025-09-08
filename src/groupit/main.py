#!/usr/bin/env python3

import sys
from pathlib import Path

def main() -> int:
    """
    Main entry point for the groupit application
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Fast version check - handle before importing heavy modules
        if len(sys.argv) >= 2 and sys.argv[1] in ['--version']:
            print(_get_pkg_version())
            return 0
        
        # Import CLI components only when needed
        from .cli import create_parser
        from .cli.commands import analyze_command, commit_command, status_command, validate_command
        from .cli.parser import validate_arguments
        from .config import setup_logging
        
        # Create and parse arguments
        parser = create_parser()
        args = parser.parse_args()
        
        if hasattr(args, 'version') and args.version:
            print(_get_pkg_version())
            return 0
        
        # Show help if no command provided
        if not args.command:
            parser.print_help()
            return 0
        
        # Validate arguments
        validation_errors = validate_arguments(args)
        if validation_errors:
            print("Error: Invalid arguments:", file=sys.stderr)
            for error in validation_errors:
                print(f"  - {error}", file=sys.stderr)
            return 1
        
        # Setup basic logging (commands will configure detailed logging)
        setup_logging()
        
        # Load configuration file if specified
        if hasattr(args, 'config') and args.config:
            from .config import get_settings
            config_path = Path(args.config)
            if config_path.exists():
                get_settings(config_path, force_reload=True)
        
        # Dispatch to appropriate command
        if args.command == 'analyze':
            return analyze_command(args)
        elif args.command == 'commit':
            return commit_command(args)
        elif args.command == 'status':
            return status_command(args)
        elif args.command == 'validate':
            return validate_command(args)
        else:
            print(f"Error: Unknown command '{args.command}'", file=sys.stderr)
            parser.print_help()
            return 1
            
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130  # Standard exit code for SIGINT
        
    except ImportError as e:
        print(f"Error: Missing dependency - {e}", file=sys.stderr)
        print("Please install required dependencies with: pip install -r requirements.txt", file=sys.stderr)
        return 1
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _pkg_info(ov: bool = False) -> str:
    """Get version information dynamically from package metadata
    
    Args:
        ov: If True, return only version number. If False, return detailed info.
    """
    # Fast path: just get version number
    if ov:
        pkg_version = _get_pkg_version()
        return f"v{pkg_version}"
    
    # Full path: get all information
    import sys
    from pathlib import Path
    
    try:
        # Try to get version from installed package metadata
        from importlib.metadata import version, metadata
        pkg_version = version("groupit")
        pkg_metadata = metadata("groupit")
        dependencies = pkg_metadata.get_all("Requires-Dist") or []
    except Exception:
        # Fallback: try pkg_resources or read from pyproject.toml
        try:
            import pkg_resources
            dist = pkg_resources.get_distribution("groupit")
            pkg_version = dist.version
            dependencies = [str(req) for req in dist.requires()]
        except Exception:
            # Final fallback: read from pyproject.toml
            pkg_version, dependencies = _read_from_pyproject()
    
    # Get Python version requirement
    python_version = _get_python_requirement()
    
    # Format dependencies for display
    dep_lines = _format_dependencies(dependencies)
    
    return f"""
v{pkg_version}

System Requirements:
- Python {python_version}
- Git
Core Dependencies:
{dep_lines}
"""


def _get_pkg_version() -> str:
    """Ultra-fast version check without any heavy imports"""
    try:
        # Try installed package first (if available)
        from importlib.metadata import version
        return f"v{version('groupit')}"
    except Exception:
        # Read directly from pyproject.toml
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                return "v0.1.0"  # fallback
        
        try:
            # Use relative path from current file
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent
            pyproject_path = project_root / "pyproject.toml"
            
            if pyproject_path.exists():
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)
                version_str = data.get("project", {}).get("version", "0.1.0")
                return f"v{version_str}"
        except Exception:
            pass
    
    return "v0.1.0"

def _read_from_pyproject() -> tuple[str, list[str]]:
    """Read version and dependencies from pyproject.toml"""
    try:
        import tomllib
    except ImportError:
        # Fallback for Python < 3.11
        try:
            import tomli as tomllib
        except ImportError:
            return "unknown", []
    
    try:
        # Find pyproject.toml file
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent  # Go up from src/groupit/
        pyproject_path = project_root / "pyproject.toml"
        
        if pyproject_path.exists():
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
            
            version = data.get("project", {}).get("version", "unknown")
            dependencies = data.get("project", {}).get("dependencies", [])
            return version, dependencies
    except Exception:
        pass
    
    return "unknown", []


def _get_python_requirement() -> str:
    """Get Python version requirement"""
    try:
        from importlib.metadata import metadata
        pkg_metadata = metadata("groupit")
        python_req = pkg_metadata.get("Requires-Python", ">=3.8")
        return python_req
    except:
        # Fallback: read from pyproject.toml
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                return ">=3.8"
        
        try:
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent
            pyproject_path = project_root / "pyproject.toml"
            
            if pyproject_path.exists():
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)
                return data.get("project", {}).get("requires-python", ">=3.8")
        except Exception:
            pass
    
    return ">=3.8"


def _format_dependencies(dependencies: list[str]) -> str:
    """Format dependencies for display"""
    if not dependencies:
        return "- No dependencies found"
    
    formatted = []
    for dep in dependencies:
        # Clean up dependency string (remove extra conditions, etc.)
        dep_name = dep.split()[0].split(">=")[0].split("==")[0].split("~=")[0]
        if dep_name and not dep_name.startswith("extra"):
            formatted.append(f"- {dep}")
    
    return "\n".join(sorted(formatted)) if formatted else "- No dependencies found"


def debug_info() -> dict:
    """Get debug information for troubleshooting"""
    import platform
    import sys
    
    info = {
        'platform': platform.platform(),
        'python_version': sys.version,
        'python_path': sys.executable,
        'working_directory': str(Path.cwd()),
        'groupit_path': str(Path(__file__).parent),
    }
    
    # Check dependencies
    dependencies = [
        'git', 'sklearn', 'numpy', 'rich', 'unidiff', 'networkx',
        'openai', 'google.generativeai'
    ]
    
    installed_deps = []
    missing_deps = []
    
    for dep in dependencies:
        try:
            __import__(dep)
            installed_deps.append(dep)
        except ImportError:
            missing_deps.append(dep)
    
    info['installed_dependencies'] = installed_deps
    info['missing_dependencies'] = missing_deps
    
    return info


if __name__ == '__main__':
    sys.exit(main())
