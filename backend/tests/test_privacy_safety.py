from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.privacy_safety import (
    assert_no_forbidden_keys,
    assert_no_forbidden_path_patterns,
    assert_no_raw_term_leaks,
    path_ends_with_pattern,
    scan_raw_term_leaks,
    walk_forbidden_keys,
    walk_forbidden_path_patterns,
    PUBLIC_ANALYSIS_BUNDLE_FORBIDDEN_KEYS,
    PUBLIC_ANALYSIS_BUNDLE_FORBIDDEN_PATH_SUFFIXES,
)


def test_path_ends_with_pattern_wildcard_segment() -> None:
    parts = ["artifact", "content_blocks", "2", "sentences", "0", "normalized_text"]
    assert path_ends_with_pattern(parts, ("sentences", "*", "normalized_text"))
    assert not path_ends_with_pattern(parts, ("sentences", "normalized_text"))


def test_walk_forbidden_keys_finds_nested_key() -> None:
    payload = {"content_blocks": [{"block_id": "C1", "normalized_text": "raw"}]}
    hits = walk_forbidden_keys(payload, frozenset({"normalized_text"}), root_label="bundle")
    assert len(hits) == 1
    assert hits[0].key == "normalized_text"
    assert hits[0].path.endswith(".normalized_text")


def test_walk_forbidden_keys_allows_sentences_container() -> None:
    payload = {
        "content_blocks": [
            {
                "block_id": "C1",
                "sentences": [{"sentence_id": "C1:S001", "analysis_text": "masked"}],
            }
        ]
    }
    hits = walk_forbidden_keys(
        payload,
        PUBLIC_ANALYSIS_BUNDLE_FORBIDDEN_KEYS,
        root_label="bundle",
    )
    assert hits == []


def test_walk_forbidden_path_patterns_finds_sentence_normalized_text() -> None:
    payload = {
        "content_blocks": [
            {
                "block_id": "C1",
                "sentences": [
                    {
                        "sentence_id": "C1:S001",
                        "analysis_text": "masked",
                        "normalized_text": "raw",
                    }
                ],
            }
        ]
    }
    hits = walk_forbidden_path_patterns(
        payload,
        PUBLIC_ANALYSIS_BUNDLE_FORBIDDEN_PATH_SUFFIXES,
        root_label="bundle",
    )
    assert any(hit.path.endswith(".normalized_text") for hit in hits)


def test_scan_raw_term_leaks_finds_term() -> None:
    payload = {"heading_path": ["6.1 VT8802 I期研究"]}
    hits = scan_raw_term_leaks(payload, ["VT8802"], root_label="bundle")
    assert len(hits) == 1
    assert hits[0].term == "VT8802"


def test_scan_raw_term_leaks_does_not_false_positive_masked_token() -> None:
    payload = {"analysis_text": "StudyDrug_001 body"}
    hits = scan_raw_term_leaks(payload, ["VT8802"], root_label="bundle")
    assert hits == []


def test_assert_helpers_raise_with_path() -> None:
    payload = {"normalized_text": "raw"}
    try:
        assert_no_forbidden_keys(payload, {"normalized_text"}, label="bundle")
    except ValueError as exc:
        assert "normalized_text" in str(exc)
    else:
        raise AssertionError("expected ValueError")

    try:
        assert_no_raw_term_leaks(payload, ["raw"], label="bundle")
    except ValueError as exc:
        assert "raw" in str(exc)
    else:
        raise AssertionError("expected ValueError")

    nested = {"sentences": [{"normalized_text": "raw"}]}
    try:
        assert_no_forbidden_path_patterns(
            nested,
            PUBLIC_ANALYSIS_BUNDLE_FORBIDDEN_PATH_SUFFIXES,
            label="bundle",
        )
    except ValueError as exc:
        assert "sentences" in str(exc)
    else:
        raise AssertionError("expected ValueError")
