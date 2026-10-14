"""Minimal current Evidence Comparison source fixtures for tests."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_evidence_source_bundle import (
    AGGREGATE_EVIDENCE_SOURCE_BUNDLE_FILENAME,
    build_aggregate_evidence_source_bundle,
)
from runtime.io import save_json


def write_current_ec_source_fixture(
    root: Path,
    *,
    label: str,
    document_type: str,
    heading_paths: Sequence[Sequence[str]],
) -> Path:
    """Persist one small current aggregate-evidence source bundle."""

    scopes = []
    for index, heading_path in enumerate(heading_paths, start=1):
        scope_id = f"scope_{label}_{index:02d}"
        unit_id = f"unit_{label}_{index:02d}"
        sentence_id = f"sentence_{label}_{index:02d}"
        block_id = f"block_{label}_{index:02d}"
        text = f"{label} evidence sentence {index}."
        scopes.append(
            {
                "scope_id": scope_id,
                "scope_order": index - 1,
                "heading_path": list(heading_path),
                "units": [
                    {
                        "unit_id": unit_id,
                        "unit_order": 0,
                        "text": text,
                        "source": {"block_ids": [block_id]},
                        "sentences": [
                            {
                                "sentence_id": sentence_id,
                                "sentence_order": 0,
                                "text": text,
                                "source_block_ids": [block_id],
                            }
                        ],
                    }
                ],
            }
        )

    bundle = build_aggregate_evidence_source_bundle(
        doc_id=f"doc_{label}",
        file_hash=f"sha256:{label}",
        document_type=document_type,
        heading_scopes=scopes,
    )
    output_path = root / label / AGGREGATE_EVIDENCE_SOURCE_BUNDLE_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(output_path, bundle)
    return output_path


__all__ = ["write_current_ec_source_fixture"]
