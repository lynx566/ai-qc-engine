"""CLI helpers owned by the Aggregate Evidence assess runner."""

from __future__ import annotations

import argparse

from llm.provider_cli import validate_configured_llm_cli_args


def resolve_llm_profile_args(args: argparse.Namespace) -> None:
    validate_configured_llm_cli_args(args)


def resolve_assessment_profile_name(
    llm_input_bundle: dict,
    *,
    override: str | None,
) -> str:
    from runtime.assessment_registry import (
        normalize_assessment_profile_name,
        resolve_assessment_profile,
        warn_deprecated_assessment_profile_alias,
    )

    if override is not None:
        return resolve_assessment_profile(override)
    if "tag_profile_ref" in llm_input_bundle:
        raise SystemExit(
            "assessment input must not include legacy field tag_profile_ref; "
            "use assessment_profile_ref"
        )
    assessment_profile_ref = llm_input_bundle.get("assessment_profile_ref")
    if not assessment_profile_ref:
        raise SystemExit(
            "assessment input missing assessment_profile_ref; "
            "pass --assessment-profile to override"
        )

    token = str(assessment_profile_ref)
    warn_deprecated_assessment_profile_alias(token)
    return resolve_assessment_profile(normalize_assessment_profile_name(token))
