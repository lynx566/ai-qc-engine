from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.routing.primary_sentence_contract import routed_body_text_from_sentences
from steps.filter import (
    extract_zones_from_bundle,
    to_debug_filter_payload,
    to_public_filter_payload,
)
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from tests.filter_test_helpers import resolved_filter_job
from tests.projection_test_helpers import projected_sentence, raw_projected_source
from tests.route_test_fixtures import DEFAULT_SEMANTIC_MODULE_ID
from tests.routing_test_helpers import build_current_route_artifacts_from_inputs

LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


def _unit_body_text(unit: dict) -> str:
    sentences = unit.get("sentences") or []
    return routed_body_text_from_sentences(
        sentences,
        source_stage=str(unit.get("source_stage") or "") or None,
    )


def _analysis_heading(
    block_id: str,
    *,
    analysis_text: str,
    stripped: str,
    level: int = 2,
) -> dict:
    return {
        "block_id": block_id,
        "kind": "heading",
        "analysis_text": analysis_text,
        "meta": {
            "heading_level": level,
            "heading_text_stripped": stripped,
        },
    }


def _paragraph(block_id: str, analysis_text: str) -> dict:
    return {
        "block_id": block_id,
        "kind": "paragraph",
        "analysis_text": analysis_text,
    }


def test_zone_matching_uses_structural_heading_not_analysis_text() -> None:
    """Matching source = structural metadata, not block analysis_text."""
    bundle = {
        "doc_id": "doc_001",
        "file_name": "doc_001.docx",
        "source_type": "docx",
        "content_blocks": [
            _analysis_heading(
                "h1",
                analysis_text="<<SPONSOR>> 5.2.1 临床安全性",
                stripped="临床安全性",
                level=3,
            ),
            _paragraph("p1", "analysis body"),
        ],
    }

    raw = extract_zones_from_bundle(
        bundle,
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )

    assert raw["matched_zone_count"] == 1
    match = raw["matched_zones"][0]["match"]
    assert match["matched_heading_text"] == "临床安全性"
    assert match["matched_term"] in {"临床安全性", "安全性"}


def test_public_filter_blocks_use_analysis_text_only() -> None:
    bundle = {
        "doc_id": "doc_001",
        "file_name": "doc_001.docx",
        "source_type": "docx",
        "content_blocks": [
            _analysis_heading(
                "h1",
                analysis_text="<<SPONSOR>> 5.2.1 临床安全性",
                stripped="临床安全性",
                level=3,
            ),
            _paragraph("p1", "analysis body text"),
        ],
    }

    public = to_public_filter_payload(
        extract_zones_from_bundle(
            bundle,
            resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
        )
    )
    heading = public["matched_zones"][0]["blocks"][0]
    assert "text" not in heading
    assert heading["analysis_text"] == "<<SPONSOR>> 5.2.1 临床安全性"
    assert "heading_text_stripped" not in (heading.get("meta") or {})


def test_public_heading_lineage_text_is_analysis() -> None:
    bundle = {
        "doc_id": "doc_001",
        "file_name": "doc_001.docx",
        "source_type": "docx",
        "content_blocks": [
            _analysis_heading(
                "h0",
                analysis_text="<<SITE>> 5 临床研究",
                stripped="临床研究",
                level=1,
            ),
            _analysis_heading(
                "h1",
                analysis_text="<<SPONSOR>> 5.2.1 临床安全性",
                stripped="临床安全性",
                level=3,
            ),
            _paragraph("p1", "analysis body"),
        ],
    }

    public = to_public_filter_payload(
        extract_zones_from_bundle(
            bundle,
            resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
        )
    )
    lineage = public["matched_zones"][0]["heading_lineage"]
    assert lineage[-1]["text"] == "<<SPONSOR>> 5.2.1 临床安全性"
    assert "heading_text_stripped" not in lineage[-1]


