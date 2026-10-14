"""
Content boundary between filter zone matching and downstream LLM (tag).

Principle (do not violate):

    matching source = raw / original structural metadata
    LLM source      = masked textual content

Filter runs on ``analysis_bundle`` but zone heading matching must prefer
``meta.heading_text_stripped``, ``meta.heading_level``,
etc. — fields preserved by the prepare_analysis stage — not ``block["text"]`` when that
carries masked placeholders.

Tag / LLM prompts must consume masked ``analysis_text`` via formal
``assessment_input`` heading-scope evidence (validated by
``artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_safety``).
They must **not** read filter audit fields such as
``match.matched_heading_text``, ``heading_lineage[].text`` (structural), or
``meta.heading_text_stripped`` as prompt body text.
"""

from __future__ import annotations

# Field names — single source of truth for reviews and tests.
LLM_TEXT_FIELD = "analysis_text"
ANALYSIS_TEXT_FIELD = "analysis_text"


def block_analysis_text(block: dict) -> str:
    """
    Downstream analysis text for filter/tag.

    Priority: analysis_text → normalized_text → text (raw extract legacy).
    """
    return str(
        block.get(ANALYSIS_TEXT_FIELD)
        or block.get("normalized_text")
        or block.get("text")
        or ""
    )
STRUCTURAL_HEADING_STRIPPED_FIELD = "heading_text_stripped"

# Filter export fields that are matching / audit metadata only (not LLM input).
FILTER_MATCH_AUDIT_FIELDS = frozenset(
    {
        "matched_heading_text",
        "matched_heading_text_stripped",
        "matched_heading_original_text",
    }
)

FILTER_STRUCTURAL_ONLY_FIELDS = frozenset(
    {
        STRUCTURAL_HEADING_STRIPPED_FIELD,
        "heading_level",
    }
)
