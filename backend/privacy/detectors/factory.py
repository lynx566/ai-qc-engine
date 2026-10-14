"""
Privacy detector construction from profile + language configuration.

Detector names (``registry``, ``regex``, ``uie``) are validated via
:func:`privacy.config.validate_detector_list`.  UIE / local-model fallback
uses lazy imports so the caller does not pay for paddleNLP unless requested.
"""

from __future__ import annotations

from collections.abc import Iterable

from privacy.detectors.base import SensitiveEntityDetector
from privacy.detectors.composite import CompositeDetector
from privacy.detectors.regex_detector import RegexDetector, RegexRule
from privacy.detectors.registry_detector import RegistryDetector, RegistryEntry
from privacy.profile import PrivacyProfile


def _regex_rules_for_language(
    profile: PrivacyProfile,
    language: str | None,
) -> list[RegexRule]:
    if language is None:
        return []
    return list(profile.regex_rules.get(language, ()))


def _try_uie_detector(
    profile: PrivacyProfile,
    language: str | None,
) -> tuple[SensitiveEntityDetector, str] | None:
    if language is None:
        return None

    schema = profile.uie_schema_by_language.get(language)
    if not schema:
        return None

    try:
        from privacy.detectors.uie_detector import UIEDetector

        return (
            UIEDetector(
                schema,
                denylist=profile.uie_denylist,
            ),
            "uie",
        )
    except ModuleNotFoundError:
        from privacy.detectors.local_model_detector import LocalModelDetector

        return LocalModelDetector(), "local_model"


def build_stage_detectors(
    detector_names: list[str],
    *,
    profile: PrivacyProfile,
    language: str | None,
    registry_entries: Iterable[RegistryEntry] | None = None,
) -> tuple[list[SensitiveEntityDetector], list[str]]:
    """
    Build detectors from an explicit stage plugin list.

    Supported names: ``registry``, ``regex``, ``uie``. ``dictionary`` is rejected.
    A name is omitted from the active list when its prerequisites are missing
    (e.g. no registry entries, no regex rules for language).
    """
    from privacy.config import validate_detector_list

    validate_detector_list(detector_names)
    detectors: list[SensitiveEntityDetector] = []
    kinds: list[str] = []

    for name in detector_names:
        if name == "registry":
            resolved_registry_entries = list(
                profile.registry_entries if registry_entries is None else registry_entries
            )
            if resolved_registry_entries:
                detectors.append(RegistryDetector(resolved_registry_entries))
                kinds.append("registry")
        elif name == "regex":
            regex_rules = _regex_rules_for_language(profile, language)
            if regex_rules:
                detectors.append(RegexDetector(rules=regex_rules))
                kinds.append("regex")
        elif name == "uie":
            uie_detector = _try_uie_detector(profile, language)
            if uie_detector is not None:
                detector, kind = uie_detector
                detectors.append(detector)
                kinds.append(kind)

    return detectors, kinds


def build_mask_detectors(
    *,
    profile: PrivacyProfile,
    language: str | None,
    enable_uie: bool = False,
    registry_entries: Iterable[RegistryEntry] | None = None,
) -> tuple[list[SensitiveEntityDetector], list[str]]:
    """
    Build active mask detectors for a profile + language (after_extract defaults).

    Registry (clinical program) runs first for the default clinical profile.
    Regex is omitted when ``profile.regex_rules[language]`` is empty.
    UIE is off by default; enable with ``enable_uie=True`` (lazy import).
    """
    names: list[str] = ["registry", "regex"]
    if enable_uie:
        names.append("uie")
    return build_stage_detectors(
        names,
        profile=profile,
        language=language,
        registry_entries=registry_entries,
    )


def _build_composite_detector(
    *,
    language: str | None,
    profile: PrivacyProfile,
    enable_uie: bool = False,
) -> CompositeDetector:
    detectors, _kinds = build_mask_detectors(
        profile=profile,
        language=language,
        enable_uie=enable_uie,
    )
    return CompositeDetector(detectors=detectors)
