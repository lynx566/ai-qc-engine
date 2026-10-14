"""Semantic configuration contract for clinical-safety Comparison Finding Assessment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..comparison_mode import ComparisonModeId

HeadingSelectionMatchMode = Literal["exact", "contains"]

_SINGLE_SOURCE_COMPARISON_MODE_IDS = frozenset({"scope_local", "focus_comparison"})
_CROSS_COMPARISON_MODE_IDS = frozenset({"ib_to_dsur", "dsur_to_ib"})
_ALL_COMPARISON_MODE_IDS = _SINGLE_SOURCE_COMPARISON_MODE_IDS | _CROSS_COMPARISON_MODE_IDS


def _require_non_empty_str(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must be a non-empty, trimmed string")
    return stripped


@dataclass(frozen=True, slots=True)
class HeadingSelectionProfile:
    """Heading-path term selection inputs for one participant side."""

    include_terms: tuple[str, ...]
    match_mode: HeadingSelectionMatchMode = "contains"
    exclude_terms: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.include_terms:
            raise ValueError("include_terms must be a non-empty tuple")
        for index, term in enumerate(self.include_terms):
            _require_non_empty_str(term, field_name=f"include_terms[{index}]")
        if self.match_mode not in ("exact", "contains"):
            raise ValueError("match_mode must be 'exact' or 'contains'")
        for index, term in enumerate(self.exclude_terms):
            _require_non_empty_str(term, field_name=f"exclude_terms[{index}]")


@dataclass(frozen=True, slots=True)
class IbToDsurComparisonModeBinding:
    """Role bindings for IB scope focus against all DSUR comparison scopes."""

    focus_role_id: str
    comparison_role_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "focus_role_id",
            _require_non_empty_str(self.focus_role_id, field_name="focus_role_id"),
        )
        object.__setattr__(
            self,
            "comparison_role_id",
            _require_non_empty_str(
                self.comparison_role_id,
                field_name="comparison_role_id",
            ),
        )
        if self.focus_role_id == self.comparison_role_id:
            raise ValueError("focus_role_id and comparison_role_id must differ")


@dataclass(frozen=True, slots=True)
class DsurToIbComparisonModeBinding:
    """Role bindings and heading-selection profiles for DSUR-to-IB assessment."""

    dsur_role_id: str
    ib_role_id: str
    dsur_scope_selection: HeadingSelectionProfile
    ib_scope_selection: HeadingSelectionProfile

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "dsur_role_id",
            _require_non_empty_str(self.dsur_role_id, field_name="dsur_role_id"),
        )
        object.__setattr__(
            self,
            "ib_role_id",
            _require_non_empty_str(self.ib_role_id, field_name="ib_role_id"),
        )
        if self.dsur_role_id == self.ib_role_id:
            raise ValueError("dsur_role_id and ib_role_id must differ")
        if not isinstance(self.dsur_scope_selection, HeadingSelectionProfile):
            raise TypeError("dsur_scope_selection must be a HeadingSelectionProfile")
        if not isinstance(self.ib_scope_selection, HeadingSelectionProfile):
            raise TypeError("ib_scope_selection must be a HeadingSelectionProfile")


@dataclass(frozen=True, slots=True)
class ComparisonFindingAssessmentCapabilityDeclaration:
    """Application-declared Finding Assessment inputs for one capability."""

    enabled_comparison_modes: tuple[str, ...]
    participant_role_ids: tuple[str, ...]
    ib_to_dsur: IbToDsurComparisonModeBinding | None = None
    dsur_to_ib: DsurToIbComparisonModeBinding | None = None


@dataclass(frozen=True, slots=True)
class ResolvedClinicalSafetyComparisonFindingAssessmentConfig:
    """Frozen planning configuration for one Finding Assessment invocation."""

    enabled_comparison_modes: tuple[ComparisonModeId, ...]
    participant_role_ids: tuple[str, ...]
    ib_to_dsur: IbToDsurComparisonModeBinding | None = None
    dsur_to_ib: DsurToIbComparisonModeBinding | None = None

    def __post_init__(self) -> None:
        if not self.enabled_comparison_modes:
            raise ValueError("enabled_comparison_modes must be a non-empty tuple")
        seen_modes: set[str] = set()
        for index, mode_id in enumerate(self.enabled_comparison_modes):
            if not isinstance(mode_id, str) or not mode_id.strip():
                raise ValueError(
                    f"enabled_comparison_modes[{index}] must be a non-empty string"
                )
            if mode_id not in _ALL_COMPARISON_MODE_IDS:
                raise ValueError(f"unknown comparison mode id: {mode_id!r}")
            if mode_id in seen_modes:
                raise ValueError(f"duplicate comparison mode id: {mode_id!r}")
            seen_modes.add(mode_id)

        if not self.participant_role_ids:
            raise ValueError("participant_role_ids must be a non-empty tuple")
        seen_roles: set[str] = set()
        for index, role_id in enumerate(self.participant_role_ids):
            normalized = _require_non_empty_str(
                role_id,
                field_name=f"participant_role_ids[{index}]",
            )
            if normalized in seen_roles:
                raise ValueError(f"duplicate participant role_id: {normalized!r}")
            seen_roles.add(normalized)

        enabled_cross = seen_modes & _CROSS_COMPARISON_MODE_IDS
        enabled_single = seen_modes & _SINGLE_SOURCE_COMPARISON_MODE_IDS
        if enabled_cross and enabled_single:
            raise ValueError(
                "single-source and cross comparison modes cannot be enabled together"
            )
        if enabled_cross and len(self.participant_role_ids) < 2:
            raise ValueError(
                "cross comparison modes require at least two participant role IDs"
            )
        if enabled_single and len(self.participant_role_ids) != 1:
            raise ValueError(
                "single-source comparison modes require exactly one participant role ID"
            )

        if "ib_to_dsur" in seen_modes:
            if self.ib_to_dsur is None:
                raise ValueError(
                    "ib_to_dsur comparison mode requires ib_to_dsur configuration"
                )
        elif self.ib_to_dsur is not None:
            raise ValueError(
                "ib_to_dsur configuration requires ib_to_dsur comparison mode"
            )

        if "dsur_to_ib" in seen_modes:
            if self.dsur_to_ib is None:
                raise ValueError(
                    "dsur_to_ib comparison mode requires dsur_to_ib configuration"
                )
        elif self.dsur_to_ib is not None:
            raise ValueError(
                "dsur_to_ib configuration requires dsur_to_ib comparison mode"
            )

        if self.ib_to_dsur is not None:
            _validate_role_membership(
                role_id=self.ib_to_dsur.focus_role_id,
                participant_role_ids=self.participant_role_ids,
                field_name="ib_to_dsur.focus_role_id",
            )
            _validate_role_membership(
                role_id=self.ib_to_dsur.comparison_role_id,
                participant_role_ids=self.participant_role_ids,
                field_name="ib_to_dsur.comparison_role_id",
            )

        if self.dsur_to_ib is not None:
            _validate_role_membership(
                role_id=self.dsur_to_ib.dsur_role_id,
                participant_role_ids=self.participant_role_ids,
                field_name="dsur_to_ib.dsur_role_id",
            )
            _validate_role_membership(
                role_id=self.dsur_to_ib.ib_role_id,
                participant_role_ids=self.participant_role_ids,
                field_name="dsur_to_ib.ib_role_id",
            )


def _validate_role_membership(
    *,
    role_id: str,
    participant_role_ids: tuple[str, ...],
    field_name: str,
) -> None:
    if role_id not in participant_role_ids:
        raise ValueError(
            f"{field_name}={role_id!r} is not declared in participant_role_ids"
        )


__all__ = [
    "ComparisonFindingAssessmentCapabilityDeclaration",
    "DsurToIbComparisonModeBinding",
    "HeadingSelectionMatchMode",
    "HeadingSelectionProfile",
    "IbToDsurComparisonModeBinding",
    "ResolvedClinicalSafetyComparisonFindingAssessmentConfig",
]