def test_debug_heading_lineage_text_is_structural() -> None:
    bundle = {
        "doc_id": "doc_001",
        "file_name": "doc_001.docx",
        "source_type": "docx",
        "content_blocks": [
            _analysis_heading(
                "h1",
                analysis_text="<<SPONSOR>> 5.2.1 临床安全性",
                stripped="临床安全性",
                level=3,
            ),
            _paragraph("p1", "analysis body"),
        ],
    }

    debug = to_debug_filter_payload(
        extract_zones_from_bundle(
            bundle,
            resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
        ),
        mask_result={
            "masked_blocks": [
                {
                    "block_id": "h1",
                    "original_text": "5.2.1 临床安全性",
                    "masked_text": "<<SPONSOR>> 5.2.1 临床安全性",
                }
            ]
        },
    )
    lineage = debug["matched_zones"][0]["heading_lineage"]
    assert lineage[-1]["text"] == "临床安全性"


def _boundary_doc_meta_bundle(*, doc_id: str = "doc_001") -> dict:
    return {
        "doc_meta_bundle_id": "doc_meta_boundary_test",
        "doc_id": doc_id,
        "file_hash": LINEAGE_FILE_HASH,
        "summary": {
            "doc_type": "IB",
            "study_drug": "StudyDrug_001",
            "sponsor": None,
            "investigator": None,
            "protocol_ids": [],
            "version": None,
            "document_date": None,
            "cutoff_date": None,
            "reporting_period": None,
        },
    }


def _boundary_block_manifest(*, doc_id: str = "doc_001") -> dict:
    return {
        "block_manifest_id": "block_manifest_boundary_test",
        "doc_id": doc_id,
        "file_hash": LINEAGE_FILE_HASH,
        "analysis_bundle_ref": {"analysis_bundle_id": "prepare_analysis_boundary"},
        "blocks": [
            {
                "block_id": "h1",
                "kind": "heading",
                "order": 1,
                "heading_path": ["<<SPONSOR>> 5.2.1 临床安全性"],
                "analysis_text": "<<SPONSOR>> 5.2.1 临床安全性",
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_boundary",
                    "block_id": "h1",
                },
            },
            {
                "block_id": "p1",
                "kind": "paragraph",
                "order": 2,
                "heading_path": ["<<SPONSOR>> 5.2.1 临床安全性"],
                "analysis_text": "analysis paragraph",
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_boundary",
                    "block_id": "p1",
                },
            },
        ],
    }


def _boundary_coverage_bundle(*, doc_id: str = "doc_001") -> dict:
    return {
        "coverage_bundle_id": "coverage_boundary_test",
        "doc_id": doc_id,
        "file_hash": LINEAGE_FILE_HASH,
        "block_manifest_ref": {"block_manifest_id": "block_manifest_boundary_test"},
        "analysis_bundle_ref": {"analysis_bundle_id": "prepare_analysis_boundary"},
        "zone_key": "ib_clinical_safety_zh",
        "coverage": [
            {
                "block_id": "h1",
                "block_kind": "heading",
                "order": 1,
                "heading_path": ["<<SPONSOR>> 5.2.1 临床安全性"],
                "selected_by_filter": True,
                "zone_match": {"zone_id": "Z0001"},
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_boundary",
                    "block_id": "h1",
                },
            },
            {
                "block_id": "p1",
                "block_kind": "paragraph",
                "order": 2,
                "heading_path": ["<<SPONSOR>> 5.2.1 临床安全性"],
                "selected_by_filter": True,
                "zone_match": {"zone_id": "Z0001"},
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_boundary",
                    "block_id": "p1",
                },
            },
        ],
    }


