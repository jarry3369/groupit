"""
Configuration path helpers.
"""

import os
from pathlib import Path


def get_default_config_path() -> Path:
    """Return the default user config path for the current platform."""
    if os.name == 'nt':
        appdata = os.getenv('APPDATA')
        if appdata:
            return Path(appdata) / 'groupit' / 'config.json'

    config_root = Path(os.getenv('XDG_CONFIG_HOME', Path.home() / '.config'))
    return config_root / 'groupit' / 'config.json'
