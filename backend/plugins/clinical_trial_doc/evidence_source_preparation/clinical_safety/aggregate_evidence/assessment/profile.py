from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.prompts.clinical_safety_aggregate_heading_scope_assessment_zh import (
    DEFAULT_AGGREGATE_HEADING_SCOPE_ASSESSMENT_INSTRUCTIONS,
    build_clinical_safety_aggregate_heading_scope_assessment_zh_messages,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.prompts.clinical_safety_aggregate_heading_scope_assessment_zh import (
    PROMPT_NAME as AGGREGATE_HEADING_SCOPE_ASSESSMENT_PROMPT_NAME,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.prompts.clinical_safety_aggregate_heading_scope_assessment_zh import (
    PROMPT_VERSION as AGGREGATE_HEADING_SCOPE_ASSESSMENT_PROMPT_VERSION,
)

CLINICAL_SAFETY_AGGREGATE_HEADING_SCOPE_ASSESSMENT_ZH_PROFILE_NAME = (
    "clinical_safety_aggregate_heading_scope_assessment_zh"
)

LlmInputGranularity = Literal["unit", "canonical_unit_1to1"]


@dataclass(frozen=True)
class ClinicalTrialDocAssessmentProfile:
    """Business assessment profile: prompt binding for one document/task flavor."""

    name: str
    prompt_name: str
    prompt_version: str
    build_messages: Callable[[dict[str, Any]], list[dict[str, str]]]
    default_instructions: str
    llm_input_granularity: LlmInputGranularity = "unit"


CLINICAL_SAFETY_AGGREGATE_HEADING_SCOPE_ASSESSMENT_ZH_PROFILE = ClinicalTrialDocAssessmentProfile(
    name=CLINICAL_SAFETY_AGGREGATE_HEADING_SCOPE_ASSESSMENT_ZH_PROFILE_NAME,
    prompt_name=AGGREGATE_HEADING_SCOPE_ASSESSMENT_PROMPT_NAME,
    prompt_version=AGGREGATE_HEADING_SCOPE_ASSESSMENT_PROMPT_VERSION,
    build_messages=build_clinical_safety_aggregate_heading_scope_assessment_zh_messages,
    default_instructions=DEFAULT_AGGREGATE_HEADING_SCOPE_ASSESSMENT_INSTRUCTIONS,
    llm_input_granularity="canonical_unit_1to1",
)
