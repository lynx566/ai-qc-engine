"""Targeted tests for finding review state artifact contract."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.finding_review_state import (
    FINDING_REVIEW_STATE_LEGACY_SCHEMA_VERSION,
    FINDING_REVIEW_STATE_SCHEMA_VERSION,
    FINDING_REVIEW_STATE_V020_SCHEMA_VERSION,
    build_finding_review_state_payload,
    should_persist_finding_review_entry,
    validate_finding_review_entry,
    validate_finding_review_state,
)


def test_valid_empty_artifact() -> None:
    payload = build_finding_review_state_payload(
        flow_run_id="document_consistency_qc_test",
        findings={},
    )
    assert payload["findings"] == {}
    assert payload["schema_version"] == FINDING_REVIEW_STATE_SCHEMA_VERSION


def test_valid_confirmed_entry() -> None:
    payload = build_finding_review_state_payload(
        flow_run_id="document_consistency_qc_test",
        findings={
            "L001": {
                "decision": "confirmed",
                "marked": False,
                "updated_at": "2026-09-13T00:00:00Z",
            }
        },
    )
    assert payload["findings"]["L001"]["decision"] == "confirmed"
    assert payload["findings"]["L001"]["marked"] is False


def test_valid_ignored_entry() -> None:
    payload = build_finding_review_state_payload(
        flow_run_id="document_consistency_qc_test",
        findings={
            "L005": {
                "decision": "ignored",
                "marked": False,
                "updated_at": "2026-09-13T00:00:00Z",
            }
        },
    )
    assert payload["findings"]["L005"]["decision"] == "ignored"


def test_v020_resolved_reads_as_confirmed() -> None:
    payload = validate_finding_review_state(
        {
            "artifact_type": "document_consistency_qc_finding_review_state",
            "schema_version": FINDING_REVIEW_STATE_V020_SCHEMA_VERSION,
            "flow_run_id": "document_consistency_qc_test",
            "findings": {
                "L001": {
                    "resolved": True,
                    "marked": False,
                    "updated_at": "2026-09-13T00:00:00Z",
                }
            },
        }
    )
    assert payload["schema_version"] == FINDING_REVIEW_STATE_SCHEMA_VERSION
    assert payload["findings"]["L001"]["decision"] == "confirmed"


def test_valid_marked_with_note() -> None:
    payload = build_finding_review_state_payload(
        flow_run_id="document_consistency_qc_test",
        findings={
            "L002": {
                "decision": "pending",
                "marked": True,
                "note": "follow up",
                "updated_at": "2026-09-13T00:00:00Z",
            }
        },
    )
    assert payload["findings"]["L002"]["marked"] is True
    assert payload["findings"]["L002"]["note"] == "follow up"


def test_valid_confirmed_and_marked_together() -> None:
    payload = build_finding_review_state_payload(
        flow_run_id="document_consistency_qc_test",
        findings={
            "L003": {
                "decision": "confirmed",
                "marked": True,
                "updated_at": "2026-09-13T00:00:00Z",
            }
        },
    )
    assert payload["findings"]["L003"]["decision"] == "confirmed"
    assert payload["findings"]["L003"]["marked"] is True


def test_note_only_entry_persists() -> None:
    payload = build_finding_review_state_payload(
        flow_run_id="document_consistency_qc_test",
        findings={
            "L004": {
                "decision": "pending",
                "marked": False,
                "note": "memo",
                "updated_at": "2026-09-13T00:00:00Z",
            }
        },
    )
    assert payload["findings"]["L004"]["note"] == "memo"


def test_invalid_boolean_rejected() -> None:
    with pytest.raises(TypeError, match="marked must be a boolean"):
        validate_finding_review_entry(
            {
                "decision": "confirmed",
                "marked": "yes",
                "updated_at": "2026-09-13T00:00:00Z",
            },
            finding_id="L001",
        )


def test_malformed_note_rejected() -> None:
    with pytest.raises(TypeError, match="note must be a string"):
        validate_finding_review_entry(
            {
                "decision": "confirmed",
                "marked": False,
                "note": 123,
                "updated_at": "2026-09-13T00:00:00Z",
            },
            finding_id="L001",
        )


def test_sparse_defaults_not_persisted() -> None:
    assert (
        should_persist_finding_review_entry(
            decision="pending",
            marked=False,
            note=None,
        )
        is False
    )


def test_sparse_confirmed_is_persisted() -> None:
    assert should_persist_finding_review_entry(
        decision="confirmed",
        marked=False,
        note=None,
    ) is True


def test_sparse_ignored_is_persisted() -> None:
    assert should_persist_finding_review_entry(
        decision="ignored",
        marked=False,
        note=None,
    ) is True


def test_sparse_marked_is_persisted() -> None:
    assert should_persist_finding_review_entry(
        decision="pending",
        marked=True,
        note=None,
    ) is True


def test_sparse_note_is_persisted() -> None:
    assert (
        should_persist_finding_review_entry(
            decision="pending",
            marked=False,
            note="memo",
        )
        is True
    )


def test_sparse_defaults_in_artifact_rejected() -> None:
    with pytest.raises(ValueError, match="requires decision confirmed/ignored"):
        validate_finding_review_state(
            {
                "artifact_type": "document_consistency_qc_finding_review_state",
                "schema_version": FINDING_REVIEW_STATE_SCHEMA_VERSION,
                "flow_run_id": "document_consistency_qc_test",
                "findings": {
                    "L001": {
                        "decision": "pending",
                        "marked": False,
                        "updated_at": "2026-09-13T00:00:00Z",
                    }
                },
            }
        )


def test_invalid_finding_id_rejected() -> None:
    with pytest.raises(ValueError, match="finding_id must match"):
        validate_finding_review_entry(
            {
                "decision": "confirmed",
                "marked": False,
                "updated_at": "2026-09-13T00:00:00Z",
            },
            finding_id="F001",
        )


def test_legacy_normal_maps_to_pending() -> None:
    payload = validate_finding_review_state(
        {
            "artifact_type": "document_consistency_qc_finding_review_state",
            "schema_version": FINDING_REVIEW_STATE_LEGACY_SCHEMA_VERSION,
            "flow_run_id": "document_consistency_qc_test",
            "findings": {
                "L001": {
                    "review_state": "normal",
                    "note": "memo",
                    "updated_at": "2026-09-13T00:00:00Z",
                }
            },
        }
    )
    entry = payload["findings"]["L001"]
    assert entry["decision"] == "pending"
    assert entry["marked"] is False
    assert entry["note"] == "memo"


def test_legacy_reviewed_maps_to_confirmed() -> None:
    payload = validate_finding_review_state(
        {
            "artifact_type": "document_consistency_qc_finding_review_state",
            "schema_version": FINDING_REVIEW_STATE_LEGACY_SCHEMA_VERSION,
            "flow_run_id": "document_consistency_qc_test",
            "findings": {
                "L001": {
                    "review_state": "reviewed",
                    "updated_at": "2026-09-13T00:00:00Z",
                }
            },
        }
    )
    entry = payload["findings"]["L001"]
    assert entry["decision"] == "confirmed"
    assert entry["marked"] is False


def test_legacy_flagged_maps_to_marked() -> None:
    payload = validate_finding_review_state(
        {
            "artifact_type": "document_consistency_qc_finding_review_state",
            "schema_version": FINDING_REVIEW_STATE_LEGACY_SCHEMA_VERSION,
            "flow_run_id": "document_consistency_qc_test",
            "findings": {
                "L002": {
                    "review_state": "flagged",
                    "note": "keep",
                    "updated_at": "2026-09-13T00:00:00Z",
                }
            },
        }
    )
    entry = payload["findings"]["L002"]
    assert entry["decision"] == "pending"
    assert entry["marked"] is True
    assert entry["note"] == "keep"
