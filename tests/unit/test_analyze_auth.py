import argparse

from groupit.auth.service import AuthResolution
from groupit.cli.commands.analyze import _validate_llm_config
import groupit.cli.commands.analyze as analyze_module


def test_validate_llm_config_requires_resolved_credential(monkeypatch):
    monkeypatch.setattr(
        analyze_module,
        'AuthService',
        lambda: type(
            'StubService',
            (),
            {
                'resolve': lambda self, provider, explicit_api_key=None: AuthResolution(
                    provider=provider,
                    credential=None,
                    source='none',
                    requires_auth=True,
                    validation_state='unverified',
                    diagnostic='no credential found',
                )
            },
        )(),
    )

    args = argparse.Namespace(llm='openai', api_key=None)

    assert _validate_llm_config(args) is False


def test_validate_llm_config_accepts_resolved_credential(monkeypatch):
    monkeypatch.setattr(
        analyze_module,
        'AuthService',
        lambda: type(
            'StubService',
            (),
            {
                'resolve': lambda self, provider, explicit_api_key=None: AuthResolution(
                    provider=provider,
                    credential='env-key',
                    source='env',
                    requires_auth=True,
                    validation_state='unverified',
                    diagnostic='environment variable OPENAI_API_KEY is set',
                )
            },
        )(),
    )

    args = argparse.Namespace(llm='openai', api_key=None)

    assert _validate_llm_config(args) is True
