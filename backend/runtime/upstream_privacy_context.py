"""Resolve privacy runtime metadata from upstream mask/prepare_analysis artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.io import load_json


@dataclass(frozen=True)
class UpstreamPrivacyRuntimeContext:
    """Date-shift settings recorded by an upstream privacy/mask run."""

    date_shift_offset_days: int | None = None


def _coerce_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed > 0 else None
    return None


def _extract_from_run_summary(summary: dict[str, Any]) -> UpstreamPrivacyRuntimeContext:
    offset: int | None = None

    privacy_transform = summary.get("privacy_transform")
    if isinstance(privacy_transform, dict):
        settings = privacy_transform.get("settings")
        if isinstance(settings, dict):
            offset = _coerce_positive_int(settings.get("date_shift_offset_days"))

    return UpstreamPrivacyRuntimeContext(date_shift_offset_days=offset)


def _extract_from_privacy_audit(audit: dict[str, Any]) -> UpstreamPrivacyRuntimeContext:
    offset: int | None = None
    date_shift = audit.get("date_shift")
    if isinstance(date_shift, dict):
        offset = _coerce_positive_int(date_shift.get("offset_days"))
    return UpstreamPrivacyRuntimeContext(date_shift_offset_days=offset)


def resolve_upstream_privacy_runtime_context(
    *,
    analysis_bundle_path: Path | str | None = None,
    analysis_bundle: dict[str, Any] | None = None,
    private_audit_bundle: dict[str, Any] | None = None,
) -> UpstreamPrivacyRuntimeContext:
    """
    Read upstream mask runtime metadata when sibling artifacts are available.

    Date-shift offset prefers ``run_summary.json`` beside *analysis_bundle_path*,
    then ``privacy_audit.json``.
    """
    offset: int | None = None

    if analysis_bundle_path is not None:
        analysis_dir = Path(analysis_bundle_path).resolve().parent
        run_summary_path = analysis_dir / "run_summary.json"
        if run_summary_path.is_file():
            summary = load_json(run_summary_path)
            if isinstance(summary, dict):
                extracted = _extract_from_run_summary(summary)
                offset = extracted.date_shift_offset_days

        if offset is None:
            privacy_audit_path = analysis_dir / "privacy_audit.json"
            if privacy_audit_path.is_file():
                audit = load_json(privacy_audit_path)
                if isinstance(audit, dict):
                    offset = _extract_from_privacy_audit(audit).date_shift_offset_days

    return UpstreamPrivacyRuntimeContext(date_shift_offset_days=offset)
