"""Tests for Request File Intake (Step 0A)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.request_file_intake import (
    REQUEST_FILE_INTAKE_RESULT_ARTIFACT_TYPE,
    REQUEST_FILE_INTAKE_RESULT_SCHEMA_VERSION,
    build_request_file_intake_result,
    validate_request_file_intake_result,
)
from core.document.doc_identity import (
    FILE_HASH_PREFIX,
    SHA256_HEX_LENGTH,
    compute_content_hash,
    compute_file_hash,
)
from steps.request_file_intake import RequestFileInput, RequestFileIntakeStepResult, run


def _input(
    content: bytes,
    *,
    original_file_name: str,
) -> RequestFileInput:
    return RequestFileInput(content=content, original_file_name=original_file_name)


def test_same_bytes_same_filename_same_hash() -> None:
    content = b"same-content"
    first = run(_input(content, original_file_name="A.docx")).request_file_intake_result
    second = run(_input(content, original_file_name="A.docx")).request_file_intake_result
    assert first["document"]["file_hash"] == second["document"]["file_hash"]


def test_same_bytes_different_filenames_same_hash() -> None:
    content = b"same-content"
    first = run(_input(content, original_file_name="IB.docx")).request_file_intake_result
    second = run(_input(content, original_file_name="IB_copy.docx")).request_file_intake_result
    assert first["document"]["file_hash"] == second["document"]["file_hash"]
    assert first["document"]["original_file_name"] == "IB.docx"
    assert second["document"]["original_file_name"] == "IB_copy.docx"


def test_different_bytes_same_filename_different_hash() -> None:
    first = run(_input(b"version-a", original_file_name="IB.docx")).request_file_intake_result
    second = run(_input(b"version-b", original_file_name="IB.docx")).request_file_intake_result
    assert first["document"]["file_hash"] != second["document"]["file_hash"]


def test_hash_format_sha256_hex() -> None:
    result = run(_input(b"hello", original_file_name="sample.docx")).request_file_intake_result
    digest = result["document"]["file_hash"]
    assert digest.startswith(FILE_HASH_PREFIX)
    hex_part = digest.removeprefix(FILE_HASH_PREFIX)
    assert len(hex_part) == SHA256_HEX_LENGTH
    assert hex_part == hashlib.sha256(b"hello").hexdigest()


def test_compute_content_hash_matches_compute_file_hash(tmp_path: Path) -> None:
    docx = tmp_path / "sample.docx"
    content = b"chunked-equivalence"
    docx.write_bytes(content)
    assert compute_content_hash(content) == compute_file_hash(docx)


def test_one_input_produces_one_document_entry() -> None:
    result = run(_input(b"only", original_file_name="only.docx")).request_file_intake_result
    assert result["document"]["file_hash"] == compute_content_hash(b"only")
    assert result["document"]["original_file_name"] == "only.docx"


def test_repeated_execution_structurally_identical() -> None:
    record = _input(b"beta", original_file_name="b.docx")
    first = run(record)
    second = run(record)
    assert first == second


def test_validator_rejects_malformed_hash() -> None:
    payload = build_request_file_intake_result(
        file_hash=compute_content_hash(b"ok"),
        original_file_name="ok.docx",
    )
    payload["document"]["file_hash"] = "sha256:not-hex"
    with pytest.raises(ValueError, match="hex segment"):
        validate_request_file_intake_result(payload)


def test_validator_rejects_unexpected_root_keys() -> None:
    payload = build_request_file_intake_result(
        file_hash=compute_content_hash(b"ok"),
        original_file_name="ok.docx",
    )
    payload["doc_id"] = "doc_should_not_exist"
    with pytest.raises(ValueError, match="unexpected root keys"):
        validate_request_file_intake_result(payload)


def test_validator_rejects_documents_collection_key() -> None:
    payload = {
        "artifact_type": REQUEST_FILE_INTAKE_RESULT_ARTIFACT_TYPE,
        "schema_version": REQUEST_FILE_INTAKE_RESULT_SCHEMA_VERSION,
        "documents": [
            {
                "file_hash": compute_content_hash(b"ok"),
                "original_file_name": "ok.docx",
            }
        ],
    }
    with pytest.raises(ValueError, match="unexpected root keys"):
        validate_request_file_intake_result(payload)


def test_output_has_no_doc_id_or_clinical_fields() -> None:
    result = run(_input(b"payload", original_file_name="payload.docx")).request_file_intake_result
    serialized = json.dumps(result, ensure_ascii=False)
    for forbidden in (
        "doc_id",
        "source_path",
        "document_type",
        "zone_key",
        "comparison_profile",
        "clinical_program_id",
    ):
        assert forbidden not in serialized


def test_step_does_not_require_filesystem_paths() -> None:
    result = run(_input(b"in-memory-only", original_file_name="memory.docx")).request_file_intake_result
    assert result["artifact_type"] == REQUEST_FILE_INTAKE_RESULT_ARTIFACT_TYPE
    assert result["document"]["file_hash"] == compute_content_hash(b"in-memory-only")


def test_wrong_artifact_type_rejected() -> None:
    payload = build_request_file_intake_result(
        file_hash=compute_content_hash(b"ok"),
        original_file_name="ok.docx",
    )
    payload["artifact_type"] = "wrong_type"
    with pytest.raises(ValueError, match="artifact_type must be"):
        validate_request_file_intake_result(payload)


def test_wrong_schema_version_rejected() -> None:
    payload = build_request_file_intake_result(
        file_hash=compute_content_hash(b"ok"),
        original_file_name="ok.docx",
    )
    payload["schema_version"] = "9.9.9"
    with pytest.raises(ValueError, match="schema_version must be"):
        validate_request_file_intake_result(payload)


def test_one_input_produces_canonical_document_hash() -> None:
    step_result = run(_input(b"only", original_file_name="only.docx"))
    assert step_result.request_file_intake_result["document"]["file_hash"] == (
        compute_content_hash(b"only")
    )


def test_trace_has_no_path_data() -> None:
    step_result = run(_input(b"x", original_file_name="x.docx"))
    formal = step_result.request_file_intake_result
    assert "source_path" not in json.dumps(formal, ensure_ascii=False)


def test_step_result_is_request_file_intake_step_result() -> None:
    step_result = run(_input(b"x", original_file_name="x.docx"))
    assert isinstance(step_result, RequestFileIntakeStepResult)


@patch("steps.request_file_intake.compute_content_hash")
def test_step_uses_core_hash_primitive(mock_hash) -> None:
    mock_hash.return_value = "sha256:" + "c" * 64
    step_result = run(_input(b"payload", original_file_name="payload.docx"))
    mock_hash.assert_called_once_with(b"payload")
    assert step_result.request_file_intake_result["document"]["file_hash"] == (
        "sha256:" + "c" * 64
    )


def test_builder_requires_file_hash_and_original_file_name() -> None:
    with pytest.raises(ValueError, match="document.original_file_name is required"):
        build_request_file_intake_result(
            file_hash=compute_content_hash(b"ok"),
            original_file_name="",
        )
