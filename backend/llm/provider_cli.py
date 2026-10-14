"""Generic CLI registration, validation, and provider construction for LLM runtime capability."""

from __future__ import annotations

import argparse

from llm.providers.base import LLMProvider
from llm.providers.factory import build_api_provider

from llm.model_registry import resolve_llm_selection

_API_PROFILE_REQUIRED_MESSAGE = "API execution requires explicit --llm-profile"
_PROVIDER_CAPABLE_LLM_MODE = "api"


def _llm_profile_without_backend_message(allowed_modes: tuple[str, ...]) -> str:
    mode_flags = " or ".join(f"--llm {mode}" for mode in allowed_modes)
    return f"--llm-profile requires {mode_flags}"


def _allowed_llm_modes(args: argparse.Namespace) -> tuple[str, ...]:
    allowed_modes = getattr(args, "_llm_allowed_modes", None)
    if not allowed_modes:
        raise ValueError("CLI args missing registered _llm_allowed_modes")
    return tuple(allowed_modes)


def register_llm_provider_override_cli_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    """Register optional API provider override arguments without --llm mode selection."""

    parser.add_argument(
        "--llm-profile",
        default=None,
        help="Canonical LLM profile override for API provider construction.",
    )
    thinking = parser.add_mutually_exclusive_group()
    thinking.add_argument(
        "--thinking",
        dest="thinking",
        action="store_true",
        help="Explicitly enable provider thinking mode for API execution.",
    )
    thinking.add_argument(
        "--no-thinking",
        dest="thinking",
        action="store_false",
        help="Explicitly disable provider thinking mode for API execution.",
    )
    parser.set_defaults(thinking=None)


def has_llm_provider_override_cli_args(args: argparse.Namespace) -> bool:
    """Return whether CLI args request an explicit provider override."""

    return args.llm_profile is not None or args.thinking is not None


def validate_optional_llm_provider_override_cli_args(args: argparse.Namespace) -> None:
    """Validate optional provider override arguments before execution."""

    if args.llm_profile is not None:
        resolve_llm_selection(args.llm_profile, thinking=args.thinking)


def build_llm_provider_from_override_cli_args(
    args: argparse.Namespace,
    *,
    default_profile: str,
    default_thinking: bool | None,
) -> LLMProvider:
    """Construct an API provider from CLI overrides with installed defaults."""

    profile = args.llm_profile or default_profile
    thinking = args.thinking if args.thinking is not None else default_thinking
    return build_api_provider(
        llm_profile=profile,
        thinking=thinking,
    )


def register_llm_cli_arguments(
    parser: argparse.ArgumentParser,
    *,
    llm_required: bool = False,
    allowed_modes: tuple[str, ...],
) -> None:
    """Register generic LLM CLI arguments on a parser."""

    if not allowed_modes:
        raise ValueError("allowed_modes must contain at least one LLM mode")

    llm_kwargs: dict[str, object] = {
        "choices": list(allowed_modes),
        "required": llm_required,
        "help": (
            "LLM execution mode available to pipeline operations that require an LLM."
        ),
    }
    if not llm_required:
        llm_kwargs["default"] = None
    parser.add_argument("--llm", **llm_kwargs)
    register_llm_provider_override_cli_arguments(parser)
    parser.set_defaults(_llm_allowed_modes=allowed_modes)


def validate_optional_llm_cli_args(args: argparse.Namespace) -> None:
    """Validate optional LLM CLI arguments before execution."""

    llm_mode = getattr(args, "llm", None)
    if llm_mode is None:
        if args.llm_profile is not None:
            raise SystemExit(_llm_profile_without_backend_message(_allowed_llm_modes(args)))
        return
    validate_configured_llm_cli_args(args)


def validate_configured_llm_cli_args(args: argparse.Namespace) -> None:
    """Validate required or explicitly configured LLM CLI arguments."""

    allowed_modes = _allowed_llm_modes(args)
    llm_mode = args.llm
    if llm_mode not in allowed_modes:
        raise SystemExit(
            f"unsupported --llm mode {llm_mode!r}; allowed modes: {', '.join(allowed_modes)}"
        )
    if llm_mode == "mock":
        return
    if llm_mode != _PROVIDER_CAPABLE_LLM_MODE:
        raise SystemExit(
            f"unsupported --llm mode {llm_mode!r}; "
            f"provider construction supports {_PROVIDER_CAPABLE_LLM_MODE!r} only"
        )
    if not args.llm_profile:
        raise SystemExit(_API_PROFILE_REQUIRED_MESSAGE)
    resolve_llm_selection(args.llm_profile, thinking=args.thinking)


def build_llm_provider_from_cli_args(
    args: argparse.Namespace,
) -> LLMProvider | None:
    """Construct an optional LLM provider from provider-capable CLI arguments."""

    llm_mode = getattr(args, "llm", None)
    if llm_mode is None:
        return None
    if llm_mode == _PROVIDER_CAPABLE_LLM_MODE:
        return build_api_provider(
            llm_profile=args.llm_profile,
            thinking=args.thinking,
        )
    raise ValueError(
        f"cannot construct LLMProvider from --llm {llm_mode!r}; "
        f"only {_PROVIDER_CAPABLE_LLM_MODE!r} is provider-capable"
    )


__all__ = [
    "build_llm_provider_from_cli_args",
    "build_llm_provider_from_override_cli_args",
    "has_llm_provider_override_cli_args",
    "register_llm_cli_arguments",
    "register_llm_provider_override_cli_arguments",
    "validate_configured_llm_cli_args",
    "validate_optional_llm_cli_args",
    "validate_optional_llm_provider_override_cli_args",
]
