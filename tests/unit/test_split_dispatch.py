import argparse
import sys

import groupit.cli as cli_module
import groupit.cli.commands as commands_module
import groupit.cli.parser as parser_module
import groupit.config as config_module
import groupit.main as main_module


def test_lazy_commands_export_split():
    split_command = commands_module.__getattr__('split_command')

    assert split_command.__name__ == 'split_command'


def test_main_dispatches_split(monkeypatch):
    captured = {}

    class DummyParser:
        def parse_args(self):
            return argparse.Namespace(
                command='split',
                version=False,
                debug=False,
                config=None,
            )

        def print_help(self):
            raise AssertionError('print_help should not be called')

    def fake_split_command(args):
        captured['command'] = args.command
        return 17

    monkeypatch.setattr(cli_module, 'create_parser', lambda: DummyParser())
    monkeypatch.setattr(parser_module, 'validate_arguments', lambda args: [])
    monkeypatch.setattr(config_module, 'setup_logging', lambda *args, **kwargs: None)
    monkeypatch.setattr(commands_module, '_cached_commands', {'split_command': fake_split_command})
    monkeypatch.setattr(sys, 'argv', ['groupit', 'split', 'HEAD'])

    assert main_module.main() == 17
    assert captured['command'] == 'split'
