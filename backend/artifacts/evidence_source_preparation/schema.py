"""Canonical Evidence Source Preparation artifact vocabulary.

This module holds stage-level vocabulary shared across Evidence Source
Preparation implementations. Concrete evidence-form lifecycle labels,
validators, and artifact envelopes live under scoped ownership paths such as
``artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence``.
"""

from __future__ import annotations

EVIDENCE_SOURCE_PREPARATION_STAGE = "evidence_source_preparation"

__all__ = [
    "EVIDENCE_SOURCE_PREPARATION_STAGE",
]
