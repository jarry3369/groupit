from groupit.cli.parser import create_parser, validate_arguments


def test_split_parser_accepts_minimal_args():
    parser = create_parser()

    args = parser.parse_args(['split', 'HEAD'])

    assert args.command == 'split'
    assert args.commit_hash == 'HEAD'
    assert args.execute is False
    assert args.llm == 'openai'
    assert validate_arguments(args) == []


def test_split_parser_accepts_execute_flags():
    parser = create_parser()

    args = parser.parse_args(
        [
            'split',
            'abc1234',
            '--execute',
            '--auto-confirm',
            '--llm',
            'none',
            '--preserve-metadata',
            '--preserve-date',
            'single',
            '--date-increment',
            '5',
            '--author',
            'Jane Doe',
            '--author-email',
            'jane@example.com',
            '--gpg-sign',
            'ABC123',
        ]
    )

    assert args.command == 'split'
    assert args.commit_hash == 'abc1234'
    assert args.execute is True
    assert args.auto_confirm is True
    assert args.llm == 'none'
    assert args.preserve_metadata is True
    assert args.preserve_date == 'single'
    assert args.date_increment == 5
    assert args.author == 'Jane Doe'
    assert args.author_email == 'jane@example.com'
    assert args.gpg_sign == 'ABC123'
