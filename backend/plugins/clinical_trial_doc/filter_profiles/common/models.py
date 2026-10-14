from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Language = Literal["zh", "en"]
HeadingMatchMode = Literal["exact", "contains"]


@dataclass(frozen=True)
class HeadingFilterPolicy:
    """Executable heading-based recall policy (selection inputs only)."""

    heading_match_mode: HeadingMatchMode
    heading_terms: tuple[str, ...]
    exclude_heading_terms: tuple[str, ...] = ()
    required_heading_level: int | None = None


@dataclass(frozen=True)
class ClinicalTrialFilterConfig:
    """
    Installed clinical-trial Filter config: identity, catalog metadata, and policy.

    Filter profiles define recall-oriented source selection rules for the filter
    stage. They are not semantic evidence types. Evidence routing into
    aggregate/table/case/risk branches happens later in tag_prepare.

    Identifiers:
    - ``zone_config_name``: stable logical id without version (e.g. ``ib_clinical_safety_zh``).
    - ``zone_config_version``: dot-separated version string (e.g. ``0.2.0``), aligned with
      other ``*_version`` fields in run metadata.
    - ``filter_job_id``: language-neutral product Filter recall job (e.g. ``ib_clinical_safety``).
    """

    zone_config_name: str
    zone_config_version: str
    filter_job_id: str
    language: Language
    policy: HeadingFilterPolicy
    strategy_id: str = "heading_zone"

    def __post_init__(self) -> None:
        if not isinstance(self.filter_job_id, str) or not self.filter_job_id.strip():
            raise ValueError("filter_job_id must be a non-empty string")
