import argparse
import sys

import groupit.cli as cli_module
import groupit.cli.commands as commands_module
import groupit.cli.parser as parser_module
import groupit.config as config_module
import groupit.main as main_module


def test_lazy_commands_export_auth():
    auth_command = commands_module.__getattr__('auth_command')

    assert auth_command.__name__ == 'auth_command'


def test_main_dispatches_auth(monkeypatch):
    captured = {}

    class DummyParser:
        def parse_args(self):
            return argparse.Namespace(
                command='auth',
                auth_action='status',
                version=False,
                debug=False,
                config=None,
            )

        def print_help(self):
            raise AssertionError('print_help should not be called')

    def fake_auth_command(args):
        captured['command'] = args.command
        captured['auth_action'] = args.auth_action
        return 23

    monkeypatch.setattr(cli_module, 'create_parser', lambda: DummyParser())
    monkeypatch.setattr(parser_module, 'validate_arguments', lambda args: [])
    monkeypatch.setattr(config_module, 'setup_logging', lambda *args, **kwargs: None)
    monkeypatch.setattr(commands_module, '_cached_commands', {'auth_command': fake_auth_command})
    monkeypatch.setattr(sys, 'argv', ['groupit', 'auth', 'status'])

    assert main_module.main() == 23
    assert captured == {'command': 'auth', 'auth_action': 'status'}
