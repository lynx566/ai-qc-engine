"""Tests for caller-owned LLM CLI mode registration in llm/provider_cli.py."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from llm import provider_cli


def _parse(
    argv: list[str],
    *,
    llm_required: bool = False,
    allowed_modes: tuple[str, ...],
) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    provider_cli.register_llm_cli_arguments(
        parser,
        llm_required=llm_required,
        allowed_modes=allowed_modes,
    )
    args = parser.parse_args(argv)
    if llm_required:
        provider_cli.validate_configured_llm_cli_args(args)
    else:
        provider_cli.validate_optional_llm_cli_args(args)
    return args


def test_api_only_registration_rejects_mock() -> None:
    with pytest.raises(SystemExit):
        _parse(["--llm", "mock"], allowed_modes=("api",))


def test_mock_and_api_registration_accepts_mock() -> None:
    args = _parse(
        ["--llm", "mock"],
        llm_required=True,
        allowed_modes=("mock", "api"),
    )

    assert args.llm == "mock"
    assert args.llm_profile is None


def test_build_llm_provider_rejects_mock_mode() -> None:
    args = _parse(
        ["--llm", "mock"],
        llm_required=True,
        allowed_modes=("mock", "api"),
    )

    with pytest.raises(ValueError, match="cannot construct LLMProvider"):
        provider_cli.build_llm_provider_from_cli_args(args)


def test_build_llm_provider_returns_none_when_unconfigured() -> None:
    args = _parse([], allowed_modes=("api",))

    assert provider_cli.build_llm_provider_from_cli_args(args) is None


def test_provider_override_cli_accepts_profile_without_llm_mode() -> None:
    parser = argparse.ArgumentParser()
    provider_cli.register_llm_provider_override_cli_arguments(parser)
    args = parser.parse_args(["--llm-profile", "deepseek_v4_flash", "--no-thinking"])
    provider_cli.validate_optional_llm_provider_override_cli_args(args)

    assert args.llm_profile == "deepseek_v4_flash"
    assert args.thinking is False


def test_build_llm_provider_from_override_uses_installed_defaults() -> None:
    parser = argparse.ArgumentParser()
    provider_cli.register_llm_provider_override_cli_arguments(parser)
    args = parser.parse_args(["--no-thinking"])
    captured: dict[str, object] = {}

    def _build_api_provider(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(provider_cli, "build_api_provider", _build_api_provider)
        provider = provider_cli.build_llm_provider_from_override_cli_args(
            args,
            default_profile="qwen3_7_plus_2026_05_26",
            default_thinking=None,
        )

    assert provider is not None
    assert captured == {
        "llm_profile": "qwen3_7_plus_2026_05_26",
        "thinking": False,
    }
