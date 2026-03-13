from groupit.cli.parser import create_parser, validate_arguments


def test_auth_login_parser_accepts_provider():
    parser = create_parser()

    args = parser.parse_args(['auth', 'login', 'openai'])

    assert args.command == 'auth'
    assert args.auth_action == 'login'
    assert args.provider == 'openai'
    assert args.no_validate is False
    assert validate_arguments(args) == []


def test_auth_status_parser_accepts_json_flag():
    parser = create_parser()

    args = parser.parse_args(['auth', 'status', '--json'])

    assert args.command == 'auth'
    assert args.auth_action == 'status'
    assert args.json is True
    assert validate_arguments(args) == []


def test_auth_validate_arguments_requires_subcommand():
    parser = create_parser()

    args = parser.parse_args(['auth'])

    assert validate_arguments(args) == ['auth requires a subcommand: login, logout, or status']