def _projected_sources_with_text(
    coverage_bundle: dict,
    text_by_block_id: dict[str, str],
) -> tuple:
    sources = []
    for row in coverage_bundle["coverage"]:
        block_id = str(row["block_id"])
        block_kind = str(row["block_kind"])
        sources.append(
            raw_projected_source(
                semantic_module_id=DEFAULT_SEMANTIC_MODULE_ID,
                block_id=block_id,
                block_kind=block_kind,
                heading_path=list(row.get("heading_path") or []),
                lineage={
                    "zone_key": str(coverage_bundle["zone_key"]),
                    "zone_id": str((row.get("zone_match") or {}).get("zone_id") or ""),
                },
                sentences=(
                    projected_sentence(
                        sentence_id=f"{block_id}:S001",
                        text=text_by_block_id[block_id],
                        source_block_id=block_id,
                    ),
                ),
            )
        )
    return tuple(sources)


def test_current_route_units_use_projected_text_not_match_audit() -> None:
    coverage_bundle = _boundary_coverage_bundle()
    artifacts = build_current_route_artifacts_from_inputs(
        coverage_bundle=coverage_bundle,
        block_manifest=_boundary_block_manifest(),
        doc_meta_bundle=_boundary_doc_meta_bundle(),
        projected_sources=_projected_sources_with_text(
            coverage_bundle,
            {
                "h1": "<<SPONSOR>> 5.2.1 临床安全性",
                "p1": "analysis paragraph",
            },
        ),
    )

    bundle = artifacts["routed_bundles"]["aggregate"]
    assert len(bundle["units"]) == 1
    unit = bundle["units"][0]
    # Text units include paragraph/list_item coverage rows only; headings
    # stay out of unit.text (see llm_input._is_text_candidate_row).
    # Headings provide context sentences but do not contribute to unit.text.
    assert _unit_body_text(unit) == "analysis paragraph"
    assert unit["heading_path"] == ["<<SPONSOR>> 5.2.1 临床安全性"]
    assert unit["context_block_ids"] == ["h1"]
    assert "context_sentences" not in unit
    assert unit["sentences"]
    assert "matched_heading_text" not in json.dumps(bundle, ensure_ascii=False)


def test_current_route_units_omit_forbidden_and_raw_text_fields() -> None:
    block_manifest = {
        "block_manifest_id": "block_manifest_boundary_test",
        "doc_id": "doc_001",
        "file_hash": LINEAGE_FILE_HASH,
        "analysis_bundle_ref": {"analysis_bundle_id": "prepare_analysis_boundary"},
        "blocks": [
            {
                "block_id": "p1",
                "kind": "paragraph",
                "order": 1,
                "heading_path": [],
                "analysis_text": "masked private text",
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_boundary",
                    "block_id": "p1",
                },
            }
        ],
    }
    coverage_bundle = {
        "coverage_bundle_id": "coverage_boundary_test",
        "doc_id": "doc_001",
        "file_hash": LINEAGE_FILE_HASH,
        "block_manifest_ref": {"block_manifest_id": "block_manifest_boundary_test"},
        "analysis_bundle_ref": {"analysis_bundle_id": "prepare_analysis_boundary"},
        "zone_key": "ib_clinical_safety_zh",
        "coverage": [
            {
                "block_id": "p1",
                "block_kind": "paragraph",
                "order": 1,
                "heading_path": [],
                "selected_by_filter": True,
                "text_ref": {
                    "analysis_bundle_id": "prepare_analysis_boundary",
                    "block_id": "p1",
                },
            }
        ],
    }

    artifacts = build_current_route_artifacts_from_inputs(
        coverage_bundle=coverage_bundle,
        block_manifest=block_manifest,
        doc_meta_bundle=_boundary_doc_meta_bundle(),
        projected_sources=_projected_sources_with_text(
            coverage_bundle,
            {"p1": "masked private text"},
        ),
    )

    bundle = artifacts["routed_bundles"]["aggregate"]
    serialized = json.dumps(bundle, ensure_ascii=False)
    for forbidden in (
        "normalized_text",
        "span_map",
        "source_ref",
        "document_meta",
        "privacy_transforms",
        "matched_rule",
        "evidence",
    ):
        assert f'"{forbidden}"' not in serialized
    assert _unit_body_text(bundle["units"][0]) == "masked private text"
    assert "raw private text" not in serialized
